"""Heuristic generic-food recommendation logic for the MVP."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
import math
import re

import duckdb

DEFAULT_ASSUMPTIONS = [
    "Recommendations are generic and are not matched to exact store inventory.",
    "Quantities are approximate and intended as a simple shopping guide.",
]
NUTRIENT_SUMMARY_META = {
    "protein": ("protein_target_g", "protein_estimated_g"),
    "energy_fibre_kcal": ("calorie_target_kcal", "calorie_estimated_kcal"),
    "carbohydrate": ("carbohydrate_target_g", "carbohydrate_estimated_g"),
    "fat": ("fat_target_g", "fat_estimated_g"),
    "fiber": ("fiber_target_g", "fiber_estimated_g"),
    "calcium": ("calcium_target_mg", "calcium_estimated_mg"),
    "iron": ("iron_target_mg", "iron_estimated_mg"),
    "vitamin_c": ("vitamin_c_target_mg", "vitamin_c_estimated_mg"),
}

PREP_LEVEL_SCORES = {"none": 3.0, "low": 2.0, "medium": 1.0, "high": 0.0}
MEAL_STYLE_OPTIONS = {"breakfast", "lunch_dinner", "snack", "any"}
SHOPPING_MODE_OPTIONS = {"fresh", "balanced", "bulk"}
GOAL_PROFILE_OPTIONS = {
    "muscle_gain",
    "fat_loss",
    "maintenance",
    "high_protein_vegetarian",
    "budget_friendly_healthy",
    "generic_balanced",
}
GOAL_BASE_TARGETS = {
    "generic_balanced": {"protein": 100.0, "energy_fibre_kcal": 2200.0, "carbohydrate": 250.0, "fat": 70.0, "fiber": 30.0},
    "muscle_gain": {"protein": 180.0, "energy_fibre_kcal": 2800.0, "carbohydrate": 330.0, "fat": 85.0, "fiber": 35.0},
    "fat_loss": {"protein": 145.0, "energy_fibre_kcal": 1700.0, "carbohydrate": 160.0, "fat": 55.0, "fiber": 32.0},
    "maintenance": {"protein": 115.0, "energy_fibre_kcal": 2250.0, "carbohydrate": 240.0, "fat": 70.0, "fiber": 30.0},
    "budget_friendly_healthy": {"protein": 110.0, "energy_fibre_kcal": 2100.0, "carbohydrate": 240.0, "fat": 65.0, "fiber": 32.0},
    "high_protein_vegetarian": {"protein": 145.0, "energy_fibre_kcal": 2400.0, "carbohydrate": 260.0, "fat": 75.0, "fiber": 32.0},
}
MEAL_STYLE_TAGS = {
    "breakfast": {"breakfast"},
    "lunch_dinner": {"lunch", "dinner"},
    "snack": {"snack", "side"},
}
STATE_REGION_CODES = {
    "CT": "100", "ME": "100", "MA": "100", "NH": "100", "RI": "100", "VT": "100",
    "NJ": "100", "NY": "100", "PA": "100",
    "IL": "200", "IN": "200", "MI": "200", "OH": "200", "WI": "200",
    "IA": "200", "KS": "200", "MN": "200", "MO": "200", "NE": "200", "ND": "200", "SD": "200",
    "DE": "300", "DC": "300", "FL": "300", "GA": "300", "MD": "300", "NC": "300", "SC": "300", "VA": "300", "WV": "300",
    "AL": "300", "KY": "300", "MS": "300", "TN": "300",
    "AR": "300", "LA": "300", "OK": "300", "TX": "300",
    "AZ": "400", "CO": "400", "ID": "400", "MT": "400", "NV": "400", "NM": "400", "UT": "400", "WY": "400",
    "AK": "400", "CA": "400", "HI": "400", "OR": "400", "WA": "400",
}
BLS_AREA_NAMES = {
    "0": "U.S. city average",
    "100": "Northeast urban",
    "200": "Midwest urban",
    "300": "South urban",
    "400": "West urban",
}
USDA_AREA_NAMES = {
    "US": "U.S. average",
    "NORTHEAST": "Northeast",
    "MIDWEST": "Midwest",
    "SOUTH": "South",
    "WEST": "West",
    "ATLANTA": "Atlanta",
    "BOSTON": "Boston",
    "CHICAGO": "Chicago",
    "DALLAS": "Dallas",
    "DETROIT": "Detroit",
    "HOUSTON": "Houston",
    "LOS_ANGELES": "Los Angeles",
    "MIAMI": "Miami",
    "NEW_YORK": "New York",
    "PHILADELPHIA": "Philadelphia",
}
USDA_METRO_BBOXES = {
    "ATLANTA": (33.4, 34.2, -85.1, -83.5),
    "BOSTON": (42.0, 42.7, -71.5, -70.7),
    "CHICAGO": (41.5, 42.3, -88.3, -87.2),
    "DALLAS": (32.4, 33.1, -97.4, -96.4),
    "DETROIT": (42.1, 42.7, -83.5, -82.8),
    "HOUSTON": (29.4, 30.2, -95.9, -94.9),
    "LOS_ANGELES": (33.6, 34.4, -118.9, -117.6),
    "MIAMI": (25.5, 26.1, -80.6, -80.0),
    "NEW_YORK": (40.45, 41.05, -74.4, -73.5),
    "PHILADELPHIA": (39.7, 40.2, -75.5, -74.8),
}
USDA_REGION_FROM_BLS = {"100": "NORTHEAST", "200": "MIDWEST", "300": "SOUTH", "400": "WEST"}
PRICE_EFFICIENCY_DIVISORS = {
    "protein": 18.0,
    "energy_fibre_kcal": 450.0,
    "carbohydrate": 90.0,
    "fiber": 8.0,
    "calcium": 120.0,
    "vitamin_c": 60.0,
}
BREAKFAST_PROTEIN_IDS = {"eggs", "greek_yogurt", "protein_yogurt", "cottage_cheese", "milk"}
BREAKFAST_CARB_IDS = {"oats", "corn_flakes", "bagel", "wholemeal_bread", "pita"}
BREAKFAST_PRODUCE_IDS = {"bananas", "apples", "oranges", "berries", "grapes", "pears", "kiwi", "pineapple", "mango"}
SNACK_PROTEIN_IDS = {"greek_yogurt", "protein_yogurt", "cottage_cheese", "cheese", "eggs", "nuts", "peanut_butter", "almond_butter"}
SNACK_CARB_IDS = {"corn_flakes", "bagel", "wholemeal_bread", "pita", "tortilla"}
SNACK_PRODUCE_IDS = BREAKFAST_PRODUCE_IDS | {"carrots", "cucumber", "celery", "bell_peppers", "tomatoes"}
HEAVY_MEAL_PROTEIN_IDS = {"rotisserie_chicken", "chicken_breast", "ground_beef", "turkey", "salmon", "shrimp"}
MUSCLE_GAIN_PROTEIN_IDS = {"eggs", "milk", "greek_yogurt", "protein_yogurt", "chicken_breast", "turkey", "tuna", "cottage_cheese"}
MUSCLE_GAIN_CARB_IDS = {"oats", "rice", "pasta", "wholemeal_bread", "bagel", "potatoes", "sweet_potatoes", "quinoa"}
MUSCLE_GAIN_PRODUCE_IDS = {"bananas", "berries", "oranges", "spinach", "bell_peppers", "frozen_vegetables", "broccoli"}
MUSCLE_GAIN_BOOSTER_IDS = {"olive_oil", "peanut_butter", "nuts", "almond_butter", "cheese"}
FAT_LOSS_PROTEIN_IDS = {"chicken_breast", "tuna", "tofu", "greek_yogurt", "protein_yogurt", "cottage_cheese", "eggs", "edamame"}
FAT_LOSS_CARB_IDS = {"oats", "potatoes", "sweet_potatoes", "quinoa", "wholemeal_bread"}
FAT_LOSS_PRODUCE_IDS = {"spinach", "lettuce", "cucumber", "tomatoes", "bell_peppers", "broccoli", "cauliflower", "berries", "mushrooms", "zucchini"}
MAINTENANCE_PROTEIN_IDS = {"eggs", "chicken_breast", "tofu", "greek_yogurt", "tuna", "rotisserie_chicken"}
MAINTENANCE_CARB_IDS = {"rice", "oats", "potatoes", "wholemeal_bread", "quinoa"}
MAINTENANCE_PRODUCE_IDS = {"bananas", "apples", "broccoli", "carrots", "bell_peppers", "spinach", "lettuce"}
BUDGET_HEALTHY_PROTEIN_IDS = {"lentils", "beans", "black_beans", "chickpeas", "eggs", "tofu", "peanut_butter"}
BUDGET_HEALTHY_CARB_IDS = {"oats", "rice", "pasta", "potatoes", "wholemeal_bread"}
BUDGET_HEALTHY_PRODUCE_IDS = {"bananas", "apples", "carrots", "cabbage", "broccoli", "lettuce", "onions", "frozen_vegetables", "potatoes"}
BUDGET_HEALTHY_BOOSTER_IDS = {"peanut_butter", "olive_oil"}
HIGH_PROTEIN_VEGETARIAN_PROTEIN_IDS = {"tofu", "greek_yogurt", "protein_yogurt", "cottage_cheese", "eggs", "milk", "edamame"}
HIGH_PROTEIN_VEGETARIAN_CARB_IDS = {"oats", "wholemeal_bread", "quinoa", "rice", "bagel"}
HIGH_PROTEIN_VEGETARIAN_PRODUCE_IDS = {"spinach", "berries", "bananas", "bell_peppers", "broccoli", "oranges"}
GOAL_ROLE_TEMPLATE_IDS = {
    "muscle_gain": {
        "protein_anchor": ("eggs", "greek_yogurt", "protein_yogurt", "cottage_cheese", "turkey", "chicken_breast", "milk"),
        "carb_base": ("oats", "pasta", "potatoes", "bagel", "wholemeal_bread", "rice", "sweet_potatoes"),
        "produce": ("bananas", "berries", "oranges", "bell_peppers", "spinach", "frozen_vegetables"),
        "calorie_booster": ("olive_oil", "peanut_butter", "nuts", "almond_butter", "cheese"),
    },
    "fat_loss": {
        "protein_anchor": ("tuna", "tofu", "greek_yogurt", "protein_yogurt", "cottage_cheese", "chicken_breast", "eggs"),
        "carb_base": ("wholemeal_bread", "quinoa", "oats", "potatoes", "sweet_potatoes"),
        "produce": ("spinach", "bell_peppers", "lettuce", "cucumber", "tomatoes", "broccoli", "cauliflower", "berries"),
        "calorie_booster": (),
    },
    "maintenance": {
        "protein_anchor": ("eggs", "tofu", "chicken_breast", "rotisserie_chicken", "greek_yogurt", "tuna"),
        "carb_base": ("wholemeal_bread", "potatoes", "oats", "quinoa", "rice"),
        "produce": ("carrots", "apples", "lettuce", "bell_peppers", "spinach", "bananas"),
        "calorie_booster": ("olive_oil", "peanut_butter", "nuts"),
    },
    "budget_friendly_healthy": {
        "protein_anchor": ("lentils", "eggs", "tofu", "beans", "peanut_butter"),
        "carb_base": ("rice", "pasta", "potatoes", "oats", "wholemeal_bread"),
        "produce": ("cabbage", "frozen_vegetables", "carrots", "onions", "potatoes", "bananas", "apples", "lettuce"),
        "calorie_booster": ("olive_oil", "peanut_butter"),
    },
    "high_protein_vegetarian": {
        "protein_anchor": ("eggs", "tofu", "greek_yogurt", "protein_yogurt", "cottage_cheese", "edamame", "milk"),
        "carb_base": ("oats", "wholemeal_bread", "quinoa", "rice", "bagel"),
        "produce": ("spinach", "berries", "oranges", "bell_peppers", "bananas", "broccoli"),
        "calorie_booster": ("peanut_butter", "olive_oil"),
    },
}


def _detect_goal_profile(
    protein_target_g: float,
    calorie_target_kcal: float,
    preferences: dict[str, object],
    nutrition_targets: dict[str, float],
) -> str:
    meal_style = str(preferences.get("meal_style") or "any")
    if preferences.get("budget_friendly"):
        return "budget_friendly_healthy"
    if preferences.get("vegetarian") and not preferences.get("vegan") and protein_target_g >= 135:
        return "high_protein_vegetarian"
    if preferences.get("vegetarian") or preferences.get("vegan"):
        return "generic_balanced"
    if meal_style in {"breakfast", "snack"}:
        if calorie_target_kcal >= 2600 or protein_target_g >= 175:
            return "muscle_gain"
        return "generic_balanced"

    carbohydrate_target_g = float(nutrition_targets.get("carbohydrate") or 0.0)
    protein_density_target = protein_target_g / max(calorie_target_kcal / 1000.0, 1.0)
    if calorie_target_kcal >= 2500 or carbohydrate_target_g >= 300 or (protein_target_g >= 160 and calorie_target_kcal >= 2300):
        return "muscle_gain"
    if calorie_target_kcal <= 1900 or (calorie_target_kcal <= 2100 and protein_density_target >= 72):
        return "fat_loss"
    if 1950 <= calorie_target_kcal <= 2450:
        return "maintenance"
    return "generic_balanced"


def _goal_basket_policy(
    goal_profile: str,
    protein_target_g: float,
    calorie_target_kcal: float,
    nutrition_targets: dict[str, float],
) -> dict[str, object]:
    policy: dict[str, object] = {
        "desired_protein_anchors": 2 if protein_target_g >= 90 else 1,
        "desired_produce_items": 2 if calorie_target_kcal >= 1800 or any(
            nutrition_targets.get(key) for key in ("fiber", "calcium", "iron", "vitamin_c")
        ) else 1,
        "carb_share": 0.45 if calorie_target_kcal >= 1800 else 0.35,
        "carb_fiber_ratio": 0.35,
        "booster_gap_ratio": 0.08,
        "booster_gap_floor": 150.0,
        "booster_fat_gap": 10.0,
        "booster_enabled": True,
        "protein_anchor_shares": (0.35, 0.2),
        "target_role_calorie_shares": {
            "protein_anchor": 0.34,
            "carb_base": 0.38,
            "produce": 0.16,
            "calorie_booster": 0.12,
        },
        "fat_loss_overshoot_ratio": 0.05,
        "fat_loss_overshoot_floor": 70.0,
        "final_carb_fill_ratio": 0.7,
        "final_booster_fill_ratio": 1.0,
    }

    if goal_profile == "muscle_gain":
        policy.update(
            {
                "desired_protein_anchors": 2,
                "desired_produce_items": 2,
                "carb_share": 0.47,
                "carb_fiber_ratio": 0.16,
                "booster_gap_ratio": 0.03,
                "booster_gap_floor": 90.0,
                "booster_fat_gap": 6.0,
                "protein_anchor_shares": (0.28, 0.18),
                "target_role_calorie_shares": {
                    "protein_anchor": 0.29,
                    "carb_base": 0.43,
                    "produce": 0.1,
                    "calorie_booster": 0.18,
                },
                "final_carb_fill_ratio": 0.95,
                "final_booster_fill_ratio": 1.15,
            }
        )
    elif goal_profile == "fat_loss":
        policy.update(
            {
                "desired_protein_anchors": 2 if protein_target_g >= 100 else 1,
                "desired_produce_items": 3 if calorie_target_kcal <= 2000 or nutrition_targets.get("fiber") else 2,
                "carb_share": 0.29,
                "carb_fiber_ratio": 0.12,
                "booster_gap_ratio": 0.16,
                "booster_gap_floor": 260.0,
                "booster_fat_gap": 14.0,
                "booster_enabled": False,
                "protein_anchor_shares": (0.42, 0.24),
                "target_role_calorie_shares": {
                    "protein_anchor": 0.43,
                    "carb_base": 0.24,
                    "produce": 0.33,
                    "calorie_booster": 0.0,
                },
                "fat_loss_overshoot_ratio": 0.035,
                "fat_loss_overshoot_floor": 50.0,
                "final_carb_fill_ratio": 0.0,
                "final_booster_fill_ratio": 0.0,
            }
        )
    elif goal_profile == "maintenance":
        policy.update(
            {
                "desired_protein_anchors": 2 if protein_target_g >= 110 else 1,
                "desired_produce_items": 2,
                "carb_share": 0.38,
                "carb_fiber_ratio": 0.22,
                "booster_gap_ratio": 0.1,
                "booster_gap_floor": 180.0,
                "booster_fat_gap": 11.0,
                "protein_anchor_shares": (0.31, 0.18),
                "target_role_calorie_shares": {
                    "protein_anchor": 0.32,
                    "carb_base": 0.37,
                    "produce": 0.19,
                    "calorie_booster": 0.12,
                },
                "final_carb_fill_ratio": 0.55,
                "final_booster_fill_ratio": 0.65,
            }
        )
    elif goal_profile == "budget_friendly_healthy":
        policy.update(
            {
                "desired_protein_anchors": 2 if protein_target_g >= 100 else 1,
                "desired_produce_items": 2,
                "carb_share": 0.36,
                "carb_fiber_ratio": 0.08,
                "booster_gap_ratio": 0.07,
                "booster_gap_floor": 130.0,
                "booster_fat_gap": 9.0,
                "protein_anchor_shares": (0.3, 0.22),
                "target_role_calorie_shares": {
                    "protein_anchor": 0.27,
                    "carb_base": 0.36,
                    "produce": 0.19,
                    "calorie_booster": 0.18,
                },
                "final_carb_fill_ratio": 0.3,
                "final_booster_fill_ratio": 0.55,
            }
        )
    elif goal_profile == "high_protein_vegetarian":
        policy.update(
            {
                "desired_protein_anchors": 2,
                "desired_produce_items": 2,
                "carb_share": 0.34,
                "carb_fiber_ratio": 0.2,
                "booster_gap_ratio": 0.08,
                "booster_gap_floor": 150.0,
                "booster_fat_gap": 8.0,
                "protein_anchor_shares": (0.33, 0.22),
                "target_role_calorie_shares": {
                    "protein_anchor": 0.35,
                    "carb_base": 0.31,
                    "produce": 0.18,
                    "calorie_booster": 0.16,
                },
                "final_carb_fill_ratio": 0.42,
                "final_booster_fill_ratio": 0.75,
            }
        )
    return policy


def _goal_template_ids(goal_profile: str, role: str) -> tuple[str, ...]:
    if goal_profile not in GOAL_PROFILE_OPTIONS or goal_profile == "generic_balanced":
        return ()
    role_map = GOAL_ROLE_TEMPLATE_IDS.get(goal_profile, {})
    return tuple(role_map.get(role, ()))


def _goal_template_ids_for_pick(
    goal_profile: str,
    role: str,
    chosen: Sequence[tuple[str, str]],
    available: dict[str, dict[str, object]],
) -> tuple[str, ...]:
    template_ids = list(_goal_template_ids(goal_profile, role))
    if not template_ids:
        return ()

    chosen_role_ids = [food_id for food_id, chosen_role in chosen if chosen_role == role]
    if goal_profile == "muscle_gain":
        if role == "protein_anchor":
            if chosen_role_ids:
                chosen_has_lean_meat = any(
                    str(available.get(food_id, {}).get("generic_food_id") or "") in {"turkey", "chicken_breast", "tuna"}
                    for food_id in chosen_role_ids
                )
                if chosen_has_lean_meat:
                    return ("eggs", "milk", "greek_yogurt", "protein_yogurt", "cottage_cheese", "turkey", "chicken_breast")
                return ("turkey", "chicken_breast", "eggs", "milk", "greek_yogurt", "protein_yogurt", "cottage_cheese")
            return ("turkey", "chicken_breast", "eggs", "greek_yogurt", "protein_yogurt", "milk", "cottage_cheese")
        if role == "carb_base":
            return ("bagel", "pasta", "oats", "potatoes", "wholemeal_bread", "sweet_potatoes", "rice")
        if role == "produce":
            if chosen_role_ids:
                chosen_clusters = {
                    _produce_cluster(available.get(food_id, {}))
                    for food_id in chosen_role_ids
                    if food_id in available
                }
                if "fruit" in chosen_clusters:
                    return ("bell_peppers", "spinach", "frozen_vegetables", "broccoli", "berries", "bananas")
                return ("bananas", "berries", "oranges", "bell_peppers", "spinach", "frozen_vegetables")
            return ("bananas", "berries", "oranges")
    if goal_profile == "fat_loss" and role == "produce":
        if chosen_role_ids:
            return ("bell_peppers", "lettuce", "cucumber", "tomatoes", "cauliflower", "broccoli", "berries")
        return ("spinach", "lettuce", "cucumber", "bell_peppers")
    if goal_profile == "fat_loss":
        if role == "protein_anchor" and chosen_role_ids:
            return ("tofu", "greek_yogurt", "protein_yogurt", "cottage_cheese", "chicken_breast", "eggs", "tuna")
        if role == "carb_base":
            return ("wholemeal_bread", "quinoa", "oats", "potatoes", "sweet_potatoes")
    if goal_profile == "budget_friendly_healthy":
        if role == "protein_anchor":
            chosen_legume = any(
                str(available.get(food_id, {}).get("food_family") or "") == "legume"
                for food_id in chosen_role_ids
            )
            if chosen_legume:
                return ("eggs", "tofu")
            return ("lentils", "beans", "eggs", "tofu", "peanut_butter")
        if role == "carb_base":
            return ("rice", "pasta", "potatoes", "wholemeal_bread", "oats")
        if role == "produce":
            if chosen_role_ids:
                return ("potatoes", "bananas", "carrots", "onions", "frozen_vegetables", "apples", "lettuce", "cabbage")
            return ("cabbage", "frozen_vegetables", "carrots", "onions")
    if goal_profile == "maintenance":
        if role == "protein_anchor" and chosen_role_ids:
            chosen_has_animal = any(
                str(available.get(food_id, {}).get("food_family") or "") == "protein"
                for food_id in chosen_role_ids
            )
            if chosen_has_animal:
                return ("eggs", "tofu", "greek_yogurt", "rotisserie_chicken", "chicken_breast", "tuna")
            return ("chicken_breast", "rotisserie_chicken", "eggs", "tofu", "greek_yogurt", "tuna")
        if role == "carb_base":
            return ("wholemeal_bread", "potatoes", "quinoa", "rice", "oats")
        if role == "produce":
            if chosen_role_ids:
                return ("carrots", "lettuce", "apples", "bell_peppers", "spinach", "bananas")
            return ("carrots", "apples", "lettuce", "bell_peppers")
    if goal_profile == "high_protein_vegetarian":
        if role == "protein_anchor":
            chosen_has_soy = any(
                str(available.get(food_id, {}).get("generic_food_id") or "") in {"tofu", "edamame"}
                for food_id in chosen_role_ids
            )
            chosen_has_dairy_or_egg = any(
                str(available.get(food_id, {}).get("food_family") or "") == "dairy"
                or str(available.get(food_id, {}).get("generic_food_id") or "") == "eggs"
                for food_id in chosen_role_ids
            )
            if chosen_has_soy and not chosen_has_dairy_or_egg:
                return ("greek_yogurt", "protein_yogurt", "cottage_cheese", "eggs", "tofu", "edamame", "milk")
            if chosen_has_dairy_or_egg and not chosen_has_soy:
                return ("tofu", "edamame", "eggs", "greek_yogurt", "protein_yogurt", "cottage_cheese", "milk")
            return ("tofu", "eggs", "greek_yogurt", "protein_yogurt", "cottage_cheese", "edamame", "milk")
        if role == "carb_base":
            return ("wholemeal_bread", "quinoa", "oats", "bagel", "rice")
        if role == "produce":
            if chosen_role_ids:
                return ("spinach", "bell_peppers", "oranges", "berries", "bananas", "broccoli")
            return ("spinach", "berries", "oranges", "bell_peppers")
    return tuple(template_ids)


def _goal_template_slack(goal_profile: str, role: str) -> float:
    if goal_profile not in GOAL_PROFILE_OPTIONS or goal_profile == "generic_balanced":
        return 0.0
    return {
        "protein_anchor": 2.4,
        "carb_base": 2.8,
        "produce": 3.2,
        "calorie_booster": 1.6,
    }.get(role, 0.0)


def _goal_role_calorie_cap(
    food: dict[str, object],
    *,
    role: str,
    calorie_target_kcal: float,
    basket_policy: dict[str, object] | None,
    role_count: int,
) -> float | None:
    if calorie_target_kcal <= 0:
        return None

    configured_shares = basket_policy.get("target_role_calorie_shares") if isinstance(basket_policy, dict) else None
    if not isinstance(configured_shares, dict):
        return None

    role_share = max(0.0, float(configured_shares.get(role, 0.0)))
    if role_share <= 0.0:
        return None

    calorie_density = max(float(food.get("energy_fibre_kcal") or 0.0), 1.0)
    per_item_target_calories = (calorie_target_kcal * role_share) / max(role_count, 1)
    role_cap_multiplier = {
        "protein_anchor": 1.25,
        "carb_base": 1.35,
        "produce": 1.05,
        "calorie_booster": 1.05,
    }.get(role, 1.1)
    return 100.0 * per_item_target_calories * role_cap_multiplier / calorie_density


def _goal_target_pressure(
    goal_profile: str,
    *,
    protein_target_g: float = 0.0,
    calorie_target_kcal: float = 0.0,
    nutrition_targets: dict[str, float] | None = None,
) -> float:
    reference = GOAL_BASE_TARGETS.get(goal_profile, GOAL_BASE_TARGETS["generic_balanced"])
    ratios = [
        protein_target_g / max(float(reference["protein"]), 1.0) if protein_target_g > 0 else 0.0,
        calorie_target_kcal / max(float(reference["energy_fibre_kcal"]), 1.0) if calorie_target_kcal > 0 else 0.0,
    ]
    normalized_targets = nutrition_targets or {}
    for nutrient_id in ("carbohydrate", "fat", "fiber"):
        target_value = float(normalized_targets.get(nutrient_id) or 0.0)
        reference_value = float(reference.get(nutrient_id) or 0.0)
        if target_value > 0 and reference_value > 0:
            ratios.append(target_value / reference_value)
    return max(1.0, min(max(ratios, default=1.0), 5.0))


def _goal_quantity_cap(
    food: dict[str, object],
    role: str,
    goal_profile: str,
    *,
    protein_target_g: float = 0.0,
    calorie_target_kcal: float = 0.0,
    nutrition_targets: dict[str, float] | None = None,
    basket_policy: dict[str, object] | None = None,
    role_count: int = 1,
) -> float | None:
    food_id = str(food.get("generic_food_id") or "")
    family = str(food.get("food_family") or "")
    purchase_unit_size_g = float(food.get("purchase_unit_size_g") or 0.0)

    cap_g: float | None = None
    if goal_profile == "budget_friendly_healthy":
        if role == "protein_anchor":
            if food_id in {"lentils", "beans", "black_beans", "chickpeas"}:
                cap_g = 160.0
            if food_id == "eggs":
                cap_g = 240.0
            if food_id == "tofu":
                cap_g = 320.0
            if food_id == "peanut_butter":
                cap_g = 60.0
        elif role == "carb_base":
            if food_id == "rice":
                cap_g = 260.0
            if food_id == "pasta":
                cap_g = 360.0
            if food_id == "oats":
                cap_g = 240.0
            if food_id in {"potatoes", "sweet_potatoes"}:
                cap_g = 480.0
            if food_id == "wholemeal_bread":
                cap_g = max(320.0, min(purchase_unit_size_g, 420.0) if purchase_unit_size_g > 0 else 320.0)
        elif role == "produce":
            if food_id in {"cabbage", "frozen_vegetables"}:
                cap_g = 380.0
            if food_id in {"carrots", "bananas", "apples", "lettuce", "onions"}:
                cap_g = 320.0
            if food_id in {"potatoes", "sweet_potatoes"}:
                cap_g = 650.0
        elif role == "calorie_booster":
            cap_g = 15.0 if family == "fat" else 30.0

    if goal_profile == "fat_loss":
        if role == "protein_anchor":
            if food_id in {"tuna", "chicken_breast", "tofu", "greek_yogurt", "protein_yogurt", "cottage_cheese"}:
                cap_g = 280.0
            if food_id == "eggs":
                cap_g = 240.0
        elif role == "carb_base":
            if food_id in {"wholemeal_bread", "oats", "quinoa"}:
                cap_g = 250.0
            if food_id in {"potatoes", "sweet_potatoes"}:
                cap_g = 420.0
        elif role == "produce":
            if food_id in {"spinach", "lettuce", "cucumber", "tomatoes"}:
                cap_g = 350.0
            if food_id in {"bell_peppers", "broccoli", "cauliflower"}:
                cap_g = 420.0
            if food_id == "berries":
                cap_g = 280.0
        elif role == "calorie_booster":
            cap_g = 0.0

    if goal_profile == "muscle_gain":
        if role == "protein_anchor":
            if food_id == "eggs":
                cap_g = 600.0
            if food_id in {"greek_yogurt", "protein_yogurt", "cottage_cheese", "milk"}:
                cap_g = 420.0
            if food_id in {"turkey", "chicken_breast"}:
                cap_g = 240.0
        elif role == "carb_base":
            if food_id == "oats":
                cap_g = 350.0
            if food_id in {"rice", "pasta"}:
                cap_g = 360.0
            if food_id in {"potatoes", "sweet_potatoes"}:
                cap_g = 760.0
            if food_id in {"bagel", "wholemeal_bread"}:
                cap_g = 360.0
        elif role == "calorie_booster":
            cap_g = 45.0 if family == "fat" else 60.0

    if cap_g is None:
        return None

    target_pressure = _goal_target_pressure(
        goal_profile,
        protein_target_g=protein_target_g,
        calorie_target_kcal=calorie_target_kcal,
        nutrition_targets=nutrition_targets,
    )
    if target_pressure > 1.0:
        cap_growth = {
            "protein_anchor": 1.0,
            "carb_base": 1.05,
            "produce": 0.55,
            "calorie_booster": 0.35,
        }.get(role, 0.75)
        scaled_base_cap_g = cap_g * (1.0 + ((target_pressure - 1.0) * cap_growth))
        cap_g = max(cap_g, scaled_base_cap_g)

    role_calorie_cap_g = _goal_role_calorie_cap(
        food,
        role=role,
        calorie_target_kcal=calorie_target_kcal,
        basket_policy=basket_policy,
        role_count=role_count,
    )
    if role_calorie_cap_g is not None:
        cap_g = max(cap_g, role_calorie_cap_g)

    return round(cap_g, 6)


def _apply_goal_quantity_caps(
    chosen: Sequence[tuple[str, str]],
    available: dict[str, dict[str, object]],
    quantities: dict[str, float],
    goal_profile: str,
    *,
    protein_target_g: float = 0.0,
    calorie_target_kcal: float = 0.0,
    nutrition_targets: dict[str, float] | None = None,
    basket_policy: dict[str, object] | None = None,
) -> None:
    if goal_profile == "generic_balanced":
        return
    role_counts: dict[str, int] = {}
    for _food_id, role in chosen:
        role_counts[role] = role_counts.get(role, 0) + 1
    for food_id, role in chosen:
        if food_id not in quantities:
            continue
        cap_g = _goal_quantity_cap(
            available[food_id],
            role,
            goal_profile,
            protein_target_g=protein_target_g,
            calorie_target_kcal=calorie_target_kcal,
            nutrition_targets=nutrition_targets,
            basket_policy=basket_policy,
            role_count=role_counts.get(role, 1),
        )
        if cap_g is None:
            continue
        if cap_g <= 0:
            quantities[food_id] = 0.0
            continue
        if quantities[food_id] > cap_g:
            quantities[food_id] = _round_quantity_g(available[food_id], cap_g)


def _query_dicts(
    con: duckdb.DuckDBPyConnection,
    query: str,
    params: dict[str, bool],
) -> list[dict[str, object]]:
    con.execute(query, parameters=params)
    cols = [d[0] for d in con.description or []]
    return [{c: r for c, r in zip(cols, row, strict=True)} for row in con.fetchall()]


def _load_candidates(
    con: duckdb.DuckDBPyConnection,
    vegetarian: bool,
    dairy_free: bool,
    vegan: bool,
    price_area_code: str = "0",
    usda_area_code: str = "US",
) -> dict[str, dict[str, object]]:
    rows = _query_dicts(
        con,
        """
        SELECT
          g.*,
          COALESCE(ua.estimated_unit_price, pa.estimated_unit_price, p.estimated_unit_price) AS bls_estimated_unit_price,
          COALESCE(ua.price_unit_display, pa.price_unit_display, p.price_unit_display) AS price_unit_display,
          COALESCE(ua.price_basis_kind, pa.price_basis_kind, p.price_basis_kind) AS price_basis_kind,
          COALESCE(ua.price_basis_value, pa.price_basis_value, p.price_basis_value) AS price_basis_value,
          CASE
            WHEN ua.estimated_unit_price IS NOT NULL THEN ur.regional_price_low
            ELSE pr.regional_price_low
          END AS regional_price_low,
          CASE
            WHEN ua.estimated_unit_price IS NOT NULL THEN ur.regional_price_high
            ELSE pr.regional_price_high
          END AS regional_price_high,
          CASE
            WHEN ua.estimated_unit_price IS NOT NULL THEN ur.regional_price_area_count
            ELSE pr.regional_price_area_count
          END AS regional_price_area_count,
          COALESCE(ua.food_name, pa.item_name, p.item_name) AS bls_item_name,
          COALESCE(ua.observed_year, pa.latest_year, p.latest_year) AS bls_price_year,
          COALESCE(ua.observed_month_label, pa.latest_period, p.latest_period) AS bls_price_period,
          COALESCE(ua.area_code, pa.area_code, p.area_code, '0') AS bls_price_area_code,
          ua.usda_base_observed_at AS usda_base_observed_at,
          ua.cpi_base_observed_at AS cpi_base_observed_at,
          ua.cpi_current_observed_at AS cpi_current_observed_at,
          ua.cpi_base_value AS cpi_base_value,
          ua.cpi_current_value AS cpi_current_value,
          ua.inflation_multiplier AS usda_inflation_multiplier,
          CASE
            WHEN ua.estimated_unit_price IS NOT NULL THEN 'usda_area'
            WHEN pa.estimated_unit_price IS NOT NULL THEN 'bls_area'
            WHEN p.estimated_unit_price IS NOT NULL THEN 'bls_national'
            ELSE NULL
          END AS price_reference_source
        FROM generic_foods AS g
        LEFT JOIN generic_food_usda_prices_by_area AS ua
          ON g.generic_food_id = ua.generic_food_id AND ua.area_code = $usda_area_code
        LEFT JOIN generic_food_prices_by_area AS pa
          ON g.generic_food_id = pa.generic_food_id AND pa.area_code = $price_area_code
        LEFT JOIN generic_food_prices AS p
          ON g.generic_food_id = p.generic_food_id
        LEFT JOIN (
          SELECT
            generic_food_id,
            MIN(estimated_unit_price) AS regional_price_low,
            MAX(estimated_unit_price) AS regional_price_high,
            COUNT(*) AS regional_price_area_count
          FROM generic_food_usda_prices_by_area
          GROUP BY generic_food_id
        ) AS ur
          ON g.generic_food_id = ur.generic_food_id
        LEFT JOIN (
          SELECT
            generic_food_id,
            MIN(estimated_unit_price) AS regional_price_low,
            MAX(estimated_unit_price) AS regional_price_high,
            COUNT(*) AS regional_price_area_count
          FROM generic_food_prices_by_area
          GROUP BY generic_food_id
        ) AS pr
          ON g.generic_food_id = pr.generic_food_id
        WHERE (NOT $vegetarian OR vegetarian)
          AND (NOT $dairy_free OR dairy_free)
          AND (NOT $vegan OR vegan)
        ORDER BY g.commonality_rank, g.display_name
        """,
        {
            "vegetarian": vegetarian,
            "dairy_free": dairy_free,
            "vegan": vegan,
            "price_area_code": price_area_code,
            "usda_area_code": usda_area_code,
        },
    )
    return {str(row["generic_food_id"]): row for row in rows}


def _pick_first(preferred_ids: Iterable[str], available: dict[str, dict[str, object]], excluded: set[str]) -> str | None:
    for food_id in preferred_ids:
        if food_id in available and food_id not in excluded:
            return food_id
    return None


def _effective_preferences(preferences: dict[str, object]) -> dict[str, object]:
    vegan = bool(preferences.get("vegan", False))
    vegetarian = vegan or bool(preferences.get("vegetarian", False))
    dairy_free = vegan or bool(preferences.get("dairy_free", False))
    meal_style = str(preferences.get("meal_style", "any") or "any").strip().lower()
    if meal_style not in MEAL_STYLE_OPTIONS:
        meal_style = "any"
    return {
        "vegan": vegan,
        "vegetarian": vegetarian,
        "dairy_free": dairy_free,
        "low_prep": False,
        "budget_friendly": bool(preferences.get("budget_friendly", False)),
        "meal_style": meal_style,
    }


def _metadata_bool(food: dict[str, object], field_name: str) -> bool:
    value = food.get(field_name)
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() == "true"


def _meal_tags(food: dict[str, object]) -> set[str]:
    raw = str(food.get("meal_type") or "")
    return {part for part in raw.split("|") if part}


def _base_commonality_score(food: dict[str, object]) -> float:
    return max(0.0, 1.5 - 0.05 * (int(food["commonality_rank"]) - 1))


def _price_basis_total_g(food: dict[str, object]) -> float | None:
    unit_price = food.get("bls_estimated_unit_price")
    if unit_price is None:
        return None

    price_basis_kind = str(food.get("price_basis_kind") or "")
    price_basis_value = float(food.get("price_basis_value") or 0.0)
    if price_basis_value <= 0:
        return None

    if price_basis_kind == "weight_g":
        return price_basis_value
    if price_basis_kind == "volume_liter":
        purchase_unit_size_g = float(food.get("purchase_unit_size_g") or 0.0)
        return purchase_unit_size_g if purchase_unit_size_g > 0 else (price_basis_value * 1000.0)
    if price_basis_kind == "count":
        purchase_unit_size_g = float(food.get("purchase_unit_size_g") or 0.0)
        if purchase_unit_size_g > 0:
            return purchase_unit_size_g
        default_serving_g = max(float(food.get("default_serving_g") or 50.0), 1.0)
        return default_serving_g * price_basis_value
    return None


def _scaled_price_efficiency(raw_value: float, divisor: float) -> float:
    if raw_value <= 0 or divisor <= 0:
        return 0.0
    return math.log1p(raw_value / divisor)


def _price_efficiency_signals(food: dict[str, object]) -> dict[str, float]:
    cached = food.get("_price_efficiency_signals")
    if isinstance(cached, dict):
        return cached

    signals = {
        "protein_per_dollar": 0.0,
        "calories_per_dollar": 0.0,
        "carbs_per_dollar": 0.0,
        "fiber_per_dollar": 0.0,
        "calcium_per_dollar": 0.0,
        "vitamin_c_per_dollar": 0.0,
        "protein_score": 0.0,
        "calories_score": 0.0,
        "carbs_score": 0.0,
        "fiber_score": 0.0,
        "calcium_score": 0.0,
        "vitamin_c_score": 0.0,
    }

    unit_price = food.get("bls_estimated_unit_price")
    basis_total_g = _price_basis_total_g(food)
    if unit_price is None or basis_total_g is None or float(unit_price) <= 0:
        food["_price_efficiency_signals"] = signals
        return signals

    factor = basis_total_g / 100.0
    estimated_unit_price = float(unit_price)
    raw_values = {
        "protein": float(food.get("protein") or 0.0) * factor / estimated_unit_price,
        "energy_fibre_kcal": float(food.get("energy_fibre_kcal") or 0.0) * factor / estimated_unit_price,
        "carbohydrate": float(food.get("carbohydrate") or 0.0) * factor / estimated_unit_price,
        "fiber": float(food.get("fiber") or 0.0) * factor / estimated_unit_price,
        "calcium": float(food.get("calcium") or 0.0) * factor / estimated_unit_price,
        "vitamin_c": float(food.get("vitamin_c") or 0.0) * factor / estimated_unit_price,
    }
    signals.update(
        {
            "protein_per_dollar": raw_values["protein"],
            "calories_per_dollar": raw_values["energy_fibre_kcal"],
            "carbs_per_dollar": raw_values["carbohydrate"],
            "fiber_per_dollar": raw_values["fiber"],
            "calcium_per_dollar": raw_values["calcium"],
            "vitamin_c_per_dollar": raw_values["vitamin_c"],
            "protein_score": _scaled_price_efficiency(raw_values["protein"], PRICE_EFFICIENCY_DIVISORS["protein"]),
            "calories_score": _scaled_price_efficiency(raw_values["energy_fibre_kcal"], PRICE_EFFICIENCY_DIVISORS["energy_fibre_kcal"]),
            "carbs_score": _scaled_price_efficiency(raw_values["carbohydrate"], PRICE_EFFICIENCY_DIVISORS["carbohydrate"]),
            "fiber_score": _scaled_price_efficiency(raw_values["fiber"], PRICE_EFFICIENCY_DIVISORS["fiber"]),
            "calcium_score": _scaled_price_efficiency(raw_values["calcium"], PRICE_EFFICIENCY_DIVISORS["calcium"]),
            "vitamin_c_score": _scaled_price_efficiency(raw_values["vitamin_c"], PRICE_EFFICIENCY_DIVISORS["vitamin_c"]),
        }
    )
    food["_price_efficiency_signals"] = signals
    return signals


def _food_shelf_stability(food: dict[str, object]) -> str:
    return str(food.get("shelf_stability") or "").strip().lower()


def _is_shelf_stable(food: dict[str, object]) -> bool:
    return _metadata_bool(food, "shelf_stable") or _food_shelf_stability(food) == "stable"


def _is_perishable(food: dict[str, object]) -> bool:
    food_family = str(food["food_family"])
    shelf_stability = _food_shelf_stability(food)
    if _metadata_bool(food, "cold_only") or shelf_stability == "chilled":
        return True
    if food_family == "dairy":
        return True
    if food_family == "produce" and not _is_shelf_stable(food):
        return True
    return False


def _is_bulk_friendly(food: dict[str, object]) -> bool:
    food_family = str(food["food_family"])
    return (
        _is_shelf_stable(food)
        or _metadata_bool(food, "microwave_friendly")
        or food_family in {"grain", "legume", "fat"}
        or str(food.get("generic_food_id")) == "frozen_vegetables"
    )


def _meal_style_score(food: dict[str, object], role: str, preferences: dict[str, object]) -> float:
    meal_style = str(preferences.get("meal_style") or "any")
    if meal_style == "any":
        return 0.0

    tags = _meal_tags(food)
    preferred_tags = MEAL_STYLE_TAGS.get(meal_style, set())
    prep_level = str(food.get("prep_level") or "medium")
    prep_score = PREP_LEVEL_SCORES.get(prep_level, 0.0)
    food_family = str(food["food_family"])
    score = 0.0

    if tags & preferred_tags:
        score += 3.0
    elif meal_style == "lunch_dinner" and role == "produce" and tags & {"side"}:
        score += 1.0
    else:
        score -= 1.1

    if meal_style == "breakfast":
        if _metadata_bool(food, "breakfast_friendly"):
            score += 1.8
        if food_family in {"grain", "dairy"}:
            score += 1.0
        if str(food.get("generic_food_id")) == "eggs":
            score += 1.4
        if role == "protein_anchor" and food_family == "dairy":
            score += 2.8
        if role == "protein_anchor" and float(food.get("fat") or 0) > float(food.get("protein") or 0):
            score -= 2.8
        if role == "protein_anchor" and food_family == "protein" and not _metadata_bool(food, "breakfast_friendly"):
            score -= 2.6
        if role == "carb_base" and food_family == "grain" and _metadata_bool(food, "breakfast_friendly"):
            score += 0.8
        if role == "produce" and tags & {"breakfast", "snack"}:
            score += 1.0
    elif meal_style == "snack":
        if tags & {"snack", "side"}:
            score += 1.6
        if prep_score >= 2.0:
            score += 1.1
        if _metadata_bool(food, "cold_only"):
            score += 0.8
        if _metadata_bool(food, "shelf_stable"):
            score += 0.8
        if food_family in {"dairy", "fat", "produce"}:
            score += 0.9
        if role == "protein_anchor" and food_family == "dairy":
            score += 3.0
        if role == "protein_anchor" and float(food.get("fat") or 0) > float(food.get("protein") or 0):
            score -= 2.5
        if role == "protein_anchor" and food_family == "protein" and not (tags & {"snack", "side"}):
            score -= 2.4
        if role == "protein_anchor" and not (tags & {"snack", "side"}) and not _metadata_bool(food, "cold_only"):
            score -= 2.5
        if role == "carb_base" and food_family == "produce":
            score += 0.8
        if role == "produce" and (prep_score >= 2.0 or tags & {"snack"}):
            score += 0.8
    elif meal_style == "lunch_dinner":
        if tags & {"lunch", "dinner"}:
            score += 1.3
        if _metadata_bool(food, "microwave_friendly"):
            score += 1.0
        if food_family in {"protein", "grain", "legume"}:
            score += 1.0
        if role == "calorie_booster" and _metadata_bool(food, "cold_only"):
            score -= 0.8
        if role == "protein_anchor" and _metadata_bool(food, "breakfast_friendly") and not (tags & {"lunch", "dinner"}):
            score -= 0.8

    return score


def _produce_cluster(food: dict[str, object]) -> str:
    tags = _meal_tags(food)
    prep_level = str(food.get("prep_level") or "medium")
    carbohydrate = float(food.get("carbohydrate") or 0.0)
    fiber = float(food.get("fiber") or 0.0)
    calcium = float(food.get("calcium_score") or 0.0)
    iron = float(food.get("iron_score") or 0.0)
    vitamin_c = float(food.get("vitamin_c_score") or 0.0)

    if "breakfast" in tags:
        return "fruit"
    if _metadata_bool(food, "microwave_friendly") and "dinner" in tags:
        return "freezer_veg"
    if carbohydrate >= 12:
        return "starchy_produce"
    if calcium >= 1.5 or iron >= 1.2 or (vitamin_c >= 1.8 and fiber >= 2.0):
        return "leafy_green"
    if prep_level in {"none", "low"}:
        return "portable_produce"
    return "vegetable"


def _carb_cluster(food: dict[str, object]) -> str:
    tags = _meal_tags(food)
    food_family = str(food["food_family"])
    prep_level = str(food.get("prep_level") or "medium")
    breakfast_friendly = _metadata_bool(food, "breakfast_friendly")

    if breakfast_friendly or "breakfast" in tags:
        return "breakfast_carb"
    if food_family == "produce":
        return "portable_carb" if prep_level in {"none", "low"} else "starchy_produce"
    if food_family == "legume":
        return "legume_carb"
    if prep_level == "none":
        return "bread_wrap"
    return "meal_base"


def _low_prep_preference_signal(food: dict[str, object], role: str) -> float:
    food_id = str(food.get("generic_food_id") or "")
    prep_level = str(food.get("prep_level") or "medium")
    prep_score = PREP_LEVEL_SCORES.get(prep_level, 0.0)
    microwave_friendly = _metadata_bool(food, "microwave_friendly")
    bonus = prep_score * {
        "protein_anchor": 1.0,
        "carb_base": 0.95,
        "produce": 0.9,
        "calorie_booster": 0.6,
    }.get(role, 0.8)

    if prep_level == "none":
        bonus += {
            "protein_anchor": 0.75,
            "carb_base": 0.6,
            "produce": 0.3,
            "calorie_booster": 0.2,
        }.get(role, 0.25)
    elif prep_level == "low":
        bonus += {
            "protein_anchor": 0.35,
            "carb_base": 0.25,
            "produce": 0.2,
            "calorie_booster": 0.08,
        }.get(role, 0.15)
    elif prep_level == "medium":
        bonus -= {
            "protein_anchor": 0.95,
            "carb_base": 0.55,
            "produce": 0.4,
            "calorie_booster": 0.1,
        }.get(role, 0.25)

    if microwave_friendly:
        bonus += {
            "protein_anchor": 0.55,
            "carb_base": 0.55,
            "produce": 0.45,
            "calorie_booster": 0.3,
        }.get(role, 0.2)

    if role == "protein_anchor":
        if food_id in {"rotisserie_chicken", "eggs", "tofu", "tuna", "greek_yogurt", "protein_yogurt", "cottage_cheese", "veggie_burger", "hummus"}:
            bonus += 0.35
        if food_id in {"chicken_breast", "ground_beef", "turkey", "salmon", "shrimp"} and prep_level == "medium" and not microwave_friendly:
            bonus -= 0.65
    elif role == "carb_base":
        if food_id in {"wholemeal_bread", "tortilla", "corn_tortilla", "pita", "bagel", "corn_flakes", "oats", "couscous"}:
            bonus += 0.35
    elif role == "produce":
        cluster = _produce_cluster(food)
        if food_id == "frozen_vegetables":
            bonus += 0.45
        elif cluster in {"portable_produce", "freezer_veg", "leafy_green"}:
            bonus += 0.2

    return round(bonus, 6)


def _low_prep_ready(food: dict[str, object], role: str) -> bool:
    prep_level = str(food.get("prep_level") or "medium")
    if prep_level in {"none", "low"}:
        return True
    if role in {"protein_anchor", "carb_base", "produce"} and _metadata_bool(food, "microwave_friendly"):
        return True
    return False


def _cook_heavy_food(food: dict[str, object], role: str) -> bool:
    if role == "calorie_booster":
        return False
    prep_level = str(food.get("prep_level") or "medium")
    return prep_level == "medium" and not _metadata_bool(food, "microwave_friendly")


def _meal_suggestion_food_id(food: dict[str, object]) -> str:
    return str(food.get("generic_food_id") or "")


def _meal_suggestion_role_cluster(food: dict[str, object], role: str) -> str:
    if role == "produce":
        return _produce_cluster(food)
    if role == "carb_base":
        return _carb_cluster(food)
    return str(food.get("food_family") or "")


def _role_style_score(food: dict[str, object], role: str, preferences: dict[str, object]) -> float:
    meal_style = str(preferences.get("meal_style") or "any")
    if meal_style == "any":
        return 0.0

    prep_level = str(food.get("prep_level") or "medium")
    prep_score = PREP_LEVEL_SCORES.get(prep_level, 0.0)
    score = 0.0

    if role == "produce":
        cluster = _produce_cluster(food)
        if meal_style == "breakfast":
            if cluster == "fruit":
                score += 3.0
            elif cluster == "portable_produce":
                score += 1.2
            else:
                score -= 2.1
            if prep_level in {"none", "low"}:
                score += 0.9
        elif meal_style == "snack":
            if cluster in {"fruit", "portable_produce"}:
                score += 2.2
            elif cluster == "vegetable":
                score += 0.5
            elif cluster == "leafy_green":
                score -= 0.8
            elif cluster == "freezer_veg":
                score -= 1.6
            else:
                score -= 1.0
            score += prep_score * 0.45
        elif meal_style == "lunch_dinner":
            if cluster in {"vegetable", "leafy_green", "starchy_produce"}:
                score += 1.8
            if cluster == "fruit":
                score -= 1.8
            if prep_level == "medium":
                score += 0.5
    elif role == "carb_base":
        cluster = _carb_cluster(food)
        if meal_style == "breakfast":
            if cluster == "breakfast_carb":
                score += 3.2
            elif cluster == "bread_wrap":
                score += 1.7
            else:
                score -= 2.0
            if prep_level in {"none", "low"}:
                score += 0.8
        elif meal_style == "snack":
            if cluster in {"portable_carb", "bread_wrap", "breakfast_carb"}:
                score += 2.2
            elif cluster == "starchy_produce":
                score += 0.4
            else:
                score -= 1.0
            score += prep_score * 0.35
        elif meal_style == "lunch_dinner":
            if cluster in {"meal_base", "legume_carb", "starchy_produce"}:
                score += 2.0
            if cluster == "breakfast_carb":
                score -= 1.6
            if prep_level in {"low", "medium"}:
                score += 0.5
    return score


def _goal_role_score(food: dict[str, object], role: str, goal_profile: str) -> float:
    if goal_profile not in GOAL_PROFILE_OPTIONS or goal_profile == "generic_balanced":
        return 0.0

    food_id = str(food.get("generic_food_id") or "")
    family = str(food["food_family"])
    cluster = _meal_suggestion_role_cluster(food, role)
    calories = float(food.get("energy_fibre_kcal") or 0.0)
    fat = float(food.get("fat") or 0.0)
    score = 0.0

    if goal_profile == "muscle_gain":
        if role == "protein_anchor":
            if food_id in MUSCLE_GAIN_PROTEIN_IDS:
                score += 2.8
            if food_id in {"eggs", "greek_yogurt", "protein_yogurt", "cottage_cheese", "milk"}:
                score += 2.5
            if food_id in {"turkey", "chicken_breast"}:
                score += 1.2
            if food_id == "tuna":
                score -= 1.6
            if food_id == "rotisserie_chicken":
                score -= 1.3
            if food_id in {"lentils", "beans", "black_beans", "chickpeas"}:
                score -= 1.1
        elif role == "carb_base":
            if food_id in MUSCLE_GAIN_CARB_IDS:
                score += 3.0
            if food_id in {"pasta", "bagel"}:
                score += 2.3
            if food_id in {"oats", "potatoes", "wholemeal_bread"}:
                score += 1.1
            if cluster == "meal_base":
                score += 1.0
            if food_id == "rice":
                score -= 0.6
            if food_id == "corn_flakes":
                score -= 1.1
        elif role == "produce":
            if food_id in MUSCLE_GAIN_PRODUCE_IDS:
                score += 2.8
            if cluster == "fruit":
                score += 1.6
            if food_id in {"berries", "bananas", "oranges"}:
                score += 1.1
            if food_id == "broccoli":
                score -= 1.6
        elif role == "calorie_booster":
            if food_id in MUSCLE_GAIN_BOOSTER_IDS:
                score += 1.6
            if calories < 180:
                score -= 0.7
    elif goal_profile == "fat_loss":
        if role == "protein_anchor":
            if food_id in FAT_LOSS_PROTEIN_IDS:
                score += 3.0
            if food_id in {"tofu", "greek_yogurt", "protein_yogurt", "cottage_cheese"}:
                score += 1.8
            if food_id in {"rotisserie_chicken", "ground_beef", "salmon"}:
                score -= 1.8
            if calories >= 200 or fat > 12:
                score -= 1.4
        elif role == "carb_base":
            if food_id in FAT_LOSS_CARB_IDS:
                score += 2.5
            if food_id in {"wholemeal_bread", "quinoa"}:
                score += 1.5
            if food_id == "oats":
                score += 0.4
            if cluster == "starchy_produce":
                score += 0.8
            if food_id in {"rice", "pasta"}:
                score -= 1.4
            if food_id == "corn_flakes":
                score -= 2.0
        elif role == "produce":
            if food_id in FAT_LOSS_PRODUCE_IDS:
                score += 2.8
            if cluster in {"vegetable", "leafy_green"}:
                score += 1.0
            if food_id in {"spinach", "lettuce", "cucumber", "bell_peppers", "tomatoes"}:
                score += 1.1
            if cluster == "fruit":
                score -= 0.6
            if cluster == "starchy_produce":
                score -= 1.0
        elif role == "calorie_booster":
            score -= 3.4
            if family == "fat":
                score -= 1.3
    elif goal_profile == "maintenance":
        if role == "protein_anchor":
            if food_id in MAINTENANCE_PROTEIN_IDS:
                score += 1.8
            if food_id in {"eggs", "tofu", "chicken_breast"}:
                score += 1.7
            if food_id == "rotisserie_chicken":
                score += 0.2
            if food_id == "tuna":
                score -= 1.2
            if food_id in {"lentils", "beans", "black_beans", "chickpeas"}:
                score -= 1.4
        elif role == "carb_base":
            if food_id in MAINTENANCE_CARB_IDS:
                score += 1.8
            if food_id in {"potatoes", "wholemeal_bread"}:
                score += 2.5
            if food_id == "quinoa":
                score += 1.2
            if food_id == "oats":
                score -= 1.1
            if food_id == "rice":
                score -= 1.8
            if food_id == "corn_flakes":
                score -= 0.8
        elif role == "produce":
            if food_id in MAINTENANCE_PRODUCE_IDS:
                score += 1.8
            if food_id in {"apples", "carrots", "lettuce", "bell_peppers", "spinach"}:
                score += 1.6
            if cluster in {"vegetable", "fruit"}:
                score += 0.4
            if food_id in {"broccoli", "kale", "brussels_sprouts"}:
                score -= 1.2
        elif role == "calorie_booster" and food_id in {"olive_oil", "peanut_butter", "nuts"}:
            score += 0.3
    elif goal_profile == "budget_friendly_healthy":
        if role == "protein_anchor":
            if food_id in BUDGET_HEALTHY_PROTEIN_IDS:
                score += 3.2
            if food_id in {"eggs", "tofu"}:
                score += 2.2
            if food_id == "peanut_butter":
                score += 0.2
            if food_id in {"beans", "black_beans", "chickpeas"}:
                score -= 1.0
            if food_id in {"rotisserie_chicken", "salmon", "shrimp", "protein_yogurt", "cottage_cheese"}:
                score -= 2.0
        elif role == "carb_base":
            if food_id in BUDGET_HEALTHY_CARB_IDS:
                score += 2.8
            if food_id in {"rice", "pasta", "potatoes"}:
                score += 1.2
            if food_id == "oats":
                score -= 1.8
            if cluster in {"meal_base", "starchy_produce"}:
                score += 0.6
            if food_id == "quinoa":
                score -= 1.2
            if food_id == "corn_flakes":
                score -= 1.3
        elif role == "produce":
            if food_id in BUDGET_HEALTHY_PRODUCE_IDS:
                score += 2.4
            if food_id in {"carrots", "cabbage", "frozen_vegetables", "bananas", "potatoes", "apples", "onions"}:
                score += 1.2
            if food_id in {"cabbage", "frozen_vegetables", "onions"}:
                score += 0.9
            if cluster == "portable_produce":
                score += 0.5
            if food_id in {"berries", "avocado", "bell_peppers", "broccoli"}:
                score -= 1.2
        elif role == "calorie_booster":
            if food_id in BUDGET_HEALTHY_BOOSTER_IDS:
                score += 1.2
            if food_id in {"nuts", "almond_butter", "cheese"}:
                score -= 0.9
    elif goal_profile == "high_protein_vegetarian":
        if role == "protein_anchor":
            if food_id in HIGH_PROTEIN_VEGETARIAN_PROTEIN_IDS:
                score += 3.4
            if food_id in {"eggs", "tofu", "greek_yogurt", "protein_yogurt", "cottage_cheese", "edamame"}:
                score += 1.8
            if food_id in {"lentils", "beans", "black_beans", "chickpeas"}:
                score -= 2.1
            if food_id == "peanut_butter":
                score -= 0.8
        elif role == "carb_base":
            if food_id in HIGH_PROTEIN_VEGETARIAN_CARB_IDS:
                score += 2.4
            if food_id in {"wholemeal_bread", "quinoa"}:
                score += 2.2
            if food_id in {"oats", "bagel"}:
                score -= 0.2 if food_id == "oats" else 0.4
            if food_id == "rice":
                score -= 0.9
            if food_id == "corn_flakes":
                score -= 1.4
        elif role == "produce":
            if food_id in HIGH_PROTEIN_VEGETARIAN_PRODUCE_IDS:
                score += 2.5
            if cluster in {"leafy_green", "fruit"}:
                score += 0.5
            if food_id in {"spinach", "berries", "oranges", "bell_peppers"}:
                score += 1.2
            if food_id in {"broccoli", "kale"}:
                score -= 1.0
        elif role == "calorie_booster" and food_id in {"peanut_butter", "olive_oil"}:
            score += 0.5

    return score


def _role_candidate(food: dict[str, object], role: str) -> bool:
    family = str(food["food_family"])
    protein = float(food["protein"])
    carbohydrate = float(food["carbohydrate"])
    fat = float(food["fat"])
    calories = float(food["energy_fibre_kcal"])

    if role == "protein_anchor":
        return family in {"protein", "legume", "dairy", "grain"} and (protein >= 8 or _metadata_bool(food, "high_protein"))
    if role == "carb_base":
        return family in {"grain", "legume", "produce"} and carbohydrate >= 12
    if role == "produce":
        return family == "produce"
    if role == "calorie_booster":
        return family in {"fat", "dairy", "protein", "grain", "produce"} and (fat >= 8 or calories >= 150 or family == "fat")
    return False


def _role_score(
    food: dict[str, object],
    role: str,
    preferences: dict[str, object],
    nutrition_targets: dict[str, float],
    goal_profile: str,
) -> float:
    if not _role_candidate(food, role):
        return float("-inf")

    family = str(food["food_family"])
    tags = _meal_tags(food)
    prep_level = str(food.get("prep_level") or "medium")
    prep_score = PREP_LEVEL_SCORES.get(prep_level, 0.0)
    budget_score = float(food.get("budget_score") or 0)
    protein = float(food["protein"])
    calories = float(food["energy_fibre_kcal"])
    carbohydrate = float(food["carbohydrate"])
    fat = float(food["fat"])
    protein_density_score = float(food.get("protein_density_score") or 0)
    fiber_score = float(food.get("fiber_score") or 0)
    calcium_score = float(food.get("calcium_score") or 0)
    iron_score = float(food.get("iron_score") or 0)
    vitamin_c_score = float(food.get("vitamin_c_score") or 0)
    price_signals = _price_efficiency_signals(food)

    score = _base_commonality_score(food)
    score += _meal_style_score(food, role, preferences)
    score += _role_style_score(food, role, preferences)
    score += _goal_role_score(food, role, goal_profile)

    if role == "protein_anchor":
        score += {"protein": 2.4, "legume": 1.9, "dairy": 1.5, "grain": 0.4}.get(family, -2.0)
        score += protein_density_score * 2.2
        score += protein / 22.0
        if _metadata_bool(food, "high_protein"):
            score += 1.0
        if tags & {"lunch", "dinner", "breakfast"}:
            score += 0.3
        if preferences["low_prep"]:
            score += _low_prep_preference_signal(food, role)
        if preferences["budget_friendly"]:
            score += budget_score * 0.9
        score += price_signals["protein_score"] * 0.45
        score += price_signals["calories_score"] * 0.12
        if preferences["budget_friendly"]:
            score += price_signals["protein_score"] * 1.05
            score += price_signals["calories_score"] * 0.3
            if price_signals["protein_per_dollar"] <= 0:
                score -= 0.2
        if nutrition_targets.get("fiber"):
            score += fiber_score * 0.6
        if nutrition_targets.get("calcium"):
            score += calcium_score * 0.5
            score += price_signals["calcium_score"] * 0.2
        if nutrition_targets.get("iron"):
            score += iron_score * 0.9
        if nutrition_targets.get("fat"):
            score += min(fat / 12.0, 1.5)
    elif role == "carb_base":
        score += {"grain": 2.6, "legume": 1.8, "produce": 1.2}.get(family, -2.0)
        score += carbohydrate / 18.0
        score += calories / 240.0
        if tags & {"breakfast", "lunch", "dinner"}:
            score += 0.4
        if _metadata_bool(food, "breakfast_friendly"):
            score += 0.3
        if preferences["low_prep"]:
            score += _low_prep_preference_signal(food, role)
        if preferences["budget_friendly"]:
            score += budget_score * 0.8
            score += fiber_score * 0.7
            if carbohydrate >= 70 and float(food.get("fiber") or 0.0) < 2.0:
                score -= 0.8
        score += price_signals["carbs_score"] * 0.35
        score += price_signals["calories_score"] * 0.25
        if preferences["budget_friendly"]:
            score += price_signals["carbs_score"] * 0.95
            score += price_signals["calories_score"] * 0.8
            score += price_signals["fiber_score"] * 0.4
            if price_signals["carbs_per_dollar"] <= 0 and price_signals["calories_per_dollar"] <= 0:
                score -= 0.25
        if nutrition_targets.get("carbohydrate"):
            score += carbohydrate / 15.0
        if nutrition_targets.get("fiber"):
            score += fiber_score * 0.8
        if nutrition_targets.get("iron"):
            score += iron_score * 0.3
        if nutrition_targets.get("calcium"):
            score += calcium_score * 0.2
    elif role == "produce":
        score += 3.0
        score += fiber_score * 0.5
        score += vitamin_c_score * 0.6
        score += iron_score * 0.2
        score += calcium_score * 0.1
        if tags & {"side", "snack"}:
            score += 0.5
        if preferences["low_prep"]:
            score += _low_prep_preference_signal(food, role)
        if preferences["budget_friendly"]:
            score += budget_score * 0.5
            if _produce_cluster(food) in {"portable_produce", "starchy_produce"}:
                score += 0.3
        score += price_signals["fiber_score"] * 0.2
        score += price_signals["vitamin_c_score"] * 0.25
        if preferences["budget_friendly"]:
            score += price_signals["fiber_score"] * 0.6
            score += price_signals["vitamin_c_score"] * 0.7
            score += price_signals["calories_score"] * 0.2
        if nutrition_targets.get("fiber"):
            score += fiber_score * 0.8
            score += price_signals["fiber_score"] * 0.3
        if nutrition_targets.get("vitamin_c"):
            score += vitamin_c_score * 1.0
            score += price_signals["vitamin_c_score"] * 0.45
        if nutrition_targets.get("iron"):
            score += iron_score * 0.8
        if nutrition_targets.get("calcium"):
            score += calcium_score * 0.5
            score += price_signals["calcium_score"] * 0.25
    else:
        score += {"fat": 3.0, "dairy": 1.4, "protein": 1.0, "grain": 0.8, "produce": 0.5}.get(family, -1.0)
        score += calories / 130.0
        score += fat / 8.0
        if tags & {"snack", "breakfast", "dinner"}:
            score += 0.3
        if preferences["low_prep"]:
            score += _low_prep_preference_signal(food, role)
        if preferences["budget_friendly"]:
            score += budget_score * 0.6
        score += price_signals["calories_score"] * 0.4
        if preferences["budget_friendly"]:
            score += price_signals["calories_score"] * 1.0
            if price_signals["calories_per_dollar"] <= 0:
                score -= 0.2
        if nutrition_targets.get("fat"):
            score += fat / 6.0
        if nutrition_targets.get("calcium"):
            score += calcium_score * 0.5
            score += price_signals["calcium_score"] * 0.2

    return score


def _build_role_scores(
    available: dict[str, dict[str, object]],
    role: str,
    preferences: dict[str, object],
    nutrition_targets: dict[str, float],
    goal_profile: str,
) -> dict[str, float]:
    scores: dict[str, float] = {}
    for food_id, food in available.items():
        score = _role_score(food, role, preferences, nutrition_targets, goal_profile)
        if score != float("-inf"):
            scores[food_id] = score
    return scores


def _build_role_order(
    available: dict[str, dict[str, object]],
    role: str,
    preferences: dict[str, object],
    nutrition_targets: dict[str, float],
    goal_profile: str,
) -> list[str]:
    role_scores = _build_role_scores(available, role, preferences, nutrition_targets, goal_profile)
    ranked: list[tuple[float, int, str, str]] = []
    for food_id, score in role_scores.items():
        food = available[food_id]
        ranked.append((-score, int(food["commonality_rank"]), str(food["display_name"]), food_id))
    ranked.sort()
    return [food_id for _, _, _, food_id in ranked]


def _similarity_penalty(food: dict[str, object], other_food: dict[str, object], role: str) -> float:
    penalty = 0.0
    if str(food["food_family"]) == str(other_food["food_family"]):
        penalty += {"protein_anchor": 0.45, "carb_base": 0.7, "produce": 1.0, "calorie_booster": 0.45}[role]
    if _meal_tags(food) & _meal_tags(other_food):
        penalty += 0.25
    if str(food.get("prep_level") or "") == str(other_food.get("prep_level") or ""):
        penalty += 0.15
    if _is_perishable(food) == _is_perishable(other_food):
        penalty += 0.15

    if role == "produce" and _produce_cluster(food) == _produce_cluster(other_food):
        penalty += 1.0
    if role == "carb_base" and _carb_cluster(food) == _carb_cluster(other_food):
        penalty += 0.8

    if role == "protein_anchor":
        nutrient_keys = ("protein", "fat")
    elif role == "carb_base":
        nutrient_keys = ("carbohydrate", "fiber")
    elif role == "produce":
        nutrient_keys = ("fiber", "vitamin_c", "iron")
    else:
        nutrient_keys = ("fat", "energy_fibre_kcal")

    closeness = 0.0
    for key in nutrient_keys:
        a = float(food.get(key) or 0.0)
        b = float(other_food.get(key) or 0.0)
        denominator = max(max(a, b), 1.0)
        closeness += 1.0 - min(abs(a - b) / denominator, 1.0)
    closeness /= max(len(nutrient_keys), 1)
    penalty += closeness * {"protein_anchor": 0.45, "carb_base": 0.85, "produce": 1.1, "calorie_booster": 0.55}[role]
    return penalty


def _role_diversity_penalty(
    food_id: str,
    role: str,
    available: dict[str, dict[str, object]],
    chosen: list[tuple[str, str]],
) -> float:
    penalty = 0.0
    food = available[food_id]
    chosen_ids = {chosen_id for chosen_id, _chosen_role in chosen}
    if food_id in chosen_ids:
        return 100.0

    role_peers = [chosen_id for chosen_id, chosen_role in chosen if chosen_role == role and chosen_id in available]
    if not role_peers:
        return 0.0

    for peer_id in role_peers:
        penalty += _similarity_penalty(food, available[peer_id], role)

    if role == "produce" and sum(1 for peer_id in role_peers if _is_perishable(available[peer_id])) >= 1 and _is_perishable(food):
        penalty += 0.45
    if role == "protein_anchor" and any(str(available[peer_id]["food_family"]) == str(food["food_family"]) for peer_id in role_peers):
        penalty += 0.15
    if role == "carb_base" and any(_carb_cluster(available[peer_id]) == _carb_cluster(food) for peer_id in role_peers):
        penalty += 0.35
    return penalty


def _diversity_window(role: str, preferences: dict[str, object]) -> float:
    base = {"protein_anchor": 1.3, "carb_base": 2.0, "produce": 2.6, "calorie_booster": 1.2}[role]
    if str(preferences.get("meal_style") or "any") != "any":
        base += 0.35
    if preferences.get("budget_friendly"):
        base += 0.25 if role in {"carb_base", "produce"} else 0.1
    return base


def _pick_diverse_candidate(
    role: str,
    available: dict[str, dict[str, object]],
    role_scores: dict[str, float],
    excluded: set[str],
    chosen: list[tuple[str, str]],
    preferences: dict[str, object],
    goal_profile: str = "generic_balanced",
) -> str | None:
    candidates = [
        food_id
        for food_id in sorted(
            role_scores,
            key=lambda candidate_id: (
                -role_scores[candidate_id],
                int(available[candidate_id]["commonality_rank"]),
                str(available[candidate_id]["display_name"]),
                candidate_id,
            ),
        )
        if food_id not in excluded and food_id in available
    ]
    if not candidates:
        return None

    best_score = role_scores[candidates[0]]
    candidate_window = _diversity_window(role, preferences)
    short_list = [food_id for food_id in candidates if best_score - role_scores[food_id] <= candidate_window]
    if not short_list:
        short_list = [candidates[0]]

    preferred_ids = _goal_template_ids_for_pick(goal_profile, role, chosen, available)
    preferred_rank = {food_id: idx for idx, food_id in enumerate(preferred_ids)}
    use_goal_template = False
    if preferred_rank:
        template_window = candidate_window + _goal_template_slack(goal_profile, role)
        template_candidates = [
            food_id
            for food_id in candidates
            if food_id in preferred_rank and best_score - role_scores[food_id] <= template_window
        ]
        if template_candidates:
            short_list = template_candidates
            use_goal_template = True

    ranked = []
    for food_id in short_list:
        diversity_penalty = _role_diversity_penalty(food_id, role, available, chosen)
        adjusted_score = role_scores[food_id] - diversity_penalty
        if use_goal_template:
            ranked.append(
                (
                    preferred_rank[food_id],
                    -adjusted_score,
                    -role_scores[food_id],
                    int(available[food_id]["commonality_rank"]),
                    str(available[food_id]["display_name"]),
                    food_id,
                )
            )
        else:
            ranked.append(
                (
                    -adjusted_score,
                    -role_scores[food_id],
                    int(available[food_id]["commonality_rank"]),
                    str(available[food_id]["display_name"]),
                    food_id,
                )
            )
    ranked.sort()
    return ranked[0][-1]


def _round_quantity_g(food: dict[str, object], quantity_g: float) -> float:
    default_serving_g = float(food["default_serving_g"])
    food_family = str(food["food_family"])
    food_id = str(food["generic_food_id"])
    if food_id in {"eggs", "bananas"}:
        servings = max(1, round(quantity_g / default_serving_g))
        return round(servings * default_serving_g, 1)
    if food_family == "fat":
        return round(max(5.0, quantity_g) / 5) * 5.0
    return round(max(10.0, quantity_g) / 10) * 10.0


def _pluralize_purchase_unit(unit: str, count: int) -> str:
    irregular = {
        "bag": "bags",
        "block": "blocks",
        "bottle": "bottles",
        "box": "boxes",
        "bunch": "bunches",
        "can pack": "can packs",
        "crown": "crowns",
        "gallon": "gallons",
        "jar": "jars",
        "loaf": "loaves",
        "pack": "packs",
        "tub": "tubs",
        "dozen eggs": "dozen eggs",
    }
    if count == 1:
        return unit
    return irregular.get(unit, unit if unit.endswith("s") else f"{unit}s")


def _quantity_display(food: dict[str, object], quantity_g: float, days: int = 1) -> str:
    food_id = str(food["generic_food_id"])
    purchase_unit = str(food["purchase_unit"])
    purchase_unit_size_g = float(food["purchase_unit_size_g"])
    display_name = str(food["display_name"])
    default_serving_g = max(float(food.get("default_serving_g") or 0.0), 1.0)

    if purchase_unit_size_g > 0:
        unit_ratio = quantity_g / purchase_unit_size_g
        if food_id == "eggs" and "dozen" in purchase_unit:
            grams_per_egg = max(purchase_unit_size_g / 12.0, 1.0)
            egg_count = max(1, round(quantity_g / grams_per_egg))
            if egg_count < 10:
                return f"~{egg_count} eggs (~{round(quantity_g)} g)"
            rounded_dozens = round(egg_count / 12)
            if rounded_dozens >= 1 and abs((rounded_dozens * 12) - egg_count) <= 2:
                return f"{rounded_dozens} {_pluralize_purchase_unit(purchase_unit, rounded_dozens)} (~{round(quantity_g)} g)"
            return f"~{egg_count} eggs (~{round(quantity_g)} g)"

        if unit_ratio < 0.75:
            serving_ratio = quantity_g / default_serving_g
            if 0.9 <= serving_ratio <= 4.5:
                rounded_servings = round(serving_ratio, 1)
                serving_label = "serving" if abs(rounded_servings - 1.0) < 1e-6 else "servings"
                if abs(rounded_servings - round(rounded_servings)) < 0.15:
                    rounded_servings = int(round(rounded_servings))
                return f"~{rounded_servings} {serving_label} {display_name} (~{round(quantity_g)} g)"
            return f"~{round(quantity_g)} g {display_name}"

        unit_count = max(1, round(unit_ratio))
        unit_label = _pluralize_purchase_unit(purchase_unit, unit_count)
        size_prefix = ""
        if days > 1 and unit_count == 1 and purchase_unit in {"bag", "box", "pack", "bottle"} and quantity_g >= purchase_unit_size_g * 0.75:
            size_prefix = "large "
        return f"{unit_count} {size_prefix}{unit_label} {display_name} (~{round(quantity_g)} g)"

    return f"~{round(quantity_g)} g {display_name}"


def _pantry_reduction_factor(food: dict[str, object], days: int, shopping_mode: str) -> float:
    factor_by_days = {1: 0.0, 3: 0.3, 5: 0.45, 7: 0.6}
    factor = factor_by_days.get(days, 0.35)
    if shopping_mode == "fresh" and _is_perishable(food):
        factor -= 0.15
    elif shopping_mode == "bulk" and _is_bulk_friendly(food):
        factor += 0.1
    return max(0.0, min(factor, 0.75))


def _apply_pantry_adjustments(
    chosen: Sequence[tuple[str, str]],
    available: dict[str, dict[str, object]],
    scaled_quantities: dict[str, float],
    pantry_items: set[str],
    *,
    days: int,
    shopping_mode: str,
) -> tuple[dict[str, float], list[str]]:
    if not pantry_items:
        return dict(scaled_quantities), []

    adjusted_quantities = dict(scaled_quantities)
    pantry_notes: list[str] = []
    role_members: dict[str, list[str]] = {}
    for food_id, role in chosen:
        if food_id in adjusted_quantities and adjusted_quantities[food_id] > 0:
            role_members.setdefault(role, []).append(food_id)

    for food_id, role in chosen:
        if food_id not in pantry_items or food_id not in adjusted_quantities:
            continue

        planned_quantity_g = float(adjusted_quantities.get(food_id, 0.0))
        if planned_quantity_g <= 0:
            continue

        food = available[food_id]
        factor = _pantry_reduction_factor(food, days, shopping_mode)
        reduced_quantity_g = _round_quantity_g(food, planned_quantity_g * factor) if factor > 0 else 0.0
        role_peers = [peer_id for peer_id in role_members.get(role, []) if peer_id != food_id and peer_id not in pantry_items]
        purchase_unit_size_g = float(food.get("purchase_unit_size_g") or 0.0)
        omission_threshold_g = max(
            0.0,
            purchase_unit_size_g * 0.35 if purchase_unit_size_g > 0 else float(food.get("default_serving_g") or 0.0) * 0.75,
        )

        if role_peers and reduced_quantity_g <= omission_threshold_g:
            adjusted_quantities[food_id] = 0.0
            pantry_notes.append(f"Removed {food['display_name']} from the shopping list because it was marked as already available.")
        elif reduced_quantity_g < planned_quantity_g:
            adjusted_quantities[food_id] = reduced_quantity_g
            pantry_notes.append(f"Reduced {food['display_name']} because it was marked as already available in your pantry.")

    if not any(quantity_g > 0 for quantity_g in adjusted_quantities.values()):
        pantry_candidates = [food_id for food_id, _role in chosen if food_id in pantry_items and food_id in scaled_quantities]
        if pantry_candidates:
            fallback_food_id = pantry_candidates[0]
            fallback_food = available[fallback_food_id]
            fallback_quantity_g = _round_quantity_g(
                fallback_food,
                float(scaled_quantities[fallback_food_id]) * max(0.25, _pantry_reduction_factor(fallback_food, days, shopping_mode)),
            )
            adjusted_quantities[fallback_food_id] = fallback_quantity_g
            pantry_notes.append(
                f"Kept a small top-up amount of {fallback_food['display_name']} in the list so the plan still shows one practical buy."
            )

    adjusted_quantities = {
        food_id: quantity_g
        for food_id, quantity_g in adjusted_quantities.items()
        if quantity_g > 0
    }
    return adjusted_quantities, pantry_notes


def _item_totals(food: dict[str, object], quantity_g: float) -> tuple[float, float]:
    factor = quantity_g / 100.0
    protein = float(food["protein"]) * factor
    calories = float(food["energy_fibre_kcal"]) * factor
    return protein, calories


def _estimate_item_cost_for_unit_price(food: dict[str, object], quantity_g: float, estimated_unit_price: float) -> float | None:
    price_basis_kind = str(food.get("price_basis_kind") or "")
    price_basis_value = float(food.get("price_basis_value") or 0.0)
    if price_basis_value <= 0:
        return None

    if price_basis_kind == "weight_g":
        estimated_item_cost = estimated_unit_price * (quantity_g / price_basis_value)
    elif price_basis_kind == "volume_liter":
        purchase_unit_size_g = float(food.get("purchase_unit_size_g") or 0.0)
        basis_total_g = purchase_unit_size_g if purchase_unit_size_g > 0 else (price_basis_value * 1000.0)
        estimated_item_cost = estimated_unit_price * (quantity_g / basis_total_g)
    elif price_basis_kind == "count":
        purchase_unit_size_g = float(food.get("purchase_unit_size_g") or 0.0)
        if purchase_unit_size_g > 0:
            basis_total_g = purchase_unit_size_g
        else:
            default_serving_g = max(float(food.get("default_serving_g") or 50.0), 1.0)
            basis_total_g = default_serving_g * price_basis_value
        estimated_item_cost = estimated_unit_price * (quantity_g / basis_total_g)
    else:
        estimated_item_cost = None

    return round(estimated_item_cost, 2) if estimated_item_cost is not None else None


def _price_reference(food: dict[str, object], quantity_g: float) -> tuple[float | None, float | None, str | None]:
    unit_price = food.get("bls_estimated_unit_price")
    if unit_price is None:
        return None, None, None

    estimated_unit_price = float(unit_price)
    price_unit_display = str(food.get("price_unit_display") or "") or None
    estimated_item_cost = _estimate_item_cost_for_unit_price(food, quantity_g, estimated_unit_price)
    if float(food.get("price_basis_value") or 0.0) <= 0:
        return round(estimated_unit_price, 2), None, price_unit_display
    return round(estimated_unit_price, 2), estimated_item_cost, price_unit_display


def _price_range(food: dict[str, object], quantity_g: float) -> tuple[float | None, float | None]:
    area_count = int(food.get("regional_price_area_count") or 0)
    if area_count < 2:
        return None, None

    low_unit_price = food.get("regional_price_low")
    high_unit_price = food.get("regional_price_high")
    if low_unit_price is None or high_unit_price is None:
        return None, None

    estimated_price_low = _estimate_item_cost_for_unit_price(food, quantity_g, float(low_unit_price))
    estimated_price_high = _estimate_item_cost_for_unit_price(food, quantity_g, float(high_unit_price))
    if estimated_price_low is None or estimated_price_high is None:
        return None, None
    return estimated_price_low, estimated_price_high


def _price_source_used(food: dict[str, object]) -> str | None:
    source = str(food.get("price_reference_source") or "")
    if source == "usda_area":
        return "usda_area"
    if source == "bls_area":
        return "bls_area"
    if source == "bls_national":
        return "bls_fallback"
    return None


def _usda_adjustment_context(available: dict[str, dict[str, object]]) -> dict[str, object] | None:
    for food in available.values():
        if str(food.get("price_reference_source") or "") != "usda_area":
            continue
        multiplier = food.get("usda_inflation_multiplier")
        base_period = food.get("cpi_base_observed_at")
        current_period = food.get("cpi_current_observed_at")
        if multiplier is None or not base_period or not current_period:
            continue
        return {
            "multiplier": float(multiplier),
            "base_period": str(base_period),
            "current_period": str(current_period),
            "base_value": float(food.get("cpi_base_value") or 0.0),
            "current_value": float(food.get("cpi_current_value") or 0.0),
        }
    return None


def _tracked_totals(food: dict[str, object], quantity_g: float) -> dict[str, float]:
    factor = quantity_g / 100.0
    return {
        "protein": float(food["protein"]) * factor,
        "energy_fibre_kcal": float(food["energy_fibre_kcal"]) * factor,
        "carbohydrate": float(food["carbohydrate"]) * factor,
        "fat": float(food["fat"]) * factor,
        "fiber": float(food["fiber"]) * factor,
        "calcium": float(food["calcium"]) * factor,
        "iron": float(food["iron"]) * factor,
        "vitamin_c": float(food["vitamin_c"]) * factor,
    }


def _reason(role: str, food: dict[str, object]) -> str:
    display_name = str(food["display_name"])
    if role == "protein_anchor":
        return f"{display_name} is doing most of the protein work in this basket."
    if role == "carb_base":
        return f"{display_name} provides an easy calorie and carbohydrate base."
    if role == "produce":
        return f"{display_name} keeps the basket practical with a simple produce option."
    return f"{display_name} helps close the remaining calorie gap."


def _shopping_mode_days(food: dict[str, object], days: int, shopping_mode: str) -> tuple[float, list[str], list[str]]:
    if days <= 1:
        return 1.0, [], []

    display_name = str(food["display_name"])
    effective_days = float(days)
    scaling_notes: list[str] = []
    warnings: list[str] = []
    perishable = _is_perishable(food)
    bulk_friendly = _is_bulk_friendly(food)
    shelf_stability = _food_shelf_stability(food)

    if shopping_mode == "fresh":
        if perishable:
            capped_days = min(days, 3)
            if capped_days < days:
                effective_days = float(capped_days)
                scaling_notes.append("Fresh mode keeps short-life items closer to a 3-day quantity.")
                warnings.append(f"{display_name} was kept closer to a fresh top-up amount for this shopping window.")
        elif shelf_stability == "ambient":
            capped_days = min(days, 4)
            if capped_days < days:
                effective_days = float(capped_days)
                scaling_notes.append("Fresh mode softens some room-temperature produce and pantry-adjacent items.")
    elif shopping_mode == "balanced":
        if perishable:
            capped_days = min(days, 5)
            if capped_days < days:
                effective_days = float(capped_days)
                scaling_notes.append("Balanced mode softens clearly perishable items on longer shopping windows.")
    else:
        if perishable:
            capped_days = min(days, 5)
            if capped_days < days:
                effective_days = float(capped_days)
                scaling_notes.append("Bulk mode still softens clearly perishable items.")
                warnings.append(f"{display_name} is perishable, so the bulk list still avoids a full {days}-day scale-up.")
        elif bulk_friendly and days >= 5:
            effective_days = float(days) * 1.1
            scaling_notes.append("Bulk mode slightly over-buys shelf-stable items to make pantry shopping easier.")

    return effective_days, scaling_notes, warnings


def _apply_quantity_sanity(
    food: dict[str, object],
    quantity_g: float,
    shopping_mode: str,
) -> tuple[float, list[str], list[str]]:
    purchase_unit_size_g = float(food.get("purchase_unit_size_g") or 0)
    display_name = str(food["display_name"])
    warnings: list[str] = []
    scaling_notes: list[str] = []

    if purchase_unit_size_g <= 0:
        return quantity_g, scaling_notes, warnings

    unit_count = quantity_g / purchase_unit_size_g
    if _is_perishable(food):
        max_units = {"fresh": 3, "balanced": 5, "bulk": 6}[shopping_mode]
        if unit_count > max_units:
            quantity_g = purchase_unit_size_g * max_units
            scaling_notes.append(f"{display_name} was capped to a more practical {max_units}-unit shopping quantity.")
            warnings.append(f"{display_name} was softened to avoid buying an impractical amount of perishable food.")
            unit_count = max_units

    if unit_count >= 6:
        warnings.append(f"{display_name} is a large buy for one trip. Consider topping up later or using the suggested swap.")
    return quantity_g, scaling_notes, warnings


def _quantity_unit_count(food: dict[str, object], quantity_g: float) -> float:
    purchase_unit_size_g = float(food.get("purchase_unit_size_g") or 0)
    if purchase_unit_size_g > 0:
        return quantity_g / purchase_unit_size_g
    default_serving_g = max(float(food.get("default_serving_g") or 100), 1.0)
    return quantity_g / default_serving_g


def _split_threshold(food: dict[str, object], role: str, shopping_mode: str) -> float:
    if role == "produce" or _is_perishable(food):
        return {"fresh": 2.0, "balanced": 3.0, "bulk": 4.0}[shopping_mode]
    if role == "protein_anchor":
        return {"fresh": 3.0, "balanced": 4.0, "bulk": 5.0}[shopping_mode]
    return {"fresh": 4.0, "balanced": 5.0, "bulk": 6.0}[shopping_mode]


def _split_fraction(food: dict[str, object], role: str) -> float:
    if role == "produce":
        return 0.35
    if _is_perishable(food):
        return 0.3
    return 0.25


def _split_candidate(
    food_id: str,
    role: str,
    available: dict[str, dict[str, object]],
    role_orders: dict[str, list[str]],
    chosen_ids: set[str],
) -> str | None:
    preferred: list[str] = []
    fallback: list[str] = []
    current_food = available[food_id]
    current_perishable = _is_perishable(current_food)
    for candidate_id in role_orders.get(role, []):
        if candidate_id == food_id or candidate_id not in available:
            continue
        candidate_food = available[candidate_id]
        if role == "produce" and not _is_perishable(candidate_food):
            continue
        if role == "protein_anchor" and current_perishable and not (candidate_food["food_family"] in {"protein", "legume", "dairy"}):
            continue
        target_list = preferred if candidate_id not in chosen_ids else fallback
        if role == "produce" and current_perishable and _is_perishable(candidate_food):
            target_list.append(candidate_id)
        else:
            target_list.append(candidate_id)
    for pool in (preferred, fallback):
        if pool:
            return pool[0]
    return None


def _insert_role_item_after(
    chosen: list[tuple[str, str]],
    source_food_id: str,
    candidate_id: str,
    role: str,
) -> None:
    if any(food_id == candidate_id for food_id, _role in chosen):
        return
    for idx, (food_id, existing_role) in enumerate(chosen):
        if food_id == source_food_id and existing_role == role:
            chosen.insert(idx + 1, (candidate_id, role))
            return
    chosen.append((candidate_id, role))


def _apply_split_realism(
    chosen: list[tuple[str, str]],
    available: dict[str, dict[str, object]],
    role_orders: dict[str, list[str]],
    scaled_quantities: dict[str, float],
    days: int,
    shopping_mode: str,
) -> tuple[list[tuple[str, str]], dict[str, float], list[str], list[str], bool]:
    if days < 5:
        return chosen, scaled_quantities, [], [], False

    updated_chosen = list(chosen)
    updated_quantities = dict(scaled_quantities)
    chosen_ids = {food_id for food_id, _role in updated_chosen}
    split_notes: list[str] = []
    realism_notes: list[str] = []
    adjusted = False

    for food_id, role in list(updated_chosen):
        quantity_g = updated_quantities.get(food_id, 0.0)
        if quantity_g <= 0:
            continue

        food = available[food_id]
        role_members = [
            candidate_id
            for candidate_id, candidate_role in updated_chosen
            if candidate_role == role and updated_quantities.get(candidate_id, 0.0) > 0
        ]
        role_total = sum(updated_quantities.get(candidate_id, 0.0) for candidate_id in role_members)
        if role_total <= 0:
            continue

        unit_count = _quantity_unit_count(food, quantity_g)
        concentration = quantity_g / role_total
        should_split = unit_count > _split_threshold(food, role, shopping_mode)
        if not should_split and role in {"produce", "protein_anchor"} and _is_perishable(food):
            threshold = 0.55 if role == "produce" else 0.65
            should_split = concentration >= threshold
        if not should_split:
            continue

        candidate_id = _split_candidate(food_id, role, available, role_orders, chosen_ids)
        if candidate_id is None:
            continue

        candidate_food = available[candidate_id]
        split_fraction = _split_fraction(food, role)
        split_quantity_g = _round_quantity_g(candidate_food, quantity_g * split_fraction)
        min_candidate_quantity_g = max(
            float(candidate_food.get("default_serving_g") or 0.0),
            min(float(candidate_food.get("purchase_unit_size_g") or 0.0), 100.0),
        )
        if split_quantity_g < max(40.0, min_candidate_quantity_g):
            continue

        remaining_quantity_g = _round_quantity_g(food, quantity_g - split_quantity_g)
        min_remaining_quantity_g = max(
            float(food.get("default_serving_g") or 0.0) * 0.6,
            min(float(food.get("purchase_unit_size_g") or 0.0), 120.0),
            40.0,
        )
        if remaining_quantity_g < min_remaining_quantity_g:
            continue

        updated_quantities[food_id] = remaining_quantity_g
        updated_quantities[candidate_id] = updated_quantities.get(candidate_id, 0.0) + split_quantity_g
        _insert_role_item_after(updated_chosen, food_id, candidate_id, role)
        chosen_ids.add(candidate_id)
        adjusted = True

        split_notes.append(
            f"Split part of {food['display_name']} into {candidate_food['display_name']} to keep the {role.replace('_', ' ')} mix more practical."
        )
        if role == "produce":
            realism_notes.append("Longer shopping windows spread fresh produce across multiple items instead of concentrating it in one pick.")
        elif role == "protein_anchor" and _is_perishable(food):
            realism_notes.append("Longer shopping windows spread short-life proteins across a couple of practical options.")
        else:
            realism_notes.append("Very large single-item quantities were softened with same-role swaps to keep the list more realistic.")

    return updated_chosen, updated_quantities, sorted(set(split_notes)), sorted(set(realism_notes)), adjusted


def _reason_short(role: str, food: dict[str, object], preferences: dict[str, object], nutrition_targets: dict[str, float]) -> str:
    meal_style = str(preferences.get("meal_style") or "any")
    if role == "protein_anchor":
        if meal_style == "breakfast" and (_metadata_bool(food, "breakfast_friendly") or "breakfast" in _meal_tags(food)):
            return "Breakfast protein anchor"
        if meal_style == "snack" and str(food.get("prep_level") or "") in {"none", "low"}:
            return "Snack-ready protein"
        if preferences["low_prep"] and _low_prep_ready(food, role):
            return "Ready-to-use protein option"
        return "High-protein anchor"
    if role == "carb_base":
        if meal_style == "breakfast" and (_metadata_bool(food, "breakfast_friendly") or "breakfast" in _meal_tags(food)):
            return "Breakfast carb base"
        if meal_style == "snack" and str(food.get("prep_level") or "") in {"none", "low"}:
            return "Snack-friendly carb base"
        if preferences["budget_friendly"] and float(food.get("budget_score") or 0) >= 4:
            return "Budget-friendly staple"
        return "Easy carb base"
    if role == "produce":
        if meal_style == "breakfast":
            return "Breakfast-friendly fruit or produce"
        if meal_style == "snack":
            return "Snack-ready produce"
        if nutrition_targets.get("fiber") and float(food.get("fiber_score") or 0) >= 2:
            return "High-fiber produce"
        if nutrition_targets.get("vitamin_c") and float(food.get("vitamin_c_score") or 0) >= 2:
            return "Vitamin C rich produce"
        if nutrition_targets.get("iron") and float(food.get("iron_score") or 0) >= 1.5:
            return "Iron-supporting produce"
        return "Practical produce pick"
    if meal_style == "snack":
        return "Snack calorie booster"
    if meal_style == "breakfast":
        return "Breakfast calorie support"
    if preferences["budget_friendly"] and float(food.get("budget_score") or 0) >= 4:
        return "Budget-friendly calorie support"
    return "Simple calorie booster"


def _why_selected(role: str, food: dict[str, object], preferences: dict[str, object], nutrition_targets: dict[str, float]) -> str:
    parts: list[str] = []
    meal_style = str(preferences.get("meal_style") or "any")
    if role == "protein_anchor":
        parts.append(f"Provides about {round(float(food['protein']))} g protein per 100 g.")
    elif role == "carb_base":
        parts.append(f"Provides about {round(float(food['carbohydrate']))} g carbohydrate per 100 g.")
    elif role == "produce":
        if float(food.get("vitamin_c_score") or 0) >= 1.5:
            parts.append("Adds produce with strong vitamin C coverage.")
        elif float(food.get("fiber_score") or 0) >= 1.5:
            parts.append("Adds extra fiber without making the basket hard to shop.")
        else:
            parts.append("Keeps the basket practical with an everyday produce option.")
    else:
        parts.append(f"Adds dense calories with about {round(float(food['fat']))} g fat per 100 g.")

    if meal_style != "any":
        label = {"breakfast": "breakfast", "lunch_dinner": "lunch and dinner", "snack": "snack"}[meal_style]
        if _meal_tags(food) & MEAL_STYLE_TAGS.get(meal_style, set()):
            parts.append(f"Fits the {label} use case.")
        elif meal_style == "snack" and str(food.get("prep_level") or "") in {"none", "low"}:
            parts.append("Easy to use as a quick snack.")
        elif meal_style == "lunch_dinner" and _metadata_bool(food, "microwave_friendly"):
            parts.append("Works well in a quick lunch or dinner routine.")

    if preferences["low_prep"] and str(food.get("prep_level") or "") in {"none", "low"}:
        parts.append("Fits a low-prep routine.")
    elif preferences["low_prep"] and _low_prep_ready(food, role):
        parts.append("Keeps prep light for a faster routine.")
    if preferences["budget_friendly"] and float(food.get("budget_score") or 0) >= 4:
        parts.append("Leans toward a lower-cost staple.")
    if nutrition_targets.get("fiber") and float(food.get("fiber_score") or 0) >= 1.5:
        parts.append("Helps push the basket toward the fiber target.")
    if nutrition_targets.get("calcium") and float(food.get("calcium_score") or 0) >= 1.5:
        parts.append("Supports the calcium target.")
    if nutrition_targets.get("iron") and float(food.get("iron_score") or 0) >= 1.5:
        parts.append("Supports the iron target.")
    if nutrition_targets.get("vitamin_c") and float(food.get("vitamin_c_score") or 0) >= 1.5:
        parts.append("Supports the vitamin C target.")
    return " ".join(parts)


def _meal_suggestion_item_score(food: dict[str, object], role: str, meal_type: str) -> float:
    food_id = _meal_suggestion_food_id(food)
    tags = _meal_tags(food)
    food_family = str(food["food_family"])
    prep_level = str(food.get("prep_level") or "medium")
    prep_score = PREP_LEVEL_SCORES.get(prep_level, 0.0)
    score = _base_commonality_score(food)

    if meal_type == "breakfast":
        if role == "protein_anchor":
            if _metadata_bool(food, "breakfast_friendly") or "breakfast" in tags:
                score += 4.0
            if food_id in BREAKFAST_PROTEIN_IDS:
                score += 3.0
            if food_family == "dairy":
                score += 2.0
            if str(food.get("generic_food_id")) == "eggs":
                score += 2.5
            if food_id in HEAVY_MEAL_PROTEIN_IDS:
                score -= 5.0
            if food_family == "legume":
                score -= 4.0
            if tags & {"lunch", "dinner"} and "breakfast" not in tags:
                score -= 3.8
        elif role == "carb_base":
            cluster = _carb_cluster(food)
            if cluster == "breakfast_carb":
                score += 4.2
            if food_id in BREAKFAST_CARB_IDS:
                score += 2.4
            elif cluster == "bread_wrap":
                score += 2.0
            else:
                score -= 3.2
        elif role == "produce":
            cluster = _produce_cluster(food)
            if food_id in BREAKFAST_PRODUCE_IDS:
                score += 3.2
            if cluster == "fruit":
                score += 3.4
            elif cluster == "portable_produce":
                score += 1.4
            else:
                score -= 3.0
        else:
            if "breakfast" in tags:
                score += 1.4
    elif meal_type == "lunch":
        if role == "protein_anchor":
            if tags & {"lunch", "dinner"}:
                score += 3.2
            if _metadata_bool(food, "microwave_friendly"):
                score += 0.8
        elif role == "carb_base":
            cluster = _carb_cluster(food)
            if cluster in {"meal_base", "legume_carb", "starchy_produce"}:
                score += 2.8
            elif cluster == "breakfast_carb":
                score -= 1.2
        elif role == "produce":
            cluster = _produce_cluster(food)
            if cluster in {"vegetable", "leafy_green", "starchy_produce", "freezer_veg"}:
                score += 2.2
            elif cluster == "fruit":
                score -= 0.8
    elif meal_type == "snack":
        if role == "protein_anchor":
            if tags & {"snack", "side"}:
                score += 2.8
            if food_id in SNACK_PROTEIN_IDS:
                score += 3.0
            if prep_score >= 2.0:
                score += 1.0
            if _metadata_bool(food, "cold_only"):
                score += 0.6
            if food_id in HEAVY_MEAL_PROTEIN_IDS:
                score -= 5.0
            if tags & {"lunch", "dinner"} and not (tags & {"snack", "side"}):
                score -= 2.8
        elif role == "carb_base":
            cluster = _carb_cluster(food)
            if food_id in SNACK_CARB_IDS:
                score += 2.4
            if cluster in {"portable_carb", "bread_wrap", "breakfast_carb"}:
                score += 2.2
            elif cluster in {"meal_base", "legume_carb", "starchy_produce"}:
                score -= 2.6
        elif role == "produce":
            cluster = _produce_cluster(food)
            if food_id in SNACK_PRODUCE_IDS:
                score += 3.0
            if cluster in {"fruit", "portable_produce"}:
                score += 2.6
            elif cluster == "vegetable":
                score += 0.2
            else:
                score -= 2.6
            if food_id not in SNACK_PRODUCE_IDS and cluster not in {"fruit", "portable_produce"}:
                score -= 1.2
            if food_id in {"lettuce", "spinach", "kale", "broccoli"}:
                score -= 3.0
        else:
            if food_family in {"fat", "dairy"}:
                score += 1.4
            if food_id in {"nuts", "peanut_butter", "almond_butter", "cheese"}:
                score += 1.5
            if _is_shelf_stable(food) or _metadata_bool(food, "cold_only"):
                score += 0.8
    else:
        if role == "protein_anchor":
            if tags & {"dinner", "lunch"}:
                score += 3.4
            if _metadata_bool(food, "microwave_friendly"):
                score += 0.8
        elif role == "carb_base":
            cluster = _carb_cluster(food)
            if cluster in {"meal_base", "legume_carb", "starchy_produce"}:
                score += 3.0
            elif cluster == "breakfast_carb":
                score -= 1.4
        elif role == "produce":
            cluster = _produce_cluster(food)
            if cluster in {"vegetable", "leafy_green", "freezer_veg", "starchy_produce"}:
                score += 2.3
            elif cluster == "fruit":
                score -= 1.0
        else:
            if food_family in {"fat", "dairy"}:
                score += 0.6

    return score


def _best_meal_item(
    shopping_items: list[dict[str, object]],
    available: dict[str, dict[str, object]],
    role: str,
    meal_type: str,
    excluded: set[str],
    used_counts: dict[str, int],
    used_role_clusters: dict[str, set[str]],
) -> tuple[dict[str, object] | None, float]:
    candidates = [item for item in shopping_items if str(item["role"]) == role and str(item["generic_food_id"]) not in excluded]
    if not candidates:
        return None, float("-inf")
    ranked: list[tuple[tuple[float, int, str, str], float, dict[str, object]]] = []
    for item in candidates:
        food = available[str(item["generic_food_id"])]
        food_id = _meal_suggestion_food_id(food)
        adjusted_score = _meal_suggestion_item_score(food, role, meal_type)
        repeat_penalty = used_counts.get(food_id, 0) * {
            "produce": 2.8,
            "carb_base": 1.9,
            "calorie_booster": 1.3,
            "protein_anchor": 1.0,
        }.get(role, 1.0)
        if _meal_suggestion_role_cluster(food, role) in used_role_clusters.get(role, set()):
            repeat_penalty += {
                "produce": 2.0,
                "carb_base": 1.4,
                "calorie_booster": 0.8,
                "protein_anchor": 0.6,
            }.get(role, 0.5)
        adjusted_score -= repeat_penalty
        ranked.append(
            (
                (
                    -adjusted_score,
                    int(food["commonality_rank"]),
                    str(item["name"]),
                    str(item["generic_food_id"]),
                ),
                adjusted_score,
                item,
            )
        )
    ranked.sort(key=lambda row: row[0])
    return ranked[0][2], ranked[0][1]


def _meal_suggestion_description(meal_type: str, items: list[dict[str, object]]) -> str:
    names = [str(item["name"]) for item in items]
    if not names:
        return ""
    if len(names) == 1:
        joined = names[0]
    elif len(names) == 2:
        joined = f"{names[0]} and {names[1]}"
    else:
        joined = f"{', '.join(names[:-1])}, and {names[-1]}"

    labels = {
        "breakfast": "Try",
        "lunch": "Use",
        "snack": "Keep",
        "dinner": "Build",
    }
    suffixes = {
        "breakfast": "for a simple breakfast using this shopping list.",
        "lunch": "for a straightforward lunch from this list.",
        "snack": "on hand for a quick snack from this list.",
        "dinner": "into an easy dinner with the recommended basket.",
    }
    return f"{labels[meal_type]} {joined} {suffixes[meal_type]}"


def _meal_suggestion_role_min_score(meal_type: str, role: str) -> float:
    thresholds = {
        ("breakfast", "protein_anchor"): 2.0,
        ("breakfast", "carb_base"): 2.0,
        ("breakfast", "produce"): 2.2,
        ("snack", "protein_anchor"): 1.8,
        ("snack", "produce"): 2.6,
        ("snack", "carb_base"): 1.4,
        ("snack", "calorie_booster"): 1.0,
        ("lunch", "protein_anchor"): 0.8,
        ("lunch", "carb_base"): 0.8,
        ("lunch", "produce"): 0.8,
        ("dinner", "protein_anchor"): 0.8,
        ("dinner", "carb_base"): 0.8,
        ("dinner", "produce"): 0.8,
        ("dinner", "calorie_booster"): 0.2,
    }
    return thresholds.get((meal_type, role), 0.0)


def _build_meal_suggestions(
    shopping_list: list[dict[str, object]],
    available: dict[str, dict[str, object]],
) -> list[dict[str, object]]:
    if not shopping_list:
        return []

    templates = [
        ("breakfast", "Breakfast idea", ["protein_anchor", "carb_base", "produce"], 2, 3, 2.6),
        ("lunch", "Lunch idea", ["protein_anchor", "carb_base", "produce"], 2, 3, 1.2),
        ("snack", "Snack idea", ["protein_anchor", "produce", "calorie_booster", "carb_base"], 2, 3, 2.2),
        ("dinner", "Dinner idea", ["protein_anchor", "carb_base", "produce", "calorie_booster"], 2, 4, 1.4),
    ]

    suggestions: list[dict[str, object]] = []
    seen_signatures: set[tuple[str, ...]] = set()
    used_counts: dict[str, int] = {}
    used_role_clusters: dict[str, set[str]] = {}
    for meal_type, title, role_order, min_items, max_items, min_avg_score in templates:
        chosen_items: list[dict[str, object]] = []
        chosen_scores: list[float] = []
        excluded: set[str] = set()
        for role in role_order:
            if len(chosen_items) >= max_items:
                break
            candidate, candidate_score = _best_meal_item(shopping_list, available, role, meal_type, excluded, used_counts, used_role_clusters)
            if candidate is None:
                continue
            if candidate_score < _meal_suggestion_role_min_score(meal_type, role):
                continue
            chosen_items.append(candidate)
            chosen_scores.append(candidate_score)
            excluded.add(str(candidate["generic_food_id"]))

        if len(chosen_items) < min_items:
            continue

        average_score = sum(chosen_scores) / len(chosen_scores) if chosen_scores else 0.0
        if average_score < min_avg_score:
            continue

        signature = tuple(sorted(str(item["generic_food_id"]) for item in chosen_items))
        if signature in seen_signatures:
            continue
        seen_signatures.add(signature)
        for item in chosen_items:
            food = available[str(item["generic_food_id"])]
            food_id = _meal_suggestion_food_id(food)
            used_counts[food_id] = used_counts.get(food_id, 0) + 1
            used_role_clusters.setdefault(str(item["role"]), set()).add(_meal_suggestion_role_cluster(food, str(item["role"])))
        suggestions.append(
            {
                "meal_type": meal_type,
                "title": title,
                "items": [str(item["name"]) for item in chosen_items],
                "description": _meal_suggestion_description(meal_type, chosen_items),
            }
        )

    if len(suggestions) < 2:
        fallback_templates = [
            ("snack", "Snack idea", ["protein_anchor", "produce", "carb_base", "calorie_booster"], 2, 3, 1.2),
            ("lunch", "Lunch idea", ["protein_anchor", "carb_base", "produce"], 2, 3, 0.6),
        ]
        for meal_type, title, role_order, min_items, max_items, min_avg_score in fallback_templates:
            if len(suggestions) >= 3:
                break
            chosen_items = []
            chosen_scores = []
            excluded = set()
            for role in role_order:
                if len(chosen_items) >= max_items:
                    break
                candidate, candidate_score = _best_meal_item(
                    shopping_list,
                    available,
                    role,
                    meal_type,
                    excluded,
                    used_counts,
                    used_role_clusters,
                )
                if candidate is None:
                    continue
                if candidate_score < (_meal_suggestion_role_min_score(meal_type, role) - 0.8):
                    continue
                chosen_items.append(candidate)
                chosen_scores.append(candidate_score)
                excluded.add(str(candidate["generic_food_id"]))

            if len(chosen_items) < min_items:
                continue
            average_score = sum(chosen_scores) / len(chosen_scores) if chosen_scores else 0.0
            if average_score < min_avg_score:
                continue
            signature = tuple(sorted(str(item["generic_food_id"]) for item in chosen_items))
            if signature in seen_signatures:
                continue
            seen_signatures.add(signature)
            suggestions.append(
                {
                    "meal_type": meal_type,
                    "title": title,
                    "items": [str(item["name"]) for item in chosen_items],
                    "description": _meal_suggestion_description(meal_type, chosen_items),
                }
            )

    if len(suggestions) < 2:
        ranked_snack_items: list[tuple[float, int, dict[str, object]]] = []
        for item in shopping_list:
            food = available[str(item["generic_food_id"])]
            score = _meal_suggestion_item_score(food, str(item["role"]), "snack")
            ranked_snack_items.append(
                (
                    -score,
                    int(food.get("commonality_rank") or 999),
                    item,
                )
            )
        ranked_snack_items.sort()
        compact_items: list[dict[str, object]] = []
        compact_signature_ids: set[str] = set()
        for _neg_score, _rank, item in ranked_snack_items:
            food_id = str(item["generic_food_id"])
            if food_id in compact_signature_ids:
                continue
            compact_items.append(item)
            compact_signature_ids.add(food_id)
            if len(compact_items) >= 3:
                break
        if len(compact_items) >= 2:
            signature = tuple(sorted(compact_signature_ids))
            if signature not in seen_signatures:
                suggestions.append(
                    {
                        "meal_type": "snack",
                        "title": "Snack idea",
                        "items": [str(item["name"]) for item in compact_items],
                        "description": _meal_suggestion_description("snack", compact_items),
                    }
                )

    return suggestions


def _value_explanation(
    role: str,
    food: dict[str, object],
    preferences: dict[str, object],
    nutrition_targets: dict[str, float],
) -> tuple[str | None, str | None]:
    price_signals = _price_efficiency_signals(food)
    unit_price = food.get("bls_estimated_unit_price")
    if unit_price is None:
        return None, None

    metric_candidates: list[tuple[float, str, str]] = []
    budget_friendly = bool(preferences.get("budget_friendly"))

    if role == "protein_anchor":
        metric_candidates.extend(
            [
                (
                    price_signals["protein_score"] + (0.25 if budget_friendly else 0.0),
                    "High protein per dollar",
                    "Compared with other protein picks, this one delivers strong protein value for the price reference.",
                ),
                (
                    price_signals["calories_score"] * 0.8 + (0.15 if budget_friendly else 0.0),
                    "Good calorie value for protein",
                    "This protein option also carries a relatively efficient calorie cost for the average-price reference.",
                ),
            ]
        )
    elif role == "carb_base":
        metric_candidates.extend(
            [
                (
                    price_signals["calories_score"] + (0.35 if budget_friendly else 0.0),
                    "Low-cost calorie base",
                    "This carb base covers a lot of calories for the average-price reference.",
                ),
                (
                    price_signals["carbs_score"] + (0.2 if budget_friendly else 0.0),
                    "Good carbs per dollar",
                    "This option provides a strong amount of carbohydrate for the average-price reference.",
                ),
                (
                    price_signals["fiber_score"] * 0.8 + (0.15 if budget_friendly else 0.0),
                    "Affordable fiber source",
                    "Among the priced carb options, this one adds useful fiber without pushing cost up much.",
                ),
            ]
        )
    elif role == "produce":
        metric_candidates.extend(
            [
                (
                    price_signals["fiber_score"] + (0.2 if budget_friendly else 0.0),
                    "Affordable fiber source",
                    "This produce item adds fiber at a relatively good average-price value.",
                ),
                (
                    price_signals["vitamin_c_score"] + (0.15 if budget_friendly else 0.0),
                    "Good vitamin C value",
                    "This produce choice gives strong vitamin C coverage for the average-price reference.",
                ),
            ]
        )
        if nutrition_targets.get("calcium"):
            metric_candidates.append(
                (
                    price_signals["calcium_score"] + (0.1 if budget_friendly else 0.0),
                    "Affordable calcium support",
                    "This produce item helps the calcium target without relying on a high average-price item.",
                )
            )
    else:
        metric_candidates.extend(
            [
                (
                    price_signals["calories_score"] + (0.3 if budget_friendly else 0.0),
                    "Low-cost calorie booster",
                    "This extra adds a lot of calories for the average-price reference.",
                ),
                (
                    price_signals["calcium_score"] * 0.8,
                    "Good calcium value",
                    "This booster also contributes calcium at a relatively good average-price value.",
                ),
            ]
        )

    if budget_friendly and float(food.get("budget_score") or 0) >= 4:
        metric_candidates.append(
            (
                0.45,
                "Budget-friendly staple",
                "It stays consistent with the lower-cost bias used for budget-friendly baskets.",
            )
        )

    best_score = 0.0
    best_short: str | None = None
    best_note: str | None = None
    for candidate_score, candidate_short, candidate_note in metric_candidates:
        if candidate_score > best_score:
            best_score = candidate_score
            best_short = candidate_short
            best_note = candidate_note

    if best_score < 0.22:
        return None, None
    return best_short, best_note


def _substitution_reason(role: str, substitution: str | None) -> str | None:
    if substitution is None:
        return None
    if role == "protein_anchor":
        return "Similar protein anchor that fits the same basket role."
    if role == "carb_base":
        return "Can replace the main carb base while keeping the basket balanced."
    if role == "produce":
        return "Easy produce swap with a similar support role."
    return "Can replace this calorie-support item without changing the overall basket structure."


def _substitution(
    food_id: str,
    role: str,
    available: dict[str, dict[str, object]],
    role_orders: dict[str, list[str]],
) -> str | None:
    for candidate_id in role_orders.get(role, []):
        if candidate_id != food_id and candidate_id in available:
            return str(available[candidate_id]["display_name"])
    return None


def _state_from_address(address: str) -> str | None:
    match = re.search(r",\s*([A-Z]{2})(?:\s*(?:,|\d{5}))", address.upper())
    if match:
        return match.group(1)
    return None


def _city_from_address(address: str) -> str | None:
    match = re.search(r",\s*([^,]+),\s*[A-Z]{2}(?:\s*(?:,|\d{5}))", address)
    if match:
        return match.group(1).strip()
    return None


def _approximate_area_from_lat_lon(lat: float, lon: float) -> str | None:
    if not (-170.0 <= lon <= -60.0 and 18.0 <= lat <= 72.0):
        return None
    if lon <= -104.0:
        return "400"
    if lon <= -89.0:
        return "300" if lat < 39.0 else "200"
    return "300" if lat < 40.5 else "100"


def _approximate_usda_area_from_lat_lon(lat: float, lon: float) -> str:
    for area_code, (min_lat, max_lat, min_lon, max_lon) in USDA_METRO_BBOXES.items():
        if min_lat <= lat <= max_lat and min_lon <= lon <= max_lon:
            return area_code
    bls_area_code = _approximate_area_from_lat_lon(lat, lon)
    return USDA_REGION_FROM_BLS.get(bls_area_code or "", "US")


def _match_usda_metro_from_stores(stores: list[dict[str, object]]) -> str | None:
    metro_city_map = {
        ("atlanta", "ga"): "ATLANTA",
        ("boston", "ma"): "BOSTON",
        ("chicago", "il"): "CHICAGO",
        ("dallas", "tx"): "DALLAS",
        ("detroit", "mi"): "DETROIT",
        ("houston", "tx"): "HOUSTON",
        ("los angeles", "ca"): "LOS_ANGELES",
        ("miami", "fl"): "MIAMI",
        ("new york", "ny"): "NEW_YORK",
        ("philadelphia", "pa"): "PHILADELPHIA",
    }
    for store in stores:
        address = str(store.get("address") or "")
        state = (_state_from_address(address) or "").strip().lower()
        city = (_city_from_address(address) or "").strip().lower()
        area_code = metro_city_map.get((city, state))
        if area_code:
            return area_code
    return None


def resolve_price_context(
    lat: float,
    lon: float,
    stores: list[dict[str, object]] | None = None,
) -> dict[str, str]:
    stores = stores or []
    usda_area_code = _match_usda_metro_from_stores(stores)
    bls_area_code = None
    for store in stores:
        state = _state_from_address(str(store.get("address") or ""))
        if state and state in STATE_REGION_CODES:
            bls_area_code = STATE_REGION_CODES[state]
            if not usda_area_code:
                usda_area_code = USDA_REGION_FROM_BLS.get(bls_area_code, "US")
            break

    if not bls_area_code:
        bls_area_code = _approximate_area_from_lat_lon(lat, lon) or "0"
    if not usda_area_code:
        usda_area_code = _approximate_usda_area_from_lat_lon(lat, lon)

    return {
        "usda_area_code": usda_area_code,
        "usda_area_name": USDA_AREA_NAMES.get(usda_area_code, USDA_AREA_NAMES["US"]),
        "bls_area_code": bls_area_code,
        "bls_area_name": BLS_AREA_NAMES.get(bls_area_code, BLS_AREA_NAMES["0"]),
    }


def resolve_bls_price_area(
    lat: float,
    lon: float,
    stores: list[dict[str, object]] | None = None,
) -> tuple[str, str, str]:
    context = resolve_price_context(lat, lon, stores)
    area_code = context["bls_area_code"]
    area_name = context["bls_area_name"]
    if area_code == "0":
        return (
            area_code,
            area_name,
            "Using U.S. city average BLS average prices as the typical grocery reference because no better regional match was available from the request location.",
        )
    return (
        area_code,
        area_name,
        f"Using {area_name} BLS average prices as the typical regional grocery reference, with U.S. city average fallback when a mapped regional price is unavailable.",
    )


def recommend_generic_food_candidates(
    con: duckdb.DuckDBPyConnection,
    protein_target_g: float,
    calorie_target_kcal: float,
    preferences: dict[str, object] | None = None,
    nutrition_targets: dict[str, float] | None = None,
    pantry_items: Iterable[str] | None = None,
    days: int = 1,
    shopping_mode: str = "balanced",
    price_context: dict[str, str] | None = None,
    stores: Sequence[dict[str, object]] | None = None,
    candidate_count: int = 6,
    candidate_generation_config: dict[str, object] | None = None,
) -> list[dict[str, object]]:
    from dietdashboard.hybrid_planner import recommend_generic_food_candidates as _recommend_generic_food_candidates

    return _recommend_generic_food_candidates(
        con,
        protein_target_g=protein_target_g,
        calorie_target_kcal=calorie_target_kcal,
        preferences=preferences,
        nutrition_targets=nutrition_targets,
        pantry_items=pantry_items,
        days=days,
        shopping_mode=shopping_mode,
        price_context=price_context,
        stores=stores,
        candidate_count=candidate_count,
        candidate_generation_config=candidate_generation_config,
    )


def recommend_generic_foods(
    con: duckdb.DuckDBPyConnection,
    protein_target_g: float,
    calorie_target_kcal: float,
    preferences: dict[str, object] | None = None,
    nutrition_targets: dict[str, float] | None = None,
    pantry_items: Iterable[str] | None = None,
    days: int = 1,
    shopping_mode: str = "balanced",
    price_context: dict[str, str] | None = None,
    stores: Sequence[dict[str, object]] | None = None,
    scorer_config: dict[str, object] | None = None,
    candidate_generation_config: dict[str, object] | None = None,
) -> dict[str, object]:
    from dietdashboard.hybrid_planner import (
        normalize_candidate_generation_config,
        normalize_scorer_config,
        recommend_with_trained_scorer,
    )

    return recommend_with_trained_scorer(
        con,
        protein_target_g=protein_target_g,
        calorie_target_kcal=calorie_target_kcal,
        preferences=preferences,
        nutrition_targets=nutrition_targets,
        pantry_items=pantry_items,
        days=days,
        shopping_mode=shopping_mode,
        price_context=price_context,
        stores=stores,
        scorer_config=normalize_scorer_config(scorer_config),
        candidate_generation_config=normalize_candidate_generation_config(candidate_generation_config),
    )
