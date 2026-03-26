# Hybrid Planner Final Summary

## Main Algorithm
- Version: `hybrid_planner_generalized_v5_main`
- Label: Generalized Hybrid Planner Main
- Scorer artifact: `/Users/yinghansun/Desktop/diet-optimization-main/artifacts/plan_scorer/hybrid_planner_fair_v1/plan_candidate_scorer.joblib`
- Candidate-generator artifact: `/Users/yinghansun/Desktop/diet-optimization-main/artifacts/candidate_generator/candidate_generator_best.joblib`

## Use This Version
- Cite algorithm version: `hybrid_planner_generalized_v5_main`
- Final preset comparison artifact: `/Users/yinghansun/Desktop/diet-optimization-main/artifacts/plan_scorer/hybrid_planner_generalized_v5/preset_comparison_summary.json`
- Final ablation artifact: `/Users/yinghansun/Desktop/diet-optimization-main/artifacts/plan_scorer/hybrid_planner_generalized_v5/ablation/hybrid_planner_ablation_summary.json`
- Final robustness artifact: `/Users/yinghansun/Desktop/diet-optimization-main/artifacts/plan_scorer/hybrid_planner_generalized_v5/robustness/hybrid_planner_robustness_summary.json`
- Regenerate preset comparison with: `make compare-preset-model-participation-final`

## Baseline vs Final
- Hybrid score improved on `4` of `5` presets.
- Model or hybrid candidates won on `4` presets.
- Selected source changed on `4` presets.
- Final materially different baskets appeared on `4` presets.
- Current model-win presets: muscle_gain, maintenance, high_protein_vegetarian, budget_friendly_healthy
- Remaining heuristic presets: fat_loss

## Ablation Takeaways
- Removing structured complementarity kept `3` model wins and `3` score improvements.
- Removing structured materialization kept `3` model wins and `3` score improvements.
- The full generalized hybrid planner kept `4` model wins with `4` improved presets.

## Robustness
- Evaluated `30` local scenario variants.
- The hybrid planner pipeline beat heuristic+scorer on `16` cases.
- Model or hybrid candidates won on `16` cases.
- Average winner-source stability ratio: `0.733334`
- Brittle cases detected: `0`

## Why Fat Loss Still Heuristic
- Selected source: `heuristic`
- Remaining score gap to the best materially different model candidate: `0.441382`
- Diagnosis: Model candidates were generated but heuristic still won by 0.441 scorer points. Lower scorer score by 0.441. More repetitive basket structure.
- Current limitation: Materially-different model candidates survived, but the strongest one still lost due to poor produce choice. It lost mainly on repetition penalty.

## Final Positioning
- This is the frozen final hybrid planner configuration for presentation: one generalized hybrid planner, one fair scorer artifact, one selected candidate-generator artifact, and evaluation evidence that shows which shared components matter.
