-- Ingest staged USDA Food-at-Home Monthly Area Prices extracts, materialize
-- generic-food price references by USDA area, and inflation-adjust them with the
-- local BLS Food-at-Home CPI snapshot.

CREATE OR REPLACE TABLE usda_food_area_prices_raw AS (
  SELECT
    source_file,
    source_sheet,
    CAST(row_number AS INTEGER) AS row_number,
    CAST(year AS INTEGER) AS year,
    TRIM(CAST(month AS VARCHAR)) AS month,
    TRIM(CAST(area_code AS VARCHAR)) AS area_code,
    TRIM(CAST(area_name AS VARCHAR)) AS area_name,
    TRIM(CAST(food_code AS VARCHAR)) AS food_code,
    TRIM(CAST(food_name AS VARCHAR)) AS food_name,
    TRY_CAST(purchase_dollars_wtd AS DOUBLE) AS purchase_dollars_wtd,
    TRY_CAST(purchase_grams_wtd AS DOUBLE) AS purchase_grams_wtd,
    TRY_CAST(store_count AS INTEGER) AS store_count,
    TRY_CAST(unit_value_mean_wtd AS DOUBLE) AS unit_value_mean_wtd,
    TRY_CAST(unit_value_mean_unwtd AS DOUBLE) AS unit_value_mean_unwtd,
    TRY_CAST(unit_value_se_wtd AS DOUBLE) AS unit_value_se_wtd,
    TRY_CAST(price_index_geks AS DOUBLE) AS price_index_geks,
    raw_record_json
  FROM read_csv_auto('data/usda/usda_food_area_prices_raw_staged.csv', header = TRUE)
);

CREATE OR REPLACE TABLE usda_food_area_prices AS (
  SELECT
    source_file,
    source_sheet,
    CAST(observed_year AS INTEGER) AS observed_year,
    CAST(observed_month AS INTEGER) AS observed_month,
    TRIM(CAST(observed_month_label AS VARCHAR)) AS observed_month_label,
    TRIM(CAST(observed_at AS VARCHAR)) AS observed_at,
    TRIM(CAST(area_code AS VARCHAR)) AS area_code,
    TRIM(CAST(area_name AS VARCHAR)) AS area_name,
    TRIM(CAST(area_scope AS VARCHAR)) AS area_scope,
    TRIM(CAST(food_code AS VARCHAR)) AS food_code,
    TRIM(CAST(food_name AS VARCHAR)) AS food_name,
    TRIM(CAST(food_key AS VARCHAR)) AS food_key,
    TRY_CAST(purchase_dollars_wtd AS DOUBLE) AS purchase_dollars_wtd,
    TRY_CAST(purchase_grams_wtd AS DOUBLE) AS purchase_grams_wtd,
    TRY_CAST(store_count AS INTEGER) AS store_count,
    TRY_CAST(unit_value_mean_wtd AS DOUBLE) AS unit_value_mean_wtd,
    TRY_CAST(unit_value_mean_unwtd AS DOUBLE) AS unit_value_mean_unwtd,
    TRY_CAST(unit_value_se_wtd AS DOUBLE) AS unit_value_se_wtd,
    TRY_CAST(price_index_geks AS DOUBLE) AS price_index_geks,
    TRY_CAST(normalized_price_per_100g AS DOUBLE) AS normalized_price_per_100g
  FROM read_csv_auto('data/usda/usda_food_area_prices_normalized.csv', header = TRUE)
);

CREATE OR REPLACE TABLE generic_food_usda_map AS (
  SELECT
    TRIM(generic_food_id) AS generic_food_id,
    TRIM(usda_food_key) AS usda_food_key,
    TRIM(usda_food_name) AS usda_food_name,
    CAST(weight AS DOUBLE) AS weight,
    CAST(is_primary AS BOOL) AS is_primary,
    CAST(sort_order AS INTEGER) AS sort_order,
    TRIM(mapping_note) AS mapping_note
  FROM read_csv_auto('data/generic_food_usda_map.csv', header = TRUE)
);

CREATE OR REPLACE TABLE usda_price_areas AS (
  SELECT DISTINCT
    area_code,
    area_name,
    area_scope
  FROM usda_food_area_prices
  ORDER BY area_scope, area_name, area_code
);

CREATE OR REPLACE TABLE food_cpi_adjustment_context AS (
WITH usda_base AS (
  SELECT MAX(observed_at) AS usda_base_observed_at
  FROM usda_food_area_prices
),
base_cpi AS (
  SELECT
    observed_at AS cpi_base_observed_at,
    cpi_value AS cpi_base_value
  FROM food_cpi_index, usda_base
  WHERE observed_at <= usda_base_observed_at
  QUALIFY ROW_NUMBER() OVER (ORDER BY observed_year DESC, observed_month DESC) = 1
),
current_cpi AS (
  SELECT
    observed_at AS cpi_current_observed_at,
    cpi_value AS cpi_current_value
  FROM food_cpi_index
  QUALIFY ROW_NUMBER() OVER (ORDER BY observed_year DESC, observed_month DESC) = 1
)
SELECT
  COALESCE(usda_base.usda_base_observed_at, current_cpi.cpi_current_observed_at) AS usda_base_observed_at,
  base_cpi.cpi_base_observed_at,
  base_cpi.cpi_base_value,
  current_cpi.cpi_current_observed_at,
  current_cpi.cpi_current_value,
  COALESCE(current_cpi.cpi_current_value / NULLIF(base_cpi.cpi_base_value, 0), 1.0) AS inflation_multiplier,
  'CUUR0000SAF11' AS cpi_series_id,
  'BLS CPI Food at home, U.S. city average, not seasonally adjusted' AS cpi_series_name
FROM usda_base
CROSS JOIN current_cpi
LEFT JOIN base_cpi ON TRUE
);

