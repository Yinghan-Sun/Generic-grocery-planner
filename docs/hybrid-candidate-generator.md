# Hybrid Learned Candidate Generator

## Runtime Architecture

The generic grocery planner now supports an additive Route B candidate-generation upgrade:

1. `dietdashboard/hybrid_planner.py` still builds the original deterministic heuristic candidates.
2. A new local learned candidate generator scores food-role pairs for the current scenario and proposes additional basket seeds.
3. The runtime materializes both seed sets into full baskets, deduplicates exact and near-duplicates, and preserves candidate source metadata.
4. `dietdashboard/plan_scorer.py` ranks the fused candidate pool with the existing trained local scorer.
5. The highest-ranked basket is returned.

The deterministic planner remains intact and is still the default path unless model candidates are explicitly enabled.

## Where The New Pieces Live

New candidate-generator modules:

- [`dietdashboard/model_candidate_features.py`](/Users/yinghansun/Desktop/diet-optimization-main/dietdashboard/model_candidate_features.py)
- [`dietdashboard/model_candidate_generator.py`](/Users/yinghansun/Desktop/diet-optimization-main/dietdashboard/model_candidate_generator.py)
- [`dietdashboard/model_candidate_training.py`](/Users/yinghansun/Desktop/diet-optimization-main/dietdashboard/model_candidate_training.py)
- [`dietdashboard/model_candidate_tuning.py`](/Users/yinghansun/Desktop/diet-optimization-main/dietdashboard/model_candidate_tuning.py)

New offline scripts:

- [`scripts/build_candidate_generator_dataset.py`](/Users/yinghansun/Desktop/diet-optimization-main/scripts/build_candidate_generator_dataset.py)
- [`scripts/tune_candidate_generator.py`](/Users/yinghansun/Desktop/diet-optimization-main/scripts/tune_candidate_generator.py)
- [`scripts/train_candidate_generator.py`](/Users/yinghansun/Desktop/diet-optimization-main/scripts/train_candidate_generator.py)
- [`scripts/evaluate_hybrid_planner.py`](/Users/yinghansun/Desktop/diet-optimization-main/scripts/evaluate_hybrid_planner.py)

## Training Data Strategy

The candidate generator is trained entirely from local planner behavior:

- `600` reproducible planning scenarios are built from combinations of:
  - nutrition target profiles
  - meal styles
  - vegetarian, vegan, dairy-free, low-prep, and budget-friendly preferences
  - pantry variants
  - shopping windows and shopping modes
  - regional USDA/BLS price contexts
  - nearby store-count variations
- For each scenario, the existing heuristic planner generates multiple deterministic candidates.
- The current heuristic label function in [`dietdashboard/plan_scorer.py`](/Users/yinghansun/Desktop/diet-optimization-main/dietdashboard/plan_scorer.py) picks the strongest heuristic basket for that scenario.
- Every valid `(scenario, food, role)` pair becomes a supervised example.
- The label is `1` when that food appears in the strongest heuristic basket for that role, otherwise `0`.

Saved dataset artifacts:

- [`artifacts/candidate_generator/candidate_generator_training_dataset.csv`](/Users/yinghansun/Desktop/diet-optimization-main/artifacts/candidate_generator/candidate_generator_training_dataset.csv)
- [`artifacts/candidate_generator/candidate_generator_training_dataset.schema.json`](/Users/yinghansun/Desktop/diet-optimization-main/artifacts/candidate_generator/candidate_generator_training_dataset.schema.json)
- [`artifacts/candidate_generator/candidate_generator_training_dataset.scenarios.json`](/Users/yinghansun/Desktop/diet-optimization-main/artifacts/candidate_generator/candidate_generator_training_dataset.scenarios.json)

Current dataset size:

- `67,920` labeled food-role rows
- `600` scenarios
- split rows: train `41,314`, validation `13,823`, test `12,783`

## Features

The learned generator uses local structured features only.

Scenario features:

- daily protein, calories, macro and micronutrient targets
- days and shopping mode
- nearby store count
- pantry item count
- inferred goal profile
- target role counts from the basket policy
- BLS and USDA regional price codes
- dietary-preference flags

Food features:

- family, prep level, shelf stability, purchase unit
- calories, protein, carbs, fat, fiber, calcium, iron, vitamin C
- density and nutrient-score columns already present in `generic_foods`
- representative unit price and regional price spread
- food tags such as shelf-stable, microwave-friendly, breakfast-friendly
- whether the food is already in the pantry
- the current heuristic role score and role rank

Top random-forest feature importances are saved in:

- [`artifacts/candidate_generator/candidate_generator_best_feature_summary.csv`](/Users/yinghansun/Desktop/diet-optimization-main/artifacts/candidate_generator/candidate_generator_best_feature_summary.csv)

The strongest signals in the final model are:

- `heuristic_role_rank`
- `heuristic_role_score`
- `energy_fibre_kcal`
- `commonality_rank`
- `regional_price_span`

## Final Model And Artifacts

Selected model:

- `random_forest`

Saved artifacts:

- [`artifacts/candidate_generator/candidate_generator_best.joblib`](/Users/yinghansun/Desktop/diet-optimization-main/artifacts/candidate_generator/candidate_generator_best.joblib)
- [`artifacts/candidate_generator/models/candidate_generator_logistic_regression.joblib`](/Users/yinghansun/Desktop/diet-optimization-main/artifacts/candidate_generator/models/candidate_generator_logistic_regression.joblib)
- [`artifacts/candidate_generator/models/candidate_generator_random_forest.joblib`](/Users/yinghansun/Desktop/diet-optimization-main/artifacts/candidate_generator/models/candidate_generator_random_forest.joblib)
- [`artifacts/candidate_generator/models/candidate_generator_hist_gradient_boosting.joblib`](/Users/yinghansun/Desktop/diet-optimization-main/artifacts/candidate_generator/models/candidate_generator_hist_gradient_boosting.joblib)

Why the random forest won:

- best validation role-recall-at-budget: `0.970252`
- best validation average precision: `0.996410`
- best validation log loss: `0.009764`
- best validation exact-seed reconstruction rate: `0.884298`
- strongest held-out protein-gap improvement in end-to-end hybrid evaluation among the tree models
- easy to explain for a course presentation
- artifact remains fully local and deterministic at inference time

## Hyperparameter Tuning

Tuning is explicit and reproducible.

Search sizes:

- logistic regression: `6` trials
- random forest: `24` trials
- hist gradient boosting: `48` trials
- total: `78` trials

Primary tuning metric:

- `validation_role_recall_at_budget`

Tie-breakers:

- `validation_scenario_exact_seed_rate`
- `validation_average_precision`
- `validation_log_loss`

Saved tuning outputs:

- [`artifacts/candidate_generator/candidate_generator_tuning_results.csv`](/Users/yinghansun/Desktop/diet-optimization-main/artifacts/candidate_generator/candidate_generator_tuning_results.csv)
- [`artifacts/candidate_generator/candidate_generator_tuning_summary.json`](/Users/yinghansun/Desktop/diet-optimization-main/artifacts/candidate_generator/candidate_generator_tuning_summary.json)
- [`artifacts/candidate_generator/candidate_generator_model_comparison.json`](/Users/yinghansun/Desktop/diet-optimization-main/artifacts/candidate_generator/candidate_generator_model_comparison.json)

## Runtime Controls

The new runtime flags are optional and backward compatible:

- `enable_model_candidates`
- `model_candidate_count`
- `candidate_generator_model_path`
- `candidate_generator_backend`
- `debug_candidate_generation`

Behavior:

- default: model candidates disabled
- if enabled and the artifact is missing or invalid, the request fails clearly with a local artifact error
- heuristic candidate generation remains available and unchanged

## Debug Payload

When `debug_candidate_generation=true`, the response includes:

- heuristic candidate count
- learned candidate count
- fused candidate count
- candidate ids
- source labels such as `heuristic`, `model`, `repaired_model`, or `hybrid`
- shopping-food ids per candidate
- generator scores and heuristic selection scores

## Evaluation Outputs

Held-out end-to-end evaluation artifacts:

- [`artifacts/candidate_generator/hybrid_planner_evaluation_detailed.csv`](/Users/yinghansun/Desktop/diet-optimization-main/artifacts/candidate_generator/hybrid_planner_evaluation_detailed.csv)
- [`artifacts/candidate_generator/hybrid_planner_evaluation_summary.json`](/Users/yinghansun/Desktop/diet-optimization-main/artifacts/candidate_generator/hybrid_planner_evaluation_summary.json)
- [`artifacts/candidate_generator/hybrid_planner_evaluation_summary.md`](/Users/yinghansun/Desktop/diet-optimization-main/artifacts/candidate_generator/hybrid_planner_evaluation_summary.md)

## Main Commands

Build the dataset:

```bash
make build-candidate-generator-dataset
```

Tune hyperparameters:

```bash
make tune-candidate-generator
```

Train the selected model:

```bash
make train-candidate-generator
```

Run the held-out comparison:

```bash
make evaluate-hybrid-planner
```
