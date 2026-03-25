# Module 2 One-Pager

## Objectives
Build a local-only, reproducible, explainable hybrid grocery-planning model that expands candidate generation beyond heuristics while preserving the deterministic planner as a baseline and fallback.

## Models Used
- Learned candidate generator: Random Forest food-role inclusion model trained on locally generated planner scenarios.
- Plan scorer: fair reranking model that compares heuristic and learned candidates under one scoring layer.
- Deterministic planner: preserved as the heuristic baseline and runtime fallback.

## How They Function
The learned generator scores `(scenario, food, role)` combinations and proposes extra basket seeds. Those seeds are materialized into baskets, fused with heuristic candidates, deduplicated, and ranked by the fair scorer. The deterministic planner remains in the loop for structure, realism, and backward compatibility.

## Why These Models Were Chosen
This design fit the repo’s local DuckDB-based architecture, preserved explainability, and created a real training/tuning/evaluation pipeline without replacing the deterministic planner. Route B was preferable to a full replacement because it improved search diversity while retaining a stable baseline path.

## Alternatives Considered
- Logistic Regression candidate generator
- Random Forest candidate generator
- HistGradientBoosting candidate generator

Random Forest was selected because it best reconstructed strong heuristic seed baskets and remained presentation-friendly and interpretable.

## Tuning / Hyperparameters
Candidate-generator tuning covered 78 total configurations. The selected Random Forest used `n_estimators=200`, `max_depth=None`, `max_features=0.5`, `min_samples_leaf=2`, and `random_seed=42`. The scorer was also retrained with fair-alternative features so it would not over-prefer heuristic-looking baskets.

## Performance Metrics
- Final frozen algorithm: `route_b_generalized_v5_main`
- Main preset score improvements: `4` of 5
- Main preset model/hybrid wins: `4` of 5
- Materially different final baskets: `4` of 5
- Robustness sweep: `16` improvements across `30` scenarios

## Ablation Findings
The generalized components matter. Removing structured complementarity drops the final system from 4 model wins to 3. Removing structured materialization also drops it from 4 to 3. The full generalized Route B keeps all 4 current model wins.

## Limitations
- `fat_loss` remains heuristic under the final generalized system.
- Remaining gap to the best materially different model candidate: `0.441382`
- The learned generator still inherits some bias from heuristic-derived labels.
- Runtime is still approximate with respect to real store inventory.

## Use This Version
- Cite algorithm version: `route_b_generalized_v5_main`
- Final preset comparison: `/Users/yinghansun/Desktop/diet-optimization-main/artifacts/plan_scorer/route_b_generalized_v5/preset_comparison_summary.json`
- Regenerate with: `make compare-preset-model-participation-final`
