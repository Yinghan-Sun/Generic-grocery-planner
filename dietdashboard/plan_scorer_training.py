"""Offline dataset generation and training helpers for the plan scorer."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import duckdb

from dietdashboard.generic_recommender import recommend_generic_food_candidates
from dietdashboard import plan_scorer

PRICE_CONTEXTS = (
    {
        "context_id": "us",
        "usda_area_code": "US",
        "usda_area_name": "U.S. average",
        "bls_area_code": "0",
        "bls_area_name": "U.S. city average",
        "store_count": 2,
    },
    {
        "context_id": "west",
        "usda_area_code": "WEST",
        "usda_area_name": "West",
        "bls_area_code": "400",
        "bls_area_name": "West urban",
        "store_count": 4,
    },
    {
        "context_id": "new_york",
        "usda_area_code": "NEW_YORK",
        "usda_area_name": "New York",
        "bls_area_code": "100",
        "bls_area_name": "Northeast urban",
        "store_count": 5,
    },
)
WINDOW_VARIANTS = (
    (1, "balanced"),
    (3, "fresh"),
    (5, "bulk"),
)
SCENARIO_TEMPLATES = (
    {
        "scenario_id": "balanced_any",
        "protein_target_g": 120.0,
        "calorie_target_kcal": 2100.0,
        "preferences": {"meal_style": "any"},
        "nutrition_targets": {"carbohydrate": 230.0, "fat": 70.0, "fiber": 30.0, "calcium": 1000.0, "iron": 18.0, "vitamin_c": 90.0},
    },
    {
        "scenario_id": "muscle_gain_any",
        "protein_target_g": 180.0,
        "calorie_target_kcal": 2800.0,
        "preferences": {"meal_style": "any"},
        "nutrition_targets": {"carbohydrate": 320.0, "fat": 85.0, "fiber": 32.0, "calcium": 1100.0, "iron": 18.0, "vitamin_c": 95.0},
    },
    {
        "scenario_id": "fat_loss_any",
        "protein_target_g": 145.0,
        "calorie_target_kcal": 1750.0,
        "preferences": {"meal_style": "lunch_dinner"},
        "nutrition_targets": {"carbohydrate": 170.0, "fat": 55.0, "fiber": 32.0, "calcium": 1000.0, "iron": 18.0, "vitamin_c": 100.0},
    },
    {
        "scenario_id": "high_protein_vegetarian",
        "protein_target_g": 145.0,
        "calorie_target_kcal": 2350.0,
        "preferences": {"meal_style": "any", "vegetarian": True},
        "nutrition_targets": {"carbohydrate": 255.0, "fat": 75.0, "fiber": 32.0, "calcium": 1200.0, "iron": 18.0, "vitamin_c": 95.0},
    },
    {
        "scenario_id": "budget_friendly",
        "protein_target_g": 110.0,
        "calorie_target_kcal": 2100.0,
        "preferences": {"meal_style": "lunch_dinner", "budget_friendly": True},
        "nutrition_targets": {"carbohydrate": 245.0, "fat": 65.0, "fiber": 34.0, "calcium": 1000.0, "iron": 18.0, "vitamin_c": 90.0},
    },
    {
        "scenario_id": "low_prep",
        "protein_target_g": 120.0,
        "calorie_target_kcal": 2050.0,
        "preferences": {"meal_style": "any", "low_prep": True},
        "nutrition_targets": {"carbohydrate": 225.0, "fat": 70.0, "fiber": 28.0},
    },
    {
        "scenario_id": "breakfast",
        "protein_target_g": 105.0,
        "calorie_target_kcal": 1900.0,
        "preferences": {"meal_style": "breakfast"},
        "nutrition_targets": {"carbohydrate": 220.0, "fat": 62.0, "fiber": 26.0, "calcium": 1000.0},
    },
    {
        "scenario_id": "snack",
        "protein_target_g": 95.0,
        "calorie_target_kcal": 1800.0,
        "preferences": {"meal_style": "snack", "low_prep": True},
        "nutrition_targets": {"carbohydrate": 190.0, "fat": 60.0, "fiber": 24.0},
    },
)


def project_root() -> Path:
    return plan_scorer.project_root()


def default_db_path() -> Path:
    return project_root() / "data" / "data.db"


def _stub_stores(count: int, prefix: str) -> list[dict[str, object]]:
    stores: list[dict[str, object]] = []
    for index in range(count):
        stores.append(
            {
                "store_id": f"{prefix}:store_{index}",
                "name": f"Training Store {index}",
                "address": f"{index} Demo St",
                "distance_m": float(200 + index * 120),
                "lat": 37.3861 + (index * 0.001),
                "lon": -122.0839 - (index * 0.001),
                "category": "supermarket",
            }
        )
    return stores


def build_training_rows(
    db_path: str | Path | None = None,
    *,
    candidate_count: int = 8,
) -> list[dict[str, object]]:
    resolved_db_path = Path(db_path) if db_path is not None else default_db_path()
    rows: list[dict[str, object]] = []
    with duckdb.connect(resolved_db_path, read_only=True) as con:
        for scenario in SCENARIO_TEMPLATES:
            for price_context in PRICE_CONTEXTS:
                for days, shopping_mode in WINDOW_VARIANTS:
                    request_id = f"{scenario['scenario_id']}:{price_context['context_id']}:{days}:{shopping_mode}"
                    stores = _stub_stores(int(price_context["store_count"]), request_id)
                    candidates = recommend_generic_food_candidates(
                        con,
                        protein_target_g=float(scenario["protein_target_g"]),
                        calorie_target_kcal=float(scenario["calorie_target_kcal"]),
                        preferences=dict(scenario["preferences"]),
                        nutrition_targets=dict(scenario["nutrition_targets"]),
                        pantry_items=[],
                        days=days,
                        shopping_mode=shopping_mode,
                        price_context={
                            "usda_area_code": str(price_context["usda_area_code"]),
                            "usda_area_name": str(price_context["usda_area_name"]),
                            "bls_area_code": str(price_context["bls_area_code"]),
                            "bls_area_name": str(price_context["bls_area_name"]),
                        },
                        stores=stores,
                        candidate_count=candidate_count,
                    )
                    if len(candidates) < 2:
                        continue
                    for candidate in candidates:
                        features = plan_scorer.extract_candidate_features(candidate)
                        row = {
                            "request_id": request_id,
                            "candidate_id": str(candidate["candidate_id"]),
                            "label_score": plan_scorer.heuristic_candidate_label(features),
                            **features,
                        }
                        rows.append(row)
    return rows


def dataset_schema_summary(rows: list[dict[str, object]]) -> dict[str, object]:
    request_ids = sorted({str(row["request_id"]) for row in rows})
    goal_profiles = sorted({str(row["goal_profile"]) for row in rows})
    return {
        "row_count": len(rows),
        "request_count": len(request_ids),
        "goal_profiles": goal_profiles,
        "numeric_features": list(plan_scorer.NUMERIC_FEATURES),
        "boolean_features": list(plan_scorer.BOOLEAN_FEATURES),
        "categorical_features": list(plan_scorer.CATEGORICAL_FEATURES),
        "metadata_fields": list(plan_scorer.TRAINING_METADATA_FIELDS),
        "label_field": "label_score",
    }


def write_training_dataset(
    output_path: str | Path | None = None,
    *,
    db_path: str | Path | None = None,
    candidate_count: int = 8,
) -> tuple[Path, Path, list[dict[str, object]]]:
    rows = build_training_rows(db_path=db_path, candidate_count=candidate_count)
    dataset_path = Path(output_path) if output_path is not None else plan_scorer.default_dataset_path()
    dataset_path.parent.mkdir(parents=True, exist_ok=True)
    schema_path = dataset_path.with_suffix(".schema.json")

    fieldnames = [
        *plan_scorer.TRAINING_METADATA_FIELDS,
        *plan_scorer.NUMERIC_FEATURES,
        *plan_scorer.BOOLEAN_FEATURES,
        *plan_scorer.CATEGORICAL_FEATURES,
    ]
    with dataset_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    schema_path.write_text(json.dumps(dataset_schema_summary(rows), indent=2, sort_keys=True), encoding="utf-8")
    return dataset_path, schema_path, rows


def train_and_save_model(
    *,
    db_path: str | Path | None = None,
    output_dir: str | Path | None = None,
    candidate_count: int = 8,
    backend: str = "auto",
    learning_rate: float = 0.05,
    max_depth: int = 3,
    n_estimators: int = 250,
    validation_split: float = 0.25,
    random_seed: int = plan_scorer.DEFAULT_RANDOM_SEED,
) -> dict[str, object]:
    resolved_output_dir = Path(output_dir) if output_dir is not None else plan_scorer.default_model_dir()
    resolved_output_dir.mkdir(parents=True, exist_ok=True)

    dataset_path, schema_path, rows = write_training_dataset(
        resolved_output_dir / plan_scorer.default_dataset_path().name,
        db_path=db_path,
        candidate_count=candidate_count,
    )
    bundle, metrics = plan_scorer.train_model(
        rows,
        backend=backend,
        learning_rate=learning_rate,
        max_depth=max_depth,
        n_estimators=n_estimators,
        validation_split=validation_split,
        random_seed=random_seed,
    )
    model_path = plan_scorer.save_bundle(bundle, resolved_output_dir / plan_scorer.default_model_path().name)
    metrics_path = resolved_output_dir / plan_scorer.default_metrics_path().name
    metrics_path.write_text(json.dumps(metrics, indent=2, sort_keys=True), encoding="utf-8")

    feature_summary_rows = plan_scorer.feature_summary_rows(bundle)
    feature_summary_path = resolved_output_dir / plan_scorer.default_feature_summary_path().name
    if feature_summary_rows:
        with feature_summary_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(feature_summary_rows[0].keys()))
            writer.writeheader()
            writer.writerows(feature_summary_rows)

    return {
        "dataset_path": dataset_path,
        "schema_path": schema_path,
        "model_path": model_path,
        "metrics_path": metrics_path,
        "feature_summary_path": feature_summary_path,
        "metrics": metrics,
        "row_count": len(rows),
        "request_count": len({str(row['request_id']) for row in rows}),
    }
