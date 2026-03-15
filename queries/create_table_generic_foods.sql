-- Materialized generic food catalog for the MVP recommendation engine.

CREATE OR REPLACE TABLE generic_food_catalog AS (
  SELECT
    src.generic_food_id,
    src.display_name,
    src.food_family,
    CAST(src.default_serving_g AS FLOAT) AS default_serving_g,
    src.purchase_unit,
    CAST(src.purchase_unit_size_g AS FLOAT) AS purchase_unit_size_g,
    CAST(src.vegetarian AS BOOL) AS vegetarian,
    CAST(src.vegan AS BOOL) AS vegan,
    CAST(src.dairy_free AS BOOL) AS dairy_free,
    CAST(src.gluten_free AS BOOL) AS gluten_free,
    CAST(src.high_protein AS BOOL) AS high_protein,
    CAST(src.breakfast_friendly AS BOOL) AS breakfast_friendly,
    src.meal_type,
    src.prep_level,
    src.shelf_stability,
    CAST(src.budget_score AS INTEGER) AS budget_score,
    CAST(src.shelf_stable AS BOOL) AS shelf_stable,
    CAST(src.cold_only AS BOOL) AS cold_only,
    CAST(src.microwave_friendly AS BOOL) AS microwave_friendly,
    CAST(src.commonality_rank AS INTEGER) AS commonality_rank,
    src.notes
  FROM read_csv_auto('data/generic_food_catalog.csv', header = TRUE, delim = ',') AS src
);

CREATE OR REPLACE TABLE generic_food_source_map AS (
  SELECT
    src.generic_food_id,
    CAST(src.ciqual_food_code AS BIGINT) AS ciqual_food_code,
    CAST(src.weight AS DOUBLE) AS weight,
    CAST(src.is_primary AS BOOL) AS is_primary,
    CAST(src.sort_order AS INTEGER) AS sort_order
  FROM read_csv_auto('data/generic_food_source_map.csv', header = TRUE, delim = ',') AS src
);

CREATE OR REPLACE TABLE generic_foods AS (
WITH
weighted AS (
  SELECT
    m.generic_food_id,
    COUNT(*) AS source_food_count,
    SUM(m.weight) AS total_weight,
    SUM(b.energy_fibre_kcal * m.weight) / SUM(m.weight) AS energy_fibre_kcal,
    SUM(b.protein * m.weight) / SUM(m.weight) AS protein,
    SUM(b.carbohydrate * m.weight) / SUM(m.weight) AS carbohydrate,
    SUM(b.fat * m.weight) / SUM(m.weight) AS fat,
    SUM(b.fiber * m.weight) / SUM(m.weight) AS fiber,
    SUM(b.sugars * m.weight) / SUM(m.weight) AS sugars,
    SUM(b.sodium * m.weight) / SUM(m.weight) AS sodium,
    SUM(b.calcium * m.weight) / SUM(m.weight) AS calcium,
    SUM(b.iron * m.weight) / SUM(m.weight) AS iron,
    SUM(b.vitamin_c * m.weight) / SUM(m.weight) AS vitamin_c,
    STRING_AGG(CAST(m.ciqual_food_code AS VARCHAR), ', ' ORDER BY m.sort_order) AS source_food_codes,
    STRING_AGG(b.food_name, '; ' ORDER BY m.sort_order) AS source_food_names
  FROM generic_food_source_map AS m
  JOIN food_nutrition_base AS b ON m.ciqual_food_code = b.ciqual_food_code
  GROUP BY m.generic_food_id
),
primary_source AS (
  SELECT
    m.generic_food_id,
    m.ciqual_food_code AS primary_source_food_code,
    b.food_name AS primary_source_food_name
  FROM generic_food_source_map AS m
  JOIN food_nutrition_base AS b ON m.ciqual_food_code = b.ciqual_food_code
  WHERE m.is_primary
)
SELECT
  c.generic_food_id,
  c.display_name,
  c.food_family,
  c.default_serving_g,
  c.purchase_unit,
  c.purchase_unit_size_g,
  c.vegetarian,
  c.vegan,
  c.dairy_free,
  c.gluten_free,
  c.high_protein,
  c.breakfast_friendly,
  c.meal_type,
  c.prep_level,
  c.shelf_stability,
  c.budget_score,
  c.shelf_stable,
  c.cold_only,
  c.microwave_friendly,
  c.commonality_rank,
  c.notes,
  p.primary_source_food_code,
  p.primary_source_food_name,
  w.source_food_count,
  w.source_food_codes,
  w.source_food_names,
  w.energy_fibre_kcal,
  w.protein,
  w.carbohydrate,
  w.fat,
  w.fiber,
  w.sugars,
  w.sodium,
  w.calcium,
  w.iron,
  w.vitamin_c,
  ROUND(LEAST(w.protein / 10.0, 5.0), 2) AS protein_density_score,
  ROUND(LEAST(w.fiber / 4.0, 5.0), 2) AS fiber_score,
  ROUND(LEAST(w.calcium / 200.0, 5.0), 2) AS calcium_score,
  ROUND(LEAST(w.iron / 3.0, 5.0), 2) AS iron_score,
  ROUND(LEAST(w.vitamin_c / 20.0, 5.0), 2) AS vitamin_c_score
FROM generic_food_catalog AS c
JOIN weighted AS w USING (generic_food_id)
LEFT JOIN primary_source AS p USING (generic_food_id)
ORDER BY c.commonality_rank, c.display_name
);

COMMENT ON TABLE generic_foods IS 'Curated generic-food catalog with approximate nutrient values for the MVP recommender';
