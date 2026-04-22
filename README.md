# Diet Dashboard (Generic Grocery Planner)

Diet Dashboard is a Flask application that turns a location, daily nutrition targets, and a small set of user preferences into a generic grocery plan. The current app does not optimize branded products or exact store inventory. Instead, it produces a basket of common food categories, rough quantities, representative regional price estimates, nearby grocery options, and store-fit suggestions for the generated basket.

The runtime is built around local DuckDB databases plus shipped model artifacts:

- `data/data.db` supplies generic food, nutrition, and price reference data.
- `data/store_discovery.db` supplies the nearby-store sidecar index and cache.
- `artifacts/candidate_generator/candidate_generator_best.joblib` supplies learned candidate generation.
- `artifacts/plan_scorer/hybrid_planner_fair_v1/plan_candidate_scorer.joblib` supplies final candidate reranking.
- `dietdashboard/static/generic_bundle.js` and `dietdashboard/static/bundle.css` supply the prebuilt frontend bundle.

## What The App Does

Given a location and nutrition targets, the app will:

- geocode an address in the browser or use browser geolocation/direct coordinates
- look up nearby grocery stores from a local store index
- infer a planning goal profile from the request
- generate multiple candidate grocery baskets
- optionally add learned candidates from a trained candidate-generator artifact
- fuse and deduplicate the candidate pool
- rerank the pool with a trained scorer
- materialize the winning candidate into a shopping list with quantities
- estimate a representative basket cost from USDA and BLS price references
- suggest nearby stores that best fit the basket style
- generate lightweight meal ideas and exportable text output

## Features

- Goal presets in the frontend for `Muscle Gain`, `Fat Loss`, `Maintenance`, `High-Protein Vegetarian`, `Budget-Friendly Healthy`, `Vegan`, and `Dairy-free`
- Required calorie and protein targets, with optional carbohydrate, fat, and fiber targets in the current UI
- API support for additional optional calcium, iron, and vitamin C targets
- Shopping windows restricted to `1`, `3`, `5`, or `7` days
- Shopping modes `fresh`, `balanced`, and `bulk`
- Generic basket roles such as `protein_anchor`, `carb_base`, `produce`, and `calorie_booster`
- Pantry adjustments for common staples the user already has
- Nearby-store lookup with local sidecar data, cached results, and optional live Overpass fallback depending on configuration
- Representative regional pricing using USDA monthly area prices when available, with BLS regional or national fallback
- Store-fit ranking and grouped picks such as one-stop, budget, produce, and bulk
- Lightweight meal suggestions built from the same recommended basket
- Copy and download actions for text exports
- Developer mode UI and debug payloads when `PROD=0` and `/generic?developer=1` is used

## Demo Scope

The current web app is intentionally narrower than a full diet optimization system.

Included in the shipped demo:

- generic food recommendations rather than branded SKU matching
- rough quantities and nutrition summaries
- representative regional price guidance
- nearby-store discovery and store-fit heuristics
- one-click hybrid planning in the browser

Intentionally not included in the current runtime:

- exact store inventory checks
- exact product/SKU recommendations
- account management, checkout, or saved plans
- medical or clinical nutrition advice
- a full meal-planning or calendar workflow
- a self-contained raw-data rebuild from source files alone

Also note:

- the frontend can geocode typed addresses through Nominatim, but direct latitude/longitude entry avoids that dependency
- the default production container uses `STORE_DISCOVERY_MODE=local`, so live Overpass lookups are not required in production unless you override that setting
- `data/data.db` still contains older tables from broader diet-optimization work, but the current Flask routes only expose the generic grocery planner flow

## Project Structure

