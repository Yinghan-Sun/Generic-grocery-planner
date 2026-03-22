"""Offline training utilities for generic-food role classification."""

from __future__ import annotations

from collections import Counter, defaultdict
import csv
import json
from pathlib import Path

import duckdb

from dietdashboard import generic_recommender as gr

ROLE_LABELS = ("protein_anchor", "carb_base", "produce", "calorie_booster")
NUMERIC_FEATURES = (
    "default_serving_g",
    "purchase_unit_size_g",
    "budget_score",
    "commonality_rank",
    "energy_fibre_kcal",
    "protein",
    "carbohydrate",
    "fat",
    "fiber",
    "calcium",
    "iron",
    "vitamin_c",
    "protein_density_score",
    "fiber_score",
    "calcium_score",
    "iron_score",
    "vitamin_c_score",
    "representative_unit_price",
    "regional_price_low",
    "regional_price_high",
    "regional_price_span",
)
BOOLEAN_FEATURES = (
    "vegetarian",
    "vegan",
    "dairy_free",
    "gluten_free",
    "high_protein",
    "breakfast_friendly",
    "shelf_stable",
    "cold_only",
    "microwave_friendly",
    "price_available",
    "usda_price_reference",
    "bls_area_price_reference",
    "bls_fallback_price_reference",
    "meal_tag_breakfast",
    "meal_tag_lunch",
    "meal_tag_dinner",
    "meal_tag_snack",
    "meal_tag_side",
)
CATEGORICAL_FEATURES = (
    "food_family",
    "purchase_unit",
    "prep_level",
    "shelf_stability",
    "price_reference_source",
)
GOAL_BASE_TARGETS = {
    "generic_balanced": {"protein": 100.0, "energy_fibre_kcal": 2200.0, "carbohydrate": 250.0, "fat": 70.0, "fiber": 30.0, "calcium": 1000.0, "iron": 18.0, "vitamin_c": 90.0},
    "muscle_gain": {"protein": 180.0, "energy_fibre_kcal": 2800.0, "carbohydrate": 330.0, "fat": 85.0, "fiber": 35.0, "calcium": 1200.0, "iron": 18.0, "vitamin_c": 100.0},
    "fat_loss": {"protein": 145.0, "energy_fibre_kcal": 1700.0, "carbohydrate": 160.0, "fat": 55.0, "fiber": 32.0, "calcium": 1000.0, "iron": 18.0, "vitamin_c": 100.0},
    "maintenance": {"protein": 115.0, "energy_fibre_kcal": 2250.0, "carbohydrate": 240.0, "fat": 70.0, "fiber": 30.0, "calcium": 1000.0, "iron": 18.0, "vitamin_c": 90.0},
    "budget_friendly_healthy": {"protein": 110.0, "energy_fibre_kcal": 2100.0, "carbohydrate": 240.0, "fat": 65.0, "fiber": 32.0, "calcium": 1000.0, "iron": 18.0, "vitamin_c": 90.0},
    "high_protein_vegetarian": {"protein": 145.0, "energy_fibre_kcal": 2400.0, "carbohydrate": 260.0, "fat": 75.0, "fiber": 32.0, "calcium": 1200.0, "iron": 18.0, "vitamin_c": 95.0},
}
ROLE_MANUAL_OVERRIDES = {
    # Milk is used as a protein-supporting training food in the current goal templates,
    # but it falls below the heuristic role-candidate threshold used for direct scoring.
    "milk": "protein_anchor",
}


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def default_dataset_path() -> Path:
    return project_root() / "artifacts" / "food_role_model" / "generic_food_role_training_dataset.csv"


def default_model_dir() -> Path:
    return project_root() / "artifacts" / "food_role_model"


def _scenario_grid() -> list[dict[str, object]]:
    scenarios: list[dict[str, object]] = []
    for goal_profile, nutrition_targets in GOAL_BASE_TARGETS.items():
        for meal_style in ("any", "breakfast", "lunch_dinner", "snack"):
            preferences = {
                "meal_style": meal_style,
                "budget_friendly": goal_profile == "budget_friendly_healthy",
                "vegetarian": goal_profile == "high_protein_vegetarian",
                "vegan": False,
                "dairy_free": False,
                "low_prep": meal_style in {"breakfast", "snack"},
            }
            scenarios.append(
                {
                    "scenario_id": f"{goal_profile}:{meal_style}",
                    "goal_profile": goal_profile,
                    "preferences": gr._effective_preferences(preferences),
                    "nutrition_targets": dict(nutrition_targets),
                }
            )
    return scenarios


