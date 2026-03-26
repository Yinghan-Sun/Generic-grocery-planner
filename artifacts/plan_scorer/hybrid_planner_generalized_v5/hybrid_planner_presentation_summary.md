# Hybrid Planner Presentation Summary

Algorithm to present: `hybrid_planner_generalized_v5_main`

## What It Does
- Preserves the deterministic grocery planner as the baseline and fallback.
- Adds a learned local candidate generator that proposes extra structured basket seeds.
- Uses the fair plan scorer to rank heuristic and model candidates together.
- Runs automatically as a one-click flow in the standard UI, without exposing model backends or debug toggles to normal users.

## Baseline vs Final
- Hybrid score improved on `4` of 5 main presets.
- Model or hybrid candidates won on `4` presets.
- Selected source changed on `4` presets.
- Materially different final baskets appeared on `4` presets.

## Preset-Level Result
- Model wins: muscle_gain, maintenance, high_protein_vegetarian, budget_friendly_healthy
- Remaining heuristic preset: fat_loss

## Ablation Highlights
- Removing structured complementarity reduced model wins from 4 to 3.
- Removing structured materialization reduced model wins from 4 to 3.
- The full generalized hybrid planner kept all 4 current model wins.

## Robustness Highlights
- Evaluated `30` local scenario variants.
- The hybrid planner pipeline improved scorer score on `16` cases.
- Model or hybrid candidates won on `16` cases.
- No brittle cases were detected: `0`.

## Remaining Limitation
- `fat_loss` still prefers the heuristic winner.
- Remaining gap to the best materially different model candidate: `0.441382`.
- Current explanation: Materially-different model candidates survived, but the strongest one still lost due to poor produce choice. It lost mainly on repetition penalty.

## Use This Version
- Cite version: `hybrid_planner_generalized_v5_main`
- Frozen scorer artifact: `/Users/yinghansun/Desktop/diet-optimization-main/artifacts/plan_scorer/hybrid_planner_fair_v1/plan_candidate_scorer.joblib`
- Frozen candidate-generator artifact: `/Users/yinghansun/Desktop/diet-optimization-main/artifacts/candidate_generator/candidate_generator_best.joblib`
- Final preset comparison artifact: `/Users/yinghansun/Desktop/diet-optimization-main/artifacts/plan_scorer/hybrid_planner_generalized_v5/preset_comparison_summary.json`
- Regenerate preset comparison with: `make compare-preset-model-participation-final`