```text
dietdashboard/
  app.py                          Flask entrypoint, page routes, JSON APIs, timeout wrappers
  generic_recommender.py          Price-context resolution and public recommendation entrypoints
  hybrid_planner.py               Candidate generation, fusion, materialization, scorer integration
  plan_scorer.py                  Trained scorer loading, feature extraction, scoring utilities
  model_candidate_generator.py    Learned candidate-generator artifact loading and scoring
  model_candidate_features.py     Feature definitions for learned candidate generation
  store_discovery.py              Nearby-store lookup, cache, live/offline enrichment logic
  store_fit.py                    Basket-to-store heuristic ranking and grouped store picks
  request_logging.py              Request metadata logging to tmp/requests.db
  frontend/
    html/                         Jinja templates (`generic_dashboard.html`, `about.html`, `base.html`)
    js/                           Unbundled frontend code and UI components
    bundle.sh                     `esbuild` wrapper for rebuilding the bundle
    styles.css                    Frontend stylesheet source
  static/
    generic_bundle.js             Committed frontend bundle served by Flask
    bundle.css                    Committed compiled CSS served by Flask

artifacts/
  candidate_generator/            Candidate-generator artifacts, training datasets, tuning output
  plan_scorer/                    Scorer artifacts, training datasets, comparison/evaluation output
  food_role_model/                Optional role-model training artifacts

data/
  data.db                         Main runtime DuckDB database
  store_discovery.db              Store-discovery sidecar DuckDB database
  generic_food_*.csv              Generic catalog and mapping inputs
  bls/                            BLS average price and CPI source files
  usda/                           USDA area-price source files
  store_places_seed.csv           Seed nearby-store input used when building `store_places`
  store_backfill_cities.csv       Default city list for store backfill scripts
  foursquare_os/                  Optional offline Foursquare OS ingest input

queries/                          SQL used to build tables in `data/data.db`
scripts/                          Validation, ingestion, training, and evaluation scripts
Containerfile                     Primary production container used by Fly.io
Dockerfile                        Simpler alternate container definition
Makefile                          Developer shortcuts for setup, tests, data rebuild, training
fly.toml                          Fly.io app configuration
Procfile                          Process declaration for `python -m dietdashboard.app`
```

## How It Works

The shipped app uses a hybrid planning pipeline rather than a single deterministic pass.

### 1. Input collection

The frontend collects:

- location query or direct coordinates
- days and shopping mode
- calories and protein
- optional carbohydrate, fat, and fiber
- dietary flags and meal-style preference
- pantry items already on hand

The browser geocodes typed addresses with Nominatim (`https://nominatim.openstreetmap.org/search`). If the user clicks `Use My Location`, the browser uses `navigator.geolocation`. The frontend can also call `/api/stores/nearby` first and then reuse that store snapshot in the recommendation request.

### 2. Store lookup and price-context resolution

`/api/recommendations/generic` either:

- normalizes a caller-provided `stores` snapshot, or
- performs its own nearby-store lookup with `dietdashboard.store_discovery.nearby_stores`

Store lookup behavior depends on `STORE_DISCOVERY_MODE`:

- `local`: use the local unified index in `data/store_discovery.db`, then fall back to seeded `store_places` in `data/data.db`
- `auto`: try the local unified index, then cache, then live Overpass, then local seed data
- `live`: use cache, then live Overpass

After store lookup, `resolve_price_context()` maps the request to a USDA area code and a BLS area code using store addresses when possible, then latitude/longitude fallback when necessary. That context drives price selection later in the pipeline.

### 3. Candidate preparation

`hybrid_planner._prepare_context()` loads eligible generic foods from `data/data.db` by joining:

- `generic_foods`
- `generic_food_usda_prices_by_area`
- `generic_food_prices_by_area`
- `generic_food_prices`

At this stage the pipeline:

- filters foods by `vegetarian`, `dairy_free`, and `vegan`
- infers a `goal_profile` such as `muscle_gain`, `fat_loss`, `maintenance`, `budget_friendly_healthy`, `high_protein_vegetarian`, or `generic_balanced`
- builds basket policy parameters for the detected goal
- computes role scores and role orders for each basket role

### 4. Heuristic candidate generation

`hybrid_planner._generate_candidate_seeds()` creates multiple heuristic basket seeds. These seeds vary role choices and trade off nutrient fit, diversity, preference alignment, price efficiency, and basket structure.

### 5. Learned candidate generation

If learned candidates are enabled, the planner loads the shipped candidate-generator artifact from:

- `artifacts/candidate_generator/candidate_generator_best.joblib`

The final runtime configuration in `dietdashboard/hybrid_pipeline_final.py` enables learned candidates by default and points at the best candidate-generator artifact. The shipped default backend label is `random_forest`.

