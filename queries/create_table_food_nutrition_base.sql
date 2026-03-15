-- Price-free nutrition base for generic food recommendations.
-- One row per source food code with a small set of nutrients needed by the MVP.

CREATE OR REPLACE TABLE food_nutrition_base AS (
WITH
base_foods AS (
  SELECT alim_code AS ciqual_food_code FROM ciqual_alim
    UNION
  SELECT ALIM_CODE AS ciqual_food_code FROM calnut_0
),
selected_nutrients AS (
  SELECT
    bf.ciqual_food_code,
    nm.id AS nutrient_id,
    nm.ciqual_const_code,
    nm.ciqual_unit,
    nm.calnut_const_code,
    nm.calnut_unit
  FROM base_foods AS bf
  JOIN nutrient_map AS nm ON nm.id IN (
    'energy_fibre_kcal',
    'protein',
    'carbohydrate',
    'fat',
    'fiber',
    'sugars',
    'sodium',
    'calcium',
    'iron',
    'vitamin_c'
  )
),
ciqual_best AS (
  SELECT * EXCLUDE (rn) FROM (
    SELECT
      *,
      ROW_NUMBER() OVER (
        PARTITION BY alim_code, const_code
        ORDER BY
          CASE code_confiance WHEN 'A' THEN 1 WHEN 'B' THEN 2 WHEN 'C' THEN 3 ELSE 4 END,
          source_code
      ) AS rn
    FROM ciqual_compo
  )
  WHERE rn = 1
),
calnut_best AS (
  SELECT * EXCLUDE (rn) FROM (
    SELECT
      *,
      ROW_NUMBER() OVER (
        PARTITION BY ALIM_CODE, CONST_CODE
        ORDER BY combl, FOOD_LABEL
      ) AS rn
    FROM calnut_1
  )
  WHERE rn = 1
),
resolved AS (
  SELECT
    sn.ciqual_food_code,
    sn.nutrient_id,
    CASE
      WHEN ciq.mean IS NOT NULL THEN ciq.mean
      WHEN cal.mean IS NOT NULL THEN cal.mean
      ELSE 0
    END AS nutrient_value,
    CASE
      WHEN ciq.mean IS NOT NULL THEN CONCAT('ciqual_', ciq.code_confiance, '_', ciq.source_code)
      WHEN cal.mean IS NOT NULL THEN CONCAT('calnut_', CASE WHEN cal.combl THEN 'combl' ELSE 'direct' END)
      ELSE 'assumed_0'
    END AS nutrient_origin
  FROM selected_nutrients AS sn
  LEFT JOIN ciqual_best AS ciq
    ON sn.ciqual_food_code = ciq.alim_code AND sn.ciqual_const_code = ciq.const_code
  LEFT JOIN calnut_best AS cal
    ON sn.ciqual_food_code = cal.ALIM_CODE AND sn.calnut_const_code = cal.CONST_CODE
),
aggregated AS (
SELECT
  bf.ciqual_food_code,
  COALESCE(ciq.alim_nom_eng, cal.FOOD_LABEL) AS food_name,
  COALESCE(ciq.alim_grp_code, cal.alim_grp_code) AS ciqual_group_code,
  COALESCE(ciq.alim_ssgrp_code, cal.alim_ssgrp_code) AS ciqual_subgroup_code,
  COALESCE(ciq.alim_ssssgrp_code, cal.alim_ssssgrp_code) AS ciqual_subsubgroup_code,
  MAX(CASE WHEN r.nutrient_id = 'energy_fibre_kcal' THEN r.nutrient_value END) AS energy_fibre_kcal,
  MAX(CASE WHEN r.nutrient_id = 'energy_fibre_kcal' THEN r.nutrient_origin END) AS energy_fibre_kcal_origin,
  MAX(CASE WHEN r.nutrient_id = 'protein' THEN r.nutrient_value END) AS protein,
  MAX(CASE WHEN r.nutrient_id = 'protein' THEN r.nutrient_origin END) AS protein_origin,
  MAX(CASE WHEN r.nutrient_id = 'carbohydrate' THEN r.nutrient_value END) AS carbohydrate,
  MAX(CASE WHEN r.nutrient_id = 'carbohydrate' THEN r.nutrient_origin END) AS carbohydrate_origin,
  MAX(CASE WHEN r.nutrient_id = 'fat' THEN r.nutrient_value END) AS fat,
  MAX(CASE WHEN r.nutrient_id = 'fat' THEN r.nutrient_origin END) AS fat_origin,
  MAX(CASE WHEN r.nutrient_id = 'fiber' THEN r.nutrient_value END) AS fiber,
  MAX(CASE WHEN r.nutrient_id = 'fiber' THEN r.nutrient_origin END) AS fiber_origin,
  MAX(CASE WHEN r.nutrient_id = 'sugars' THEN r.nutrient_value END) AS sugars,
  MAX(CASE WHEN r.nutrient_id = 'sugars' THEN r.nutrient_origin END) AS sugars_origin,
  MAX(CASE WHEN r.nutrient_id = 'sodium' THEN r.nutrient_value END) AS sodium,
  MAX(CASE WHEN r.nutrient_id = 'sodium' THEN r.nutrient_origin END) AS sodium_origin,
  MAX(CASE WHEN r.nutrient_id = 'calcium' THEN r.nutrient_value END) AS calcium,
  MAX(CASE WHEN r.nutrient_id = 'calcium' THEN r.nutrient_origin END) AS calcium_origin,
  MAX(CASE WHEN r.nutrient_id = 'iron' THEN r.nutrient_value END) AS iron,
  MAX(CASE WHEN r.nutrient_id = 'iron' THEN r.nutrient_origin END) AS iron_origin,
  MAX(CASE WHEN r.nutrient_id = 'vitamin_c' THEN r.nutrient_value END) AS vitamin_c,
  MAX(CASE WHEN r.nutrient_id = 'vitamin_c' THEN r.nutrient_origin END) AS vitamin_c_origin
FROM base_foods AS bf
LEFT JOIN resolved AS r USING (ciqual_food_code)
LEFT JOIN ciqual_alim AS ciq ON bf.ciqual_food_code = ciq.alim_code
LEFT JOIN calnut_0 AS cal ON bf.ciqual_food_code = cal.ALIM_CODE
GROUP BY
  bf.ciqual_food_code,
  COALESCE(ciq.alim_nom_eng, cal.FOOD_LABEL),
  COALESCE(ciq.alim_grp_code, cal.alim_grp_code),
  COALESCE(ciq.alim_ssgrp_code, cal.alim_ssgrp_code),
  COALESCE(ciq.alim_ssssgrp_code, cal.alim_ssssgrp_code)
)
SELECT
  ciqual_food_code,
  food_name,
  ciqual_group_code,
  ciqual_subgroup_code,
  ciqual_subsubgroup_code,
  COALESCE(NULLIF(energy_fibre_kcal, 0), 4 * protein + 4 * carbohydrate + 9 * fat + 2 * fiber, 0) AS energy_fibre_kcal,
  CASE
    WHEN COALESCE(energy_fibre_kcal, 0) > 0 THEN energy_fibre_kcal_origin
    WHEN protein IS NOT NULL AND carbohydrate IS NOT NULL AND fat IS NOT NULL AND fiber IS NOT NULL THEN 'derived_from_macros'
    ELSE energy_fibre_kcal_origin
  END AS energy_fibre_kcal_origin,
  protein,
  protein_origin,
  carbohydrate,
  carbohydrate_origin,
  fat,
  fat_origin,
  fiber,
  fiber_origin,
  sugars,
  sugars_origin,
  sodium,
  sodium_origin,
  calcium,
  calcium_origin,
  iron,
  iron_origin,
  vitamin_c,
  vitamin_c_origin
FROM aggregated
);

COMMENT ON TABLE food_nutrition_base IS 'Price-free nutrition table keyed by CIQUAL food code for generic-food recommendations';
