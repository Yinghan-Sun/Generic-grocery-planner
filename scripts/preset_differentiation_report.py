#!/usr/bin/env -S uv run --extra ml python
"""Generate a reusable preset-differentiation summary for the hybrid grocery planner."""

from __future__ import annotations

import argparse
import itertools
import json
from pathlib import Path

import duckdb

from dietdashboard import candidate_debug
from dietdashboard import hybrid_pipeline_evaluation
from dietdashboard import hybrid_pipeline_final
from dietdashboard.store_discovery import DEFAULT_LIMIT as DEFAULT_STORE_LIMIT
from dietdashboard.store_discovery import DEFAULT_RADIUS_M


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db-path", type=Path, default=hybrid_pipeline_evaluation.default_db_path(), help="Path to the local DuckDB database.")
    parser.add_argument("--lat", type=float, default=hybrid_pipeline_final.DEFAULT_LOCATION["lat"], help="Latitude for the preset comparison location.")
    parser.add_argument("--lon", type=float, default=hybrid_pipeline_final.DEFAULT_LOCATION["lon"], help="Longitude for the preset comparison location.")
    parser.add_argument("--radius-m", type=float, default=DEFAULT_RADIUS_M, help="Nearby-store search radius in meters.")
    parser.add_argument("--store-limit", type=int, default=DEFAULT_STORE_LIMIT, help="Nearby-store limit.")
    parser.add_argument(
        "--output-path",
        type=Path,
        default=hybrid_pipeline_final.FINAL_OUTPUT_DIR / "preset_differentiation_summary.json",
        help="Path for the generated JSON summary.",
    )
    parser.add_argument(
        "--before-path",
        type=Path,
        default=Path("tmp/preset_differentiation_before.json"),
        help="Optional before-change baseline JSON created during local diagnosis.",
    )
    return parser.parse_args()


def _role_food_ids(response: dict[str, object]) -> dict[str, list[str]]:
    role_food_ids = {
        "protein_anchor": [],
        "carb_base": [],
        "produce": [],
        "calorie_booster": [],
    }
    for item in response.get("shopping_list") or []:
        role = str(item.get("role") or "")
        food_id = str(item.get("generic_food_id") or "")
        if role in role_food_ids and food_id:
            role_food_ids[role].append(food_id)
    return role_food_ids


def _selected_feature_row(response: dict[str, object]) -> dict[str, object]:
    scoring_debug = response.get("scoring_debug")
    if not isinstance(scoring_debug, dict):
        return {}
    selected_candidate_id = str(response.get("selected_candidate_id") or "")
    for row in scoring_debug.get("candidates") or []:
        if not isinstance(row, dict):
            continue
        if str(row.get("candidate_id") or "") == selected_candidate_id or bool(row.get("selected")):
            return dict(row.get("features") or {})
    return {}


def _pairwise_role_overlaps(left_roles: dict[str, list[str]], right_roles: dict[str, list[str]]) -> dict[str, float]:
    overlaps: dict[str, float] = {}
    for role in ("protein_anchor", "carb_base", "produce", "calorie_booster"):
        left_ids = set(left_roles.get(role) or [])
        right_ids = set(right_roles.get(role) or [])
        denominator = len(left_ids | right_ids)
        overlaps[role] = round((len(left_ids & right_ids) / denominator) if denominator else 1.0, 6)
    return overlaps


