# Module 2 Model Summary

## Objective

The Module 2 upgrade adds a real trainable model to the Generic Grocery Planner without removing the original planner.

The new model objective is:

- predict which foods are promising additions to a grocery basket for each planner role
- generate extra candidate baskets locally from those learned signals
- let the existing local scorer rank heuristic and learned candidates together

This turns the planner from heuristic-only into a hybrid decision system:

- rules still guarantee stability and explainability
- the learned model broadens the candidate search space
- the scorer keeps one consistent ranking layer across all candidates

## Final Frozen Algorithm

The final presentation version is frozen as:

- algorithm version: `route_b_generalized_v5_main`
- label: `Generalized Route B Main`
- frozen scorer artifact: [`artifacts/plan_scorer/route_b_fair_v1/plan_candidate_scorer.joblib`](/Users/yinghansun/Desktop/diet-optimization-main/artifacts/plan_scorer/route_b_fair_v1/plan_candidate_scorer.joblib)
- frozen candidate-generator artifact: [`artifacts/candidate_generator/candidate_generator_best.joblib`](/Users/yinghansun/Desktop/diet-optimization-main/artifacts/candidate_generator/candidate_generator_best.joblib)
- final evaluation output directory: [`artifacts/plan_scorer/route_b_generalized_v5`](/Users/yinghansun/Desktop/diet-optimization-main/artifacts/plan_scorer/route_b_generalized_v5)

This is the version used for the final preset comparison, ablation study, robustness sweep, and presentation-ready summary artifacts.

## Existing Architecture That Was Preserved

The implementation keeps the current repo structure intact:

- app entrypoint: [`dietdashboard/app.py`](/Users/yinghansun/Desktop/diet-optimization-main/dietdashboard/app.py)
- recommendation entrypoint: [`dietdashboard/generic_recommender.py`](/Users/yinghansun/Desktop/diet-optimization-main/dietdashboard/generic_recommender.py)
- candidate generation and ranking: [`dietdashboard/hybrid_planner.py`](/Users/yinghansun/Desktop/diet-optimization-main/dietdashboard/hybrid_planner.py)
- scorer: [`dietdashboard/plan_scorer.py`](/Users/yinghansun/Desktop/diet-optimization-main/dietdashboard/plan_scorer.py)
- local data source: DuckDB in `data/data.db`

Nothing calls an external API at runtime.

The deterministic planner still works as:

- the baseline
- the fallback when model candidates are disabled
- the label source for the offline supervised dataset

## Methodology

Final methodology:

1. Generate many local planning scenarios from nutrition goals, dietary preferences, pantry states, shopping windows, store counts, and regional price contexts.
2. Run the current deterministic planner on each scenario to get several heuristic candidates.
3. Use the current heuristic basket label function to identify the strongest candidate for that scenario.
4. Convert the winning basket into binary food-role labels.
5. Train a supervised classifier over `(scenario, food, role)` rows.
6. At runtime, score all valid foods for each role, build learned basket seeds, merge them with heuristic seeds, dedupe, and rank the combined pool with the existing scorer.

This design was chosen because it is:

- local-only
- explainable
- compatible with the repo’s current deterministic planner
- easy to present to a course audience
- robust enough to fail clearly when artifacts are missing

## How The Model Works

The learned candidate generator predicts:

- `P(food should appear in role | scenario context, food attributes, heuristic signals)`

Roles are:

- `protein_anchor`
- `carb_base`
- `produce`
- `calorie_booster`

Runtime flow:

1. Build the current planner context from the request.
2. Compute food-role features from local structured data.
3. Score all valid food-role pairs with the trained local model.
4. Build learned candidate seeds with diversity and heuristic regularization.
5. Materialize full baskets with the same quantity and realism logic used by the heuristic planner.
6. Fuse heuristic and learned candidates.
7. Deduplicate exact and near-duplicate baskets.
8. Rank the fused pool with the trained local plan scorer.
9. Return the highest-ranked basket.

The learned model proposes. The existing rules repair. The scorer decides.

## Models Considered

Three candidate-generator model families were evaluated:

1. Logistic Regression
2. Random Forest
3. HistGradientBoosting

Validation winner metrics from [`artifacts/candidate_generator/candidate_generator_tuning_summary.json`](/Users/yinghansun/Desktop/diet-optimization-main/artifacts/candidate_generator/candidate_generator_tuning_summary.json):

