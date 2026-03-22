#!/usr/bin/env python
"""Train and evaluate generic-food role classification models."""

from __future__ import annotations

import argparse
from collections import Counter
import csv
import json
from pathlib import Path

from joblib import dump
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction import DictVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score
from sklearn.model_selection import GridSearchCV, StratifiedKFold, cross_val_predict
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import MaxAbsScaler

from dietdashboard import food_role_model

RANDOM_STATE = 42


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset",
        type=Path,
        default=food_role_model.default_dataset_path(),
        help="Path to the training dataset CSV.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=food_role_model.default_model_dir(),
        help="Directory for model artifacts and evaluation outputs.",
    )
    return parser.parse_args()


def _ensure_dataset(dataset_path: Path) -> Path:
    if dataset_path.exists():
        return dataset_path
    dataset_path.parent.mkdir(parents=True, exist_ok=True)
    food_role_model.write_training_dataset(dataset_path)
    return dataset_path


def _load_dataset(dataset_path: Path) -> tuple[list[dict[str, object]], list[str], list[dict[str, str]]]:
    rows: list[dict[str, object]] = []
    labels: list[str] = []
    metadata: list[dict[str, str]] = []
    with dataset_path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            features: dict[str, object] = {}
            for field in food_role_model.NUMERIC_FEATURES:
                features[field] = float(row[field] or 0.0)
            for field in food_role_model.BOOLEAN_FEATURES:
                features[field] = float(row[field] or 0.0)
            for field in food_role_model.CATEGORICAL_FEATURES:
                features[field] = row[field]
            rows.append(features)
            labels.append(row["label_role"])
            metadata.append(
                {
                    "generic_food_id": row["generic_food_id"],
                    "display_name": row["display_name"],
                    "label_source": row["label_source"],
                }
            )
    return rows, labels, metadata


def _model_specs() -> list[tuple[str, Pipeline, dict[str, list[object]]]]:
    logistic_pipeline = Pipeline(
        [
            ("vectorizer", DictVectorizer(sparse=True)),
            ("scaler", MaxAbsScaler()),
            (
                "classifier",
                LogisticRegression(
                    max_iter=5000,
                    random_state=RANDOM_STATE,
                ),
            ),
        ]
    )
    random_forest_pipeline = Pipeline(
        [
            ("vectorizer", DictVectorizer(sparse=False)),
            (
                "classifier",
                RandomForestClassifier(
                    random_state=RANDOM_STATE,
                ),
            ),
        ]
    )
    return [
        (
            "logistic_regression",
            logistic_pipeline,
            {
                "classifier__C": [0.25, 1.0, 4.0],
                "classifier__class_weight": [None, "balanced"],
            },
        ),
        (
            "random_forest",
            random_forest_pipeline,
            {
                "classifier__n_estimators": [200, 400],
                "classifier__max_depth": [4, 8, None],
                "classifier__min_samples_leaf": [1, 2, 4],
                "classifier__class_weight": [None, "balanced"],
            },
        ),
    ]


def _evaluate_model(
    name: str,
    search: GridSearchCV,
    X: list[dict[str, object]],
    y: list[str],
    cv: StratifiedKFold,
) -> dict[str, object]:
    best_estimator = search.best_estimator_
    predictions = cross_val_predict(best_estimator, X, y, cv=cv, n_jobs=-1)
    report = classification_report(y, predictions, output_dict=True, zero_division=0)
    return {
        "model_name": name,
        "best_params": search.best_params_,
        "cv_macro_f1": round(float(search.best_score_), 4),
        "accuracy": round(float(accuracy_score(y, predictions)), 4),
        "macro_f1": round(float(f1_score(y, predictions, average="macro")), 4),
        "weighted_f1": round(float(f1_score(y, predictions, average="weighted")), 4),
        "predictions": list(predictions),
        "classification_report": report,
    }


def _selected_result(results: list[dict[str, object]]) -> dict[str, object]:
    return sorted(
        results,
        key=lambda result: (
            -float(result["macro_f1"]),
            result["model_name"] != "logistic_regression",
        ),
    )[0]


def _write_confusion_matrix(output_path: Path, y_true: list[str], y_pred: list[str]) -> None:
    labels = list(food_role_model.ROLE_LABELS)
    matrix = confusion_matrix(y_true, y_pred, labels=labels)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["true_label", *labels])
        for label, row in zip(labels, matrix, strict=True):
            writer.writerow([label, *row.tolist()])


def _write_oof_predictions(
    output_path: Path,
    y_true: list[str],
    y_pred: list[str],
    metadata: list[dict[str, str]],
) -> None:
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["generic_food_id", "display_name", "label_source", "true_label", "predicted_label", "correct"])
        for item, true_label, predicted_label in zip(metadata, y_true, y_pred, strict=True):
            writer.writerow(
                [
                    item["generic_food_id"],
                    item["display_name"],
                    item["label_source"],
                    true_label,
                    predicted_label,
                    int(true_label == predicted_label),
                ]
            )