Learned candidates are generated from feature rows defined in `model_candidate_features.py` and scored by `model_candidate_generator.py`.

### 6. Candidate materialization

Each seed is materialized into a full grocery plan. This is where the app turns role selections into:

- per-item quantities
- multi-day scaling
- shopping-mode adjustments
- pantry reductions
- realism/splitting adjustments
- item-level price estimates
- basket-level price totals
- nutrition summaries
- meal suggestions

Model-derived seeds can go through structured materialization before the final basket is built. The final runtime configuration currently enables both structured complementarity and structured materialization.

### 7. Candidate fusion and reranking

Heuristic and learned candidates are combined into a raw pool, then deduplicated or merged when near-duplicates are found.

The fused candidate pool is then reranked by the trained plan scorer loaded from:

- `artifacts/plan_scorer/hybrid_planner_fair_v1/plan_candidate_scorer.joblib`

The scorer uses feature rows defined in `plan_scorer.py` and selects the final winner returned to the API caller.

### 8. Post-processing

After the final basket is selected, the app:

- ranks nearby stores with `store_fit.recommend_store_fits()`
- returns grouped store picks such as `one_stop_pick`, `budget_pick`, `produce_pick`, and `bulk_pick`
- adds assumptions, scaling notes, pantry notes, warnings, pricing notes, and optional debug metadata

In production mode (`PROD=1`), developer-only planner debug fields are stripped from the JSON response.

### 9. Request logging and bounded optional stages

The app logs request metadata to `tmp/requests.db` through `request_logging.py`.

Nearby-store lookup and store-fit ranking are wrapped in configurable timeout guards:

- `NEARBY_STORES_TIMEOUT_S`
- `RECOMMENDATION_STORE_LOOKUP_TIMEOUT_S`
- `STORE_FIT_TIMEOUT_S`

If those optional stages exceed the timeout, the app degrades gracefully and returns fallback data instead of failing the entire request.

## Data And Runtime Artifacts

### Required To Run The Shipped App

These files must exist for the default runtime described by the code:

- `data/data.db`
- `data/store_discovery.db`
- `artifacts/candidate_generator/candidate_generator_best.joblib`
- `artifacts/plan_scorer/hybrid_planner_fair_v1/plan_candidate_scorer.joblib`
- `dietdashboard/static/generic_bundle.js`
- `dietdashboard/static/bundle.css`

The current production `Containerfile` copies exactly those runtime classes of assets into the image.

### Generated At Runtime

The app creates or updates these files while running:

- `tmp/requests.db` for request logging
- `data/store_discovery.db` cache/live-index tables when store discovery runs in modes that refresh or persist sidecar data

### Useful But Not Required For The Default Runtime

- backend-specific candidate-generator artifacts under `artifacts/candidate_generator/models/`
- older scorer artifacts under `artifacts/plan_scorer/`
- evaluation summaries under `artifacts/plan_scorer/hybrid_planner_generalized_v5/`
- raw CSV and parquet inputs under `data/` used for rebuilds, audits, or retraining

### Required Only For Rebuilds Or Training

The codebase contains rebuild and training paths that are separate from the shipped runtime:

- generic food catalog and mapping CSVs in `data/`
- BLS raw files under `data/bls/`
- USDA files under `data/usda/`
- seed and offline store datasets such as `data/store_places_seed.csv` and `data/foursquare_os/foursquare_os_places_grocery_metros.parquet`
- SQL in `queries/`
- training and evaluation scripts in `scripts/`

Important limitation:

- `Makefile` expects raw CIQUAL and CALNUT files such as `data/ciqual2020/alim.csv`, `data/ciqual2020/compo.csv`, `data/calnut.0.csv`, and `data/calnut.1.csv`
- those files are not present in this workspace
- as a result, a full rebuild of `data/data.db` from raw nutrition sources is not reproducible from this checkout alone, even though the shipped `data/data.db` is present and sufficient to run the app

## Local Setup

### Prerequisites

- Python `3.13`
- `uv`
- `esbuild` on `PATH` if you want to rebuild frontend assets

Why `--extra ml` is required:

- the app imports the scorer and candidate-generator modules at runtime
- those modules depend on `scikit-learn`
- the production container also installs the `ml` extra

### Run The Existing Shipped Build

