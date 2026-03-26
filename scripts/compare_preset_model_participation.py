#!/usr/bin/env -S uv run --extra ml python
"""Compare the main local demo presets under heuristic-only versus model-enabled mode."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import duckdb

from dietdashboard import candidate_debug
from dietdashboard import model_candidate_generator
from dietdashboard import hybrid_pipeline_evaluation
from dietdashboard import hybrid_pipeline_final
from dietdashboard.store_discovery import DEFAULT_LIMIT as DEFAULT_STORE_LIMIT
from dietdashboard.store_discovery import DEFAULT_RADIUS_M


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db-path", type=Path, default=hybrid_pipeline_evaluation.default_db_path(), help="Path to the local DuckDB database.")
    parser.add_argument("--lat", type=float, default=hybrid_pipeline_final.DEFAULT_LOCATION["lat"], help="Latitude for preset comparison.")
    parser.add_argument("--lon", type=float, default=hybrid_pipeline_final.DEFAULT_LOCATION["lon"], help="Longitude for preset comparison.")
    parser.add_argument("--radius-m", type=float, default=DEFAULT_RADIUS_M, help="Nearby-store search radius in meters.")
    parser.add_argument("--store-limit", type=int, default=DEFAULT_STORE_LIMIT, help="Nearby-store limit.")
    parser.add_argument("--candidate-count", type=int, default=6, help="Total candidates ranked by the scorer.")
    parser.add_argument("--model-candidate-count", type=int, default=4, help="Maximum learned candidates to add in hybrid mode.")
    parser.add_argument("--scorer-model-path", type=Path, default=hybrid_pipeline_final.FINAL_SCORER_MODEL_PATH, help="Path to the trained plan-scorer artifact.")
    parser.add_argument(
        "--candidate-generator-model-path",
        type=Path,
        default=model_candidate_generator.default_model_path(),
        help="Path to the selected candidate-generator artifact.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=hybrid_pipeline_final.FINAL_OUTPUT_DIR,
        help="Directory for the preset comparison CSV and JSON outputs.",
    )
    return parser.parse_args()


def _selected_scorer_score(response: dict[str, object]) -> float:
    return hybrid_pipeline_evaluation.selected_scorer_score(response)


def _protein_gap(response: dict[str, object]) -> float:
    summary = dict(response.get("nutrition_summary") or {})
    return round(abs(float(summary.get("protein_estimated_g") or 0.0) - float(summary.get("protein_target_g") or 0.0)), 6)


def _calorie_gap(response: dict[str, object]) -> float:
    summary = dict(response.get("nutrition_summary") or {})
    return round(abs(float(summary.get("calorie_estimated_kcal") or 0.0) - float(summary.get("calorie_target_kcal") or 0.0)), 6)


def _run_system(
    con: duckdb.DuckDBPyConnection,
    *,
    preset: dict[str, object],
    stores: list[dict[str, object]],
    price_context: dict[str, str],
    scorer_model_path: Path,
    candidate_count: int,
    enable_model_candidates: bool,
    model_candidate_count: int,
    candidate_generator_model_path: Path,
) -> dict[str, object]:
    return hybrid_pipeline_evaluation.run_scored_system(
        con,
        preset=preset,
        stores=stores,
        price_context=price_context,
        scorer_model_path=scorer_model_path,
        candidate_count=candidate_count,
        candidate_generation_config=hybrid_pipeline_final.final_candidate_generation_config(
            enable_model_candidates=enable_model_candidates,
            model_candidate_count=model_candidate_count,
            candidate_generator_model_path=candidate_generator_model_path,
            debug=True,
        ),
    )


def main() -> int:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    csv_path = args.output_dir / "preset_comparison_summary.csv"
    json_path = args.output_dir / "preset_comparison_summary.json"

    with duckdb.connect(args.db_path, read_only=True) as con:
        stores, price_context = hybrid_pipeline_evaluation.load_store_context(
            con,
            lat=args.lat,
            lon=args.lon,
            radius_m=args.radius_m,
            store_limit=args.store_limit,
        )

        rows: list[dict[str, object]] = []
        for preset in hybrid_pipeline_final.MAIN_PRESETS:
            heuristic_response = _run_system(
                con,
                preset=preset,
                stores=stores,
                price_context=price_context,
                scorer_model_path=args.scorer_model_path,
                candidate_count=args.candidate_count,
                enable_model_candidates=False,
                model_candidate_count=args.model_candidate_count,
                candidate_generator_model_path=args.candidate_generator_model_path,
            )
            hybrid_response = _run_system(
                con,
                preset=preset,
                stores=stores,
                price_context=price_context,
                scorer_model_path=args.scorer_model_path,
                candidate_count=args.candidate_count,
                enable_model_candidates=True,
                model_candidate_count=args.model_candidate_count,
                candidate_generator_model_path=args.candidate_generator_model_path,
            )

            difference = candidate_debug.compare_candidates(heuristic_response, hybrid_response)
            hybrid_debug = dict(hybrid_response.get("candidate_comparison_debug") or {})
            algorithmic_faithfulness = dict(hybrid_debug.get("algorithmic_faithfulness") or {})
            row = {
                "hybrid_planner_algorithm_version": str(hybrid_response.get("hybrid_planner_algorithm_version") or ""),
                "hybrid_planner_structured_complementarity_enabled": int(
                    bool((hybrid_response.get("hybrid_planner_algorithm") or {}).get("structured_complementarity_enabled", True))
                ),
                "hybrid_planner_structured_materialization_enabled": int(
                    bool((hybrid_response.get("hybrid_planner_algorithm") or {}).get("structured_materialization_enabled", True))
                ),
                "preset_id": str(preset["preset_id"]),
                "preset_label": str(preset["label"]),
                "heuristic_selected_source": str(heuristic_response.get("selected_candidate_source") or "heuristic"),
                "hybrid_selected_source": str(hybrid_response.get("selected_candidate_source") or "heuristic"),
                "selected_candidate_source_changed": int(
                    str(heuristic_response.get("selected_candidate_source") or "heuristic")
                    != str(hybrid_response.get("selected_candidate_source") or "heuristic")
                ),
                "heuristic_scorer_score": round(_selected_scorer_score(heuristic_response), 6),
                "hybrid_scorer_score": round(_selected_scorer_score(hybrid_response), 6),
                "hybrid_score_improved": int(_selected_scorer_score(hybrid_response) > _selected_scorer_score(heuristic_response)),
                "heuristic_protein_gap_g": _protein_gap(heuristic_response),
                "hybrid_protein_gap_g": _protein_gap(hybrid_response),
                "hybrid_protein_gap_improved": int(_protein_gap(hybrid_response) < _protein_gap(heuristic_response)),
                "heuristic_calorie_gap_kcal": _calorie_gap(heuristic_response),
                "hybrid_calorie_gap_kcal": _calorie_gap(hybrid_response),
                "hybrid_calorie_gap_improved": int(_calorie_gap(hybrid_response) < _calorie_gap(heuristic_response)),
                "heuristic_estimated_basket_cost": round(float(heuristic_response.get("estimated_basket_cost") or 0.0), 6),
                "hybrid_estimated_basket_cost": round(float(hybrid_response.get("estimated_basket_cost") or 0.0), 6),
                "hybrid_cost_improved": int(
                    float(hybrid_response.get("estimated_basket_cost") or 0.0)
                    < float(heuristic_response.get("estimated_basket_cost") or 0.0)
                ),
                "selected_result_overlap_jaccard": round(float(difference["jaccard_overlap"]), 6),
                "changed_food_count": int(difference["changed_food_count"]),
                "role_assignment_changes": int(difference["role_assignment_changes"]),
                "final_basket_changed_by_role": int(int(difference["role_assignment_changes"]) >= 1),
                "cost_delta": round(float(difference["cost_delta"]), 6),
                "protein_gap_delta_g": round(float(difference["protein_gap_delta_g"]), 6),
                "calorie_gap_delta_kcal": round(float(difference["calorie_gap_delta_kcal"]), 6),
                "materially_different": int(bool(difference["materially_different"])),
                "cosmetically_similar": int(not bool(difference["materially_different"])),
                "difference_summary": str(difference["difference_summary"]),
                "hybrid_best_materially_different_model_candidate_id": str(hybrid_debug.get("best_materially_different_model_candidate_id") or ""),
                "hybrid_best_materially_different_model_candidate_source": str(
                    hybrid_debug.get("best_materially_different_model_candidate_source") or ""
                ),
                "hybrid_best_materially_different_model_candidate_score": (
                    round(float(hybrid_debug.get("best_materially_different_model_candidate_score") or 0.0), 6)
                    if hybrid_debug.get("best_materially_different_model_candidate_score") is not None
                    else None
                ),
                "hybrid_best_materially_different_model_score_gap_to_selected": (
                    round(float(hybrid_debug.get("best_materially_different_model_candidate_score_gap_to_selected") or 0.0), 6)
                    if hybrid_debug.get("best_materially_different_model_candidate_score_gap_to_selected") is not None
                    else None
                ),
                "hybrid_best_materially_different_model_loss_reason": str(
                    hybrid_debug.get("best_materially_different_model_candidate_loss_reason") or ""
                ),
                "hybrid_best_materially_different_model_loss_dimensions": dict(
                    hybrid_debug.get("best_materially_different_model_candidate_loss_dimensions") or {}
                ),
                "hybrid_best_materially_different_model_role_substitution_summaries": list(
                    hybrid_debug.get("best_materially_different_model_candidate_role_substitution_summaries") or []
                ),
                "hybrid_best_materially_different_model_failure_mode": str(
                    hybrid_debug.get("best_materially_different_model_candidate_failure_mode") or ""
                ),
                "hybrid_best_materially_different_model_produce_difference_summary": str(
                    hybrid_debug.get("best_materially_different_model_candidate_produce_difference_summary") or ""
                ),
                "hybrid_best_materially_different_model_seed_to_final_drift_summary": str(
                    hybrid_debug.get("best_materially_different_model_candidate_seed_to_final_drift_summary") or ""
                ),
                "hybrid_best_materially_different_model_seed_to_final_drift_score": (
                    round(float(hybrid_debug.get("best_materially_different_model_candidate_seed_to_final_drift_score") or 0.0), 6)
                    if hybrid_debug.get("best_materially_different_model_candidate_seed_to_final_drift_score") is not None
                    else None
                ),
                "hybrid_best_materially_different_model_remaining_primary_reason": str(
                    hybrid_debug.get("best_materially_different_model_candidate_remaining_primary_reason") or ""
                ),
                "hybrid_model_candidates_merged_count": int(hybrid_debug.get("model_candidates_merged_count") or 0),
                "hybrid_model_candidates_materially_different_count": int(hybrid_debug.get("model_candidates_materially_different_count") or 0),
                "hybrid_materially_different_model_candidates_surviving_after_fusion": int(
                    hybrid_debug.get("materially_different_model_candidates_surviving_after_fusion") or 0
                ),
                "hybrid_average_heuristic_model_overlap_jaccard": round(float(hybrid_debug.get("average_heuristic_model_overlap_jaccard") or 0.0), 6),
                "hybrid_model_candidates_mostly_near_duplicates": int(bool(hybrid_debug.get("model_candidates_mostly_near_duplicates"))),
                "hybrid_best_model_candidate_reason_summary": str(hybrid_debug.get("best_model_candidate_reason_summary") or ""),
                "hybrid_diagnosis_text": str(hybrid_debug.get("diagnosis_text") or ""),
                "hybrid_why_no_model_win_yet": str(hybrid_debug.get("why_no_model_win_yet") or ""),
                "hybrid_algorithmic_winner_mode": str(algorithmic_faithfulness.get("winner_mode") or ""),
                "hybrid_algorithmic_seed_to_final_drift_summary": str(algorithmic_faithfulness.get("seed_to_final_drift_summary") or ""),
                "hybrid_algorithmic_seed_to_final_drift_score": (
                    round(float(algorithmic_faithfulness.get("seed_to_final_drift_score") or 0.0), 6)
                    if algorithmic_faithfulness.get("seed_to_final_drift_score") is not None
                    else None
                ),
                "hybrid_algorithmic_top_terms": list(algorithmic_faithfulness.get("top_terms") or []),
            }
            rows.append(row)

    fieldnames = list(rows[0].keys()) if rows else []
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    summary_payload = {
        "main_algorithm": hybrid_pipeline_final.final_runtime_metadata(),
        "location": {
            "label": hybrid_pipeline_final.DEFAULT_LOCATION["label"],
            "lat": args.lat,
            "lon": args.lon,
            "radius_m": args.radius_m,
            "store_limit": args.store_limit,
        },
        "scorer_model_path": str(args.scorer_model_path),
        "candidate_generator_model_path": str(args.candidate_generator_model_path),
        "material_difference_rule": candidate_debug.MATERIAL_DIFFERENCE_RULE_TEXT,
        "preset_count": len(rows),
        "hybrid_score_improved_preset_count": sum(1 for row in rows if float(row["hybrid_scorer_score"]) > float(row["heuristic_scorer_score"])),
        "hybrid_cost_improved_preset_count": sum(int(row["hybrid_cost_improved"]) for row in rows),
        "hybrid_protein_gap_improved_preset_count": sum(int(row["hybrid_protein_gap_improved"]) for row in rows),
        "hybrid_calorie_gap_improved_preset_count": sum(int(row["hybrid_calorie_gap_improved"]) for row in rows),
        "materially_different_preset_count": sum(int(row["materially_different"]) for row in rows),
        "model_selected_preset_count": sum(1 for row in rows if str(row["hybrid_selected_source"]) in {"model", "repaired_model", "hybrid"}),
        "selected_candidate_source_changed_preset_count": sum(int(row["selected_candidate_source_changed"]) for row in rows),
        "final_basket_changed_by_role_preset_count": sum(int(row["final_basket_changed_by_role"]) for row in rows),
        "materially_different_model_candidates_surviving_preset_count": sum(
            1 for row in rows if int(row["hybrid_materially_different_model_candidates_surviving_after_fusion"]) > 0
        ),
        "best_materially_different_model_candidate_preset_count": sum(
            1 for row in rows if str(row["hybrid_best_materially_different_model_candidate_id"])
        ),
        "remaining_heuristic_preset_ids": [
            str(row["preset_id"])
            for row in rows
            if str(row["hybrid_selected_source"]) not in {"model", "repaired_model", "hybrid"}
        ],
        "current_model_win_preset_ids": [
            str(row["preset_id"])
            for row in rows
            if str(row["hybrid_selected_source"]) in {"model", "repaired_model", "hybrid"}
        ],
        "presets": rows,
    }
    fat_loss_row = next((row for row in rows if str(row["preset_id"]) == "fat_loss"), None)
    if fat_loss_row is not None:
        summary_payload["why_fat_loss_still_heuristic"] = {
            "selected_source": str(fat_loss_row["hybrid_selected_source"]),
            "score_gap_to_best_materially_different_model": fat_loss_row[
                "hybrid_best_materially_different_model_score_gap_to_selected"
            ],
            "remaining_primary_reason": str(fat_loss_row["hybrid_best_materially_different_model_remaining_primary_reason"]),
            "diagnosis_text": str(fat_loss_row["hybrid_diagnosis_text"]),
            "why_no_model_win_yet": str(fat_loss_row["hybrid_why_no_model_win_yet"]),
            "produce_difference_summary": str(fat_loss_row["hybrid_best_materially_different_model_produce_difference_summary"]),
            "seed_to_final_drift_summary": str(fat_loss_row["hybrid_best_materially_different_model_seed_to_final_drift_summary"]),
        }
    json_path.write_text(json.dumps(summary_payload, indent=2), encoding="utf-8")

    print(f"wrote_csv={csv_path}")
    print(f"wrote_json={json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