CREATE OR REPLACE TABLE generic_food_usda_prices_by_area AS (
WITH latest_usda AS (
  SELECT
    area_code,
    area_name,
    area_scope,
    food_code,
    food_name,
    food_key,
    observed_year,
    observed_month,
    observed_month_label,
    observed_at,
    normalized_price_per_100g,
    ROW_NUMBER() OVER (
      PARTITION BY area_code, food_key
      ORDER BY observed_year DESC, observed_month DESC, source_file, source_sheet
    ) AS rn
  FROM usda_food_area_prices
  WHERE normalized_price_per_100g IS NOT NULL
),
latest_items AS (
  SELECT
    area_code,
    area_name,
    area_scope,
    food_code,
    food_name,
    food_key,
    observed_year,
    observed_month,
    observed_month_label,
    observed_at,
    normalized_price_per_100g
  FROM latest_usda
  WHERE rn = 1
),
weighted AS (
  SELECT
    m.generic_food_id,
    li.area_code,
    MIN_BY(li.area_name, m.sort_order) AS area_name,
    MIN_BY(li.area_scope, m.sort_order) AS area_scope,
    COUNT(*) AS mapped_item_count,
    SUM(m.weight) AS total_weight,
    SUM(li.normalized_price_per_100g * m.weight) / SUM(m.weight) AS base_estimated_unit_price,
    'per 100 g' AS price_unit_display,
    'weight_g' AS price_basis_kind,
    100.0 AS price_basis_value,
    MIN_BY(li.food_key, m.sort_order) AS food_key,
    MIN_BY(li.food_name, m.sort_order) AS food_name,
    STRING_AGG(li.food_key, ', ' ORDER BY m.sort_order) AS mapped_food_keys,
    STRING_AGG(li.food_name, '; ' ORDER BY m.sort_order) AS mapped_food_names,
    MAX(li.observed_year) AS observed_year,
    MAX_BY(li.observed_month, li.observed_year * 100 + li.observed_month) AS observed_month,
    MAX_BY(li.observed_month_label, li.observed_year * 100 + li.observed_month) AS observed_month_label,
    MAX_BY(li.observed_at, li.observed_year * 100 + li.observed_month) AS observed_at
  FROM generic_food_usda_map AS m
  JOIN latest_items AS li
    ON LOWER(TRIM(m.usda_food_key)) = LOWER(TRIM(li.food_key))
  GROUP BY m.generic_food_id, li.area_code
)
SELECT
  w.generic_food_id,
  w.area_code,
  w.area_name,
  w.area_scope,
  w.mapped_item_count,
  w.food_key,
  w.food_name,
  w.mapped_food_keys,
  w.mapped_food_names,
  w.observed_year,
  w.observed_month,
  w.observed_month_label,
  w.observed_at,
  w.base_estimated_unit_price,
  ROUND(w.base_estimated_unit_price * COALESCE(c.inflation_multiplier, 1.0), 6) AS estimated_unit_price,
  w.price_unit_display,
  w.price_basis_kind,
  w.price_basis_value,
  c.usda_base_observed_at,
  c.cpi_base_observed_at,
  c.cpi_base_value,
  c.cpi_current_observed_at,
  c.cpi_current_value,
  COALESCE(c.inflation_multiplier, 1.0) AS inflation_multiplier,
  c.cpi_series_id,
  c.cpi_series_name
FROM weighted AS w
LEFT JOIN food_cpi_adjustment_context AS c ON TRUE
ORDER BY w.area_scope, w.area_code, w.generic_food_id
);

COMMENT ON TABLE usda_food_area_prices_raw IS 'Locally staged USDA Food-at-Home Monthly Area Prices raw rows extracted from offline files';
COMMENT ON TABLE usda_food_area_prices IS 'Normalized USDA Food-at-Home Monthly Area Prices rows with one area, month, and food group per row';
COMMENT ON TABLE generic_food_usda_map IS 'Approximate mappings from generic foods to USDA Food-at-Home Monthly Area Prices food groups';
COMMENT ON TABLE usda_price_areas IS 'Distinct USDA Food-at-Home Monthly Area Prices areas present in the locally staged data';
COMMENT ON TABLE food_cpi_adjustment_context IS 'Single-row CPI adjustment context used to scale historical USDA food-area prices toward the latest local CPI month';
COMMENT ON TABLE generic_food_usda_prices_by_area IS 'Area-aware generic-food price references from the latest local USDA Food-at-Home Monthly Area Prices rows, inflation-adjusted with local BLS food-at-home CPI';
