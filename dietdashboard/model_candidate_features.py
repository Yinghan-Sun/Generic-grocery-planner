"""Shared feature extraction for the learned candidate generator."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from dietdashboard import generic_recommender as gr

ROLE_LABELS = ("protein_anchor", "carb_base", "produce", "calorie_booster")
NUMERIC_FEATURES = (
    "target_protein_g",
    "target_calorie_kcal",
    "target_carbohydrate_g",
    "target_fat_g",
    "target_fiber_g",
    "target_calcium_mg",
    "target_iron_mg",
    "target_vitamin_c_mg",
    "days",
    "nearby_store_count",
    "pantry_item_count",
    "available_food_count",
    "target_protein_anchor_count",
    "target_carb_base_count",
    "target_produce_count",
    "target_calorie_booster_count",
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
    "heuristic_role_score",
    "heuristic_role_rank",
)
BOOLEAN_FEATURES = (
    "budget_friendly_preference",
    "low_prep_preference",
    "vegetarian_preference",
    "vegan_preference",
    "dairy_free_preference",
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
    "bls_national_price_reference",
    "meal_tag_breakfast",
    "meal_tag_lunch",
    "meal_tag_dinner",
    "meal_tag_snack",
    "meal_tag_side",
    "food_in_pantry",
)
CATEGORICAL_FEATURES = (
    "goal_profile",
    "shopping_mode",
    "meal_style",
    "bls_area_code",
    "usda_area_code",
    "food_family",
    "purchase_unit",
    "prep_level",
    "shelf_stability",
    "price_reference_source",
    "role",
)
TRAINING_METADATA_FIELDS = (
    "scenario_id",
    "split",
    "generic_food_id",
    "display_name",
    "role",
    "label_selected",
    "target_candidate_id",
    "target_candidate_score",
)


def _safe_float(value: object) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _safe_int(value: object) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _bool_int(value: object) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, str):
        return int(value.strip().lower() in {"1", "true", "yes"})
    return int(bool(value))


def build_context_features(
    *,
    protein_target_g: float,
    calorie_target_kcal: float,
    preferences: Mapping[str, object] | None,
    nutrition_targets: Mapping[str, float | int | None] | None,
    days: int,
    shopping_mode: str,
    price_context: Mapping[str, object] | None,
    pantry_items: Sequence[str] | None,
    nearby_store_count: int,
    available_food_count: int,
    goal_profile: str | None = None,
    basket_policy: Mapping[str, object] | None = None,
) -> dict[str, object]:
    normalized_preferences = gr._effective_preferences(dict(preferences or {}))  # noqa: SLF001
    normalized_targets = {
        key: _safe_float(value)
        for key, value in (nutrition_targets or {}).items()
        if value is not None and _safe_float(value) > 0
    }
    resolved_goal_profile = goal_profile or gr._detect_goal_profile(  # noqa: SLF001
        protein_target_g,
        calorie_target_kcal,
        normalized_preferences,
        normalized_targets,
    )
    resolved_basket_policy = basket_policy or gr._goal_basket_policy(  # noqa: SLF001
        resolved_goal_profile,
        protein_target_g,
        calorie_target_kcal,
        normalized_targets,
    )
    resolved_price_context = dict(price_context or {})
    return {
        "target_protein_g": round(float(protein_target_g), 6),
        "target_calorie_kcal": round(float(calorie_target_kcal), 6),
        "target_carbohydrate_g": round(_safe_float(normalized_targets.get("carbohydrate")), 6),
        "target_fat_g": round(_safe_float(normalized_targets.get("fat")), 6),
        "target_fiber_g": round(_safe_float(normalized_targets.get("fiber")), 6),
        "target_calcium_mg": round(_safe_float(normalized_targets.get("calcium")), 6),
        "target_iron_mg": round(_safe_float(normalized_targets.get("iron")), 6),
        "target_vitamin_c_mg": round(_safe_float(normalized_targets.get("vitamin_c")), 6),
        "days": max(1, _safe_int(days)),
        "nearby_store_count": max(0, _safe_int(nearby_store_count)),
        "pantry_item_count": len({str(food_id).strip() for food_id in (pantry_items or []) if str(food_id).strip()}),
        "available_food_count": max(0, _safe_int(available_food_count)),
        "target_protein_anchor_count": max(1, _safe_int(resolved_basket_policy.get("desired_protein_anchors", 1))),
        "target_carb_base_count": 1,
        "target_produce_count": max(1, _safe_int(resolved_basket_policy.get("desired_produce_items", 1))),
        "target_calorie_booster_count": int(bool(resolved_basket_policy.get("booster_enabled", False))),
        "budget_friendly_preference": _bool_int(normalized_preferences.get("budget_friendly")),
        "low_prep_preference": 0,
        "vegetarian_preference": _bool_int(normalized_preferences.get("vegetarian")),
        "vegan_preference": _bool_int(normalized_preferences.get("vegan")),
        "dairy_free_preference": _bool_int(normalized_preferences.get("dairy_free")),
        "goal_profile": str(resolved_goal_profile),
        "shopping_mode": str(shopping_mode or "balanced"),
        "meal_style": str(normalized_preferences.get("meal_style") or "any"),
        "bls_area_code": str(resolved_price_context.get("bls_area_code") or "0"),
        "usda_area_code": str(resolved_price_context.get("usda_area_code") or "US"),
    }


def build_food_role_features(
    *,
    food: Mapping[str, object],
    role: str,
    context_features: Mapping[str, object],
    pantry_items: Sequence[str] | None,
    heuristic_role_score: float,
    heuristic_role_rank: int,
) -> dict[str, object]:
    meal_tags = gr._meal_tags(dict(food))  # noqa: SLF001
    regional_price_low = _safe_float(food.get("regional_price_low"))
    regional_price_high = _safe_float(food.get("regional_price_high"))
    price_source = str(food.get("price_reference_source") or "none")
    food_id = str(food.get("generic_food_id") or "")

    row = dict(context_features)
    row.update(
        {
            "default_serving_g": _safe_float(food.get("default_serving_g")),
            "purchase_unit_size_g": _safe_float(food.get("purchase_unit_size_g")),
            "budget_score": _safe_float(food.get("budget_score")),
            "commonality_rank": _safe_float(food.get("commonality_rank")),
            "energy_fibre_kcal": _safe_float(food.get("energy_fibre_kcal")),
            "protein": _safe_float(food.get("protein")),
            "carbohydrate": _safe_float(food.get("carbohydrate")),
            "fat": _safe_float(food.get("fat")),
            "fiber": _safe_float(food.get("fiber")),
            "calcium": _safe_float(food.get("calcium")),
            "iron": _safe_float(food.get("iron")),
            "vitamin_c": _safe_float(food.get("vitamin_c")),
            "protein_density_score": _safe_float(food.get("protein_density_score")),
            "fiber_score": _safe_float(food.get("fiber_score")),
            "calcium_score": _safe_float(food.get("calcium_score")),
            "iron_score": _safe_float(food.get("iron_score")),
            "vitamin_c_score": _safe_float(food.get("vitamin_c_score")),
            "representative_unit_price": _safe_float(food.get("bls_estimated_unit_price")),
            "regional_price_low": regional_price_low,
            "regional_price_high": regional_price_high,
            "regional_price_span": max(0.0, regional_price_high - regional_price_low),
            "heuristic_role_score": round(float(heuristic_role_score), 6),
            "heuristic_role_rank": max(1, _safe_int(heuristic_role_rank)),
            "vegetarian": _bool_int(food.get("vegetarian")),
            "vegan": _bool_int(food.get("vegan")),
            "dairy_free": _bool_int(food.get("dairy_free")),
            "gluten_free": _bool_int(food.get("gluten_free")),
            "high_protein": _bool_int(gr._metadata_bool(dict(food), "high_protein")),  # noqa: SLF001
            "breakfast_friendly": _bool_int(gr._metadata_bool(dict(food), "breakfast_friendly")),  # noqa: SLF001
            "shelf_stable": _bool_int(gr._is_shelf_stable(dict(food))),  # noqa: SLF001
            "cold_only": _bool_int(gr._metadata_bool(dict(food), "cold_only")),  # noqa: SLF001
            "microwave_friendly": _bool_int(gr._metadata_bool(dict(food), "microwave_friendly")),  # noqa: SLF001
            "price_available": _bool_int(_safe_float(food.get("bls_estimated_unit_price")) > 0),
            "usda_price_reference": _bool_int(price_source == "usda_area"),
            "bls_area_price_reference": _bool_int(price_source == "bls_area"),
            "bls_national_price_reference": _bool_int(price_source == "bls_national"),
            "meal_tag_breakfast": _bool_int("breakfast" in meal_tags),
            "meal_tag_lunch": _bool_int("lunch" in meal_tags),
            "meal_tag_dinner": _bool_int("dinner" in meal_tags),
            "meal_tag_snack": _bool_int("snack" in meal_tags),
            "meal_tag_side": _bool_int("side" in meal_tags),
            "food_in_pantry": _bool_int(food_id in {str(item).strip() for item in (pantry_items or []) if str(item).strip()}),
            "food_family": str(food.get("food_family") or ""),
            "purchase_unit": str(food.get("purchase_unit") or ""),
            "prep_level": str(food.get("prep_level") or ""),
            "shelf_stability": str(food.get("shelf_stability") or ""),
            "price_reference_source": price_source,
            "role": str(role),
        }
    )
    return row