- Logistic Regression
  - role recall at budget: `0.848780`
  - average precision: `0.843594`
  - exact seed rate: `0.272727`
- HistGradientBoosting
  - role recall at budget: `0.955568`
  - average precision: `0.989718`
  - exact seed rate: `0.752066`
- Random Forest
  - role recall at budget: `0.970252`
  - average precision: `0.996410`
  - exact seed rate: `0.884298`

Why Random Forest was selected:

- strongest overall validation recovery of good heuristic seed foods
- lowest validation log loss among the tested models
- clearer feature-importance outputs than HistGradientBoosting
- more flexible than Logistic Regression for nonlinear interactions between preferences, price context, and food attributes

Why the others were not selected:

- Logistic Regression was the easiest to explain, but it reconstructed strong seed baskets much less reliably.
- HistGradientBoosting was strong, but it trailed Random Forest on the main tuning metric and exact-seed reconstruction while being less transparent.

## Hyperparameters

Tuning searched `78` total configurations:

- Logistic Regression: `6`
- Random Forest: `24`
- HistGradientBoosting: `48`

Selected Random Forest hyperparameters:

- `n_estimators = 200`
- `max_depth = None`
- `max_features = 0.5`
- `min_samples_leaf = 2`
- `random_seed = 42`

The tuning metric was `validation_role_recall_at_budget`, with tie-breakers on:

- exact seed reconstruction rate
- average precision
- log loss

## Performance

Held-out scenario evaluation used `113` test scenarios and compared:

- heuristic-only baseline
- hybrid planner with the selected Random Forest candidate generator
- hybrid planner with Logistic Regression
- hybrid planner with HistGradientBoosting

From [`artifacts/candidate_generator/hybrid_planner_evaluation_summary.json`](/Users/yinghansun/Desktop/diet-optimization-main/artifacts/candidate_generator/hybrid_planner_evaluation_summary.json):

Heuristic-only baseline:

- avg scorer score: `8.271185`
- avg protein gap: `27.660177 g`
- avg calorie gap: `1025.200000 kcal`
- avg basket cost: `$33.24`

Hybrid best model:

- avg scorer score: `8.614313`
- avg protein gap: `26.533628 g`
- avg calorie gap: `996.113274 kcal`
- avg basket cost: `$32.33`

Hybrid best versus baseline:

- beats baseline by scorer in `29.20%` of held-out scenarios
- average scorer improvement: `+0.343128`
- average protein gap improvement: `1.126549 g`
- average calorie gap improvement: `29.086726 kcal`
- average cost change: `-$0.914867`
- model-sourced candidate selected in `62.83%` of held-out scenarios

Alternative end-to-end comparisons:

- Logistic Regression had the highest average scorer delta (`+0.528954`) but worsened protein and calorie gaps on average, so it was not selected.
- HistGradientBoosting was very competitive on cost and protein gap, but it lagged Random Forest on the explicit tuning objective and delivered much smaller calorie-gap improvement in the held-out runtime comparison.

## Why Hybrid Was Better Than Replacing The Heuristic

The deterministic planner still provides:

- sensible role structure
- quantity logic
- pantry and realism adjustments
- a stable fallback

The learned generator improves the system by:

- exploring candidates the heuristic beam does not always surface
- adapting candidate suggestions to scenario and price context patterns learned offline
- increasing the diversity of the candidate pool without abandoning explainability

## Limitations And Failure Cases

Important limitations:

- The candidate generator learns from heuristic winners, so it can inherit heuristic bias.
- If the scenario is very unusual, the model can still suggest unrealistic seeds that need rule-based repair.
- Recommendation quality still depends on the existing scorer, so model-generated candidates are only as useful as the ranking layer that evaluates them.
- Store realism is still approximate because the planner uses representative regional pricing and nearby-store counts, not exact inventory.
- The hybrid runtime is slower than heuristic-only because it scores additional food-role rows and materializes more baskets.
- Missing or stale artifacts break the learned path when explicitly enabled.
- Sparse coverage in local price/store tables can limit how well the model generalizes across geography.
- Deduplication is practical rather than perfect; baskets that are very similar but not near enough under the current overlap rule can still coexist.

## Commands

Build dataset:

```bash
make build-candidate-generator-dataset
```

Tune:

```bash
make tune-candidate-generator
```

Train:

```bash
make train-candidate-generator
```

Evaluate:

```bash
make evaluate-hybrid-planner
```

Run tests:

```bash
make test-plan-scorer
```