def _write_feature_summary(model_name: str, estimator: Pipeline, output_path: Path) -> str:
    vectorizer = estimator.named_steps["vectorizer"]
    feature_names = vectorizer.get_feature_names_out()
    classifier = estimator.named_steps["classifier"]

    if model_name == "logistic_regression":
        rows: list[list[object]] = []
        for class_index, class_name in enumerate(classifier.classes_):
            class_coefficients = classifier.coef_[class_index]
            top_indices = sorted(range(len(feature_names)), key=lambda idx: class_coefficients[idx], reverse=True)[:12]
            for index in top_indices:
                rows.append([class_name, feature_names[index], round(float(class_coefficients[index]), 6)])
        with output_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["label_role", "feature_name", "coefficient"])
            writer.writerows(rows)
        return "logistic_coefficients"

    importances = classifier.feature_importances_
    top_indices = sorted(range(len(feature_names)), key=lambda idx: importances[idx], reverse=True)[:25]
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["feature_name", "importance"])
        for index in top_indices:
            writer.writerow([feature_names[index], round(float(importances[index]), 6)])
    return "random_forest_feature_importance"


def main() -> int:
    args = parse_args()
    dataset_path = _ensure_dataset(args.dataset)
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    X, y, metadata = _load_dataset(dataset_path)
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)

    results: list[dict[str, object]] = []
    for model_name, pipeline, param_grid in _model_specs():
        search = GridSearchCV(
            pipeline,
            param_grid=param_grid,
            scoring="f1_macro",
            cv=cv,
            n_jobs=-1,
            refit=True,
        )
        search.fit(X, y)
        results.append(_evaluate_model(model_name, search, X, y, cv))

    selected = _selected_result(results)
    selected_name = str(selected["model_name"])

    selected_pipeline = next(pipeline for name, pipeline, _grid in _model_specs() if name == selected_name)
    selected_pipeline.set_params(**selected["best_params"])
    selected_pipeline.fit(X, y)

    model_artifact_path = output_dir / "generic_food_role_classifier.joblib"
    evaluation_path = output_dir / "role_model_evaluation.json"
    confusion_matrix_path = output_dir / "role_model_confusion_matrix.csv"
    feature_summary_path = output_dir / "role_model_feature_summary.csv"
    comparison_path = output_dir / "role_model_comparison.json"
    predictions_path = output_dir / "role_model_oof_predictions.csv"

    dump(
        {
            "model_name": selected_name,
            "pipeline": selected_pipeline,
            "label_names": list(food_role_model.ROLE_LABELS),
            "feature_fields": {
                "numeric": list(food_role_model.NUMERIC_FEATURES),
                "boolean": list(food_role_model.BOOLEAN_FEATURES),
                "categorical": list(food_role_model.CATEGORICAL_FEATURES),
            },
            "training_dataset_path": str(dataset_path),
        },
        model_artifact_path,
    )

    _write_confusion_matrix(confusion_matrix_path, y, list(selected["predictions"]))
    _write_oof_predictions(predictions_path, y, list(selected["predictions"]), metadata)
    feature_summary_kind = _write_feature_summary(selected_name, selected_pipeline, feature_summary_path)

    comparison_payload = {
        "dataset_path": str(dataset_path),
        "dataset_size": len(y),
        "label_distribution": dict(sorted(Counter(y).items())),
        "label_source_distribution": dict(sorted(Counter(item["label_source"] for item in metadata).items())),
        "models": [
            {
                "model_name": result["model_name"],
                "best_params": result["best_params"],
                "cv_macro_f1": result["cv_macro_f1"],
                "accuracy": result["accuracy"],
                "macro_f1": result["macro_f1"],
                "weighted_f1": result["weighted_f1"],
            }
            for result in results
        ],
        "selected_model": selected_name,
    }
    comparison_path.write_text(json.dumps(comparison_payload, indent=2, sort_keys=True), encoding="utf-8")

    selected_report = selected["classification_report"]
    evaluation_payload = {
        "dataset_path": str(dataset_path),
        "dataset_size": len(y),
        "label_distribution": dict(sorted(Counter(y).items())),
        "label_source_distribution": dict(sorted(Counter(item["label_source"] for item in metadata).items())),
        "validation_method": {
            "type": "stratified_k_fold",
            "n_splits": 5,
            "shuffle": True,
            "random_state": RANDOM_STATE,
        },
        "selected_model": {
            "model_name": selected_name,
            "best_params": selected["best_params"],
            "accuracy": selected["accuracy"],
            "macro_f1": selected["macro_f1"],
            "weighted_f1": selected["weighted_f1"],
            "feature_summary_kind": feature_summary_kind,
            "model_artifact_path": str(model_artifact_path),
            "confusion_matrix_path": str(confusion_matrix_path),
            "feature_summary_path": str(feature_summary_path),
            "predictions_path": str(predictions_path),
        },
        "per_class_metrics": {
            label: {
                "precision": round(float(selected_report[label]["precision"]), 4),
                "recall": round(float(selected_report[label]["recall"]), 4),
                "f1_score": round(float(selected_report[label]["f1-score"]), 4),
                "support": int(selected_report[label]["support"]),
            }
            for label in food_role_model.ROLE_LABELS
        },
        "overall_metrics": {
            "accuracy": selected["accuracy"],
            "macro_f1": selected["macro_f1"],
            "weighted_f1": selected["weighted_f1"],
        },
    }
    evaluation_path.write_text(json.dumps(evaluation_payload, indent=2, sort_keys=True), encoding="utf-8")

    print(f"dataset_path={dataset_path}")
    print(f"model_artifact_path={model_artifact_path}")
    print(f"evaluation_path={evaluation_path}")
    print(f"selected_model={selected_name}")
    print(f"overall_metrics={evaluation_payload['overall_metrics']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