def _visible_structure_judgment(preset_id: str, response: dict[str, object], features: dict[str, object]) -> dict[str, object]:
    role_food_ids = _role_food_ids(response)
    notes: list[str] = []
    passed = False

    if preset_id == "muscle_gain":
        passed = (
            bool(role_food_ids["calorie_booster"])
            and bool(role_food_ids["carb_base"])
            and len(role_food_ids["protein_anchor"]) == 2
            and float(features.get("fruit_produce_count") or 0.0) >= 1.0
        )
        if role_food_ids["calorie_booster"]:
            notes.append("includes explicit calorie support")
        if float(features.get("fruit_produce_count") or 0.0) >= 1.0:
            notes.append("keeps quick-carb fruit")
    elif preset_id == "fat_loss":
        passed = (
            not role_food_ids["calorie_booster"]
            and len(role_food_ids["produce"]) >= 3
            and float(features.get("high_volume_produce_count") or 0.0) >= 2.0
        )
        if not role_food_ids["calorie_booster"]:
            notes.append("no calorie booster")
        if len(role_food_ids["produce"]) >= 3:
            notes.append("three-produce volume structure")
    elif preset_id == "maintenance":
        passed = len(role_food_ids["protein_anchor"]) == 2 and len(role_food_ids["produce"]) == 2
        if role_food_ids["calorie_booster"]:
            notes.append("keeps a moderate booster")
        notes.append("middle-ground mixed basket")
    elif preset_id == "high_protein_vegetarian":
        passed = float(features.get("animal_protein_anchor_count") or 0.0) == 0.0 and len(role_food_ids["protein_anchor"]) == 2
        if float(features.get("animal_protein_anchor_count") or 0.0) == 0.0:
            notes.append("protein anchors are fully vegetarian")
        if float(features.get("soy_protein_anchor_count") or 0.0) >= 1.0 and float(features.get("dairy_or_egg_anchor_count") or 0.0) >= 1.0:
            notes.append("combines soy with egg/dairy protein")
    elif preset_id == "budget_friendly_healthy":
        passed = (
            float(features.get("legume_protein_anchor_count") or 0.0) >= 1.0
            and float(features.get("budget_support_anchor_count") or 0.0) >= 1.0
            and bool(role_food_ids["calorie_booster"])
        )
        if float(features.get("legume_protein_anchor_count") or 0.0) >= 1.0:
            notes.append("uses a low-cost legume anchor")
        if float(features.get("budget_support_anchor_count") or 0.0) >= 1.0:
            notes.append("pairs it with eggs or tofu for support")
        if role_food_ids["calorie_booster"]:
            notes.append("adds inexpensive fat support")

    return {
        "passed": bool(passed),
        "notes": notes,
    }


def _preset_summary(preset: dict[str, object], response: dict[str, object]) -> dict[str, object]:
    role_food_ids = _role_food_ids(response)
    features = _selected_feature_row(response)
    return {
        "label": str(preset["label"]),
        "goal_profile": str(response.get("goal_profile") or ""),
        "selected_candidate_source": str(response.get("selected_candidate_source") or ""),
        "shopping_food_ids": [str(item.get("generic_food_id") or "") for item in response.get("shopping_list") or []],
        "role_counts": {role: len(food_ids) for role, food_ids in role_food_ids.items()},
        "role_food_ids": role_food_ids,
        "nutrition_summary": dict(response.get("nutrition_summary") or {}),
        "estimated_basket_cost": round(float(response.get("estimated_basket_cost") or 0.0), 6),
        "goal_structure_alignment_score": round(float(features.get("goal_structure_alignment_score") or 0.0), 6),
        "role_share_gap_total": round(float(features.get("role_share_gap_total") or 0.0), 6),
        "selected_features": {
            key: features.get(key)
            for key in (
                "protein_abs_gap_g",
                "calorie_abs_gap_kcal",
                "carbohydrate_abs_gap_g",
                "fat_abs_gap_g",
                "goal_structure_alignment_score",
                "role_share_gap_total",
                "budget_support_anchor_count",
                "legume_protein_anchor_count",
                "animal_protein_anchor_count",
                "soy_protein_anchor_count",
                "dairy_or_egg_anchor_count",
                "fruit_produce_count",
                "high_volume_produce_count",
                "low_cost_produce_count",
                "calorie_booster_share",
            )
        },
        "hybrid_planner_execution": dict(response.get("hybrid_planner_execution") or {}),
        "visible_structure_judgment": _visible_structure_judgment(str(preset["preset_id"]), response, features),
    }