1. Install Python dependencies:

   ```bash
   uv sync --extra ml
   ```

2. Start the Flask app:

   ```bash
   uv run python -m dietdashboard.app
   ```

   Or:

   ```bash
   make run-app
   ```

3. Open:

   ```text
   http://localhost:8000
   ```

If you only want to run the shipped app, you do not need to retrain models or rebuild the DuckDB databases first.

### Rebuild The Frontend Bundle

The committed static bundle is already present, so this step is only needed if you edit files under `dietdashboard/frontend/`.

```bash
cd dietdashboard/frontend
./bundle.sh
```

Watch mode:

```bash
make frontend-watch
```

Combined app + watch mode:

```bash
make run-dev
```

Note:

- the repo does not include a `package.json`
- `bundle.sh` calls `esbuild` directly
- you need `esbuild` installed separately and available on `PATH`

## Validation And Test Scripts

Useful validation entrypoints in the current repo:

```bash
make smoke-generic
make test-generic-behavior
make test-plan-scorer
make qa-generic
```

What they cover:

- `scripts/generic_smoke_test.py`: basic route, API, production-sanitization, and timeout behavior
- `scripts/generic_behavior_test.py`: scenario regression checks across vegetarian/vegan, price behavior, pantry handling, store-fit, and multi-day scaling
- `scripts/hybrid_planner_test.py`: scorer training smoke tests, candidate-generator training/tuning smoke tests, and hybrid candidate generation

## Optional Data Rebuild, Ingestion, And Training

These paths are optional. They are not required to run the app as currently shipped.

### Rebuild `data/data.db`

```bash
make build-generic-data
```

Component steps:

```bash
make create-table-food-nutrition-base
make create-table-generic-foods
make create-table-bls-average-prices
make create-table-generic-food-prices
make create-table-food-cpi-index
make create-table-usda-food-area-prices
make create-table-store-places
```

Remember that the full rebuild path expects raw CIQUAL/CALNUT inputs that are not included in this workspace.

### Maintain The Store Sidecar Database

```bash
make store-discovery-summary
make store-discovery-prune-cache
make store-discovery-dedupe-live
make backfill-generic-stores
make ingest-foursquare-stores
make ingest-foursquare-os-places
```

Related scripts:

- `scripts/backfill_generic_stores.py` geocodes cities with Nominatim and backfills live Overpass grocery results into `data/store_discovery.db`
- `scripts/ingest_foursquare_stores.py` ingests local Foursquare-like CSV, Parquet, or JSONL data into the sidecar DB
- `scripts/store_discovery_admin.py` inspects and maintains the sidecar DB

### Train Or Evaluate Artifacts

```bash
make build-food-role-dataset
make train-food-role-model
make build-candidate-generator-dataset
make tune-candidate-generator
make train-candidate-generator
make build-plan-scorer-dataset
make train-plan-scorer
make evaluate-hybrid-planner
make compare-plan-scorers
make hybrid-planner-ablation
make hybrid-planner-robustness
make hybrid-planner-final-summary
```

The current app does not require these steps unless you want to regenerate or compare artifacts.

## Deployment

### Recommended Production Image

The primary production image is defined in `Containerfile`.

Build:

```bash
docker build . -t diet-dashboard -f Containerfile
```

Run:

```bash
docker run --rm -p 8000:8000 diet-dashboard
```

What `Containerfile` does:

- uses `ghcr.io/astral-sh/uv:bookworm-slim`
- copies `dietdashboard/`, `artifacts/`, `data/data.db`, and `data/store_discovery.db`
- installs dependencies with `uv sync --frozen --no-editable --no-dev --extra ml`
- sets `PROD=1`
- sets `STORE_DISCOVERY_MODE=local`
- serves `dietdashboard.app:create_app()` with Gunicorn on port `8000`

### Alternate Container

There is also a simpler `Dockerfile` that copies the whole repo and runs:

```bash
python -m dietdashboard.app
```

The Fly.io config uses `Containerfile`, not `Dockerfile`.

### Production Environment Variables

The app has defaults for all of these, but they are the real configuration points read by the code:

