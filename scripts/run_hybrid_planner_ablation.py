#!/usr/bin/env -S uv run --extra ml python
"""Run a small ablation study for the frozen generalized hybrid planner pipeline."""

from __future__ import annotations

import argparse
import csv
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
    parser.add_argument("--lat", type=float, default=hybrid_pipeline_final.DEFAULT_LOCATION["lat"], help="Latitude for evaluation.")
    parser.add_argument("--lon", type=float, default=hybrid_pipeline_final.DEFAULT_LOCATION["lon"], help="Longitude for evaluation.")
    parser.add_argument("--radius-m", type=float, default=DEFAULT_RADIUS_M, help="Nearby-store search radius in meters.")
    parser.add_argument("--store-limit", type=int, default=DEFAULT_STORE_LIMIT, help="Nearby-store limit.")
    parser.add_argument("--candidate-count", type=int, default=6, help="Total candidates ranked by the scorer.")
    parser.add_argument("--scorer-model-path", type=Path, default=hybrid_pipeline_final.FINAL_SCORER_MODEL_PATH, help="Path to the frozen fair scorer artifact.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=hybrid_pipeline_final.FINAL_OUTPUT_DIR / "ablation",
        help="Directory for the ablation CSV and JSON outputs.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    csv_path = args.output_dir / "hybrid_planner_ablation_summary.csv"
    json_path = args.output_dir / "hybrid_planner_ablation_summary.json"

    responses: dict[tuple[str, str], dict[str, object]] = {}
    rows: list[dict[str, object]] = []
    ablations = hybrid_pipeline_final.ablation_specs()

    with duckdb.connect(args.db_path, read_only=True) as con:
        stores, price_context = hybrid_pipeline_evaluation.load_store_context(
            con,
            lat=args.lat,
            lon=args.lon,
            radius_m=args.radius_m,
            store_limit=args.store_limit,
        )

        for preset in hybrid_pipeline_final.MAIN_PRESETS:
            for spec in ablations:
                if str(spec["mode"]) == "legacy_heuristic":
                    response = hybrid_pipeline_evaluation.run_legacy_heuristic(
                        con,
                        preset=preset,
                        stores=stores,
                        price_context=price_context,
                        scorer_model_path=args.scorer_model_path,
                        candidate_count=args.candidate_count,
                    )
                else:
                    response = hybrid_pipeline_evaluation.run_scored_system(
                        con,
                        preset=preset,
                        stores=stores,
                        price_context=price_context,
                        scorer_model_path=args.scorer_model_path,
                        candidate_count=args.candidate_count,
                        candidate_generation_config=spec.get("candidate_generation_config"),
                    )
                responses[(str(spec["system_id"]), str(preset["preset_id"]))] = response

        baseline_system_id = "heuristic_scorer_only"
        full_system_id = hybrid_pipeline_final.FINAL_ALGORITHM_VERSION.replace("_v5_main", "_main")
        if not any(str(spec["system_id"]) == full_system_id for spec in ablations):
            full_system_id = "hybrid_planner_generalized_main"

        for preset in hybrid_pipeline_final.MAIN_PRESETS:
            preset_id = str(preset["preset_id"])
            baseline_response = responses[(baseline_system_id, preset_id)]
            full_response = responses[(full_system_id, preset_id)]
            baseline_score = hybrid_pipeline_evaluation.selected_scorer_score(baseline_response)
            full_selected_source = hybrid_pipeline_evaluation.selected_source(full_response)
            for spec in ablations:
                system_id = str(spec["system_id"])
                response = responses[(system_id, preset_id)]
                difference = candidate_debug.compare_candidates(baseline_response, response)
                score = hybrid_pipeline_evaluation.selected_scorer_score(response)
                row = {
                    "system_id": system_id,
                    "system_label": str(spec["label"]),
                    "system_mode": str(spec["mode"]),
                    "preset_id": preset_id,
                    "preset_label": str(preset["label"]),
                    "hybrid_planner_algorithm_version": str(response.get("hybrid_planner_algorithm_version") or ""),
                    "selected_source": hybrid_pipeline_evaluation.selected_source(response),
                    "scorer_score": score,
                    "protein_gap_g": hybrid_pipeline_evaluation.protein_gap(response),
                    "calorie_gap_kcal": hybrid_pipeline_evaluation.calorie_gap(response),
                    "estimated_basket_cost": hybrid_pipeline_evaluation.estimated_basket_cost(response),
                    "score_delta_vs_heuristic_scorer": round(score - baseline_score, 6),
                    "protein_gap_delta_vs_heuristic_scorer": round(
                        hybrid_pipeline_evaluation.protein_gap(response) - hybrid_pipeline_evaluation.protein_gap(baseline_response),
                        6,
                    ),
                    "calorie_gap_delta_vs_heuristic_scorer": round(
                        hybrid_pipeline_evaluation.calorie_gap(response) - hybrid_pipeline_evaluation.calorie_gap(baseline_response),
                        6,
                    ),
                    "cost_delta_vs_heuristic_scorer": round(
                        hybrid_pipeline_evaluation.estimated_basket_cost(response)
                        - hybrid_pipeline_evaluation.estimated_basket_cost(baseline_response),
                        6,
                    ),
                    "selected_candidate_source_changed_vs_heuristic_scorer": int(
                        hybrid_pipeline_evaluation.selected_source(response)
                        != hybrid_pipeline_evaluation.selected_source(baseline_response)
                    ),
                    "materially_different_vs_heuristic_scorer": int(bool(difference["materially_different"])),
                    "difference_summary_vs_heuristic_scorer": str(difference["difference_summary"]),
                    "full_generalized_selected_source": full_selected_source,
                    "matches_full_generalized_source": int(hybrid_pipeline_evaluation.selected_source(response) == full_selected_source),
                }
                rows.append(row)

    fieldnames = list(rows[0].keys()) if rows else []
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    full_model_win_preset_ids = {
        row["preset_id"]
        for row in rows
        if row["system_id"] == full_system_id and str(row["selected_source"]) in {"model", "repaired_model", "hybrid"}
    }
    systems_summary: list[dict[str, object]] = []
    for spec in ablations:
        system_id = str(spec["system_id"])
        system_rows = [row for row in rows if row["system_id"] == system_id]
        lost_full_wins = [
            row["preset_id"]
            for row in system_rows
            if row["preset_id"] in full_model_win_preset_ids and str(row["selected_source"]) not in {"model", "repaired_model", "hybrid"}
        ]
        systems_summary.append(
            {
                "system_id": system_id,
                "system_label": str(spec["label"]),
                "system_mode": str(spec["mode"]),
                "hybrid_score_improved_preset_count": sum(
                    1 for row in system_rows if float(row["score_delta_vs_heuristic_scorer"]) > 0.0
                ),
                "model_selected_preset_count": sum(
                    1 for row in system_rows if str(row["selected_source"]) in {"model", "repaired_model", "hybrid"}
                ),
                "selected_candidate_source_changed_preset_count": sum(
                    int(row["selected_candidate_source_changed_vs_heuristic_scorer"]) for row in system_rows
                ),
                "materially_different_preset_count": sum(
                    int(row["materially_different_vs_heuristic_scorer"]) for row in system_rows
                ),
                "average_score_delta_vs_heuristic_scorer": round(
                    sum(float(row["score_delta_vs_heuristic_scorer"]) for row in system_rows) / max(len(system_rows), 1),
                    6,
                ),
                "current_full_wins_disappear_count": len(lost_full_wins),
                "current_full_wins_disappear_preset_ids": lost_full_wins,
                "preset_outcomes": [
                    {
                        "preset_id": row["preset_id"],
                        "selected_source": row["selected_source"],
                        "score_delta_vs_heuristic_scorer": row["score_delta_vs_heuristic_scorer"],
                        "difference_summary_vs_heuristic_scorer": row["difference_summary_vs_heuristic_scorer"],
                    }
                    for row in system_rows
                ],
            }
        )

    summary_payload = {
        "main_algorithm": hybrid_pipeline_final.final_runtime_metadata(),
        "comparison_reference_system_id": baseline_system_id,
        "preset_count": len(hybrid_pipeline_final.MAIN_PRESETS),
        "full_generalized_model_win_preset_ids": sorted(full_model_win_preset_ids),
        "systems": systems_summary,
        "rows": rows,
    }
    json_path.write_text(json.dumps(summary_payload, indent=2), encoding="utf-8")

    print(f"wrote_csv={csv_path}")
    print(f"wrote_json={json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
