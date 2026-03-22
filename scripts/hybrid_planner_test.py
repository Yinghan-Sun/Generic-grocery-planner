#!/usr/bin/env -S uv run --extra ml python
"""Regression checks for the model-ranked generic planner runtime."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

import duckdb

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
    return ["model_only_smoke"]


def main() -> int:
    scenarios: list[str] = []
    scenarios.extend(run_feature_extraction_test())
    scenarios.extend(run_training_artifact_test())
    scenarios.extend(run_missing_model_failure_test())
    scenarios.extend(run_model_only_smoke_test())
    print(f"hybrid_planner_scenarios={','.join(scenarios)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