| Variable | Purpose |
| --- | --- |
| `PORT` | Flask development port or external process port. Default `8000`. |
| `PROD` | Production mode toggle. When `1`, debug planner metadata is stripped and GoatCounter is injected in `base.html`. |
| `STORE_DISCOVERY_MODE` | Store lookup strategy: `local`, `auto`, or `live`. |
| `STORE_DISCOVERY_DB_PATH` | Path to `store_discovery.db`. |
| `STORE_DISCOVERY_MAIN_DB_PATH` | Path to the main `data.db`. |
| `OVERPASS_API_URL` | Overpass endpoint for live store lookup. |
| `OVERPASS_TIMEOUT_S` | Timeout for live Overpass requests. |
| `OVERPASS_USER_AGENT` | User agent string for live Overpass requests. |
| `STORE_DISCOVERY_CACHE_TTL_S` | TTL for cached live store searches. |
| `STORE_DISCOVERY_PERSIST_LIVE` | Whether live results are persisted into the sidecar DB. |
| `STORE_DISCOVERY_LIVE_INDEX_MAX_AGE_S` | Max age for live index rows. |
| `STORE_DISCOVERY_LIVE_INDEX_MIN_RESULTS` | Minimum result threshold before considering a refresh. |
| `STORE_DISCOVERY_UNIFIED_REFRESH_TTL_S` | TTL for refreshing the unified store index. |
| `STORE_DISCOVERY_READ_RETRY_COUNT` | Retry count for unified-store reads. |
| `STORE_DISCOVERY_READ_RETRY_DELAY_MS` | Delay between unified-store read retries. |
| `NEARBY_STORES_TIMEOUT_S` | Timeout for `/api/stores/nearby`. |
| `RECOMMENDATION_STORE_LOOKUP_TIMEOUT_S` | Timeout for store lookup inside recommendation requests. |
| `STORE_FIT_TIMEOUT_S` | Timeout for store-fit ranking. |
| `TRAINED_SCORER_CANDIDATE_COUNT` | Default candidate pool size for reranking. |
| `TRAINED_SCORER_DEBUG` | Default scorer debug toggle outside production. |
| `ENABLE_MODEL_CANDIDATES` | Enable or disable learned candidate generation by default. |
| `MODEL_CANDIDATE_COUNT` | Number of learned candidates to add by default. |
| `CANDIDATE_GENERATOR_BACKEND` | Default backend label expected by the candidate-generator artifact. |
| `MODEL_CANDIDATE_DEBUG` | Default candidate-generation debug toggle outside production. |
| `TRAINED_SCORER_MODEL_PATH` | Override scorer artifact path. |
| `CANDIDATE_GENERATOR_MODEL_PATH` | Override candidate-generator artifact path. |
| `GUNICORN_WORKERS` | Gunicorn worker count in the production container. |
| `GUNICORN_THREADS` | Gunicorn thread count in the production container. |
| `GUNICORN_TIMEOUT` | Gunicorn worker timeout. |
| `GUNICORN_GRACEFUL_TIMEOUT` | Gunicorn graceful timeout. |

### Fly.io

The repo includes:

- `fly.toml` pointing at `Containerfile`
- `.github/workflows/fly-deploy.yml` that runs `flyctl deploy --remote-only` on pushes to `main`

Current visible Fly config in this workspace:

- app name: `diet-optimization-main`
- region: `lax`
- internal port: `8000`
- minimum running machines: `1`
- VM memory: `1024 MB`

## Routes And API

### Page Routes

- `GET /` - renders the generic grocery planner dashboard
- `GET /generic` - same planner page as `/`
- `GET /about` - static about page describing the demo and attribution notes

### Static Assets

- `GET /static/generic_bundle.js`
- `GET /static/bundle.css`

Flask adds a file-mtime query parameter for cache busting through `static_asset_url()`.

### `GET /api/stores/nearby`

Query parameters:

- `lat` required
- `lon` required
- `radius_m` optional, default `10000`, max `50000`
- `limit` optional, default `5`, max `25`

Response shape:

```json
{
  "stores": [
    {
      "store_id": "foursquare_os_places:...",
      "name": "Ramon Luna & Co.",
      "address": "1595 California St",
      "distance_m": 713.3,
      "lat": 37.39459832004907,
      "lon": -122.0894738766627,
      "category": "grocery"
    }
  ]
}
```

