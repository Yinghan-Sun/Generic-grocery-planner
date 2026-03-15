-- Ingest BLS average-price CSV files and materialize a normalized monthly price table.

CREATE OR REPLACE TABLE bls_ap_item AS (
  SELECT
    TRIM(item_code) AS item_code,
    item_name
  FROM read_csv_auto('data/bls/ap.item.csv', header = TRUE)
);

CREATE OR REPLACE TABLE bls_ap_series AS (
  SELECT
    TRIM(series_id) AS series_id,
    TRIM(area_code) AS area_code,
    TRIM(item_code) AS item_code,
    series_title,
    footnote_codes,
    CAST(begin_year AS INTEGER) AS begin_year,
    begin_period,
    CAST(end_year AS INTEGER) AS end_year,
    end_period
  FROM read_csv_auto('data/bls/ap.series.csv', header = TRUE)
);

CREATE OR REPLACE TABLE bls_ap_data_food AS (
  SELECT
    TRIM(series_id) AS series_id,
    CAST(year AS INTEGER) AS year,
    TRIM(period) AS period,
    TRY_CAST(NULLIF(TRIM(value), '-') AS DOUBLE) AS value,
    footnote_codes
  FROM read_csv_auto('data/bls/ap.data.3.Food.csv', header = TRUE)
);

CREATE OR REPLACE TABLE bls_average_prices AS (
WITH monthly AS (
  SELECT
    d.series_id,
    s.area_code,
    s.item_code,
    i.item_name,
    d.year,
    d.period,
    CAST(SUBSTR(d.period, 2, 2) AS INTEGER) AS period_month,
    d.value,
    s.series_title
  FROM bls_ap_data_food AS d
  JOIN bls_ap_series AS s USING (series_id)
  JOIN bls_ap_item AS i USING (item_code)
  WHERE d.period LIKE 'M%'
    AND d.period <> 'M13'
    AND d.value IS NOT NULL
)
SELECT
  series_id,
  area_code,
  item_code,
  item_name,
  year,
  period,
  period_month,
  value,
  series_title
FROM monthly
ORDER BY item_code, year, period_month
);

COMMENT ON TABLE bls_average_prices IS 'Monthly BLS average food prices enriched with item names from local BLS CSV extracts';
