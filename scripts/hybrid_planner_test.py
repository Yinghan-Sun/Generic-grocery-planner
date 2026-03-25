#!/usr/bin/env -S uv run --extra ml python
"""Regression checks for the model-ranked generic planner runtime."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

import duckdb

from dietdashboard import model_candidate_generator
from dietdashboard import model_candidate_training
from dietdashboard import model_candidate_tuning
from dietdashboard import plan_scorer
from dietdashboard import plan_scorer_training
from dietdashboard.generic_recommender import recommend_generic_food_candidates, recommend_generic_foods

PRICE_CONTEXT = {
    "usda_area_code": "WEST",
    "usda_area_name": "West",
    "bls_area_code": "400",
    "bls_area_name": "West urban",
}
BASE_REQUEST = {
    "protein_target_g": 130.0,
    "calorie_target_kcal": 2100.0,
    "preferences": {"meal_style": "lunch_dinner"},
    "nutrition_targets": {"carbohydrate": 230.0, "fat": 70.0, "fiber": 30.0},
    "pantry_items": [],
    "days": 1,
    "shopping_mode": "balanced",
    "price_context": PRICE_CONTEXT,
    "stores": [
        {
            "store_id": "stub:0",
            "name": "Training Store",
            "address": "0 Demo St",
            "distance_m": 150.0,
            "lat": 37.3861,
            "lon": -122.0839,
            "category": "supermarket",
        }
    ],
}


def assert_equal(actual: Any, expected: Any, label: str) -> None:
    if actual != expected:
        raise AssertionError(f"{label}: expected {expected!r}, got {actual!r}")


def assert_true(value: bool, label: str) -> None:
    if not value:
        raise AssertionError(f"{label}: expected truthy value")


def run_feature_extraction_test() -> list[str]:
    with duckdb.connect("data/data.db", read_only=True) as con:
        candidates = recommend_generic_food_candidates(con, candidate_count=3, **BASE_REQUEST)
    assert_true(len(candidates) >= 2, "feature extraction candidates available")
    feature_row = plan_scorer.extract_candidate_features(candidates[0])
    assert_true(all(field in feature_row for field in plan_scorer.NUMERIC_FEATURES), "feature extraction numeric fields")
    assert_true(all(field in feature_row for field in plan_scorer.BOOLEAN_FEATURES), "feature extraction boolean fields")
    assert_true(all(field in feature_row for field in plan_scorer.CATEGORICAL_FEATURES), "feature extraction categorical fields")
    assert_true(float(plan_scorer.heuristic_candidate_label(feature_row)) != 0.0, "feature extraction heuristic label")
    return ["feature_extraction"]


def run_training_artifact_test() -> list[str]:
    with tempfile.TemporaryDirectory() as tmp_dir:
        output_dir = Path(tmp_dir)
        summary = plan_scorer_training.train_and_save_model(
            output_dir=output_dir,
            candidate_count=3,
            backend="sklearn_ridge",
            learning_rate=0.1,
            max_depth=2,
            n_estimators=40,
            validation_split=0.3,
            random_seed=7,
        )
        assert_true(summary["model_path"].exists(), "training artifact model exists")
        assert_true(summary["dataset_path"].exists(), "training artifact dataset exists")
        assert_true(summary["metrics_path"].exists(), "training artifact metrics exists")
        bundle = plan_scorer.load_bundle(summary["model_path"])
        assert_equal(str(bundle["backend"]), "sklearn_ridge", "training artifact backend")
        assert_true(float(summary["metrics"]["validation_mae"]) >= 0.0, "training artifact mae valid")
    return ["training_artifact_creation"]


def run_missing_model_failure_test() -> list[str]:
    with duckdb.connect("data/data.db", read_only=True) as con:
        try:
            recommend_generic_foods(
                con,
                protein_target_g=BASE_REQUEST["protein_target_g"],
                calorie_target_kcal=BASE_REQUEST["calorie_target_kcal"],
                preferences=BASE_REQUEST["preferences"],
                nutrition_targets=BASE_REQUEST["nutrition_targets"],
                pantry_items=BASE_REQUEST["pantry_items"],
                days=BASE_REQUEST["days"],
                shopping_mode=BASE_REQUEST["shopping_mode"],
                price_context=BASE_REQUEST["price_context"],
                stores=BASE_REQUEST["stores"],
                scorer_config={
                    "candidate_count": 4,
                    "scorer_model_path": "artifacts/plan_scorer/does_not_exist.joblib",
                    "debug": True,
                },
            )
        except plan_scorer.PlanScorerArtifactError as exc:
            assert_true("Required trained plan scorer artifact" in str(exc), "missing model error message")
        else:
            raise AssertionError("missing model should raise PlanScorerArtifactError")
    return ["missing_model_failure"]


def run_model_only_smoke_test() -> list[str]:
    with tempfile.TemporaryDirectory() as tmp_dir:
        output_dir = Path(tmp_dir)
        summary = plan_scorer_training.train_and_save_model(
            output_dir=output_dir,
            candidate_count=3,
            backend="sklearn_ridge",
            learning_rate=0.1,
            max_depth=2,
            n_estimators=40,
            validation_split=0.3,
            random_seed=11,
        )
        with duckdb.connect("data/data.db", read_only=True) as con:
            recommendation = recommend_generic_foods(
                con,
                protein_target_g=BASE_REQUEST["protein_target_g"],
                calorie_target_kcal=BASE_REQUEST["calorie_target_kcal"],
                preferences=BASE_REQUEST["preferences"],
                nutrition_targets=BASE_REQUEST["nutrition_targets"],
                pantry_items=BASE_REQUEST["pantry_items"],
                days=BASE_REQUEST["days"],
                shopping_mode=BASE_REQUEST["shopping_mode"],
                price_context=BASE_REQUEST["price_context"],
                stores=BASE_REQUEST["stores"],
                scorer_config={
                    "candidate_count": 4,
                    "scorer_model_path": str(summary["model_path"]),
                    "debug": True,
                },
            )
    assert_true(bool(recommendation.get("scorer_used")), "trained scorer used")
    assert_equal(str(recommendation.get("scorer_backend")), "sklearn_ridge", "trained scorer backend")
    assert_true(int(recommendation.get("candidate_count_considered") or 0) >= 1, "trained scorer candidate count")
    assert_true(isinstance(recommendation.get("scoring_debug"), dict), "trained scorer debug payload")
    debug_payload = recommendation["scoring_debug"]
    assert_true(len(debug_payload["candidates"]) >= 1, "trained scorer debug candidates")
    assert_true(all("model_score" in candidate for candidate in debug_payload["candidates"]), "debug model scores")
    assert_true(all("heuristic_score" in candidate for candidate in debug_payload["candidates"]), "debug heuristic scores")
    assert_equal(str(recommendation.get("selected_candidate_source")), "heuristic", "heuristic-only selected source")
    return ["model_only_smoke"]


def run_candidate_dataset_generation_test() -> tuple[list[str], Path]:
    temp_dir = Path(tempfile.mkdtemp())
    dataset_path, schema_path, scenarios_path, rows, scenarios = model_candidate_training.write_training_dataset(
        temp_dir / "candidate_generator_dataset.csv",
        candidate_count=4,
        scenario_limit=12,
    )
    assert_true(dataset_path.exists(), "candidate dataset exists")
    assert_true(schema_path.exists(), "candidate schema exists")
    assert_true(scenarios_path.exists(), "candidate scenarios exists")
    assert_true(len(rows) > 0, "candidate dataset non-empty")
    assert_true(len(scenarios) > 0, "candidate scenarios non-empty")
    split_counts = {str(row["split"]) for row in rows}
    assert_true("train" in split_counts, "candidate dataset train split present")
    return ["candidate_dataset_generation"], temp_dir


def run_candidate_tuning_and_training_test(dataset_dir: Path) -> list[str]:
    dataset_path = dataset_dir / "candidate_generator_dataset.csv"
    tuning_summary = model_candidate_tuning.run_tuning(
        dataset_path=dataset_path,
        output_dir=dataset_dir,
        max_trials_per_backend=1,
    )
    assert_true(Path(tuning_summary["results_path"]).exists(), "candidate tuning results exists")
    assert_true(Path(tuning_summary["best_config_path"]).exists(), "candidate best config exists")
    training_summary = model_candidate_training.train_and_save_model(
        dataset_path=dataset_path,
        output_dir=dataset_dir,
        config_path=Path(tuning_summary["best_config_path"]),
    )
    assert_true(training_summary["model_path"].exists(), "candidate model exists")
    assert_true(training_summary["metrics_path"].exists(), "candidate metrics exists")
    bundle = model_candidate_generator.load_bundle(training_summary["model_path"])
    assert_true(bundle.get("pipeline") is not None, "candidate pipeline available")
    assert_true(float(training_summary["metrics"]["test_average_precision"]) >= 0.0, "candidate metrics valid")
    return ["candidate_tuning_and_training"]


def run_missing_candidate_model_failure_test() -> list[str]:
    with duckdb.connect("data/data.db", read_only=True) as con:
        try:
            recommend_generic_foods(
                con,
                protein_target_g=BASE_REQUEST["protein_target_g"],
                calorie_target_kcal=BASE_REQUEST["calorie_target_kcal"],
                preferences=BASE_REQUEST["preferences"],
                nutrition_targets=BASE_REQUEST["nutrition_targets"],
                pantry_items=BASE_REQUEST["pantry_items"],
                days=BASE_REQUEST["days"],
                shopping_mode=BASE_REQUEST["shopping_mode"],
                price_context=BASE_REQUEST["price_context"],
                stores=BASE_REQUEST["stores"],
                scorer_config={
                    "candidate_count": 4,
                    "scorer_model_path": str(plan_scorer.default_model_path()),
                    "debug": True,
                },
                candidate_generation_config={
                    "enable_model_candidates": True,
                    "model_candidate_count": 3,
                    "candidate_generator_model_path": "artifacts/candidate_generator/does_not_exist.joblib",
                    "debug": True,
                },
            )
        except model_candidate_generator.ModelCandidateArtifactError as exc:
            assert_true("Required candidate-generator artifact" in str(exc), "missing candidate model error message")
        else:
            raise AssertionError("missing candidate model should raise ModelCandidateArtifactError")
    return ["missing_candidate_model_failure"]


def run_invalid_candidate_model_failure_test(dataset_dir: Path) -> list[str]:
    invalid_path = dataset_dir / "invalid_candidate_generator.joblib"
    invalid_path.write_text("not a joblib artifact", encoding="utf-8")
    with duckdb.connect("data/data.db", read_only=True) as con:
        try:
            recommend_generic_foods(
                con,
                protein_target_g=BASE_REQUEST["protein_target_g"],
                calorie_target_kcal=BASE_REQUEST["calorie_target_kcal"],
                preferences=BASE_REQUEST["preferences"],
                nutrition_targets=BASE_REQUEST["nutrition_targets"],
                pantry_items=BASE_REQUEST["pantry_items"],
                days=BASE_REQUEST["days"],
                shopping_mode=BASE_REQUEST["shopping_mode"],
                price_context=BASE_REQUEST["price_context"],
                stores=BASE_REQUEST["stores"],
                scorer_config={
                    "candidate_count": 4,
                    "scorer_model_path": str(plan_scorer.default_model_path()),
                    "debug": True,
                },
                candidate_generation_config={
                    "enable_model_candidates": True,
                    "model_candidate_count": 3,
                    "candidate_generator_model_path": str(invalid_path),
                    "debug": True,
                },
            )
        except model_candidate_generator.ModelCandidateArtifactError as exc:
            assert_true("could not be loaded" in str(exc), "invalid candidate model error message")
        else:
            raise AssertionError("invalid candidate model should raise ModelCandidateArtifactError")
    return ["invalid_candidate_model_failure"]


def run_hybrid_candidate_generation_test(dataset_dir: Path) -> list[str]:
    trained_model_path = dataset_dir / "candidate_generator_best.joblib"
    with duckdb.connect("data/data.db", read_only=True) as con:
        recommendation = recommend_generic_foods(
            con,
            protein_target_g=BASE_REQUEST["protein_target_g"],
            calorie_target_kcal=BASE_REQUEST["calorie_target_kcal"],
            preferences=BASE_REQUEST["preferences"],
            nutrition_targets=BASE_REQUEST["nutrition_targets"],
            pantry_items=BASE_REQUEST["pantry_items"],
            days=BASE_REQUEST["days"],
            shopping_mode=BASE_REQUEST["shopping_mode"],
            price_context=BASE_REQUEST["price_context"],
            stores=BASE_REQUEST["stores"],
            scorer_config={
                "candidate_count": 4,
                "scorer_model_path": str(plan_scorer.default_model_path()),
                "debug": True,
            },
            candidate_generation_config={
                "enable_model_candidates": True,
                "model_candidate_count": 3,
                "candidate_generator_model_path": str(trained_model_path),
                "debug": True,
            },
        )
    assert_true(isinstance(recommendation.get("candidate_generation_debug"), dict), "candidate generation debug payload")
    generation_debug = recommendation["candidate_generation_debug"]
    assert_true(int(generation_debug["heuristic_candidate_count"]) >= 1, "heuristic candidate count present")
    assert_true(int(generation_debug["model_candidate_count"]) >= 1, "model candidate count present")
    assert_true(int(generation_debug["fused_candidate_count"]) >= 1, "fused candidate count present")
    assert_true(isinstance(recommendation.get("candidate_comparison_debug"), dict), "candidate comparison debug payload")
    comparison_debug = recommendation["candidate_comparison_debug"]
    assert_true(
        int(generation_debug["fused_candidate_count"]) <= int(generation_debug["heuristic_candidate_count"]) + int(generation_debug["model_candidate_count"]),
        "candidate dedupe reduces or preserves total count",
    )
    debug_candidates = generation_debug["candidates"]
    shopping_keys = [tuple(candidate["shopping_food_ids"]) for candidate in debug_candidates]
    assert_equal(len(shopping_keys), len(set(shopping_keys)), "deduped candidate shopping ids unique")
    assert_true(isinstance(generation_debug.get("raw_candidates"), list), "raw candidate debug rows present")
    assert_true(all("fusion_status" in candidate for candidate in generation_debug["raw_candidates"]), "raw candidate fusion status present")
    assert_true(all("overlap_with_selected_candidate" in candidate for candidate in debug_candidates), "candidate overlap debug present")
    assert_true(all("chosen_food_ids" in candidate for candidate in debug_candidates), "chosen food ids exposed")
    assert_true(all("selection_reason_summary" in candidate for candidate in generation_debug["raw_candidates"]), "candidate loss reasons exposed")
    assert_true(
        any(candidate["source"] in {"model", "repaired_model", "hybrid"} for candidate in debug_candidates),
        "model-backed candidate present after fusion",
    )
    assert_true(
        comparison_debug.get("material_difference_rule") is not None,
        "material difference rule exposed",
    )
    assert_true(
        comparison_debug.get("best_heuristic_candidate_id") is not None,
        "best heuristic candidate id exposed",
    )
    assert_true(
        comparison_debug.get("materially_different_model_candidates_surviving_after_fusion") is not None,
        "materially different surviving model candidate count exposed",
    )
    assert_true(
        str(recommendation.get("selected_candidate_source")) in {"heuristic", "model", "repaired_model", "hybrid"},
        "selected candidate source exposed",
    )
    return ["hybrid_candidate_generation"]


def main() -> int:
    scenarios: list[str] = []
    scenarios.extend(run_feature_extraction_test())
    scenarios.extend(run_training_artifact_test())
    scenarios.extend(run_missing_model_failure_test())
    scenarios.extend(run_model_only_smoke_test())
    dataset_scenarios, dataset_dir = run_candidate_dataset_generation_test()
    scenarios.extend(dataset_scenarios)
    scenarios.extend(run_candidate_tuning_and_training_test(dataset_dir))
    scenarios.extend(run_missing_candidate_model_failure_test())
    scenarios.extend(run_invalid_candidate_model_failure_test(dataset_dir))
    scenarios.extend(run_hybrid_candidate_generation_test(dataset_dir))
    print(f"hybrid_planner_scenarios={','.join(scenarios)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
