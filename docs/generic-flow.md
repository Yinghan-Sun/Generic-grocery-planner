# Generic Planner Flow

## What The App Does

The current app is a generic grocery planner demo.

It turns:
- a location
- nutrition targets
- simple dietary preferences
- optional pantry inputs

into:
- nearby grocery suggestions from a local store index
- a goal-aware generic shopping list
- representative regional basket-cost guidance
- meal suggestions
- store-fit recommendations

## Current Routes

Page routes:
- `/`
- `/generic`
- `/about`

API routes:
- `GET /api/stores/nearby`
- `POST /api/recommendations/generic`

## High-Level Request Flow

1. The frontend loads `/` or `/generic`.
2. The user enters a city/address or coordinates.
3. The frontend can geocode the address to coordinates.
4. The frontend calls `GET /api/stores/nearby`.
5. The frontend submits targets, preferences, pantry items, and nearby stores to `POST /api/recommendations/generic`.
6. The backend automatically builds deterministic heuristic candidates, adds learned candidates from the frozen local candidate-generator artifact, fuses and deduplicates the combined pool, ranks it with the trained scorer, and returns the highest-scoring result.
7. The backend adds representative regional price guidance and store-fit metadata.
8. The frontend renders the shopping list, basket summary, store picks, and export actions.

## Backend Modules

Primary modules:
- [`dietdashboard/app.py`](/Users/yinghansun/Desktop/diet-optimization-main/dietdashboard/app.py)
- [`dietdashboard/generic_recommender.py`](/Users/yinghansun/Desktop/diet-optimization-main/dietdashboard/generic_recommender.py)
- [`dietdashboard/hybrid_planner.py`](/Users/yinghansun/Desktop/diet-optimization-main/dietdashboard/hybrid_planner.py)
- [`dietdashboard/model_candidate_generator.py`](/Users/yinghansun/Desktop/diet-optimization-main/dietdashboard/model_candidate_generator.py)
- [`dietdashboard/model_candidate_training.py`](/Users/yinghansun/Desktop/diet-optimization-main/dietdashboard/model_candidate_training.py)
- [`dietdashboard/plan_scorer.py`](/Users/yinghansun/Desktop/diet-optimization-main/dietdashboard/plan_scorer.py)
- [`dietdashboard/store_discovery.py`](/Users/yinghansun/Desktop/diet-optimization-main/dietdashboard/store_discovery.py)
- [`dietdashboard/store_fit.py`](/Users/yinghansun/Desktop/diet-optimization-main/dietdashboard/store_fit.py)

## Frontend Files

Primary frontend files:
- [`dietdashboard/frontend/html/generic_dashboard.html`](/Users/yinghansun/Desktop/diet-optimization-main/dietdashboard/frontend/html/generic_dashboard.html)
- [`dietdashboard/frontend/js/generic_index.js`](/Users/yinghansun/Desktop/diet-optimization-main/dietdashboard/frontend/js/generic_index.js)
- [`dietdashboard/frontend/js/components/location_input.js`](/Users/yinghansun/Desktop/diet-optimization-main/dietdashboard/frontend/js/components/location_input.js)
- [`dietdashboard/frontend/js/components/store_results.js`](/Users/yinghansun/Desktop/diet-optimization-main/dietdashboard/frontend/js/components/store_results.js)
- [`dietdashboard/frontend/js/components/generic_results.js`](/Users/yinghansun/Desktop/diet-optimization-main/dietdashboard/frontend/js/components/generic_results.js)

Build command:

```bash
cd dietdashboard/frontend && ./bundle.sh
```

## Main DuckDB Tables

Runtime tables in `data/data.db`:
- `food_nutrition_base`
- `generic_food_catalog`
- `generic_food_source_map`
- `generic_foods`
- `bls_average_prices`
- `generic_food_prices`
- `generic_food_prices_by_area`
- `food_cpi_index`
- `usda_food_area_prices`
- `generic_food_usda_map`
- `generic_food_usda_prices_by_area`
- `store_places`

Runtime tables in `data/store_discovery.db`:
- `store_search_cache`
- `store_places_live`
- `store_places_foursquare`
- `store_places_unified`

## Data Build Files

Generic rebuild SQL:
- [`queries/load_generic.sql`](/Users/yinghansun/Desktop/diet-optimization-main/queries/load_generic.sql)
- [`queries/create_table_food_nutrition_base.sql`](/Users/yinghansun/Desktop/diet-optimization-main/queries/create_table_food_nutrition_base.sql)
- [`queries/create_table_generic_foods.sql`](/Users/yinghansun/Desktop/diet-optimization-main/queries/create_table_generic_foods.sql)
- [`queries/create_table_bls_average_prices.sql`](/Users/yinghansun/Desktop/diet-optimization-main/queries/create_table_bls_average_prices.sql)
- [`queries/create_table_generic_food_prices.sql`](/Users/yinghansun/Desktop/diet-optimization-main/queries/create_table_generic_food_prices.sql)
- [`queries/create_table_food_cpi_index.sql`](/Users/yinghansun/Desktop/diet-optimization-main/queries/create_table_food_cpi_index.sql)
- [`queries/create_table_usda_food_area_prices.sql`](/Users/yinghansun/Desktop/diet-optimization-main/queries/create_table_usda_food_area_prices.sql)
- [`queries/create_table_store_places.sql`](/Users/yinghansun/Desktop/diet-optimization-main/queries/create_table_store_places.sql)

Supporting scripts:
- [`scripts/prepare_usda_food_area_prices.py`](/Users/yinghansun/Desktop/diet-optimization-main/scripts/prepare_usda_food_area_prices.py)
- [`scripts/fetch_bls_food_cpi.py`](/Users/yinghansun/Desktop/diet-optimization-main/scripts/fetch_bls_food_cpi.py)
- [`scripts/backfill_generic_stores.py`](/Users/yinghansun/Desktop/diet-optimization-main/scripts/backfill_generic_stores.py)
- [`scripts/ingest_foursquare_stores.py`](/Users/yinghansun/Desktop/diet-optimization-main/scripts/ingest_foursquare_stores.py)

## Price Layer

Runtime price priority is:
1. USDA area-aware inflation-adjusted price
2. BLS area-aware price
3. BLS fallback
4. no price

These prices are representative regional estimates, not exact store or SKU quotes.

## Store Discovery

The demo defaults to local store-discovery mode.

Normal lookup order in local mode:
1. unified local store index
2. seed `store_places` fallback from `data/data.db`

Optional maintenance workflows can still backfill or ingest store data locally into the sidecar DB.

## Tests

Primary checks:

```bash
make test-generic
make qa-generic
make test-plan-scorer
make build-candidate-generator-dataset
make tune-candidate-generator
make train-candidate-generator
make evaluate-hybrid-planner
```

## Local Start

Canonical app entrypoint:

```bash
python -m dietdashboard.app
```

Local `uv` equivalent:

```bash
uv run python -m dietdashboard.app
```
