-- Load previous nutrient map and constants from CSV files
CREATE TABLE ciqual_const AS SELECT * FROM read_csv('data/ciqual2020/const.csv');
CREATE TABLE calnut_const AS (
  SELECT CONST_CODE as const_code, regexp_extract(CONST_LABEL, '(.+)_(\w+)', ['name', 'unit']) as const_label
  FROM read_csv('data/calnut.1.csv') GROUP BY CONST_CODE, CONST_LABEL
);
CREATE TABLE nutrient_map AS SELECT *, ROW_NUMBER() OVER () AS row_num FROM read_csv('data/nutrient_map.csv');
-- Nutrient map with updated ciqual and calnut constants (should not change)
CREATE TABLE nutrient_map_updated AS
SELECT
  nm.id,
  nm.name,
  ciqc.const_code AS ciqual_const_code, -- updated
  ciqc.const_nom_eng AS ciqual_const_name_eng, -- updated
  ciqc.const_nom_fr AS ciqual_const_name_fr, -- updated
  nm.ciqual_unit,
  calc.const_code AS calnut_const_code, -- updated
  calc.const_label.name AS calnut_const_name, -- updated
  calc.const_label.unit AS calnut_unit, -- updated
  nm.off_id,
  nm.count,
  nm.template,
  nm.nnr2023_id,
  nm.nutrient_type,
  nm.disabled,
  nm.comments,
FROM nutrient_map nm
FULL JOIN ciqual_const ciqc ON nm.ciqual_const_code = ciqc.const_code
FULL JOIN calnut_const calc ON nm.calnut_const_code = calc.const_code
ORDER BY nm.row_num;
-- Overwrite the csv file
COPY nutrient_map_updated TO 'data/nutrient_map.csv';

-- Other commands to check for missing constants:
-- Rows lacking a matching ciqual_const_code
--   SELECT id, name, ciqual_const_code, ciqual_const_name_eng, ciqual_const_name_fr
--   FROM nutrient_map
--   ANTI JOIN ciqual_const ON nutrient_map.ciqual_const_code = ciqual_const.const_code;
-- Rows lacking a matching calnut_const_code
--   SELECT id, name, calnut_const_code, calnut_const_name
--   FROM nutrient_map
--   ANTI JOIN calnut_const ON nutrient_map.calnut_const_code = calnut_const.const_code;
