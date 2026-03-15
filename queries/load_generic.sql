/* Minimal generic-planner data load.
Loads only the nutrition-source tables needed to materialize generic foods.
*/

CREATE OR REPLACE TABLE nutrient_map AS (
  SELECT id, name, nutrient_type,
  ciqual_const_code, ciqual_const_name_eng, ciqual_unit,
  calnut_const_code, calnut_const_name, calnut_unit,
  off_id, count, template, nnr2023_id, disabled
  FROM read_csv('data/nutrient_map.csv')
  WHERE calnut_const_code IS NOT NULL
);

CREATE OR REPLACE TABLE ciqual_alim AS (
  SELECT alim_code, alim_nom_eng, alim_grp_code, alim_ssgrp_code, alim_ssssgrp_code
  FROM read_csv('data/ciqual2020/alim.csv')
);

CREATE OR REPLACE TABLE ciqual_compo AS (
  SELECT alim_code, const_code, code_confiance, source_code,
  CASE WHEN min = '-' THEN NULL ELSE CAST(REPLACE(REPLACE(min, 'traces', '0'), ',', '.') AS FLOAT) END AS lb,
  CASE WHEN max = '-' THEN NULL ELSE CAST(REPLACE(REPLACE(max, 'traces', '0'), ',', '.') AS FLOAT) END AS ub,
  CASE WHEN teneur = '-' THEN NULL ELSE CAST(REPLACE(REPLACE(teneur, 'traces', '0'), ',', '.') AS FLOAT) END AS mean
  FROM read_csv('data/ciqual2020/compo.csv')
);

CREATE OR REPLACE TABLE calnut_0 AS (
  SELECT ALIM_CODE, FOOD_LABEL,
  alim_grp_code, alim_ssgrp_code, alim_ssssgrp_code,
  alim_grp_nom_fr, alim_ssgrp_nom_fr, alim_ssssgrp_nom_fr
  FROM read_csv('data/calnut.0.csv')
  WHERE HYPOTH = 'MB'
);

CREATE OR REPLACE TABLE calnut_1 AS (
  SELECT ALIM_CODE, FOOD_LABEL, CONST_LABEL, CONST_CODE,
  CAST(indic_combl AS BOOL) AS combl,
  CAST(REPLACE(LB, ',', '.') AS FLOAT) AS lb,
  CAST(REPLACE(UB, ',', '.') AS FLOAT) AS ub,
  CAST(REPLACE(MB, ',', '.') AS FLOAT) AS mean
  FROM read_csv('data/calnut.1.csv')
);
