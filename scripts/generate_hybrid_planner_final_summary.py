#!/usr/bin/env -S uv run --extra ml python
"""Generate presentation-ready summary artifacts for the frozen hybrid planner pipeline."""

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
        help="Directory containing the final preset comparison report and where summary artifacts should be written.",
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
    return parser.parse_args()


def _load_json(path: Path) -> dict[str, object]:
    if not path.exists():
        raise FileNotFoundError(f"Missing required artifact: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    preset_summary = _load_json(args.output_dir / "preset_comparison_summary.json")
    ablation_summary = _load_json(args.ablation_dir / "hybrid_planner_ablation_summary.json")
    robustness_summary = _load_json(args.robustness_dir / "hybrid_planner_robustness_summary.json")

    config_json_path = args.output_dir / "hybrid_planner_main_algorithm_config.json"
    summary_json_path = args.output_dir / "hybrid_planner_final_summary.json"
    summary_csv_path = args.output_dir / "hybrid_planner_final_summary.csv"
    summary_md_path = args.output_dir / "hybrid_planner_final_summary.md"

    config_payload = hybrid_pipeline_final.final_runtime_metadata()
    config_payload["final_output_dir"] = str(hybrid_pipeline_final.FINAL_OUTPUT_DIR)
    config_json_path.write_text(json.dumps(config_payload, indent=2), encoding="utf-8")

    ablation_by_system = {
        str(entry["system_id"]): entry
        for entry in list(ablation_summary.get("systems") or [])
        if isinstance(entry, dict)
    }
    full_ablation = dict(ablation_by_system.get("hybrid_planner_generalized_main") or {})
    no_complementarity = dict(ablation_by_system.get("hybrid_planner_no_structured_complementarity") or {})
    no_materialization = dict(ablation_by_system.get("hybrid_planner_no_structured_materialization") or {})
    heuristic_scorer = dict(ablation_by_system.get("heuristic_scorer_only") or {})

    fat_loss_explanation = dict(preset_summary.get("why_fat_loss_still_heuristic") or {})
    current_model_wins = list(preset_summary.get("current_model_win_preset_ids") or [])
    remaining_heuristic = list(preset_summary.get("remaining_heuristic_preset_ids") or [])
    official_artifacts = {
        "main_algorithm_config_json": str(config_json_path),
        "preset_comparison_json": str(args.output_dir / "preset_comparison_summary.json"),
        "ablation_json": str(args.ablation_dir / "hybrid_planner_ablation_summary.json"),
        "robustness_json": str(args.robustness_dir / "hybrid_planner_robustness_summary.json"),
        "final_summary_json": str(summary_json_path),
        "final_summary_md": str(summary_md_path),
    }
    commands = {
        "preset_comparison": "make compare-preset-model-participation-final",
        "ablation": "make hybrid-planner-ablation",
        "robustness": "make hybrid-planner-robustness",
        "final_summary": "make hybrid-planner-final-summary",
    }

    summary_payload = {
        "main_algorithm": hybrid_pipeline_final.final_runtime_metadata(),
        "official_artifacts": official_artifacts,
        "regeneration_commands": commands,
        "baseline_vs_final": {
            "hybrid_score_improved_preset_count": int(preset_summary.get("hybrid_score_improved_preset_count") or 0),
            "model_selected_preset_count": int(preset_summary.get("model_selected_preset_count") or 0),
            "selected_candidate_source_changed_preset_count": int(
                preset_summary.get("selected_candidate_source_changed_preset_count") or 0
            ),
            "materially_different_preset_count": int(preset_summary.get("materially_different_preset_count") or 0),
            "current_model_win_preset_ids": current_model_wins,
            "remaining_heuristic_preset_ids": remaining_heuristic,
        },
        "ablation": {
            "heuristic_scorer_only": heuristic_scorer,
            "hybrid_planner_no_structured_complementarity": no_complementarity,
            "hybrid_planner_no_structured_materialization": no_materialization,
            "hybrid_planner_generalized_main": full_ablation,
        },
        "robustness": {
            "scenario_count": int(robustness_summary.get("scenario_count") or 0),
            "score_improved_case_count": int(robustness_summary.get("score_improved_case_count") or 0),
            "model_selected_case_count": int(robustness_summary.get("model_selected_case_count") or 0),
            "selected_candidate_source_changed_case_count": int(
                robustness_summary.get("selected_candidate_source_changed_case_count") or 0
            ),
            "materially_different_case_count": int(robustness_summary.get("materially_different_case_count") or 0),
            "average_score_delta_vs_heuristic": float(robustness_summary.get("average_score_delta_vs_heuristic") or 0.0),
            "average_winner_source_stability_ratio": float(
                robustness_summary.get("average_winner_source_stability_ratio") or 0.0
            ),
            "brittle_case_count": int(robustness_summary.get("brittle_case_count") or 0),
        },
        "remaining_limitation": {
            "fat_loss": fat_loss_explanation,
            "future_principled_work": [
                "Richer learned pair and set proposals for low-calorie, high-satiety basket alternatives.",
                "Additional training scenarios that better cover strong fat-loss produce and carb-complementarity patterns.",
                "Potentially learning seed-level complementarity directly instead of inferring it from food-role marginals.",
            ],
        },
        "why_this_is_the_final_algorithm": [
            "The runtime now uses one frozen generalized hybrid planner configuration rather than accumulating more preset-specific fixes.",
            "Candidate generation is driven by shared structured terms such as complementarity, novelty, practicality, and nutrient support.",
            "Model materialization uses shared seed-preservation and allocation rules instead of preset-only correction layers.",
            "The fair scorer artifact remains in place, so materially different but valid alternatives are still rankable.",
        ],
    }
    summary_json_path.write_text(json.dumps(summary_payload, indent=2), encoding="utf-8")

    csv_row = {
        "algorithm_version": hybrid_pipeline_final.FINAL_ALGORITHM_VERSION,
        "hybrid_score_improved_preset_count": int(preset_summary.get("hybrid_score_improved_preset_count") or 0),
        "model_selected_preset_count": int(preset_summary.get("model_selected_preset_count") or 0),
        "selected_candidate_source_changed_preset_count": int(
            preset_summary.get("selected_candidate_source_changed_preset_count") or 0
        ),
        "materially_different_preset_count": int(preset_summary.get("materially_different_preset_count") or 0),
        "robustness_scenario_count": int(robustness_summary.get("scenario_count") or 0),
        "robustness_score_improved_case_count": int(robustness_summary.get("score_improved_case_count") or 0),
        "robustness_model_selected_case_count": int(robustness_summary.get("model_selected_case_count") or 0),
        "robustness_brittle_case_count": int(robustness_summary.get("brittle_case_count") or 0),
        "fat_loss_selected_source": str(fat_loss_explanation.get("selected_source") or ""),
        "fat_loss_score_gap_to_best_materially_different_model": fat_loss_explanation.get(
            "score_gap_to_best_materially_different_model"
        ),
        "current_model_win_preset_ids": "|".join(current_model_wins),
        "remaining_heuristic_preset_ids": "|".join(remaining_heuristic),
    }
    with summary_csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(csv_row.keys()))
        writer.writeheader()
        writer.writerow(csv_row)

    md_lines = [
        "# Hybrid Planner Final Summary",
        "",
        "## Main Algorithm",
        f"- Version: `{hybrid_pipeline_final.FINAL_ALGORITHM_VERSION}`",
        f"- Label: {hybrid_pipeline_final.FINAL_ALGORITHM_LABEL}",
        f"- Scorer artifact: `{hybrid_pipeline_final.FINAL_SCORER_MODEL_PATH}`",
        f"- Candidate-generator artifact: `{hybrid_pipeline_final.FINAL_CANDIDATE_GENERATOR_MODEL_PATH}`",
        "",
        "## Use This Version",
        f"- Cite algorithm version: `{hybrid_pipeline_final.FINAL_ALGORITHM_VERSION}`",
        f"- Final preset comparison artifact: `{official_artifacts['preset_comparison_json']}`",
        f"- Final ablation artifact: `{official_artifacts['ablation_json']}`",
        f"- Final robustness artifact: `{official_artifacts['robustness_json']}`",
        f"- Regenerate preset comparison with: `{commands['preset_comparison']}`",
        "",
        "## Baseline vs Final",
        f"- Hybrid score improved on `{preset_summary.get('hybrid_score_improved_preset_count', 0)}` of `{preset_summary.get('preset_count', 0)}` presets.",
        f"- Model or hybrid candidates won on `{preset_summary.get('model_selected_preset_count', 0)}` presets.",
        f"- Selected source changed on `{preset_summary.get('selected_candidate_source_changed_preset_count', 0)}` presets.",
        f"- Final materially different baskets appeared on `{preset_summary.get('materially_different_preset_count', 0)}` presets.",
        f"- Current model-win presets: {', '.join(current_model_wins) if current_model_wins else 'none'}",
        f"- Remaining heuristic presets: {', '.join(remaining_heuristic) if remaining_heuristic else 'none'}",
        "",
        "## Ablation Takeaways",
        f"- Removing structured complementarity kept `{no_complementarity.get('model_selected_preset_count', 0)}` model wins and `{no_complementarity.get('hybrid_score_improved_preset_count', 0)}` score improvements.",
        f"- Removing structured materialization kept `{no_materialization.get('model_selected_preset_count', 0)}` model wins and `{no_materialization.get('hybrid_score_improved_preset_count', 0)}` score improvements.",
        f"- The full generalized hybrid planner kept `{full_ablation.get('model_selected_preset_count', 0)}` model wins with `{full_ablation.get('hybrid_score_improved_preset_count', 0)}` improved presets.",
        "",
        "## Robustness",
        f"- Evaluated `{robustness_summary.get('scenario_count', 0)}` local scenario variants.",
        f"- The hybrid planner pipeline beat heuristic+scorer on `{robustness_summary.get('score_improved_case_count', 0)}` cases.",
        f"- Model or hybrid candidates won on `{robustness_summary.get('model_selected_case_count', 0)}` cases.",
        f"- Average winner-source stability ratio: `{robustness_summary.get('average_winner_source_stability_ratio', 0.0)}`",
        f"- Brittle cases detected: `{robustness_summary.get('brittle_case_count', 0)}`",
        "",
        "## Why Fat Loss Still Heuristic",
        f"- Selected source: `{fat_loss_explanation.get('selected_source', '')}`",
        f"- Remaining score gap to the best materially different model candidate: `{fat_loss_explanation.get('score_gap_to_best_materially_different_model', '')}`",
        f"- Diagnosis: {fat_loss_explanation.get('diagnosis_text', '')}",
        f"- Current limitation: {fat_loss_explanation.get('why_no_model_win_yet', '')}",
        "",
        "## Final Positioning",
        "- This is the frozen final hybrid planner configuration for presentation: one generalized hybrid planner, one fair scorer artifact, one selected candidate-generator artifact, and evaluation evidence that shows which shared components matter.",
    ]
    summary_md_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    print(f"wrote_config_json={config_json_path}")
    print(f"wrote_summary_json={summary_json_path}")
    print(f"wrote_summary_csv={summary_csv_path}")
    print(f"wrote_summary_md={summary_md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