### `POST /api/recommendations/generic`

Required request fields:

- `location.lat`
- `location.lon`
- `targets.protein`
- `targets.energy_fibre_kcal`

Supported optional request fields:

- `targets.carbohydrate`
- `targets.fat`
- `targets.fiber`
- `targets.calcium`
- `targets.iron`
- `targets.vitamin_c`
- `preferences.vegetarian`
- `preferences.dairy_free`
- `preferences.vegan`
- `preferences.budget_friendly`
- `preferences.meal_style` (`breakfast`, `lunch_dinner`, `snack`, `any`)
- `pantry_items`
- `stores`
- `radius_m`
- `store_limit`
- `days` (`1`, `3`, `5`, `7`)
- `shopping_mode` (`fresh`, `balanced`, `bulk`)

Development-oriented optional fields:

- `candidate_count`
- `enable_model_candidates`
- `model_candidate_count`
- `candidate_generator_backend`
- `debug_candidate_generation`
- `debug_scorer`
- `scorer_model_path`
- `candidate_generator_model_path`

Example request:

```bash
curl -X POST http://localhost:8000/api/recommendations/generic \
  -H 'Content-Type: application/json' \
  -d '{
    "location": {"lat": 37.401, "lon": -122.09},
    "targets": {
      "protein": 130,
      "energy_fibre_kcal": 2100,
      "carbohydrate": 240,
      "fat": 70,
      "fiber": 30
    },
    "preferences": {
      "vegetarian": false,
      "dairy_free": false,
      "vegan": false,
      "budget_friendly": false,
      "meal_style": "any"
    },
    "pantry_items": ["oats"],
    "store_limit": 5,
    "days": 3,
    "shopping_mode": "balanced"
  }'
```

Representative response keys:

- `shopping_list`
- `meal_suggestions`
- `nutrition_summary`
- `estimated_basket_cost`
- `estimated_basket_cost_low`
- `estimated_basket_cost_high`
- `price_source_note`
- `price_adjustment_note`
- `price_coverage_note`
- `price_confidence_note`
- `stores`
- `recommended_store_order`
- `store_fit_notes`
- `one_stop_pick`
- `budget_pick`
- `produce_pick`
- `bulk_pick`
- `goal_profile`
- `selected_candidate_source`
- `selected_candidate_sources`
- `selected_candidate_id`
- `candidate_count_considered`
- `hybrid_planner_algorithm`
- `hybrid_planner_execution`

Notes:

- production responses remove planner debug details and model/backend paths
- non-production requests can expose `candidate_generation_debug`, `scoring_debug`, and `candidate_comparison_debug` when enabled
- the current frontend only surfaces the developer controls when `/generic?developer=1` is used

## Origin And Attribution

This repository appears to be derived from earlier diet-optimization work, but the exact lineage cannot be fully proven from the current code alone.

Signals visible in this workspace:

- the package name in `pyproject.toml` is `diet-optimization`
- the Fly.io app name is `diet-optimization-main`
- the `/about` page links to `https://github.com/albertaillet/diet-optimization`
- `data/data.db` still contains legacy tables from broader earlier work alongside the current generic-planner tables

Reference mentioned in the codebase:

- https://github.com/albertaillet/diet-optimization

What can and cannot be claimed from local evidence:

- it is reasonable to say this project appears to have evolved from earlier diet-optimization work
- it would not be accurate to claim a fully verified upstream lineage from the current source tree alone
- this local workspace does contain `.git` metadata and a current remote pointing at `https://github.com/Yinghan-Sun/Generic-grocery-planner.git`
- there is no top-level `LICENSE` file in the current working tree
- there is a `NOTICE` file, but it is specifically about Foursquare OS Places attribution and does not establish an overall project license

## Practical Summary

If you only want to run the app:

```bash
uv sync --extra ml
uv run python -m dietdashboard.app
```

If you want the production-like container path:

```bash
docker build . -t diet-dashboard -f Containerfile
docker run --rm -p 8000:8000 diet-dashboard
```

If you want to edit the frontend:

```bash
make run-dev
```

If you want to retrain or rebuild data, start in `Makefile` and expect that some raw rebuild inputs are not included in this checkout.
