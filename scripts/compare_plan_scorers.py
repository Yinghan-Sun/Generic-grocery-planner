#!/usr/bin/env -S uv run --extra ml python
"""Compare old and new scorer artifacts on the same heuristic and hybrid candidate pools."""

from __future__ import annotations

import argparse
import csv
import json
from collections.abc import Mapping
from pathlib import Path

import duckdb

from dietdashboard import candidate_debug
from dietdashboard import hybrid_planner
from dietdashboard import model_candidate_generator
from dietdashboard import model_candidate_training
from dietdashboard import plan_scorer
from dietdashboard.generic_recommender import resolve_price_context
from dietdashboard.store_discovery import DEFAULT_LIMIT as DEFAULT_STORE_LIMIT
from dietdashboard.store_discovery import DEFAULT_RADIUS_M, nearby_stores

DEFAULT_LOCATION = {"label": "Mountain View, CA", "lat": 37.401, "lon": -122.09}
MAIN_PRESETS = [
    {
        "preset_id": "muscle_gain",
        "label": "Muscle Gain",
        "targets": {"protein": 170.0, "energy_fibre_kcal": 2800.0, "carbohydrate": 330.0, "fat": 85.0, "fiber": 35.0},
        "preferences": {"vegetarian": False, "dairy_free": False, "vegan": False, "low_prep": False, "budget_friendly": False, "meal_style": "any"},
        "days": 1,
        "shopping_mode": "balanced",
    },
    {
        "preset_id": "fat_loss",
        "label": "Fat Loss",
        "targets": {"protein": 150.0, "energy_fibre_kcal": 1800.0, "carbohydrate": 160.0, "fat": 55.0, "fiber": 30.0},
        "preferences": {"vegetarian": False, "dairy_free": False, "vegan": False, "low_prep": False, "budget_friendly": False, "meal_style": "any"},
        "days": 1,
        "shopping_mode": "balanced",
    },
    {
        "preset_id": "maintenance",
        "label": "Maintenance",
        "targets": {"protein": 130.0, "energy_fibre_kcal": 2200.0, "carbohydrate": 240.0, "fat": 70.0, "fiber": 30.0},
        "preferences": {"vegetarian": False, "dairy_free": False, "vegan": False, "low_prep": False, "budget_friendly": False, "meal_style": "any"},
        "days": 1,
        "shopping_mode": "balanced",
    },
    {
        "preset_id": "high_protein_vegetarian",
        "label": "High-Protein Vegetarian",
        "targets": {
            "protein": 140.0,
            "energy_fibre_kcal": 2100.0,
            "carbohydrate": 220.0,
            "fat": 70.0,
            "fiber": 32.0,
            "iron": 18.0,
        },
        "preferences": {"vegetarian": True, "dairy_free": False, "vegan": False, "low_prep": False, "budget_friendly": False, "meal_style": "any"},
        "days": 1,
        "shopping_mode": "balanced",
    },
    {
        "preset_id": "budget_friendly_healthy",
        "label": "Budget-Friendly Healthy",
        "targets": {"protein": 120.0, "energy_fibre_kcal": 2100.0, "carbohydrate": 230.0, "fat": 65.0, "fiber": 35.0},
        "preferences": {"vegetarian": False, "dairy_free": False, "vegan": False, "low_prep": False, "budget_friendly": True, "meal_style": "any"},
        "days": 1,
        "shopping_mode": "balanced",
    },
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db-path", type=Path, default=model_candidate_training.default_db_path(), help="Path to the local DuckDB database.")
    parser.add_argument("--lat", type=float, default=DEFAULT_LOCATION["lat"], help="Latitude for the comparison location.")
    parser.add_argument("--lon", type=float, default=DEFAULT_LOCATION["lon"], help="Longitude for the comparison location.")
    parser.add_argument("--radius-m", type=float, default=DEFAULT_RADIUS_M, help="Nearby-store search radius in meters.")
    parser.add_argument("--store-limit", type=int, default=DEFAULT_STORE_LIMIT, help="Nearby-store limit.")
    parser.add_argument("--candidate-count", type=int, default=6, help="Heuristic candidate count to generate per preset.")
    parser.add_argument("--model-candidate-count", type=int, default=4, help="Maximum learned candidates to add per preset.")
    parser.add_argument("--old-scorer-model-path", type=Path, default=plan_scorer.default_model_path(), help="Path to the baseline scorer artifact.")
    parser.add_argument(
        "--new-scorer-model-path",
        type=Path,
        default=plan_scorer.default_model_dir() / "hybrid_planner_fair_v1" / plan_scorer.default_model_path().name,
        help="Path to the new scorer artifact.",
    )
    parser.add_argument(
        "--candidate-generator-model-path",
        type=Path,
        default=model_candidate_generator.default_model_path(),
        help="Path to the learned candidate-generator artifact.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=plan_scorer.default_model_dir(),
        help="Directory for the scorer comparison CSV and JSON outputs.",
    )
    return parser.parse_args()


def _build_candidate_pools(
    con: duckdb.DuckDBPyConnection,
    *,
    preset: dict[str, object],
    stores: list[dict[str, object]],
    price_context: dict[str, str],
    candidate_count: int,
    model_candidate_count: int,
    candidate_generator_model_path: Path,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    _heuristic_raw, heuristic_candidates, _heuristic_debug = hybrid_planner._build_candidate_pool(  # noqa: SLF001
        con,
        protein_target_g=float(preset["targets"]["protein"]),
        calorie_target_kcal=float(preset["targets"]["energy_fibre_kcal"]),
        preferences=dict(preset["preferences"]),
        nutrition_targets={key: value for key, value in dict(preset["targets"]).items() if key not in {"protein", "energy_fibre_kcal"}},
        pantry_items=[],
        days=int(preset["days"]),
        shopping_mode=str(preset["shopping_mode"]),
        price_context=price_context,
        stores=stores,
        candidate_count=candidate_count,
        candidate_generation_config={"enable_model_candidates": False},
    )
    _hybrid_raw, hybrid_candidates, _hybrid_debug = hybrid_planner._build_candidate_pool(  # noqa: SLF001
        con,
        protein_target_g=float(preset["targets"]["protein"]),
        calorie_target_kcal=float(preset["targets"]["energy_fibre_kcal"]),
        preferences=dict(preset["preferences"]),
        nutrition_targets={key: value for key, value in dict(preset["targets"]).items() if key not in {"protein", "energy_fibre_kcal"}},
        pantry_items=[],
        days=int(preset["days"]),
        shopping_mode=str(preset["shopping_mode"]),
        price_context=price_context,
        stores=stores,
        candidate_count=candidate_count,
        candidate_generation_config={
            "enable_model_candidates": True,
            "model_candidate_count": model_candidate_count,
            "candidate_generator_model_path": str(candidate_generator_model_path),
        },
    )
    return heuristic_candidates, hybrid_candidates


def _best_materially_different_model_row(
    ranked_rows: list[dict[str, object]],
) -> dict[str, object] | None:
    best_heuristic_row = hybrid_planner._best_ranked_entry(ranked_rows, origin="heuristic")  # noqa: SLF001
    if best_heuristic_row is None:
        return None
    return next(
        (
            row
            for row in ranked_rows
            if "model" in hybrid_planner._candidate_origin_labels(row["candidate"])  # noqa: SLF001
            and bool(candidate_debug.compare_candidates(row["candidate"], best_heuristic_row["candidate"]).get("materially_different"))
        ),
        None,
    )


def _source_label(row: dict[str, object]) -> str:
    return str(row["candidate"]["candidate_metadata"].get("source") or "heuristic")


def _pool_selection_summary(
    ranked_rows: list[dict[str, object]],
) -> dict[str, object]:
    selected_row = ranked_rows[0]
    best_materially_different_model_row = _best_materially_different_model_row(ranked_rows)
    best_materially_different_gap = (
        round(float(selected_row["model_score"]) - float(best_materially_different_model_row["model_score"]), 6)
        if best_materially_different_model_row is not None
        else None
    )
    feature_deltas = hybrid_planner._feature_delta_snapshot(  # noqa: SLF001
        selected_row,
        best_materially_different_model_row,
    )
    loss_reason = hybrid_planner._loss_reason_from_feature_deltas(feature_deltas)  # noqa: SLF001
    best_heuristic_row = hybrid_planner._best_ranked_entry(ranked_rows, origin="heuristic")  # noqa: SLF001
    selected_vs_best_heuristic = (
        candidate_debug.compare_candidates(selected_row["candidate"], best_heuristic_row["candidate"])
        if best_heuristic_row is not None
        else None
    )
    return {
        "selected_candidate_id": str(selected_row["candidate"]["candidate_id"]),
        "selected_candidate_source": _source_label(selected_row),
        "selected_candidate_score": round(float(selected_row["model_score"]), 6),
        "selected_candidate_shopping_food_ids": list(selected_row["candidate"]["candidate_metadata"].get("shopping_food_ids") or []),
        "selected_protein_gap_g": round(float(selected_row["feature_row"].get("protein_abs_gap_g") or 0.0), 6),
        "selected_calorie_gap_kcal": round(float(selected_row["feature_row"].get("calorie_abs_gap_kcal") or 0.0), 6),
        "selected_estimated_basket_cost": round(float(selected_row["feature_row"].get("estimated_basket_cost") or 0.0), 6),
        "selected_materially_differs_from_best_heuristic": bool(
            selected_vs_best_heuristic and selected_vs_best_heuristic.get("materially_different")
        ),
        "selected_difference_summary_vs_best_heuristic": (
            str(selected_vs_best_heuristic.get("difference_summary") or "")
            if selected_vs_best_heuristic is not None
            else ""
        ),
        "best_materially_different_model_candidate_id": (
            str(best_materially_different_model_row["candidate"]["candidate_id"])
            if best_materially_different_model_row is not None
            else None
        ),
        "best_materially_different_model_candidate_score": (
            round(float(best_materially_different_model_row["model_score"]), 6)
            if best_materially_different_model_row is not None
            else None
        ),
        "best_materially_different_model_gap_to_winner": best_materially_different_gap,
        "best_materially_different_model_loss_reason": (
            "selected materially-different model candidate won"
            if best_materially_different_model_row is not None
            and str(best_materially_different_model_row["candidate"]["candidate_id"]) == str(selected_row["candidate"]["candidate_id"])
            else loss_reason
        ),
        "best_materially_different_model_feature_deltas_vs_selected": feature_deltas,
    }


def _regressed_badly(old_summary: Mapping[str, object], new_summary: Mapping[str, object]) -> bool:
    return bool(
        float(new_summary["selected_protein_gap_g"]) - float(old_summary["selected_protein_gap_g"]) >= 15.0
        or float(new_summary["selected_calorie_gap_kcal"]) - float(old_summary["selected_calorie_gap_kcal"]) >= 150.0
        or float(new_summary["selected_estimated_basket_cost"]) - float(old_summary["selected_estimated_basket_cost"]) >= 3.0
    )


def _average_losing_gap(rows: list[dict[str, object]], key: str) -> float:
    values = [float(row[key]) for row in rows if row[key] is not None and float(row[key]) > 0]
    if not values:
        return 0.0
    return round(sum(values) / len(values), 6)


def main() -> int:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    old_bundle = plan_scorer.load_bundle(args.old_scorer_model_path)
    new_bundle = plan_scorer.load_bundle(args.new_scorer_model_path)

    rows: list[dict[str, object]] = []
    with duckdb.connect(args.db_path, read_only=True) as con:
        stores = nearby_stores(con, lat=args.lat, lon=args.lon, radius_m=args.radius_m, limit=args.store_limit)
        price_context = resolve_price_context(args.lat, args.lon, stores)

        for preset in MAIN_PRESETS:
            heuristic_candidates, hybrid_candidates = _build_candidate_pools(
                con,
                preset=preset,
                stores=stores,
                price_context=price_context,
                candidate_count=args.candidate_count,
                model_candidate_count=args.model_candidate_count,
                candidate_generator_model_path=args.candidate_generator_model_path,
            )

            old_heuristic_ranked = hybrid_planner._score_and_rank_candidates(heuristic_candidates, scorer_bundle=old_bundle)  # noqa: SLF001
            old_hybrid_ranked = hybrid_planner._score_and_rank_candidates(hybrid_candidates, scorer_bundle=old_bundle)  # noqa: SLF001
            new_heuristic_ranked = hybrid_planner._score_and_rank_candidates(heuristic_candidates, scorer_bundle=new_bundle)  # noqa: SLF001
            new_hybrid_ranked = hybrid_planner._score_and_rank_candidates(hybrid_candidates, scorer_bundle=new_bundle)  # noqa: SLF001

            old_summary = _pool_selection_summary(old_hybrid_ranked)
            new_summary = _pool_selection_summary(new_hybrid_ranked)
            old_heuristic_summary = _pool_selection_summary(old_heuristic_ranked)
            new_heuristic_summary = _pool_selection_summary(new_heuristic_ranked)
            before_after_difference = candidate_debug.compare_candidates(
                old_hybrid_ranked[0]["candidate"],
                new_hybrid_ranked[0]["candidate"],
            )

            rows.append(
                {
                    "preset_id": str(preset["preset_id"]),
                    "preset_label": str(preset["label"]),
                    "old_hybrid_selected_source": str(old_summary["selected_candidate_source"]),
                    "new_hybrid_selected_source": str(new_summary["selected_candidate_source"]),
                    "selected_candidate_source_changed": int(
                        str(old_summary["selected_candidate_source"]) != str(new_summary["selected_candidate_source"])
                    ),
                    "old_hybrid_selected_score": float(old_summary["selected_candidate_score"]),
                    "new_hybrid_selected_score": float(new_summary["selected_candidate_score"]),
                    "old_hybrid_score_improved_vs_heuristic_only": int(
                        float(old_summary["selected_candidate_score"]) > float(old_heuristic_summary["selected_candidate_score"])
                    ),
                    "new_hybrid_score_improved_vs_heuristic_only": int(
                        float(new_summary["selected_candidate_score"]) > float(new_heuristic_summary["selected_candidate_score"])
                    ),
                    "old_model_selected": int(str(old_summary["selected_candidate_source"]) in {"model", "repaired_model", "hybrid"}),
                    "new_model_selected": int(str(new_summary["selected_candidate_source"]) in {"model", "repaired_model", "hybrid"}),
                    "old_materially_different_model_selected": int(
                        bool(old_summary["selected_materially_differs_from_best_heuristic"])
                        and str(old_summary["selected_candidate_source"]) in {"model", "repaired_model", "hybrid"}
                    ),
                    "new_materially_different_model_selected": int(
                        bool(new_summary["selected_materially_differs_from_best_heuristic"])
                        and str(new_summary["selected_candidate_source"]) in {"model", "repaired_model", "hybrid"}
                    ),
                    "old_gap_to_best_materially_different_model": old_summary["best_materially_different_model_gap_to_winner"],
                    "new_gap_to_best_materially_different_model": new_summary["best_materially_different_model_gap_to_winner"],
                    "old_best_materially_different_model_loss_reason": str(old_summary["best_materially_different_model_loss_reason"] or ""),
                    "new_best_materially_different_model_loss_reason": str(new_summary["best_materially_different_model_loss_reason"] or ""),
                    "old_selected_protein_gap_g": float(old_summary["selected_protein_gap_g"]),
                    "new_selected_protein_gap_g": float(new_summary["selected_protein_gap_g"]),
                    "old_selected_calorie_gap_kcal": float(old_summary["selected_calorie_gap_kcal"]),
                    "new_selected_calorie_gap_kcal": float(new_summary["selected_calorie_gap_kcal"]),
                    "old_selected_estimated_basket_cost": float(old_summary["selected_estimated_basket_cost"]),
                    "new_selected_estimated_basket_cost": float(new_summary["selected_estimated_basket_cost"]),
                    "before_after_selected_overlap_jaccard": round(float(before_after_difference["jaccard_overlap"]), 6),
                    "before_after_difference_summary": str(before_after_difference["difference_summary"]),
                    "quality_regressed_badly": int(_regressed_badly(old_summary, new_summary)),
                }
            )

    csv_path = args.output_dir / "scorer_artifact_comparison_summary.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    summary_payload = {
        "location": {
            "label": DEFAULT_LOCATION["label"],
            "lat": args.lat,
            "lon": args.lon,
            "radius_m": args.radius_m,
            "store_limit": args.store_limit,
        },
        "old_scorer_model_path": str(args.old_scorer_model_path),
        "new_scorer_model_path": str(args.new_scorer_model_path),
        "candidate_generator_model_path": str(args.candidate_generator_model_path),
        "old_scorer": {
            "hybrid_score_improved_preset_count": sum(int(row["old_hybrid_score_improved_vs_heuristic_only"]) for row in rows),
            "model_selected_preset_count": sum(int(row["old_model_selected"]) for row in rows),
            "materially_different_model_selected_preset_count": sum(int(row["old_materially_different_model_selected"]) for row in rows),
            "losing_materially_different_model_preset_count": sum(
                1 for row in rows if row["old_gap_to_best_materially_different_model"] is not None and float(row["old_gap_to_best_materially_different_model"]) > 0
            ),
            "average_gap_to_best_losing_materially_different_model": _average_losing_gap(rows, "old_gap_to_best_materially_different_model"),
        },
        "new_scorer": {
            "hybrid_score_improved_preset_count": sum(int(row["new_hybrid_score_improved_vs_heuristic_only"]) for row in rows),
            "model_selected_preset_count": sum(int(row["new_model_selected"]) for row in rows),
            "materially_different_model_selected_preset_count": sum(int(row["new_materially_different_model_selected"]) for row in rows),
            "losing_materially_different_model_preset_count": sum(
                1 for row in rows if row["new_gap_to_best_materially_different_model"] is not None and float(row["new_gap_to_best_materially_different_model"]) > 0
            ),
            "average_gap_to_best_losing_materially_different_model": _average_losing_gap(rows, "new_gap_to_best_materially_different_model"),
        },
        "before_after": {
            "selected_candidate_source_changed_preset_count": sum(int(row["selected_candidate_source_changed"]) for row in rows),
            "quality_regressed_badly_preset_count": sum(int(row["quality_regressed_badly"]) for row in rows),
            "presets": rows,
        },
    }

    json_path = args.output_dir / "scorer_artifact_comparison_summary.json"
    json_path.write_text(json.dumps(summary_payload, indent=2), encoding="utf-8")

    print(f"csv_path={csv_path}")
    print(f"json_path={json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
