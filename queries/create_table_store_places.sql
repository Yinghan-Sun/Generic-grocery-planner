-- Normalized local seed data for nearby-store lookup in the MVP.

CREATE OR REPLACE TABLE store_places AS (
  SELECT
    CONCAT(src.source, ':', src.source_place_id) AS store_id,
    src.source,
    src.source_place_id,
    src.name,
    src.brand,
    COALESCE(NULLIF(src.chain_name, ''), NULLIF(src.brand, ''), src.name) AS chain_name,
    src.category_primary,
    CAST(src.lat AS DOUBLE) AS lat,
    CAST(src.lon AS DOUBLE) AS lon,
    src.address_line,
    src.city,
    src.region,
    src.postcode,
    UPPER(src.country_code) AS country_code,
    src.website,
    lower(src.category_primary) IN ('supermarket', 'grocery_store') AS is_grocery,
    lower(src.category_primary) = 'supermarket' AS is_supermarket
  FROM read_csv_auto('data/store_places_seed.csv', header = TRUE, delim = ',') AS src
);

COMMENT ON TABLE store_places IS 'Normalized nearby-store seed data for the generic-food MVP';
