"""Dataset generation utilities for the learned grocery candidate generator."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
import csv
import hashlib
import json
from pathlib import Path

import duckdb

from dietdashboard import hybrid_planner
from dietdashboard import model_candidate_features as candidate_features
from dietdashboard import model_candidate_generator
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
        "context_id": "midwest",
        "usda_area_code": "MIDWEST",
        "usda_area_name": "Midwest",
        "bls_area_code": "200",
        "bls_area_name": "Midwest urban",
        "store_count": 3,
    },
    {
        "context_id": "south",
        "usda_area_code": "SOUTH",
        "usda_area_name": "South",
        "bls_area_code": "300",
        "bls_area_name": "South urban",
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
    (5, "balanced"),
    (7, "bulk"),
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
        "scenario_id": "fat_loss_high_protein",
        "protein_target_g": 150.0,
        "calorie_target_kcal": 1750.0,
        "preferences": {"meal_style": "lunch_dinner"},
        "nutrition_targets": {"carbohydrate": 170.0, "fat": 55.0, "fiber": 34.0, "calcium": 1000.0, "iron": 18.0, "vitamin_c": 100.0},
    },
    {
        "scenario_id": "high_protein_vegetarian",
        "protein_target_g": 145.0,
        "calorie_target_kcal": 2350.0,
        "preferences": {"meal_style": "any", "vegetarian": True},
        "nutrition_targets": {"carbohydrate": 255.0, "fat": 75.0, "fiber": 34.0, "calcium": 1200.0, "iron": 18.0, "vitamin_c": 95.0},
    },
    {
        "scenario_id": "vegan_balanced",
        "protein_target_g": 125.0,
        "calorie_target_kcal": 2200.0,
        "preferences": {"meal_style": "lunch_dinner", "vegan": True},
        "nutrition_targets": {"carbohydrate": 245.0, "fat": 68.0, "fiber": 36.0, "iron": 20.0, "vitamin_c": 100.0},
    },
    {
        "scenario_id": "dairy_free_high_protein",
        "protein_target_g": 135.0,
        "calorie_target_kcal": 2150.0,
        "preferences": {"meal_style": "any", "dairy_free": True},
        "nutrition_targets": {"carbohydrate": 225.0, "fat": 68.0, "fiber": 28.0, "iron": 18.0},
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
        "scenario_id": "snack_low_prep",
        "protein_target_g": 95.0,
        "calorie_target_kcal": 1800.0,
        "preferences": {"meal_style": "snack", "low_prep": True},
        "nutrition_targets": {"carbohydrate": 190.0, "fat": 60.0, "fiber": 24.0},
    },
)


def project_root() -> Path:
    return model_candidate_generator.project_root()


def default_db_path() -> Path:
    return project_root() / "data" / "data.db"


def default_dataset_path() -> Path:
    return model_candidate_generator.default_model_dir() / "candidate_generator_training_dataset.csv"


def default_schema_path() -> Path:
    return default_dataset_path().with_suffix(".schema.json")


def default_scenarios_path() -> Path:
    return model_candidate_generator.default_model_dir() / "candidate_generator_training_scenarios.json"


def _stable_split(scenario_id: str) -> str:
    bucket = int(hashlib.md5(scenario_id.encode("utf-8")).hexdigest()[:8], 16) % 10  # noqa: S324
    if bucket < 2:
        return "test"
    if bucket < 4:
        return "validation"
    return "train"


def _stub_stores(count: int, prefix: str) -> list[dict[str, object]]:
    return [
        {
            "store_id": f"{prefix}:store_{index}",
            "name": f"Training Store {index}",
            "address": f"{index} Demo St",
            "distance_m": float(200 + index * 125),
            "lat": 37.3861 + (index * 0.001),
            "lon": -122.0839 - (index * 0.001),
            "category": "supermarket" if index % 2 == 0 else "grocery",
        }
        for index in range(count)
    ]


def _pantry_variants(preferences: Mapping[str, object]) -> list[tuple[str, list[str]]]:
    normalized_preferences = dict(preferences)
    vegetarian = bool(normalized_preferences.get("vegetarian"))
    vegan = bool(normalized_preferences.get("vegan"))
    dairy_free = bool(normalized_preferences.get("dairy_free"))
    meal_style = str(normalized_preferences.get("meal_style") or "any")

    if vegan:
        variants = [
            ("empty", []),
            ("vegan_staples", ["rice", "oats", "lentils"]),
            ("produce_stocked", ["bananas", "spinach", "carrots"]),
        ]
    elif vegetarian:
        variants = [
            ("empty", []),
            ("veg_staples", ["rice", "oats", "lentils"]),
            ("veg_mixed", ["bananas", "spinach", "eggs"]),
        ]
    else:
        variants = [
            ("empty", []),
            ("protein_stocked", ["rice", "oats", "eggs"]),
            ("mixed_staples", ["bananas", "wholemeal_bread", "peanut_butter"]),
        ]

    if dairy_free:
        variants = [
            (name, [food_id for food_id in food_ids if food_id not in {"milk", "greek_yogurt", "protein_yogurt", "cheese", "cottage_cheese"}])
            for name, food_ids in variants
        ]
    if meal_style == "breakfast":
        variants.append(("breakfast_pantry", ["oats", "bananas", "wholemeal_bread"]))
    if meal_style == "snack":
        variants.append(("snack_pantry", ["bananas", "apples", "peanut_butter"]))

    deduped: list[tuple[str, list[str]]] = []
    seen_items: set[tuple[str, ...]] = set()
    for name, items in variants:
        key = tuple(sorted(items))
        if key in seen_items:
            continue
        seen_items.add(key)
        deduped.append((name, items))
    return deduped[:3]


def scenario_grid(*, scenario_limit: int | None = None) -> list[dict[str, object]]:
    scenarios: list[dict[str, object]] = []
    for template in SCENARIO_TEMPLATES:
        for price_context in PRICE_CONTEXTS:
            for days, shopping_mode in WINDOW_VARIANTS:
                for pantry_name, pantry_items in _pantry_variants(template["preferences"]):
                    scenario_id = f"{template['scenario_id']}:{price_context['context_id']}:{days}:{shopping_mode}:{pantry_name}"
                    scenarios.append(
                        {
                            "scenario_id": scenario_id,
                            "split": _stable_split(scenario_id),
                            "protein_target_g": float(template["protein_target_g"]),
                            "calorie_target_kcal": float(template["calorie_target_kcal"]),
                            "preferences": dict(template["preferences"]),
                            "nutrition_targets": dict(template["nutrition_targets"]),
                            "pantry_items": list(pantry_items),
                            "days": int(days),
                            "shopping_mode": shopping_mode,
                            "price_context": {
                                "usda_area_code": str(price_context["usda_area_code"]),
                                "usda_area_name": str(price_context["usda_area_name"]),
                                "bls_area_code": str(price_context["bls_area_code"]),
                                "bls_area_name": str(price_context["bls_area_name"]),
                            },
                            "stores": _stub_stores(int(price_context["store_count"]), scenario_id),
                        }
                    )
    scenarios.sort(key=lambda row: str(row["scenario_id"]))
    if scenario_limit is not None:
        return scenarios[: max(1, int(scenario_limit))]
    return scenarios


def _target_candidate(candidates: Sequence[Mapping[str, object]]) -> tuple[dict[str, object], float]:
    ranked: list[tuple[float, str, dict[str, object]]] = []
    for candidate in candidates:
        feature_row = plan_scorer.extract_candidate_features(candidate)
        label_score = plan_scorer.heuristic_candidate_label(feature_row)
        ranked.append((float(label_score), str(candidate["candidate_id"]), dict(candidate)))
    best_score, _candidate_id, best_candidate = sorted(ranked, key=lambda row: (-row[0], row[1]))[0]
    return best_candidate, best_score


def build_training_rows(
    db_path: str | Path | None = None,
    *,
    candidate_count: int = 10,
    scenario_limit: int | None = None,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    resolved_db_path = Path(db_path) if db_path is not None else default_db_path()
    scenarios = scenario_grid(scenario_limit=scenario_limit)
    rows: list[dict[str, object]] = []
    with duckdb.connect(resolved_db_path, read_only=True) as con:
        for scenario in scenarios:
            context = hybrid_planner._prepare_context(  # noqa: SLF001
                con,
                protein_target_g=float(scenario["protein_target_g"]),
                calorie_target_kcal=float(scenario["calorie_target_kcal"]),
                preferences=dict(scenario["preferences"]),
                nutrition_targets=dict(scenario["nutrition_targets"]),
                pantry_items=list(scenario["pantry_items"]),
                days=int(scenario["days"]),
                shopping_mode=str(scenario["shopping_mode"]),
                price_context=dict(scenario["price_context"]),
                nearby_store_count=len(scenario["stores"]),
            )
            candidates = hybrid_planner.recommend_generic_food_candidates(
                con,
                protein_target_g=float(scenario["protein_target_g"]),
                calorie_target_kcal=float(scenario["calorie_target_kcal"]),
                preferences=dict(scenario["preferences"]),
                nutrition_targets=dict(scenario["nutrition_targets"]),
                pantry_items=list(scenario["pantry_items"]),
                days=int(scenario["days"]),
                shopping_mode=str(scenario["shopping_mode"]),
                price_context=dict(scenario["price_context"]),
                stores=list(scenario["stores"]),
                candidate_count=candidate_count,
            )
            target_candidate, target_candidate_score = _target_candidate(candidates)
            selected_by_role: dict[str, set[str]] = defaultdict(set)
            for item in target_candidate["recommendation"]["shopping_list"]:
                selected_by_role[str(item["role"])].add(str(item["generic_food_id"]))

            context_features = candidate_features.build_context_features(
                protein_target_g=float(scenario["protein_target_g"]),
                calorie_target_kcal=float(scenario["calorie_target_kcal"]),
                preferences=dict(scenario["preferences"]),
                nutrition_targets=dict(scenario["nutrition_targets"]),
                days=int(scenario["days"]),
                shopping_mode=str(scenario["shopping_mode"]),
                price_context=dict(scenario["price_context"]),
                pantry_items=list(scenario["pantry_items"]),
                nearby_store_count=len(scenario["stores"]),
                available_food_count=len(context.available),
                goal_profile=context.goal_profile,
                basket_policy=context.basket_policy,
            )
            role_rank_maps = {
                role: {food_id: index + 1 for index, food_id in enumerate(context.role_orders[role])}
                for role in candidate_features.ROLE_LABELS
            }
            for role in candidate_features.ROLE_LABELS:
                for food_id, food in context.available.items():
                    if food_id not in context.role_scores[role]:
                        continue
                    feature_row = candidate_features.build_food_role_features(
                        food=food,
                        role=role,
                        context_features=context_features,
                        pantry_items=list(scenario["pantry_items"]),
                        heuristic_role_score=float(context.role_scores[role][food_id]),
                        heuristic_role_rank=int(role_rank_maps[role].get(food_id, len(role_rank_maps[role]) + 1)),
                    )
                    rows.append(
                        {
                            "scenario_id": str(scenario["scenario_id"]),
                            "split": str(scenario["split"]),
                            "generic_food_id": str(food_id),
                            "display_name": str(food["display_name"]),
                            "role": role,
                            "label_selected": int(food_id in selected_by_role[role]),
                            "target_candidate_id": str(target_candidate["candidate_id"]),
                            "target_candidate_score": round(float(target_candidate_score), 6),
                            **feature_row,
                        }
                    )
    return rows, scenarios


def dataset_schema_summary(rows: Sequence[Mapping[str, object]], scenarios: Sequence[Mapping[str, object]]) -> dict[str, object]:
    split_counter = Counter(str(row["split"]) for row in rows)
    scenario_split_counter = Counter(str(row["split"]) for row in scenarios)
    positive_counter = Counter(str(row["role"]) for row in rows if int(row["label_selected"]) == 1)
    row_counter = Counter(str(row["role"]) for row in rows)
    return {
        "row_count": len(rows),
        "scenario_count": len(scenarios),
        "split_row_counts": dict(sorted(split_counter.items())),
        "split_scenario_counts": dict(sorted(scenario_split_counter.items())),
        "role_positive_counts": dict(sorted(positive_counter.items())),
        "role_positive_rates": {
            role: round(positive_counter.get(role, 0) / max(row_counter.get(role, 1), 1), 6)
            for role in candidate_features.ROLE_LABELS
        },
        "numeric_features": list(candidate_features.NUMERIC_FEATURES),
        "boolean_features": list(candidate_features.BOOLEAN_FEATURES),
        "categorical_features": list(candidate_features.CATEGORICAL_FEATURES),
        "metadata_fields": list(candidate_features.TRAINING_METADATA_FIELDS),
        "label_field": "label_selected",
        "candidate_count_per_scenario": None,
    }


def write_training_dataset(
    output_path: str | Path | None = None,
    *,
    db_path: str | Path | None = None,
    candidate_count: int = 10,
    scenario_limit: int | None = None,
) -> tuple[Path, Path, Path, list[dict[str, object]], list[dict[str, object]]]:
    rows, scenarios = build_training_rows(
        db_path=db_path,
        candidate_count=candidate_count,
        scenario_limit=scenario_limit,
    )
    dataset_path = Path(output_path) if output_path is not None else default_dataset_path()
    dataset_path.parent.mkdir(parents=True, exist_ok=True)
    schema_path = dataset_path.with_suffix(".schema.json")
    scenarios_path = default_scenarios_path() if output_path is None else dataset_path.with_suffix(".scenarios.json")

    fieldnames = [
        *candidate_features.TRAINING_METADATA_FIELDS,
        *candidate_features.NUMERIC_FEATURES,
        *candidate_features.BOOLEAN_FEATURES,
        *candidate_features.CATEGORICAL_FEATURES,
    ]
    with dataset_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    schema_payload = dataset_schema_summary(rows, scenarios)
    schema_payload["candidate_count_per_scenario"] = candidate_count
    schema_path.write_text(json.dumps(schema_payload, indent=2, sort_keys=True), encoding="utf-8")
    scenarios_path.write_text(json.dumps(list(scenarios), indent=2, sort_keys=True), encoding="utf-8")
    return dataset_path, schema_path, scenarios_path, rows, scenarios


def load_dataset_rows(
    dataset_path: str | Path | None = None,
    *,
    splits: Sequence[str] | None = None,
) -> list[dict[str, object]]:
    resolved_dataset_path = Path(dataset_path) if dataset_path is not None else default_dataset_path()
    allowed_splits = {str(split) for split in splits} if splits is not None else None
    rows: list[dict[str, object]] = []
    with resolved_dataset_path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for raw_row in reader:
            if allowed_splits is not None and str(raw_row["split"]) not in allowed_splits:
                continue
            row: dict[str, object] = {}
            for field in candidate_features.TRAINING_METADATA_FIELDS:
                if field == "label_selected":
                    row[field] = int(raw_row[field] or 0)
                elif field == "target_candidate_score":
                    row[field] = float(raw_row[field] or 0.0)
                else:
                    row[field] = raw_row[field]
            for field in candidate_features.NUMERIC_FEATURES:
                row[field] = float(raw_row[field] or 0.0)
            for field in candidate_features.BOOLEAN_FEATURES:
                row[field] = int(float(raw_row[field] or 0))
            for field in candidate_features.CATEGORICAL_FEATURES:
                row[field] = raw_row[field]
            rows.append(row)
    return rows


def train_and_save_model(
    *,
    dataset_path: str | Path | None = None,
    output_dir: str | Path | None = None,
    model_output_path: str | Path | None = None,
    backend: str = "auto",
    hyperparameters: Mapping[str, object] | None = None,
    config_path: str | Path | None = None,
    random_seed: int = model_candidate_generator.DEFAULT_RANDOM_SEED,
) -> dict[str, object]:
    resolved_output_dir = Path(output_dir) if output_dir is not None else model_candidate_generator.default_model_dir()
    resolved_output_dir.mkdir(parents=True, exist_ok=True)

    config_payload = None
    if config_path is not None:
        config_payload = json.loads(Path(config_path).read_text(encoding="utf-8"))
        backend = str(config_payload["backend"])
        hyperparameters = dict(config_payload.get("hyperparameters") or {})
        random_seed = int(config_payload.get("random_seed", random_seed))
    resolved_backend = model_candidate_generator.resolve_backend(backend)
    resolved_hyperparameters = dict(hyperparameters or {})

    training_rows = load_dataset_rows(dataset_path, splits=("train", "validation"))
    test_rows = load_dataset_rows(dataset_path, splits=("test",))
    if not training_rows:
        raise ValueError("Candidate-generator training requires train/validation rows.")
    evaluation_split = "test"
    if not test_rows:
        validation_rows = load_dataset_rows(dataset_path, splits=("validation",))
        if validation_rows:
            test_rows = validation_rows
            evaluation_split = "validation_fallback"
        else:
            test_rows = list(training_rows)
            evaluation_split = "train_validation_fallback"

    bundle = model_candidate_generator.fit_bundle(
        training_rows,
        backend=resolved_backend,
        random_seed=random_seed,
        hyperparameters=resolved_hyperparameters,
    )
    test_metrics = model_candidate_generator.evaluate_rows(bundle, test_rows, prefix="test")
    bundle["metrics"] = {
        "backend": resolved_backend,
        "hyperparameters": resolved_hyperparameters,
        "random_seed": random_seed,
        "evaluation_split": evaluation_split,
        "train_validation_row_count": len(training_rows),
        "test_row_count": len(test_rows),
        **test_metrics,
    }
    if config_payload is not None:
        bundle["selected_config"] = config_payload

    resolved_model_path = Path(model_output_path) if model_output_path is not None else resolved_output_dir / model_candidate_generator.default_model_path().name
    model_path = model_candidate_generator.save_bundle(bundle, resolved_model_path)
    metrics_path = resolved_output_dir / f"{model_path.stem}_metrics.json"
    metrics_path.write_text(json.dumps(bundle["metrics"], indent=2, sort_keys=True), encoding="utf-8")

    feature_summary_rows = model_candidate_generator.feature_summary_rows(bundle, reference_rows=test_rows)
    feature_summary_path = resolved_output_dir / f"{model_path.stem}_feature_summary.csv"
    if feature_summary_rows:
        with feature_summary_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(feature_summary_rows[0].keys()))
            writer.writeheader()
            writer.writerows(feature_summary_rows)

    return {
        "dataset_path": Path(dataset_path) if dataset_path is not None else default_dataset_path(),
        "model_path": model_path,
        "metrics_path": metrics_path,
        "feature_summary_path": feature_summary_path,
        "metrics": dict(bundle["metrics"]),
    }