def _baseline_role_scores(
    food: dict[str, object],
    *,
    preferences: dict[str, object],
    nutrition_targets: dict[str, float],
    goal_profile: str,
) -> dict[str, float]:
    return {
        role: score
        for role, score in (
            (role, gr._role_score(food, role, preferences, nutrition_targets, goal_profile))
            for role in ROLE_LABELS
        )
        if score != float("-inf")
    }


def _fallback_role(food: dict[str, object]) -> str:
    food_id = str(food.get("generic_food_id") or "")
    if food_id in ROLE_MANUAL_OVERRIDES:
        return ROLE_MANUAL_OVERRIDES[food_id]

    family = str(food.get("food_family") or "")
    if family == "produce":
        return "produce"
    if family == "fat":
        return "calorie_booster"
    if family == "grain":
        return "carb_base"
    if family in {"protein", "legume", "dairy"}:
        return "protein_anchor"
    return "calorie_booster"


def load_candidate_foods(
    con: duckdb.DuckDBPyConnection,
    *,
    price_area_code: str = "0",
    usda_area_code: str = "US",
) -> dict[str, dict[str, object]]:
    return gr._load_candidates(  # noqa: SLF001
        con,
        vegetarian=False,
        dairy_free=False,
        vegan=False,
        price_area_code=price_area_code,
        usda_area_code=usda_area_code,
    )


def derive_role_labels(available: dict[str, dict[str, object]]) -> dict[str, dict[str, object]]:
    scenarios = _scenario_grid()
    role_votes: dict[str, Counter[str]] = defaultdict(Counter)
    role_score_sums: dict[str, Counter[str]] = defaultdict(Counter)

    for scenario in scenarios:
        preferences = dict(scenario["preferences"])
        nutrition_targets = dict(scenario["nutrition_targets"])
        goal_profile = str(scenario["goal_profile"])
        for food_id, food in available.items():
            role_scores = _baseline_role_scores(
                food,
                preferences=preferences,
                nutrition_targets=nutrition_targets,
                goal_profile=goal_profile,
            )
            if not role_scores:
                continue

            best_role = min(
                role_scores,
                key=lambda role: (-role_scores[role], ROLE_LABELS.index(role)),
            )
            role_votes[food_id][best_role] += 1
            for role, score in role_scores.items():
                role_score_sums[food_id][role] += score

    labels: dict[str, dict[str, object]] = {}
    total_scenarios = len(scenarios)
    for food_id, food in available.items():
        votes = role_votes.get(food_id, Counter())
        if votes:
            top_vote_count = max(votes.values())
            top_roles = [role for role in ROLE_LABELS if votes.get(role, 0) == top_vote_count]
            if len(top_roles) == 1:
                label = top_roles[0]
            else:
                label = min(
                    top_roles,
                    key=lambda role: (
                        -(role_score_sums[food_id][role] / max(votes[role], 1)),
                        ROLE_LABELS.index(role),
                    ),
                )
            label_source = "heuristic_vote"
            label_vote_share = top_vote_count / total_scenarios
        else:
            label = _fallback_role(food)
            label_source = "manual_override" if food_id in ROLE_MANUAL_OVERRIDES else "family_fallback"
            label_vote_share = 0.0

        labels[food_id] = {
            "label_role": label,
            "label_source": label_source,
            "label_vote_share": round(label_vote_share, 4),
            "vote_protein_anchor": int(votes.get("protein_anchor", 0)),
            "vote_carb_base": int(votes.get("carb_base", 0)),
            "vote_produce": int(votes.get("produce", 0)),
            "vote_calorie_booster": int(votes.get("calorie_booster", 0)),
        }

    return labels


