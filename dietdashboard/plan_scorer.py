"""Local utilities for training and applying a candidate-plan scorer."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path

from joblib import dump, load
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.feature_extraction import DictVectorizer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import Pipeline

from dietdashboard import candidate_debug


class PlanScorerArtifactError(RuntimeError):
    """Raised when the required trained scorer artifact is missing or invalid."""


NUMERIC_FEATURES = (
    "days",
    "target_protein_g",
    "target_calorie_kcal",
    "estimated_protein_g",
    "estimated_calorie_kcal",
    "estimated_carbohydrate_g",
    "estimated_fat_g",
    "estimated_fiber_g",
    "estimated_calcium_mg",
    "estimated_iron_mg",
    "estimated_vitamin_c_mg",
    "protein_abs_gap_g",
    "calorie_abs_gap_kcal",
    "carbohydrate_abs_gap_g",
    "fat_abs_gap_g",
    "fiber_abs_gap_g",
    "calcium_abs_gap_mg",
    "iron_abs_gap_mg",
    "vitamin_c_abs_gap_mg",
    "protein_gap_ratio",
    "calorie_gap_ratio",
    "macro_gap_ratio_sum",
    "estimated_basket_cost",
    "price_per_1000_kcal",
    "price_per_100g_protein",
    "priced_item_ratio",
    "unique_ingredient_count",
    "protein_anchor_count",
    "carb_base_count",
    "produce_count",
    "calorie_booster_count",
    "goal_structure_alignment_score",
    "role_share_gap_total",
    "protein_anchor_share",
    "carb_base_share",
    "produce_share",
    "calorie_booster_share",
    "protein_anchor_family_diversity",
    "animal_protein_anchor_count",
    "lean_protein_anchor_count",
    "vegetarian_protein_anchor_count",
    "legume_protein_anchor_count",
    "soy_protein_anchor_count",
    "dairy_or_egg_anchor_count",
    "budget_support_anchor_count",
    "fruit_produce_count",
    "high_volume_produce_count",
    "low_cost_produce_count",
    "food_family_diversity_count",
    "role_diversity_count",
    "repetition_penalty",
    "unrealistic_basket_penalty",
    "preference_match_score",
    "heuristic_selection_score",
    "overlap_with_best_heuristic_jaccard",
    "changed_food_count_vs_best_heuristic",
    "role_assignment_changes_vs_best_heuristic",
    "cost_delta_vs_best_heuristic",
    "protein_gap_delta_vs_best_heuristic",
    "calorie_gap_delta_vs_best_heuristic",
    "macro_gap_ratio_delta_vs_best_heuristic",
    "diversity_gain_vs_best_heuristic",
    "role_diversity_delta_vs_best_heuristic",
    "repetition_penalty_delta_vs_best_heuristic",
    "unrealistic_penalty_delta_vs_best_heuristic",
    "preference_match_delta_vs_best_heuristic",
    "alternative_quality_score",
    "nearby_store_count",
    "warning_count",
    "realism_note_count",
    "pantry_note_count",
    "scaling_note_count",
)
BOOLEAN_FEATURES = (
    "adjusted_by_split",
    "has_price_estimate",
    "budget_friendly_preference",
    "low_prep_preference",
    "vegetarian_preference",
    "vegan_preference",
    "dairy_free_preference",
    "materially_different_from_best_heuristic",
    "nutritionally_competitive_with_best_heuristic",
    "cost_competitive_with_best_heuristic",
    "diversity_improved_vs_best_heuristic",
)
CATEGORICAL_FEATURES = (
    "goal_profile",
    "shopping_mode",
    "meal_style",
)
TRAINING_METADATA_FIELDS = (
    "request_id",
    "candidate_id",
    "baseline_candidate_id",
    "candidate_source",
    "label_score",
)
DEFAULT_RANDOM_SEED = 42


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def default_model_dir() -> Path:
    return project_root() / "artifacts" / "plan_scorer"


def default_model_path() -> Path:
    return default_model_dir() / "plan_candidate_scorer.joblib"


def default_dataset_path() -> Path:
    return default_model_dir() / "plan_candidate_training_dataset.csv"


def default_metrics_path() -> Path:
    return default_model_dir() / "plan_candidate_training_metrics.json"


def default_feature_summary_path() -> Path:
    return default_model_dir() / "plan_candidate_feature_summary.csv"


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


def _safe_bool(value: object) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, str):
        return int(value.strip().lower() in {"1", "true", "yes"})
    return int(bool(value))


def _nutrition_value(summary: Mapping[str, object], key: str) -> float:
    return _safe_float(summary.get(key))


def _goal_tradeoff_profile(feature_row: Mapping[str, object]) -> dict[str, float]:
    goal_profile = str(feature_row.get("goal_profile") or "generic_balanced")
    budget_friendly = bool(_safe_bool(feature_row.get("budget_friendly_preference")))
    profile = {
        "protein_gap_scale": 1.0,
        "calorie_gap_scale": 1.0,
        "macro_gap_scale": 1.0,
        "cost_penalty_scale": 1.0,
        "price_penalty_scale": 1.0,
        "diversity_reward_scale": 1.0,
        "repetition_penalty_scale": 1.0,
        "preference_reward_scale": 1.0,
        "alternative_protein_tolerance_g": 12.0,
        "alternative_calorie_tolerance_kcal": 180.0,
        "alternative_macro_tolerance": 0.3,
        "alternative_cost_tolerance": 1.5,
        "soft_cost_delta": 0.75,
        "soft_protein_delta": 4.0,
        "soft_calorie_delta": 60.0,
    }

    if goal_profile == "muscle_gain":
        profile.update(
            {
                "protein_gap_scale": 1.18,
                "calorie_gap_scale": 1.2,
                "cost_penalty_scale": 0.88,
                "price_penalty_scale": 0.9,
                "diversity_reward_scale": 0.95,
                "alternative_protein_tolerance_g": 14.0,
                "alternative_calorie_tolerance_kcal": 220.0,
                "alternative_cost_tolerance": 2.2,
                "soft_cost_delta": 1.2,
            }
        )
    elif goal_profile == "fat_loss":
        profile.update(
            {
                "protein_gap_scale": 1.15,
                "calorie_gap_scale": 1.08,
                "cost_penalty_scale": 0.95,
                "diversity_reward_scale": 0.9,
                "repetition_penalty_scale": 1.05,
                "alternative_protein_tolerance_g": 10.0,
                "alternative_calorie_tolerance_kcal": 140.0,
                "alternative_cost_tolerance": 1.2,
                "soft_cost_delta": 0.6,
            }
        )
    elif goal_profile == "maintenance":
        profile.update(
            {
                "cost_penalty_scale": 0.92,
                "diversity_reward_scale": 1.12,
                "repetition_penalty_scale": 1.08,
                "preference_reward_scale": 1.05,
                "alternative_cost_tolerance": 1.6,
            }
        )
    elif goal_profile == "budget_friendly_healthy":
        profile.update(
            {
                "cost_penalty_scale": 1.45,
                "price_penalty_scale": 1.35,
                "diversity_reward_scale": 0.88,
                "alternative_cost_tolerance": 0.75,
                "soft_cost_delta": 0.35,
                "alternative_protein_tolerance_g": 10.0,
                "alternative_calorie_tolerance_kcal": 150.0,
            }
        )
    elif goal_profile == "high_protein_vegetarian":
        profile.update(
            {
                "protein_gap_scale": 1.1,
                "calorie_gap_scale": 1.05,
                "cost_penalty_scale": 0.88,
                "diversity_reward_scale": 1.18,
                "repetition_penalty_scale": 1.12,
                "preference_reward_scale": 1.08,
                "alternative_protein_tolerance_g": 13.0,
                "alternative_calorie_tolerance_kcal": 190.0,
                "alternative_cost_tolerance": 2.0,
                "soft_cost_delta": 1.1,
            }
        )

    if budget_friendly:
        profile["cost_penalty_scale"] *= 1.12
        profile["price_penalty_scale"] *= 1.08
        profile["alternative_cost_tolerance"] = min(profile["alternative_cost_tolerance"], 0.85)
        profile["soft_cost_delta"] = min(profile["soft_cost_delta"], 0.45)
    return profile


def _candidate_source_labels(candidate: Mapping[str, object]) -> set[str]:
    metadata = candidate.get("candidate_metadata")
    if not isinstance(metadata, Mapping):
        return {"heuristic"}
    labels = metadata.get("source_labels")
    if isinstance(labels, Sequence):
        normalized = {str(label or "").strip() for label in labels if str(label or "").strip()}
        if normalized:
            return normalized
    return {str(metadata.get("source") or "heuristic")}


def _best_heuristic_reference_index(
    candidates: Sequence[Mapping[str, object]],
    feature_rows: Sequence[Mapping[str, object]],
) -> int:
    heuristic_indices = [
        index
        for index, candidate in enumerate(candidates)
        if "heuristic" in _candidate_source_labels(candidate)
    ]
    if not heuristic_indices:
        return 0
    return max(
        heuristic_indices,
        key=lambda index: (
            float(heuristic_candidate_label(feature_rows[index])),
            float(_safe_float(feature_rows[index].get("heuristic_selection_score"))),
            -float(_safe_float(feature_rows[index].get("unrealistic_basket_penalty"))),
            str(candidates[index].get("candidate_id") or ""),
        ),
    )


def extract_candidate_features(candidate: Mapping[str, object]) -> dict[str, object]:
    recommendation = candidate.get("recommendation") if isinstance(candidate.get("recommendation"), Mapping) else {}
    recommendation = recommendation if isinstance(recommendation, Mapping) else {}
    metadata = candidate.get("candidate_metadata") if isinstance(candidate.get("candidate_metadata"), Mapping) else {}
    metadata = metadata if isinstance(metadata, Mapping) else {}
    request_context = candidate.get("request_context") if isinstance(candidate.get("request_context"), Mapping) else {}
    request_context = request_context if isinstance(request_context, Mapping) else {}
    preferences = request_context.get("preferences") if isinstance(request_context.get("preferences"), Mapping) else {}
    preferences = preferences if isinstance(preferences, Mapping) else {}
    nutrition_summary = recommendation.get("nutrition_summary") if isinstance(recommendation.get("nutrition_summary"), Mapping) else {}
    nutrition_summary = nutrition_summary if isinstance(nutrition_summary, Mapping) else {}

    estimated_calories = _nutrition_value(nutrition_summary, "calorie_estimated_kcal")
    estimated_protein = _nutrition_value(nutrition_summary, "protein_estimated_g")
    basket_cost = _safe_float(recommendation.get("estimated_basket_cost"))
    priced_item_count = max(_safe_int(recommendation.get("priced_item_count")), 0)
    shopping_list = recommendation.get("shopping_list") if isinstance(recommendation.get("shopping_list"), Sequence) else []
    item_count = len(shopping_list)
    total_price = basket_cost if basket_cost > 0 else 0.0

    protein_target = _nutrition_value(nutrition_summary, "protein_target_g")
    calorie_target = _nutrition_value(nutrition_summary, "calorie_target_kcal")
    carbohydrate_target = _nutrition_value(nutrition_summary, "carbohydrate_target_g")
    fat_target = _nutrition_value(nutrition_summary, "fat_target_g")
    fiber_target = _nutrition_value(nutrition_summary, "fiber_target_g")
    calcium_target = _nutrition_value(nutrition_summary, "calcium_target_mg")
    iron_target = _nutrition_value(nutrition_summary, "iron_target_mg")
    vitamin_c_target = _nutrition_value(nutrition_summary, "vitamin_c_target_mg")

    protein_gap = abs(estimated_protein - protein_target)
    calorie_gap = abs(estimated_calories - calorie_target)
    carbohydrate_gap = abs(_nutrition_value(nutrition_summary, "carbohydrate_estimated_g") - carbohydrate_target)
    fat_gap = abs(_nutrition_value(nutrition_summary, "fat_estimated_g") - fat_target)
    fiber_gap = abs(_nutrition_value(nutrition_summary, "fiber_estimated_g") - fiber_target)
    calcium_gap = abs(_nutrition_value(nutrition_summary, "calcium_estimated_mg") - calcium_target)
    iron_gap = abs(_nutrition_value(nutrition_summary, "iron_estimated_mg") - iron_target)
    vitamin_c_gap = abs(_nutrition_value(nutrition_summary, "vitamin_c_estimated_mg") - vitamin_c_target)

    def ratio(gap: float, target: float) -> float:
        if target <= 0:
            return 0.0
        return gap / max(target, 1.0)

    features: dict[str, object] = {
        "days": _safe_int(recommendation.get("days")) or _safe_int(request_context.get("days")) or 1,
        "target_protein_g": protein_target,
        "target_calorie_kcal": calorie_target,
        "estimated_protein_g": estimated_protein,
        "estimated_calorie_kcal": estimated_calories,
        "estimated_carbohydrate_g": _nutrition_value(nutrition_summary, "carbohydrate_estimated_g"),
        "estimated_fat_g": _nutrition_value(nutrition_summary, "fat_estimated_g"),
        "estimated_fiber_g": _nutrition_value(nutrition_summary, "fiber_estimated_g"),
        "estimated_calcium_mg": _nutrition_value(nutrition_summary, "calcium_estimated_mg"),
        "estimated_iron_mg": _nutrition_value(nutrition_summary, "iron_estimated_mg"),
        "estimated_vitamin_c_mg": _nutrition_value(nutrition_summary, "vitamin_c_estimated_mg"),
        "protein_abs_gap_g": protein_gap,
        "calorie_abs_gap_kcal": calorie_gap,
        "carbohydrate_abs_gap_g": carbohydrate_gap,
        "fat_abs_gap_g": fat_gap,
        "fiber_abs_gap_g": fiber_gap,
        "calcium_abs_gap_mg": calcium_gap,
        "iron_abs_gap_mg": iron_gap,
        "vitamin_c_abs_gap_mg": vitamin_c_gap,
        "protein_gap_ratio": ratio(protein_gap, protein_target),
        "calorie_gap_ratio": ratio(calorie_gap, calorie_target),
        "macro_gap_ratio_sum": (
            ratio(carbohydrate_gap, carbohydrate_target)
            + ratio(fat_gap, fat_target)
            + ratio(fiber_gap, fiber_target)
            + ratio(calcium_gap, calcium_target)
            + ratio(iron_gap, iron_target)
            + ratio(vitamin_c_gap, vitamin_c_target)
        ),
        "estimated_basket_cost": total_price,
        "price_per_1000_kcal": total_price / max(estimated_calories / 1000.0, 0.1) if total_price > 0 else 0.0,
        "price_per_100g_protein": total_price / max(estimated_protein / 100.0, 0.1) if total_price > 0 else 0.0,
        "priced_item_ratio": priced_item_count / max(item_count, 1),
        "unique_ingredient_count": item_count,
        "protein_anchor_count": _safe_int(metadata.get("role_counts", {}).get("protein_anchor") if isinstance(metadata.get("role_counts"), Mapping) else 0),
        "carb_base_count": _safe_int(metadata.get("role_counts", {}).get("carb_base") if isinstance(metadata.get("role_counts"), Mapping) else 0),
        "produce_count": _safe_int(metadata.get("role_counts", {}).get("produce") if isinstance(metadata.get("role_counts"), Mapping) else 0),
        "calorie_booster_count": _safe_int(metadata.get("role_counts", {}).get("calorie_booster") if isinstance(metadata.get("role_counts"), Mapping) else 0),
        "goal_structure_alignment_score": _safe_float(metadata.get("goal_structure_alignment_score")),
        "role_share_gap_total": _safe_float(metadata.get("role_share_gap_total")),
        "protein_anchor_share": _safe_float(metadata.get("role_calorie_shares", {}).get("protein_anchor") if isinstance(metadata.get("role_calorie_shares"), Mapping) else 0),
        "carb_base_share": _safe_float(metadata.get("role_calorie_shares", {}).get("carb_base") if isinstance(metadata.get("role_calorie_shares"), Mapping) else 0),
        "produce_share": _safe_float(metadata.get("role_calorie_shares", {}).get("produce") if isinstance(metadata.get("role_calorie_shares"), Mapping) else 0),
        "calorie_booster_share": _safe_float(metadata.get("role_calorie_shares", {}).get("calorie_booster") if isinstance(metadata.get("role_calorie_shares"), Mapping) else 0),
        "protein_anchor_family_diversity": _safe_float(metadata.get("protein_anchor_family_diversity")),
        "animal_protein_anchor_count": _safe_float(metadata.get("animal_protein_anchor_count")),
        "lean_protein_anchor_count": _safe_float(metadata.get("lean_protein_anchor_count")),
        "vegetarian_protein_anchor_count": _safe_float(metadata.get("vegetarian_protein_anchor_count")),
        "legume_protein_anchor_count": _safe_float(metadata.get("legume_protein_anchor_count")),
        "soy_protein_anchor_count": _safe_float(metadata.get("soy_protein_anchor_count")),
        "dairy_or_egg_anchor_count": _safe_float(metadata.get("dairy_or_egg_anchor_count")),
        "budget_support_anchor_count": _safe_float(metadata.get("budget_support_anchor_count")),
        "fruit_produce_count": _safe_float(metadata.get("fruit_produce_count")),
        "high_volume_produce_count": _safe_float(metadata.get("high_volume_produce_count")),
        "low_cost_produce_count": _safe_float(metadata.get("low_cost_produce_count")),
        "food_family_diversity_count": _safe_int(metadata.get("food_family_diversity_count")),
        "role_diversity_count": _safe_int(metadata.get("role_diversity_count")),
        "repetition_penalty": _safe_float(metadata.get("repetition_penalty")),
        "unrealistic_basket_penalty": _safe_float(metadata.get("unrealistic_basket_penalty")),
        "preference_match_score": _safe_float(metadata.get("preference_match_score")),
        "heuristic_selection_score": _safe_float(metadata.get("heuristic_selection_score")),
        "overlap_with_best_heuristic_jaccard": 1.0,
        "changed_food_count_vs_best_heuristic": 0.0,
        "role_assignment_changes_vs_best_heuristic": 0.0,
        "cost_delta_vs_best_heuristic": 0.0,
        "protein_gap_delta_vs_best_heuristic": 0.0,
        "calorie_gap_delta_vs_best_heuristic": 0.0,
        "macro_gap_ratio_delta_vs_best_heuristic": 0.0,
        "diversity_gain_vs_best_heuristic": 0.0,
        "role_diversity_delta_vs_best_heuristic": 0.0,
        "repetition_penalty_delta_vs_best_heuristic": 0.0,
        "unrealistic_penalty_delta_vs_best_heuristic": 0.0,
        "preference_match_delta_vs_best_heuristic": 0.0,
        "alternative_quality_score": 0.0,
        "nearby_store_count": _safe_int(metadata.get("nearby_store_count")),
        "warning_count": len(recommendation.get("warnings") or []),
        "realism_note_count": len(recommendation.get("realism_notes") or []),
        "pantry_note_count": len(recommendation.get("pantry_notes") or []),
        "scaling_note_count": len(recommendation.get("scaling_notes") or []),
        "adjusted_by_split": _safe_bool(recommendation.get("adjusted_by_split")),
        "has_price_estimate": _safe_bool("estimated_basket_cost" in recommendation),
        "budget_friendly_preference": _safe_bool(preferences.get("budget_friendly")),
        "low_prep_preference": _safe_bool(preferences.get("low_prep")),
        "vegetarian_preference": _safe_bool(preferences.get("vegetarian")),
        "vegan_preference": _safe_bool(preferences.get("vegan")),
        "dairy_free_preference": _safe_bool(preferences.get("dairy_free")),
        "materially_different_from_best_heuristic": 0,
        "nutritionally_competitive_with_best_heuristic": 1,
        "cost_competitive_with_best_heuristic": 1,
        "diversity_improved_vs_best_heuristic": 0,
        "goal_profile": str(recommendation.get("goal_profile") or request_context.get("goal_profile") or "generic_balanced"),
        "shopping_mode": str(recommendation.get("shopping_mode") or request_context.get("shopping_mode") or "balanced"),
        "meal_style": str(preferences.get("meal_style") or "any"),
    }
    return features


def _goal_structure_label_adjustment(feature_row: Mapping[str, object]) -> float:
    goal_profile = str(feature_row.get("goal_profile") or "generic_balanced")
    alignment = _safe_float(feature_row.get("goal_structure_alignment_score"))
    role_gap = _safe_float(feature_row.get("role_share_gap_total"))
    booster_share = _safe_float(feature_row.get("calorie_booster_share"))
    produce_share = _safe_float(feature_row.get("produce_share"))
    score = (0.34 * alignment) - (0.2 * role_gap)
    score += 0.03 * _safe_float(feature_row.get("protein_anchor_family_diversity"))

    if goal_profile == "muscle_gain":
        if _safe_float(feature_row.get("lean_protein_anchor_count")) >= 1 and _safe_float(feature_row.get("dairy_or_egg_anchor_count")) >= 1:
            score += 0.12
        score += 0.05 * min(_safe_float(feature_row.get("fruit_produce_count")), 1.0)
        score += 0.24 * max(0.0, booster_share - 0.08)
        if _safe_float(feature_row.get("calorie_booster_count")) == 0:
            score -= 0.08
    elif goal_profile == "fat_loss":
        score += 0.06 * min(_safe_float(feature_row.get("high_volume_produce_count")), 3.0)
        score -= 0.18 * _safe_float(feature_row.get("calorie_booster_count"))
        score -= 0.07 * max(_safe_float(feature_row.get("fruit_produce_count")) - 1.0, 0.0)
        if produce_share >= 0.22:
            score += 0.08
    elif goal_profile == "maintenance":
        if 0.04 <= booster_share <= 0.16:
            score += 0.06
        score += 0.04 * min(_safe_float(feature_row.get("fruit_produce_count")), 1.0)
    elif goal_profile == "high_protein_vegetarian":
        score += 0.1 * min(_safe_float(feature_row.get("soy_protein_anchor_count")), _safe_float(feature_row.get("dairy_or_egg_anchor_count")), 1.0)
        score -= 0.18 * _safe_float(feature_row.get("animal_protein_anchor_count"))
        score -= 0.06 * _safe_float(feature_row.get("legume_protein_anchor_count"))
    elif goal_profile == "budget_friendly_healthy":
        score += 0.08 * min(_safe_float(feature_row.get("budget_support_anchor_count")), 1.0)
        score += 0.06 * min(_safe_float(feature_row.get("low_cost_produce_count")), 2.0)
        score -= 0.1 * max(_safe_float(feature_row.get("legume_protein_anchor_count")) - 1.0, 0.0)
        if _safe_float(feature_row.get("estimated_fat_g")) < max(_safe_float(feature_row.get("target_calorie_kcal")) * 0.02, 35.0):
            score -= 0.08
    return round(score, 6)


def heuristic_candidate_label(feature_row: Mapping[str, object]) -> float:
    profile = _goal_tradeoff_profile(feature_row)
    score = 0.0
    score += 4.0 * max(0.0, 1.0 - (_safe_float(feature_row.get("protein_gap_ratio")) * profile["protein_gap_scale"]))
    score += 3.4 * max(0.0, 1.0 - (_safe_float(feature_row.get("calorie_gap_ratio")) * profile["calorie_gap_scale"]))
    score += 1.8 * max(0.0, 1.0 - ((_safe_float(feature_row.get("macro_gap_ratio_sum")) * profile["macro_gap_scale"]) / 6.0))
    score += 0.3 * _safe_float(feature_row.get("unique_ingredient_count"))
    score += 0.25 * _safe_float(feature_row.get("food_family_diversity_count")) * profile["diversity_reward_scale"]
    score += 0.18 * _safe_float(feature_row.get("preference_match_score")) * profile["preference_reward_scale"]
    score += 0.02 * _safe_float(feature_row.get("heuristic_selection_score"))
    score += _goal_structure_label_adjustment(feature_row)
    score -= 0.38 * _safe_float(feature_row.get("repetition_penalty")) * profile["repetition_penalty_scale"]
    score -= 0.65 * _safe_float(feature_row.get("unrealistic_basket_penalty"))
    score -= 0.15 * _safe_float(feature_row.get("warning_count"))

    estimated_cost = _safe_float(feature_row.get("estimated_basket_cost"))
    if estimated_cost > 0:
        score -= 0.05 * estimated_cost * profile["cost_penalty_scale"]
        score -= 0.03 * _safe_float(feature_row.get("price_per_1000_kcal")) * profile["price_penalty_scale"]
        score -= 0.025 * _safe_float(feature_row.get("price_per_100g_protein")) * profile["price_penalty_scale"]
    if _safe_bool(feature_row.get("low_prep_preference")):
        score -= 0.12 * _safe_float(feature_row.get("unrealistic_basket_penalty"))
    return round(score, 6)


def alternative_quality_score(feature_row: Mapping[str, object]) -> float:
    if not _safe_bool(feature_row.get("materially_different_from_best_heuristic")):
        return 0.0

    profile = _goal_tradeoff_profile(feature_row)
    protein_delta = _safe_float(feature_row.get("protein_gap_delta_vs_best_heuristic"))
    calorie_delta = _safe_float(feature_row.get("calorie_gap_delta_vs_best_heuristic"))
    macro_delta = _safe_float(feature_row.get("macro_gap_ratio_delta_vs_best_heuristic"))
    cost_delta = _safe_float(feature_row.get("cost_delta_vs_best_heuristic"))
    diversity_gain = _safe_float(feature_row.get("diversity_gain_vs_best_heuristic"))
    role_diversity_delta = _safe_float(feature_row.get("role_diversity_delta_vs_best_heuristic"))
    repetition_delta = _safe_float(feature_row.get("repetition_penalty_delta_vs_best_heuristic"))
    unrealistic_delta = _safe_float(feature_row.get("unrealistic_penalty_delta_vs_best_heuristic"))
    preference_delta = _safe_float(feature_row.get("preference_match_delta_vs_best_heuristic"))

    protein_competitiveness = max(0.0, 1.0 - (max(protein_delta, 0.0) / max(profile["alternative_protein_tolerance_g"], 1.0)))
    calorie_competitiveness = max(0.0, 1.0 - (max(calorie_delta, 0.0) / max(profile["alternative_calorie_tolerance_kcal"], 1.0)))
    macro_competitiveness = max(0.0, 1.0 - (max(macro_delta, 0.0) / max(profile["alternative_macro_tolerance"], 0.01)))
    cost_competitiveness = 1.0 - min(max(cost_delta, 0.0) / max(profile["alternative_cost_tolerance"], 0.1), 1.5)
    diversity_bonus = (min(max(diversity_gain, 0.0), 2.0) * 0.16 * profile["diversity_reward_scale"]) + (
        min(max(role_diversity_delta, 0.0), 1.0) * 0.08
    )
    repetition_bonus = min(max(-repetition_delta, 0.0), 2.0) * 0.14 * profile["repetition_penalty_scale"]
    realism_bonus = min(max(-unrealistic_delta, 0.0), 1.0) * 0.1
    preference_bonus = max(preference_delta, 0.0) * 0.08 * profile["preference_reward_scale"]

    score = 0.18
    score += 0.42 * protein_competitiveness
    score += 0.34 * calorie_competitiveness
    score += 0.16 * macro_competitiveness
    score += 0.14 * cost_competitiveness
    score += diversity_bonus + repetition_bonus + realism_bonus + preference_bonus
    score -= max(0.0, cost_delta - profile["soft_cost_delta"]) * 0.12 * profile["cost_penalty_scale"]
    score -= max(0.0, protein_delta - profile["soft_protein_delta"]) * 0.02 * profile["protein_gap_scale"]
    score -= max(0.0, calorie_delta - profile["soft_calorie_delta"]) * 0.0015 * profile["calorie_gap_scale"]
    if not _safe_bool(feature_row.get("nutritionally_competitive_with_best_heuristic")):
        score -= 0.18
    if not _safe_bool(feature_row.get("cost_competitive_with_best_heuristic")):
        score -= 0.1 * profile["cost_penalty_scale"]
    return round(score, 6)


def training_candidate_label(feature_row: Mapping[str, object]) -> float:
    label = heuristic_candidate_label(feature_row)
    label += alternative_quality_score(feature_row)
    if _safe_bool(feature_row.get("materially_different_from_best_heuristic")):
        if _safe_bool(feature_row.get("nutritionally_competitive_with_best_heuristic")) and _safe_bool(
            feature_row.get("cost_competitive_with_best_heuristic")
        ):
            label += 0.14
        if _safe_bool(feature_row.get("diversity_improved_vs_best_heuristic")):
            label += 0.06
    return round(label, 6)


def enrich_request_feature_rows(
    candidates: Sequence[Mapping[str, object]],
    feature_rows: Sequence[dict[str, object]],
    *,
    best_heuristic_candidate: Mapping[str, object] | None = None,
) -> list[dict[str, object]]:
    if not candidates or not feature_rows:
        return [dict(feature_row) for feature_row in feature_rows]

    enriched_rows = [dict(feature_row) for feature_row in feature_rows]
    if best_heuristic_candidate is None:
        reference_index = _best_heuristic_reference_index(candidates, enriched_rows)
        best_heuristic_candidate = candidates[reference_index]
        best_heuristic_feature_row = enriched_rows[reference_index]
    else:
        try:
            reference_index = next(
                index for index, candidate in enumerate(candidates)
                if str(candidate.get("candidate_id") or "") == str(best_heuristic_candidate.get("candidate_id") or "")
            )
        except StopIteration:
            best_heuristic_feature_row = extract_candidate_features(best_heuristic_candidate)
        else:
            best_heuristic_feature_row = enriched_rows[reference_index]

    profile = _goal_tradeoff_profile(best_heuristic_feature_row)
    for candidate, feature_row in zip(candidates, enriched_rows, strict=True):
        similarity = candidate_debug.compare_candidates(best_heuristic_candidate, candidate)
        feature_row["overlap_with_best_heuristic_jaccard"] = round(float(similarity["jaccard_overlap"]), 6)
        feature_row["changed_food_count_vs_best_heuristic"] = int(similarity["changed_food_count"])
        feature_row["role_assignment_changes_vs_best_heuristic"] = int(similarity["role_assignment_changes"])
        feature_row["cost_delta_vs_best_heuristic"] = round(
            _safe_float(feature_row.get("estimated_basket_cost")) - _safe_float(best_heuristic_feature_row.get("estimated_basket_cost")),
            6,
        )
        feature_row["protein_gap_delta_vs_best_heuristic"] = round(
            _safe_float(feature_row.get("protein_abs_gap_g")) - _safe_float(best_heuristic_feature_row.get("protein_abs_gap_g")),
            6,
        )
        feature_row["calorie_gap_delta_vs_best_heuristic"] = round(
            _safe_float(feature_row.get("calorie_abs_gap_kcal")) - _safe_float(best_heuristic_feature_row.get("calorie_abs_gap_kcal")),
            6,
        )
        feature_row["macro_gap_ratio_delta_vs_best_heuristic"] = round(
            _safe_float(feature_row.get("macro_gap_ratio_sum")) - _safe_float(best_heuristic_feature_row.get("macro_gap_ratio_sum")),
            6,
        )
        feature_row["diversity_gain_vs_best_heuristic"] = round(
            _safe_float(feature_row.get("food_family_diversity_count")) - _safe_float(best_heuristic_feature_row.get("food_family_diversity_count")),
            6,
        )
        feature_row["role_diversity_delta_vs_best_heuristic"] = round(
            _safe_float(feature_row.get("role_diversity_count")) - _safe_float(best_heuristic_feature_row.get("role_diversity_count")),
            6,
        )
        feature_row["repetition_penalty_delta_vs_best_heuristic"] = round(
            _safe_float(feature_row.get("repetition_penalty")) - _safe_float(best_heuristic_feature_row.get("repetition_penalty")),
            6,
        )
        feature_row["unrealistic_penalty_delta_vs_best_heuristic"] = round(
            _safe_float(feature_row.get("unrealistic_basket_penalty")) - _safe_float(best_heuristic_feature_row.get("unrealistic_basket_penalty")),
            6,
        )
        feature_row["preference_match_delta_vs_best_heuristic"] = round(
            _safe_float(feature_row.get("preference_match_score")) - _safe_float(best_heuristic_feature_row.get("preference_match_score")),
            6,
        )
        materially_different = int(bool(similarity["materially_different"]))
        feature_row["materially_different_from_best_heuristic"] = materially_different
        feature_row["nutritionally_competitive_with_best_heuristic"] = int(
            _safe_float(feature_row["protein_gap_delta_vs_best_heuristic"]) <= profile["alternative_protein_tolerance_g"]
            and _safe_float(feature_row["calorie_gap_delta_vs_best_heuristic"]) <= profile["alternative_calorie_tolerance_kcal"]
            and _safe_float(feature_row["macro_gap_ratio_delta_vs_best_heuristic"]) <= profile["alternative_macro_tolerance"]
        )
        feature_row["cost_competitive_with_best_heuristic"] = int(
            _safe_float(feature_row["cost_delta_vs_best_heuristic"]) <= profile["alternative_cost_tolerance"]
        )
        feature_row["diversity_improved_vs_best_heuristic"] = int(
            _safe_float(feature_row["diversity_gain_vs_best_heuristic"]) > 0
            or _safe_float(feature_row["role_diversity_delta_vs_best_heuristic"]) > 0
            or _safe_float(feature_row["repetition_penalty_delta_vs_best_heuristic"]) < 0
        )
        feature_row["alternative_quality_score"] = alternative_quality_score(feature_row)
    return enriched_rows


def build_request_feature_rows(
    candidates: Sequence[Mapping[str, object]],
    *,
    best_heuristic_candidate: Mapping[str, object] | None = None,
) -> list[dict[str, object]]:
    base_rows = [extract_candidate_features(candidate) for candidate in candidates]
    return enrich_request_feature_rows(
        candidates,
        base_rows,
        best_heuristic_candidate=best_heuristic_candidate,
    )


def available_backends() -> list[str]:
    backends: list[str] = []
    try:
        import xgboost  # noqa: F401
    except Exception:  # noqa: BLE001
        pass
    else:
        backends.append("xgboost")

    try:
        import lightgbm  # noqa: F401
    except Exception:  # noqa: BLE001
        pass
    else:
        backends.append("lightgbm")

    backends.extend(["sklearn_gradient_boosting", "sklearn_random_forest", "sklearn_ridge"])
    return backends


def resolve_backend(requested: str = "auto") -> str:
    ordered = available_backends()
    if requested == "auto":
        return ordered[0]
    if requested not in ordered:
        raise ValueError(f"Unsupported scorer backend: {requested}")
    return requested


def _make_pipeline(
    *,
    backend: str,
    learning_rate: float,
    max_depth: int,
    n_estimators: int,
    random_seed: int,
) -> Pipeline:
    backend = resolve_backend(backend)
    if backend == "xgboost":
        from xgboost import XGBRegressor

        regressor = XGBRegressor(
            learning_rate=learning_rate,
            max_depth=max_depth,
            n_estimators=n_estimators,
            random_state=random_seed,
            objective="reg:squarederror",
            verbosity=0,
        )
    elif backend == "lightgbm":
        from lightgbm import LGBMRegressor

        regressor = LGBMRegressor(
            learning_rate=learning_rate,
            max_depth=max_depth,
            n_estimators=n_estimators,
            random_state=random_seed,
            verbose=-1,
        )
    elif backend == "sklearn_gradient_boosting":
        regressor = GradientBoostingRegressor(
            learning_rate=learning_rate,
            max_depth=max_depth,
            n_estimators=n_estimators,
            random_state=random_seed,
        )
    elif backend == "sklearn_random_forest":
        regressor = RandomForestRegressor(
            max_depth=max_depth,
            n_estimators=n_estimators,
            random_state=random_seed,
            n_jobs=-1,
        )
    else:
        regressor = Ridge(alpha=max(learning_rate, 0.001), random_state=random_seed)

    return Pipeline(
        [
            ("vectorizer", DictVectorizer(sparse=False)),
            ("regressor", regressor),
        ]
    )


def _group_top1_accuracy(groups: Sequence[str], y_true: Sequence[float], y_pred: Sequence[float]) -> float:
    grouped_true: dict[str, list[tuple[float, int]]] = defaultdict(list)
    grouped_pred: dict[str, list[tuple[float, int]]] = defaultdict(list)
    for index, (group_id, truth, pred) in enumerate(zip(groups, y_true, y_pred, strict=True)):
        grouped_true[group_id].append((truth, index))
        grouped_pred[group_id].append((pred, index))
    if not grouped_true:
        return 0.0

    correct = 0
    for group_id, truth_rows in grouped_true.items():
        true_best_index = sorted(truth_rows, key=lambda row: (-row[0], row[1]))[0][1]
        pred_best_index = sorted(grouped_pred[group_id], key=lambda row: (-row[0], row[1]))[0][1]
        correct += int(true_best_index == pred_best_index)
    return correct / len(grouped_true)


def _pairwise_accuracy(groups: Sequence[str], y_true: Sequence[float], y_pred: Sequence[float]) -> float:
    grouped_indices: dict[str, list[int]] = defaultdict(list)
    for index, group_id in enumerate(groups):
        grouped_indices[group_id].append(index)

    correct = 0
    total = 0
    for indices in grouped_indices.values():
        for left in range(len(indices)):
            for right in range(left + 1, len(indices)):
                left_index = indices[left]
                right_index = indices[right]
                truth_delta = y_true[left_index] - y_true[right_index]
                if abs(truth_delta) < 1e-9:
                    continue
                pred_delta = y_pred[left_index] - y_pred[right_index]
                total += 1
                correct += int((truth_delta > 0 and pred_delta > 0) or (truth_delta < 0 and pred_delta < 0))
    if total == 0:
        return 0.0
    return correct / total


def train_model(
    rows: Sequence[Mapping[str, object]],
    *,
    backend: str = "auto",
    learning_rate: float = 0.05,
    max_depth: int = 3,
    n_estimators: int = 250,
    validation_split: float = 0.25,
    random_seed: int = DEFAULT_RANDOM_SEED,
) -> tuple[dict[str, object], dict[str, object]]:
    if not rows:
        raise ValueError("Training rows are required.")
    if not 0 < validation_split < 1:
        raise ValueError("validation_split must be between 0 and 1.")

    X = [{field: row[field] for field in (*NUMERIC_FEATURES, *BOOLEAN_FEATURES, *CATEGORICAL_FEATURES)} for row in rows]
    y = [_safe_float(row["label_score"]) for row in rows]
    groups = [str(row["request_id"]) for row in rows]

    splitter = GroupShuffleSplit(n_splits=1, test_size=validation_split, random_state=random_seed)
    train_indices, valid_indices = next(splitter.split(X, y, groups))
    X_train = [X[index] for index in train_indices]
    y_train = [y[index] for index in train_indices]
    X_valid = [X[index] for index in valid_indices]
    y_valid = [y[index] for index in valid_indices]
    groups_valid = [groups[index] for index in valid_indices]

    resolved_backend = resolve_backend(backend)
    pipeline = _make_pipeline(
        backend=resolved_backend,
        learning_rate=learning_rate,
        max_depth=max_depth,
        n_estimators=n_estimators,
        random_seed=random_seed,
    )
    pipeline.fit(X_train, y_train)
    validation_predictions = list(pipeline.predict(X_valid))

    metrics = {
        "backend": resolved_backend,
        "learning_rate": learning_rate,
        "max_depth": max_depth,
        "n_estimators": n_estimators,
        "random_seed": random_seed,
        "validation_split": validation_split,
        "row_count": len(rows),
        "request_count": len(set(groups)),
        "train_row_count": len(X_train),
        "validation_row_count": len(X_valid),
        "materially_different_row_count": sum(_safe_bool(row.get("materially_different_from_best_heuristic")) for row in rows),
        "model_candidate_row_count": sum(1 for row in rows if str(row.get("candidate_source") or "") in {"model", "repaired_model", "hybrid"}),
        "label_strategy": "fair_alternative_v1",
        "validation_mae": round(float(mean_absolute_error(y_valid, validation_predictions)), 6),
        "validation_rmse": round(float(mean_squared_error(y_valid, validation_predictions) ** 0.5), 6),
        "validation_r2": round(float(r2_score(y_valid, validation_predictions)), 6),
        "validation_top1_accuracy": round(float(_group_top1_accuracy(groups_valid, y_valid, validation_predictions)), 6),
        "validation_pairwise_accuracy": round(float(_pairwise_accuracy(groups_valid, y_valid, validation_predictions)), 6),
    }

    final_pipeline = _make_pipeline(
        backend=resolved_backend,
        learning_rate=learning_rate,
        max_depth=max_depth,
        n_estimators=n_estimators,
        random_seed=random_seed,
    )
    final_pipeline.fit(X, y)

    bundle = {
        "pipeline": final_pipeline,
        "backend": resolved_backend,
        "feature_fields": {
            "numeric": list(NUMERIC_FEATURES),
            "boolean": list(BOOLEAN_FEATURES),
            "categorical": list(CATEGORICAL_FEATURES),
        },
        "training_metadata_fields": list(TRAINING_METADATA_FIELDS),
        "metrics": metrics,
        "created_at": datetime.now(UTC).isoformat(),
        "label_strategy": "fair_alternative_v1",
    }
    return bundle, metrics


def score_feature_rows(bundle: Mapping[str, object], rows: Sequence[Mapping[str, object]]) -> list[float]:
    pipeline = bundle.get("pipeline")
    if pipeline is None:
        raise PlanScorerArtifactError("Loaded trained plan scorer artifact is invalid: missing fitted pipeline.")
    X = [{field: row[field] for field in (*NUMERIC_FEATURES, *BOOLEAN_FEATURES, *CATEGORICAL_FEATURES)} for row in rows]
    try:
        return [float(score) for score in pipeline.predict(X)]
    except Exception as exc:  # noqa: BLE001
        raise PlanScorerArtifactError(f"Loaded trained plan scorer artifact could not score candidate plans: {exc}") from exc


def save_bundle(bundle: Mapping[str, object], output_path: str | Path) -> Path:
    resolved = Path(output_path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    dump(dict(bundle), resolved)
    return resolved


@lru_cache(maxsize=8)
def _load_bundle_cached(resolved_model_path_str: str) -> dict[str, object]:
    resolved_model_path = Path(resolved_model_path_str)
    try:
        bundle = dict(load(resolved_model_path))
    except FileNotFoundError as exc:
        raise PlanScorerArtifactError(
            f"Required trained plan scorer artifact is missing: {resolved_model_path}"
        ) from exc
    except Exception as exc:  # noqa: BLE001
        raise PlanScorerArtifactError(
            f"Required trained plan scorer artifact could not be loaded from {resolved_model_path}: {exc}"
        ) from exc

    if bundle.get("pipeline") is None:
        raise PlanScorerArtifactError(
            f"Loaded trained plan scorer artifact is invalid: {resolved_model_path} does not contain a fitted pipeline."
        )
    return bundle


def load_bundle(model_path: str | Path) -> dict[str, object]:
    resolved_model_path = str(Path(model_path).resolve())
    return dict(_load_bundle_cached(resolved_model_path))


def feature_summary_rows(bundle: Mapping[str, object]) -> list[dict[str, object]]:
    pipeline = bundle.get("pipeline")
    if pipeline is None:
        return []
    vectorizer = pipeline.named_steps["vectorizer"]
    regressor = pipeline.named_steps["regressor"]
    feature_names = vectorizer.get_feature_names_out()

    rows: list[dict[str, object]] = []
    if hasattr(regressor, "feature_importances_"):
        importances = list(regressor.feature_importances_)
        ranked = sorted(zip(feature_names, importances, strict=True), key=lambda row: row[1], reverse=True)
        rows.extend({"feature_name": str(name), "importance": round(float(value), 6)} for name, value in ranked)
    elif hasattr(regressor, "coef_"):
        coefficients = getattr(regressor, "coef_")
        flattened = coefficients.tolist() if hasattr(coefficients, "tolist") else list(coefficients)
        ranked = sorted(zip(feature_names, flattened, strict=True), key=lambda row: abs(float(row[1])), reverse=True)
        rows.extend({"feature_name": str(name), "coefficient": round(float(value), 6)} for name, value in ranked)
    return rows
