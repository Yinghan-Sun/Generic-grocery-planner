#!/usr/bin/env -S uv run --extra ml python
"""Run a small robustness sweep for the frozen generalized Route B algorithm."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

import duckdb

from dietdashboard import candidate_debug
from dietdashboard import route_b_evaluation
from dietdashboard import route_b_final
from dietdashboard.store_discovery import DEFAULT_LIMIT as DEFAULT_STORE_LIMIT
from dietdashboard.store_discovery import DEFAULT_RADIUS_M


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db-path", type=Path, default=route_b_evaluation.default_db_path(), help="Path to the local DuckDB database.")
    parser.add_argument("--lat", type=float, default=route_b_final.DEFAULT_LOCATION["lat"], help="Latitude for the main robustness location.")
    parser.add_argument("--lon", type=float, default=route_b_final.DEFAULT_LOCATION["lon"], help="Longitude for the main robustness location.")
    parser.add_argument("--radius-m", type=float, default=DEFAULT_RADIUS_M, help="Nearby-store search radius in meters.")
    parser.add_argument("--store-limit", type=int, default=DEFAULT_STORE_LIMIT, help="Nearby-store limit.")
    parser.add_argument("--candidate-count", type=int, default=6, help="Total candidates ranked by the scorer.")
    parser.add_argument("--scorer-model-path", type=Path, default=route_b_final.FINAL_SCORER_MODEL_PATH, help="Path to the frozen fair scorer artifact.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=route_b_final.FINAL_OUTPUT_DIR / "robustness",
        help="Directory for the robustness CSV and JSON outputs.",
    )
    return parser.parse_args()


def _scaled_targets(targets: dict[str, float], *, protein_scale: float, calorie_scale: float) -> dict[str, float]:
    scaled = {key: float(value) for key, value in targets.items()}
    for key, value in list(scaled.items()):
        if key == "protein":
            scaled[key] = round(value * protein_scale, 3)
        elif key == "energy_fibre_kcal":
            scaled[key] = round(value * calorie_scale, 3)
        else:
            scaled[key] = round(value * ((protein_scale + calorie_scale) / 2.0), 3)
    return scaled


def _scenario_variants() -> list[dict[str, object]]:
    return [
        {"variant_id": "base", "label": "Base preset"},
        {
            "variant_id": "targets_plus_5pct",
            "label": "Targets +5%",
            "protein_scale": 1.05,
            "calorie_scale": 1.05,
        },
        {
            "variant_id": "targets_minus_5pct",
            "label": "Targets -5%",
            "protein_scale": 0.95,
            "calorie_scale": 0.95,
        },
        {
            "variant_id": "days3_fresh",
            "label": "3 days / fresh",
            "days": 3,
            "shopping_mode": "fresh",
        },
        {
            "variant_id": "days3_bulk",
            "label": "3 days / bulk",
            "days": 3,
            "shopping_mode": "bulk",
        },
        {
            "variant_id": "alternate_location",
            "label": "Alternate location",
            "location": route_b_final.ALTERNATE_LOCATION,
        },
    ]


def _apply_variant(
    preset: dict[str, object],
    variant: dict[str, object],
) -> dict[str, object]:
    updated = {
        "preset_id": str(preset["preset_id"]),
        "label": str(preset["label"]),
        "targets": dict(preset["targets"]),
        "preferences": dict(preset["preferences"]),
        "days": int(preset["days"]),
        "shopping_mode": str(preset["shopping_mode"]),
        "pantry_items": list(preset.get("pantry_items") or []),
    }
    if variant.get("protein_scale") or variant.get("calorie_scale"):
        updated["targets"] = _scaled_targets(
            dict(updated["targets"]),
            protein_scale=float(variant.get("protein_scale") or 1.0),
            calorie_scale=float(variant.get("calorie_scale") or 1.0),
        )
    if variant.get("days") is not None:
        updated["days"] = int(variant["days"])
    if variant.get("shopping_mode") is not None:
        updated["shopping_mode"] = str(variant["shopping_mode"])
    return updated


def _is_brittle_case(
    *,
    score_delta: float,
    protein_gap_delta: float,
    calorie_gap_delta: float,
    cost_delta: float,
) -> bool:
    return bool(
        score_delta < -0.5
        or calorie_gap_delta >= 200.0
        or (protein_gap_delta >= 15.0 and cost_delta >= 2.0)
    )


def main() -> int:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    csv_path = args.output_dir / "route_b_robustness_summary.csv"
    json_path = args.output_dir / "route_b_robustness_summary.json"

    variants = _scenario_variants()
    rows: list[dict[str, object]] = []
    store_context_cache: dict[tuple[float, float], tuple[list[dict[str, object]], dict[str, str]]] = {}

    with duckdb.connect(args.db_path, read_only=True) as con:
        for preset in route_b_final.MAIN_PRESETS:
            for variant in variants:
                scenario_preset = _apply_variant(preset, variant)
                location = dict(variant.get("location") or {"lat": args.lat, "lon": args.lon, "label": route_b_final.DEFAULT_LOCATION["label"]})
                location_key = (float(location["lat"]), float(location["lon"]))
                if location_key not in store_context_cache:
                    store_context_cache[location_key] = route_b_evaluation.load_store_context(
                        con,
                        lat=float(location["lat"]),
                        lon=float(location["lon"]),
                        radius_m=args.radius_m,
                        store_limit=args.store_limit,
                    )
                stores, price_context = store_context_cache[location_key]

                heuristic_response = route_b_evaluation.run_scored_system(
                    con,
                    preset=scenario_preset,
                    stores=stores,
                    price_context=price_context,
                    scorer_model_path=args.scorer_model_path,
                    candidate_count=args.candidate_count,
                    candidate_generation_config=route_b_final.final_candidate_generation_config(
                        enable_model_candidates=False,
                        debug=True,
                    ),
                )
                final_response = route_b_evaluation.run_scored_system(
                    con,
                    preset=scenario_preset,
                    stores=stores,
                    price_context=price_context,
                    scorer_model_path=args.scorer_model_path,
                    candidate_count=args.candidate_count,
                    candidate_generation_config=route_b_final.final_candidate_generation_config(debug=True),
                )

                difference = candidate_debug.compare_candidates(heuristic_response, final_response)
                score_delta = round(
                    route_b_evaluation.selected_scorer_score(final_response)
                    - route_b_evaluation.selected_scorer_score(heuristic_response),
                    6,
                )
                protein_gap_delta = round(
                    route_b_evaluation.protein_gap(final_response) - route_b_evaluation.protein_gap(heuristic_response),
                    6,
                )
                calorie_gap_delta = round(
                    route_b_evaluation.calorie_gap(final_response) - route_b_evaluation.calorie_gap(heuristic_response),
                    6,
                )
                cost_delta = round(
                    route_b_evaluation.estimated_basket_cost(final_response)
                    - route_b_evaluation.estimated_basket_cost(heuristic_response),
                    6,
                )
                rows.append(
                    {
                        "scenario_id": f"{preset['preset_id']}__{variant['variant_id']}",
                        "preset_id": str(preset["preset_id"]),
                        "preset_label": str(preset["label"]),
                        "variant_id": str(variant["variant_id"]),
                        "variant_label": str(variant["label"]),
                        "location_label": str(location["label"]),
                        "heuristic_selected_source": route_b_evaluation.selected_source(heuristic_response),
                        "final_selected_source": route_b_evaluation.selected_source(final_response),
                        "selected_candidate_source_changed": int(
                            route_b_evaluation.selected_source(heuristic_response)
                            != route_b_evaluation.selected_source(final_response)
                        ),
                        "heuristic_scorer_score": route_b_evaluation.selected_scorer_score(heuristic_response),
                        "final_scorer_score": route_b_evaluation.selected_scorer_score(final_response),
                        "score_delta_vs_heuristic": score_delta,
                        "heuristic_protein_gap_g": route_b_evaluation.protein_gap(heuristic_response),
                        "final_protein_gap_g": route_b_evaluation.protein_gap(final_response),
                        "protein_gap_delta_vs_heuristic": protein_gap_delta,
                        "heuristic_calorie_gap_kcal": route_b_evaluation.calorie_gap(heuristic_response),
                        "final_calorie_gap_kcal": route_b_evaluation.calorie_gap(final_response),
                        "calorie_gap_delta_vs_heuristic": calorie_gap_delta,
                        "heuristic_estimated_basket_cost": route_b_evaluation.estimated_basket_cost(heuristic_response),
                        "final_estimated_basket_cost": route_b_evaluation.estimated_basket_cost(final_response),
                        "cost_delta_vs_heuristic": cost_delta,
                        "materially_different": int(bool(difference["materially_different"])),
                        "difference_summary": str(difference["difference_summary"]),
                        "brittle_case": int(
                            _is_brittle_case(
                                score_delta=score_delta,
                                protein_gap_delta=protein_gap_delta,
                                calorie_gap_delta=calorie_gap_delta,
                                cost_delta=cost_delta,
                            )
                        ),
                    }
                )

    fieldnames = list(rows[0].keys()) if rows else []
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    per_preset_rows: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        per_preset_rows[str(row["preset_id"])].append(row)

    preset_stability: list[dict[str, object]] = []
    for preset in route_b_final.MAIN_PRESETS:
        preset_id = str(preset["preset_id"])
        preset_rows = per_preset_rows[preset_id]
        source_counts = Counter(str(row["final_selected_source"]) for row in preset_rows)
        dominant_source, dominant_count = source_counts.most_common(1)[0]
        preset_stability.append(
            {
                "preset_id": preset_id,
                "dominant_final_source": dominant_source,
                "winner_source_stability_ratio": round(dominant_count / max(len(preset_rows), 1), 6),
                "final_source_distribution": dict(source_counts),
                "score_improved_case_count": sum(1 for row in preset_rows if float(row["score_delta_vs_heuristic"]) > 0.0),
                "materially_different_case_count": sum(int(row["materially_different"]) for row in preset_rows),
            }
        )

    brittle_cases = [
        {
            "scenario_id": row["scenario_id"],
            "preset_id": row["preset_id"],
            "variant_id": row["variant_id"],
            "score_delta_vs_heuristic": row["score_delta_vs_heuristic"],
            "difference_summary": row["difference_summary"],
        }
        for row in rows
        if int(row["brittle_case"]) == 1
    ]

    summary_payload = {
        "main_algorithm": route_b_final.final_runtime_metadata(),
        "scenario_count": len(rows),
        "variant_count": len(variants),
        "score_improved_case_count": sum(1 for row in rows if float(row["score_delta_vs_heuristic"]) > 0.0),
        "model_selected_case_count": sum(
            1 for row in rows if str(row["final_selected_source"]) in {"model", "repaired_model", "hybrid"}
        ),
        "selected_candidate_source_changed_case_count": sum(int(row["selected_candidate_source_changed"]) for row in rows),
        "materially_different_case_count": sum(int(row["materially_different"]) for row in rows),
        "average_score_delta_vs_heuristic": round(
            sum(float(row["score_delta_vs_heuristic"]) for row in rows) / max(len(rows), 1),
            6,
        ),
        "average_winner_source_stability_ratio": round(
            sum(float(entry["winner_source_stability_ratio"]) for entry in preset_stability) / max(len(preset_stability), 1),
            6,
        ),
        "brittle_case_count": len(brittle_cases),
        "brittle_cases": brittle_cases,
        "preset_stability": preset_stability,
        "rows": rows,
    }
    json_path.write_text(json.dumps(summary_payload, indent=2), encoding="utf-8")

    print(f"wrote_csv={csv_path}")
    print(f"wrote_json={json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