def _feature_row(food: dict[str, object]) -> dict[str, object]:
    meal_tags = gr._meal_tags(food)  # noqa: SLF001
    price_source = str(food.get("price_reference_source") or "")
    regional_price_low = float(food.get("regional_price_low") or 0.0)
    regional_price_high = float(food.get("regional_price_high") or 0.0)
    representative_unit_price = float(food.get("bls_estimated_unit_price") or 0.0)
    feature_row: dict[str, object] = {
        "generic_food_id": str(food["generic_food_id"]),
        "display_name": str(food["display_name"]),
        "food_family": str(food["food_family"]),
        "purchase_unit": str(food.get("purchase_unit") or ""),
        "prep_level": str(food.get("prep_level") or ""),
        "shelf_stability": str(food.get("shelf_stability") or ""),
        "price_reference_source": price_source or "none",
        "default_serving_g": float(food.get("default_serving_g") or 0.0),
        "purchase_unit_size_g": float(food.get("purchase_unit_size_g") or 0.0),
        "budget_score": float(food.get("budget_score") or 0.0),
        "commonality_rank": float(food.get("commonality_rank") or 0.0),
        "energy_fibre_kcal": float(food.get("energy_fibre_kcal") or 0.0),
        "protein": float(food.get("protein") or 0.0),
        "carbohydrate": float(food.get("carbohydrate") or 0.0),
        "fat": float(food.get("fat") or 0.0),
        "fiber": float(food.get("fiber") or 0.0),
        "calcium": float(food.get("calcium") or 0.0),
        "iron": float(food.get("iron") or 0.0),
        "vitamin_c": float(food.get("vitamin_c") or 0.0),
        "protein_density_score": float(food.get("protein_density_score") or 0.0),
        "fiber_score": float(food.get("fiber_score") or 0.0),
        "calcium_score": float(food.get("calcium_score") or 0.0),
        "iron_score": float(food.get("iron_score") or 0.0),
        "vitamin_c_score": float(food.get("vitamin_c_score") or 0.0),
        "representative_unit_price": representative_unit_price,
        "regional_price_low": regional_price_low,
        "regional_price_high": regional_price_high,
        "regional_price_span": max(0.0, regional_price_high - regional_price_low),
        "vegetarian": int(gr._metadata_bool(food, "vegetarian")),  # noqa: SLF001
        "vegan": int(gr._metadata_bool(food, "vegan")),  # noqa: SLF001
        "dairy_free": int(gr._metadata_bool(food, "dairy_free")),  # noqa: SLF001
        "gluten_free": int(gr._metadata_bool(food, "gluten_free")),  # noqa: SLF001
        "high_protein": int(gr._metadata_bool(food, "high_protein")),  # noqa: SLF001
        "breakfast_friendly": int(gr._metadata_bool(food, "breakfast_friendly")),  # noqa: SLF001
        "shelf_stable": int(gr._metadata_bool(food, "shelf_stable")),  # noqa: SLF001
        "cold_only": int(gr._metadata_bool(food, "cold_only")),  # noqa: SLF001
        "microwave_friendly": int(gr._metadata_bool(food, "microwave_friendly")),  # noqa: SLF001
        "price_available": int(representative_unit_price > 0),
        "usda_price_reference": int(price_source == "usda_area"),
        "bls_area_price_reference": int(price_source == "bls_area"),
        "bls_fallback_price_reference": int(price_source == "bls_national"),
        "meal_tag_breakfast": int("breakfast" in meal_tags),
        "meal_tag_lunch": int("lunch" in meal_tags),
        "meal_tag_dinner": int("dinner" in meal_tags),
        "meal_tag_snack": int("snack" in meal_tags),
        "meal_tag_side": int("side" in meal_tags),
    }
    return feature_row


def build_training_rows(
    db_path: str | Path | None = None,
    *,
    price_area_code: str = "0",
    usda_area_code: str = "US",
) -> list[dict[str, object]]:
    resolved_db_path = Path(db_path) if db_path is not None else (project_root() / "data" / "data.db")
    with duckdb.connect(resolved_db_path, read_only=True) as con:
        available = load_candidate_foods(con, price_area_code=price_area_code, usda_area_code=usda_area_code)

    labels = derive_role_labels(available)
    rows: list[dict[str, object]] = []
    for food_id in sorted(available, key=lambda key: (int(available[key]["commonality_rank"]), str(available[key]["display_name"]))):
        feature_row = _feature_row(available[food_id])
        feature_row.update(labels[food_id])
        rows.append(feature_row)
    return rows


def dataset_schema_summary(rows: list[dict[str, object]]) -> dict[str, object]:
    label_counts = Counter(str(row["label_role"]) for row in rows)
    label_sources = Counter(str(row["label_source"]) for row in rows)
    return {
        "row_count": len(rows),
        "label_counts": dict(sorted(label_counts.items())),
        "label_sources": dict(sorted(label_sources.items())),
        "numeric_features": list(NUMERIC_FEATURES),
        "boolean_features": list(BOOLEAN_FEATURES),
        "categorical_features": list(CATEGORICAL_FEATURES),
        "label_column": "label_role",
    }


def write_training_dataset(output_path: str | Path | None = None, *, db_path: str | Path | None = None) -> tuple[Path, Path]:
    rows = build_training_rows(db_path=db_path)
    dataset_path = Path(output_path) if output_path is not None else default_dataset_path()
    dataset_path.parent.mkdir(parents=True, exist_ok=True)
    schema_path = dataset_path.with_suffix(".schema.json")

    fieldnames = list(rows[0].keys())
    with dataset_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    schema_summary = dataset_schema_summary(rows)
    schema_path.write_text(json.dumps(schema_summary, indent=2, sort_keys=True), encoding="utf-8")
    return dataset_path, schema_path

