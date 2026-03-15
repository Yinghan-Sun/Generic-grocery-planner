-- Ingest a local BLS CPI Food-at-Home snapshot and expose a simple inflation context
-- for adjusting historical USDA Food-at-Home Monthly Area Prices toward current levels.

CREATE OR REPLACE TABLE food_cpi_index AS (
  SELECT
    TRIM(CAST(series_id AS VARCHAR)) AS series_id,
    TRIM(CAST(series_title AS VARCHAR)) AS series_title,
    CAST(observed_year AS INTEGER) AS observed_year,
    CAST(observed_month AS INTEGER) AS observed_month,
    TRIM(CAST(period AS VARCHAR)) AS period,
    TRIM(CAST(period_name AS VARCHAR)) AS period_name,
    TRIM(CAST(observed_at AS VARCHAR)) AS observed_at,
    TRY_CAST(cpi_value AS DOUBLE) AS cpi_value,
    TRIM(CAST(footnotes_json AS VARCHAR)) AS footnotes_json
  FROM read_csv_auto('data/bls/cpi_food_at_home.csv', header = TRUE)
);

COMMENT ON TABLE food_cpi_index IS 'Local BLS CPI Food-at-Home monthly index snapshot used to inflation-adjust historical USDA food-area prices';
