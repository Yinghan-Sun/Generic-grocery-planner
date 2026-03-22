"""Model-ranked candidate generation and trained-scorer integration."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

import duckdb

from dietdashboard import generic_recommender as gr
from dietdashboard import plan_scorer

DEFAULT_CANDIDATE_COUNT = 6
MAX_CANDIDATE_COUNT = 12


@dataclass(frozen=True)
class PlannerContext:
    protein_target_g: float
    calorie_target_kcal: float
    preferences: dict[str, object]
    nutrition_targets: dict[str, float]
    pantry_items: set[str]
    days: int
    shopping_mode: str
    price_context: dict[str, str]
    available: dict[str, dict[str, object]]
    goal_profile: str
    basket_policy: dict[str, object]
    role_scores: dict[str, dict[str, float]]
    role_orders: dict[str, list[str]]


@dataclass
class CandidateSeed:
    chosen: list[tuple[str, str]]
    excluded: set[str]
    selection_trace: list[dict[str, object]]
    heuristic_selection_score: float


def normalize_scorer_config(config: dict[str, object] | None) -> dict[str, object]:
    raw = dict(config or {})
    candidate_count = raw.get("candidate_count", DEFAULT_CANDIDATE_COUNT)
    try:
        candidate_count_value = int(candidate_count)
    except (TypeError, ValueError):
        candidate_count_value = DEFAULT_CANDIDATE_COUNT
    candidate_count_value = max(1, min(MAX_CANDIDATE_COUNT, candidate_count_value))
    model_path = raw.get("scorer_model_path") or plan_scorer.default_model_path()
    return {
        "candidate_count": candidate_count_value,
        "scorer_model_path": str(model_path),
        "debug": bool(raw.get("debug")),
    }


def _prepare_context(
    con: duckdb.DuckDBPyConnection,
    *,
    protein_target_g: float,
    calorie_target_kcal: float,
    preferences: dict[str, object] | None,
    nutrition_targets: dict[str, float] | None,
    pantry_items: Iterable[str] | None,
    days: int,
    shopping_mode: str,
    price_context: dict[str, str] | None,
) -> PlannerContext:
    normalized_preferences = gr._effective_preferences(preferences or {})  # noqa: SLF001
    normalized_targets = {
        key: float(value)
        for key, value in (nutrition_targets or {}).items()
        if value is not None and float(value) > 0
    }
    normalized_pantry_items = {str(food_id).strip() for food_id in (pantry_items or []) if str(food_id).strip()}
    normalized_days = max(1, int(days))
    normalized_shopping_mode = str(shopping_mode or "balanced").strip().lower()
    if normalized_shopping_mode not in gr.SHOPPING_MODE_OPTIONS:
        normalized_shopping_mode = "balanced"
    resolved_price_context = price_context or {
        "usda_area_code": "US",
        "usda_area_name": gr.USDA_AREA_NAMES["US"],
        "bls_area_code": "0",
        "bls_area_name": gr.BLS_AREA_NAMES["0"],
    }
    usda_area_code = str(resolved_price_context.get("usda_area_code") or "US")
    bls_area_code = str(resolved_price_context.get("bls_area_code") or "0")

    available = gr._load_candidates(  # noqa: SLF001
        con,
        vegetarian=bool(normalized_preferences["vegetarian"]),
        dairy_free=bool(normalized_preferences["dairy_free"]),
        vegan=bool(normalized_preferences["vegan"]),
        price_area_code=bls_area_code,
        usda_area_code=usda_area_code,
    )
    if not available:
        raise ValueError("No generic foods are available for the selected preferences.")

    goal_profile = gr._detect_goal_profile(  # noqa: SLF001
        protein_target_g,
        calorie_target_kcal,
        normalized_preferences,
        normalized_targets,
    )
    basket_policy = gr._goal_basket_policy(  # noqa: SLF001
        goal_profile,
        protein_target_g,
        calorie_target_kcal,
        normalized_targets,
    )
    role_scores = {
        "protein_anchor": gr._build_role_scores(available, "protein_anchor", normalized_preferences, normalized_targets, goal_profile),  # noqa: SLF001
        "carb_base": gr._build_role_scores(available, "carb_base", normalized_preferences, normalized_targets, goal_profile),  # noqa: SLF001
        "produce": gr._build_role_scores(available, "produce", normalized_preferences, normalized_targets, goal_profile),  # noqa: SLF001
        "calorie_booster": gr._build_role_scores(available, "calorie_booster", normalized_preferences, normalized_targets, goal_profile),  # noqa: SLF001
    }
    role_orders = {
        "protein_anchor": gr._build_role_order(available, "protein_anchor", normalized_preferences, normalized_targets, goal_profile),  # noqa: SLF001
        "carb_base": gr._build_role_order(available, "carb_base", normalized_preferences, normalized_targets, goal_profile),  # noqa: SLF001
        "produce": gr._build_role_order(available, "produce", normalized_preferences, normalized_targets, goal_profile),  # noqa: SLF001
        "calorie_booster": gr._build_role_order(available, "calorie_booster", normalized_preferences, normalized_targets, goal_profile),  # noqa: SLF001
    }
    return PlannerContext(
        protein_target_g=protein_target_g,
        calorie_target_kcal=calorie_target_kcal,
        preferences=normalized_preferences,
        nutrition_targets=normalized_targets,
        pantry_items=normalized_pantry_items,
        days=normalized_days,
        shopping_mode=normalized_shopping_mode,
        price_context=resolved_price_context,
        available=available,
        goal_profile=goal_profile,
        basket_policy=basket_policy,
        role_scores=role_scores,
        role_orders=role_orders,
    )


def _selection_score_for_food(
    context: PlannerContext,
    *,
    role: str,
    food_id: str,
    chosen: list[tuple[str, str]],
) -> float:
    base_score = context.role_scores[role][food_id]
    diversity_penalty = gr._role_diversity_penalty(food_id, role, context.available, chosen)  # noqa: SLF001
    return base_score - diversity_penalty


def _rank_diverse_candidates(
    context: PlannerContext,
    *,
    role: str,
    excluded: set[str],
    chosen: list[tuple[str, str]],
) -> list[str]:
    role_scores = context.role_scores[role]
    available = context.available
    preferences = context.preferences
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
        return []

    best_score = role_scores[candidates[0]]
    candidate_window = gr._diversity_window(role, preferences)  # noqa: SLF001
    short_list = [food_id for food_id in candidates if best_score - role_scores[food_id] <= candidate_window]
    if not short_list:
        short_list = [candidates[0]]

    preferred_ids = gr._goal_template_ids_for_pick(context.goal_profile, role, chosen, available)  # noqa: SLF001
    preferred_rank = {food_id: index for index, food_id in enumerate(preferred_ids)}
    use_goal_template = False
    if preferred_rank:
        template_window = candidate_window + gr._goal_template_slack(context.goal_profile, role)  # noqa: SLF001
        template_candidates = [
            food_id
            for food_id in candidates
            if food_id in preferred_rank and best_score - role_scores[food_id] <= template_window
        ]
        if template_candidates:
            short_list = template_candidates
            use_goal_template = True

    ranked: list[tuple[object, ...]] = []
    for food_id in short_list:
        adjusted_score = _selection_score_for_food(context, role=role, food_id=food_id, chosen=chosen)
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
    return [str(row[-1]) for row in ranked]


def _candidate_role_sequence(context: PlannerContext) -> list[str]:
    sequence = ["protein_anchor"] * int(context.basket_policy["desired_protein_anchors"])
    sequence.append("carb_base")
    sequence.extend(["produce"] * int(context.basket_policy["desired_produce_items"]))
    return sequence


def _seed_sort_key(seed: CandidateSeed) -> tuple[float, tuple[str, ...]]:
    return (
        -seed.heuristic_selection_score,
        tuple(food_id for food_id, _role in seed.chosen),
    )


def _generate_candidate_seeds(context: PlannerContext, candidate_count: int) -> list[CandidateSeed]:
    beam_width = max(candidate_count * 4, 8)
    branch_limits = {
        "protein_anchor": 3,
        "carb_base": 3,
        "produce": 4,
    }
    seeds = [CandidateSeed(chosen=[], excluded=set(), selection_trace=[], heuristic_selection_score=0.0)]
    for step_index, role in enumerate(_candidate_role_sequence(context)):
        expanded: list[CandidateSeed] = []
        for seed in seeds:
            ranked = _rank_diverse_candidates(context, role=role, excluded=seed.excluded, chosen=seed.chosen)
            if not ranked:
                expanded.append(
                    CandidateSeed(
                        chosen=list(seed.chosen),
                        excluded=set(seed.excluded),
                        selection_trace=list(seed.selection_trace),
                        heuristic_selection_score=seed.heuristic_selection_score,
                    )
                )
                continue
            for choice_index, food_id in enumerate(ranked[: branch_limits[role]]):
                adjusted_score = _selection_score_for_food(context, role=role, food_id=food_id, chosen=seed.chosen)
                expanded.append(
                    CandidateSeed(
                        chosen=[*seed.chosen, (food_id, role)],
                        excluded={*seed.excluded, food_id},
                        selection_trace=[
                            *seed.selection_trace,
                            {
                                "step_index": step_index,
                                "role": role,
                                "food_id": food_id,
                                "display_name": str(context.available[food_id]["display_name"]),
                                "choice_rank": choice_index,
                                "selection_score": round(adjusted_score, 6),
                            },
                        ],
                        heuristic_selection_score=seed.heuristic_selection_score + adjusted_score,
                    )
                )

        deduped: dict[tuple[str, ...], CandidateSeed] = {}
        for seed in sorted(expanded, key=_seed_sort_key):
            key = tuple(food_id for food_id, _role in seed.chosen)
            if key not in deduped:
                deduped[key] = seed
        seeds = list(deduped.values())[:beam_width]

    return [seed for seed in seeds if seed.chosen][:candidate_count]


def _candidate_preference_match_score(context: PlannerContext, chosen: list[tuple[str, str]]) -> float:
    if not chosen:
        return 0.0

    total = 0.0
    meal_style = str(context.preferences.get("meal_style") or "any")
    desired_tags = gr.MEAL_STYLE_TAGS.get(meal_style, set())  # noqa: SLF001
    for food_id, role in chosen:
        food = context.available[food_id]
        prep_score = float(gr.PREP_LEVEL_SCORES.get(str(food.get("prep_level") or ""), 0.0))  # noqa: SLF001
        tags = gr._meal_tags(food)  # noqa: SLF001
        if context.preferences.get("budget_friendly"):
            total += float(food.get("budget_score") or 0.0)
        if context.preferences.get("low_prep"):
            total += prep_score
        if desired_tags and tags & desired_tags:
            total += 1.5
        if role == "produce" and context.preferences.get("low_prep") and gr._metadata_bool(food, "microwave_friendly"):  # noqa: SLF001
            total += 0.5
    return round(total / max(len(chosen), 1), 6)


def _candidate_repetition_penalty(context: PlannerContext, chosen: list[tuple[str, str]]) -> float:
    penalty = 0.0
    for index, (food_id, role) in enumerate(chosen):
        for other_food_id, other_role in chosen[index + 1 :]:
            if role == other_role:
                penalty += gr._similarity_penalty(context.available[food_id], context.available[other_food_id], role)  # noqa: SLF001
            else:
                if str(context.available[food_id]["food_family"]) == str(context.available[other_food_id]["food_family"]):
                    penalty += 0.2
    return round(penalty, 6)


def _candidate_unrealistic_penalty(
    context: PlannerContext,
    chosen: list[tuple[str, str]],
    plan_quantities: dict[str, float],
    response: dict[str, object],
) -> float:
    penalty = 0.0
    if len(chosen) <= 3:
        penalty += 0.8
    if context.days >= 5:
        perishable_count = sum(1 for food_id, _role in chosen if gr._is_perishable(context.available[food_id]))  # noqa: SLF001
        if perishable_count >= 3:
            penalty += 0.6
    for food_id, quantity_g in plan_quantities.items():
        food = context.available[food_id]
        default_serving_g = max(float(food.get("default_serving_g") or 0.0), 1.0)
        if quantity_g > default_serving_g * 8:
            penalty += 0.35
        if not gr._is_shelf_stable(food) and context.days >= 5 and quantity_g > default_serving_g * 5:  # noqa: SLF001
            penalty += 0.25
    penalty += 0.12 * len(response.get("warnings") or [])
    return round(penalty, 6)


def _candidate_role_counts(chosen: list[tuple[str, str]]) -> dict[str, int]:
    counts = Counter(role for _food_id, role in chosen)
    return {role: int(counts.get(role, 0)) for role in ("protein_anchor", "carb_base", "produce", "calorie_booster")}


def _candidate_bundle_from_response(
    context: PlannerContext,
    *,
    response: dict[str, object],
    candidate_id: str,
    selection_trace: list[dict[str, object]],
    heuristic_selection_score: float,
    stores: Sequence[dict[str, object]] | None,
) -> dict[str, object]:
    shopping_list = response.get("shopping_list") if isinstance(response.get("shopping_list"), Sequence) else []
    chosen = [
        (str(item["generic_food_id"]), str(item["role"]))
        for item in shopping_list
        if str(item.get("generic_food_id") or "") in context.available
    ]
    plan_quantities = {
        str(item["generic_food_id"]): float(item["quantity_g"])
        for item in shopping_list
        if str(item.get("generic_food_id") or "") in context.available
    }
    role_counts = _candidate_role_counts(chosen)
    shopping_ids = [str(item["generic_food_id"]) for item in shopping_list]
    shopping_food_ids = {food_id for food_id in shopping_ids if food_id in context.available}
    family_diversity = len({str(context.available[food_id]["food_family"]) for food_id in shopping_food_ids})
    metadata = {
        "candidate_id": candidate_id,
        "chosen_food_ids": [food_id for food_id, _role in chosen],
        "shopping_food_ids": shopping_ids,
        "selection_trace": list(selection_trace),
        "heuristic_selection_score": round(float(heuristic_selection_score), 6),
        "role_counts": role_counts,
        "food_family_diversity_count": family_diversity,
        "role_diversity_count": sum(1 for count in role_counts.values() if count > 0),
        "repetition_penalty": _candidate_repetition_penalty(context, chosen),
        "preference_match_score": _candidate_preference_match_score(context, chosen),
        "unrealistic_basket_penalty": _candidate_unrealistic_penalty(context, chosen, plan_quantities, response),
        "nearby_store_count": len(stores or []),
    }
    return {
        "candidate_id": metadata["candidate_id"],
        "recommendation": response,
        "candidate_metadata": metadata,
        "request_context": {
            "goal_profile": context.goal_profile,
            "shopping_mode": context.shopping_mode,
            "days": context.days,
            "preferences": dict(context.preferences),
        },
    }


def _materialize_candidate(
    context: PlannerContext,
    seed: CandidateSeed,
    *,
    candidate_index: int,
    stores: Sequence[dict[str, object]] | None,
) -> dict[str, object]:
    available = context.available
    chosen = list(seed.chosen)
    excluded = {food_id for food_id, _role in chosen}
    if not chosen:
        raise ValueError("No generic foods could be selected for the recommendation.")

    quantities: dict[str, float] = {}
    protein_anchors = [food_id for food_id, role in chosen if role == "protein_anchor"]
    carb_base = next((food_id for food_id, role in chosen if role == "carb_base"), None)
    low_prep = bool(context.preferences["low_prep"])

    primary_protein_share, secondary_protein_share = context.basket_policy["protein_anchor_shares"]
    for index, food_id in enumerate(protein_anchors):
        food = available[food_id]
        if len(protein_anchors) == 1:
            protein_share = context.protein_target_g * 0.45
        else:
            protein_share = context.protein_target_g * (primary_protein_share if index == 0 else secondary_protein_share)
        grams = max(float(food["default_serving_g"]), 100.0 * protein_share / max(float(food["protein"]), 1.0))
        quantities[food_id] = grams

    if carb_base is not None:
        food = available[carb_base]
        carb_share = float(context.basket_policy["carb_share"])
        grams = max(
            float(food["default_serving_g"]),
            100.0 * (context.calorie_target_kcal * carb_share) / max(float(food["energy_fibre_kcal"]), 1.0),
        )
        carbohydrate_target_g = context.nutrition_targets.get("carbohydrate")
        if carbohydrate_target_g:
            grams = max(grams, 100.0 * (carbohydrate_target_g * 0.55) / max(float(food["carbohydrate"]), 1.0))
        fiber_target_g = context.nutrition_targets.get("fiber")
        if fiber_target_g:
            carb_fiber = float(food.get("fiber") or 0.0)
            fiber_ratio = float(context.basket_policy["carb_fiber_ratio"])
            if carb_fiber >= 5.0:
                grams = max(grams, 100.0 * (fiber_target_g * fiber_ratio) / max(carb_fiber, 0.5))
            elif carb_fiber >= 3.0:
                grams = max(grams, 100.0 * (fiber_target_g * min(fiber_ratio, 0.18)) / max(carb_fiber, 0.5))
        quantities[carb_base] = grams

    for food_id, role in chosen:
        if role != "produce":
            continue
        food = available[food_id]
        servings = 1 if context.calorie_target_kcal < 1800 else 2
        if low_prep and str(food["generic_food_id"]) == "spinach":
            servings = 1
        if context.goal_profile == "fat_loss":
            servings += 1
        elif context.goal_profile == "muscle_gain" and gr._produce_cluster(food) == "fruit":  # noqa: SLF001
            servings += 1
        if context.nutrition_targets.get("fiber"):
            servings += 1
        if context.nutrition_targets.get("vitamin_c") and float(food["vitamin_c"]) >= 20:
            servings += 1
        quantities[food_id] = max(float(food["default_serving_g"]), float(food["default_serving_g"]) * servings)

    def totals() -> dict[str, float]:
        total = {key: 0.0 for key in gr.NUTRIENT_SUMMARY_META}  # noqa: SLF001
        for food_id, quantity_g in quantities.items():
            for nutrient_id, value in gr._tracked_totals(available[food_id], quantity_g).items():  # noqa: SLF001
                total[nutrient_id] += value
        return total

    total_nutrients = totals()
    protein_deficit = max(0.0, context.protein_target_g - total_nutrients["protein"])
    if protein_deficit > 0 and protein_anchors:
        first_anchor = protein_anchors[0]
        quantities[first_anchor] += 100.0 * protein_deficit * 0.7 / max(float(available[first_anchor]["protein"]), 1.0)
        if len(protein_anchors) > 1:
            second_anchor = protein_anchors[1]
            quantities[second_anchor] += 100.0 * protein_deficit * 0.3 / max(float(available[second_anchor]["protein"]), 1.0)

    total_nutrients = totals()
    calorie_deficit = max(0.0, context.calorie_target_kcal - total_nutrients["energy_fibre_kcal"])
    booster = None
    fat_target_g = context.nutrition_targets.get("fat")
    fat_gap = max(0.0, fat_target_g - total_nutrients["fat"]) if fat_target_g else 0.0
    booster_threshold = max(
        float(context.basket_policy["booster_gap_floor"]),
        context.calorie_target_kcal * float(context.basket_policy["booster_gap_ratio"]),
    )
    if bool(context.basket_policy["booster_enabled"]) and (
        calorie_deficit > booster_threshold or fat_gap > float(context.basket_policy["booster_fat_gap"])
    ):
        booster = gr._pick_diverse_candidate(  # noqa: SLF001
            "calorie_booster",
            available,
            context.role_scores["calorie_booster"],
            excluded,
            chosen,
            context.preferences,
            context.goal_profile,
        )
        if booster is not None:
            chosen.append((booster, "calorie_booster"))
            excluded.add(booster)
            booster_grams = 100.0 * max(calorie_deficit, 0.0) / max(float(available[booster]["energy_fibre_kcal"]), 1.0)
            if fat_gap > 0:
                booster_grams = max(booster_grams, 100.0 * fat_gap * 0.7 / max(float(available[booster]["fat"]), 1.0))
            quantities[booster] = booster_grams

    gr._apply_goal_quantity_caps(chosen, available, quantities, context.goal_profile)  # noqa: SLF001

    if context.goal_profile == "fat_loss":
        overshoot_tolerance = max(
            float(context.basket_policy["fat_loss_overshoot_floor"]),
            context.calorie_target_kcal * float(context.basket_policy["fat_loss_overshoot_ratio"]),
        )
        total_nutrients = totals()
        calorie_overshoot = total_nutrients["energy_fibre_kcal"] - context.calorie_target_kcal
        if calorie_overshoot > overshoot_tolerance and booster is not None and booster in quantities:
            booster_food = available[booster]
            min_booster_g = max(float(booster_food.get("default_serving_g") or 0.0) * 0.6, 20.0)
            reducible_g = max(0.0, quantities[booster] - min_booster_g)
            reduce_g = min(
                reducible_g,
                100.0 * calorie_overshoot / max(float(booster_food["energy_fibre_kcal"]), 1.0),
            )
            quantities[booster] = max(0.0, quantities[booster] - reduce_g)
            if quantities[booster] < min_booster_g:
                quantities[booster] = 0.0

        total_nutrients = totals()
        calorie_overshoot = total_nutrients["energy_fibre_kcal"] - context.calorie_target_kcal
        if calorie_overshoot > overshoot_tolerance and carb_base is not None and carb_base in quantities:
            carb_food = available[carb_base]
            min_carb_g = max(float(carb_food.get("default_serving_g") or 0.0), 60.0)
            reducible_g = max(0.0, quantities[carb_base] - min_carb_g)
            reduce_g = min(
                reducible_g,
                100.0 * calorie_overshoot / max(float(carb_food["energy_fibre_kcal"]), 1.0),
            )
            quantities[carb_base] = max(min_carb_g, quantities[carb_base] - reduce_g)

        total_nutrients = totals()
        calorie_overshoot = total_nutrients["energy_fibre_kcal"] - context.calorie_target_kcal
        protein_surplus = total_nutrients["protein"] - context.protein_target_g
        if calorie_overshoot > overshoot_tolerance and len(protein_anchors) > 1 and protein_surplus > 10:
            secondary_anchor = protein_anchors[-1]
            if secondary_anchor in quantities:
                anchor_food = available[secondary_anchor]
                min_anchor_g = max(float(anchor_food.get("default_serving_g") or 0.0), 80.0)
                reducible_g = max(0.0, quantities[secondary_anchor] - min_anchor_g)
                reduce_g = min(
                    reducible_g,
                    100.0 * calorie_overshoot / max(float(anchor_food["energy_fibre_kcal"]), 1.0),
                    100.0 * max(0.0, protein_surplus - 5.0) / max(float(anchor_food["protein"]), 1.0),
                )
                quantities[secondary_anchor] = max(min_anchor_g, quantities[secondary_anchor] - reduce_g)

    total_nutrients = totals()
    calorie_deficit = max(0.0, context.calorie_target_kcal - total_nutrients["energy_fibre_kcal"])
    final_carb_fill_ratio = float(context.basket_policy["final_carb_fill_ratio"])
    final_booster_fill_ratio = float(context.basket_policy["final_booster_fill_ratio"])
    protein_close_enough = total_nutrients["protein"] >= (context.protein_target_g * 0.95)
    if context.goal_profile == "fat_loss" and protein_close_enough:
        final_carb_fill_ratio = 0.0
        final_booster_fill_ratio = 0.0
    if calorie_deficit > 0 and carb_base is not None and final_carb_fill_ratio > 0:
        quantities[carb_base] += (
            100.0
            * calorie_deficit
            * final_carb_fill_ratio
            / max(float(available[carb_base]["energy_fibre_kcal"]), 1.0)
        )
    total_nutrients = totals()
    calorie_deficit = max(0.0, context.calorie_target_kcal - total_nutrients["energy_fibre_kcal"])
    if calorie_deficit > 0 and booster is not None and final_booster_fill_ratio > 0:
        quantities[booster] += (
            100.0
            * calorie_deficit
            * final_booster_fill_ratio
            / max(float(available[booster]["energy_fibre_kcal"]), 1.0)
        )

    gr._apply_goal_quantity_caps(chosen, available, quantities, context.goal_profile)  # noqa: SLF001

    scaled_quantities: dict[str, float] = {}
    warnings: list[str] = []
    scaling_notes: list[str] = []
    for food_id, role in chosen:
        effective_days, item_scaling_notes, item_warnings = gr._shopping_mode_days(available[food_id], context.days, context.shopping_mode)  # noqa: SLF001
        quantity_g = gr._round_quantity_g(available[food_id], quantities.get(food_id, 0.0) * effective_days)  # noqa: SLF001
        quantity_g, sanity_notes, sanity_warnings = gr._apply_quantity_sanity(available[food_id], quantity_g, context.shopping_mode)  # noqa: SLF001
        if quantity_g <= 0:
            continue
        scaled_quantities[food_id] = quantity_g
        scaling_notes.extend(item_scaling_notes)
        scaling_notes.extend(sanity_notes)
        warnings.extend(item_warnings)
        warnings.extend(sanity_warnings)

    def scaled_totals() -> dict[str, float]:
        total = {key: 0.0 for key in gr.NUTRIENT_SUMMARY_META}  # noqa: SLF001
        for scaled_food_id, scaled_quantity_g in scaled_quantities.items():
            for nutrient_id, value in gr._tracked_totals(available[scaled_food_id], scaled_quantity_g).items():  # noqa: SLF001
                total[nutrient_id] += value
        return total

    target_protein_total = context.protein_target_g * context.days
    target_calorie_total = context.calorie_target_kcal * context.days
    if context.days > 1 and context.shopping_mode in {"fresh", "bulk"} and scaled_quantities:
        current_totals = scaled_totals()
        protein_gap = max(0.0, target_protein_total - current_totals["protein"])
        stable_protein_anchors = [
            food_id
            for food_id in protein_anchors
            if food_id in scaled_quantities and (gr._is_shelf_stable(available[food_id]) or not gr._is_perishable(available[food_id]))  # noqa: SLF001
        ]
        if protein_gap > max(20.0, target_protein_total * 0.08) and stable_protein_anchors:
            fill_food_id = stable_protein_anchors[0]
            scaled_quantities[fill_food_id] += 100.0 * protein_gap * 0.8 / max(float(available[fill_food_id]["protein"]), 1.0)
            scaling_notes.append("Stable protein items were topped up after perishable items were softened for the shopping window.")

        current_totals = scaled_totals()
        calorie_gap = max(0.0, target_calorie_total - current_totals["energy_fibre_kcal"])
        if calorie_gap > max(250.0, target_calorie_total * 0.08) and carb_base is not None and carb_base in scaled_quantities:
            if gr._is_bulk_friendly(available[carb_base]):  # noqa: SLF001
                scaled_quantities[carb_base] += 100.0 * calorie_gap * 0.75 / max(float(available[carb_base]["energy_fibre_kcal"]), 1.0)
                scaling_notes.append("Shelf-stable carb items were topped up to keep the shopping list usable across the full window.")

        current_totals = scaled_totals()
        calorie_gap = max(0.0, target_calorie_total - current_totals["energy_fibre_kcal"])
        if calorie_gap > max(150.0, target_calorie_total * 0.04) and booster is not None and booster in scaled_quantities:
            if gr._is_bulk_friendly(available[booster]):  # noqa: SLF001
                scaled_quantities[booster] += 100.0 * calorie_gap / max(float(available[booster]["energy_fibre_kcal"]), 1.0)
                scaling_notes.append("Pantry-friendly extras were topped up to reduce large calorie gaps after perishable items were softened.")

    chosen, scaled_quantities, split_notes, realism_notes, adjusted_by_split = gr._apply_split_realism(  # noqa: SLF001
        chosen,
        available,
        context.role_orders,
        scaled_quantities,
        context.days,
        context.shopping_mode,
    )
    plan_quantities = dict(scaled_quantities)
    shopping_quantities, pantry_notes = gr._apply_pantry_adjustments(  # noqa: SLF001
        chosen,
        available,
        scaled_quantities,
        context.pantry_items,
        days=context.days,
        shopping_mode=context.shopping_mode,
    )

    shopping_list: list[dict[str, object]] = []
    estimated_totals = {key: 0.0 for key in gr.NUTRIENT_SUMMARY_META}  # noqa: SLF001
    for planned_food_id, planned_quantity_g in plan_quantities.items():
        for nutrient_id, value in gr._tracked_totals(available[planned_food_id], planned_quantity_g).items():  # noqa: SLF001
            estimated_totals[nutrient_id] += value
    estimated_basket_cost = 0.0
    estimated_basket_cost_low = 0.0
    estimated_basket_cost_high = 0.0
    priced_item_count = 0
    priced_from_usda_count = 0
    priced_from_bls_area_count = 0
    priced_from_fallback_count = 0
    range_supported_item_count = 0
    for food_id, role in chosen:
        quantity_g = shopping_quantities.get(food_id, 0.0)
        if quantity_g <= 0:
            continue
        nutrient_totals = gr._tracked_totals(available[food_id], quantity_g)  # noqa: SLF001
        protein = nutrient_totals["protein"]
        calories = nutrient_totals["energy_fibre_kcal"]
        substitution = gr._substitution(food_id, role, available, context.role_orders)  # noqa: SLF001
        estimated_unit_price, estimated_item_cost, price_unit_display = gr._price_reference(available[food_id], quantity_g)  # noqa: SLF001
        estimated_price_low, estimated_price_high = gr._price_range(available[food_id], quantity_g)  # noqa: SLF001
        price_source_used = gr._price_source_used(available[food_id])  # noqa: SLF001
        value_reason_short, price_efficiency_note = gr._value_explanation(role, available[food_id], context.preferences, context.nutrition_targets)  # noqa: SLF001
        if estimated_item_cost is not None:
            estimated_basket_cost += estimated_item_cost
            priced_item_count += 1
            if price_source_used == "usda_area":
                priced_from_usda_count += 1
            elif price_source_used == "bls_area":
                priced_from_bls_area_count += 1
            elif price_source_used == "bls_fallback":
                priced_from_fallback_count += 1
            if estimated_price_low is not None and estimated_price_high is not None:
                estimated_basket_cost_low += estimated_price_low
                estimated_basket_cost_high += estimated_price_high
                range_supported_item_count += 1
            else:
                estimated_basket_cost_low += estimated_item_cost
                estimated_basket_cost_high += estimated_item_cost
        shopping_list.append(
            {
                "generic_food_id": food_id,
                "name": available[food_id]["display_name"],
                "role": role,
                "substitution": substitution,
                "substitution_reason": gr._substitution_reason(role, substitution),  # noqa: SLF001
                "reason_short": gr._reason_short(role, available[food_id], context.preferences, context.nutrition_targets),  # noqa: SLF001
                "why_selected": gr._why_selected(role, available[food_id], context.preferences, context.nutrition_targets),  # noqa: SLF001
                "quantity_g": round(quantity_g, 1),
                "quantity_display": gr._quantity_display(available[food_id], quantity_g, days=context.days),  # noqa: SLF001
                "estimated_unit_price": estimated_unit_price,
                "estimated_item_cost": estimated_item_cost,
                "typical_unit_price": estimated_unit_price,
                "typical_item_cost": estimated_item_cost,
                "estimated_price_low": estimated_price_low,
                "estimated_price_high": estimated_price_high,
                "price_unit_display": price_unit_display,
                "price_source_used": price_source_used,
                "value_reason_short": value_reason_short,
                "price_efficiency_note": price_efficiency_note,
                "estimated_protein_g": round(protein, 1),
                "estimated_calories_kcal": round(calories, 1),
                "reason": gr._reason(role, available[food_id]),  # noqa: SLF001
            }
        )

    nutrition_summary = {
        "protein_target_g": round(context.protein_target_g * context.days, 1),
        "protein_estimated_g": round(estimated_totals["protein"], 1),
        "calorie_target_kcal": round(context.calorie_target_kcal * context.days, 1),
        "calorie_estimated_kcal": round(estimated_totals["energy_fibre_kcal"], 1),
    }
    for nutrient_id, target_value in context.nutrition_targets.items():
        if nutrient_id in {"protein", "energy_fibre_kcal"}:
            continue
        target_key, estimated_key = gr.NUTRIENT_SUMMARY_META[nutrient_id]  # noqa: SLF001
        nutrition_summary[target_key] = round(target_value * context.days, 1)
        nutrition_summary[estimated_key] = round(estimated_totals[nutrient_id], 1)

    assumptions = list(gr.DEFAULT_ASSUMPTIONS)  # noqa: SLF001
    if context.days > 1:
        assumptions.append(f"Shopping quantities and nutrition totals are scaled for {context.days} days using the same daily targets.")
    if pantry_notes:
        assumptions.append("Items marked as already available were reduced or removed from the shopping list. Nutrition totals still assume you use those pantry items.")
    unpriced_item_count = len(shopping_list) - priced_item_count
    price_confidence_note = None
    if priced_item_count:
        assumptions.append("Price estimates use local USDA monthly area prices when available, with local BLS average-price fallback and simple unit conversions. They are representative regional guidance, not store-specific quotes.")
        assumptions.append("Estimated basket cost only includes items that currently have a local USDA or BLS price reference.")
        if range_supported_item_count:
            assumptions.append("Price ranges reflect the spread across available USDA or BLS regional price areas where current mappings support it.")
        usda_adjustment_context = gr._usda_adjustment_context(available)  # noqa: SLF001
        if priced_from_usda_count:
            price_confidence_note = (
                "These are representative grocery price estimates built from local USDA Food-at-Home Monthly Area Prices where available, "
                "inflation-adjusted with local BLS Food at Home CPI and backed by local BLS average-price fallback when USDA coverage is missing. Treat them as typical regional price references, "
                "not exact store or SKU quotes."
            )
        else:
            price_confidence_note = (
                "These are representative grocery price estimates from local BLS average-price tables. "
                "Treat them as a typical regional price level, not an exact store or SKU quote."
            )
    else:
        usda_adjustment_context = None

    usda_area_name = str(context.price_context.get("usda_area_name") or gr.USDA_AREA_NAMES["US"])  # noqa: SLF001
    bls_area_code = str(context.price_context.get("bls_area_code") or "0")
    bls_area_name = str(context.price_context.get("bls_area_name") or gr.BLS_AREA_NAMES["0"])  # noqa: SLF001
    if priced_item_count:
        if priced_from_usda_count and priced_from_bls_area_count == 0 and priced_from_fallback_count == 0:
            price_source_note = (
                f"Using inflation-adjusted {usda_area_name} USDA Food-at-Home Monthly Area Prices as the typical regional grocery reference for this basket."
            )
        elif priced_from_usda_count:
            price_source_note = (
                f"Using inflation-adjusted {usda_area_name} USDA Food-at-Home Monthly Area Prices for {priced_from_usda_count} item{'' if priced_from_usda_count == 1 else 's'}, "
                f"{bls_area_name} BLS average prices for {priced_from_bls_area_count} item{'' if priced_from_bls_area_count == 1 else 's'}, "
                f"and U.S. city average BLS fallback for {priced_from_fallback_count} item{'' if priced_from_fallback_count == 1 else 's'}."
            )
        elif bls_area_code == "0":
            price_source_note = "Using U.S. city average BLS average prices as the typical grocery reference."
        else:
            price_source_note = (
                f"Using {bls_area_name} BLS average prices as the typical regional grocery reference"
                if priced_from_fallback_count == 0
                else (
                    f"Using {bls_area_name} BLS average prices as the typical regional grocery reference "
                    f"for {priced_from_bls_area_count} item{'' if priced_from_bls_area_count == 1 else 's'}, "
                    f"with U.S. city average fallback for {priced_from_fallback_count} item{'' if priced_from_fallback_count == 1 else 's'}."
                )
            )
    else:
        price_source_note = None

    if priced_from_usda_count:
        price_area_code = str(context.price_context.get("usda_area_code") or "US")
        price_area_name = usda_area_name
    else:
        price_area_code = bls_area_code
        price_area_name = bls_area_name

    response: dict[str, object] = {
        "days": context.days,
        "goal_profile": context.goal_profile,
        "shopping_mode": context.shopping_mode,
        "adjusted_by_split": adjusted_by_split,
        "shopping_list": shopping_list,
        "meal_suggestions": gr._build_meal_suggestions(shopping_list, available),  # noqa: SLF001
        "nutrition_summary": nutrition_summary,
        "assumptions": assumptions,
        "price_area_code": price_area_code,
        "price_area_name": price_area_name,
        "price_source_note": price_source_note,
        "usda_priced_item_count": priced_from_usda_count,
        "bls_priced_item_count": priced_from_bls_area_count + priced_from_fallback_count,
        "unpriced_item_count": unpriced_item_count,
    }
    if priced_item_count:
        response["estimated_basket_cost"] = round(estimated_basket_cost, 2)
        response["typical_basket_cost"] = round(estimated_basket_cost, 2)
        response["priced_item_count"] = priced_item_count
        response["price_coverage_note"] = (
            f"{priced_from_usda_count} basket item{'' if priced_from_usda_count == 1 else 's'} use USDA monthly area prices, "
            f"{priced_from_bls_area_count + priced_from_fallback_count} use BLS reference pricing, "
            f"and {unpriced_item_count} remain unpriced."
        )
        response["basket_cost_note"] = (
            f"Estimated typical basket cost covers {priced_item_count} priced items using local USDA or BLS regional price references "
            f"and excludes {unpriced_item_count} unpriced items."
        )
        response["price_confidence_note"] = price_confidence_note
        if priced_from_usda_count and usda_adjustment_context:
            response["price_adjustment_note"] = (
                "USDA Food-at-Home Monthly Area Prices end in "
                f"{usda_adjustment_context['base_period']}. USDA-priced items are scaled toward current grocery levels "
                f"using the local BLS Food at Home CPI through {usda_adjustment_context['current_period']} "
                f"(multiplier {usda_adjustment_context['multiplier']:.3f})."
            )
        if range_supported_item_count:
            response["estimated_basket_cost_low"] = round(estimated_basket_cost_low, 2)
            response["estimated_basket_cost_high"] = round(estimated_basket_cost_high, 2)
    if split_notes:
        response["split_notes"] = split_notes
    if realism_notes:
        response["realism_notes"] = realism_notes
    if pantry_notes:
        response["pantry_notes"] = pantry_notes
    if scaling_notes:
        response["scaling_notes"] = sorted(set(scaling_notes))
    if warnings:
        response["warnings"] = sorted(set(warnings))
    return _candidate_bundle_from_response(
        context,
        response=response,
        candidate_id=f"candidate_{candidate_index:02d}",
        selection_trace=seed.selection_trace,
        heuristic_selection_score=seed.heuristic_selection_score,
        stores=stores,
    )


def recommend_generic_food_candidates(
    con: duckdb.DuckDBPyConnection,
    *,
    protein_target_g: float,
    calorie_target_kcal: float,
    preferences: dict[str, object] | None = None,
    nutrition_targets: dict[str, float] | None = None,
    pantry_items: Iterable[str] | None = None,
    days: int = 1,
    shopping_mode: str = "balanced",
    price_context: dict[str, str] | None = None,
    stores: Sequence[dict[str, object]] | None = None,
    candidate_count: int = DEFAULT_CANDIDATE_COUNT,
) -> list[dict[str, object]]:
    context = _prepare_context(
        con,
        protein_target_g=protein_target_g,
        calorie_target_kcal=calorie_target_kcal,
        preferences=preferences,
        nutrition_targets=nutrition_targets,
        pantry_items=pantry_items,
        days=days,
        shopping_mode=shopping_mode,
        price_context=price_context,
    )
    requested_count = max(1, min(MAX_CANDIDATE_COUNT, int(candidate_count)))
    seeds = _generate_candidate_seeds(context, requested_count)
    candidates: list[dict[str, object]] = []
    seen_shopping_lists: set[tuple[str, ...]] = set()
    for index, seed in enumerate(seeds):
        candidate = _materialize_candidate(context, seed, candidate_index=index, stores=stores)
        shopping_key = tuple(candidate["candidate_metadata"]["shopping_food_ids"])
        if shopping_key in seen_shopping_lists:
            continue
        seen_shopping_lists.add(shopping_key)
        candidates.append(candidate)
    if not candidates:
        raise ValueError("No generic foods could be selected for the recommendation.")
    return candidates[:requested_count]


def recommend_with_trained_scorer(
    con: duckdb.DuckDBPyConnection,
    *,
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
) -> dict[str, object]:
    normalized_config = normalize_scorer_config(scorer_config)
    candidates = recommend_generic_food_candidates(
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
        candidate_count=int(normalized_config["candidate_count"]),
    )

    model_path = Path(str(normalized_config["scorer_model_path"]))
    scorer_bundle = plan_scorer.load_bundle(model_path)
    feature_rows = [plan_scorer.extract_candidate_features(candidate) for candidate in candidates]
    heuristic_scores = [plan_scorer.heuristic_candidate_label(row) for row in feature_rows]
    model_scores = plan_scorer.score_feature_rows(scorer_bundle, feature_rows)

    ranked = sorted(
        zip(candidates, feature_rows, heuristic_scores, model_scores, strict=True),
        key=lambda row: (-row[3], -row[2], row[0]["candidate_id"]),
    )
    selected_candidate, _selected_features, _selected_heuristic_score, _selected_model_score = ranked[0]
    response = dict(selected_candidate["recommendation"])
    response["scorer_used"] = True
    response["scorer_backend"] = str(scorer_bundle.get("backend") or "unknown")
    response["candidate_count_considered"] = len(candidates)

    if normalized_config["debug"]:
        response["scoring_debug"] = {
            "candidate_count": len(candidates),
            "selected_candidate_id": selected_candidate["candidate_id"],
            "model_path": str(model_path),
            "backend": str(scorer_bundle.get("backend") or "unknown"),
            "candidates": [
                {
                    "candidate_id": candidate["candidate_id"],
                    "shopping_food_ids": candidate["candidate_metadata"]["shopping_food_ids"],
                    "heuristic_selection_score": candidate["candidate_metadata"]["heuristic_selection_score"],
                    "heuristic_score": round(float(heuristic_score), 6),
                    "model_score": round(float(model_score), 6),
                    "selected": candidate["candidate_id"] == selected_candidate["candidate_id"],
                    "features": {key: feature_row[key] for key in (*plan_scorer.NUMERIC_FEATURES, *plan_scorer.BOOLEAN_FEATURES, *plan_scorer.CATEGORICAL_FEATURES)},
                }
                for candidate, feature_row, heuristic_score, model_score in ranked
            ],
        }
    return response
