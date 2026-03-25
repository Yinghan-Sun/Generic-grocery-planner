"""Artifact loading, training, and scoring for learned candidate generation."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path

from joblib import dump, load
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.feature_extraction import DictVectorizer
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, log_loss, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import MaxAbsScaler

from dietdashboard import model_candidate_features as features

DEFAULT_RANDOM_SEED = 42
PRIMARY_TUNING_METRIC = "validation_role_recall_at_budget"


class ModelCandidateArtifactError(RuntimeError):
    """Raised when the learned candidate-generator artifact is missing or invalid."""


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def default_model_dir() -> Path:
    return project_root() / "artifacts" / "candidate_generator"


def default_model_path() -> Path:
    return default_model_dir() / "candidate_generator_best.joblib"


def default_backend_model_dir() -> Path:
    return default_model_dir() / "models"


def default_backend_model_path(backend: str) -> Path:
    return default_backend_model_dir() / f"candidate_generator_{resolve_backend(backend)}.joblib"


def default_metrics_path() -> Path:
    return default_model_dir() / "candidate_generator_training_metrics.json"


def default_feature_summary_path() -> Path:
    return default_model_dir() / "candidate_generator_feature_summary.csv"


def available_backends() -> list[str]:
    return ["logistic_regression", "random_forest", "hist_gradient_boosting"]


def resolve_backend(requested: str = "auto") -> str:
    if requested == "auto":
        return "hist_gradient_boosting"
    if requested not in available_backends():
        raise ValueError(f"Unsupported candidate-generator backend: {requested}")
    return requested


def _feature_row(row: Mapping[str, object]) -> dict[str, object]:
    return {
        field: row[field]
        for field in (*features.NUMERIC_FEATURES, *features.BOOLEAN_FEATURES, *features.CATEGORICAL_FEATURES)
    }


def _label(row: Mapping[str, object]) -> int:
    value = row.get("label_selected")
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _build_pipeline(
    *,
    backend: str,
    random_seed: int,
    hyperparameters: Mapping[str, object] | None = None,
) -> Pipeline:
    params = dict(hyperparameters or {})
    resolved_backend = resolve_backend(backend)
    if resolved_backend == "logistic_regression":
        classifier = LogisticRegression(
            C=float(params.get("C", 1.0)),
            class_weight=params.get("class_weight"),
            max_iter=int(params.get("max_iter", 4000)),
            random_state=random_seed,
        )
        return Pipeline(
            [
                ("vectorizer", DictVectorizer(sparse=True)),
                ("scaler", MaxAbsScaler()),
                ("classifier", classifier),
            ]
        )
    if resolved_backend == "random_forest":
        classifier = RandomForestClassifier(
            n_estimators=int(params.get("n_estimators", 300)),
            max_depth=None if params.get("max_depth") in {None, "none"} else int(params["max_depth"]),
            min_samples_leaf=int(params.get("min_samples_leaf", 1)),
            max_features=params.get("max_features", "sqrt"),
            class_weight=params.get("class_weight"),
            random_state=random_seed,
            n_jobs=-1,
        )
        return Pipeline(
            [
                ("vectorizer", DictVectorizer(sparse=False)),
                ("classifier", classifier),
            ]
        )
    classifier = HistGradientBoostingClassifier(
        learning_rate=float(params.get("learning_rate", 0.08)),
        max_depth=None if params.get("max_depth") in {None, "none"} else int(params["max_depth"]),
        max_leaf_nodes=int(params.get("max_leaf_nodes", 31)),
        min_samples_leaf=int(params.get("min_samples_leaf", 20)),
        l2_regularization=float(params.get("l2_regularization", 0.0)),
        random_state=random_seed,
    )
    return Pipeline(
        [
            ("vectorizer", DictVectorizer(sparse=False)),
            ("classifier", classifier),
        ]
    )


def _fit_pipeline(
    rows: Sequence[Mapping[str, object]],
    *,
    backend: str,
    random_seed: int,
    hyperparameters: Mapping[str, object] | None = None,
) -> Pipeline:
    if not rows:
        raise ValueError("Training rows are required.")
    X = [_feature_row(row) for row in rows]
    y = [_label(row) for row in rows]
    positive_count = sum(y)
    negative_count = len(y) - positive_count
    positive_weight = (negative_count / positive_count) if positive_count and negative_count else 1.0
    sample_weight = [positive_weight if label == 1 else 1.0 for label in y]
    pipeline = _build_pipeline(
        backend=backend,
        random_seed=random_seed,
        hyperparameters=hyperparameters,
    )
    pipeline.fit(X, y, classifier__sample_weight=sample_weight)
    return pipeline


def _predict_probabilities(pipeline: Pipeline, rows: Sequence[Mapping[str, object]]) -> list[float]:
    if not rows:
        return []
    X = [_feature_row(row) for row in rows]
    try:
        probabilities = pipeline.predict_proba(X)
    except Exception as exc:  # noqa: BLE001
        raise ModelCandidateArtifactError(f"Candidate-generator artifact could not score foods: {exc}") from exc
    return [float(row[1]) for row in probabilities]


def _safe_metric(metric_name: str, y_true: Sequence[int], y_prob: Sequence[float]) -> float:
    positive_count = sum(y_true)
    if not y_true or positive_count == 0 or positive_count == len(y_true):
        return 0.0
    if metric_name == "average_precision":
        return float(average_precision_score(y_true, y_prob))
    if metric_name == "roc_auc":
        return float(roc_auc_score(y_true, y_prob))
    if metric_name == "log_loss":
        return float(log_loss(y_true, y_prob, labels=[0, 1]))
    if metric_name == "brier":
        return float(brier_score_loss(y_true, y_prob))
    raise ValueError(f"Unsupported metric: {metric_name}")


def _group_budget_metrics(rows: Sequence[Mapping[str, object]], probabilities: Sequence[float], prefix: str) -> dict[str, float]:
    grouped_rows: dict[tuple[str, str], list[tuple[int, Mapping[str, object], float]]] = defaultdict(list)
    for index, (row, probability) in enumerate(zip(rows, probabilities, strict=True)):
        grouped_rows[(str(row["scenario_id"]), str(row["role"]))].append((index, row, float(probability)))

    role_hit_rates: list[float] = []
    role_recall_rates: list[float] = []
    role_exact_match_rates: list[float] = []
    role_jaccards: list[float] = []
    scenario_success: dict[str, list[int]] = defaultdict(list)
    scenario_jaccards: dict[str, list[float]] = defaultdict(list)

    for (scenario_id, _role), group_rows in grouped_rows.items():
        positives = {index for index, row, _probability in group_rows if _label(row) == 1}
        if not positives:
            continue
        budget = max(1, len(positives))
        ranked = sorted(
            group_rows,
            key=lambda item: (
                -item[2],
                float(item[1].get("heuristic_role_rank", 10_000)),
                str(item[1].get("display_name") or ""),
                str(item[1].get("generic_food_id") or ""),
            ),
        )
        predicted = {index for index, _row, _probability in ranked[:budget]}
        true_positive_count = len(positives)
        overlap = len(predicted & positives)
        union = len(predicted | positives)
        hit = int(overlap > 0)
        recall = overlap / true_positive_count
        exact_match = int(predicted == positives)
        jaccard = (overlap / union) if union else 0.0
        role_hit_rates.append(hit)
        role_recall_rates.append(recall)
        role_exact_match_rates.append(exact_match)
        role_jaccards.append(jaccard)
        scenario_success[scenario_id].append(exact_match)
        scenario_jaccards[scenario_id].append(jaccard)

    scenario_exact_rates = [int(all(values)) for values in scenario_success.values() if values]
    scenario_mean_jaccards = [sum(values) / len(values) for values in scenario_jaccards.values() if values]

    def average(values: Sequence[float | int]) -> float:
        if not values:
            return 0.0
        return round(float(sum(values) / len(values)), 6)

    return {
        f"{prefix}_role_hit_rate_at_budget": average(role_hit_rates),
        f"{prefix}_role_recall_at_budget": average(role_recall_rates),
        f"{prefix}_role_exact_match_rate": average(role_exact_match_rates),
        f"{prefix}_role_mean_jaccard": average(role_jaccards),
        f"{prefix}_scenario_exact_seed_rate": average(scenario_exact_rates),
        f"{prefix}_scenario_mean_jaccard": average(scenario_mean_jaccards),
    }


def evaluate_rows(
    bundle: Mapping[str, object],
    rows: Sequence[Mapping[str, object]],
    *,
    prefix: str,
) -> dict[str, object]:
    pipeline = bundle.get("pipeline")
    if pipeline is None:
        raise ModelCandidateArtifactError("Loaded candidate-generator artifact is invalid: missing fitted pipeline.")
    probabilities = _predict_probabilities(pipeline, rows)
    labels = [_label(row) for row in rows]
    metrics: dict[str, object] = {
        f"{prefix}_row_count": len(rows),
        f"{prefix}_positive_rate": round((sum(labels) / len(labels)) if labels else 0.0, 6),
        f"{prefix}_average_precision": round(_safe_metric("average_precision", labels, probabilities), 6),
        f"{prefix}_roc_auc": round(_safe_metric("roc_auc", labels, probabilities), 6),
        f"{prefix}_log_loss": round(_safe_metric("log_loss", labels, probabilities), 6),
        f"{prefix}_brier_score": round(_safe_metric("brier", labels, probabilities), 6),
    }
    metrics.update(_group_budget_metrics(rows, probabilities, prefix))
    return metrics


def fit_bundle(
    rows: Sequence[Mapping[str, object]],
    *,
    backend: str,
    random_seed: int = DEFAULT_RANDOM_SEED,
    hyperparameters: Mapping[str, object] | None = None,
) -> dict[str, object]:
    pipeline = _fit_pipeline(
        rows,
        backend=backend,
        random_seed=random_seed,
        hyperparameters=hyperparameters,
    )
    return {
        "pipeline": pipeline,
        "backend": resolve_backend(backend),
        "hyperparameters": dict(hyperparameters or {}),
        "feature_fields": {
            "numeric": list(features.NUMERIC_FEATURES),
            "boolean": list(features.BOOLEAN_FEATURES),
            "categorical": list(features.CATEGORICAL_FEATURES),
        },
        "training_metadata_fields": list(features.TRAINING_METADATA_FIELDS),
        "label_field": "label_selected",
        "created_at": datetime.now(UTC).isoformat(),
    }


def score_feature_rows(bundle: Mapping[str, object], rows: Sequence[Mapping[str, object]]) -> list[float]:
    pipeline = bundle.get("pipeline")
    if pipeline is None:
        raise ModelCandidateArtifactError("Loaded candidate-generator artifact is invalid: missing fitted pipeline.")
    return _predict_probabilities(pipeline, rows)


def save_bundle(bundle: Mapping[str, object], output_path: str | Path) -> Path:
    resolved_output_path = Path(output_path)
    resolved_output_path.parent.mkdir(parents=True, exist_ok=True)
    dump(dict(bundle), resolved_output_path)
    return resolved_output_path


def load_bundle(model_path: str | Path) -> dict[str, object]:
    resolved_model_path = Path(model_path)
    try:
        bundle = dict(load(resolved_model_path))
    except FileNotFoundError as exc:
        raise ModelCandidateArtifactError(
            f"Required candidate-generator artifact is missing: {resolved_model_path}"
        ) from exc
    except Exception as exc:  # noqa: BLE001
        raise ModelCandidateArtifactError(
            f"Required candidate-generator artifact could not be loaded from {resolved_model_path}: {exc}"
        ) from exc
    if bundle.get("pipeline") is None:
        raise ModelCandidateArtifactError(
            f"Loaded candidate-generator artifact is invalid: {resolved_model_path} does not contain a fitted pipeline."
        )
    return bundle


def feature_summary_rows(
    bundle: Mapping[str, object],
    reference_rows: Sequence[Mapping[str, object]] | None = None,
) -> list[dict[str, object]]:
    pipeline = bundle.get("pipeline")
    if pipeline is None:
        return []
    vectorizer = pipeline.named_steps["vectorizer"]
    feature_names = list(vectorizer.get_feature_names_out())
    classifier = pipeline.named_steps["classifier"]

    if hasattr(classifier, "coef_"):
        coefficients = classifier.coef_[0]
        top_indices = sorted(range(len(feature_names)), key=lambda index: abs(float(coefficients[index])), reverse=True)[:30]
        return [
            {
                "feature_name": feature_names[index],
                "value": round(float(coefficients[index]), 6),
                "summary_kind": "coefficient",
            }
            for index in top_indices
        ]

    if hasattr(classifier, "feature_importances_"):
        importances = classifier.feature_importances_
        top_indices = sorted(range(len(feature_names)), key=lambda index: float(importances[index]), reverse=True)[:30]
        return [
            {
                "feature_name": feature_names[index],
                "value": round(float(importances[index]), 6),
                "summary_kind": "feature_importance",
            }
            for index in top_indices
        ]

    if reference_rows:
        sample_rows = list(reference_rows[: min(512, len(reference_rows))])
        X_sample = [_feature_row(row) for row in sample_rows]
        y_sample = [_label(row) for row in sample_rows]
        X_vectorized = vectorizer.transform(X_sample)
        if hasattr(X_vectorized, "toarray"):
            X_vectorized = X_vectorized.toarray()
        permutation = permutation_importance(
            classifier,
            X_vectorized,
            y_sample,
            n_repeats=5,
            random_state=DEFAULT_RANDOM_SEED,
            n_jobs=-1,
        )
        top_indices = sorted(range(len(feature_names)), key=lambda index: float(permutation.importances_mean[index]), reverse=True)[:30]
        return [
            {
                "feature_name": feature_names[index],
                "value": round(float(permutation.importances_mean[index]), 6),
                "summary_kind": "permutation_importance",
            }
            for index in top_indices
        ]

    return []
