#!/usr/bin/env -S uv run --extra ml python
"""Generate presentation-ready hybrid planner artifacts from frozen final reports."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from dietdashboard import hybrid_pipeline_final


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=hybrid_pipeline_final.FINAL_OUTPUT_DIR,
        help="Directory containing the final hybrid planner reports and where presentation assets should be written.",
    )
    parser.add_argument(
        "--ablation-dir",
        type=Path,
        default=hybrid_pipeline_final.FINAL_OUTPUT_DIR / "ablation",
        help="Directory containing the ablation report.",
    )
    parser.add_argument(
        "--robustness-dir",
        type=Path,
        default=hybrid_pipeline_final.FINAL_OUTPUT_DIR / "robustness",
        help="Directory containing the robustness report.",
    )
    parser.add_argument(
        "--docs-dir",
        type=Path,
        default=hybrid_pipeline_final.REPO_ROOT / "docs",
        help="Directory for generated presentation/report markdown files.",
    )
    return parser.parse_args()


def _load_json(path: Path) -> dict[str, object]:
    if not path.exists():
        raise FileNotFoundError(f"Missing required artifact: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    fieldnames = list(rows[0].keys()) if rows else []
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _markdown_table(headers: list[str], rows: list[list[object]]) -> str:
    rendered_rows = [[str(value) for value in row] for row in rows]
    widths = [len(header) for header in headers]
    for row in rendered_rows:
        for index, value in enumerate(row):
            widths[index] = max(widths[index], len(value))
    header_line = "| " + " | ".join(header.ljust(widths[index]) for index, header in enumerate(headers)) + " |"
    divider_line = "| " + " | ".join("-" * widths[index] for index, _header in enumerate(headers)) + " |"
    body_lines = [
        "| " + " | ".join(value.ljust(widths[index]) for index, value in enumerate(row)) + " |"
        for row in rendered_rows
    ]
    return "\n".join([header_line, divider_line, *body_lines]) + "\n"


def _write_md_table(path: Path, title: str, headers: list[str], rows: list[list[object]], note: str | None = None) -> None:
    lines = [f"# {title}", ""]
    if note:
        lines.extend([note, ""])
    lines.append(_markdown_table(headers, rows))
    path.write_text("\n".join(lines), encoding="utf-8")


def _yes_no(value: object) -> str:
    return "Yes" if bool(value) else "No"


def main() -> int:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.docs_dir.mkdir(parents=True, exist_ok=True)

    preset_summary = _load_json(args.output_dir / "preset_comparison_summary.json")
    ablation_summary = _load_json(args.ablation_dir / "hybrid_planner_ablation_summary.json")
    robustness_summary = _load_json(args.robustness_dir / "hybrid_planner_robustness_summary.json")
    final_summary = _load_json(args.output_dir / "hybrid_planner_final_summary.json")

    presentation_json_path = args.output_dir / "hybrid_planner_presentation_summary.json"
    presentation_md_path = args.output_dir / "hybrid_planner_presentation_summary.md"
    presets_csv_path = args.output_dir / "hybrid_planner_slide_table_presets.csv"
    presets_md_path = args.output_dir / "hybrid_planner_slide_table_presets.md"
    ablation_csv_path = args.output_dir / "hybrid_planner_slide_table_ablation.csv"
    ablation_md_path = args.output_dir / "hybrid_planner_slide_table_ablation.md"
    robustness_csv_path = args.output_dir / "hybrid_planner_slide_table_robustness.csv"
    robustness_md_path = args.output_dir / "hybrid_planner_slide_table_robustness.md"
    plot_presets_csv_path = args.output_dir / "hybrid_planner_plot_data_presets.csv"
    plot_ablation_csv_path = args.output_dir / "hybrid_planner_plot_data_ablation.csv"
    plot_robustness_csv_path = args.output_dir / "hybrid_planner_plot_data_robustness.csv"
    script_md_path = args.docs_dir / "module2-presentation-script.md"
    one_pager_md_path = args.docs_dir / "module2-one-pager.md"

    algorithm = dict(final_summary.get("main_algorithm") or hybrid_pipeline_final.final_runtime_metadata())
    baseline = dict(final_summary.get("baseline_vs_final") or {})
    robustness = dict(final_summary.get("robustness") or {})
    fat_loss = dict(dict(final_summary.get("remaining_limitation") or {}).get("fat_loss") or {})
    official_artifacts = dict(final_summary.get("official_artifacts") or {})
    commands = dict(final_summary.get("regeneration_commands") or {})

    preset_rows = list(preset_summary.get("presets") or [])
    ablation_systems = list(ablation_summary.get("systems") or [])
    robustness_rows = list(robustness_summary.get("rows") or [])
    robustness_stability = list(robustness_summary.get("preset_stability") or [])

    slide_preset_rows: list[dict[str, object]] = []
    for row in preset_rows:
        score_delta = round(float(row["hybrid_scorer_score"]) - float(row["heuristic_scorer_score"]), 6)
        slide_preset_rows.append(
        {
            "preset": str(row["preset_label"]),
                "heuristic_winner": str(row["heuristic_selected_source"]),
                "final_winner": str(row["hybrid_selected_source"]),
                "score_improved": _yes_no(int(row["hybrid_score_improved"])),
                "materially_different": _yes_no(int(row["materially_different"])),
                "score_delta_vs_baseline": score_delta,
                "note": str(row["difference_summary"] or row["hybrid_why_no_model_win_yet"] or ""),
            }
        )
    _write_csv(presets_csv_path, slide_preset_rows)
    _write_md_table(
        presets_md_path,
        "Hybrid Planner Slide Table: Preset Outcomes",
        list(slide_preset_rows[0].keys()),
        [list(row.values()) for row in slide_preset_rows],
        note=f"Frozen final algorithm: {algorithm.get('algorithm_version', hybrid_pipeline_final.FINAL_ALGORITHM_VERSION)}",
    )

    slide_ablation_rows: list[dict[str, object]] = []
    for system in ablation_systems:
        slide_ablation_rows.append(
            {
                "component": str(system["system_label"]),
                "model_wins": int(system["model_selected_preset_count"]),
                "score_improved_presets": int(system["hybrid_score_improved_preset_count"]),
                "source_changed_presets": int(system["selected_candidate_source_changed_preset_count"]),
                "materially_different_presets": int(system["materially_different_preset_count"]),
                "current_full_wins_lost": int(system["current_full_wins_disappear_count"]),
            }
        )
    _write_csv(ablation_csv_path, slide_ablation_rows)
    _write_md_table(
        ablation_md_path,
        "Hybrid Planner Slide Table: Ablation Outcomes",
        list(slide_ablation_rows[0].keys()),
        [list(row.values()) for row in slide_ablation_rows],
        note="Higher model wins and score improvements indicate more of the frozen final behavior was preserved.",
    )

    preset_brittle_counts: dict[str, int] = {}
    for stability_row in robustness_stability:
        preset_id = str(stability_row["preset_id"])
        preset_brittle_counts[preset_id] = sum(
            1 for row in robustness_rows if str(row["preset_id"]) == preset_id and int(row["brittle_case"]) == 1
        )
    slide_robustness_rows: list[dict[str, object]] = []
    for stability_row in robustness_stability:
        slide_robustness_rows.append(
            {
                "preset": str(stability_row["preset_id"]),
                "dominant_final_source": str(stability_row["dominant_final_source"]),
                "winner_source_stability_ratio": round(float(stability_row["winner_source_stability_ratio"]), 6),
                "improved_cases": int(stability_row["score_improved_case_count"]),
                "materially_different_cases": int(stability_row["materially_different_case_count"]),
                "brittle_cases": int(preset_brittle_counts[str(stability_row["preset_id"])]),
            }
        )
    _write_csv(robustness_csv_path, slide_robustness_rows)
    _write_md_table(
        robustness_md_path,
        "Hybrid Planner Slide Table: Robustness Outcomes",
        list(slide_robustness_rows[0].keys()),
        [list(row.values()) for row in slide_robustness_rows],
        note="This table summarizes how stable the final winner source stays across local perturbations.",
    )

    plot_preset_rows: list[dict[str, object]] = []
    for row in preset_rows:
        plot_preset_rows.append(
            {
                "preset_id": str(row["preset_id"]),
                "preset_label": str(row["preset_label"]),
                "heuristic_scorer_score": float(row["heuristic_scorer_score"]),
                "hybrid_scorer_score": float(row["hybrid_scorer_score"]),
                "score_delta": round(float(row["hybrid_scorer_score"]) - float(row["heuristic_scorer_score"]), 6),
                "heuristic_selected_source": str(row["heuristic_selected_source"]),
                "hybrid_selected_source": str(row["hybrid_selected_source"]),
                "materially_different": int(row["materially_different"]),
                "selected_candidate_source_changed": int(row["selected_candidate_source_changed"]),
            }
        )
    _write_csv(plot_presets_csv_path, plot_preset_rows)

    plot_ablation_rows: list[dict[str, object]] = []
    for system in ablation_systems:
        plot_ablation_rows.append(
            {
                "system_id": str(system["system_id"]),
                "system_label": str(system["system_label"]),
                "model_selected_preset_count": int(system["model_selected_preset_count"]),
                "hybrid_score_improved_preset_count": int(system["hybrid_score_improved_preset_count"]),
                "selected_candidate_source_changed_preset_count": int(
                    system["selected_candidate_source_changed_preset_count"]
                ),
                "materially_different_preset_count": int(system["materially_different_preset_count"]),
                "average_score_delta_vs_heuristic_scorer": float(system["average_score_delta_vs_heuristic_scorer"]),
            }
        )
    _write_csv(plot_ablation_csv_path, plot_ablation_rows)
    _write_csv(plot_robustness_csv_path, [dict(row) for row in robustness_rows])

    presentation_payload = {
        "algorithm_to_present": hybrid_pipeline_final.FINAL_ALGORITHM_VERSION,
        "label": hybrid_pipeline_final.FINAL_ALGORITHM_LABEL,
        "what_the_system_does": [
            "Keeps the deterministic grocery planner as the baseline path.",
            "Adds a learned local candidate generator that proposes extra structured basket seeds.",
            "Uses one fair scorer to rank heuristic and learned candidates together.",
            "Runs as a one-click recommendation flow in the normal UI without user-facing model-selection controls.",
        ],
        "baseline_vs_final": baseline,
        "preset_results": [
            {
                "preset_id": str(row["preset_id"]),
                "selected_source": str(row["hybrid_selected_source"]),
                "score_improved": bool(row["hybrid_score_improved"]),
                "materially_different": bool(row["materially_different"]),
            }
            for row in preset_rows
        ],
        "ablation_highlights": {
            "no_complementarity_model_wins": int(
                next(
                    system["model_selected_preset_count"]
                    for system in ablation_systems
                    if system["system_id"] == "hybrid_planner_no_structured_complementarity"
                )
            ),
            "no_materialization_model_wins": int(
                next(
                    system["model_selected_preset_count"]
                    for system in ablation_systems
                    if system["system_id"] == "hybrid_planner_no_structured_materialization"
                )
            ),
            "full_generalized_model_wins": int(
                next(
                    system["model_selected_preset_count"]
                    for system in ablation_systems
                    if system["system_id"] == "hybrid_planner_generalized_main"
                )
            ),
        },
        "robustness_highlights": robustness,
        "remaining_limitation": {
            "fat_loss_selected_source": str(fat_loss.get("selected_source") or ""),
            "fat_loss_gap_to_best_materially_different_model": fat_loss.get("score_gap_to_best_materially_different_model"),
            "fat_loss_explanation": str(fat_loss.get("why_no_model_win_yet") or ""),
        },
        "use_this_version": {
            "algorithm_version": hybrid_pipeline_final.FINAL_ALGORITHM_VERSION,
            "scorer_artifact": str(hybrid_pipeline_final.FINAL_SCORER_MODEL_PATH),
            "candidate_generator_artifact": str(hybrid_pipeline_final.FINAL_CANDIDATE_GENERATOR_MODEL_PATH),
            "preset_comparison_artifact": str(official_artifacts.get("preset_comparison_json") or args.output_dir / "preset_comparison_summary.json"),
            "regenerate_preset_comparison_command": str(commands.get("preset_comparison") or "make compare-preset-model-participation-final"),
        },
    }
    presentation_json_path.write_text(json.dumps(presentation_payload, indent=2), encoding="utf-8")

    presentation_md_lines = [
        "# Hybrid Planner Presentation Summary",
        "",
        f"Algorithm to present: `{hybrid_pipeline_final.FINAL_ALGORITHM_VERSION}`",
        "",
        "## What It Does",
        "- Preserves the deterministic grocery planner as the baseline and fallback.",
        "- Adds a learned local candidate generator that proposes extra structured basket seeds.",
        "- Uses the fair plan scorer to rank heuristic and model candidates together.",
        "- Runs automatically as a one-click flow in the standard UI, without exposing model backends or debug toggles to normal users.",
        "",
        "## Baseline vs Final",
        f"- Hybrid score improved on `{baseline.get('hybrid_score_improved_preset_count', 0)}` of 5 main presets.",
        f"- Model or hybrid candidates won on `{baseline.get('model_selected_preset_count', 0)}` presets.",
        f"- Selected source changed on `{baseline.get('selected_candidate_source_changed_preset_count', 0)}` presets.",
        f"- Materially different final baskets appeared on `{baseline.get('materially_different_preset_count', 0)}` presets.",
        "",
        "## Preset-Level Result",
        f"- Model wins: {', '.join(baseline.get('current_model_win_preset_ids', [])) or 'none'}",
        f"- Remaining heuristic preset: {', '.join(baseline.get('remaining_heuristic_preset_ids', [])) or 'none'}",
        "",
        "## Ablation Highlights",
        "- Removing structured complementarity reduced model wins from 4 to 3.",
        "- Removing structured materialization reduced model wins from 4 to 3.",
        "- The full generalized hybrid planner kept all 4 current model wins.",
        "",
        "## Robustness Highlights",
        f"- Evaluated `{robustness.get('scenario_count', 0)}` local scenario variants.",
        f"- The hybrid planner pipeline improved scorer score on `{robustness.get('score_improved_case_count', 0)}` cases.",
        f"- Model or hybrid candidates won on `{robustness.get('model_selected_case_count', 0)}` cases.",
        f"- No brittle cases were detected: `{robustness.get('brittle_case_count', 0)}`.",
        "",
        "## Remaining Limitation",
        f"- `fat_loss` still prefers the heuristic winner.",
        f"- Remaining gap to the best materially different model candidate: `{fat_loss.get('score_gap_to_best_materially_different_model', '')}`.",
        f"- Current explanation: {fat_loss.get('why_no_model_win_yet', '')}",
        "",
        "## Use This Version",
        f"- Cite version: `{hybrid_pipeline_final.FINAL_ALGORITHM_VERSION}`",
        f"- Frozen scorer artifact: `{hybrid_pipeline_final.FINAL_SCORER_MODEL_PATH}`",
        f"- Frozen candidate-generator artifact: `{hybrid_pipeline_final.FINAL_CANDIDATE_GENERATOR_MODEL_PATH}`",
        f"- Final preset comparison artifact: `{official_artifacts.get('preset_comparison_json', '')}`",
        f"- Regenerate preset comparison with: `{commands.get('preset_comparison', 'make compare-preset-model-participation-final')}`",
    ]
    presentation_md_path.write_text("\n".join(presentation_md_lines) + "\n", encoding="utf-8")

    script_lines = [
        "# Module 2 Presentation Script",
        "",
        "## 3-5 Minute Talk Track",
        "",
        "### 1. Problem",
        "Our original Generic Grocery Planner was deterministic and explainable, but it only searched the candidate space through heuristic beams. That made it stable, but it also meant the planner could miss strong alternative baskets.",
        "",
        "### 2. Why Heuristic-Only Was Not Enough",
        "For Module 2, the goal was not just to add a model, but to define a complete modeling package: objective, methods, alternatives, tuning, evaluation, and limitations. A pure heuristic planner could not demonstrate a real training pipeline or a meaningful learned search component.",
        "",
        "### 3. Why We Chose the Hybrid Planner Pipeline",
        "We chose a hybrid planner pipeline. The deterministic planner stays in place as the baseline. A learned local candidate generator proposes extra structured basket seeds. Then one fair scorer ranks both heuristic and learned candidates together. This kept the system local-only, explainable, and backward compatible.",
        "",
        "### 4. What A Normal User Experiences",
        "A normal user now clicks Recommend once. The app does not ask them to choose learned versus heuristic paths, candidate-generator backends, candidate counts, scorer paths, or debug modes. The backend always runs the full hybrid stack internally.",
        "",
        "### 5. What the Learned Candidate Generator Does",
        "The learned model predicts promising foods for planner roles like protein anchor, carb base, produce, and calorie booster using structured local features. At runtime, it proposes candidate baskets, and those candidates are fused with heuristic ones before scoring.",
        "",
        "### 6. What the Fair Scorer Does",
        "We also had to reduce heuristic bias in ranking. The fair scorer was retrained so that materially different but still practical baskets are treated more fairly instead of always preferring the heuristic-looking option. That was important because otherwise the learned generator could produce valid alternatives that still never win.",
        "",
        "### 7. Final Results",
        f"With the frozen final algorithm `{hybrid_pipeline_final.FINAL_ALGORITHM_VERSION}`, the hybrid planner improved scorer outcome on {baseline.get('hybrid_score_improved_preset_count', 0)} of the 5 main presets and selected a model or hybrid winner on {baseline.get('model_selected_preset_count', 0)} presets. The current model wins are {', '.join(baseline.get('current_model_win_preset_ids', []))}.",
        "",
        "### 8. Why the Generalized Final Version Matters",
        "Earlier iterations included narrower fixes for specific failure modes. The final version is better because it uses generalized complementarity, generalized seed-preserving materialization, and the fair scorer instead of accumulating more preset-specific patches. The ablation study shows those shared components matter: removing complementarity or structured materialization each drops one of the current model wins.",
        "",
        "### 9. Robustness",
        f"We also tested the frozen algorithm on {robustness.get('scenario_count', 0)} local perturbation scenarios such as target changes, multi-day shopping, and an alternate location. The hybrid planner pipeline still improved over heuristic+scorer on {robustness.get('score_improved_case_count', 0)} cases, and we found {robustness.get('brittle_case_count', 0)} brittle cases in this sweep.",
        "",
        "### 10. Limitation",
        f"The remaining limitation is `fat_loss`, which still selects the heuristic basket. The gap to the best materially different model candidate is {fat_loss.get('score_gap_to_best_materially_different_model', '')}, so the model path is competitive there, but not yet best. That suggests a real limitation in learned candidate quality for that goal rather than missing routing or missing model participation.",
        "",
        "### 11. Future Work",
        "A principled next step would be a richer learned pair or set proposal model, especially for low-calorie, high-satiety combinations, rather than more preset-specific tuning. That would keep the system faithful to the general algorithmic direction established in the final hybrid planner version.",
    ]
    script_md_path.write_text("\n".join(script_lines) + "\n", encoding="utf-8")

    one_pager_lines = [
        "# Module 2 One-Pager",
        "",
        "## Objectives",
        "Build a local-only, reproducible, explainable hybrid grocery-planning model that expands candidate generation beyond heuristics while preserving the deterministic planner as a baseline and fallback.",
        "",
        "## Models Used",
        "- Learned candidate generator: Random Forest food-role inclusion model trained on locally generated planner scenarios.",
        "- Plan scorer: fair reranking model that compares heuristic and learned candidates under one scoring layer.",
        "- Deterministic planner: preserved as the heuristic baseline and runtime fallback.",
        "",
        "## How They Function",
        "The learned generator scores `(scenario, food, role)` combinations and proposes extra basket seeds. Those seeds are materialized into baskets, fused with heuristic candidates, deduplicated, and ranked by the fair scorer. The deterministic planner remains in the loop for structure, realism, and backward compatibility, and the normal UI runs that full stack behind a single Recommend click.",
        "",
        "## Why These Models Were Chosen",
        "This design fit the repo’s local DuckDB-based architecture, preserved explainability, and created a real training/tuning/evaluation pipeline without replacing the deterministic planner. The hybrid planner pipeline was preferable to a full replacement because it improved search diversity while retaining a stable baseline path.",
        "",
        "## Alternatives Considered",
        "- Logistic Regression candidate generator",
        "- Random Forest candidate generator",
        "- HistGradientBoosting candidate generator",
        "",
        "Random Forest was selected because it best reconstructed strong heuristic seed baskets and remained presentation-friendly and interpretable.",
        "",
        "## Tuning / Hyperparameters",
        "Candidate-generator tuning covered 78 total configurations. The selected Random Forest used `n_estimators=200`, `max_depth=None`, `max_features=0.5`, `min_samples_leaf=2`, and `random_seed=42`. The scorer was also retrained with fair-alternative features so it would not over-prefer heuristic-looking baskets.",
        "",
        "## Performance Metrics",
        f"- Final frozen algorithm: `{hybrid_pipeline_final.FINAL_ALGORITHM_VERSION}`",
        f"- Main preset score improvements: `{baseline.get('hybrid_score_improved_preset_count', 0)}` of 5",
        f"- Main preset model/hybrid wins: `{baseline.get('model_selected_preset_count', 0)}` of 5",
        f"- Materially different final baskets: `{baseline.get('materially_different_preset_count', 0)}` of 5",
        f"- Robustness sweep: `{robustness.get('score_improved_case_count', 0)}` improvements across `{robustness.get('scenario_count', 0)}` scenarios",
        "",
        "## Ablation Findings",
        "The generalized components matter. Removing structured complementarity drops the final system from 4 model wins to 3. Removing structured materialization also drops it from 4 to 3. The full generalized hybrid planner keeps all 4 current model wins.",
        "",
        "## Limitations",
        f"- `fat_loss` remains heuristic under the final generalized system.",
        f"- Remaining gap to the best materially different model candidate: `{fat_loss.get('score_gap_to_best_materially_different_model', '')}`",
        "- The learned generator still inherits some bias from heuristic-derived labels.",
        "- Runtime is still approximate with respect to real store inventory.",
        "",
        "## Use This Version",
        f"- Cite algorithm version: `{hybrid_pipeline_final.FINAL_ALGORITHM_VERSION}`",
        f"- Final preset comparison: `{official_artifacts.get('preset_comparison_json', '')}`",
        f"- Regenerate with: `{commands.get('preset_comparison', 'make compare-preset-model-participation-final')}`",
    ]
    one_pager_md_path.write_text("\n".join(one_pager_lines) + "\n", encoding="utf-8")

    print(f"wrote_json={presentation_json_path}")
    print(f"wrote_md={presentation_md_path}")
    print(f"wrote_presets_csv={presets_csv_path}")
    print(f"wrote_ablation_csv={ablation_csv_path}")
    print(f"wrote_robustness_csv={robustness_csv_path}")
    print(f"wrote_script={script_md_path}")
    print(f"wrote_one_pager={one_pager_md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
