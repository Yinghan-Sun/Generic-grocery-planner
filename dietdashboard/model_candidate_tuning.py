"""Hyperparameter tuning for the learned candidate generator."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from time import perf_counter

from dietdashboard import model_candidate_generator
from dietdashboard import model_candidate_training

MODEL_SELECTION_PRIORITY = {
    "hist_gradient_boosting": 0,
    "random_forest": 1,
    "logistic_regression": 2,
}


def default_tuning_results_path() -> Path:
    return model_candidate_generator.default_model_dir() / "candidate_generator_tuning_results.csv"


def default_tuning_summary_path() -> Path:
    return model_candidate_generator.default_model_dir() / "candidate_generator_tuning_summary.json"


def default_best_config_path() -> Path:
    return model_candidate_generator.default_model_dir() / "candidate_generator_best_config.json"


def default_model_comparison_path() -> Path:
    return model_candidate_generator.default_model_dir() / "candidate_generator_model_comparison.json"


def default_backend_best_config_path(backend: str) -> Path:
    return model_candidate_generator.default_model_dir() / f"candidate_generator_best_config_{model_candidate_generator.resolve_backend(backend)}.json"


def search_space() -> dict[str, list[dict[str, object]]]:
    return {
        "logistic_regression": [
            {"C": c_value, "class_weight": class_weight, "max_iter": 4000}
            for c_value in (0.25, 1.0, 4.0)
            for class_weight in (None, "balanced")
        ],
        "random_forest": [
            {
                "n_estimators": n_estimators,
                "max_depth": max_depth,
                "min_samples_leaf": min_samples_leaf,
                "max_features": max_features,
            }
            for n_estimators in (200, 350)
            for max_depth in (6, 12, None)
            for min_samples_leaf in (1, 2)
            for max_features in ("sqrt", 0.5)
        ],
        "hist_gradient_boosting": [
            {
                "learning_rate": learning_rate,
                "max_depth": max_depth,
                "max_leaf_nodes": max_leaf_nodes,
                "min_samples_leaf": min_samples_leaf,
                "l2_regularization": l2_regularization,
            }
            for learning_rate in (0.03, 0.07, 0.1)
            for max_depth in (3, 5)
            for max_leaf_nodes in (15, 31)
            for min_samples_leaf in (20, 50)
            for l2_regularization in (0.0, 0.1)
        ],
    }


def _selection_sort_key(result: dict[str, object]) -> tuple[float, float, float, float, int]:
    return (
        -float(result[model_candidate_generator.PRIMARY_TUNING_METRIC]),
        -float(result["validation_scenario_exact_seed_rate"]),
        -float(result["validation_average_precision"]),
        float(result["validation_log_loss"]),
        MODEL_SELECTION_PRIORITY.get(str(result["backend"]), 99),
    )


def _best_per_backend(results: list[dict[str, object]]) -> dict[str, dict[str, object]]:
    winners: dict[str, dict[str, object]] = {}
    grouped: dict[str, list[dict[str, object]]] = {}
    for result in results:
        grouped.setdefault(str(result["backend"]), []).append(result)
    for backend, backend_results in grouped.items():
        winners[backend] = sorted(backend_results, key=_selection_sort_key)[0]
    return winners


def run_tuning(
    *,
    dataset_path: str | Path | None = None,
    output_dir: str | Path | None = None,
    random_seed: int = model_candidate_generator.DEFAULT_RANDOM_SEED,
    max_trials_per_backend: int | None = None,
) -> dict[str, object]:
    resolved_output_dir = Path(output_dir) if output_dir is not None else model_candidate_generator.default_model_dir()
    resolved_output_dir.mkdir(parents=True, exist_ok=True)

    train_rows = model_candidate_training.load_dataset_rows(dataset_path, splits=("train",))
    validation_rows = model_candidate_training.load_dataset_rows(dataset_path, splits=("validation",))
    if not train_rows:
        raise ValueError("Candidate-generator tuning requires at least one training row.")
    if not validation_rows:
        raise ValueError("Candidate-generator tuning requires at least one validation row.")

    results: list[dict[str, object]] = []
    for backend, parameter_grid in search_space().items():
        limited_grid = parameter_grid[: max_trials_per_backend] if max_trials_per_backend is not None else parameter_grid
        for trial_index, hyperparameters in enumerate(limited_grid):
            started_at = perf_counter()
            bundle = model_candidate_generator.fit_bundle(
                train_rows,
                backend=backend,
                random_seed=random_seed,
                hyperparameters=hyperparameters,
            )
            validation_metrics = model_candidate_generator.evaluate_rows(bundle, validation_rows, prefix="validation")
            fit_seconds = perf_counter() - started_at
            results.append(
                {
                    "backend": backend,
                    "trial_index": trial_index,
                    "random_seed": random_seed,
                    "fit_seconds": round(float(fit_seconds), 6),
                    "hyperparameters_json": json.dumps(hyperparameters, sort_keys=True),
                    **validation_metrics,
                }
            )

    backend_winners = _best_per_backend(results)
    selected_result = sorted(backend_winners.values(), key=_selection_sort_key)[0]
    selected_backend = str(selected_result["backend"])
    selected_hyperparameters = json.loads(str(selected_result["hyperparameters_json"]))

    results_path = resolved_output_dir / default_tuning_results_path().name
    with results_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(results[0].keys()))
        writer.writeheader()
        writer.writerows(results)

    summary_payload = {
        "dataset_path": str(dataset_path or model_candidate_training.default_dataset_path()),
        "random_seed": random_seed,
        "primary_metric": model_candidate_generator.PRIMARY_TUNING_METRIC,
        "search_space_sizes": {backend: len(parameter_grid) for backend, parameter_grid in search_space().items()},
        "trial_count": len(results),
        "backend_winners": {
            backend: {
                "backend": str(result["backend"]),
                "hyperparameters": json.loads(str(result["hyperparameters_json"])),
                model_candidate_generator.PRIMARY_TUNING_METRIC: result[model_candidate_generator.PRIMARY_TUNING_METRIC],
                "validation_average_precision": result["validation_average_precision"],
                "validation_scenario_exact_seed_rate": result["validation_scenario_exact_seed_rate"],
                "validation_log_loss": result["validation_log_loss"],
                "fit_seconds": result["fit_seconds"],
            }
            for backend, result in sorted(backend_winners.items())
        },
        "selected_model": {
            "backend": selected_backend,
            "hyperparameters": selected_hyperparameters,
            model_candidate_generator.PRIMARY_TUNING_METRIC: selected_result[model_candidate_generator.PRIMARY_TUNING_METRIC],
            "validation_average_precision": selected_result["validation_average_precision"],
            "validation_scenario_exact_seed_rate": selected_result["validation_scenario_exact_seed_rate"],
            "validation_log_loss": selected_result["validation_log_loss"],
        },
    }
    summary_path = resolved_output_dir / default_tuning_summary_path().name
    summary_path.write_text(json.dumps(summary_payload, indent=2, sort_keys=True), encoding="utf-8")

    best_config_payload = {
        "backend": selected_backend,
        "hyperparameters": selected_hyperparameters,
        "random_seed": random_seed,
        "selected_from": str(results_path),
        "primary_metric": model_candidate_generator.PRIMARY_TUNING_METRIC,
    }
    best_config_path = resolved_output_dir / default_best_config_path().name
    best_config_path.write_text(json.dumps(best_config_payload, indent=2, sort_keys=True), encoding="utf-8")

    backend_best_config_paths: dict[str, str] = {}
    for backend, result in sorted(backend_winners.items()):
        backend_config_path = resolved_output_dir / default_backend_best_config_path(backend).name
        backend_config_payload = {
            "backend": backend,
            "hyperparameters": json.loads(str(result["hyperparameters_json"])),
            "random_seed": random_seed,
            "selected_from": str(results_path),
            "primary_metric": model_candidate_generator.PRIMARY_TUNING_METRIC,
        }
        backend_config_path.write_text(json.dumps(backend_config_payload, indent=2, sort_keys=True), encoding="utf-8")
        backend_best_config_paths[backend] = str(backend_config_path)

    comparison_path = resolved_output_dir / default_model_comparison_path().name
    comparison_payload = {
        "models": [
            {
                "backend": backend,
                "best_hyperparameters": json.loads(str(result["hyperparameters_json"])),
                "validation_average_precision": result["validation_average_precision"],
                "validation_role_recall_at_budget": result["validation_role_recall_at_budget"],
                "validation_scenario_exact_seed_rate": result["validation_scenario_exact_seed_rate"],
                "validation_log_loss": result["validation_log_loss"],
                "fit_seconds": result["fit_seconds"],
            }
            for backend, result in sorted(backend_winners.items())
        ],
        "selected_backend": selected_backend,
    }
    comparison_path.write_text(json.dumps(comparison_payload, indent=2, sort_keys=True), encoding="utf-8")

    return {
        "results_path": results_path,
        "summary_path": summary_path,
        "best_config_path": best_config_path,
        "comparison_path": comparison_path,
        "selected_backend": selected_backend,
        "selected_hyperparameters": selected_hyperparameters,
        "backend_best_config_paths": backend_best_config_paths,
    }
