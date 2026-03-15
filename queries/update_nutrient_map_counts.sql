-- Attach the database
ATTACH DATABASE 'data/data.db' AS data (READONLY);
-- Nutrient map from CSV
CREATE TABLE nutrient_map AS SELECT *, ROW_NUMBER() OVER () AS row_num FROM read_csv('data/nutrient_map.csv');
-- Nutrient counts
CREATE TABLE nutrient_counts AS
SELECT n.unnest.name as off_id, count(*) AS count
FROM data.products, UNNEST(data.products.nutriments) AS n
GROUP BY n.unnest.name
ORDER BY count DESC;
-- Nutrient map with updated counts
CREATE OR REPLACE TABLE nutrient_map_updated AS
SELECT
  nm.id,
  nm.name,
  nm.ciqual_const_code,
  nm.ciqual_const_name_eng,
  nm.ciqual_const_name_fr,
  nm.ciqual_unit,
  nm.calnut_const_code,
  nm.calnut_const_name,
  nm.calnut_unit,
  nm.off_id,
  nc.count AS count, -- updated count from nutrient_counts
  nm.template,
  nm.nnr2023_id,
  nm.nutrient_type,
  nm.disabled,
  nm.comments,
FROM nutrient_map nm
LEFT JOIN nutrient_counts nc USING (off_id)
ORDER BY nm.row_num;
-- Overwrite the csv file
COPY nutrient_map_updated TO 'data/nutrient_map.csv';
