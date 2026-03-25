SHELL := /bin/sh

.PHONY: \
	rm-data-db rm-store-discovery-db rm-db \
	build-generic-data create-table-food-nutrition-base create-table-generic-foods \
	create-table-bls-average-prices create-table-generic-food-prices \
	fetch-food-cpi create-table-food-cpi-index create-table-usda-food-area-prices create-table-store-places \
	open-db \
	smoke-generic test-generic test-generic-behavior check-generic-catalog check-generic-price-coverage qa-generic \
	store-discovery-summary store-discovery-prune-cache store-discovery-dedupe-live backfill-generic-stores ingest-foursquare-stores ingest-foursquare-os-places \
	build-food-role-dataset train-food-role-model \
	build-candidate-generator-dataset tune-candidate-generator train-candidate-generator evaluate-hybrid-planner \
	compare-preset-model-participation compare-preset-model-participation-final compare-plan-scorers \
	build-plan-scorer-dataset train-plan-scorer test-plan-scorer \
	route-b-ablation route-b-robustness route-b-final-summary route-b-final-evidence route-b-presentation-assets \
	run-app run-dev \
	frontend-bundle frontend-watch frontend-copy \
	build-container run-container

DATA_DB := data/data.db
STORE_DISCOVERY_DB := data/store_discovery.db
CALNUT_0_CSV := data/calnut.0.csv
CALNUT_1_CSV := data/calnut.1.csv
GENERIC_FOOD_CATALOG_CSV := data/generic_food_catalog.csv
GENERIC_FOOD_SOURCE_MAP_CSV := data/generic_food_source_map.csv
GENERIC_FOOD_BLS_MAP_CSV := data/generic_food_bls_map.csv
GENERIC_FOOD_USDA_MAP_CSV := data/generic_food_usda_map.csv
STORE_PLACES_SEED_CSV := data/store_places_seed.csv
BLS_PRICE_DATA_CSV := data/bls/ap.data.3.Food.csv
BLS_ITEM_CSV := data/bls/ap.item.csv
BLS_SERIES_CSV := data/bls/ap.series.csv
BLS_CPI_FOOD_CSV := data/bls/cpi_food_at_home.csv

rm-data-db:
	rm -f $(DATA_DB)

rm-store-discovery-db:
	rm -f $(STORE_DISCOVERY_DB)

rm-db: rm-data-db rm-store-discovery-db

$(DATA_DB): data/nutrient_map.csv data/ciqual2020/alim.csv data/ciqual2020/compo.csv \
	  $(CALNUT_0_CSV) $(CALNUT_1_CSV) \
	  $(GENERIC_FOOD_CATALOG_CSV) $(GENERIC_FOOD_SOURCE_MAP_CSV) \
	  $(GENERIC_FOOD_BLS_MAP_CSV) $(GENERIC_FOOD_USDA_MAP_CSV) $(STORE_PLACES_SEED_CSV) \
	  $(BLS_PRICE_DATA_CSV) $(BLS_ITEM_CSV) $(BLS_SERIES_CSV) $(BLS_CPI_FOOD_CSV)
	duckdb $(DATA_DB) < ./queries/load_generic.sql
	$(MAKE) create-table-food-nutrition-base create-table-generic-foods \
		create-table-bls-average-prices create-table-generic-food-prices \
		create-table-food-cpi-index create-table-usda-food-area-prices create-table-store-places

build-generic-data: $(DATA_DB)

create-table-food-nutrition-base:
	duckdb $(DATA_DB) < ./queries/create_table_food_nutrition_base.sql

create-table-generic-foods:
	duckdb $(DATA_DB) < ./queries/create_table_generic_foods.sql

create-table-bls-average-prices:
	duckdb $(DATA_DB) < ./queries/create_table_bls_average_prices.sql

create-table-generic-food-prices:
	duckdb $(DATA_DB) < ./queries/create_table_generic_food_prices.sql

fetch-food-cpi:
	UV_CACHE_DIR=$${UV_CACHE_DIR:-/tmp/uv-cache} uv run python ./scripts/fetch_bls_food_cpi.py

create-table-food-cpi-index:
	duckdb $(DATA_DB) < ./queries/create_table_food_cpi_index.sql

