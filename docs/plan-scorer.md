# Plan Scorer Runtime

## What It Does

The generic grocery planner runtime is model-ranked:

1. `dietdashboard/hybrid_planner.py` generates multiple deterministic candidate plans from the same heuristic search space
2. `dietdashboard/plan_scorer.py` extracts local plan features and applies a trained local model
3. the highest-scoring candidate is returned

The trained scorer artifact is required at runtime. If it is missing or invalid, the request fails
explicitly instead of falling back to another planner path.

## Training Data

Training examples are generated fully locally from the existing planner:

- `dietdashboard/plan_scorer_training.py` builds a fixed request grid across goal styles, meal styles, shopping windows, and price contexts
- each request generates multiple candidate plans with `recommend_generic_food_candidates(...)`
- each candidate is featurized with simple interpretable basket-level features
- initial labels are derived from a deterministic heuristic objective over nutrition fit, price efficiency, diversity, realism, and existing heuristic selection signals

There is no runtime network dependency in this pipeline.

## Main Features

Current features include:

- total calories and calorie target gap
- total protein/carbs/fat/fiber and macro deviation signals
- calcium, iron, and vitamin C deviation signals
- total basket cost
- price per 1000 kcal
- price per 100 g protein
- unique ingredient count
- role and food-family diversity counts
- repetition penalty
- unrealistic basket penalty
- nearby store count
- preference-match score
- heuristic selection score
- warning, scaling-note, pantry-note, and realism-note counts

The feature schema lives in `dietdashboard/plan_scorer.py` and is designed to be expanded later.

## Train Locally

Install the optional ML extras:

```bash
uv sync --frozen --extra ml
```

Train the default scorer artifact:

```bash
make train-plan-scorer
```

Direct CLI example:

```bash
uv run --extra ml python ./scripts/train_plan_scorer.py \
  --candidate-count 8 \
  --backend auto \
  --learning-rate 0.05 \
  --max-depth 3 \
  --n-estimators 250 \
  --validation-split 0.25 \
  --random-seed 42
```

Artifacts are written under:

```text
artifacts/plan_scorer/
```

Default outputs:

- `plan_candidate_training_dataset.csv`
- `plan_candidate_training_dataset.schema.json`
- `plan_candidate_scorer.joblib`
- `plan_candidate_training_metrics.json`
- `plan_candidate_feature_summary.csv`

## Runtime Flags

API request fields:

- `candidate_count`
- `scorer_model_path`
- `debug_scorer`

Environment variables:

- `TRAINED_SCORER_CANDIDATE_COUNT`
- `TRAINED_SCORER_MODEL_PATH`
- `TRAINED_SCORER_DEBUG`

## Debugging

When `debug_scorer` is enabled, the recommendation response includes `scoring_debug` with:

- candidate ids
- shopping-list item ids
- extracted feature values
- heuristic score
- model score
- selected candidate id

This makes it easy to inspect the deterministic candidate set against the trained ranking layer.
