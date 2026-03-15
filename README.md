# Generic Grocery Planner Demo

This repository is a generic grocery planner demo.

It turns:
- a city, address, or coordinates
- nutrition targets
- simple dietary preferences
- optional pantry inputs

into:
- nearby grocery suggestions from a local store index
- a goal-aware generic shopping list
- representative regional basket-cost guidance
- lightweight meal suggestions
- store-fit recommendations

## Demo Scope

This repo now focuses on the generic planner only.

In scope:
- the generic planner homepage at `/`
- the generic planner alias at `/generic`
- the about page at `/about`
- the generic planner APIs
- local DuckDB-backed recommendation, pricing, and store-discovery logic

Out of scope:
- the old product-price optimizer
- branded-product linear optimization
- legacy optimizer routes, SQL, and frontend assets
- any live refresh requirement for normal demo runtime

Runtime is local and deterministic. The only optional outbound lookup still used by the UI is browser-side address geocoding; entering coordinates directly avoids that step.

## Project Origin / Attribution

This demo evolved from earlier diet-optimization work.

Based on the files available in this workspace, the clearest preserved upstream reference is the historical GitHub link:
- `https://github.com/albertaillet/diet-optimization`

Important limits on what can be claimed from this local copy:
- there is no top-level `LICENSE` file in this workspace
- there is no `.git` directory here, so git remotes and commit history are not available
- because of that, upstream license and provenance details cannot be fully verified from local files alone

Recommendation:
- keep this attribution note in the repo
- preserve any upstream notice if a verified license file is restored later

## Data Strategy

### Runtime artifacts

The demo runtime expects prebuilt local artifacts:
- `data/data.db`
- `data/store_discovery.db`
- `dietdashboard/static/generic_bundle.js`
- `dietdashboard/static/bundle.css`

The two DuckDB files are the main demo deployment artifacts.

### Rebuild-only inputs

These inputs are only needed if you want to rebuild the data locally:
- `data/nutrient_map.csv`
- `data/ciqual2020/alim.csv`
- `data/ciqual2020/compo.csv`
- `data/calnut.0.csv`
- `data/calnut.1.csv`
- `data/generic_food_catalog.csv`
- `data/generic_food_source_map.csv`
- `data/generic_food_bls_map.csv`
- `data/generic_food_usda_map.csv`
- `data/store_places_seed.csv`
- `data/store_backfill_cities.csv`
- `data/bls/ap.data.3.Food.csv`
- `data/bls/ap.item.csv`
- `data/bls/ap.series.csv`
- `data/bls/cpi_food_at_home.csv`
- `data/usda/food-at-home-monthly-area-prices-2012-to-2018.zip`

### Deployment artifact strategy

The simplest demo deployment strategy is:
1. ship the prebuilt DuckDB artifacts
2. ship the built frontend static files
3. run the app locally against those files

The repo keeps `*.db` ignored by default, so those database files should be treated as explicit build or release artifacts rather than assumed source-controlled files.

## Run Locally

Dependency install:

```bash
uv sync --frozen --no-dev
```

Frontend build:

```bash
cd dietdashboard/frontend && ./bundle.sh
```

Canonical app entrypoint:

```bash
python -m dietdashboard.app
```

If you are running through `uv`, the equivalent local command is:

```bash
uv run python -m dietdashboard.app
```

Then open:

```text
http://127.0.0.1:8000/
```

## Optional Local Rebuild

If the DuckDB runtime artifacts are missing and you have the rebuild inputs above:

```bash
make build-generic-data
```

Useful checks:

```bash
make test-generic
make qa-generic
make store-discovery-summary
```

## Deployment Notes

Runtime assumptions for the demo:
- no live price refresh required
- no live store refresh required
- `STORE_DISCOVERY_MODE` defaults to `local`

Optional environment variables:
- `PROD=1`
- `STORE_DISCOVERY_MODE=local|auto|live`
- `PORT=8000` or another port if your platform sets one

For Procfile-style deploys, the app command is:

```text
python -m dietdashboard.app
```

For container deploys, the included `Containerfile` expects the prebuilt DuckDB artifacts to already be present in the build context.

## Route Summary

Page routes:
- `/`
- `/generic`
- `/about`

API routes:
- `GET /api/stores/nearby`
- `POST /api/recommendations/generic`

## Additional Docs

- [Generic Flow](docs/generic-flow.md)
- [Generic QA Checklist](docs/generic-qa-checklist.md)