def _pairwise_summary(preset_id_to_response: dict[str, dict[str, object]]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for left_id, right_id in itertools.combinations(preset_id_to_response, 2):
        left_response = preset_id_to_response[left_id]
        right_response = preset_id_to_response[right_id]
        comparison = candidate_debug.compare_candidates(left_response, right_response)
        rows.append(
            {
                "left": left_id,
                "right": right_id,
                "shopping_list_jaccard": round(float(comparison.get("jaccard_overlap") or 0.0), 6),
                "shared_food_count": int(comparison.get("shared_food_count") or 0),
                "changed_food_count": int(comparison.get("changed_food_count") or 0),
                "difference_summary": str(comparison.get("difference_summary") or ""),
                "role_overlaps": _pairwise_role_overlaps(_role_food_ids(left_response), _role_food_ids(right_response)),
            }
        )
    return rows


def _pairwise_aggregate(rows: list[dict[str, object]]) -> dict[str, float]:
    if not rows:
        return {"average_shopping_list_jaccard": 0.0, "max_shopping_list_jaccard": 0.0}
    jaccards = [float(row["shopping_list_jaccard"]) for row in rows]
    return {
        "average_shopping_list_jaccard": round(sum(jaccards) / len(jaccards), 6),
        "max_shopping_list_jaccard": round(max(jaccards), 6),
        "min_shopping_list_jaccard": round(min(jaccards), 6),
    }


def _before_after_summary(before_payload: dict[str, object] | None, after_payload: dict[str, object]) -> dict[str, object] | None:
    if not before_payload:
        return None

    before_pairwise = {
        tuple(sorted((str(row["left"]), str(row["right"])))): float(row["shopping_list_jaccard"])
        for row in before_payload.get("pairwise") or []
    }
    after_pairwise = {
        tuple(sorted((str(row["left"]), str(row["right"])))): float(row["shopping_list_jaccard"])
        for row in after_payload.get("pairwise") or []
    }
    pair_deltas = []
    for pair_key, before_value in before_pairwise.items():
        after_value = after_pairwise.get(pair_key)
        if after_value is None:
            continue
        pair_deltas.append(
            {
                "left": pair_key[0],
                "right": pair_key[1],
                "before_shopping_list_jaccard": round(before_value, 6),
                "after_shopping_list_jaccard": round(after_value, 6),
                "delta_shopping_list_jaccard": round(after_value - before_value, 6),
            }
        )

    before_aggregate = _pairwise_aggregate(list(before_payload.get("pairwise") or []))
    after_aggregate = _pairwise_aggregate(list(after_payload.get("pairwise") or []))
    preset_changes = {}
    for preset_id, before_summary in dict(before_payload.get("presets") or {}).items():
        after_summary = dict(after_payload.get("presets") or {}).get(preset_id)
        if not isinstance(after_summary, dict):
            continue
        preset_changes[preset_id] = {
            "before_shopping_food_ids": list(before_summary.get("shopping_food_ids") or []),
            "after_shopping_food_ids": list(after_summary.get("shopping_food_ids") or []),
            "basket_changed": list(before_summary.get("shopping_food_ids") or []) != list(after_summary.get("shopping_food_ids") or []),
        }
    return {
        "before_path_version": str(before_payload.get("version") or "unknown"),
        "before_aggregate": before_aggregate,
        "after_aggregate": after_aggregate,
        "average_shopping_list_jaccard_delta": round(
            after_aggregate["average_shopping_list_jaccard"] - before_aggregate["average_shopping_list_jaccard"],
            6,
        ),
        "max_shopping_list_jaccard_delta": round(
            after_aggregate["max_shopping_list_jaccard"] - before_aggregate["max_shopping_list_jaccard"],
            6,
        ),
        "pairwise_deltas": pair_deltas,
        "preset_changes": preset_changes,
    }


def _assessment(
    preset_summaries: dict[str, dict[str, object]],
    pairwise_rows: list[dict[str, object]],
    before_after_summary: dict[str, object] | None,
) -> dict[str, object]:
    pairwise_map = {
        tuple(sorted((str(row["left"]), str(row["right"])))): row
        for row in pairwise_rows
    }
    visible_structure_pass_count = sum(
        1
        for summary in preset_summaries.values()
        if bool(dict(summary.get("visible_structure_judgment") or {}).get("passed"))
    )

    def pair_row(left: str, right: str) -> dict[str, object]:
        return dict(pairwise_map.get(tuple(sorted((left, right)))) or {})

    critical_pairwise_checks = {
        "muscle_gain_vs_fat_loss": {
            "passed": (
                float(pair_row("muscle_gain", "fat_loss").get("shopping_list_jaccard") or 1.0) <= 0.12
                and not preset_summaries["fat_loss"]["role_food_ids"]["calorie_booster"]
                and bool(preset_summaries["muscle_gain"]["role_food_ids"]["calorie_booster"])
            ),
            "notes": [
                "muscle gain keeps a calorie booster while fat loss avoids one",
                f"shopping-list overlap={pair_row('muscle_gain', 'fat_loss').get('shopping_list_jaccard')}",
            ],
        },
        "muscle_gain_vs_maintenance": {
            "passed": (
                preset_summaries["muscle_gain"]["role_food_ids"]["carb_base"]
                != preset_summaries["maintenance"]["role_food_ids"]["carb_base"]
                and "bananas" in preset_summaries["muscle_gain"]["shopping_food_ids"]
                and "wholemeal_bread" in preset_summaries["maintenance"]["shopping_food_ids"]
            ),
            "notes": [
                "muscle gain now uses a performance-style carb and quick-carb fruit",
                "maintenance keeps a more moderate bread-based basket",
            ],
        },
        "budget_friendly_healthy_vs_maintenance": {
            "passed": (
                float(preset_summaries["budget_friendly_healthy"]["estimated_basket_cost"])
                < float(preset_summaries["maintenance"]["estimated_basket_cost"])
                and "lentils" in preset_summaries["budget_friendly_healthy"]["shopping_food_ids"]
                and "rotisserie_chicken" in preset_summaries["maintenance"]["shopping_food_ids"]
            ),
            "notes": [
                "budget preset keeps a low-cost staple structure",
                "maintenance stays more moderate and animal-protein-based",
            ],
        },
        "high_protein_vegetarian_vs_meat_presets": {
            "passed": (
                float(preset_summaries["high_protein_vegetarian"]["selected_features"]["animal_protein_anchor_count"] or 0.0) == 0.0
                and float(pair_row("high_protein_vegetarian", "muscle_gain").get("shopping_list_jaccard") or 1.0) <= 0.12
                and float(pair_row("high_protein_vegetarian", "maintenance").get("shopping_list_jaccard") or 1.0) <= 0.12
            ),
            "notes": [
                "vegetarian preset uses only vegetarian protein anchors",
                "it stays visually distinct from the meat-based baskets",
            ],
        },
    }

    basket_changed_count = 0
    if isinstance(before_after_summary, dict):
        basket_changed_count = sum(
            1
            for row in dict(before_after_summary.get("preset_changes") or {}).values()
            if bool(dict(row).get("basket_changed"))
        )

    all_critical_checks_pass = all(
        bool(dict(check).get("passed"))
        for check in critical_pairwise_checks.values()
    )
    overall_judgment = "improved" if visible_structure_pass_count == len(preset_summaries) and all_critical_checks_pass else "mixed"

    return {
        "visible_structure_pass_count": visible_structure_pass_count,
        "preset_count": len(preset_summaries),
        "all_presets_pass_visible_structure": visible_structure_pass_count == len(preset_summaries),
        "basket_changed_count_vs_before": basket_changed_count,
        "critical_pairwise_checks": critical_pairwise_checks,
        "overall_judgment": overall_judgment,
        "summary": (
            "Preset baskets now show clearer structural separation across the main user-facing goals."
            if overall_judgment == "improved"
            else "Preset differentiation improved in some areas, but at least one critical separation check still needs work."
        ),
    }


def main() -> int:
    args = parse_args()
    args.output_path.parent.mkdir(parents=True, exist_ok=True)

    with duckdb.connect(args.db_path, read_only=True) as con:
        stores, price_context = hybrid_pipeline_evaluation.load_store_context(
            con,
            lat=args.lat,
            lon=args.lon,
            radius_m=args.radius_m,
            store_limit=args.store_limit,
        )
        preset_id_to_response: dict[str, dict[str, object]] = {}
        preset_summaries: dict[str, dict[str, object]] = {}
        for preset in hybrid_pipeline_final.MAIN_PRESETS:
            response = hybrid_pipeline_evaluation.run_scored_system(
                con,
                preset=preset,
                stores=stores,
                price_context=price_context,
                scorer_model_path=hybrid_pipeline_final.FINAL_SCORER_MODEL_PATH,
                candidate_generation_config=hybrid_pipeline_final.final_candidate_generation_config(debug=True),
                candidate_count=int(hybrid_pipeline_final.final_runtime_metadata()["candidate_count"]),
            )
            preset_id = str(preset["preset_id"])
            preset_id_to_response[preset_id] = response
            preset_summaries[preset_id] = _preset_summary(preset, response)

    pairwise_rows = _pairwise_summary(preset_id_to_response)
    aggregate = _pairwise_aggregate(pairwise_rows)
    before_payload = json.loads(args.before_path.read_text()) if args.before_path.exists() else None
    before_after_summary = _before_after_summary(before_payload, {"presets": preset_summaries, "pairwise": pairwise_rows})
    payload = {
        "version": "after_changes",
        "algorithm": hybrid_pipeline_final.final_runtime_metadata(),
        "location": {
            "label": hybrid_pipeline_final.DEFAULT_LOCATION["label"],
            "lat": args.lat,
            "lon": args.lon,
            "radius_m": args.radius_m,
            "store_limit": args.store_limit,
        },
        "presets": preset_summaries,
        "pairwise": pairwise_rows,
        "aggregate": aggregate,
        "before_after_summary": before_after_summary,
        "assessment": _assessment(preset_summaries, pairwise_rows, before_after_summary),
    }
    args.output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"preset_differentiation_summary={args.output_path}")
    print(f"average_shopping_list_jaccard={aggregate['average_shopping_list_jaccard']}")
    print(f"max_shopping_list_jaccard={aggregate['max_shopping_list_jaccard']}")
    if payload["before_after_summary"] is not None:
        print(f"average_shopping_list_jaccard_delta={payload['before_after_summary']['average_shopping_list_jaccard_delta']}")
        print(f"max_shopping_list_jaccard_delta={payload['before_after_summary']['max_shopping_list_jaccard_delta']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
