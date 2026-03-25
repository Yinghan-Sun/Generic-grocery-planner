"""Reusable candidate-comparison helpers for local hybrid-planner diagnostics."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence

ROLE_SHORT_LABELS = {
    "protein_anchor": "protein",
    "carb_base": "carb",
    "produce": "produce",
    "calorie_booster": "booster",
}

MATERIAL_DIFFERENCE_RULE_TEXT = (
    "Two baskets are materially different when any of these triggers fire: shopping-food Jaccard overlap < 0.67, "
    "at least 2 changed foods, at least 2 role-assignment changes, cost delta >= $3, protein-gap delta >= 15 g, "
    "or calorie-gap delta >= 150 kcal."
)


def _ordered_unique(values: Sequence[object]) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = str(value or "").strip()
        if normalized and normalized not in seen:
            ordered.append(normalized)
            seen.add(normalized)
    return ordered


def _recommendation(payload: Mapping[str, object]) -> Mapping[str, object]:
    recommendation = payload.get("recommendation")
    if isinstance(recommendation, Mapping):
        return recommendation
    return payload


def shopping_food_ids(payload: Mapping[str, object]) -> list[str]:
    metadata = payload.get("candidate_metadata")
    if isinstance(metadata, Mapping) and isinstance(metadata.get("shopping_food_ids"), Sequence):
        return _ordered_unique(metadata["shopping_food_ids"])
    recommendation = _recommendation(payload)
    shopping_list = recommendation.get("shopping_list")
    if isinstance(shopping_list, Sequence):
        return _ordered_unique(
            [item.get("generic_food_id") for item in shopping_list if isinstance(item, Mapping)]
        )
    return []


def chosen_food_ids(payload: Mapping[str, object]) -> list[str]:
    metadata = payload.get("candidate_metadata")
    if isinstance(metadata, Mapping) and isinstance(metadata.get("chosen_food_ids"), Sequence):
        return _ordered_unique(metadata["chosen_food_ids"])
    return shopping_food_ids(payload)


def role_map(payload: Mapping[str, object]) -> dict[str, str]:
    recommendation = _recommendation(payload)
    shopping_list = recommendation.get("shopping_list")
    out: dict[str, str] = {}
    if not isinstance(shopping_list, Sequence):
        return out
    for item in shopping_list:
        if not isinstance(item, Mapping):
            continue
        food_id = str(item.get("generic_food_id") or "").strip()
        role = str(item.get("role") or "").strip()
        if food_id and role:
            out[food_id] = role
    return out


def role_counts(payload: Mapping[str, object]) -> dict[str, int]:
    metadata = payload.get("candidate_metadata")
    if isinstance(metadata, Mapping) and isinstance(metadata.get("role_counts"), Mapping):
        return {
            role: int(metadata["role_counts"].get(role, 0))
            for role in ("protein_anchor", "carb_base", "produce", "calorie_booster")
        }
    counts = Counter(role_map(payload).values())
    return {role: int(counts.get(role, 0)) for role in ("protein_anchor", "carb_base", "produce", "calorie_booster")}


def estimated_cost(payload: Mapping[str, object]) -> float:
    recommendation = _recommendation(payload)
    try:
        return float(recommendation.get("estimated_basket_cost") or 0.0)
    except (TypeError, ValueError):
        return 0.0


def nutrition_summary(payload: Mapping[str, object]) -> Mapping[str, object]:
    recommendation = _recommendation(payload)
    summary = recommendation.get("nutrition_summary")
    return summary if isinstance(summary, Mapping) else {}


def protein_gap_g(payload: Mapping[str, object]) -> float:
    summary = nutrition_summary(payload)
    try:
        target = float(summary.get("protein_target_g") or 0.0)
        estimated = float(summary.get("protein_estimated_g") or 0.0)
    except (TypeError, ValueError):
        return 0.0
    return abs(estimated - target)


def calorie_gap_kcal(payload: Mapping[str, object]) -> float:
    summary = nutrition_summary(payload)
    try:
        target = float(summary.get("calorie_target_kcal") or 0.0)
        estimated = float(summary.get("calorie_estimated_kcal") or 0.0)
    except (TypeError, ValueError):
        return 0.0
    return abs(estimated - target)


def jaccard_overlap(left_ids: Sequence[str], right_ids: Sequence[str]) -> float:
    left_set = set(_ordered_unique(left_ids))
    right_set = set(_ordered_unique(right_ids))
    union = left_set | right_set
    if not union:
        return 1.0
    return len(left_set & right_set) / len(union)


def _changed_role_labels(
    left_role_map: Mapping[str, str],
    right_role_map: Mapping[str, str],
    left_only: Sequence[str],
    right_only: Sequence[str],
    shared: Sequence[str],
) -> list[str]:
    changed_roles: set[str] = set()
    for food_id in left_only:
        changed_roles.add(str(left_role_map.get(food_id) or ""))
    for food_id in right_only:
        changed_roles.add(str(right_role_map.get(food_id) or ""))
    for food_id in shared:
        left_role = str(left_role_map.get(food_id) or "")
        right_role = str(right_role_map.get(food_id) or "")
        if left_role and right_role and left_role != right_role:
            changed_roles.update([left_role, right_role])
    labels = [ROLE_SHORT_LABELS.get(role, role) for role in sorted(changed_roles) if role]
    return [label for label in labels if label]


def difference_summary(metrics: Mapping[str, object]) -> str:
    changed_food_count = int(metrics.get("changed_food_count") or 0)
    role_assignment_changes = int(metrics.get("role_assignment_changes") or 0)
    changed_role_labels = list(metrics.get("changed_role_labels") or [])
    jaccard = float(metrics.get("jaccard_overlap") or 0.0)
    if changed_food_count == 0 and role_assignment_changes == 0:
        if bool(metrics.get("materially_different")):
            return "Same foods, meaningfully different quantities"
        return "Same basket"
    if changed_food_count == 1 and role_assignment_changes <= 1:
        return "Only 1 food changed"
    if changed_role_labels == ["produce"]:
        return "Same basket structure, different produce"
    if changed_food_count <= 4 and changed_role_labels and len(changed_role_labels) <= 2:
        return f"{changed_food_count} {'/'.join(changed_role_labels)} substitutions"
    if jaccard >= 0.67:
        return "Similar basket with a few substitutions"
    return "Large basket change"


def compare_candidates(left: Mapping[str, object], right: Mapping[str, object]) -> dict[str, object]:
    left_ids = shopping_food_ids(left)
    right_ids = shopping_food_ids(right)
    left_set = set(left_ids)
    right_set = set(right_ids)
    shared_food_ids = sorted(left_set & right_set)
    left_only_food_ids = sorted(left_set - right_set)
    right_only_food_ids = sorted(right_set - left_set)
    left_role_map = role_map(left)
    right_role_map = role_map(right)
    role_assignment_changes = sum(
        1
        for food_id in shared_food_ids
        if left_role_map.get(food_id) and right_role_map.get(food_id) and left_role_map[food_id] != right_role_map[food_id]
    )
    changed_food_count = len(left_only_food_ids) + len(right_only_food_ids)
    cost_delta = estimated_cost(right) - estimated_cost(left)
    protein_gap_delta = protein_gap_g(right) - protein_gap_g(left)
    calorie_gap_delta = calorie_gap_kcal(right) - calorie_gap_kcal(left)
    jaccard = jaccard_overlap(left_ids, right_ids)
    metrics: dict[str, object] = {
        "jaccard_overlap": round(jaccard, 6),
        "shared_food_count": len(shared_food_ids),
        "changed_food_count": changed_food_count,
        "role_assignment_changes": role_assignment_changes,
        "left_only_food_ids": left_only_food_ids,
        "right_only_food_ids": right_only_food_ids,
        "cost_delta": round(cost_delta, 6),
        "protein_gap_delta_g": round(protein_gap_delta, 6),
        "calorie_gap_delta_kcal": round(calorie_gap_delta, 6),
    }
    metrics["changed_role_labels"] = _changed_role_labels(
        left_role_map,
        right_role_map,
        left_only_food_ids,
        right_only_food_ids,
        shared_food_ids,
    )
    metrics["materially_different"] = bool(
        jaccard < 0.67
        or changed_food_count >= 2
        or role_assignment_changes >= 2
        or abs(cost_delta) >= 3.0
        or abs(protein_gap_delta) >= 15.0
        or abs(calorie_gap_delta) >= 150.0
    )
    metrics["difference_summary"] = difference_summary(metrics)
    return metrics