create-table-usda-food-area-prices:
	$(MAKE) create-table-food-cpi-index
	UV_CACHE_DIR=$${UV_CACHE_DIR:-/tmp/uv-cache} uv run python ./scripts/prepare_usda_food_area_prices.py
	duckdb $(DATA_DB) < ./queries/create_table_usda_food_area_prices.sql

create-table-store-places:
	duckdb $(DATA_DB) < ./queries/create_table_store_places.sql

open-db: $(DATA_DB)
	duckdb -readonly $(DATA_DB)

smoke-generic:
	uv run ./scripts/generic_smoke_test.py

test-generic: smoke-generic test-generic-behavior test-plan-scorer

test-generic-behavior:
	uv run ./scripts/generic_behavior_test.py

test-plan-scorer:
	uv run --extra ml ./scripts/hybrid_planner_test.py

check-generic-catalog:
	uv run python ./scripts/generic_catalog_admin.py

check-generic-price-coverage:
	uv run python ./scripts/generic_price_coverage_admin.py

qa-generic: test-generic check-generic-catalog check-generic-price-coverage store-discovery-summary

store-discovery-summary:
	uv run python ./scripts/store_discovery_admin.py summary

store-discovery-prune-cache:
	uv run python ./scripts/store_discovery_admin.py prune-cache

store-discovery-dedupe-live:
	uv run python ./scripts/store_discovery_admin.py dedupe-live

backfill-generic-stores:
	uv run python ./scripts/backfill_generic_stores.py

FOURSQUARE_INPUT ?= ./data/foursquare_places_sample.csv
FOURSQUARE_OS_INPUT ?= ./data/foursquare_os/foursquare_os_places_grocery_metros.parquet

ingest-foursquare-stores:
	uv run python ./scripts/ingest_foursquare_stores.py --input $(FOURSQUARE_INPUT)

ingest-foursquare-os-places:
	uv run python ./scripts/ingest_foursquare_stores.py --input $(FOURSQUARE_OS_INPUT) --source foursquare_os_places

build-food-role-dataset:
	uv run --extra ml python ./scripts/build_food_role_training_dataset.py

train-food-role-model:
	uv run --extra ml python ./scripts/train_food_role_model.py

build-candidate-generator-dataset:
	uv run --extra ml python ./scripts/build_candidate_generator_dataset.py

tune-candidate-generator:
	uv run --extra ml python ./scripts/tune_candidate_generator.py

train-candidate-generator:
	uv run --extra ml python ./scripts/train_candidate_generator.py

evaluate-hybrid-planner:
	uv run --extra ml python ./scripts/evaluate_hybrid_planner.py

compare-preset-model-participation:
	uv run --extra ml python ./scripts/compare_preset_model_participation.py

compare-preset-model-participation-final: compare-preset-model-participation

compare-plan-scorers:
	uv run --extra ml python ./scripts/compare_plan_scorers.py

route-b-ablation:
	uv run --extra ml python ./scripts/run_route_b_ablation.py

route-b-robustness:
	uv run --extra ml python ./scripts/run_route_b_robustness.py

route-b-final-summary:
	uv run --extra ml python ./scripts/generate_route_b_final_summary.py

route-b-final-evidence: compare-preset-model-participation-final route-b-ablation route-b-robustness route-b-final-summary

route-b-presentation-assets: route-b-final-evidence
	uv run --extra ml python ./scripts/generate_route_b_presentation_assets.py

build-plan-scorer-dataset:
	uv run --extra ml python ./scripts/train_plan_scorer.py --candidate-count 3 --backend sklearn_ridge --n-estimators 40 --max-depth 2

train-plan-scorer:
	uv run --extra ml python ./scripts/train_plan_scorer.py

run-app:
	uv run python -m dietdashboard.app

run-dev:
	@trap "kill 0" EXIT; \
		make frontend-watch & \
		make run-app & \
	wait

frontend-bundle:
	cd dietdashboard/frontend && ./bundle.sh

frontend-watch:
	cd dietdashboard/frontend && ./bundle.sh watch

frontend-copy:
	uv run files-to-prompt dietdashboard/frontend \
	-e js -e css -e html \
	--ignore node_modules \
	--cxml

build-container: frontend-bundle
	docker build . -t app-container -f Containerfile

run-container:
	docker run --rm -p 8000:8000 app-container
