-- Map generic foods to local BLS average-price items and materialize coarse price references.

CREATE OR REPLACE TABLE generic_food_bls_map AS (
  SELECT
    TRIM(generic_food_id) AS generic_food_id,
    TRIM(item_code) AS item_code,
    CAST(weight AS DOUBLE) AS weight,
    CAST(is_primary AS BOOL) AS is_primary,
    CAST(sort_order AS INTEGER) AS sort_order
  FROM read_csv_auto('data/generic_food_bls_map.csv', header = TRUE)
);

CREATE OR REPLACE TABLE bls_price_areas AS (
  SELECT
    area_code,
    COALESCE(NULLIF(TRIM(REGEXP_EXTRACT(MIN(series_title), '.* in (.*), average price.*', 1)), ''), 'Unknown area') AS area_name
  FROM bls_average_prices
  GROUP BY area_code
);

CREATE OR REPLACE TABLE generic_food_prices_by_area AS (
WITH latest_bls AS (
  SELECT
    series_id,
    area_code,
    item_code,
    item_name,
    year,
    period,
    value,
    ROW_NUMBER() OVER (PARTITION BY area_code, item_code ORDER BY year DESC, period_month DESC, series_id) AS rn
  FROM bls_average_prices
),
latest_items AS (
  SELECT
    area_code,
    item_code,
    series_id,
    item_name,
    year,
    period,
    value
  FROM latest_bls
  WHERE rn = 1
),
normalized AS (
  SELECT
    li.*,
    a.area_name,
    CASE
      WHEN LOWER(li.item_name) LIKE '%per doz.%' THEN 'count'
      WHEN LOWER(li.item_name) LIKE '%per 1/2 gal.%' OR LOWER(li.item_name) LIKE '%per gal.%' THEN 'volume_liter'
      WHEN LOWER(li.item_name) LIKE '%per 8 oz.%' OR LOWER(li.item_name) LIKE '%per 16 oz.%' OR LOWER(li.item_name) LIKE '%per lb.%'
        OR LOWER(li.item_name) LIKE '%cost per pound/453.6 grams%' THEN 'weight_g'
      ELSE NULL
    END AS price_basis_kind,
    CASE
      WHEN LOWER(li.item_name) LIKE '%per doz.%' THEN 12.0
      WHEN LOWER(li.item_name) LIKE '%per 1/2 gal.%' THEN COALESCE(TRY_CAST(NULLIF(REGEXP_EXTRACT(LOWER(li.item_name), '\\(([0-9.]+) lit\\)', 1), '') AS DOUBLE), 1.9)
      WHEN LOWER(li.item_name) LIKE '%per gal.%' THEN COALESCE(TRY_CAST(NULLIF(REGEXP_EXTRACT(LOWER(li.item_name), '\\(([0-9.]+) lit\\)', 1), '') AS DOUBLE), 3.8)
      WHEN LOWER(li.item_name) LIKE '%per 8 oz.%' THEN COALESCE(TRY_CAST(NULLIF(REGEXP_EXTRACT(LOWER(li.item_name), '\\(([0-9.]+) gm\\)', 1), '') AS DOUBLE), 226.8)
      WHEN LOWER(li.item_name) LIKE '%per 16 oz.%' THEN 453.6
      WHEN LOWER(li.item_name) LIKE '%per lb.%' THEN COALESCE(TRY_CAST(NULLIF(REGEXP_EXTRACT(LOWER(li.item_name), '\\(([0-9.]+) gm\\)', 1), '') AS DOUBLE), 453.6)
      WHEN LOWER(li.item_name) LIKE '%cost per pound/453.6 grams%' THEN 453.6
      ELSE NULL
    END AS price_basis_value,
    CASE
      WHEN LOWER(li.item_name) LIKE '%per doz.%' THEN 'per dozen'
      WHEN LOWER(li.item_name) LIKE '%per 1/2 gal.%' THEN 'per 1/2 gallon'
      WHEN LOWER(li.item_name) LIKE '%per gal.%' THEN 'per gallon'
      WHEN LOWER(li.item_name) LIKE '%per 8 oz.%' THEN 'per 8 oz'
      WHEN LOWER(li.item_name) LIKE '%per 16 oz.%' THEN 'per 16 oz'
      WHEN LOWER(li.item_name) LIKE '%per lb.%' OR LOWER(li.item_name) LIKE '%cost per pound/453.6 grams%' THEN 'per lb'
      ELSE 'per unit'
    END AS price_unit_display
  FROM latest_items AS li
  LEFT JOIN bls_price_areas AS a USING (area_code)
),
weighted AS (
  SELECT
    m.generic_food_id,
    n.area_code,
    MIN_BY(n.area_name, m.sort_order) AS area_name,
    COUNT(*) AS mapped_item_count,
    SUM(m.weight) AS total_weight,
    SUM(n.value * m.weight) / SUM(m.weight) AS estimated_unit_price,
    MIN_BY(n.price_unit_display, m.sort_order) AS price_unit_display,
    MIN_BY(n.price_basis_kind, m.sort_order) AS price_basis_kind,
    MIN_BY(n.price_basis_value, m.sort_order) AS price_basis_value,
    MIN_BY(n.series_id, m.sort_order) AS series_id,
    MIN_BY(n.item_code, m.sort_order) AS item_code,
    MIN_BY(n.item_name, m.sort_order) AS item_name,
    MAX(n.year) AS latest_year,
    MIN_BY(n.period, m.sort_order) AS latest_period,
    STRING_AGG(n.item_code, ', ' ORDER BY m.sort_order) AS mapped_item_codes,
    STRING_AGG(n.item_name, '; ' ORDER BY m.sort_order) AS mapped_item_names
  FROM generic_food_bls_map AS m
  JOIN normalized AS n USING (item_code)
  GROUP BY m.generic_food_id, n.area_code
)
SELECT
  generic_food_id,
  area_code,
  area_name,
  mapped_item_count,
  series_id,
  item_code,
  item_name,
  mapped_item_codes,
  mapped_item_names,
  latest_year,
  latest_period,
  estimated_unit_price,
  price_unit_display,
  price_basis_kind,
  price_basis_value
FROM weighted
ORDER BY area_code, generic_food_id
);

CREATE OR REPLACE TABLE generic_food_prices AS (
SELECT
  generic_food_id,
  area_code,
  area_name,
  mapped_item_count,
  series_id,
  item_code,
  item_name,
  mapped_item_codes,
  mapped_item_names,
  latest_year,
  latest_period,
  estimated_unit_price,
  price_unit_display,
  price_basis_kind,
  price_basis_value
FROM generic_food_prices_by_area
WHERE area_code = '0'
ORDER BY generic_food_id
);

COMMENT ON TABLE generic_food_prices IS 'Coarse generic-food price references from the latest local BLS average-price rows';
COMMENT ON TABLE generic_food_prices_by_area IS 'Coarse generic-food price references by BLS food-price area, with one latest row per area and mapped generic food';
