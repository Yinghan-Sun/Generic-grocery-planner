"""Model-ranked candidate generation and trained-scorer integration."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

import duckdb

from dietdashboard import candidate_debug
from dietdashboard import generic_recommender as gr
from dietdashboard import model_candidate_features
from dietdashboard import model_candidate_generator
from dietdashboard import plan_scorer
from dietdashboard import hybrid_pipeline_final

DEFAULT_CANDIDATE_COUNT = 6
MAX_CANDIDATE_COUNT = 12
DEFAULT_MODEL_CANDIDATE_COUNT = 4
MAX_MODEL_CANDIDATE_COUNT = 8


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
    nearby_store_count: int
    available: dict[str, dict[str, object]]
    goal_profile: str
    basket_policy: dict[str, object]
    role_scores: dict[str, dict[str, float]]
    role_orders: dict[str, list[str]]
    algorithm_config: dict[str, object]


@dataclass
class CandidateSeed:
    chosen: list[tuple[str, str]]
    excluded: set[str]
    selection_trace: list[dict[str, object]]
    heuristic_selection_score: float
    generator_score: float
    source: str
    source_backend: str


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


def normalize_candidate_generation_config(config: dict[str, object] | None) -> dict[str, object]:
    raw = dict(config or {})
    enabled = bool(raw.get("enable_model_candidates"))
    model_candidate_count = raw.get("model_candidate_count", DEFAULT_MODEL_CANDIDATE_COUNT)
    try:
        model_candidate_count_value = int(model_candidate_count)
    except (TypeError, ValueError):
        model_candidate_count_value = DEFAULT_MODEL_CANDIDATE_COUNT
    model_candidate_count_value = max(1, min(MAX_MODEL_CANDIDATE_COUNT, model_candidate_count_value))

    backend = str(raw.get("candidate_generator_backend") or "auto").strip().lower()
    if backend not in {"auto", *model_candidate_generator.available_backends()}:
        raise ValueError("Invalid candidate_generator_backend.")

    configured_model_path = raw.get("candidate_generator_model_path")
    if configured_model_path is not None and str(configured_model_path).strip():
        model_path = str(configured_model_path).strip()
    elif backend != "auto":
        model_path = str(model_candidate_generator.default_backend_model_path(backend))
    else:
        model_path = str(model_candidate_generator.default_model_path())

    return {
        "enable_model_candidates": enabled,
        "model_candidate_count": model_candidate_count_value,
        "candidate_generator_model_path": model_path,
        "candidate_generator_backend": backend,
        "algorithm_version": str(raw.get("algorithm_version") or hybrid_pipeline_final.FINAL_ALGORITHM_VERSION),
        "structured_complementarity_enabled": bool(raw.get("structured_complementarity_enabled", True)),
        "structured_materialization_enabled": bool(raw.get("structured_materialization_enabled", True)),
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
    nearby_store_count: int = 0,
    algorithm_config: dict[str, object] | None = None,
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
        nearby_store_count=max(0, int(nearby_store_count)),
        available=available,
        goal_profile=goal_profile,
        basket_policy=basket_policy,
        role_scores=role_scores,
        role_orders=role_orders,
        algorithm_config=dict(algorithm_config or {}),
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
    goal_structure_bonus = _goal_structure_selection_bonus(
        context,
        role=role,
        food_id=food_id,
        chosen=chosen,
    )
    return base_score - diversity_penalty + goal_structure_bonus


def _algorithm_flag(
    context: PlannerContext,
    key: str,
    *,
    default: bool = True,
) -> bool:
    return bool(context.algorithm_config.get(key, default))


def _structured_complementarity_enabled(context: PlannerContext) -> bool:
    return _algorithm_flag(context, "structured_complementarity_enabled", default=True)


def _structured_materialization_enabled(context: PlannerContext) -> bool:
    return _algorithm_flag(context, "structured_materialization_enabled", default=True)


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


def _seed_role_reference_map(seed: CandidateSeed | None) -> dict[tuple[str, int], str]:
    if seed is None:
        return {}
    occurrence_by_role: Counter[str] = Counter()
    references: dict[tuple[str, int], str] = {}
    for food_id, role in seed.chosen:
        occurrence_index = int(occurrence_by_role[role])
        references[(role, occurrence_index)] = food_id
        occurrence_by_role[role] += 1
    return references


def _seed_novelty_food_count(seed: CandidateSeed) -> int:
    return sum(1 for step in seed.selection_trace if bool(step.get("differs_from_best_heuristic_role")))


def _seed_sort_key(seed: CandidateSeed) -> tuple[float, float, tuple[str, ...]]:
    return (
        -seed.generator_score,
        -float(_seed_novelty_food_count(seed)),
        -seed.heuristic_selection_score,
        tuple(food_id for food_id, _role in seed.chosen),
    )


def _food_metric(food: Mapping[str, object], nutrient_id: str) -> float:
    return float(food.get(nutrient_id) or 0.0)


def _protein_density(food: Mapping[str, object]) -> float:
    return _food_metric(food, "protein") / max(_food_metric(food, "energy_fibre_kcal"), 1.0)


def _prep_score(food: Mapping[str, object]) -> float:
    return float(gr.PREP_LEVEL_SCORES.get(str(food.get("prep_level") or ""), 0.0))  # noqa: SLF001


def _produce_combo_cluster(food: Mapping[str, object]) -> str:
    food_id = str(food.get("generic_food_id") or "")
    base_cluster = gr._produce_cluster(dict(food))  # noqa: SLF001
    prep_level = str(food.get("prep_level") or "")
    fiber = _food_metric(food, "fiber")
    vitamin_c = _food_metric(food, "vitamin_c")
    calories = _food_metric(food, "energy_fibre_kcal")
    if food_id in {"spinach", "kale"}:
        return "leafy_dense"
    if food_id in {"broccoli", "cauliflower"}:
        return "crucifer_fiber"
    if food_id == "bell_peppers":
        return "vitamin_c_crisp"
    if food_id in {"tomatoes", "lettuce", "cucumber"}:
        return "watery_practical"
    if base_cluster == "fruit":
        return "fruit"
    if base_cluster == "portable_produce" and calories <= 25.0:
        return "watery_practical"
    if vitamin_c >= 70.0 and fiber >= 2.0:
        return "vitamin_c_crisp"
    if fiber >= 3.2 and calories <= 60.0:
        return "crucifer_fiber" if prep_level == "medium" else "leafy_dense"
    if prep_level in {"none", "low"} and calories <= 25.0:
        return "watery_practical"
    return base_cluster


def _produce_combo_cluster_for_food_id(food_id: str) -> str:
    normalized_food_id = str(food_id or "")
    if normalized_food_id in {"spinach", "kale"}:
        return "leafy_dense"
    if normalized_food_id in {"broccoli", "cauliflower"}:
        return "crucifer_fiber"
    if normalized_food_id == "bell_peppers":
        return "vitamin_c_crisp"
    if normalized_food_id in {"tomatoes", "lettuce", "cucumber"}:
        return "watery_practical"
    if normalized_food_id in {"berries", "apples", "bananas"}:
        return "fruit"
    return "produce"


def _produce_combo_bonus(
    context: PlannerContext,
    *,
    food_id: str,
    chosen: Sequence[tuple[str, str]],
) -> float:
    if food_id not in context.available:
        return 0.0

    food = context.available[food_id]
    candidate_cluster = _produce_combo_cluster(food)
    existing_produce_ids = [
        existing_food_id
        for existing_food_id, role in chosen
        if role == "produce" and existing_food_id in context.available
    ]
    if not existing_produce_ids:
        return 0.0

    existing_foods = [context.available[existing_food_id] for existing_food_id in existing_produce_ids]
    existing_clusters = [_produce_combo_cluster(existing_food) for existing_food in existing_foods]
    bonus = 0.0

    if candidate_cluster in existing_clusters:
        bonus -= 0.09
    if candidate_cluster == "leafy_dense" and any(cluster in {"leafy_dense", "crucifer_fiber"} for cluster in existing_clusters):
        bonus -= 0.08
    if candidate_cluster == "crucifer_fiber" and "leafy_dense" in existing_clusters and len(existing_clusters) >= 2:
        bonus -= 0.05
    if candidate_cluster == "watery_practical" and any(cluster in {"leafy_dense", "crucifer_fiber"} for cluster in existing_clusters):
        bonus += 0.08
    if candidate_cluster == "vitamin_c_crisp" and "watery_practical" in existing_clusters:
        bonus += 0.05
    if candidate_cluster == "crucifer_fiber" and "watery_practical" in existing_clusters:
        bonus += 0.05

    existing_fiber = sum(_food_metric(existing_food, "fiber") for existing_food in existing_foods)
    existing_vitamin_c = sum(_food_metric(existing_food, "vitamin_c") for existing_food in existing_foods)
    if existing_fiber >= 6.0 and candidate_cluster in {"leafy_dense", "crucifer_fiber"}:
        bonus -= 0.05
    if existing_vitamin_c >= 120.0 and candidate_cluster == "vitamin_c_crisp":
        bonus -= 0.03
    if existing_vitamin_c >= 120.0 and candidate_cluster == "watery_practical":
        bonus += 0.03

    return bonus


def _fat_loss_produce_pair_bonus(
    context: PlannerContext,
    *,
    left_food_id: str,
    right_food_id: str,
    baseline_produce_ids: Sequence[str],
) -> float:
    if left_food_id not in context.available or right_food_id not in context.available:
        return 0.0
    left_food = context.available[left_food_id]
    right_food = context.available[right_food_id]
    pair_clusters = {_produce_combo_cluster(left_food), _produce_combo_cluster(right_food)}
    pair_bonus = 0.0
    if len(pair_clusters) == 1:
        pair_bonus -= 0.1
    if pair_clusters == {"leafy_dense", "crucifer_fiber"}:
        pair_bonus -= 0.07
    if "watery_practical" in pair_clusters:
        pair_bonus += 0.05
    if "vitamin_c_crisp" in pair_clusters and "watery_practical" in pair_clusters:
        pair_bonus += 0.05
    baseline_clusters = {
        _produce_combo_cluster(context.available[food_id])
        for food_id in baseline_produce_ids
        if food_id in context.available
    }
    if pair_clusters == baseline_clusters and baseline_clusters:
        pair_bonus += 0.04
    return pair_bonus


def _seed_role_food_ids(seed: CandidateSeed, role: str) -> tuple[str, ...]:
    return tuple(food_id for food_id, chosen_role in seed.chosen if chosen_role == role)


def _seed_occurrence_map(seed: CandidateSeed) -> dict[tuple[str, int], str]:
    occurrence_by_role: Counter[str] = Counter()
    mapping: dict[tuple[str, int], str] = {}
    for food_id, role in seed.chosen:
        occurrence_index = int(occurrence_by_role[role])
        mapping[(role, occurrence_index)] = food_id
        occurrence_by_role[role] += 1
    return mapping


def _changed_roles_from_reference(
    seed: CandidateSeed,
    reference_seed: CandidateSeed | None,
) -> set[str]:
    if reference_seed is None:
        return set()
    seed_map = _seed_occurrence_map(seed)
    reference_map = _seed_occurrence_map(reference_seed)
    changed_roles: set[str] = set()
    for role, occurrence_index in {*seed_map.keys(), *reference_map.keys()}:
        if seed_map.get((role, occurrence_index)) != reference_map.get((role, occurrence_index)):
            changed_roles.add(role)
    return changed_roles


def _seed_source_hints(seed: CandidateSeed) -> set[str]:
    return {str(step.get("source_hint") or "") for step in seed.selection_trace if str(step.get("source_hint") or "")}


def _priority_profile(context: PlannerContext) -> dict[str, float]:
    fiber_target = float(context.nutrition_targets.get("fiber") or 0.0)
    fat_target = float(context.nutrition_targets.get("fat") or 0.0)
    protein_density_target = context.protein_target_g / max(context.calorie_target_kcal, 1.0)
    calorie_tightness = max(0.35, min(1.35, 2100.0 / max(context.calorie_target_kcal, 1400.0)))
    calorie_completion_priority = max(0.55, min(1.4, context.calorie_target_kcal / 2200.0))
    protein_priority = max(0.45, min(1.5, protein_density_target * 14.0))
    fiber_priority = max(0.4, min(1.45, (fiber_target / 30.0) if fiber_target else 0.55))
    fat_sensitivity = 0.45
    if fat_target > 0:
        fat_sensitivity = max(0.2, min(1.15, 0.9 - ((fat_target / max(context.calorie_target_kcal, 1.0)) - 0.03) * 10.0))
    return {
        "protein_priority": protein_priority,
        "fiber_priority": fiber_priority,
        "calorie_tightness": calorie_tightness,
        "calorie_completion_priority": calorie_completion_priority,
        "cost_priority": 1.0 if bool(context.preferences.get("budget_friendly")) else 0.45,
        "practicality_priority": 1.0 if bool(context.preferences.get("low_prep")) else 0.45,
        "fat_sensitivity": fat_sensitivity,
    }


def _commonality_bonus(food: Mapping[str, object]) -> float:
    commonality_rank = int(food.get("commonality_rank") or 999)
    if commonality_rank <= 10:
        return 0.07
    if commonality_rank <= 20:
        return 0.04
    if commonality_rank >= 35:
        return -0.05
    return 0.0


def _protein_anchor_category(food: Mapping[str, object]) -> str:
    food_id = str(food.get("generic_food_id") or "")
    family = str(food.get("food_family") or "")
    if food_id == "eggs":
        return "egg"
    if family == "dairy":
        return "dairy"
    if food_id in {"tofu", "edamame", "veggie_burger"}:
        return "soy"
    if family == "legume" or food_id in {"lentils", "beans", "black_beans", "chickpeas", "hummus"}:
        return "legume"
    if food_id in {"peanut_butter", "almond_butter"}:
        return "nut_butter"
    if food_id in {"chicken_breast", "turkey", "tuna", "shrimp"}:
        return "lean_animal"
    if food_id in {"rotisserie_chicken", "salmon", "sardines", "ground_beef"}:
        return "rich_animal"
    if family == "protein":
        return "animal"
    return family or "other"


def _goal_structure_selection_bonus(
    context: PlannerContext,
    *,
    role: str,
    food_id: str,
    chosen: Sequence[tuple[str, str]],
) -> float:
    if food_id not in context.available:
        return 0.0

    food = context.available[food_id]
    food_family = str(food.get("food_family") or "")
    food_id_value = str(food.get("generic_food_id") or "")
    chosen_same_role = [
        chosen_food_id
        for chosen_food_id, chosen_role in chosen
        if chosen_role == role and chosen_food_id in context.available
    ]
    bonus = 0.0

    if role == "protein_anchor":
        category = _protein_anchor_category(food)
        chosen_categories = [_protein_anchor_category(context.available[chosen_food_id]) for chosen_food_id in chosen_same_role]
        has_legume = "legume" in chosen_categories
        has_soy = "soy" in chosen_categories
        has_dairy_or_egg = any(value in {"dairy", "egg"} for value in chosen_categories)
        has_lean_animal = any(value in {"lean_animal", "animal"} for value in chosen_categories)

        if context.goal_profile == "muscle_gain":
            if category in {"lean_animal", "egg", "dairy"}:
                bonus += 0.12
            if has_lean_animal and category in {"dairy", "egg"}:
                bonus += 0.22
            if has_dairy_or_egg and category == "lean_animal":
                bonus += 0.2
            if category == "legume":
                bonus -= 0.18
        elif context.goal_profile == "fat_loss":
            if category in {"lean_animal", "soy", "dairy"}:
                bonus += 0.18
            if category in {"rich_animal", "nut_butter"}:
                bonus -= 0.26
            if has_lean_animal and category in {"dairy", "soy"}:
                bonus += 0.12
        elif context.goal_profile == "maintenance":
            if category in {"lean_animal", "egg", "soy", "dairy"}:
                bonus += 0.1
            if has_lean_animal and category in {"egg", "soy", "dairy"}:
                bonus += 0.08
            if category == "legume":
                bonus -= 0.08
        elif context.goal_profile == "high_protein_vegetarian":
            if category in {"dairy", "egg", "soy"}:
                bonus += 0.2
            if has_soy and category in {"dairy", "egg"}:
                bonus += 0.24
            if has_dairy_or_egg and category == "soy":
                bonus += 0.28
            if category in {"legume", "nut_butter"}:
                bonus -= 0.18
            if category in {"lean_animal", "animal", "rich_animal"}:
                bonus -= 0.4
        elif context.goal_profile == "budget_friendly_healthy":
            if not chosen_same_role:
                if category == "legume":
                    bonus += 0.18
                elif category in {"egg", "soy"}:
                    bonus += 0.12
            else:
                if has_legume and category in {"egg", "soy"}:
                    bonus += 0.36
                if has_legume and category == "nut_butter":
                    bonus += 0.14
                if has_legume and category == "legume":
                    bonus -= 0.42
                if not has_legume and category == "legume":
                    bonus += 0.16
                if category in {"rich_animal", "animal"}:
                    bonus -= 0.2

    elif role == "carb_base":
        if context.goal_profile == "muscle_gain":
            if food_id_value in {"pasta", "bagel"}:
                bonus += 0.26
            if food_id_value in {"oats", "potatoes", "wholemeal_bread", "sweet_potatoes"}:
                bonus += 0.1
            if food_id_value == "rice":
                bonus -= 0.08
        elif context.goal_profile == "fat_loss":
            if food_id_value in {"wholemeal_bread", "quinoa", "potatoes", "sweet_potatoes"}:
                bonus += 0.18
            if food_id_value in {"rice", "pasta"}:
                bonus -= 0.18
        elif context.goal_profile == "maintenance":
            if food_id_value in {"wholemeal_bread", "potatoes", "quinoa", "rice"}:
                bonus += 0.18 if food_id_value in {"wholemeal_bread", "potatoes", "quinoa"} else 0.04
            if food_id_value == "oats":
                bonus -= 0.08
        elif context.goal_profile == "high_protein_vegetarian":
            if food_id_value in {"wholemeal_bread", "quinoa"}:
                bonus += 0.24
            if food_id_value == "bagel":
                bonus += 0.08
            if food_id_value == "oats":
                bonus -= 0.12
            if food_id_value == "rice":
                bonus -= 0.1
        elif context.goal_profile == "budget_friendly_healthy":
            if food_id_value in {"rice", "pasta", "potatoes", "wholemeal_bread"}:
                bonus += 0.16
            if food_id_value == "quinoa":
                bonus -= 0.18

    elif role == "produce":
        cluster = _produce_combo_cluster(food)
        chosen_clusters = [_produce_combo_cluster(context.available[chosen_food_id]) for chosen_food_id in chosen_same_role]
        fruit_count = sum(1 for value in chosen_clusters if value == "fruit")
        high_volume_count = sum(1 for value in chosen_clusters if value in {"leafy_dense", "crucifer_fiber", "watery_practical", "vitamin_c_crisp"})

        if context.goal_profile == "muscle_gain":
            if not chosen_same_role:
                if cluster == "fruit":
                    bonus += 0.16
            else:
                if fruit_count and cluster in {"leafy_dense", "vitamin_c_crisp", "crucifer_fiber"}:
                    bonus += 0.18
                elif not fruit_count and cluster == "fruit":
                    bonus += 0.12
                if cluster == "watery_practical":
                    bonus -= 0.04
        elif context.goal_profile == "fat_loss":
            if cluster in {"leafy_dense", "crucifer_fiber", "watery_practical", "vitamin_c_crisp"}:
                bonus += 0.18
            if cluster == "fruit" and chosen_same_role:
                bonus -= 0.12
            if high_volume_count and cluster == "fruit":
                bonus -= 0.08
        elif context.goal_profile == "maintenance":
            if not chosen_same_role:
                if cluster in {"fruit", "watery_practical"}:
                    bonus += 0.1
            elif "fruit" in chosen_clusters and cluster in {"watery_practical", "vitamin_c_crisp"}:
                bonus += 0.12
            elif "fruit" not in chosen_clusters and cluster == "fruit":
                bonus += 0.1
        elif context.goal_profile == "high_protein_vegetarian":
            if not chosen_same_role:
                if cluster in {"leafy_dense", "fruit"}:
                    bonus += 0.12
            else:
                if "leafy_dense" in chosen_clusters and cluster in {"fruit", "vitamin_c_crisp"}:
                    bonus += 0.18
                elif "fruit" in chosen_clusters and cluster in {"leafy_dense", "vitamin_c_crisp"}:
                    bonus += 0.18
        elif context.goal_profile == "budget_friendly_healthy":
            if food_id_value in {"cabbage", "carrots", "onions", "frozen_vegetables", "bananas", "potatoes", "apples"}:
                bonus += 0.16
            if food_id_value in {"berries", "avocado", "bell_peppers", "broccoli"}:
                bonus -= 0.12

    elif role == "calorie_booster":
        if context.goal_profile == "muscle_gain":
            if food_id_value in {"peanut_butter", "olive_oil", "nuts", "almond_butter", "cheese"}:
                bonus += 0.18
        elif context.goal_profile == "fat_loss":
            bonus -= 0.4
        elif context.goal_profile == "maintenance":
            if food_id_value in {"olive_oil", "peanut_butter"}:
                bonus += 0.04
        elif context.goal_profile == "high_protein_vegetarian":
            if food_id_value in {"peanut_butter", "olive_oil"}:
                bonus += 0.08
        elif context.goal_profile == "budget_friendly_healthy":
            if food_id_value in {"olive_oil", "peanut_butter"}:
                bonus += 0.18
            if food_family == "fat":
                bonus += 0.04

    return round(bonus, 6)


def _role_nutrient_support_bonus(
    context: PlannerContext,
    *,
    role: str,
    food_id: str,
    profile: Mapping[str, float],
) -> float:
    if food_id not in context.available:
        return 0.0
    food = context.available[food_id]
    protein_density = _protein_density(food)
    calorie_density = _food_metric(food, "energy_fibre_kcal")
    fiber = _food_metric(food, "fiber")
    vitamin_c = _food_metric(food, "vitamin_c")
    fat = _food_metric(food, "fat")
    bonus = 0.0

    if role == "protein_anchor":
        bonus += min(protein_density * 0.55 * float(profile["protein_priority"]), 0.22)
        bonus -= min((fat / max(calorie_density, 1.0)) * 0.45 * float(profile["fat_sensitivity"]), 0.08)
    elif role == "carb_base":
        bonus += min((fiber / max(calorie_density, 1.0)) * 4.5 * float(profile["fiber_priority"]), 0.12)
        bonus += max(float(food.get("budget_score") or 0.0) - 3.0, 0.0) * 0.018 * float(profile["cost_priority"])
    elif role == "produce":
        bonus += min(fiber / 22.0 * float(profile["fiber_priority"]), 0.08)
        bonus += min(vitamin_c / 170.0, 0.06)
        bonus += max(0.0, 40.0 - calorie_density) / 250.0 * float(profile["calorie_tightness"])
    elif role == "calorie_booster":
        bonus += min(calorie_density / 900.0 * float(profile["calorie_completion_priority"]), 0.08)
        if fat >= 8.0:
            bonus += 0.02

    bonus += _commonality_bonus(food)
    bonus += max(float(food.get("budget_score") or 0.0) - 3.0, 0.0) * 0.012 * float(profile["cost_priority"])
    bonus += _prep_score(food) * 0.014 * float(profile["practicality_priority"])
    return bonus


def _pairwise_complementarity_bonus(
    context: PlannerContext,
    *,
    role: str,
    food_id: str,
    chosen: Sequence[tuple[str, str]],
    profile: Mapping[str, float],
) -> float:
    if not _structured_complementarity_enabled(context):
        return 0.0
    if food_id not in context.available:
        return 0.0
    food = context.available[food_id]
    total = 0.0
    for other_food_id, other_role in chosen:
        if other_food_id not in context.available:
            continue
        other_food = context.available[other_food_id]
        if role == other_role:
            total -= gr._similarity_penalty(food, other_food, role) * 0.12  # noqa: SLF001
            if role == "produce":
                candidate_cluster = _produce_combo_cluster(food)
                other_cluster = _produce_combo_cluster(other_food)
                if candidate_cluster != other_cluster:
                    total += 0.05
                else:
                    total -= 0.04
            elif role == "protein_anchor" and str(food.get("food_family") or "") != str(other_food.get("food_family") or ""):
                total += 0.03
            continue

        roles = {role, other_role}
        if roles == {"protein_anchor", "carb_base"}:
            protein_food = food if role == "protein_anchor" else other_food
            carb_food = food if role == "carb_base" else other_food
            total += min(_protein_density(protein_food) * 0.22 * float(profile["protein_priority"]), 0.07)
            total += min(_food_metric(carb_food, "fiber") / 28.0 * float(profile["fiber_priority"]), 0.05)
        if "produce" in roles:
            produce_food = food if role == "produce" else other_food
            total += min(_food_metric(produce_food, "fiber") / 30.0 * float(profile["fiber_priority"]), 0.04)
            total += min(_food_metric(produce_food, "vitamin_c") / 220.0, 0.04)
            if _produce_combo_cluster(produce_food) == "watery_practical":
                total += 0.02 * float(profile["practicality_priority"])
        if roles == {"calorie_booster", "produce"} and _produce_combo_cluster(food if role == "produce" else other_food) != "fruit":
            total += 0.01
    return total


def _reference_quality_adjustment(
    context: PlannerContext,
    *,
    role: str,
    food_id: str,
    heuristic_reference_food_id: str,
) -> float:
    if not heuristic_reference_food_id or heuristic_reference_food_id not in context.available or food_id not in context.available:
        return 0.0
    if food_id == heuristic_reference_food_id:
        return -0.02

    food = context.available[food_id]
    reference_food = context.available[heuristic_reference_food_id]
    adjustment = 0.05
    if role == "protein_anchor":
        if _protein_density(food) + 0.02 < _protein_density(reference_food):
            adjustment -= 0.08
        if _food_metric(food, "fat") > _food_metric(reference_food, "fat") + 4.0:
            adjustment -= 0.05
    elif role == "carb_base":
        if _food_metric(food, "fiber") + 1.2 < _food_metric(reference_food, "fiber"):
            adjustment -= 0.07
        if int(food.get("commonality_rank") or 999) > int(reference_food.get("commonality_rank") or 999) + 18:
            adjustment -= 0.05
    elif role == "produce":
        if (
            _food_metric(food, "energy_fibre_kcal") > _food_metric(reference_food, "energy_fibre_kcal") + 18.0
            and _food_metric(food, "fiber") + _food_metric(food, "vitamin_c") / 40.0
            < _food_metric(reference_food, "fiber") + _food_metric(reference_food, "vitamin_c") / 40.0
        ):
            adjustment -= 0.06
    return adjustment


def _structured_candidate_terms(
    context: PlannerContext,
    *,
    role: str,
    food_id: str,
    chosen: Sequence[tuple[str, str]],
    heuristic_reference_food_id: str,
) -> dict[str, float]:
    profile = _priority_profile(context)
    nutrient_support = _role_nutrient_support_bonus(
        context,
        role=role,
        food_id=food_id,
        profile=profile,
    )
    complementarity = _pairwise_complementarity_bonus(
        context,
        role=role,
        food_id=food_id,
        chosen=chosen,
        profile=profile,
    )
    reference_adjustment = _reference_quality_adjustment(
        context,
        role=role,
        food_id=food_id,
        heuristic_reference_food_id=heuristic_reference_food_id,
    )
    goal_structure_bonus = _goal_structure_selection_bonus(
        context,
        role=role,
        food_id=food_id,
        chosen=chosen,
    )
    novelty = 0.04 if heuristic_reference_food_id and food_id != heuristic_reference_food_id else -0.01
    practicality = (
        max(float(context.available[food_id].get("budget_score") or 0.0) - 3.0, 0.0) * 0.012 * float(profile["cost_priority"])
        + _prep_score(context.available[food_id]) * 0.015 * float(profile["practicality_priority"])
        + _commonality_bonus(context.available[food_id]) * 0.65
    )
    structured_bonus = nutrient_support + complementarity + reference_adjustment + goal_structure_bonus + novelty + practicality
    return {
        "nutrient_support": round(nutrient_support, 6),
        "complementarity": round(complementarity, 6),
        "reference_adjustment": round(reference_adjustment, 6),
        "goal_structure_bonus": round(goal_structure_bonus, 6),
        "novelty": round(novelty, 6),
        "practicality": round(practicality, 6),
        "structured_bonus": round(structured_bonus, 6),
    }


def _structured_swap_allowed(
    context: PlannerContext,
    *,
    role: str,
    current_food_id: str,
    candidate_food_id: str,
    chosen: Sequence[tuple[str, str]],
) -> bool:
    if current_food_id not in context.available or candidate_food_id not in context.available:
        return False
    if candidate_food_id == current_food_id:
        return False

    profile = _priority_profile(context)
    current_terms = _structured_candidate_terms(
        context,
        role=role,
        food_id=current_food_id,
        chosen=chosen,
        heuristic_reference_food_id=current_food_id,
    )
    candidate_terms = _structured_candidate_terms(
        context,
        role=role,
        food_id=candidate_food_id,
        chosen=chosen,
        heuristic_reference_food_id=current_food_id,
    )
    candidate_food = context.available[candidate_food_id]
    current_food = context.available[current_food_id]
    practicality_gap = (
        _prep_score(candidate_food)
        + float(candidate_food.get("budget_score") or 0.0) * 0.2
        + _commonality_bonus(candidate_food)
    ) - (
        _prep_score(current_food)
        + float(current_food.get("budget_score") or 0.0) * 0.2
        + _commonality_bonus(current_food)
    )
    return (
        float(candidate_terms["structured_bonus"]) + 0.08 >= float(current_terms["structured_bonus"])
        and practicality_gap >= -0.18 * float(profile["practicality_priority"])
    )


def _generate_structured_substitution_seeds(
    context: PlannerContext,
    *,
    model_role_scores: dict[str, dict[str, float]],
    role_rank_maps: dict[str, dict[str, int]],
    heuristic_reference_seed: CandidateSeed | None,
    source_backend: str,
    max_variants: int,
) -> list[CandidateSeed]:
    if heuristic_reference_seed is None or max_variants <= 0:
        return []

    heuristic_reference_by_role = _seed_role_reference_map(heuristic_reference_seed)
    role_options: list[tuple[int, str, list[str]]] = []
    for step_index, (food_id, role) in enumerate(heuristic_reference_seed.chosen):
        chosen_prefix = [entry for index, entry in enumerate(heuristic_reference_seed.chosen) if index < step_index]
        ranked = _rank_model_candidates(
            context,
            role=role,
            model_role_scores=model_role_scores,
            role_rank_maps=role_rank_maps,
            excluded={
                candidate_food_id
                for index, (candidate_food_id, _candidate_role) in enumerate(heuristic_reference_seed.chosen)
                if index != step_index
            },
            chosen=chosen_prefix,
            heuristic_reference_by_role=heuristic_reference_by_role,
        )
        alternatives: list[str] = []
        max_alternatives = 3 if role == "produce" else 2
        for candidate_food_id, _score, _details in ranked:
            if not _structured_swap_allowed(
                context,
                role=role,
                current_food_id=food_id,
                candidate_food_id=candidate_food_id,
                chosen=[entry for index, entry in enumerate(heuristic_reference_seed.chosen) if index != step_index],
            ):
                continue
            alternatives.append(candidate_food_id)
            if len(alternatives) >= max_alternatives:
                break
        if alternatives:
            role_options.append((step_index, role, alternatives))

    if not role_options:
        return []

    role_priority = ("produce", "protein_anchor", "carb_base")
    pair_priority = (("produce", "produce"), ("protein_anchor", "produce"), ("protein_anchor", "carb_base"))
    variants: list[CandidateSeed] = []
    seen_keys: set[tuple[str, ...]] = set()

    def add_variant(chosen_variant: list[tuple[str, str]], source_hint: str) -> None:
        seed = _build_model_seed_from_choices(
            context,
            chosen=chosen_variant,
            model_role_scores=model_role_scores,
            role_rank_maps=role_rank_maps,
            heuristic_reference_by_role=heuristic_reference_by_role,
            source_backend=source_backend,
            source_hint=source_hint,
        )
        key = tuple(food_id for food_id, _selected_role in seed.chosen)
        if key in seen_keys:
            return
        seen_keys.add(key)
        variants.append(seed)

    for role in role_priority:
        for step_index, step_role, alternatives in role_options:
            if step_role != role:
                continue
            for alternative_food_id in alternatives:
                chosen_variant = list(heuristic_reference_seed.chosen)
                chosen_variant[step_index] = (alternative_food_id, step_role)
                add_variant(chosen_variant, f"structured_{step_role}_swap")
                if len(variants) >= max_variants * 2:
                    return sorted(variants, key=_seed_sort_key)[: max_variants * 2]

    for left_role, right_role in pair_priority:
        left_rows = [row for row in role_options if row[1] == left_role]
        right_rows = [row for row in role_options if row[1] == right_role]
        for left_step_index, _left_step_role, left_alternatives in left_rows:
            for right_step_index, _right_step_role, right_alternatives in right_rows:
                if left_step_index == right_step_index:
                    continue
                chosen_variant = list(heuristic_reference_seed.chosen)
                best_pair: tuple[str, str] | None = None
                best_pair_key: tuple[float, int, int, tuple[str, str]] | None = None
                base_without_pair = [
                    entry
                    for index, entry in enumerate(heuristic_reference_seed.chosen)
                    if index not in {left_step_index, right_step_index}
                ]
                for left_food_id in left_alternatives:
                    for right_food_id in right_alternatives:
                        if left_food_id == right_food_id:
                            continue
                        pair_score = (
                            float(model_role_scores[left_role].get(left_food_id, 0.0))
                            + float(model_role_scores[right_role].get(right_food_id, 0.0))
                            + _pairwise_complementarity_bonus(
                                context,
                                role=left_role,
                                food_id=left_food_id,
                                chosen=[*base_without_pair, (right_food_id, right_role)],
                                profile=_priority_profile(context),
                            )
                            + _pairwise_complementarity_bonus(
                                context,
                                role=right_role,
                                food_id=right_food_id,
                                chosen=[*base_without_pair, (left_food_id, left_role)],
                                profile=_priority_profile(context),
                            )
                        )
                        sort_key = (
                            -pair_score,
                            max(int(role_rank_maps[left_role].get(left_food_id, 10_000)), int(role_rank_maps[right_role].get(right_food_id, 10_000))),
                            int(context.available[left_food_id].get("commonality_rank") or 999),
                            (left_food_id, right_food_id),
                        )
                        if best_pair_key is None or sort_key < best_pair_key:
                            best_pair_key = sort_key
                            best_pair = (left_food_id, right_food_id)
                if best_pair is not None:
                    chosen_variant[left_step_index] = (best_pair[0], chosen_variant[left_step_index][1])
                    chosen_variant[right_step_index] = (best_pair[1], chosen_variant[right_step_index][1])
                    add_variant(chosen_variant, f"structured_{left_role}_{right_role}_swap")
                if len(variants) >= max_variants * 3:
                    return sorted(variants, key=_seed_sort_key)[: max_variants * 3]

    return sorted(variants, key=_seed_sort_key)[: max_variants * 3]


def _select_balanced_model_seeds(
    seeds: Sequence[CandidateSeed],
    *,
    heuristic_reference_seed: CandidateSeed | None,
    candidate_count: int,
) -> list[CandidateSeed]:
    sorted_seeds = sorted(seeds, key=_seed_sort_key)
    if heuristic_reference_seed is None:
        return list(sorted_seeds[:candidate_count])

    priority_seeds: list[CandidateSeed] = []
    fallback_seeds: list[CandidateSeed] = []
    heuristic_carb_ids = _seed_role_food_ids(heuristic_reference_seed, "carb_base")
    for seed in sorted_seeds:
        changed_roles = _changed_roles_from_reference(seed, heuristic_reference_seed)
        source_hints = _seed_source_hints(seed)
        same_carb_base = _seed_role_food_ids(seed, "carb_base") == heuristic_carb_ids
        is_priority = any(source_hint.startswith("structured_") for source_hint in source_hints)
        if same_carb_base and changed_roles & {"produce", "protein_anchor"}:
            is_priority = True
        if is_priority:
            priority_seeds.append(seed)
        else:
            fallback_seeds.append(seed)

    selected: list[CandidateSeed] = []
    priority_quota = min(2, candidate_count, len(priority_seeds))
    selected.extend(priority_seeds[:priority_quota])
    for seed in [*priority_seeds[priority_quota:], *fallback_seeds]:
        if seed in selected:
            continue
        selected.append(seed)
        if len(selected) >= candidate_count:
            break
    return selected


def _goal_targeted_model_bonus(
    context: PlannerContext,
    *,
    role: str,
    food_id: str,
    heuristic_reference_food_id: str,
    chosen: Sequence[tuple[str, str]] = (),
) -> float:
    if context.goal_profile not in {"fat_loss", "maintenance"} or food_id not in context.available:
        return 0.0

    food = context.available[food_id]
    reference_food = (
        context.available[heuristic_reference_food_id]
        if heuristic_reference_food_id and heuristic_reference_food_id in context.available
        else None
    )
    bonus = 0.0

    if context.goal_profile == "fat_loss":
        if role == "protein_anchor":
            bonus += min(_protein_density(food) * 0.45, 0.14)
            if _food_metric(food, "fat") <= 2.5:
                bonus += 0.05
            if reference_food is not None and _protein_density(food) + 0.015 < _protein_density(reference_food):
                bonus -= 0.08
            if reference_food is not None and _food_metric(food, "fat") > _food_metric(reference_food, "fat") + 3.0:
                bonus -= 0.08
        elif role == "carb_base":
            if str(food.get("prep_level") or "") in {"none", "low"}:
                bonus += 0.04
            bonus += max(_food_metric(food, "fiber") - 5.0, 0.0) * 0.008
            bonus += max(float(food.get("budget_score") or 0.0) - 3.0, 0.0) * 0.025
            if int(food.get("commonality_rank") or 999) <= 15:
                bonus += 0.04
            elif int(food.get("commonality_rank") or 999) >= 30:
                bonus -= 0.05
            if reference_food is not None:
                if food_id == heuristic_reference_food_id:
                    bonus += 0.08
                if float(food.get("budget_score") or 0.0) + 0.5 < float(reference_food.get("budget_score") or 0.0):
                    bonus -= 0.08
                if int(food.get("commonality_rank") or 999) > int(reference_food.get("commonality_rank") or 999) + 12:
                    bonus -= 0.08
                if _food_metric(food, "fiber") + 1.0 < _food_metric(reference_food, "fiber"):
                    bonus -= 0.06
        elif role == "produce":
            if _food_metric(food, "energy_fibre_kcal") <= 35.0:
                bonus += 0.04
            bonus += min(_food_metric(food, "fiber") / 20.0, 0.06)
            bonus += min(_food_metric(food, "vitamin_c") / 120.0, 0.06)
            bonus += _produce_combo_bonus(
                context,
                food_id=food_id,
                chosen=chosen,
            )
    elif context.goal_profile == "maintenance":
        if role == "protein_anchor":
            if str(food.get("prep_level") or "") in {"none", "low"}:
                bonus += 0.04
            if int(food.get("commonality_rank") or 999) <= 20:
                bonus += 0.03
            if _protein_density(food) >= 0.18:
                bonus += 0.04
        elif role == "carb_base":
            if reference_food is not None and food_id == heuristic_reference_food_id:
                bonus += 0.1
            if str(food.get("prep_level") or "") == "none":
                bonus += 0.05
            elif str(food.get("prep_level") or "") == "low":
                bonus += 0.03
            if float(food.get("budget_score") or 0.0) >= 4.0:
                bonus += 0.03
            if int(food.get("commonality_rank") or 999) <= 20:
                bonus += 0.03
            elif int(food.get("commonality_rank") or 999) >= 30:
                bonus -= 0.04
            if reference_food is not None and int(food.get("commonality_rank") or 999) > int(reference_food.get("commonality_rank") or 999) + 15:
                bonus -= 0.04
        elif role == "produce":
            if str(food.get("prep_level") or "") in {"none", "low"}:
                bonus += 0.03
            if int(food.get("commonality_rank") or 999) <= 20:
                bonus += 0.02
            if _food_metric(food, "fiber") >= 2.0:
                bonus += 0.02
            if float(food.get("budget_score") or 0.0) >= 4.0:
                bonus += 0.02

    return bonus


def _goal_targeted_swap_allowed(
    context: PlannerContext,
    *,
    role: str,
    current_food_id: str,
    candidate_food_id: str,
) -> bool:
    if current_food_id not in context.available or candidate_food_id not in context.available:
        return False
    if candidate_food_id == current_food_id:
        return False

    current_food = context.available[current_food_id]
    candidate_food = context.available[candidate_food_id]
    goal_profile = context.goal_profile
    if goal_profile == "generic_balanced":
        return True

    current_category = _protein_anchor_category(current_food) if role == "protein_anchor" else ""
    candidate_category = _protein_anchor_category(candidate_food) if role == "protein_anchor" else ""

    if goal_profile == "fat_loss":
        if role == "protein_anchor":
            return (
                _protein_density(candidate_food) >= (_protein_density(current_food) * 0.88)
                and _food_metric(candidate_food, "fat") <= (_food_metric(current_food, "fat") + 3.5)
            )
        if role == "carb_base":
            return (
                _food_metric(candidate_food, "fiber") + 1.0 >= _food_metric(current_food, "fiber")
                and _food_metric(candidate_food, "protein") + 0.5 >= _food_metric(current_food, "protein")
                and float(candidate_food.get("budget_score") or 0.0) + 0.5 >= float(current_food.get("budget_score") or 0.0)
                and int(candidate_food.get("commonality_rank") or 999) <= int(current_food.get("commonality_rank") or 999) + 12
            )
        if role == "produce":
            return (
                _food_metric(candidate_food, "energy_fibre_kcal") <= (_food_metric(current_food, "energy_fibre_kcal") + 14.0)
                and (
                    _food_metric(candidate_food, "fiber") + 0.7 >= _food_metric(current_food, "fiber")
                    or _food_metric(candidate_food, "vitamin_c") + 10.0 >= _food_metric(current_food, "vitamin_c")
                    or _food_metric(candidate_food, "protein") >= _food_metric(current_food, "protein")
                )
            )
        if role == "calorie_booster":
            return False
    if goal_profile == "maintenance":
        if role == "protein_anchor":
            return (
                _protein_density(candidate_food) >= (_protein_density(current_food) * 0.8)
                and _prep_score(candidate_food) + 1.0 >= _prep_score(current_food)
                and int(candidate_food.get("commonality_rank") or 999) <= int(current_food.get("commonality_rank") or 999) + 18
            )
        if role == "carb_base":
            return False
        if role == "produce":
            return (
                _prep_score(candidate_food) + 1.0 >= _prep_score(current_food)
                and int(candidate_food.get("commonality_rank") or 999) <= int(current_food.get("commonality_rank") or 999) + 25
                and (
                    float(candidate_food.get("budget_score") or 0.0) + 1.0 >= float(current_food.get("budget_score") or 0.0)
                    or _food_metric(candidate_food, "fiber") + 0.5 >= _food_metric(current_food, "fiber")
                )
            )
        if role == "calorie_booster":
            return str(candidate_food.get("generic_food_id") or "") in {"olive_oil", "peanut_butter", "nuts"}
    if goal_profile == "muscle_gain":
        if role == "protein_anchor":
            return (
                _protein_density(candidate_food) + 0.01 >= (_protein_density(current_food) * 0.78)
                and candidate_category != "legume"
                and candidate_category != "nut_butter"
            )
        if role == "carb_base":
            return str(candidate_food.get("generic_food_id") or "") in {"oats", "pasta", "bagel", "potatoes", "wholemeal_bread", "sweet_potatoes", "rice"}
        if role == "produce":
            return _food_metric(candidate_food, "energy_fibre_kcal") <= (_food_metric(current_food, "energy_fibre_kcal") + 35.0)
        if role == "calorie_booster":
            return str(candidate_food.get("generic_food_id") or "") in {"olive_oil", "peanut_butter", "nuts", "almond_butter", "cheese"}
    if goal_profile == "high_protein_vegetarian":
        if role == "protein_anchor":
            return (
                candidate_category in {"egg", "dairy", "soy"}
                and candidate_category != "legume"
                and candidate_category != "nut_butter"
            )
        if role == "carb_base":
            return str(candidate_food.get("generic_food_id") or "") in {"wholemeal_bread", "quinoa", "oats", "bagel", "rice"}
        if role == "produce":
            return _food_metric(candidate_food, "vitamin_c") + _food_metric(candidate_food, "fiber") >= (
                _food_metric(current_food, "vitamin_c") + _food_metric(current_food, "fiber") - 15.0
            )
        if role == "calorie_booster":
            return str(candidate_food.get("generic_food_id") or "") in {"olive_oil", "peanut_butter"}
    if goal_profile == "budget_friendly_healthy":
        if role == "protein_anchor":
            return (
                float(candidate_food.get("budget_score") or 0.0) + 0.5 >= float(current_food.get("budget_score") or 0.0)
                and candidate_category not in {"rich_animal", "animal"}
            )
        if role == "carb_base":
            return str(candidate_food.get("generic_food_id") or "") in {"rice", "pasta", "potatoes", "wholemeal_bread", "oats"}
        if role == "produce":
            return (
                float(candidate_food.get("budget_score") or 0.0) + 0.5 >= float(current_food.get("budget_score") or 0.0)
                and int(candidate_food.get("commonality_rank") or 999) <= int(current_food.get("commonality_rank") or 999) + 18
            )
        if role == "calorie_booster":
            return str(candidate_food.get("generic_food_id") or "") in {"olive_oil", "peanut_butter"}
    return True


def _generate_goal_targeted_substitution_seeds(
    context: PlannerContext,
    *,
    model_role_scores: dict[str, dict[str, float]],
    role_rank_maps: dict[str, dict[str, int]],
    heuristic_reference_seed: CandidateSeed | None,
    source_backend: str,
    max_variants: int,
) -> list[CandidateSeed]:
    if heuristic_reference_seed is None or max_variants <= 0 or context.goal_profile == "generic_balanced":
        return []

    heuristic_reference_by_role = _seed_role_reference_map(heuristic_reference_seed)
    role_options: list[tuple[int, str, list[str]]] = []
    for step_index, (food_id, role) in enumerate(heuristic_reference_seed.chosen):
        ranked = _rank_model_candidates(
            context,
            role=role,
            model_role_scores=model_role_scores,
            role_rank_maps=role_rank_maps,
            excluded={
                candidate_food_id
                for index, (candidate_food_id, _candidate_role) in enumerate(heuristic_reference_seed.chosen)
                if index != step_index
            },
            chosen=[entry for index, entry in enumerate(heuristic_reference_seed.chosen) if index < step_index],
            heuristic_reference_by_role=heuristic_reference_by_role,
        )
        alternatives: list[str] = []
        max_alternatives = {
            "muscle_gain": {"protein_anchor": 2, "carb_base": 2, "produce": 2},
            "fat_loss": {"protein_anchor": 2, "carb_base": 2, "produce": 3},
            "maintenance": {"protein_anchor": 2, "carb_base": 1, "produce": 2},
            "high_protein_vegetarian": {"protein_anchor": 3, "carb_base": 2, "produce": 2},
            "budget_friendly_healthy": {"protein_anchor": 3, "carb_base": 2, "produce": 2},
        }.get(context.goal_profile, {}).get(role, 1)
        for candidate_food_id, _score, _details in ranked:
            if not _goal_targeted_swap_allowed(
                context,
                role=role,
                current_food_id=food_id,
                candidate_food_id=candidate_food_id,
            ):
                continue
            alternatives.append(candidate_food_id)
            if len(alternatives) >= max_alternatives:
                break
        if context.goal_profile == "fat_loss" and role == "produce" and alternatives:
            other_produce_ids = [
                candidate_food_id
                for index, (candidate_food_id, candidate_role) in enumerate(heuristic_reference_seed.chosen)
                if candidate_role == "produce" and index != step_index
            ]
            alternatives = sorted(
                alternatives,
                key=lambda candidate_food_id: (
                    -(
                        float(model_role_scores[role].get(candidate_food_id, 0.0))
                        + _produce_combo_bonus(
                            context,
                            food_id=candidate_food_id,
                            chosen=[(other_food_id, "produce") for other_food_id in other_produce_ids],
                        )
                    ),
                    int(role_rank_maps[role].get(candidate_food_id, 10_000)),
                    candidate_food_id,
                ),
            )
        if alternatives:
            role_options.append((step_index, role, alternatives))

    if not role_options:
        return []

    role_priority = {
        "muscle_gain": ("protein_anchor", "carb_base", "produce"),
        "fat_loss": ("produce", "protein_anchor", "carb_base"),
        "maintenance": ("produce", "protein_anchor", "carb_base"),
        "high_protein_vegetarian": ("protein_anchor", "produce", "carb_base"),
        "budget_friendly_healthy": ("protein_anchor", "carb_base", "produce"),
    }[context.goal_profile]
    pair_priority = {
        "muscle_gain": (("protein_anchor", "protein_anchor"), ("protein_anchor", "carb_base"), ("produce", "produce")),
        "fat_loss": (("produce", "produce"), ("protein_anchor", "produce")),
        "maintenance": (("produce", "produce"), ("protein_anchor", "produce")),
        "high_protein_vegetarian": (("protein_anchor", "protein_anchor"), ("protein_anchor", "produce"), ("produce", "produce")),
        "budget_friendly_healthy": (("protein_anchor", "protein_anchor"), ("protein_anchor", "carb_base"), ("produce", "produce")),
    }[context.goal_profile]

    variants: list[CandidateSeed] = []
    seen_keys: set[tuple[str, ...]] = set()

    def add_variant(chosen: list[tuple[str, str]], source_hint: str) -> None:
        seed = _build_model_seed_from_choices(
            context,
            chosen=chosen,
            model_role_scores=model_role_scores,
            role_rank_maps=role_rank_maps,
            heuristic_reference_by_role=heuristic_reference_by_role,
            source_backend=source_backend,
            source_hint=source_hint,
        )
        key = tuple(food_id for food_id, _selected_role in seed.chosen)
        if key in seen_keys:
            return
        seen_keys.add(key)
        variants.append(seed)

    for role in role_priority:
        for step_index, step_role, alternatives in role_options:
            if step_role != role:
                continue
            for alternative_food_id in alternatives:
                chosen = list(heuristic_reference_seed.chosen)
                chosen[step_index] = (alternative_food_id, step_role)
                add_variant(chosen, f"goal_targeted_{context.goal_profile}_{step_role}_swap")
                if len(variants) >= max_variants * 2:
                    return sorted(variants, key=_seed_sort_key)[: max_variants * 2]

    for left_role, right_role in pair_priority:
        left_rows = [row for row in role_options if row[1] == left_role]
        right_rows = [row for row in role_options if row[1] == right_role]
        for left_step_index, _left_step_role, left_alternatives in left_rows:
            for right_step_index, _right_step_role, right_alternatives in right_rows:
                if left_step_index == right_step_index:
                    continue
                chosen = list(heuristic_reference_seed.chosen)
                selected_left_food_id = left_alternatives[0]
                selected_right_food_id = right_alternatives[0]
                if context.goal_profile == "fat_loss" and left_role == "produce" and right_role == "produce":
                    baseline_produce_ids = [
                        food_id
                        for food_id, candidate_role in heuristic_reference_seed.chosen
                        if candidate_role == "produce"
                    ]
                    best_pair: tuple[str, str] | None = None
                    best_pair_score: tuple[float, int, tuple[str, str]] | None = None
                    for left_food_id in left_alternatives:
                        for right_food_id in right_alternatives:
                            if left_food_id == right_food_id:
                                continue
                            pair_score = (
                                float(model_role_scores["produce"].get(left_food_id, 0.0))
                                + float(model_role_scores["produce"].get(right_food_id, 0.0))
                                + _fat_loss_produce_pair_bonus(
                                    context,
                                    left_food_id=left_food_id,
                                    right_food_id=right_food_id,
                                    baseline_produce_ids=baseline_produce_ids,
                                )
                            )
                            sort_key = (-pair_score, max(role_rank_maps["produce"].get(left_food_id, 10_000), role_rank_maps["produce"].get(right_food_id, 10_000)), (left_food_id, right_food_id))
                            if best_pair_score is None or sort_key < best_pair_score:
                                best_pair_score = sort_key
                                best_pair = (left_food_id, right_food_id)
                    if best_pair is not None:
                        selected_left_food_id, selected_right_food_id = best_pair
                chosen[left_step_index] = (selected_left_food_id, chosen[left_step_index][1])
                chosen[right_step_index] = (selected_right_food_id, chosen[right_step_index][1])
                add_variant(chosen, f"goal_targeted_{context.goal_profile}_{left_role}_{right_role}_swap")
                if len(variants) >= max_variants * 3:
                    return sorted(variants, key=_seed_sort_key)[: max_variants * 3]

    return sorted(variants, key=_seed_sort_key)[: max_variants * 3]


def _select_goal_balanced_model_seeds(
    context: PlannerContext,
    seeds: Sequence[CandidateSeed],
    *,
    heuristic_reference_seed: CandidateSeed | None,
    candidate_count: int,
) -> list[CandidateSeed]:
    sorted_seeds = sorted(seeds, key=_seed_sort_key)
    if context.goal_profile == "generic_balanced" or heuristic_reference_seed is None:
        return list(sorted_seeds[:candidate_count])

    priority_seeds: list[CandidateSeed] = []
    fallback_seeds: list[CandidateSeed] = []
    heuristic_carb_ids = _seed_role_food_ids(heuristic_reference_seed, "carb_base")
    for seed in sorted_seeds:
        changed_roles = _changed_roles_from_reference(seed, heuristic_reference_seed)
        source_hints = _seed_source_hints(seed)
        same_carb_base = _seed_role_food_ids(seed, "carb_base") == heuristic_carb_ids
        is_priority = any(source_hint.startswith("goal_targeted_") for source_hint in source_hints)
        if same_carb_base and changed_roles & {"produce", "protein_anchor"}:
            is_priority = True
        if context.goal_profile in {"muscle_gain", "high_protein_vegetarian", "budget_friendly_healthy"} and changed_roles & {"protein_anchor", "carb_base"}:
            is_priority = True
        if is_priority:
            priority_seeds.append(seed)
        else:
            fallback_seeds.append(seed)

    selected: list[CandidateSeed] = []
    priority_quota = min(
        3 if context.goal_profile in {"muscle_gain", "high_protein_vegetarian", "budget_friendly_healthy"} else 2,
        candidate_count,
        len(priority_seeds),
    )
    selected.extend(priority_seeds[:priority_quota])
    for seed in [*priority_seeds[priority_quota:], *fallback_seeds]:
        if seed in selected:
            continue
        selected.append(seed)
        if len(selected) >= candidate_count:
            break
    return selected


def _generate_candidate_seeds(context: PlannerContext, candidate_count: int) -> list[CandidateSeed]:
    beam_width = max(candidate_count * 4, 8)
    branch_limits = {
        "protein_anchor": 3,
        "carb_base": 3,
        "produce": 4,
    }
    if context.goal_profile in {"budget_friendly_healthy", "high_protein_vegetarian", "muscle_gain"}:
        branch_limits["protein_anchor"] = 4
    if context.goal_profile in {"muscle_gain", "budget_friendly_healthy"}:
        branch_limits["carb_base"] = 4
    if context.goal_profile == "fat_loss":
        branch_limits["produce"] = 5
    seeds = [
        CandidateSeed(
            chosen=[],
            excluded=set(),
            selection_trace=[],
            heuristic_selection_score=0.0,
            generator_score=0.0,
            source="heuristic",
            source_backend="heuristic",
        )
    ]
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
                        generator_score=seed.generator_score,
                        source=seed.source,
                        source_backend=seed.source_backend,
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
                                "candidate_source": "heuristic",
                            },
                        ],
                        heuristic_selection_score=seed.heuristic_selection_score + adjusted_score,
                        generator_score=seed.generator_score + adjusted_score,
                        source="heuristic",
                        source_backend="heuristic",
                    )
                )

        deduped: dict[tuple[str, ...], CandidateSeed] = {}
        for seed in sorted(expanded, key=_seed_sort_key):
            key = tuple(food_id for food_id, _role in seed.chosen)
            if key not in deduped:
                deduped[key] = seed
        seeds = list(deduped.values())[:beam_width]

    return [seed for seed in seeds if seed.chosen][:candidate_count]


def _candidate_context_features(context: PlannerContext) -> dict[str, object]:
    return model_candidate_features.build_context_features(
        protein_target_g=context.protein_target_g,
        calorie_target_kcal=context.calorie_target_kcal,
        preferences=context.preferences,
        nutrition_targets=context.nutrition_targets,
        days=context.days,
        shopping_mode=context.shopping_mode,
        price_context=context.price_context,
        pantry_items=sorted(context.pantry_items),
        nearby_store_count=context.nearby_store_count,
        available_food_count=len(context.available),
        goal_profile=context.goal_profile,
        basket_policy=context.basket_policy,
    )


def _model_role_score_maps(
    context: PlannerContext,
    bundle: dict[str, object],
) -> tuple[dict[str, dict[str, float]], dict[str, dict[str, int]]]:
    context_features = _candidate_context_features(context)
    role_rank_maps = {
        role: {food_id: index + 1 for index, food_id in enumerate(context.role_orders[role])}
        for role in model_candidate_features.ROLE_LABELS
    }
    role_scores: dict[str, dict[str, float]] = {role: {} for role in model_candidate_features.ROLE_LABELS}
    for role in model_candidate_features.ROLE_LABELS:
        rows: list[dict[str, object]] = []
        food_ids: list[str] = []
        for food_id in context.role_orders[role]:
            if food_id not in context.role_scores[role]:
                continue
            food = context.available[food_id]
            rows.append(
                model_candidate_features.build_food_role_features(
                    food=food,
                    role=role,
                    context_features=context_features,
                    pantry_items=sorted(context.pantry_items),
                    heuristic_role_score=float(context.role_scores[role][food_id]),
                    heuristic_role_rank=int(role_rank_maps[role].get(food_id, len(role_rank_maps[role]) + 1)),
                )
            )
            food_ids.append(food_id)
        probabilities = model_candidate_generator.score_feature_rows(bundle, rows)
        for food_id, probability in zip(food_ids, probabilities, strict=True):
            role_scores[role][food_id] = float(probability)
    return role_scores, role_rank_maps


def _rank_model_candidates(
    context: PlannerContext,
    *,
    role: str,
    model_role_scores: dict[str, dict[str, float]],
    role_rank_maps: dict[str, dict[str, int]],
    excluded: set[str],
    chosen: list[tuple[str, str]],
    heuristic_reference_by_role: Mapping[tuple[str, int], str] | None = None,
) -> list[tuple[str, float, dict[str, object]]]:
    role_occurrence_index = sum(1 for _food_id, chosen_role in chosen if chosen_role == role)
    heuristic_reference_food_id = (
        str(heuristic_reference_by_role.get((role, role_occurrence_index)) or "")
        if heuristic_reference_by_role is not None
        else ""
    )
    best_model_probability = max(model_role_scores[role].values(), default=0.0)
    best_heuristic_role_score = max(context.role_scores[role].values(), default=0.0)
    role_window = {
        "protein_anchor": 0.16,
        "carb_base": 0.18,
        "produce": 0.2,
        "calorie_booster": 0.14,
    }[role]
    heuristic_window = gr._diversity_window(role, context.preferences) + 0.75  # noqa: SLF001
    preferred_ids = gr._goal_template_ids_for_pick(context.goal_profile, role, chosen, context.available)  # noqa: SLF001
    preferred_rank = {food_id: index for index, food_id in enumerate(preferred_ids)}

    ranked_rows: list[tuple[float, int, int, str, str, float, dict[str, object]]] = []
    for food_id, model_probability in model_role_scores[role].items():
        if food_id in excluded or food_id not in context.available:
            continue
        heuristic_role_score = float(context.role_scores[role].get(food_id, 0.0))
        if (
            best_model_probability > 0
            and (best_model_probability - float(model_probability)) > role_window
            and (best_heuristic_role_score - heuristic_role_score) > heuristic_window
        ):
            continue
        diversity_penalty = gr._role_diversity_penalty(food_id, role, context.available, chosen)  # noqa: SLF001
        heuristic_rank = int(role_rank_maps[role].get(food_id, 10_000))
        heuristic_bonus = max(0.0, heuristic_role_score) * 0.012

        novelty_bonus = 0.0
        if heuristic_reference_food_id:
            if food_id != heuristic_reference_food_id:
                novelty_bonus += {
                    "protein_anchor": 0.09,
                    "carb_base": 0.08,
                    "produce": 0.11,
                    "calorie_booster": 0.06,
                }[role]
            else:
                novelty_bonus -= {
                    "protein_anchor": 0.07,
                    "carb_base": 0.06,
                    "produce": 0.08,
                    "calorie_booster": 0.04,
                }[role]
        if heuristic_rank >= 3:
            novelty_bonus += {
                "protein_anchor": 0.06,
                "carb_base": 0.06,
                "produce": 0.08,
                "calorie_booster": 0.05,
            }[role]
        if heuristic_rank <= 2:
            novelty_bonus -= {
                "protein_anchor": 0.04,
                "carb_base": 0.03,
                "produce": 0.04,
                "calorie_booster": 0.02,
            }[role]
        if heuristic_rank > 12:
            novelty_bonus -= {
                "protein_anchor": 0.04,
                "carb_base": 0.03,
                "produce": 0.04,
                "calorie_booster": 0.03,
            }[role]
        structured_terms = _structured_candidate_terms(
            context,
            role=role,
            food_id=food_id,
            chosen=chosen,
            heuristic_reference_food_id=heuristic_reference_food_id,
        )
        structured_bonus = float(structured_terms["structured_bonus"])
        template_bonus = 0.0
        if food_id in preferred_rank:
            template_bonus = max(0.05, 0.22 - (0.03 * preferred_rank[food_id]))
        adjusted_score = (
            float(model_probability)
            + heuristic_bonus
            + novelty_bonus
            + structured_bonus
            + template_bonus
            - (diversity_penalty * 0.08)
        )
        score_details = {
            "model_probability": round(float(model_probability), 6),
            "heuristic_role_score": round(heuristic_role_score, 6),
            "heuristic_role_rank": heuristic_rank,
            "novelty_bonus": round(novelty_bonus, 6),
            "structured_bonus": round(structured_bonus, 6),
            "structured_terms": {key: float(value) for key, value in structured_terms.items()},
            "template_bonus": round(template_bonus, 6),
            "goal_bonus": round(structured_bonus, 6),
            "diversity_penalty": round(float(diversity_penalty), 6),
            "heuristic_reference_food_id": heuristic_reference_food_id or None,
            "differs_from_best_heuristic_role": bool(heuristic_reference_food_id and food_id != heuristic_reference_food_id),
            "adjusted_score": round(adjusted_score, 6),
        }
        ranked_rows.append(
            (
                -adjusted_score,
                heuristic_rank,
                int(context.available[food_id]["commonality_rank"]),
                str(context.available[food_id]["display_name"]),
                food_id,
                adjusted_score,
                score_details,
            )
        )
    ranked_rows.sort()
    short_list = ranked_rows[: {"protein_anchor": 10, "carb_base": 10, "produce": 12, "calorie_booster": 8}[role]]
    return [(str(row[4]), float(row[5]), dict(row[6])) for row in short_list]


def _build_model_seed_from_choices(
    context: PlannerContext,
    *,
    chosen: list[tuple[str, str]],
    model_role_scores: dict[str, dict[str, float]],
    role_rank_maps: dict[str, dict[str, int]],
    heuristic_reference_by_role: Mapping[tuple[str, int], str],
    source_backend: str,
    source_hint: str,
) -> CandidateSeed:
    built_chosen: list[tuple[str, str]] = []
    excluded: set[str] = set()
    selection_trace: list[dict[str, object]] = []
    heuristic_selection_score = 0.0
    generator_score = 0.0

    for step_index, (food_id, role) in enumerate(chosen):
        ranked = _rank_model_candidates(
            context,
            role=role,
            model_role_scores=model_role_scores,
            role_rank_maps=role_rank_maps,
            excluded=excluded,
            chosen=built_chosen,
            heuristic_reference_by_role=heuristic_reference_by_role,
        )
        ranked_map = {candidate_food_id: (score, details) for candidate_food_id, score, details in ranked}
        adjusted_model_score, score_details = ranked_map.get(
            food_id,
            (
                float(model_role_scores[role].get(food_id, 0.0)),
                {
                    "model_probability": round(float(model_role_scores[role].get(food_id, 0.0)), 6),
                    "heuristic_role_score": round(float(context.role_scores[role].get(food_id, 0.0)), 6),
                    "heuristic_role_rank": int(role_rank_maps[role].get(food_id, 10_000)),
                    "novelty_bonus": 0.0,
                    "structured_bonus": 0.0,
                    "structured_terms": {},
                    "template_bonus": 0.0,
                    "goal_bonus": 0.0,
                    "diversity_penalty": 0.0,
                    "heuristic_reference_food_id": heuristic_reference_by_role.get((role, sum(1 for _existing_food_id, existing_role in built_chosen if existing_role == role))),
                    "differs_from_best_heuristic_role": False,
                    "adjusted_score": round(float(model_role_scores[role].get(food_id, 0.0)), 6),
                },
            ),
        )
        heuristic_score = _selection_score_for_food(context, role=role, food_id=food_id, chosen=built_chosen)
        selection_trace.append(
            {
                "step_index": step_index,
                "role": role,
                "food_id": food_id,
                "display_name": str(context.available[food_id]["display_name"]),
                "choice_rank": next(
                    (index for index, (candidate_food_id, _score, _details) in enumerate(ranked) if candidate_food_id == food_id),
                    None,
                ),
                "selection_score": round(adjusted_model_score, 6),
                "model_probability": score_details["model_probability"],
                "heuristic_role_score": score_details["heuristic_role_score"],
                "heuristic_role_rank": score_details["heuristic_role_rank"],
                "novelty_bonus": score_details["novelty_bonus"],
                "structured_bonus": score_details.get("structured_bonus", score_details.get("goal_bonus", 0.0)),
                "structured_terms": dict(score_details.get("structured_terms") or {}),
                "goal_bonus": score_details.get("goal_bonus", score_details.get("structured_bonus", 0.0)),
                "heuristic_reference_food_id": score_details["heuristic_reference_food_id"],
                "differs_from_best_heuristic_role": bool(score_details["differs_from_best_heuristic_role"]),
                "candidate_source": "model",
                "source_hint": source_hint,
            }
        )
        heuristic_selection_score += heuristic_score
        generator_score += adjusted_model_score
        built_chosen.append((food_id, role))
        excluded.add(food_id)

    return CandidateSeed(
        chosen=built_chosen,
        excluded=excluded,
        selection_trace=selection_trace,
        heuristic_selection_score=heuristic_selection_score,
        generator_score=generator_score,
        source="model",
        source_backend=source_backend,
    )


def _generate_model_substitution_seeds(
    context: PlannerContext,
    *,
    model_role_scores: dict[str, dict[str, float]],
    role_rank_maps: dict[str, dict[str, int]],
    heuristic_reference_seed: CandidateSeed | None,
    source_backend: str,
    max_variants: int,
) -> list[CandidateSeed]:
    if heuristic_reference_seed is None or not heuristic_reference_seed.chosen or max_variants <= 0:
        return []

    heuristic_reference_by_role = _seed_role_reference_map(heuristic_reference_seed)
    alternative_picks: list[tuple[int, str, str]] = []
    for step_index, (food_id, role) in enumerate(heuristic_reference_seed.chosen):
        alternative_ranked = _rank_model_candidates(
            context,
            role=role,
            model_role_scores=model_role_scores,
            role_rank_maps=role_rank_maps,
            excluded={candidate_food_id for index, (candidate_food_id, _candidate_role) in enumerate(heuristic_reference_seed.chosen) if index != step_index},
            chosen=[entry for index, entry in enumerate(heuristic_reference_seed.chosen) if index < step_index],
            heuristic_reference_by_role=heuristic_reference_by_role,
        )
        alternative_food_id = next(
            (
                candidate_food_id
                for candidate_food_id, _score, details in alternative_ranked
                if candidate_food_id != food_id and bool(details.get("differs_from_best_heuristic_role"))
            ),
            None,
        )
        if alternative_food_id is not None:
            alternative_picks.append((step_index, role, alternative_food_id))

    variants: list[CandidateSeed] = []
    seen_keys: set[tuple[str, ...]] = set()
    for step_index, _role, alternative_food_id in alternative_picks:
        chosen = list(heuristic_reference_seed.chosen)
        chosen[step_index] = (alternative_food_id, chosen[step_index][1])
        seed = _build_model_seed_from_choices(
            context,
            chosen=chosen,
            model_role_scores=model_role_scores,
            role_rank_maps=role_rank_maps,
            heuristic_reference_by_role=heuristic_reference_by_role,
            source_backend=source_backend,
            source_hint="heuristic_substitution",
        )
        key = tuple(food_id for food_id, _selected_role in seed.chosen)
        if key not in seen_keys:
            seen_keys.add(key)
            variants.append(seed)

    for left_index in range(len(alternative_picks)):
        if len(variants) >= max_variants * 2:
            break
        for right_index in range(left_index + 1, len(alternative_picks)):
            left_step_index, _left_role, left_food_id = alternative_picks[left_index]
            right_step_index, _right_role, right_food_id = alternative_picks[right_index]
            chosen = list(heuristic_reference_seed.chosen)
            chosen[left_step_index] = (left_food_id, chosen[left_step_index][1])
            chosen[right_step_index] = (right_food_id, chosen[right_step_index][1])
            seed = _build_model_seed_from_choices(
                context,
                chosen=chosen,
                model_role_scores=model_role_scores,
                role_rank_maps=role_rank_maps,
                heuristic_reference_by_role=heuristic_reference_by_role,
                source_backend=source_backend,
                source_hint="heuristic_double_substitution",
            )
            key = tuple(food_id for food_id, _selected_role in seed.chosen)
            if key not in seen_keys:
                seen_keys.add(key)
                variants.append(seed)
            if len(variants) >= max_variants * 2:
                break

    return sorted(variants, key=_seed_sort_key)[: max_variants * 2]


def _generate_model_candidate_seeds(
    context: PlannerContext,
    *,
    bundle: dict[str, object],
    candidate_count: int,
    source_backend: str,
    heuristic_reference_seed: CandidateSeed | None = None,
) -> list[CandidateSeed]:
    beam_width = max(candidate_count * 8, 12)
    branch_limits = {
        "protein_anchor": 4,
        "carb_base": 4,
        "produce": 5,
    }
    if context.goal_profile in {"budget_friendly_healthy", "high_protein_vegetarian", "muscle_gain"}:
        branch_limits["protein_anchor"] = 5
    if context.goal_profile in {"muscle_gain", "budget_friendly_healthy"}:
        branch_limits["carb_base"] = 5
    if context.goal_profile == "fat_loss":
        branch_limits["produce"] = 6
    model_role_scores, role_rank_maps = _model_role_score_maps(context, bundle)
    heuristic_reference_by_role = _seed_role_reference_map(heuristic_reference_seed)
    seeds = [
        CandidateSeed(
            chosen=[],
            excluded=set(),
            selection_trace=[],
            heuristic_selection_score=0.0,
            generator_score=0.0,
            source="model",
            source_backend=source_backend,
        )
    ]
    for step_index, role in enumerate(_candidate_role_sequence(context)):
        expanded: list[CandidateSeed] = []
        for seed in seeds:
            ranked = _rank_model_candidates(
                context,
                role=role,
                model_role_scores=model_role_scores,
                role_rank_maps=role_rank_maps,
                excluded=seed.excluded,
                chosen=seed.chosen,
                heuristic_reference_by_role=heuristic_reference_by_role,
            )
            if not ranked:
                expanded.append(
                    CandidateSeed(
                        chosen=list(seed.chosen),
                        excluded=set(seed.excluded),
                        selection_trace=list(seed.selection_trace),
                        heuristic_selection_score=seed.heuristic_selection_score,
                        generator_score=seed.generator_score,
                        source=seed.source,
                        source_backend=seed.source_backend,
                    )
                )
                continue
            for choice_index, (food_id, adjusted_model_score, score_details) in enumerate(ranked[: branch_limits[role]]):
                heuristic_score = _selection_score_for_food(context, role=role, food_id=food_id, chosen=seed.chosen)
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
                                "selection_score": round(adjusted_model_score, 6),
                                "model_probability": score_details["model_probability"],
                                "heuristic_role_score": score_details["heuristic_role_score"],
                                "heuristic_role_rank": score_details["heuristic_role_rank"],
                                "novelty_bonus": score_details["novelty_bonus"],
                                "goal_bonus": score_details["goal_bonus"],
                                "heuristic_reference_food_id": score_details["heuristic_reference_food_id"],
                                "differs_from_best_heuristic_role": bool(score_details["differs_from_best_heuristic_role"]),
                                "candidate_source": "model",
                                "source_hint": "beam_search",
                            },
                        ],
                        heuristic_selection_score=seed.heuristic_selection_score + heuristic_score,
                        generator_score=seed.generator_score + adjusted_model_score,
                        source="model",
                        source_backend=source_backend,
                    )
                )
        deduped: dict[tuple[str, ...], CandidateSeed] = {}
        for seed in sorted(expanded, key=_seed_sort_key):
            key = tuple(food_id for food_id, _role in seed.chosen)
            if key not in deduped:
                deduped[key] = seed
        seeds = list(deduped.values())[:beam_width]

    substitution_variants = _generate_model_substitution_seeds(
        context,
        model_role_scores=model_role_scores,
        role_rank_maps=role_rank_maps,
        heuristic_reference_seed=heuristic_reference_seed,
        source_backend=source_backend,
        max_variants=max(2, candidate_count),
    )
    goal_targeted_variants = _generate_goal_targeted_substitution_seeds(
        context,
        model_role_scores=model_role_scores,
        role_rank_maps=role_rank_maps,
        heuristic_reference_seed=heuristic_reference_seed,
        source_backend=source_backend,
        max_variants=max(2, candidate_count),
    )
    structured_variants = _generate_structured_substitution_seeds(
        context,
        model_role_scores=model_role_scores,
        role_rank_maps=role_rank_maps,
        heuristic_reference_seed=heuristic_reference_seed,
        source_backend=source_backend,
        max_variants=max(2, candidate_count),
    )
    all_seeds = [seed for seed in seeds if seed.chosen]
    all_seeds.extend(substitution_variants)
    all_seeds.extend(goal_targeted_variants)
    all_seeds.extend(structured_variants)

    deduped_model_seeds: dict[tuple[str, ...], CandidateSeed] = {}
    for seed in sorted(all_seeds, key=_seed_sort_key):
        key = tuple(food_id for food_id, _role in seed.chosen)
        if key not in deduped_model_seeds:
            deduped_model_seeds[key] = seed
    return _select_goal_balanced_model_seeds(
        context,
        list(deduped_model_seeds.values()),
        heuristic_reference_seed=heuristic_reference_seed,
        candidate_count=candidate_count,
    )


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
    generator_score: float,
    source: str,
    source_backend: str,
    stores: Sequence[dict[str, object]] | None,
    materialization_debug: Mapping[str, object] | None = None,
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
    goal_structure = _goal_structure_analysis(
        context,
        chosen=chosen,
        quantities=plan_quantities,
        response=response,
    )
    metadata = {
        "candidate_id": candidate_id,
        "chosen_food_ids": [food_id for food_id, _role in chosen],
        "shopping_food_ids": shopping_ids,
        "selection_trace": list(selection_trace),
        "heuristic_selection_score": round(float(heuristic_selection_score), 6),
        "generator_score": round(float(generator_score), 6),
        "source": source,
        "source_labels": [source],
        "candidate_generator_backend": source_backend,
        "role_counts": role_counts,
        "food_family_diversity_count": family_diversity,
        "role_diversity_count": sum(1 for count in role_counts.values() if count > 0),
        "repetition_penalty": _candidate_repetition_penalty(context, chosen),
        "preference_match_score": _candidate_preference_match_score(context, chosen),
        "unrealistic_basket_penalty": _candidate_unrealistic_penalty(context, chosen, plan_quantities, response),
        "nearby_store_count": len(stores or []),
        "materialization_debug": dict(materialization_debug or {}),
        **goal_structure,
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


def _quantity_totals(
    context: PlannerContext,
    quantities: Mapping[str, float],
) -> dict[str, float]:
    totals = {key: 0.0 for key in gr.NUTRIENT_SUMMARY_META}  # noqa: SLF001
    for food_id, quantity_g in quantities.items():
        if food_id not in context.available:
            continue
        for nutrient_id, value in gr._tracked_totals(context.available[food_id], quantity_g).items():  # noqa: SLF001
            totals[nutrient_id] += value
    return totals


def _role_calorie_shares(
    context: PlannerContext,
    *,
    chosen: Sequence[tuple[str, str]],
    quantities: Mapping[str, float],
) -> dict[str, float]:
    role_calories: dict[str, float] = {}
    total_calories = 0.0
    for food_id, role in chosen:
        if food_id not in context.available:
            continue
        quantity_g = float(quantities.get(food_id, 0.0))
        if quantity_g <= 0:
            continue
        calories = quantity_g * _food_metric(context.available[food_id], "energy_fibre_kcal") / 100.0
        role_calories[role] = role_calories.get(role, 0.0) + calories
        total_calories += calories
    if total_calories <= 0:
        return {}
    return {
        role: round(calories / total_calories, 6)
        for role, calories in role_calories.items()
    }


def _role_share_drift(
    seed_role_shares: Mapping[str, float],
    final_role_shares: Mapping[str, float],
) -> float:
    return round(
        sum(
            abs(float(seed_role_shares.get(role, 0.0)) - float(final_role_shares.get(role, 0.0)))
            for role in {"protein_anchor", "carb_base", "produce", "calorie_booster"}
        ),
        6,
    )


def _goal_structure_analysis(
    context: PlannerContext,
    *,
    chosen: Sequence[tuple[str, str]],
    quantities: Mapping[str, float],
    response: Mapping[str, object],
) -> dict[str, object]:
    role_counts = _candidate_role_counts(list(chosen))
    role_shares = _role_calorie_shares(context, chosen=chosen, quantities=quantities)
    target_role_shares = _target_role_calorie_shares(
        context,
        booster_present=bool(role_counts.get("calorie_booster")),
    )
    role_share_gap_total = round(
        sum(
            abs(float(role_shares.get(role, 0.0)) - float(target_role_shares.get(role, 0.0)))
            for role in ("protein_anchor", "carb_base", "produce", "calorie_booster")
        ),
        6,
    )

    protein_anchor_ids = [food_id for food_id, role in chosen if role == "protein_anchor" and food_id in context.available]
    protein_categories = [_protein_anchor_category(context.available[food_id]) for food_id in protein_anchor_ids]
    protein_category_set = set(protein_categories)
    animal_protein_count = sum(1 for value in protein_categories if value in {"lean_animal", "rich_animal", "animal"})
    lean_protein_count = sum(1 for value in protein_categories if value == "lean_animal")
    dairy_or_egg_count = sum(1 for value in protein_categories if value in {"dairy", "egg"})
    soy_count = sum(1 for value in protein_categories if value == "soy")
    legume_count = sum(1 for value in protein_categories if value == "legume")
    budget_support_anchor_count = sum(1 for value in protein_categories if value in {"egg", "soy"})

    produce_ids = [food_id for food_id, role in chosen if role == "produce" and food_id in context.available]
    produce_clusters = [_produce_combo_cluster(context.available[food_id]) for food_id in produce_ids]
    fruit_count = sum(1 for value in produce_clusters if value == "fruit")
    high_volume_produce_count = sum(
        1
        for value in produce_clusters
        if value in {"leafy_dense", "crucifer_fiber", "watery_practical", "vitamin_c_crisp"}
    )
    low_cost_produce_count = sum(
        1
        for food_id in produce_ids
        if food_id in {"cabbage", "carrots", "onions", "frozen_vegetables", "bananas", "potatoes", "apples"}
    )

    carb_base_id = next((food_id for food_id, role in chosen if role == "carb_base"), None)
    booster_id = next((food_id for food_id, role in chosen if role == "calorie_booster"), None)
    nutrition_summary = dict(response.get("nutrition_summary") or {})
    estimated_calories = float(nutrition_summary.get("calorie_estimated_kcal") or 0.0)
    estimated_protein = float(nutrition_summary.get("protein_estimated_g") or 0.0)
    estimated_carbohydrate = float(nutrition_summary.get("carbohydrate_estimated_g") or 0.0)
    estimated_fat = float(nutrition_summary.get("fat_estimated_g") or 0.0)
    target_protein = float(nutrition_summary.get("protein_target_g") or 0.0)
    target_fat = float(nutrition_summary.get("fat_target_g") or 0.0)
    estimated_cost = float(response.get("estimated_basket_cost") or 0.0)
    cost_per_1000_kcal = estimated_cost / max(estimated_calories / 1000.0, 0.1) if estimated_cost > 0 else 0.0
    count_gap = (
        abs(int(role_counts.get("protein_anchor", 0)) - int(context.basket_policy.get("desired_protein_anchors", 0)))
        + abs(int(role_counts.get("produce", 0)) - int(context.basket_policy.get("desired_produce_items", 0)))
        + abs(int(role_counts.get("carb_base", 0)) - 1)
    )
    share_fit = max(0.0, 1.0 - (role_share_gap_total / 0.95))
    count_fit = max(0.0, 1.0 - (count_gap / 4.0))
    score = 0.6 * share_fit + 0.18 * count_fit
    notes: list[str] = []

    if context.goal_profile == "muscle_gain":
        if carb_base_id in {"oats", "pasta", "bagel", "potatoes", "wholemeal_bread", "sweet_potatoes"}:
            score += 0.18
            notes.append("performance-oriented carb base")
        if lean_protein_count >= 1 and dairy_or_egg_count >= 1:
            score += 0.2
            notes.append("mixed lean and dairy/egg proteins")
        elif lean_protein_count >= 1:
            score += 0.08
        if fruit_count >= 1:
            score += 0.08
            notes.append("includes quick-carb fruit")
        if booster_id in {"olive_oil", "peanut_butter", "nuts", "almond_butter", "cheese"}:
            score += 0.18
            notes.append("keeps calorie-dense support")
        elif float(role_shares.get("calorie_booster", 0.0)) < 0.08:
            score -= 0.14
    elif context.goal_profile == "fat_loss":
        if booster_id is None:
            score += 0.2
            notes.append("avoids calorie booster")
        else:
            score -= 0.28
        if int(role_counts.get("produce", 0)) >= 3 and high_volume_produce_count >= 2:
            score += 0.22
            notes.append("higher-volume produce structure")
        if lean_protein_count >= 1 and animal_protein_count - lean_protein_count <= 0:
            score += 0.18
            notes.append("leans on lean protein anchors")
        if carb_base_id in {"wholemeal_bread", "quinoa", "potatoes", "sweet_potatoes"}:
            score += 0.14
        if fruit_count > 1:
            score -= 0.12
        if float(role_shares.get("carb_base", 0.0)) > 0.33:
            score -= 0.12
    elif context.goal_profile == "maintenance":
        if carb_base_id in {"wholemeal_bread", "potatoes", "quinoa", "rice"}:
            score += 0.14
            notes.append("moderate staple carb base")
        if fruit_count >= 1 and int(role_counts.get("produce", 0)) >= 2:
            score += 0.12
            notes.append("balanced fruit and veg mix")
        booster_share = float(role_shares.get("calorie_booster", 0.0))
        if booster_id is None:
            score += 0.05
        elif 0.05 <= booster_share <= 0.16:
            score += 0.08
            notes.append("keeps booster moderate")
        else:
            score -= 0.06
    elif context.goal_profile == "high_protein_vegetarian":
        if animal_protein_count == 0:
            score += 0.24
            notes.append("fully vegetarian protein anchors")
        else:
            score -= 0.45
        if soy_count >= 1 and dairy_or_egg_count >= 1:
            score += 0.24
            notes.append("combines soy with dairy/egg protein")
        elif soy_count >= 1 or dairy_or_egg_count >= 1:
            score += 0.1
        if legume_count > 0:
            score -= 0.08
        if carb_base_id in {"wholemeal_bread", "quinoa", "oats", "bagel"}:
            score += 0.12
        if fruit_count >= 1 and any(value in {"leafy_dense", "vitamin_c_crisp"} for value in produce_clusters):
            score += 0.14
            notes.append("pairs fruit with greens or vitamin C produce")
        if float(role_shares.get("calorie_booster", 0.0)) > 0.22:
            score -= 0.1
    elif context.goal_profile == "budget_friendly_healthy":
        if legume_count >= 1 and budget_support_anchor_count >= 1:
            score += 0.26
            notes.append("pairs legumes with an economical support protein")
        elif legume_count >= 2:
            score -= 0.26
        if carb_base_id in {"rice", "pasta", "potatoes", "wholemeal_bread"}:
            score += 0.12
        if low_cost_produce_count >= 2:
            score += 0.18
            notes.append("leans on low-cost produce staples")
        if booster_id in {"olive_oil", "peanut_butter"}:
            score += 0.14
            notes.append("adds inexpensive fat support")
        elif target_fat > 0 and estimated_fat < target_fat * 0.72:
            score -= 0.18
        if estimated_cost > 0:
            if cost_per_1000_kcal <= 3.2:
                score += 0.14
            elif cost_per_1000_kcal >= 4.5:
                score -= 0.12
        if target_protein > 0 and estimated_protein < target_protein * 0.88:
            score -= 0.12
        carbohydrate_target = float(nutrition_summary.get("carbohydrate_target_g") or 0.0)
        if carbohydrate_target > 0 and estimated_carbohydrate > carbohydrate_target * 1.28:
            score -= 0.16

    return {
        "goal_structure_alignment_score": round(score, 6),
        "role_calorie_shares": dict(role_shares),
        "target_role_calorie_shares": dict(target_role_shares),
        "role_share_gap_total": role_share_gap_total,
        "protein_anchor_categories": list(protein_categories),
        "protein_anchor_family_diversity": len(protein_category_set),
        "animal_protein_anchor_count": animal_protein_count,
        "lean_protein_anchor_count": lean_protein_count,
        "vegetarian_protein_anchor_count": len(protein_categories) - animal_protein_count,
        "legume_protein_anchor_count": legume_count,
        "soy_protein_anchor_count": soy_count,
        "dairy_or_egg_anchor_count": dairy_or_egg_count,
        "budget_support_anchor_count": budget_support_anchor_count,
        "produce_clusters": list(produce_clusters),
        "fruit_produce_count": fruit_count,
        "high_volume_produce_count": high_volume_produce_count,
        "low_cost_produce_count": low_cost_produce_count,
        "structure_notes": notes[:5],
    }


def _maintenance_materialization_drift_summary(
    context: PlannerContext,
    *,
    seed: CandidateSeed,
    seed_intent_quantities: Mapping[str, float],
    final_chosen: Sequence[tuple[str, str]],
    final_plan_quantities: Mapping[str, float],
) -> dict[str, object]:
    seed_food_ids = [food_id for food_id, _role in seed.chosen]
    final_food_ids = [food_id for food_id, _role in final_chosen if float(final_plan_quantities.get(food_id, 0.0)) > 0.0]
    added_food_ids = [food_id for food_id in final_food_ids if food_id not in seed_food_ids]
    removed_food_ids = [food_id for food_id in seed_food_ids if food_id not in final_food_ids]
    seed_role_shares = _role_calorie_shares(context, chosen=seed.chosen, quantities=seed_intent_quantities)
    final_role_shares = _role_calorie_shares(context, chosen=final_chosen, quantities=final_plan_quantities)
    role_share_drift = _role_share_drift(seed_role_shares, final_role_shares)
    quantity_delta_ratios = []
    major_quantity_reallocation = False
    for food_id in seed_food_ids:
        seed_quantity = float(seed_intent_quantities.get(food_id, 0.0))
        final_quantity = float(final_plan_quantities.get(food_id, 0.0))
        if seed_quantity <= 0:
            continue
        delta_ratio = abs(final_quantity - seed_quantity) / max(seed_quantity, 1.0)
        quantity_delta_ratios.append(delta_ratio)
        if delta_ratio >= 0.3 or abs(final_quantity - seed_quantity) >= 90.0:
            major_quantity_reallocation = True
    average_quantity_delta_ratio = round(sum(quantity_delta_ratios) / len(quantity_delta_ratios), 6) if quantity_delta_ratios else 0.0
    booster_added = any(role == "calorie_booster" for food_id, role in final_chosen if food_id not in seed_food_ids)
    drift_score = round(
        role_share_drift
        + (0.18 if booster_added else 0.0)
        + (0.1 * len(added_food_ids))
        + (0.08 * len(removed_food_ids))
        + min(average_quantity_delta_ratio, 1.0) * 0.45,
        6,
    )

    if not added_food_ids and role_share_drift < 0.18 and average_quantity_delta_ratio < 0.18:
        summary = "model seed preserved"
    elif not booster_added and role_share_drift < 0.3 and average_quantity_delta_ratio < 0.3:
        summary = "minor quantity drift"
    elif booster_added and role_share_drift >= 0.35:
        summary = "booster introduced and basket converged toward heuristic"
    elif major_quantity_reallocation and (
        abs(final_role_shares.get("protein_anchor", 0.0) - seed_role_shares.get("protein_anchor", 0.0)) >= 0.16
        or abs(final_role_shares.get("carb_base", 0.0) - seed_role_shares.get("carb_base", 0.0)) >= 0.16
    ):
        summary = "protein/carb rebalance erased candidate distinction"
    elif booster_added:
        summary = "booster introduced but seed stayed recognizable"
    else:
        summary = "major quantity drift"

    return {
        "seed_food_ids": seed_food_ids,
        "final_food_ids": final_food_ids,
        "added_food_ids": added_food_ids,
        "removed_food_ids": removed_food_ids,
        "booster_added": booster_added,
        "seed_role_shares": seed_role_shares,
        "final_role_shares": final_role_shares,
        "role_share_drift": role_share_drift,
        "average_quantity_delta_ratio": average_quantity_delta_ratio,
        "major_quantity_reallocation": major_quantity_reallocation,
        "drift_score": drift_score,
        "summary": summary,
    }


def _model_materialization_drift_summary(
    context: PlannerContext,
    *,
    seed: CandidateSeed,
    seed_intent_quantities: Mapping[str, float],
    final_chosen: Sequence[tuple[str, str]],
    final_plan_quantities: Mapping[str, float],
) -> dict[str, object]:
    seed_food_ids = [food_id for food_id, _role in seed.chosen]
    final_food_ids = [food_id for food_id, _role in final_chosen if float(final_plan_quantities.get(food_id, 0.0)) > 0.0]
    added_food_ids = [food_id for food_id in final_food_ids if food_id not in seed_food_ids]
    removed_food_ids = [food_id for food_id in seed_food_ids if food_id not in final_food_ids]
    seed_role_shares = _role_calorie_shares(context, chosen=seed.chosen, quantities=seed_intent_quantities)
    final_role_shares = _role_calorie_shares(context, chosen=final_chosen, quantities=final_plan_quantities)
    role_share_drift = _role_share_drift(seed_role_shares, final_role_shares)
    quantity_delta_ratios = []
    major_quantity_reallocation = False
    for food_id in seed_food_ids:
        seed_quantity = float(seed_intent_quantities.get(food_id, 0.0))
        final_quantity = float(final_plan_quantities.get(food_id, 0.0))
        if seed_quantity <= 0:
            continue
        delta_ratio = abs(final_quantity - seed_quantity) / max(seed_quantity, 1.0)
        quantity_delta_ratios.append(delta_ratio)
        if delta_ratio >= 0.3 or abs(final_quantity - seed_quantity) >= 90.0:
            major_quantity_reallocation = True
    average_quantity_delta_ratio = round(sum(quantity_delta_ratios) / len(quantity_delta_ratios), 6) if quantity_delta_ratios else 0.0
    booster_added = any(role == "calorie_booster" for food_id, role in final_chosen if food_id not in seed_food_ids)
    drift_score = round(
        role_share_drift
        + (0.18 if booster_added else 0.0)
        + (0.1 * len(added_food_ids))
        + (0.08 * len(removed_food_ids))
        + min(average_quantity_delta_ratio, 1.0) * 0.45,
        6,
    )
    if not added_food_ids and role_share_drift < 0.18 and average_quantity_delta_ratio < 0.18:
        summary = "model seed preserved"
    elif role_share_drift < 0.3 and average_quantity_delta_ratio < 0.28:
        summary = "minor quantity drift"
    elif booster_added and role_share_drift >= 0.35:
        summary = "booster introduced and basket converged toward heuristic"
    elif major_quantity_reallocation:
        summary = "major quantity rebalance changed the seed structure"
    elif booster_added:
        summary = "booster introduced but seed stayed recognizable"
    else:
        summary = "moderate quantity drift"
    return {
        "seed_food_ids": seed_food_ids,
        "final_food_ids": final_food_ids,
        "added_food_ids": added_food_ids,
        "removed_food_ids": removed_food_ids,
        "booster_added": booster_added,
        "seed_role_shares": seed_role_shares,
        "final_role_shares": final_role_shares,
        "role_share_drift": role_share_drift,
        "average_quantity_delta_ratio": average_quantity_delta_ratio,
        "major_quantity_reallocation": major_quantity_reallocation,
        "drift_score": drift_score,
        "summary": summary,
    }


def _align_model_seed_choices(
    context: PlannerContext,
    seed: CandidateSeed,
    chosen: list[tuple[str, str]],
) -> list[tuple[str, str]]:
    if seed.source != "model":
        return chosen

    protein_entries = [entry for entry in chosen if entry[1] == "protein_anchor"]
    if len(protein_entries) <= 1:
        return chosen

    profile = _priority_profile(context)

    def protein_sort_key(entry: tuple[str, str]) -> tuple[float, ...]:
        food_id, _role = entry
        food = context.available[food_id]
        reference_index = _model_reference_order_index(seed, role="protein_anchor", food_id=food_id)
        return (
            float(reference_index),
            -_protein_density(food) * float(profile["protein_priority"]),
            -_prep_score(food) * float(profile["practicality_priority"]),
            -float(food.get("budget_score") or 0.0) * float(profile["cost_priority"]),
            float(food.get("commonality_rank") or 999.0),
        )

    ordered_protein_entries = iter(sorted(protein_entries, key=protein_sort_key))
    reordered: list[tuple[str, str]] = []
    for food_id, role in chosen:
        if role == "protein_anchor":
            reordered.append(next(ordered_protein_entries))
        else:
            reordered.append((food_id, role))
    return reordered


def _preserve_seed_fill(
    context: PlannerContext,
    *,
    chosen: list[tuple[str, str]],
    quantities: dict[str, float],
    protein_anchors: Sequence[str],
    carb_base: str | None,
) -> None:
    profile = _priority_profile(context)
    preferred_fill_ids: list[str] = []
    if carb_base is not None and carb_base in quantities:
        preferred_fill_ids.append(carb_base)
    preferred_fill_ids.extend(food_id for food_id in protein_anchors if food_id in quantities)

    for food_id in preferred_fill_ids:
        current_totals = _quantity_totals(context, quantities)
        calorie_deficit = max(0.0, context.calorie_target_kcal - current_totals["energy_fibre_kcal"])
        if calorie_deficit <= max(
            float(context.basket_policy["booster_gap_floor"]) * 0.65,
            context.calorie_target_kcal * float(context.basket_policy["booster_gap_ratio"]) * 0.65,
        ):
            break
        food = context.available[food_id]
        if food_id == carb_base:
            fill_ratio = max(
                0.08,
                min(0.32, 0.14 + (0.1 * float(profile["calorie_completion_priority"])) - (0.06 * float(profile["calorie_tightness"]))),
            )
        else:
            fill_ratio = max(
                0.07,
                min(0.18, 0.08 + (0.06 * float(profile["protein_priority"])) - (0.02 * float(profile["calorie_tightness"]))),
            )
        additional_grams = 100.0 * calorie_deficit * fill_ratio / max(float(food["energy_fibre_kcal"]), 1.0)
        if additional_grams <= 0:
            continue
        quantities[food_id] += additional_grams
        gr._apply_goal_quantity_caps(chosen, context.available, quantities, context.goal_profile)  # noqa: SLF001


def _rebalance_seed_quantities(
    context: PlannerContext,
    *,
    chosen: list[tuple[str, str]],
    quantities: dict[str, float],
    protein_anchors: Sequence[str],
    carb_base: str | None,
    booster: str | None,
) -> None:
    profile = _priority_profile(context)
    totals = _quantity_totals(context, quantities)
    protein_surplus = totals["protein"] - context.protein_target_g
    target_buffer = max(4.0, 7.5 - (2.0 * float(profile["protein_priority"])))
    removed_calories = 0.0

    if protein_surplus > target_buffer:
        reduction_order = list(protein_anchors[1:]) or list(protein_anchors[:1])
        if protein_anchors and protein_anchors[0] not in reduction_order:
            reduction_order.append(protein_anchors[0])
        for anchor_food_id in reduction_order:
            if anchor_food_id not in quantities or anchor_food_id not in context.available:
                continue
            anchor_food = context.available[anchor_food_id]
            min_anchor_g = max(float(anchor_food.get("default_serving_g") or 0.0), 90.0)
            reducible_g = max(0.0, quantities[anchor_food_id] - min_anchor_g)
            if reducible_g <= 0:
                continue
            reduce_g = min(
                reducible_g,
                100.0 * max(protein_surplus - target_buffer, 0.0) / max(_food_metric(anchor_food, "protein"), 1.0),
            )
            if reduce_g <= 0:
                continue
            quantities[anchor_food_id] = max(min_anchor_g, quantities[anchor_food_id] - reduce_g)
            removed_calories += reduce_g * _food_metric(anchor_food, "energy_fibre_kcal") / 100.0
            totals = _quantity_totals(context, quantities)
            protein_surplus = totals["protein"] - context.protein_target_g
            if protein_surplus <= target_buffer:
                break

    if carb_base is not None and carb_base in quantities and removed_calories > 0.0:
        current_totals = _quantity_totals(context, quantities)
        calorie_deficit = max(0.0, context.calorie_target_kcal - current_totals["energy_fibre_kcal"])
        if calorie_deficit > 0:
            carb_refill_ratio = max(
                0.3,
                min(0.85, 0.48 + (0.18 * float(profile["calorie_completion_priority"])) - (0.2 * float(profile["calorie_tightness"]))),
            )
            carb_food = context.available[carb_base]
            refill_calories = min(removed_calories * carb_refill_ratio, calorie_deficit)
            quantities[carb_base] += 100.0 * refill_calories / max(_food_metric(carb_food, "energy_fibre_kcal"), 1.0)

    if carb_base is not None and carb_base in quantities:
        carb_food = context.available[carb_base]
        current_totals = _quantity_totals(context, quantities)
        carb_calories = float(quantities.get(carb_base, 0.0)) * _food_metric(carb_food, "energy_fibre_kcal") / 100.0
        target_carb_calories = context.calorie_target_kcal * float(context.basket_policy["carb_share"])
        carb_slack = max(60.0, 150.0 - (40.0 * float(profile["calorie_tightness"])))
        calorie_overshoot = current_totals["energy_fibre_kcal"] - context.calorie_target_kcal
        if carb_calories > target_carb_calories + carb_slack or calorie_overshoot > carb_slack:
            reducible_g = max(0.0, quantities[carb_base] - max(float(carb_food.get("default_serving_g") or 0.0), 120.0))
            reduce_g = min(
                reducible_g,
                100.0 * max(max(carb_calories - target_carb_calories - carb_slack, 0.0), calorie_overshoot) / max(_food_metric(carb_food, "energy_fibre_kcal"), 1.0),
            )
            if reduce_g > 0:
                quantities[carb_base] = max(max(float(carb_food.get("default_serving_g") or 0.0), 120.0), quantities[carb_base] - reduce_g)

    if booster is not None and booster in quantities and removed_calories > 25.0:
        booster_food = context.available[booster]
        current_totals = _quantity_totals(context, quantities)
        calorie_deficit = max(0.0, context.calorie_target_kcal - current_totals["energy_fibre_kcal"])
        if calorie_deficit > 25.0:
            refill_calories = min(removed_calories * 0.45, calorie_deficit)
            quantities[booster] += 100.0 * refill_calories / max(_food_metric(booster_food, "energy_fibre_kcal"), 1.0)

    gr._apply_goal_quantity_caps(chosen, context.available, quantities, context.goal_profile)  # noqa: SLF001


def _pick_structured_booster(
    context: PlannerContext,
    *,
    excluded: set[str],
    chosen: list[tuple[str, str]],
) -> str | None:
    role = "calorie_booster"
    role_scores = context.role_scores[role]
    candidate_ids = [
        food_id
        for food_id in context.role_orders[role]
        if food_id not in excluded and food_id in context.available
    ]
    if not candidate_ids:
        return None
    shortlist = candidate_ids[:8]
    profile = _priority_profile(context)
    ranked_rows: list[tuple[float, int, str]] = []
    for food_id in shortlist:
        food = context.available[food_id]
        complementarity = _pairwise_complementarity_bonus(
            context,
            role=role,
            food_id=food_id,
            chosen=chosen,
            profile=profile,
        )
        practicality = (
            _prep_score(food) * 0.015 * float(profile["practicality_priority"])
            + max(float(food.get("budget_score") or 0.0) - 3.0, 0.0) * 0.01 * float(profile["cost_priority"])
            + _commonality_bonus(food) * 0.6
        )
        goal_structure_bonus = _goal_structure_selection_bonus(
            context,
            role=role,
            food_id=food_id,
            chosen=chosen,
        )
        adjusted_score = float(role_scores.get(food_id, 0.0)) + complementarity + practicality + goal_structure_bonus
        ranked_rows.append((-adjusted_score, int(food.get("commonality_rank") or 999), food_id))
    ranked_rows.sort()
    return str(ranked_rows[0][2]) if ranked_rows else None


def _trim_allocation_overshoot(
    context: PlannerContext,
    *,
    quantities: dict[str, float],
    protein_anchors: Sequence[str],
    carb_base: str | None,
    booster: str | None,
) -> None:
    profile = _priority_profile(context)
    overshoot_tolerance = max(55.0, context.calorie_target_kcal * max(0.03, 0.055 - (0.015 * float(profile["calorie_tightness"]))))
    totals = _quantity_totals(context, quantities)
    calorie_overshoot = totals["energy_fibre_kcal"] - context.calorie_target_kcal
    if calorie_overshoot <= overshoot_tolerance:
        return

    if booster is not None and booster in quantities and booster in context.available:
        booster_food = context.available[booster]
        min_booster_g = 5.0 if str(booster_food.get("food_family") or "") == "fat" else max(float(booster_food.get("default_serving_g") or 0.0) * 0.5, 15.0)
        reducible_g = max(0.0, quantities[booster] - min_booster_g)
        reduce_g = min(reducible_g, 100.0 * calorie_overshoot / max(_food_metric(booster_food, "energy_fibre_kcal"), 1.0))
        quantities[booster] = max(min_booster_g, quantities[booster] - reduce_g)
        totals = _quantity_totals(context, quantities)
        calorie_overshoot = totals["energy_fibre_kcal"] - context.calorie_target_kcal

    if calorie_overshoot > overshoot_tolerance and carb_base is not None and carb_base in quantities and carb_base in context.available:
        carb_food = context.available[carb_base]
        min_carb_g = max(float(carb_food.get("default_serving_g") or 0.0), 80.0)
        reducible_g = max(0.0, quantities[carb_base] - min_carb_g)
        reduce_g = min(reducible_g, 100.0 * calorie_overshoot / max(_food_metric(carb_food, "energy_fibre_kcal"), 1.0))
        quantities[carb_base] = max(min_carb_g, quantities[carb_base] - reduce_g)
        totals = _quantity_totals(context, quantities)
        calorie_overshoot = totals["energy_fibre_kcal"] - context.calorie_target_kcal

    protein_surplus = totals["protein"] - context.protein_target_g
    if calorie_overshoot > overshoot_tolerance and protein_surplus > 6.0 and len(protein_anchors) > 1:
        secondary_anchor = protein_anchors[-1]
        if secondary_anchor in quantities and secondary_anchor in context.available:
            anchor_food = context.available[secondary_anchor]
            min_anchor_g = max(float(anchor_food.get("default_serving_g") or 0.0), 85.0)
            reducible_g = max(0.0, quantities[secondary_anchor] - min_anchor_g)
            reduce_g = min(
                reducible_g,
                100.0 * calorie_overshoot / max(_food_metric(anchor_food, "energy_fibre_kcal"), 1.0),
                100.0 * max(0.0, protein_surplus - 4.0) / max(_food_metric(anchor_food, "protein"), 1.0),
            )
            quantities[secondary_anchor] = max(min_anchor_g, quantities[secondary_anchor] - reduce_g)


def _final_fill_ratios(
    context: PlannerContext,
    *,
    seed: CandidateSeed,
    booster: str | None,
    protein_close_enough: bool,
) -> tuple[float, float]:
    profile = _priority_profile(context)
    carb_ratio = float(context.basket_policy["final_carb_fill_ratio"])
    booster_ratio = float(context.basket_policy["final_booster_fill_ratio"])
    carb_ratio *= max(0.0, min(1.0, 0.35 + (0.55 * float(profile["calorie_completion_priority"])) - (0.45 * float(profile["calorie_tightness"]))))
    booster_ratio *= max(0.2, min(1.2, 0.45 + (0.55 * float(profile["calorie_completion_priority"]))))
    if protein_close_enough:
        carb_ratio *= max(0.0, 1.0 - (0.75 * float(profile["calorie_tightness"])))
        booster_ratio *= max(0.0, 1.0 - (0.65 * float(profile["calorie_tightness"])))
    if seed.source == "model" and booster is not None:
        carb_ratio *= 0.88
        booster_ratio = min(1.0, booster_ratio + 0.08)
    return round(max(carb_ratio, 0.0), 6), round(max(booster_ratio, 0.0), 6)


def _target_role_calorie_shares(
    context: PlannerContext,
    *,
    booster_present: bool,
) -> dict[str, float]:
    configured = context.basket_policy.get("target_role_calorie_shares")
    if isinstance(configured, Mapping):
        normalized = {
            role: max(0.0, float(configured.get(role, 0.0)))
            for role in ("protein_anchor", "carb_base", "produce", "calorie_booster")
        }
        if not booster_present:
            normalized["calorie_booster"] = 0.0
        total = sum(normalized.values())
        if total > 0:
            return {
                role: round(value / total, 6)
                for role, value in normalized.items()
            }

    profile = _priority_profile(context)
    protein_share = min(0.42, max(0.24, (context.protein_target_g * 4.0 / max(context.calorie_target_kcal, 1.0)) * 0.95))
    carb_share = min(0.52, max(0.3, float(context.basket_policy["carb_share"])))
    produce_share = min(0.14, max(0.06, 0.05 + (0.04 * float(profile["fiber_priority"]))))
    if not booster_present:
        total = protein_share + carb_share + produce_share
        return {
            "protein_anchor": round(protein_share / total, 6),
            "carb_base": round(carb_share / total, 6),
            "produce": round(produce_share / total, 6),
            "calorie_booster": 0.0,
        }
    booster_share = max(0.08, 1.0 - protein_share - carb_share - produce_share)
    total = protein_share + carb_share + produce_share + booster_share
    return {
        "protein_anchor": round(protein_share / total, 6),
        "carb_base": round(carb_share / total, 6),
        "produce": round(produce_share / total, 6),
        "calorie_booster": round(booster_share / total, 6),
    }


def _rebalance_role_calorie_shares(
    context: PlannerContext,
    *,
    chosen: Sequence[tuple[str, str]],
    quantities: dict[str, float],
    protein_anchors: Sequence[str],
    carb_base: str | None,
    booster: str | None,
) -> None:
    if carb_base is None or carb_base not in quantities or booster is None or booster not in quantities:
        return
    profile = _priority_profile(context)
    if float(profile["calorie_completion_priority"]) >= 1.2 and float(profile["calorie_tightness"]) <= 0.85:
        return

    current_shares = _role_calorie_shares(context, chosen=chosen, quantities=quantities)
    target_shares = _target_role_calorie_shares(context, booster_present=True)
    current_totals = _quantity_totals(context, quantities)
    total_calories = float(current_totals["energy_fibre_kcal"] or 0.0)
    if total_calories <= 0:
        return

    current_carb_calories = float(current_shares.get("carb_base", 0.0)) * total_calories
    current_booster_calories = float(current_shares.get("calorie_booster", 0.0)) * total_calories
    target_carb_calories = float(target_shares.get("carb_base", 0.0)) * total_calories
    target_booster_calories = float(target_shares.get("calorie_booster", 0.0)) * total_calories
    shift_calories = min(
        max(current_carb_calories - target_carb_calories, 0.0),
        max(target_booster_calories - current_booster_calories, 0.0),
        total_calories * 0.12,
    )
    if shift_calories <= 30.0:
        return

    carb_food = context.available[carb_base]
    booster_food = context.available[booster]
    carb_min_g = max(float(carb_food.get("default_serving_g") or 0.0), 120.0)
    carb_reduce_g = min(
        max(0.0, quantities[carb_base] - carb_min_g),
        100.0 * shift_calories / max(_food_metric(carb_food, "energy_fibre_kcal"), 1.0),
    )
    if carb_reduce_g <= 0:
        return
    quantities[carb_base] = max(carb_min_g, quantities[carb_base] - carb_reduce_g)
    actual_shift_calories = carb_reduce_g * _food_metric(carb_food, "energy_fibre_kcal") / 100.0
    quantities[booster] += 100.0 * actual_shift_calories / max(_food_metric(booster_food, "energy_fibre_kcal"), 1.0)


def _model_reference_order_index(
    seed: CandidateSeed,
    *,
    role: str,
    food_id: str,
) -> int:
    for step in seed.selection_trace:
        if str(step.get("role") or "") != role:
            continue
        if str(step.get("heuristic_reference_food_id") or "") == food_id:
            return int(step.get("step_index") or 0)
    return 99


def _reorder_goal_specific_model_choices(
    context: PlannerContext,
    seed: CandidateSeed,
    chosen: list[tuple[str, str]],
) -> list[tuple[str, str]]:
    if seed.source != "model" or context.goal_profile not in {"fat_loss", "maintenance"}:
        return chosen

    protein_entries = [entry for entry in chosen if entry[1] == "protein_anchor"]
    if len(protein_entries) <= 1:
        return chosen

    def protein_sort_key(entry: tuple[str, str]) -> tuple[float, ...]:
        food_id, _role = entry
        food = context.available[food_id]
        reference_index = _model_reference_order_index(seed, role="protein_anchor", food_id=food_id)
        if context.goal_profile == "fat_loss":
            fallback = (
                _food_metric(food, "fat"),
                -_protein_density(food),
                float(food.get("budget_score") or 0.0) * -1.0,
                float(food.get("commonality_rank") or 999.0),
            )
        else:
            fallback = (
                -_prep_score(food),
                float(food.get("commonality_rank") or 999.0),
                -_protein_density(food),
                float(food.get("budget_score") or 0.0) * -1.0,
            )
        return (float(reference_index), *fallback)

    ordered_protein_entries = iter(sorted(protein_entries, key=protein_sort_key))
    reordered: list[tuple[str, str]] = []
    for food_id, role in chosen:
        if role == "protein_anchor":
            reordered.append(next(ordered_protein_entries))
        else:
            reordered.append((food_id, role))
    return reordered


def _rebalance_goal_specific_model_quantities(
    context: PlannerContext,
    *,
    chosen: list[tuple[str, str]],
    quantities: dict[str, float],
    protein_anchors: list[str],
    carb_base: str | None,
) -> None:
    if context.goal_profile not in {"fat_loss", "maintenance"} or not protein_anchors or carb_base is None or carb_base not in quantities:
        return

    target_buffer = 6.0 if context.goal_profile == "fat_loss" else 5.5
    totals = _quantity_totals(context, quantities)
    protein_surplus = totals["protein"] - context.protein_target_g
    if protein_surplus <= target_buffer:
        return

    reduction_order = list(protein_anchors[1:]) or list(protein_anchors[:1])
    if protein_anchors[0] not in reduction_order:
        reduction_order.append(protein_anchors[0])

    carb_food = context.available[carb_base]
    for anchor_food_id in reduction_order:
        if anchor_food_id not in quantities or anchor_food_id not in context.available:
            continue
        anchor_food = context.available[anchor_food_id]
        min_anchor_g = max(
            float(anchor_food.get("default_serving_g") or 0.0),
            80.0 if context.goal_profile == "fat_loss" else 100.0,
        )
        reducible_g = max(0.0, quantities[anchor_food_id] - min_anchor_g)
        if reducible_g <= 0:
            continue
        desired_reduce_g = (
            100.0 * max(protein_surplus - target_buffer, 0.0) / max(_food_metric(anchor_food, "protein"), 1.0)
        )
        reduce_g = min(reducible_g, desired_reduce_g)
        if reduce_g <= 0:
            continue
        quantities[anchor_food_id] = max(min_anchor_g, quantities[anchor_food_id] - reduce_g)
        removed_calories = reduce_g * _food_metric(anchor_food, "energy_fibre_kcal") / 100.0
        carb_fill_ratio = 0.95 if context.goal_profile == "fat_loss" else 0.72
        quantities[carb_base] += (
            100.0
            * removed_calories
            * carb_fill_ratio
            / max(_food_metric(carb_food, "energy_fibre_kcal"), 1.0)
        )
        gr._apply_goal_quantity_caps(chosen, context.available, quantities, context.goal_profile)  # noqa: SLF001
        totals = _quantity_totals(context, quantities)
        protein_surplus = totals["protein"] - context.protein_target_g
        if protein_surplus <= target_buffer:
            break


def _rebalance_maintenance_model_quantities(
    context: PlannerContext,
    *,
    quantities: dict[str, float],
    protein_anchors: Sequence[str],
    carb_base: str | None,
    booster: str | None,
) -> None:
    if context.goal_profile != "maintenance" or carb_base is None or carb_base not in quantities:
        return

    totals = _quantity_totals(context, quantities)
    protein_surplus = totals["protein"] - context.protein_target_g
    calorie_overshoot = totals["energy_fibre_kcal"] - context.calorie_target_kcal
    removed_calories = 0.0

    if protein_surplus > 5.0 and protein_anchors:
        reduction_order = list(protein_anchors[1:]) or list(protein_anchors[:1])
        if protein_anchors[0] not in reduction_order:
            reduction_order.append(protein_anchors[0])
        for anchor_food_id in reduction_order:
            if anchor_food_id not in quantities or anchor_food_id not in context.available:
                continue
            anchor_food = context.available[anchor_food_id]
            min_anchor_g = max(float(anchor_food.get("default_serving_g") or 0.0), 95.0)
            reducible_g = max(0.0, quantities[anchor_food_id] - min_anchor_g)
            if reducible_g <= 0:
                continue
            reduce_g = min(
                reducible_g,
                100.0 * max(protein_surplus - 3.5, 0.0) / max(_food_metric(anchor_food, "protein"), 1.0),
            )
            if reduce_g <= 0:
                continue
            quantities[anchor_food_id] = max(min_anchor_g, quantities[anchor_food_id] - reduce_g)
            removed_calories += reduce_g * _food_metric(anchor_food, "energy_fibre_kcal") / 100.0
            totals = _quantity_totals(context, quantities)
            protein_surplus = totals["protein"] - context.protein_target_g
            if protein_surplus <= 5.0:
                break

    carb_food = context.available[carb_base]
    carb_calories = float(quantities.get(carb_base, 0.0)) * _food_metric(carb_food, "energy_fibre_kcal") / 100.0
    target_carb_calories = context.calorie_target_kcal * float(context.basket_policy["carb_share"])
    if carb_calories > target_carb_calories + 130.0 or calorie_overshoot > 85.0:
        reducible_g = max(0.0, quantities[carb_base] - max(float(carb_food.get("default_serving_g") or 0.0), 120.0))
        reduce_g = min(
            reducible_g,
            100.0 * max(max(carb_calories - target_carb_calories - 70.0, 0.0), calorie_overshoot) / max(_food_metric(carb_food, "energy_fibre_kcal"), 1.0),
        )
        if reduce_g > 0:
            quantities[carb_base] = max(max(float(carb_food.get("default_serving_g") or 0.0), 120.0), quantities[carb_base] - reduce_g)
            removed_calories += reduce_g * _food_metric(carb_food, "energy_fibre_kcal") / 100.0

    if booster is not None and booster in quantities and removed_calories > 35.0:
        booster_food = context.available[booster]
        current_totals = _quantity_totals(context, quantities)
        calorie_deficit = max(0.0, context.calorie_target_kcal - current_totals["energy_fibre_kcal"])
        if calorie_deficit > 30.0:
            refill_calories = min(removed_calories * 0.55, calorie_deficit)
            quantities[booster] += 100.0 * refill_calories / max(_food_metric(booster_food, "energy_fibre_kcal"), 1.0)


def _preserve_model_seed_fill(
    context: PlannerContext,
    *,
    chosen: list[tuple[str, str]],
    quantities: dict[str, float],
    protein_anchors: list[str],
    carb_base: str | None,
) -> None:
    preferred_fill_ids: list[str] = []
    if carb_base is not None and carb_base in quantities:
        preferred_fill_ids.append(carb_base)
    preferred_fill_ids.extend(
        food_id
        for food_id in protein_anchors
        if food_id in quantities and float(context.available[food_id].get("fat") or 0.0) >= 7.0
    )
    preferred_fill_ids.extend(food_id for food_id in protein_anchors if food_id in quantities)

    for food_id in preferred_fill_ids:
        current_totals = {key: 0.0 for key in gr.NUTRIENT_SUMMARY_META}  # noqa: SLF001
        for current_food_id, quantity_g in quantities.items():
            for nutrient_id, value in gr._tracked_totals(context.available[current_food_id], quantity_g).items():  # noqa: SLF001
                current_totals[nutrient_id] += value
        calorie_deficit = max(0.0, context.calorie_target_kcal - current_totals["energy_fibre_kcal"])
        if calorie_deficit <= max(
            float(context.basket_policy["booster_gap_floor"]) * 0.65,
            context.calorie_target_kcal * float(context.basket_policy["booster_gap_ratio"]) * 0.65,
        ):
            break

        food = context.available[food_id]
        if context.goal_profile == "maintenance":
            fill_ratio = 0.22 if food_id == carb_base else 0.12
        else:
            fill_ratio = 0.35 if food_id == carb_base else 0.18
        additional_grams = (
            100.0 * calorie_deficit * fill_ratio / max(float(food["energy_fibre_kcal"]), 1.0)
        )
        if additional_grams <= 0:
            continue
        quantities[food_id] += additional_grams
        gr._apply_goal_quantity_caps(chosen, context.available, quantities, context.goal_profile)  # noqa: SLF001


def _pick_seed_preserving_booster(
    context: PlannerContext,
    *,
    excluded: set[str],
    chosen: list[tuple[str, str]],
    prefer_novelty: bool,
) -> str | None:
    if not prefer_novelty:
        return gr._pick_diverse_candidate(  # noqa: SLF001
            "calorie_booster",
            context.available,
            context.role_scores["calorie_booster"],
            excluded,
            chosen,
            context.preferences,
            context.goal_profile,
        )

    role = "calorie_booster"
    role_scores = context.role_scores[role]
    candidate_ids = [
        food_id
        for food_id in context.role_orders[role]
        if food_id not in excluded and food_id in context.available
    ]
    if not candidate_ids:
        return None

    best_score = role_scores.get(candidate_ids[0], 0.0)
    heuristic_top_food_id = candidate_ids[0]
    window = gr._diversity_window(role, context.preferences) + 0.45  # noqa: SLF001
    shortlist = [food_id for food_id in candidate_ids if best_score - role_scores.get(food_id, 0.0) <= window]
    if not shortlist:
        shortlist = [heuristic_top_food_id]

    chosen_families = {str(context.available[food_id]["food_family"]) for food_id, _candidate_role in chosen if food_id in context.available}
    ranked_rows: list[tuple[float, int, str]] = []
    for food_id in shortlist:
        food = context.available[food_id]
        novelty_bonus = 0.08 if food_id != heuristic_top_food_id else -0.03
        if str(food["food_family"]) not in chosen_families:
            novelty_bonus += 0.05
        adjusted_score = float(role_scores.get(food_id, 0.0)) + novelty_bonus
        ranked_rows.append(
            (
                -adjusted_score,
                int(food["commonality_rank"]),
                food_id,
            )
        )
    ranked_rows.sort()
    return str(ranked_rows[0][2]) if ranked_rows else None


def _materialize_candidate(
    context: PlannerContext,
    seed: CandidateSeed,
    *,
    candidate_id: str,
    stores: Sequence[dict[str, object]] | None,
) -> dict[str, object]:
    available = context.available
    use_structured_materialization = seed.source == "model" and _structured_materialization_enabled(context)
    chosen = _align_model_seed_choices(context, seed, list(seed.chosen)) if use_structured_materialization else list(seed.chosen)
    excluded = {food_id for food_id, _role in chosen}
    if not chosen:
        raise ValueError("No generic foods could be selected for the recommendation.")

    quantities: dict[str, float] = {}
    protein_anchors = [food_id for food_id, role in chosen if role == "protein_anchor"]
    carb_base = next((food_id for food_id, role in chosen if role == "carb_base"), None)
    low_prep = bool(context.preferences["low_prep"])
    priority_profile = _priority_profile(context)

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
        if seed.source == "model":
            if float(priority_profile["calorie_tightness"]) >= 1.0 and _food_metric(food, "energy_fibre_kcal") <= 35.0:
                servings += 1
            elif float(priority_profile["calorie_completion_priority"]) >= 1.15 and gr._produce_cluster(food) == "fruit":  # noqa: SLF001
                servings += 1
        else:
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
    seed_intent_quantities = dict(quantities)

    total_nutrients = totals()
    calorie_deficit = max(0.0, context.calorie_target_kcal - total_nutrients["energy_fibre_kcal"])
    booster = None
    fat_target_g = context.nutrition_targets.get("fat")
    fat_gap = max(0.0, fat_target_g - total_nutrients["fat"]) if fat_target_g else 0.0
    if use_structured_materialization:
        _preserve_seed_fill(
            context,
            chosen=chosen,
            quantities=quantities,
            protein_anchors=protein_anchors,
            carb_base=carb_base,
        )
        total_nutrients = totals()
        calorie_deficit = max(0.0, context.calorie_target_kcal - total_nutrients["energy_fibre_kcal"])
        fat_gap = max(0.0, fat_target_g - total_nutrients["fat"]) if fat_target_g else 0.0
    booster_threshold = max(
        float(context.basket_policy["booster_gap_floor"]),
        context.calorie_target_kcal * float(context.basket_policy["booster_gap_ratio"]),
    )
    if seed.source == "model":
        booster_threshold *= 1.0 + (0.35 * float(priority_profile["calorie_tightness"]))
        if calorie_deficit < max(90.0, context.calorie_target_kcal * 0.045) and total_nutrients["protein"] >= (context.protein_target_g * 0.94):
            booster_threshold = float("inf")
    if bool(context.basket_policy["booster_enabled"]) and (
        calorie_deficit > booster_threshold or fat_gap > float(context.basket_policy["booster_fat_gap"])
    ):
        if use_structured_materialization:
            booster = _pick_structured_booster(
                context,
                excluded=excluded,
                chosen=chosen,
            )
        else:
            booster = gr._pick_diverse_candidate(  # noqa: SLF001
                "calorie_booster",
                context.available,
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
            if use_structured_materialization:
                booster_grams *= max(0.72, 0.95 - (0.15 * float(priority_profile["calorie_tightness"])))
            quantities[booster] = booster_grams

    gr._apply_goal_quantity_caps(chosen, available, quantities, context.goal_profile)  # noqa: SLF001
    if use_structured_materialization:
        _rebalance_seed_quantities(
            context,
            chosen=chosen,
            quantities=quantities,
            protein_anchors=protein_anchors,
            carb_base=carb_base,
            booster=booster,
        )
        _rebalance_role_calorie_shares(
            context,
            chosen=chosen,
            quantities=quantities,
            protein_anchors=protein_anchors,
            carb_base=carb_base,
            booster=booster,
        )
        _trim_allocation_overshoot(
            context,
            quantities=quantities,
            protein_anchors=protein_anchors,
            carb_base=carb_base,
            booster=booster,
        )
    elif seed.source != "model":
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
        elif context.goal_profile == "maintenance":
            overshoot_tolerance = max(90.0, context.calorie_target_kcal * 0.045)
            total_nutrients = totals()
            calorie_overshoot = total_nutrients["energy_fibre_kcal"] - context.calorie_target_kcal
            if calorie_overshoot > overshoot_tolerance and booster is not None and booster in quantities:
                booster_food = available[booster]
                min_booster_g = 5.0 if str(booster_food.get("food_family") or "") == "fat" else max(
                    float(booster_food.get("default_serving_g") or 0.0) * 0.5,
                    15.0,
                )
                reducible_g = max(0.0, quantities[booster] - min_booster_g)
                reduce_g = min(
                    reducible_g,
                    100.0 * calorie_overshoot / max(float(booster_food["energy_fibre_kcal"]), 1.0),
                )
                quantities[booster] = max(min_booster_g, quantities[booster] - reduce_g)

    total_nutrients = totals()
    calorie_deficit = max(0.0, context.calorie_target_kcal - total_nutrients["energy_fibre_kcal"])
    protein_close_enough = total_nutrients["protein"] >= (context.protein_target_g * 0.95)
    if use_structured_materialization:
        final_carb_fill_ratio, final_booster_fill_ratio = _final_fill_ratios(
            context,
            seed=seed,
            booster=booster,
            protein_close_enough=protein_close_enough,
        )
    else:
        final_carb_fill_ratio = float(context.basket_policy["final_carb_fill_ratio"])
        final_booster_fill_ratio = float(context.basket_policy["final_booster_fill_ratio"])
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
    materialization_debug = (
        _model_materialization_drift_summary(
            context,
            seed=seed,
            seed_intent_quantities=seed_intent_quantities,
            final_chosen=chosen,
            final_plan_quantities=plan_quantities,
        )
        if seed.source == "model"
        else None
    )
    if materialization_debug is not None:
        materialization_debug = dict(materialization_debug)
        materialization_debug["algorithm_mode"] = (
            "structured_materialization" if use_structured_materialization else "baseline_materialization"
        )
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
    source = seed.source
    if source == "model" and bool(response.get("adjusted_by_split")):
        source = "repaired_model"
    return _candidate_bundle_from_response(
        context,
        response=response,
        candidate_id=candidate_id,
        selection_trace=seed.selection_trace,
        heuristic_selection_score=seed.heuristic_selection_score,
        generator_score=seed.generator_score,
        source=source,
        source_backend=seed.source_backend,
        stores=stores,
        materialization_debug=materialization_debug,
    )


def _candidate_overlap(left: Mapping[str, object], right: Mapping[str, object]) -> float:
    left_ids = set(left["candidate_metadata"]["shopping_food_ids"])
    right_ids = set(right["candidate_metadata"]["shopping_food_ids"])
    union = left_ids | right_ids
    if not union:
        return 0.0
    return len(left_ids & right_ids) / len(union)


def _resolved_source_label(source_labels: set[str]) -> str:
    if "heuristic" in source_labels and len(source_labels) > 1:
        return "hybrid"
    if "repaired_model" in source_labels:
        return "repaired_model"
    if "model" in source_labels:
        return "model"
    return "heuristic"


def _merge_candidate_bundle(
    existing: dict[str, object],
    incoming: dict[str, object],
    *,
    match_type: str,
) -> None:
    existing_meta = existing["candidate_metadata"]
    incoming_meta = incoming["candidate_metadata"]
    source_labels = set(existing_meta.get("source_labels") or [existing_meta["source"]])
    source_labels.update(incoming_meta.get("source_labels") or [incoming_meta["source"]])
    existing_meta["source_labels"] = sorted(source_labels)
    existing_meta["source"] = _resolved_source_label(source_labels)
    existing_meta["generator_score"] = round(
        max(float(existing_meta.get("generator_score") or 0.0), float(incoming_meta.get("generator_score") or 0.0)),
        6,
    )
    existing_meta["origin_candidate_ids"] = sorted(
        {
            *existing_meta.get("origin_candidate_ids", [str(existing["candidate_id"])]),
            *incoming_meta.get("origin_candidate_ids", [str(incoming["candidate_id"])]),
        }
    )
    existing_meta["merged_candidate_ids"] = sorted(
        {
            *existing_meta.get("merged_candidate_ids", []),
            str(existing["candidate_id"]),
            str(incoming["candidate_id"]),
        }
    )
    existing_meta["dedupe_matches"] = sorted({*existing_meta.get("dedupe_matches", []), match_type})
    backend_labels = set(existing_meta.get("candidate_generator_backend_labels") or [])
    backend_labels.update([str(existing_meta.get("candidate_generator_backend") or "")])
    backend_labels.update(incoming_meta.get("candidate_generator_backend_labels") or [])
    backend_labels.update([str(incoming_meta.get("candidate_generator_backend") or "")])
    backend_labels.discard("")
    if backend_labels:
        existing_meta["candidate_generator_backend_labels"] = sorted(backend_labels)


def _candidate_priority_sort_key(candidate: Mapping[str, object]) -> tuple[int, float, float, str]:
    source = str(candidate["candidate_metadata"].get("source") or "heuristic")
    source_priority = {
        "hybrid": 0,
        "heuristic": 1,
        "repaired_model": 2,
        "model": 3,
    }.get(source, 9)
    return (
        source_priority,
        -float(candidate["candidate_metadata"].get("heuristic_selection_score") or 0.0),
        -float(candidate["candidate_metadata"].get("generator_score") or 0.0),
        str(candidate["candidate_id"]),
    )


def _candidate_source_labels(candidate: Mapping[str, object]) -> set[str]:
    metadata = candidate["candidate_metadata"]
    return set(metadata.get("source_labels") or [metadata.get("source") or "heuristic"])


def _best_heuristic_candidate_by_generation(candidates: Sequence[Mapping[str, object]]) -> dict[str, object] | None:
    heuristic_candidates = [candidate for candidate in candidates if "heuristic" in _candidate_source_labels(candidate)]
    if not heuristic_candidates:
        return None
    return max(
        heuristic_candidates,
        key=lambda candidate: (
            float(candidate["candidate_metadata"].get("heuristic_selection_score") or 0.0),
            float(candidate["candidate_metadata"].get("generator_score") or 0.0),
            -float(candidate["candidate_metadata"].get("unrealistic_basket_penalty") or 0.0),
            str(candidate["candidate_id"]),
        ),
    )


def _materially_different_from_heuristic_pool(
    candidate: Mapping[str, object],
    heuristic_candidates: Sequence[Mapping[str, object]],
) -> bool:
    if not heuristic_candidates:
        return False
    return any(
        bool(candidate_debug.compare_candidates(candidate, heuristic_candidate).get("materially_different"))
        for heuristic_candidate in heuristic_candidates
    )


def _dedupe_fused_candidates(
    candidates: Sequence[Mapping[str, object]],
    *,
    allow_near_duplicate_merge: bool,
) -> tuple[list[dict[str, object]], dict[str, dict[str, object]]]:
    deduped: list[dict[str, object]] = []
    for candidate in sorted(candidates, key=_candidate_priority_sort_key):
        candidate_copy = dict(candidate)
        candidate_copy["candidate_metadata"] = dict(candidate["candidate_metadata"])
        candidate_copy["request_context"] = dict(candidate["request_context"])
        candidate_copy["candidate_metadata"]["origin_candidate_ids"] = [str(candidate["candidate_id"])]

        exact_match = next(
            (
                existing
                for existing in deduped
                if tuple(existing["candidate_metadata"]["shopping_food_ids"]) == tuple(candidate_copy["candidate_metadata"]["shopping_food_ids"])
            ),
            None,
        )
        if exact_match is not None:
            _merge_candidate_bundle(exact_match, candidate_copy, match_type="exact")
            continue

        if allow_near_duplicate_merge:
            candidate_sources = _candidate_source_labels(candidate_copy)
            near_match = next(
                (
                    existing
                    for existing in deduped
                    if existing["candidate_metadata"]["role_counts"] == candidate_copy["candidate_metadata"]["role_counts"]
                    and _candidate_overlap(existing, candidate_copy) >= 0.8
                    and _candidate_source_labels(existing) != candidate_sources
                    and not bool(candidate_debug.compare_candidates(existing, candidate_copy).get("materially_different"))
                ),
                None,
            )
            if near_match is not None:
                _merge_candidate_bundle(near_match, candidate_copy, match_type="near_duplicate")
                continue

        deduped.append(candidate_copy)

    if allow_near_duplicate_merge:
        heuristic_candidates = [candidate for candidate in deduped if "heuristic" in _candidate_source_labels(candidate)]
        surviving_distinct_model_candidates = [
            candidate
            for candidate in deduped
            if "model" in _candidate_source_labels(candidate)
            and _materially_different_from_heuristic_pool(candidate, heuristic_candidates)
        ]
        if not surviving_distinct_model_candidates:
            baseline_heuristic_candidate = _best_heuristic_candidate_by_generation(candidates)
            materially_different_model_candidates = []
            for candidate in candidates:
                if "model" not in _candidate_source_labels(candidate):
                    continue
                if baseline_heuristic_candidate is None:
                    continue
                similarity = candidate_debug.compare_candidates(candidate, baseline_heuristic_candidate)
                if bool(similarity.get("materially_different")):
                    materially_different_model_candidates.append((candidate, similarity))
            if materially_different_model_candidates:
                preserved_candidate, _similarity = max(
                    materially_different_model_candidates,
                    key=lambda row: (
                        float(row[0]["candidate_metadata"].get("generator_score") or 0.0),
                        float(row[0]["candidate_metadata"].get("heuristic_selection_score") or 0.0),
                        str(row[0]["candidate_id"]),
                    ),
                )
                preserved_copy = dict(preserved_candidate)
                preserved_copy["candidate_metadata"] = dict(preserved_candidate["candidate_metadata"])
                preserved_copy["request_context"] = dict(preserved_candidate["request_context"])
                preserved_copy["candidate_metadata"]["origin_candidate_ids"] = [str(preserved_candidate["candidate_id"])]
                preserved_copy["candidate_metadata"]["dedupe_matches"] = sorted(
                    {*(preserved_copy["candidate_metadata"].get("dedupe_matches") or []), "preserved_model_distinct"}
                )
                preserved_copy["candidate_metadata"]["preserved_model_distinct_candidate"] = True
                if not any(
                    tuple(existing["candidate_metadata"]["shopping_food_ids"]) == tuple(preserved_copy["candidate_metadata"]["shopping_food_ids"])
                    for existing in deduped
                ):
                    deduped.append(preserved_copy)

    raw_candidate_resolution: dict[str, dict[str, object]] = {}
    for index, candidate in enumerate(deduped):
        candidate_id = f"candidate_{index:02d}"
        candidate["candidate_id"] = candidate_id
        candidate["candidate_metadata"]["candidate_id"] = candidate_id
        origin_candidate_ids = [str(value) for value in candidate["candidate_metadata"].get("origin_candidate_ids", [candidate_id])]
        merge_outcome = "survived_as_is"
        if bool(candidate["candidate_metadata"].get("preserved_model_distinct_candidate")):
            merge_outcome = "preserved_model_distinct"
        if len(origin_candidate_ids) > 1:
            merge_outcome = "became_hybrid" if str(candidate["candidate_metadata"].get("source") or "") == "hybrid" else "merged"
        candidate["candidate_metadata"]["merge_outcome"] = merge_outcome
        for raw_candidate_id in origin_candidate_ids:
            raw_candidate_resolution[raw_candidate_id] = {
                "fused_candidate_id": candidate_id,
                "merge_outcome": merge_outcome if raw_candidate_id != candidate_id or len(origin_candidate_ids) > 1 else "survived_as_is",
                "fused_source": str(candidate["candidate_metadata"].get("source") or "heuristic"),
                "source_labels": list(candidate["candidate_metadata"].get("source_labels") or [candidate["candidate_metadata"].get("source") or "heuristic"]),
                "dedupe_matches": list(candidate["candidate_metadata"].get("dedupe_matches", [])),
            }
    return deduped, raw_candidate_resolution


def _candidate_to_seed(candidate: Mapping[str, object]) -> CandidateSeed:
    recommendation = dict(candidate.get("recommendation") or {})
    shopping_list = recommendation.get("shopping_list") if isinstance(recommendation.get("shopping_list"), Sequence) else []
    chosen = [
        (str(item.get("generic_food_id") or ""), str(item.get("role") or ""))
        for item in shopping_list
        if (
            str(item.get("generic_food_id") or "")
            and str(item.get("role") or "")
            and str(item.get("role") or "") != "calorie_booster"
        )
    ]
    metadata = dict(candidate.get("candidate_metadata") or {})
    return CandidateSeed(
        chosen=chosen,
        excluded={food_id for food_id, _role in chosen},
        selection_trace=list(metadata.get("selection_trace") or []),
        heuristic_selection_score=float(metadata.get("heuristic_selection_score") or 0.0),
        generator_score=float(metadata.get("generator_score") or 0.0),
        source=str(metadata.get("source") or "heuristic"),
        source_backend=str(metadata.get("candidate_generator_backend") or metadata.get("source") or "heuristic"),
    )


def _select_heuristic_reference_seed(
    heuristic_candidates: Sequence[Mapping[str, object]],
    *,
    fallback_seed: CandidateSeed | None,
) -> CandidateSeed | None:
    if not heuristic_candidates:
        return fallback_seed

    try:
        feature_rows = plan_scorer.build_request_feature_rows(heuristic_candidates)
        best_index = max(
            range(len(heuristic_candidates)),
            key=lambda index: (
                plan_scorer.training_candidate_label(feature_rows[index]),
                float((heuristic_candidates[index].get("candidate_metadata") or {}).get("heuristic_selection_score") or 0.0),
            ),
        )
        return _candidate_to_seed(heuristic_candidates[best_index])
    except Exception:  # noqa: BLE001
        return _candidate_to_seed(heuristic_candidates[0]) if heuristic_candidates else fallback_seed


def _build_candidate_pool(
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
    stores: Sequence[dict[str, object]] | None,
    candidate_count: int,
    candidate_generation_config: dict[str, object] | None = None,
) -> tuple[list[dict[str, object]], list[dict[str, object]], dict[str, object]]:
    normalized_candidate_config = normalize_candidate_generation_config(candidate_generation_config)
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
        nearby_store_count=len(stores or []),
        algorithm_config=normalized_candidate_config,
    )
    requested_count = max(1, min(MAX_CANDIDATE_COUNT, int(candidate_count)))
    heuristic_seeds = _generate_candidate_seeds(context, requested_count)
    heuristic_candidates = [
        _materialize_candidate(
            context,
            seed,
            candidate_id=f"heuristic_{index:02d}",
            stores=stores,
        )
        for index, seed in enumerate(heuristic_seeds)
    ]
    heuristic_reference_seed = _select_heuristic_reference_seed(
        heuristic_candidates,
        fallback_seed=heuristic_seeds[0] if heuristic_seeds else None,
    )

    model_candidates: list[dict[str, object]] = []
    candidate_generator_backend = None
    candidate_generator_model_path = None
    if normalized_candidate_config["enable_model_candidates"]:
        candidate_generator_model_path = Path(str(normalized_candidate_config["candidate_generator_model_path"]))
        candidate_bundle = model_candidate_generator.load_bundle(candidate_generator_model_path)
        candidate_generator_backend = str(candidate_bundle.get("backend") or "unknown")
        configured_backend = str(normalized_candidate_config["candidate_generator_backend"])
        if configured_backend != "auto" and configured_backend != candidate_generator_backend:
            raise model_candidate_generator.ModelCandidateArtifactError(
                "Loaded candidate-generator artifact backend does not match candidate_generator_backend."
            )
        model_seeds = _generate_model_candidate_seeds(
            context,
            bundle=candidate_bundle,
            candidate_count=int(normalized_candidate_config["model_candidate_count"]),
            source_backend=candidate_generator_backend,
            heuristic_reference_seed=heuristic_reference_seed,
        )
        model_candidates = [
            _materialize_candidate(
                context,
                seed,
                candidate_id=f"model_{index:02d}",
                stores=stores,
            )
            for index, seed in enumerate(model_seeds)
        ]

    raw_candidates = [*heuristic_candidates, *model_candidates]
    candidates, raw_candidate_resolution = _dedupe_fused_candidates(
        raw_candidates,
        allow_near_duplicate_merge=bool(model_candidates),
    )
    if not candidates:
        raise ValueError("No generic foods could be selected for the recommendation.")
    debug_payload = {
        "model_candidates_enabled": bool(normalized_candidate_config["enable_model_candidates"]),
        "algorithm_version": str(normalized_candidate_config["algorithm_version"]),
        "structured_complementarity_enabled": bool(normalized_candidate_config["structured_complementarity_enabled"]),
        "structured_materialization_enabled": bool(normalized_candidate_config["structured_materialization_enabled"]),
        "heuristic_candidate_count": len(heuristic_candidates),
        "model_candidate_count": len(model_candidates),
        "raw_candidate_count": len(raw_candidates),
        "fused_candidate_count": len(candidates),
        "candidate_generator_model_path": str(candidate_generator_model_path) if candidate_generator_model_path else None,
        "candidate_generator_backend": candidate_generator_backend,
        "raw_candidate_resolution": raw_candidate_resolution,
    }
    return raw_candidates, candidates, debug_payload


def _score_and_rank_candidates(
    candidates: Sequence[Mapping[str, object]],
    *,
    scorer_bundle: Mapping[str, object],
) -> list[dict[str, object]]:
    feature_rows = plan_scorer.build_request_feature_rows(candidates)
    heuristic_scores = [plan_scorer.heuristic_candidate_label(row) for row in feature_rows]
    model_scores = plan_scorer.score_feature_rows(scorer_bundle, feature_rows)

    def ranking_adjustment(feature_row: Mapping[str, object]) -> float:
        goal_profile = str(feature_row.get("goal_profile") or "generic_balanced")
        adjustment = (
            0.24 * float(feature_row.get("goal_structure_alignment_score") or 0.0)
            - 0.08 * float(feature_row.get("role_share_gap_total") or 0.0)
        )
        if goal_profile == "muscle_gain":
            adjustment += 0.14 * min(float(feature_row.get("dairy_or_egg_anchor_count") or 0.0), 1.0)
            adjustment += 0.08 * min(float(feature_row.get("fruit_produce_count") or 0.0), 1.0)
            adjustment += 0.35 * float(feature_row.get("calorie_booster_share") or 0.0)
            if float(feature_row.get("calorie_booster_count") or 0.0) <= 0.0:
                adjustment -= 0.18
        elif goal_profile == "fat_loss":
            adjustment += 0.08 * min(float(feature_row.get("high_volume_produce_count") or 0.0), 3.0)
            adjustment -= 0.28 * float(feature_row.get("calorie_booster_count") or 0.0)
            adjustment -= 0.08 * max(float(feature_row.get("fruit_produce_count") or 0.0) - 1.0, 0.0)
        elif goal_profile == "maintenance":
            booster_share = float(feature_row.get("calorie_booster_share") or 0.0)
            if 0.04 <= booster_share <= 0.16:
                adjustment += 0.08
            adjustment += 0.05 * min(float(feature_row.get("fruit_produce_count") or 0.0), 1.0)
        elif goal_profile == "high_protein_vegetarian":
            adjustment += 0.2 * min(
                float(feature_row.get("soy_protein_anchor_count") or 0.0),
                float(feature_row.get("dairy_or_egg_anchor_count") or 0.0),
                1.0,
            )
            adjustment -= 0.4 * float(feature_row.get("animal_protein_anchor_count") or 0.0)
            adjustment -= 0.08 * float(feature_row.get("legume_protein_anchor_count") or 0.0)
        elif goal_profile == "budget_friendly_healthy":
            adjustment += 0.72 * min(float(feature_row.get("budget_support_anchor_count") or 0.0), 1.0)
            adjustment -= 1.05 * max(float(feature_row.get("legume_protein_anchor_count") or 0.0) - 1.0, 0.0)
            adjustment += 0.08 * min(float(feature_row.get("low_cost_produce_count") or 0.0), 2.0)
            adjustment += 0.12 * float(feature_row.get("calorie_booster_share") or 0.0)
            adjustment -= min(max(float(feature_row.get("fat_abs_gap_g") or 0.0) - 8.0, 0.0), 35.0) * 0.018
            adjustment -= min(max(float(feature_row.get("carbohydrate_abs_gap_g") or 0.0) - 25.0, 0.0), 80.0) * 0.006
            adjustment -= min(max(float(feature_row.get("protein_abs_gap_g") or 0.0) - 8.0, 0.0), 35.0) * 0.022
        return round(adjustment, 6)

    ranked = [
        {
            "candidate": candidate,
            "feature_row": feature_row,
            "heuristic_score": float(heuristic_score),
            "model_score": float(model_score),
            "ranking_score": round(float(model_score) + ranking_adjustment(feature_row), 6),
        }
        for candidate, feature_row, heuristic_score, model_score in zip(
            candidates,
            feature_rows,
            heuristic_scores,
            model_scores,
            strict=True,
        )
    ]
    return sorted(
        ranked,
        key=lambda row: (-row["ranking_score"], -row["model_score"], -row["heuristic_score"], str(row["candidate"]["candidate_id"])),
    )


def _candidate_origin_labels(candidate: Mapping[str, object]) -> set[str]:
    metadata = candidate.get("candidate_metadata")
    if not isinstance(metadata, Mapping):
        return {"heuristic"}
    labels = {str(value) for value in metadata.get("source_labels") or [metadata.get("source") or "heuristic"] if str(value)}
    normalized: set[str] = set()
    for label in labels:
        if label == "repaired_model":
            normalized.update({"repaired_model", "model"})
        else:
            normalized.add(label)
    return normalized or {"heuristic"}


def _best_ranked_entry(
    ranked_rows: Sequence[Mapping[str, object]],
    *,
    origin: str,
    pure_only: bool = False,
) -> dict[str, object] | None:
    for row in ranked_rows:
        candidate = row.get("candidate")
        if not isinstance(candidate, Mapping):
            continue
        labels = _candidate_origin_labels(candidate)
        if origin == "heuristic":
            if "heuristic" not in labels:
                continue
            if pure_only and labels != {"heuristic"}:
                continue
            return dict(row)
        if origin == "model":
            if "model" not in labels and "repaired_model" not in labels:
                continue
            if pure_only and "heuristic" in labels:
                continue
            return dict(row)
    return None


def _serialize_similarity(metrics: dict[str, object] | None) -> dict[str, object] | None:
    if not metrics:
        return None
    return {
        "jaccard_overlap": round(float(metrics.get("jaccard_overlap") or 0.0), 6),
        "shared_food_count": int(metrics.get("shared_food_count") or 0),
        "changed_food_count": int(metrics.get("changed_food_count") or 0),
        "role_assignment_changes": int(metrics.get("role_assignment_changes") or 0),
        "cost_delta": round(float(metrics.get("cost_delta") or 0.0), 6),
        "protein_gap_delta_g": round(float(metrics.get("protein_gap_delta_g") or 0.0), 6),
        "calorie_gap_delta_kcal": round(float(metrics.get("calorie_gap_delta_kcal") or 0.0), 6),
        "materially_different": bool(metrics.get("materially_different")),
        "difference_summary": str(metrics.get("difference_summary") or ""),
    }


def _candidate_similarity(left: Mapping[str, object], right: Mapping[str, object] | None) -> dict[str, object] | None:
    if right is None:
        return None
    return _serialize_similarity(candidate_debug.compare_candidates(left, right))


def _candidate_role_items(candidate: Mapping[str, object]) -> list[tuple[str, str]]:
    recommendation = dict(candidate.get("recommendation") or {})
    shopping_list = recommendation.get("shopping_list") if isinstance(recommendation.get("shopping_list"), Sequence) else []
    return [
        (str(item.get("generic_food_id") or ""), str(item.get("role") or ""))
        for item in shopping_list
        if str(item.get("generic_food_id") or "") and str(item.get("role") or "")
    ]


def _candidate_role_substitutions(
    reference_candidate: Mapping[str, object] | None,
    comparison_candidate: Mapping[str, object] | None,
) -> list[dict[str, object]]:
    if reference_candidate is None or comparison_candidate is None:
        return []

    reference_items = _candidate_role_items(reference_candidate)
    comparison_items = _candidate_role_items(comparison_candidate)
    occurrence_by_role: Counter[str] = Counter()
    substitutions: list[dict[str, object]] = []
    max_length = max(len(reference_items), len(comparison_items))
    for index in range(max_length):
        reference_food_id, reference_role = reference_items[index] if index < len(reference_items) else ("", "")
        comparison_food_id, comparison_role = comparison_items[index] if index < len(comparison_items) else ("", "")
        role = reference_role or comparison_role
        if not role:
            continue
        occurrence_index = int(occurrence_by_role[role])
        occurrence_by_role[role] += 1
        if reference_food_id == comparison_food_id:
            continue
        substitutions.append(
            {
                "role": role,
                "occurrence_index": occurrence_index,
                "from_food_id": reference_food_id or None,
                "to_food_id": comparison_food_id or None,
                "summary": f"{role} #{occurrence_index + 1}: {reference_food_id or 'none'} -> {comparison_food_id or 'none'}",
            }
        )
    return substitutions


def _produce_difference_summary(
    *,
    reference_candidate: Mapping[str, object] | None,
    comparison_candidate: Mapping[str, object] | None,
) -> str:
    if reference_candidate is None or comparison_candidate is None:
        return ""

    reference_produce_ids = [
        food_id
        for food_id, role in _candidate_role_items(reference_candidate)
        if role == "produce"
    ]
    comparison_produce_ids = [
        food_id
        for food_id, role in _candidate_role_items(comparison_candidate)
        if role == "produce"
    ]
    if not reference_produce_ids or not comparison_produce_ids:
        return ""

    reference_clusters = [_produce_combo_cluster_for_food_id(food_id) for food_id in reference_produce_ids]
    comparison_clusters = [_produce_combo_cluster_for_food_id(food_id) for food_id in comparison_produce_ids]
    if comparison_clusters.count("leafy_dense") >= 2:
        return "Leafy-heavy produce trio stayed repetitive."
    if len(set(comparison_clusters)) < len(set(reference_clusters)):
        return "Produce mix became less complementary than the heuristic baseline."
    if "watery_practical" in comparison_clusters and "watery_practical" not in reference_clusters:
        return "Model produce swap added a lighter practical produce item."
    if comparison_clusters == reference_clusters and reference_produce_ids != comparison_produce_ids:
        return "Same produce structure, but with different items."
    return "Produce mix shifted, but the overall role pattern stayed similar."


def _feature_delta_snapshot(
    selected_row: Mapping[str, object],
    comparison_row: Mapping[str, object] | None,
) -> dict[str, object] | None:
    if comparison_row is None:
        return None
    selected_features = selected_row["feature_row"]
    comparison_features = comparison_row["feature_row"]
    return {
        "protein_gap_delta_g": round(
            float(comparison_features.get("protein_abs_gap_g") or 0.0) - float(selected_features.get("protein_abs_gap_g") or 0.0),
            6,
        ),
        "calorie_gap_delta_kcal": round(
            float(comparison_features.get("calorie_abs_gap_kcal") or 0.0) - float(selected_features.get("calorie_abs_gap_kcal") or 0.0),
            6,
        ),
        "cost_delta": round(
            float(comparison_features.get("estimated_basket_cost") or 0.0) - float(selected_features.get("estimated_basket_cost") or 0.0),
            6,
        ),
        "role_diversity_delta": round(
            float(comparison_features.get("role_diversity_count") or 0.0) - float(selected_features.get("role_diversity_count") or 0.0),
            6,
        ),
        "food_family_diversity_delta": round(
            float(comparison_features.get("food_family_diversity_count") or 0.0)
            - float(selected_features.get("food_family_diversity_count") or 0.0),
            6,
        ),
        "repetition_penalty_delta": round(
            float(comparison_features.get("repetition_penalty") or 0.0) - float(selected_features.get("repetition_penalty") or 0.0),
            6,
        ),
        "unrealistic_basket_penalty_delta": round(
            float(comparison_features.get("unrealistic_basket_penalty") or 0.0)
            - float(selected_features.get("unrealistic_basket_penalty") or 0.0),
            6,
        ),
        "preference_match_delta": round(
            float(comparison_features.get("preference_match_score") or 0.0)
            - float(selected_features.get("preference_match_score") or 0.0),
            6,
        ),
        "alternative_quality_score_delta": round(
            float(comparison_features.get("alternative_quality_score") or 0.0)
            - float(selected_features.get("alternative_quality_score") or 0.0),
            6,
        ),
    }


def _feature_loss_dimensions(
    feature_deltas: Mapping[str, object] | None,
) -> dict[str, float]:
    if not feature_deltas:
        return {}

    loss_dimensions: dict[str, float] = {}
    thresholds = {
        "protein_gap_delta_g": 6.0,
        "calorie_gap_delta_kcal": 80.0,
        "cost_delta": 0.75,
        "repetition_penalty_delta": 0.15,
        "unrealistic_basket_penalty_delta": 0.12,
        "preference_match_delta": 0.35,
    }
    for key, threshold in thresholds.items():
        value = float(feature_deltas.get(key) or 0.0)
        if key == "preference_match_delta":
            if value <= -threshold:
                loss_dimensions[key] = round(value, 6)
            continue
        if value >= threshold:
            loss_dimensions[key] = round(value, 6)
    return loss_dimensions


def _loss_reason_from_feature_deltas(
    feature_deltas: Mapping[str, object] | None,
) -> str | None:
    if not feature_deltas:
        return None
    issue_scores = {
        "protein fit": max(float(feature_deltas.get("protein_gap_delta_g") or 0.0), 0.0) / 6.0,
        "calorie fit": max(float(feature_deltas.get("calorie_gap_delta_kcal") or 0.0), 0.0) / 80.0,
        "cost": max(float(feature_deltas.get("cost_delta") or 0.0), 0.0) / 0.75,
        "repetition penalty": max(float(feature_deltas.get("repetition_penalty_delta") or 0.0), 0.0) / 0.15,
        "realism penalty": max(float(feature_deltas.get("unrealistic_basket_penalty_delta") or 0.0), 0.0) / 0.12,
    }
    ranked_issues = [label for label, magnitude in sorted(issue_scores.items(), key=lambda item: item[1], reverse=True) if magnitude >= 0.75]
    if not ranked_issues:
        return "lost on several small penalties despite being materially different"
    if len(ranked_issues) == 1:
        return f"lost mainly on {ranked_issues[0]}"
    if len(ranked_issues) == 2:
        return f"lost mainly on {ranked_issues[0]} and {ranked_issues[1]}"
    return "lost on several small penalties despite being materially different"


def _likely_failure_mode(
    *,
    feature_deltas: Mapping[str, object] | None,
    role_substitutions: Sequence[Mapping[str, object]],
    best_heuristic_candidate: Mapping[str, object] | None,
    best_model_candidate: Mapping[str, object] | None,
) -> str:
    if best_model_candidate is None:
        return "candidate_pool_not_exploring_the_right_substitutions"
    if best_heuristic_candidate is None:
        return "insufficient_heuristic_reference"

    changed_roles = {str(item.get("role") or "") for item in role_substitutions if str(item.get("role") or "")}
    feature_deltas = dict(feature_deltas or {})

    heuristic_protein_ids = {
        food_id for food_id, role in _candidate_role_items(best_heuristic_candidate) if role == "protein_anchor"
    }
    model_protein_ids = {
        food_id for food_id, role in _candidate_role_items(best_model_candidate) if role == "protein_anchor"
    }

    if "calorie_booster" in changed_roles:
        return "bad_booster_behavior"
    if changed_roles & {"carb_base"} and (
        float(feature_deltas.get("protein_gap_delta_g") or 0.0) >= 8.0
        or float(feature_deltas.get("cost_delta") or 0.0) >= 0.75
        or float(feature_deltas.get("calorie_gap_delta_kcal") or 0.0) >= 120.0
    ):
        return "poor_carb_base_calibration"
    if changed_roles & {"protein_anchor"} and float(feature_deltas.get("protein_gap_delta_g") or 0.0) >= 8.0:
        return "weak_protein_anchor_choice"
    if heuristic_protein_ids == model_protein_ids and float(feature_deltas.get("protein_gap_delta_g") or 0.0) >= 8.0:
        return "quantity_materialization_mismatch"
    if changed_roles == {"produce"}:
        return "poor_produce_choice"
    if not changed_roles:
        return "candidate_pool_not_exploring_the_right_substitutions"
    return "candidate_pool_not_exploring_the_right_substitutions"


def _why_no_model_win_yet(
    *,
    selected_candidate_source: str,
    best_materially_different_model_row: Mapping[str, object] | None,
    materially_different_model_candidates_surviving_count: int,
    failure_mode: str | None,
    loss_reason: str | None,
) -> str:
    if selected_candidate_source in {"model", "repaired_model", "hybrid"}:
        return "A materially different model candidate won for this request."
    if best_materially_different_model_row is None:
        return "No materially-different model candidate survived long enough to challenge the heuristic winner."
    if materially_different_model_candidates_surviving_count <= 0:
        return "Materially-different model candidates were generated, but they did not survive fusion."
    failure_mode_label = str(failure_mode or "").replace("_", " ")
    if failure_mode_label and loss_reason:
        return f"Materially-different model candidates survived, but the strongest one still lost due to {failure_mode_label}. It {loss_reason}."
    if loss_reason:
        return f"Materially-different model candidates survived, but the strongest one still {loss_reason}."
    return "Materially-different model candidates survived, but they were still clearly lower quality than the heuristic winner."


def _candidate_reason_details(
    ranked_row: Mapping[str, object],
    *,
    selected_row: Mapping[str, object],
    raw_resolution: Mapping[str, object] | None = None,
) -> tuple[list[str], str]:
    resolution = dict(raw_resolution or {})
    candidate = ranked_row["candidate"]
    metadata = candidate["candidate_metadata"]
    materialization_debug = dict(metadata.get("materialization_debug") or {})
    merge_outcome = str(resolution.get("merge_outcome") or metadata.get("merge_outcome") or "survived_as_is")
    dedupe_matches = list(resolution.get("dedupe_matches") or metadata.get("dedupe_matches") or [])
    if merge_outcome in {"merged", "became_hybrid"}:
        if "near_duplicate" in dedupe_matches:
            return ["merged_near_duplicate"], "Merged as a near-duplicate before final ranking."
        return ["merged_exact_duplicate"], "Merged as an exact duplicate before final ranking."
    if merge_outcome == "preserved_model_distinct":
        return ["preserved_model_distinct"], "Kept as the strongest materially different model alternative."
    if str(candidate["candidate_id"]) == str(selected_row["candidate"]["candidate_id"]):
        return ["selected_winner"], "Selected winner after scorer ranking."

    tags = ["lost_on_scorer_score"]
    candidate_features = ranked_row["feature_row"]
    selected_features = selected_row["feature_row"]
    score_gap = float(selected_row["model_score"]) - float(ranked_row["model_score"])
    reasons: list[str] = [f"Lower scorer score by {score_gap:.3f}."]

    if float(candidate_features.get("protein_abs_gap_g") or 0.0) > float(selected_features.get("protein_abs_gap_g") or 0.0) + 5.0:
        tags.append("worse_protein_fit")
        reasons.append("Worse protein fit.")
    if float(candidate_features.get("calorie_abs_gap_kcal") or 0.0) > float(selected_features.get("calorie_abs_gap_kcal") or 0.0) + 50.0:
        tags.append("worse_calorie_fit")
        reasons.append("Worse calorie fit.")
    if float(candidate_features.get("macro_gap_ratio_sum") or 0.0) > float(selected_features.get("macro_gap_ratio_sum") or 0.0) + 0.12:
        tags.append("worse_macro_fit")
        reasons.append("Weaker overall macro and micronutrient fit.")
    if float(candidate_features.get("estimated_basket_cost") or 0.0) > float(selected_features.get("estimated_basket_cost") or 0.0) + 0.5:
        tags.append("higher_cost")
        reasons.append("Higher basket cost.")
    if float(candidate_features.get("unrealistic_basket_penalty") or 0.0) > float(selected_features.get("unrealistic_basket_penalty") or 0.0) + 0.08:
        tags.append("worse_realism_penalty")
        reasons.append("Higher realism penalty.")
    if float(candidate_features.get("repetition_penalty") or 0.0) > float(selected_features.get("repetition_penalty") or 0.0) + 0.08:
        tags.append("more_repetitive")
        reasons.append("More repetitive basket structure.")
    drift_summary = str(materialization_debug.get("summary") or "")
    if drift_summary in {
        "booster introduced and basket converged toward heuristic",
        "protein/carb rebalance erased candidate distinction",
    }:
        tags.append("materialization_drift")
        reasons.append(f"Materialization drifted: {drift_summary}.")

    return tags, " ".join(reasons[:3])


def _model_distinctness_summary(
    heuristic_ranked_rows: Sequence[Mapping[str, object]],
    model_ranked_rows: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    if not heuristic_ranked_rows or not model_ranked_rows:
        return {
            "average_heuristic_model_overlap_jaccard": 0.0,
            "average_model_to_best_heuristic_overlap_jaccard": 0.0,
            "model_candidates_materially_different_count": 0,
            "model_candidates_mostly_near_duplicates": False,
            "best_match_summaries": {},
        }

    pairwise_overlaps: list[float] = []
    best_match_overlaps: list[float] = []
    materially_different_count = 0
    best_match_summaries: dict[str, dict[str, object]] = {}

    for model_row in model_ranked_rows:
        model_candidate = model_row["candidate"]
        comparisons = []
        for heuristic_row in heuristic_ranked_rows:
            metrics = candidate_debug.compare_candidates(model_candidate, heuristic_row["candidate"])
            pairwise_overlaps.append(float(metrics["jaccard_overlap"]))
            comparisons.append((heuristic_row["candidate"], metrics))
        best_match_candidate, best_match_metrics = max(
            comparisons,
            key=lambda item: (float(item[1]["jaccard_overlap"]), -int(item[1]["changed_food_count"])),
        )
        best_match_overlaps.append(float(best_match_metrics["jaccard_overlap"]))
        if bool(best_match_metrics["materially_different"]):
            materially_different_count += 1
        best_match_summaries[str(model_candidate["candidate_id"])] = {
            "best_heuristic_candidate_id": str(best_match_candidate["candidate_id"]),
            "metrics": _serialize_similarity(best_match_metrics),
        }

    average_pairwise_overlap = sum(pairwise_overlaps) / len(pairwise_overlaps)
    average_best_overlap = sum(best_match_overlaps) / len(best_match_overlaps)
    mostly_near_duplicates = materially_different_count < max(1, len(model_ranked_rows) / 2.0) and average_best_overlap >= 0.67
    return {
        "average_heuristic_model_overlap_jaccard": round(average_pairwise_overlap, 6),
        "average_model_to_best_heuristic_overlap_jaccard": round(average_best_overlap, 6),
        "model_candidates_materially_different_count": materially_different_count,
        "model_candidates_mostly_near_duplicates": bool(mostly_near_duplicates),
        "best_match_summaries": best_match_summaries,
    }


def _candidate_debug_row(
    ranked_row: Mapping[str, object],
    *,
    selected_row: Mapping[str, object],
    selected_candidate: Mapping[str, object],
    best_heuristic_candidate: Mapping[str, object] | None,
    best_model_candidate: Mapping[str, object] | None,
    raw_resolution: Mapping[str, object] | None = None,
    include_features: bool = False,
) -> dict[str, object]:
    candidate = ranked_row["candidate"]
    metadata = candidate["candidate_metadata"]
    resolution = dict(raw_resolution or {})
    selected = bool(
        str(candidate["candidate_id"]) == str(selected_candidate["candidate_id"])
        or str(resolution.get("fused_candidate_id") or "") == str(selected_candidate["candidate_id"])
    )
    reason_tags, reason_summary = _candidate_reason_details(
        ranked_row,
        selected_row=selected_row,
        raw_resolution=raw_resolution,
    )
    row = {
        "candidate_id": str(candidate["candidate_id"]),
        "source": str(metadata.get("source") or "heuristic"),
        "source_labels": list(metadata.get("source_labels") or [metadata.get("source") or "heuristic"]),
        "shopping_food_ids": list(metadata.get("shopping_food_ids") or []),
        "chosen_food_ids": list(metadata.get("chosen_food_ids") or []),
        "selection_trace": list(metadata.get("selection_trace") or []),
        "role_counts": dict(metadata.get("role_counts") or {}),
        "heuristic_selection_score": round(float(metadata.get("heuristic_selection_score") or 0.0), 6),
        "generator_score": round(float(metadata.get("generator_score") or 0.0), 6),
        "heuristic_score": round(float(ranked_row["heuristic_score"]), 6),
        "model_score": round(float(ranked_row["model_score"]), 6),
        "dedupe_matches": list(resolution.get("dedupe_matches") or metadata.get("dedupe_matches") or []),
        "fusion_status": str(resolution.get("merge_outcome") or metadata.get("merge_outcome") or "survived_as_is"),
        "fused_candidate_id": str(resolution.get("fused_candidate_id") or candidate["candidate_id"]),
        "fused_source": str(resolution.get("fused_source") or metadata.get("source") or "heuristic"),
        "merged_candidate_ids": list(metadata.get("merged_candidate_ids") or []),
        "origin_candidate_ids": list(metadata.get("origin_candidate_ids") or [candidate["candidate_id"]]),
        "selected": selected,
        "overlap_with_selected_candidate": _candidate_similarity(candidate, selected_candidate),
        "overlap_with_best_heuristic_candidate": _candidate_similarity(candidate, best_heuristic_candidate),
        "overlap_with_best_model_candidate": _candidate_similarity(candidate, best_model_candidate),
        "selection_reason_tags": reason_tags,
        "selection_reason_summary": reason_summary,
        "score_gap_to_selected": round(float(selected_row["model_score"]) - float(ranked_row["model_score"]), 6),
        "materialization_debug": dict(metadata.get("materialization_debug") or {}),
        "materialization_drift_summary": str((metadata.get("materialization_debug") or {}).get("summary") or ""),
        "materialization_drift_score": (
            round(float((metadata.get("materialization_debug") or {}).get("drift_score") or 0.0), 6)
            if metadata.get("materialization_debug")
            else None
        ),
    }
    if include_features:
        row["features"] = {
            key: ranked_row["feature_row"][key]
            for key in (*plan_scorer.NUMERIC_FEATURES, *plan_scorer.BOOLEAN_FEATURES, *plan_scorer.CATEGORICAL_FEATURES)
        }
    return row


def _algorithmic_faithfulness_summary(
    ranked_row: Mapping[str, object],
) -> dict[str, object]:
    candidate = ranked_row["candidate"]
    metadata = candidate["candidate_metadata"]
    feature_row = ranked_row["feature_row"]
    materialization_debug = dict(metadata.get("materialization_debug") or {})
    structured_term_totals: dict[str, float] = {
        "complementarity": 0.0,
        "practicality": 0.0,
        "nutrient_support": 0.0,
        "novelty": 0.0,
    }
    for step in metadata.get("selection_trace") or []:
        for term_name, value in dict(step.get("structured_terms") or {}).items():
            if term_name in structured_term_totals:
                structured_term_totals[term_name] += float(value or 0.0)

    term_scores = {
        "complementarity": round(structured_term_totals["complementarity"], 6),
        "diversity": round(structured_term_totals["novelty"] + max(structured_term_totals["complementarity"], 0.0), 6),
        "nutrition_fit": round(
            max(
                0.0,
                2.8
                - (float(feature_row.get("protein_abs_gap_g") or 0.0) / 28.0)
                - (float(feature_row.get("calorie_abs_gap_kcal") or 0.0) / 320.0)
                - (float(feature_row.get("macro_gap_ratio_sum") or 0.0) * 1.4),
            ),
            6,
        ),
        "cost": round(-float(feature_row.get("estimated_basket_cost") or 0.0), 6),
        "practicality": round(
            structured_term_totals["practicality"]
            + float(feature_row.get("preference_match_score") or 0.0) * 0.08
            - float(feature_row.get("unrealistic_basket_penalty") or 0.0) * 0.9,
            6,
        ),
        "repetition_penalty": round(-float(feature_row.get("repetition_penalty") or 0.0), 6),
    }
    ranked_terms = sorted(term_scores.items(), key=lambda item: abs(float(item[1])), reverse=True)
    drift_score = float(materialization_debug.get("drift_score") or 0.0)
    if not materialization_debug:
        winner_mode = "direct_candidate_quality"
        drift_summary = "no meaningful seed drift"
    elif drift_score < 0.35:
        winner_mode = "direct_candidate_quality"
        drift_summary = str(materialization_debug.get("summary") or "model seed preserved")
    elif drift_score < 0.7:
        winner_mode = "light_materialization_adjustment"
        drift_summary = str(materialization_debug.get("summary") or "minor quantity drift")
    else:
        winner_mode = "heavy_materialization_adjustment"
        drift_summary = str(materialization_debug.get("summary") or "major quantity drift")
    return {
        "winner_mode": winner_mode,
        "seed_to_final_drift_score": round(drift_score, 6),
        "seed_to_final_drift_summary": drift_summary,
        "top_terms": [label for label, _value in ranked_terms[:4]],
        "term_scores": term_scores,
    }


def _diagnosis_text(
    *,
    model_candidate_count: int,
    model_candidates_merged_count: int,
    model_candidates_mostly_near_duplicates: bool,
    selected_candidate_source: str,
    selected_vs_best_heuristic: dict[str, object] | None,
    best_model_vs_best_heuristic_gap: float | None,
    best_model_loss_reason_summary: str | None = None,
) -> str:
    if model_candidate_count <= 0:
        return "No model candidates were generated for this request."
    if model_candidates_merged_count >= model_candidate_count:
        return "Model candidates were generated, but all of them merged into similar heuristic baskets before final ranking."
    if selected_candidate_source in {"model", "repaired_model", "hybrid"} and bool(selected_vs_best_heuristic and selected_vs_best_heuristic.get("materially_different")):
        selected_label = selected_candidate_source.replace("_", " ")
        return f"Model candidates changed the pool and a {selected_label} candidate won."
    if model_candidates_mostly_near_duplicates:
        if selected_candidate_source == "heuristic" and best_model_vs_best_heuristic_gap is not None:
            return (
                "Model candidates were mostly near-duplicates of heuristic candidates, "
                f"and heuristic still won by {abs(best_model_vs_best_heuristic_gap):.3f} scorer points."
            )
        return "Model candidates were mostly near-duplicates of heuristic candidates."
    if selected_candidate_source == "heuristic" and best_model_vs_best_heuristic_gap is not None:
        if best_model_loss_reason_summary:
            return (
                "Model candidates were generated but heuristic still won by "
                f"{abs(best_model_vs_best_heuristic_gap):.3f} scorer points. {best_model_loss_reason_summary}"
            )
        return f"Model candidates were generated but heuristic still won by {abs(best_model_vs_best_heuristic_gap):.3f} scorer points."
    if selected_vs_best_heuristic and not bool(selected_vs_best_heuristic.get("materially_different")):
        return "Model candidates were generated, but materialized baskets remained very similar."
    return "Model candidates changed the scored pool, but the final basket stayed close to the heuristic baseline."


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
    candidate_generation_config: dict[str, object] | None = None,
) -> list[dict[str, object]]:
    _raw_candidates, candidates, _debug_payload = _build_candidate_pool(
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
    return candidates


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
    candidate_generation_config: dict[str, object] | None = None,
) -> dict[str, object]:
    normalized_config = normalize_scorer_config(scorer_config)
    normalized_candidate_generation_config = normalize_candidate_generation_config(candidate_generation_config)
    raw_candidates, candidates, pool_debug = _build_candidate_pool(
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
        candidate_generation_config=normalized_candidate_generation_config,
    )

    model_path = Path(str(normalized_config["scorer_model_path"]))
    scorer_bundle = plan_scorer.load_bundle(model_path)
    ranked = _score_and_rank_candidates(candidates, scorer_bundle=scorer_bundle)
    raw_ranked = _score_and_rank_candidates(raw_candidates, scorer_bundle=scorer_bundle)

    selected_row = ranked[0]
    selected_candidate = selected_row["candidate"]
    response = dict(selected_candidate["recommendation"])
    response["scorer_used"] = True
    response["scorer_backend"] = str(scorer_bundle.get("backend") or "unknown")
    response["candidate_count_considered"] = len(candidates)
    response["selected_candidate_id"] = str(selected_candidate["candidate_id"])
    response["selected_candidate_source"] = str(selected_candidate["candidate_metadata"].get("source") or "heuristic")
    response["selected_candidate_sources"] = list(selected_candidate["candidate_metadata"].get("source_labels") or [response["selected_candidate_source"]])
    response["hybrid_planner_algorithm_version"] = str(normalized_candidate_generation_config["algorithm_version"])
    response["hybrid_planner_algorithm"] = {
        "version": str(normalized_candidate_generation_config["algorithm_version"]),
        "structured_complementarity_enabled": bool(normalized_candidate_generation_config["structured_complementarity_enabled"]),
        "structured_materialization_enabled": bool(normalized_candidate_generation_config["structured_materialization_enabled"]),
        "candidate_generator_backend": pool_debug.get("candidate_generator_backend"),
        "candidate_generator_model_path": pool_debug.get("candidate_generator_model_path"),
    }
    response["hybrid_planner_execution"] = {
        "pipeline_mode": (
            "full_hybrid"
            if bool(normalized_candidate_generation_config["enable_model_candidates"])
            else "heuristic_only"
        ),
        "algorithm_version": str(normalized_candidate_generation_config["algorithm_version"]),
        "structured_complementarity_enabled": bool(normalized_candidate_generation_config["structured_complementarity_enabled"]),
        "structured_materialization_enabled": bool(normalized_candidate_generation_config["structured_materialization_enabled"]),
        "heuristic_candidate_generation_ran": True,
        "learned_candidate_generation_ran": bool(normalized_candidate_generation_config["enable_model_candidates"]),
        "candidate_fusion_ran": True,
        "scorer_reranking_used": True,
        "heuristic_candidate_count": int(pool_debug.get("heuristic_candidate_count") or 0),
        "learned_candidate_count": int(pool_debug.get("model_candidate_count") or 0),
        "raw_candidate_count": int(pool_debug.get("raw_candidate_count") or 0),
        "fused_candidate_count": int(pool_debug.get("fused_candidate_count") or len(candidates)),
        "candidates_ranked_count": len(candidates),
        "candidate_generator_backend": pool_debug.get("candidate_generator_backend"),
        "candidate_generator_model_path": pool_debug.get("candidate_generator_model_path"),
        "scorer_backend": response["scorer_backend"],
        "scorer_model_path": str(model_path),
        "selected_candidate_id": response["selected_candidate_id"],
        "selected_candidate_source": response["selected_candidate_source"],
    }

    best_heuristic_row = _best_ranked_entry(raw_ranked, origin="heuristic")
    best_model_row = _best_ranked_entry(raw_ranked, origin="model")
    heuristic_ranked_rows = [row for row in raw_ranked if "heuristic" in _candidate_origin_labels(row["candidate"])]
    model_ranked_rows = [row for row in raw_ranked if "model" in _candidate_origin_labels(row["candidate"])]
    raw_candidate_resolution = pool_debug.get("raw_candidate_resolution", {})
    distinctness_summary = _model_distinctness_summary(heuristic_ranked_rows, model_ranked_rows)
    selected_vs_best_heuristic = _candidate_similarity(selected_candidate, best_heuristic_row["candidate"] if best_heuristic_row else None)
    selected_vs_best_model = _candidate_similarity(selected_candidate, best_model_row["candidate"] if best_model_row else None)
    best_model_vs_best_heuristic = (
        _candidate_similarity(best_model_row["candidate"], best_heuristic_row["candidate"])
        if best_model_row and best_heuristic_row
        else None
    )
    best_model_vs_best_heuristic_gap = None
    model_candidate_beat_best_heuristic = False
    if best_model_row and best_heuristic_row:
        best_model_vs_best_heuristic_gap = round(float(best_model_row["model_score"]) - float(best_heuristic_row["model_score"]), 6)
        model_candidate_beat_best_heuristic = bool(best_model_vs_best_heuristic_gap > 0)
    model_candidates_merged_count = sum(
        1
        for row in model_ranked_rows
        if str((raw_candidate_resolution.get(str(row["candidate"]["candidate_id"])) or {}).get("merge_outcome") or "survived_as_is")
        != "survived_as_is"
    )
    model_candidates_survived_count = max(len(model_ranked_rows) - model_candidates_merged_count, 0)
    materially_different_model_candidates_surviving_count = sum(
        1
        for ranked_row in ranked
        if "model" in _candidate_origin_labels(ranked_row["candidate"])
        and bool(
            _candidate_similarity(
                ranked_row["candidate"],
                best_heuristic_row["candidate"] if best_heuristic_row else None,
            )
            and _candidate_similarity(
                ranked_row["candidate"],
                best_heuristic_row["candidate"] if best_heuristic_row else None,
            )["materially_different"]
        )
    )
    best_materially_different_model_row = next(
        (
            row
            for row in model_ranked_rows
            if bool(
                _candidate_similarity(
                    row["candidate"],
                    best_heuristic_row["candidate"] if best_heuristic_row else None,
                )
                and _candidate_similarity(
                    row["candidate"],
                    best_heuristic_row["candidate"] if best_heuristic_row else None,
                )["materially_different"]
            )
        ),
        None,
    )
    selected_vs_best_materially_different_model = (
        _candidate_similarity(selected_candidate, best_materially_different_model_row["candidate"])
        if best_materially_different_model_row
        else None
    )
    best_materially_different_model_score_gap = (
        round(float(selected_row["model_score"]) - float(best_materially_different_model_row["model_score"]), 6)
        if best_materially_different_model_row
        else None
    )
    best_materially_different_model_feature_deltas = _feature_delta_snapshot(
        selected_row,
        best_materially_different_model_row,
    )
    best_materially_different_model_loss_reason = _loss_reason_from_feature_deltas(
        best_materially_different_model_feature_deltas,
    )
    best_materially_different_model_role_substitutions = _candidate_role_substitutions(
        best_heuristic_row["candidate"] if best_heuristic_row else None,
        best_materially_different_model_row["candidate"] if best_materially_different_model_row else None,
    )
    best_materially_different_model_loss_dimensions = _feature_loss_dimensions(
        best_materially_different_model_feature_deltas,
    )
    best_materially_different_model_failure_mode = _likely_failure_mode(
        feature_deltas=best_materially_different_model_feature_deltas,
        role_substitutions=best_materially_different_model_role_substitutions,
        best_heuristic_candidate=best_heuristic_row["candidate"] if best_heuristic_row else None,
        best_model_candidate=best_materially_different_model_row["candidate"] if best_materially_different_model_row else None,
    )
    best_materially_different_model_produce_difference_summary = _produce_difference_summary(
        reference_candidate=best_heuristic_row["candidate"] if best_heuristic_row else None,
        comparison_candidate=best_materially_different_model_row["candidate"] if best_materially_different_model_row else None,
    )
    best_materially_different_model_materialization_debug = (
        dict(best_materially_different_model_row["candidate"]["candidate_metadata"].get("materialization_debug") or {})
        if best_materially_different_model_row
        else {}
    )
    best_model_reason_tags: list[str] = []
    best_model_reason_summary: str | None = None
    if best_model_row is not None:
        best_model_reason_tags, best_model_reason_summary = _candidate_reason_details(
            best_model_row,
            selected_row=selected_row,
            raw_resolution=raw_candidate_resolution.get(str(best_model_row["candidate"]["candidate_id"])),
        )
    algorithmic_faithfulness = _algorithmic_faithfulness_summary(selected_row)
    comparison_debug = {
        "best_overall_candidate_id": str(selected_candidate["candidate_id"]),
        "best_overall_candidate_source": str(response["selected_candidate_source"]),
        "best_overall_candidate_score": round(float(selected_row["model_score"]), 6),
        "best_heuristic_candidate_id": str(best_heuristic_row["candidate"]["candidate_id"]) if best_heuristic_row else None,
        "best_heuristic_candidate_source": (
            str(best_heuristic_row["candidate"]["candidate_metadata"].get("source") or "heuristic")
            if best_heuristic_row
            else None
        ),
        "best_heuristic_candidate_score": round(float(best_heuristic_row["model_score"]), 6) if best_heuristic_row else None,
        "best_heuristic_candidate_shopping_food_ids": (
            list(best_heuristic_row["candidate"]["candidate_metadata"].get("shopping_food_ids") or [])
            if best_heuristic_row
            else []
        ),
        "best_model_candidate_id": str(best_model_row["candidate"]["candidate_id"]) if best_model_row else None,
        "best_model_candidate_source": (
            str(best_model_row["candidate"]["candidate_metadata"].get("source") or "model")
            if best_model_row
            else None
        ),
        "best_model_candidate_score": round(float(best_model_row["model_score"]), 6) if best_model_row else None,
        "best_model_candidate_shopping_food_ids": (
            list(best_model_row["candidate"]["candidate_metadata"].get("shopping_food_ids") or [])
            if best_model_row
            else []
        ),
        "best_model_candidate_reason_tags": best_model_reason_tags,
        "best_model_candidate_reason_summary": best_model_reason_summary,
        "model_candidate_beat_best_heuristic_candidate": model_candidate_beat_best_heuristic,
        "best_model_vs_best_heuristic_score_gap": best_model_vs_best_heuristic_gap,
        "model_candidates_generated": len(model_ranked_rows),
        "model_candidates_survived_after_fusion": model_candidates_survived_count,
        "model_candidates_merged_count": model_candidates_merged_count,
        "materially_different_model_candidates_surviving_after_fusion": materially_different_model_candidates_surviving_count,
        "average_heuristic_model_overlap_jaccard": distinctness_summary["average_heuristic_model_overlap_jaccard"],
        "average_model_to_best_heuristic_overlap_jaccard": distinctness_summary["average_model_to_best_heuristic_overlap_jaccard"],
        "model_candidates_materially_different_count": distinctness_summary["model_candidates_materially_different_count"],
        "model_candidates_mostly_near_duplicates": distinctness_summary["model_candidates_mostly_near_duplicates"],
        "best_materially_different_model_candidate_id": (
            str(best_materially_different_model_row["candidate"]["candidate_id"])
            if best_materially_different_model_row
            else None
        ),
        "best_materially_different_model_candidate_source": (
            str(best_materially_different_model_row["candidate"]["candidate_metadata"].get("source") or "model")
            if best_materially_different_model_row
            else None
        ),
        "best_materially_different_model_candidate_score": (
            round(float(best_materially_different_model_row["model_score"]), 6)
            if best_materially_different_model_row
            else None
        ),
        "best_materially_different_model_candidate_shopping_food_ids": (
            list(best_materially_different_model_row["candidate"]["candidate_metadata"].get("shopping_food_ids") or [])
            if best_materially_different_model_row
            else []
        ),
        "best_materially_different_model_candidate_score_gap_to_selected": best_materially_different_model_score_gap,
        "best_materially_different_model_candidate_feature_deltas_vs_selected": best_materially_different_model_feature_deltas,
        "best_materially_different_model_candidate_loss_reason": best_materially_different_model_loss_reason,
        "best_materially_different_model_candidate_loss_dimensions": best_materially_different_model_loss_dimensions,
        "best_materially_different_model_candidate_role_substitutions": best_materially_different_model_role_substitutions,
        "best_materially_different_model_candidate_role_substitution_summaries": [
            str(entry.get("summary") or "")
            for entry in best_materially_different_model_role_substitutions
        ],
        "best_materially_different_model_candidate_produce_difference_summary": best_materially_different_model_produce_difference_summary,
        "best_materially_different_model_candidate_failure_mode": best_materially_different_model_failure_mode,
        "best_materially_different_model_candidate_materialization_debug": best_materially_different_model_materialization_debug,
        "best_materially_different_model_candidate_seed_to_final_drift_summary": str(
            best_materially_different_model_materialization_debug.get("summary") or ""
        ),
        "best_materially_different_model_candidate_seed_to_final_drift_score": (
            round(float(best_materially_different_model_materialization_debug.get("drift_score") or 0.0), 6)
            if best_materially_different_model_materialization_debug
            else None
        ),
        "best_materially_different_model_candidate_remaining_primary_reason": (
            best_materially_different_model_loss_reason
            or str(best_materially_different_model_failure_mode or "").replace("_", " ")
        ),
        "selected_candidate_shopping_food_ids": list(selected_candidate["candidate_metadata"].get("shopping_food_ids") or []),
        "selected_vs_best_heuristic": selected_vs_best_heuristic,
        "selected_vs_best_model": selected_vs_best_model,
        "selected_vs_best_materially_different_model": selected_vs_best_materially_different_model,
        "best_model_vs_best_heuristic": best_model_vs_best_heuristic,
        "selected_candidate_materially_differs_from_best_heuristic": bool(
            selected_vs_best_heuristic and selected_vs_best_heuristic.get("materially_different")
        ),
        "selected_candidate_difference_summary": (
            str(selected_vs_best_heuristic.get("difference_summary") or "")
            if selected_vs_best_heuristic
            else ""
        ),
        "algorithmic_faithfulness": algorithmic_faithfulness,
        "material_difference_rule": candidate_debug.MATERIAL_DIFFERENCE_RULE_TEXT,
    }
    comparison_debug["diagnosis_text"] = _diagnosis_text(
        model_candidate_count=len(model_ranked_rows),
        model_candidates_merged_count=model_candidates_merged_count,
        model_candidates_mostly_near_duplicates=bool(distinctness_summary["model_candidates_mostly_near_duplicates"]),
        selected_candidate_source=str(response["selected_candidate_source"]),
        selected_vs_best_heuristic=selected_vs_best_heuristic,
        best_model_vs_best_heuristic_gap=best_model_vs_best_heuristic_gap,
        best_model_loss_reason_summary=best_model_reason_summary,
    )
    comparison_debug["why_no_model_win_yet"] = _why_no_model_win_yet(
        selected_candidate_source=str(response["selected_candidate_source"]),
        best_materially_different_model_row=best_materially_different_model_row,
        materially_different_model_candidates_surviving_count=materially_different_model_candidates_surviving_count,
        failure_mode=best_materially_different_model_failure_mode,
        loss_reason=best_materially_different_model_loss_reason,
    )
    comparison_debug["selected_candidate_contrast"] = {
        "selected_candidate_source": str(response["selected_candidate_source"]),
        "selected_candidate_shopping_food_ids": list(selected_candidate["candidate_metadata"].get("shopping_food_ids") or []),
        "best_heuristic_candidate_shopping_food_ids": comparison_debug["best_heuristic_candidate_shopping_food_ids"],
        "best_model_candidate_shopping_food_ids": comparison_debug["best_model_candidate_shopping_food_ids"],
        "difference_summary_vs_best_heuristic": comparison_debug["selected_candidate_difference_summary"],
    }
    if normalized_config["debug"]:
        response["algorithmic_faithfulness_debug"] = algorithmic_faithfulness
        response["scoring_debug"] = {
            "candidate_count": len(candidates),
            "selected_candidate_id": selected_candidate["candidate_id"],
            "model_path": str(model_path),
            "backend": str(scorer_bundle.get("backend") or "unknown"),
            "best_heuristic_candidate_id": comparison_debug["best_heuristic_candidate_id"],
            "best_model_candidate_id": comparison_debug["best_model_candidate_id"],
            "candidates": [
                _candidate_debug_row(
                    ranked_row,
                    selected_row=selected_row,
                    selected_candidate=selected_candidate,
                    best_heuristic_candidate=best_heuristic_row["candidate"] if best_heuristic_row else None,
                    best_model_candidate=best_model_row["candidate"] if best_model_row else None,
                    include_features=True,
                )
                for ranked_row in ranked
            ],
        }

    if normalized_candidate_generation_config["debug"]:
        response["algorithmic_faithfulness_debug"] = algorithmic_faithfulness
        response["candidate_generation_debug"] = {
            **pool_debug,
            "material_difference_rule": candidate_debug.MATERIAL_DIFFERENCE_RULE_TEXT,
            "model_candidates_survived_after_fusion": model_candidates_survived_count,
            "model_candidates_merged_count": model_candidates_merged_count,
            "average_heuristic_model_overlap_jaccard": distinctness_summary["average_heuristic_model_overlap_jaccard"],
            "average_model_to_best_heuristic_overlap_jaccard": distinctness_summary["average_model_to_best_heuristic_overlap_jaccard"],
            "model_candidates_materially_different_count": distinctness_summary["model_candidates_materially_different_count"],
            "model_candidates_mostly_near_duplicates": distinctness_summary["model_candidates_mostly_near_duplicates"],
            "candidates": [
                _candidate_debug_row(
                    ranked_row,
                    selected_row=selected_row,
                    selected_candidate=selected_candidate,
                    best_heuristic_candidate=best_heuristic_row["candidate"] if best_heuristic_row else None,
                    best_model_candidate=best_model_row["candidate"] if best_model_row else None,
                )
                for ranked_row in ranked
            ],
            "raw_candidates": [
                _candidate_debug_row(
                    ranked_row,
                    selected_row=selected_row,
                    selected_candidate=selected_candidate,
                    best_heuristic_candidate=best_heuristic_row["candidate"] if best_heuristic_row else None,
                    best_model_candidate=best_model_row["candidate"] if best_model_row else None,
                    raw_resolution=raw_candidate_resolution.get(str(ranked_row["candidate"]["candidate_id"])),
                )
                for ranked_row in raw_ranked
            ],
            "selected_candidate_id": selected_candidate["candidate_id"],
            "selected_candidate_source": response["selected_candidate_source"],
        }
    if normalized_config["debug"] or normalized_candidate_generation_config["debug"]:
        response["candidate_comparison_debug"] = comparison_debug
    return response
