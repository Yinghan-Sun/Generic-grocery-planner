#!/usr/bin/env -S uv run --extra ml python
"""Evaluate heuristic-only versus hybrid learned candidate generation."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from time import perf_counter

import duckdb

from dietdashboard import model_candidate_generator
from dietdashboard import model_candidate_training
from dietdashboard.generic_recommender import recommend_generic_foods
from dietdashboard.plan_scorer import default_model_path as default_scorer_model_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--db-path",
        type=Path,
        default=model_candidate_training.default_db_path(),
        help="Path to the local DuckDB database.",
    )
    parser.add_argument(
        "--scorer-model-path",
        type=Path,
        default=default_scorer_model_path(),
        help="Path to the trained plan-scorer artifact.",
    )
    parser.add_argument(
        "--candidate-generator-model-path",
        type=Path,
        default=model_candidate_generator.default_model_path(),
        help="Path to the selected candidate-generator artifact.",
    )
    parser.add_argument(
        "--candidate-count",
        type=int,
        default=6,
        help="Heuristic candidate count passed to the scorer runtime.",
    )
    parser.add_argument(
        "--model-candidate-count",
        type=int,
        default=4,
        help="Maximum number of learned candidates to add when the hybrid path is enabled.",
    )
    parser.add_argument(
        "--scenario-split",
        default="test",
        choices=("train", "validation", "test", "all"),
        help="Which scenario split to evaluate.",
    )
    parser.add_argument(
        "--scenario-limit",
        type=int,
        default=None,
        help="Optional limit for faster smoke runs.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=model_candidate_generator.default_model_dir(),
        help="Directory for evaluation reports.",
    )
    parser.add_argument(
        "--compare-backend-artifacts",
        action="store_true",
        help="Also evaluate backend-specific candidate-generator artifacts when they exist.",
    )
    return parser.parse_args()


def _scenario_rows(split: str, scenario_limit: int | None) -> list[dict[str, object]]:
    rows = model_candidate_training.scenario_grid(scenario_limit=scenario_limit)
    if split == "all":
        return rows
    return [row for row in rows if str(row["split"]) == split]


def _selected_model_score(response: dict[str, object]) -> float:
    debug_rows = response.get("scoring_debug", {}).get("candidates", [])
    for row in debug_rows:
        if row.get("selected"):
            return float(row["model_score"])
    return 0.0


def _macro_gap_ratio_sum(nutrition_summary: dict[str, object]) -> float:
    total = 0.0
    tracked_pairs = (
        ("carbohydrate_target_g", "carbohydrate_estimated_g"),
        ("fat_target_g", "fat_estimated_g"),
        ("fiber_target_g", "fiber_estimated_g"),
        ("calcium_target_mg", "calcium_estimated_mg"),
        ("iron_target_mg", "iron_estimated_mg"),
        ("vitamin_c_target_mg", "vitamin_c_estimated_mg"),
    )
    for target_key, estimate_key in tracked_pairs:
        target = float(nutrition_summary.get(target_key) or 0.0)
        estimate = float(nutrition_summary.get(estimate_key) or 0.0)
        if target > 0:
            total += abs(estimate - target) / max(target, 1.0)
    return round(total, 6)


def _price_per(value: float, denominator: float) -> float:
    if value <= 0 or denominator <= 0:
        return 0.0
    return round(value / denominator, 6)


def _system_specs(args: argparse.Namespace) -> list[dict[str, object]]:
    systems = [
        {
            "system_id": "heuristic_only",
            "label": "Heuristic Only",
            "candidate_generation_config": {
                "enable_model_candidates": False,
                "model_candidate_count": args.model_candidate_count,
                "debug": True,
            },
        },
        {
            "system_id": "hybrid_best",
            "label": "Hybrid Best Model",
            "candidate_generation_config": {
                "enable_model_candidates": True,
                "model_candidate_count": args.model_candidate_count,
                "candidate_generator_model_path": str(args.candidate_generator_model_path),
                "debug": True,
            },
        },
    ]
    if args.compare_backend_artifacts:
        for backend in model_candidate_generator.available_backends():
            backend_path = model_candidate_generator.default_backend_model_path(backend)
            if backend_path.exists():
                systems.append(
                    {
                        "system_id": f"hybrid_{backend}",
                        "label": f"Hybrid {backend}",
                        "candidate_generation_config": {
                            "enable_model_candidates": True,
                            "model_candidate_count": args.model_candidate_count,
                            "candidate_generator_model_path": str(backend_path),
                            "candidate_generator_backend": backend,
                            "debug": True,
                        },
                    }
                )
    return systems


def _scenario_result(
    response: dict[str, object],
    *,
    system_id: str,
    label: str,
    scenario: dict[str, object],
    generation_time_ms: float,
) -> dict[str, object]:
    nutrition_summary = dict(response["nutrition_summary"])
    shopping_list = list(response["shopping_list"])
    estimated_cost = float(response.get("estimated_basket_cost") or 0.0)
    estimated_protein = float(nutrition_summary.get("protein_estimated_g") or 0.0)
    estimated_calories = float(nutrition_summary.get("calorie_estimated_kcal") or 0.0)
    role_diversity = len({str(item["role"]) for item in shopping_list})
    selected_source = str(response.get("selected_candidate_source") or "heuristic")
    return {
        "system_id": system_id,
        "system_label": label,
        "scenario_id": str(scenario["scenario_id"]),
        "split": str(scenario["split"]),
        "goal_profile": str(response.get("goal_profile") or ""),
        "days": int(response.get("days") or scenario["days"]),
        "shopping_mode": str(response.get("shopping_mode") or scenario["shopping_mode"]),
        "selected_candidate_source": selected_source,
        "model_selected": int(selected_source in {"model", "repaired_model", "hybrid"}),
        "candidate_count_considered": int(response.get("candidate_count_considered") or 0),
        "generation_time_ms": round(generation_time_ms, 3),
        "protein_abs_gap_g": round(abs(estimated_protein - float(nutrition_summary.get("protein_target_g") or 0.0)), 6),
        "calorie_abs_gap_kcal": round(abs(estimated_calories - float(nutrition_summary.get("calorie_target_kcal") or 0.0)), 6),
        "macro_gap_ratio_sum": _macro_gap_ratio_sum(nutrition_summary),
        "estimated_basket_cost": round(estimated_cost, 6),
        "price_per_1000_kcal": _price_per(estimated_cost, estimated_calories / 1000.0),
        "price_per_100g_protein": _price_per(estimated_cost, estimated_protein / 100.0),
        "unique_ingredient_count": len(shopping_list),
        "role_diversity_count": role_diversity,
        "warning_count": len(response.get("warnings") or []),
        "scorer_score": round(_selected_model_score(response), 6),
    }


def _average(rows: list[dict[str, object]], key: str) -> float:
    if not rows:
        return 0.0
    return round(sum(float(row[key]) for row in rows) / len(rows), 6)


def _summary_payload(results: list[dict[str, object]]) -> dict[str, object]:
    grouped: dict[str, list[dict[str, object]]] = {}
    by_scenario: dict[tuple[str, str], dict[str, object]] = {}
    for row in results:
        grouped.setdefault(str(row["system_id"]), []).append(row)
        by_scenario[(str(row["scenario_id"]), str(row["system_id"]))] = row

    systems_summary = {
        system_id: {
            "scenario_count": len(rows),
            "avg_protein_abs_gap_g": _average(rows, "protein_abs_gap_g"),
            "avg_calorie_abs_gap_kcal": _average(rows, "calorie_abs_gap_kcal"),
            "avg_macro_gap_ratio_sum": _average(rows, "macro_gap_ratio_sum"),
            "avg_estimated_basket_cost": _average(rows, "estimated_basket_cost"),
            "avg_price_per_1000_kcal": _average(rows, "price_per_1000_kcal"),
            "avg_price_per_100g_protein": _average(rows, "price_per_100g_protein"),
            "avg_unique_ingredient_count": _average(rows, "unique_ingredient_count"),
            "avg_role_diversity_count": _average(rows, "role_diversity_count"),
            "avg_warning_count": _average(rows, "warning_count"),
            "avg_scorer_score": _average(rows, "scorer_score"),
            "avg_generation_time_ms": _average(rows, "generation_time_ms"),
            "model_selected_rate": _average(rows, "model_selected"),
        }
        for system_id, rows in sorted(grouped.items())
    }

    baseline_rows = {str(row["scenario_id"]): row for row in grouped.get("heuristic_only", [])}
    comparison = {}
    for system_id, rows in grouped.items():
        if system_id == "heuristic_only":
            continue
        matched = [(baseline_rows[str(row["scenario_id"])], row) for row in rows if str(row["scenario_id"]) in baseline_rows]
        if not matched:
            continue
        scorer_improvements = [float(row["scorer_score"]) - float(base["scorer_score"]) for base, row in matched]
        protein_gap_improvements = [float(base["protein_abs_gap_g"]) - float(row["protein_abs_gap_g"]) for base, row in matched]
        calorie_gap_improvements = [float(base["calorie_abs_gap_kcal"]) - float(row["calorie_abs_gap_kcal"]) for base, row in matched]
        cost_deltas = [float(row["estimated_basket_cost"]) - float(base["estimated_basket_cost"]) for base, row in matched]
        comparison[system_id] = {
            "scenario_count": len(matched),
            "fraction_beating_baseline_by_scorer": round(sum(1 for value in scorer_improvements if value > 0) / len(matched), 6),
            "average_scorer_improvement": round(sum(scorer_improvements) / len(matched), 6),
            "average_protein_gap_improvement_g": round(sum(protein_gap_improvements) / len(matched), 6),
            "average_calorie_gap_improvement_kcal": round(sum(calorie_gap_improvements) / len(matched), 6),
            "average_cost_delta": round(sum(cost_deltas) / len(matched), 6),
            "model_candidate_win_rate": round(sum(1 for _base, row in matched if str(row["selected_candidate_source"]) in {"model", "repaired_model", "hybrid"}) / len(matched), 6),
        }
    return {
        "systems": systems_summary,
        "baseline_comparison": comparison,
    }


def _write_markdown(summary: dict[str, object], output_path: Path) -> None:
    lines = [
        "# Hybrid Planner Evaluation",
        "",
        "## System Summary",
        "",
        "| system | scenarios | avg scorer | avg protein gap g | avg calorie gap kcal | avg cost | avg time ms | model selected rate |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for system_id, metrics in summary["systems"].items():
        lines.append(
            "| "
            + f"{system_id} | {metrics['scenario_count']} | {metrics['avg_scorer_score']} | {metrics['avg_protein_abs_gap_g']} | "
            + f"{metrics['avg_calorie_abs_gap_kcal']} | {metrics['avg_estimated_basket_cost']} | {metrics['avg_generation_time_ms']} | {metrics['model_selected_rate']} |"
        )

    if summary["baseline_comparison"]:
        lines.extend(["", "## Baseline Comparison", "", "| system | beat rate | avg scorer delta | avg protein gap delta g | avg calorie gap delta kcal | avg cost delta | model candidate win rate |", "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"])
        for system_id, metrics in summary["baseline_comparison"].items():
            lines.append(
                "| "
                + f"{system_id} | {metrics['fraction_beating_baseline_by_scorer']} | {metrics['average_scorer_improvement']} | "
                + f"{metrics['average_protein_gap_improvement_g']} | {metrics['average_calorie_gap_improvement_kcal']} | "
                + f"{metrics['average_cost_delta']} | {metrics['model_candidate_win_rate']} |"
            )

    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    scenarios = _scenario_rows(args.scenario_split, args.scenario_limit)
    systems = _system_specs(args)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    results: list[dict[str, object]] = []
    with duckdb.connect(args.db_path, read_only=True) as con:
        for scenario in scenarios:
            for system in systems:
                started_at = perf_counter()
                response = recommend_generic_foods(
                    con,
                    protein_target_g=float(scenario["protein_target_g"]),
                    calorie_target_kcal=float(scenario["calorie_target_kcal"]),
                    preferences=dict(scenario["preferences"]),
                    nutrition_targets=dict(scenario["nutrition_targets"]),
                    pantry_items=list(scenario["pantry_items"]),
                    days=int(scenario["days"]),
                    shopping_mode=str(scenario["shopping_mode"]),
                    price_context=dict(scenario["price_context"]),
                    stores=list(scenario["stores"]),
                    scorer_config={
                        "candidate_count": args.candidate_count,
                        "scorer_model_path": str(args.scorer_model_path),
                        "debug": True,
                    },
                    candidate_generation_config=dict(system["candidate_generation_config"]),
                )
                duration_ms = (perf_counter() - started_at) * 1000.0
                results.append(
                    _scenario_result(
                        response,
                        system_id=str(system["system_id"]),
                        label=str(system["label"]),
                        scenario=scenario,
                        generation_time_ms=duration_ms,
                    )
                )

    detailed_path = args.output_dir / "hybrid_planner_evaluation_detailed.csv"
    with detailed_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(results[0].keys()))
        writer.writeheader()
        writer.writerows(results)

    summary = _summary_payload(results)
    summary_path = args.output_dir / "hybrid_planner_evaluation_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")

    markdown_path = args.output_dir / "hybrid_planner_evaluation_summary.md"
    _write_markdown(summary, markdown_path)

    print(f"detailed_path={detailed_path}")
    print(f"summary_path={summary_path}")
    print(f"markdown_path={markdown_path}")
    print(f"systems={list(summary['systems'].keys())}")
    print(f"baseline_comparison={summary['baseline_comparison']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
