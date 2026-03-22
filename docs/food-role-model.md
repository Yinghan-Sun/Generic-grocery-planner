# Generic Food Role Classifier

This document summarizes the additive trainable model component included with the current
generic grocery planner project.

## Model Objective

Predict the primary planner role for each generic food item:

- `protein_anchor`
- `carb_base`
- `produce`
- `calorie_booster`

The model is intended as an offline analysis and course-project component. It does not replace
the live heuristic planner.

## Why This Model

This target fits the current codebase well:

- the planner already reasons in these four roles
- the `generic_foods` table already contains strong nutrition and metadata features
- the task is small, explainable, and easy to validate
- the outputs are easy to discuss in a project presentation

## Training Data

Source table and joins:

- `generic_foods`
- representative price fields loaded through the current recommender candidate query

Dataset artifact:

- `artifacts/food_role_model/generic_food_role_training_dataset.csv`

Current dataset size:

- `75` generic foods

Label construction:

- primary labels are derived from the current heuristic role scorer
- the code evaluates each food across a deterministic scenario grid:
  - `6` goal profiles
  - `4` meal styles
  - `24` total scenarios
- each food gets a vote for the highest-scoring valid role in each scenario
- the final label is the majority-vote role, with score-based tie-breaking
- one edge case (`milk`) uses a manual override because it appears in current goal templates but
  falls below the strict heuristic role-candidate threshold

Label distribution:

- `produce`: `30`
- `protein_anchor`: `18`
- `carb_base`: `17`
- `calorie_booster`: `10`

Label source split:

- `heuristic_vote`: `74`
- `manual_override`: `1`

## Features Used

Numeric features:

- `default_serving_g`
- `purchase_unit_size_g`
- `budget_score`
- `commonality_rank`
- `energy_fibre_kcal`
- `protein`
- `carbohydrate`
- `fat`
- `fiber`
- `calcium`
- `iron`
- `vitamin_c`
- `protein_density_score`
- `fiber_score`
- `calcium_score`
- `iron_score`
- `vitamin_c_score`
- `representative_unit_price`
- `regional_price_low`
- `regional_price_high`
- `regional_price_span`

Boolean features:

- diet flags such as `vegetarian`, `vegan`, `dairy_free`, `gluten_free`
- `high_protein`
- `breakfast_friendly`
- storage/prep flags such as `shelf_stable`, `cold_only`, `microwave_friendly`
- price-source flags
- meal-tag flags for `breakfast`, `lunch`, `dinner`, `snack`, `side`

Categorical features:

- `food_family`
- `purchase_unit`
- `prep_level`
- `shelf_stability`
- `price_reference_source`

## Models Compared

### Logistic Regression

Why included:

- simple and interpretable baseline
- strong fit for a small structured dataset
- easy to explain in a class presentation

Hyperparameters tested:

- `C`: `0.25`, `1.0`, `4.0`
- `class_weight`: `None`, `balanced`

Selected logistic configuration:

- `C = 1.0`
- `class_weight = balanced`

### Random Forest

Why included:

- stronger non-linear baseline
- easy feature-importance story

Hyperparameters tested:

- `n_estimators`: `200`, `400`
- `max_depth`: `4`, `8`, `None`
- `min_samples_leaf`: `1`, `2`, `4`
- `class_weight`: `None`, `balanced`

Best random forest configuration:

- `n_estimators = 200`
- `max_depth = 4`
- `min_samples_leaf = 1`
- `class_weight = None`

## Validation Method

- `5`-fold stratified cross-validation
- `shuffle = true`
- `random_state = 42`

This is preferable to a single train/test split because the dataset is small.

## Results

Model comparison:

- Logistic Regression:
  - accuracy: `0.9467`
  - macro F1: `0.9356`
  - weighted F1: `0.9456`
- Random Forest:
  - accuracy: `0.9333`
  - macro F1: `0.9212`
  - weighted F1: `0.9322`

Selected model:

- `Logistic Regression`

Selection rationale:

- best macro F1
- simpler and more interpretable than the random forest

Per-class metrics for the selected model:

- `protein_anchor`: precision `0.9444`, recall `0.9444`, F1 `0.9444`
- `carb_base`: precision `0.9412`, recall `0.9412`, F1 `0.9412`
- `produce`: precision `0.9375`, recall `1.0000`, F1 `0.9677`
- `calorie_booster`: precision `1.0000`, recall `0.8000`, F1 `0.8889`

Confusion-matrix highlights:

- `produce` was the easiest class
- the hardest boundary was between:
  - `protein_anchor` and `carb_base`
  - `calorie_booster` and `produce`

Observed out-of-fold mistakes:

- `lentils`: true `protein_anchor`, predicted `carb_base`
- `ricotta`: true `calorie_booster`, predicted `protein_anchor`
- `sweet_potatoes`: true `carb_base`, predicted `produce`
- `avocado`: true `calorie_booster`, predicted `produce`

These mistakes are understandable because those foods are genuinely borderline in the current
planner logic.

## Interpretation

Top positive logistic features were sensible:

- `calorie_booster`:
  - high `fat`
  - high `energy_fibre_kcal`
  - `food_family=fat`
  - snack-oriented tags
- `carb_base`:
  - `food_family=grain`
  - `carbohydrate`
  - stable / microwave-friendly storage signals
- `produce`:
  - `food_family=produce`
  - `meal_tag_side`
  - `vitamin_c`
  - produce-oriented micronutrient scores
- `protein_anchor`:
  - `high_protein`
  - `food_family=legume`
  - `food_family=protein`
  - chilled / protein-supporting metadata

That gives a useful interpretability story for presentation: the model learned the same broad
nutritional and meal-structure signals that the planner uses heuristically.

## Limitations

- the dataset is very small (`75` rows)
- labels are derived from the current heuristic planner, not from human annotation
- one food uses a manual override (`milk`)
- the model predicts a single primary role, but some foods are genuinely multi-role
- the model is currently offline / additive only and is not used to drive runtime basket selection

## Reproducible Commands

Install the optional ML dependency:

```bash
uv sync --frozen --extra ml
```

Build the training dataset:

```bash
make build-food-role-dataset
```

Train and evaluate the model:

```bash
make train-food-role-model
```

Artifacts written by training:

- `artifacts/food_role_model/generic_food_role_training_dataset.csv`
- `artifacts/food_role_model/generic_food_role_training_dataset.schema.json`
- `artifacts/food_role_model/generic_food_role_classifier.joblib`
- `artifacts/food_role_model/role_model_evaluation.json`
- `artifacts/food_role_model/role_model_comparison.json`
- `artifacts/food_role_model/role_model_confusion_matrix.csv`
- `artifacts/food_role_model/role_model_feature_summary.csv`
- `artifacts/food_role_model/role_model_oof_predictions.csv`
