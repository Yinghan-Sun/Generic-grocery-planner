# USDA Food-at-Home Monthly Area Prices staging

This directory is the offline staging area for USDA Food-at-Home Monthly Area Prices
(F-MAP) inputs used by the `/generic` price layer.

The runtime app does not fetch USDA data from the internet. DuckDB only reads local
normalized files created from whatever USDA files are placed here.

Expected upstream source shape
- Official USDA ERS Food-at-Home Monthly Area Prices releases are published as
  downloadable workbook/zip resources.
- The documented content is monthly area prices for 90 food groups across 15 areas.
- The most useful normalized price field is the weighted mean unit value per 100 grams.

Accepted local input files for normalization
- `.xlsx`
- `.csv`
- `.tsv`
- `.zip` containing one of the formats above

Recommended raw file names
- `food-at-home-monthly-area-prices-2012-to-2018.zip`
- `food_at_home_monthly_area_prices.xlsx`
- `food_at_home_monthly_area_prices.csv`
- `food_at_home_monthly_area_prices.zip`

Official 2024 ERS release shape
- The main ZIP currently expands to:
  - `FMAP-Data.csv`
  - `FMAP-ReadMe.txt`
- `FMAP-Data.csv` is a long-format file with columns:
  - `Year`
  - `Month`
  - `EFPG_code`
  - `Metroregion_code`
  - `Attribute`
  - `Value`
- The normalization script pivots that long-format release into the staged wide CSVs
  consumed by DuckDB.

The normalization script scans this directory recursively and ignores the generated
`*_staged.csv` files.

Expected input columns or close variants
- area / market area name
- optional area code
- food group / EFPG name
- optional food group code
- year
- month
- weighted mean unit value per 100 grams
- optional weighted purchase dollars / grams / store count metadata

Generated local files
- `usda_food_area_prices_raw_staged.csv`
- `usda_food_area_prices_normalized.csv`

Those generated files are safe to rebuild. If no USDA source files are present, the
normalizer will emit empty staged CSVs with headers so the DuckDB build remains stable.
