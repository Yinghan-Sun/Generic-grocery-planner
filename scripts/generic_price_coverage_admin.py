#!/usr/bin/env -S uv run python
"""Audit local generic-food price coverage across USDA and BLS layers."""

from __future__ import annotations

from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
DATA_DB = ROOT / "data" / "data.db"


def scalar(con: duckdb.DuckDBPyConnection, query: str) -> int:
    return int(con.execute(query).fetchone()[0])


def main() -> int:
    with duckdb.connect(DATA_DB, read_only=True) as con:
        total_generic_foods = scalar(con, "SELECT COUNT(*) FROM generic_foods")
        usda_mapped_foods = scalar(con, "SELECT COUNT(DISTINCT generic_food_id) FROM generic_food_usda_map")
        usda_price_covered_foods = scalar(con, "SELECT COUNT(DISTINCT generic_food_id) FROM generic_food_usda_prices_by_area")
        bls_mapped_foods = scalar(con, "SELECT COUNT(DISTINCT generic_food_id) FROM generic_food_bls_map")
        bls_price_covered_foods = scalar(con, "SELECT COUNT(DISTINCT generic_food_id) FROM generic_food_prices_by_area")
        food_cpi_rows = scalar(con, "SELECT COUNT(*) FROM food_cpi_index")
        usda_adjustment_rows = scalar(con, "SELECT COUNT(*) FROM food_cpi_adjustment_context")
        latest_cpi_observed_at = con.execute("SELECT MAX(observed_at) FROM food_cpi_index").fetchone()[0]
        cpi_multiplier = con.execute(
            "SELECT inflation_multiplier FROM food_cpi_adjustment_context LIMIT 1"
        ).fetchone()
        priced_any_foods = scalar(
            con,
            """
            SELECT COUNT(DISTINCT generic_food_id)
            FROM (
              SELECT generic_food_id FROM generic_food_usda_prices_by_area
              UNION
              SELECT generic_food_id FROM generic_food_prices_by_area
              UNION
              SELECT generic_food_id FROM generic_food_prices
            )
            """,
        )
        unpriced_foods = max(total_generic_foods - priced_any_foods, 0)

        print(f"db_path={DATA_DB}")
        print(f"total_generic_foods={total_generic_foods}")
        print(f"usda_mapped_foods={usda_mapped_foods}")
        print(f"usda_price_covered_foods={usda_price_covered_foods}")
        print(f"bls_mapped_foods={bls_mapped_foods}")
        print(f"bls_price_covered_foods={bls_price_covered_foods}")
        print(f"food_cpi_rows={food_cpi_rows}")
        print(f"food_cpi_latest_observed_at={latest_cpi_observed_at}")
        print(f"food_cpi_adjustment_rows={usda_adjustment_rows}")
        print(f"food_cpi_multiplier={float(cpi_multiplier[0]) if cpi_multiplier and cpi_multiplier[0] is not None else ''}")
        print(f"priced_any_foods={priced_any_foods}")
        print(f"unpriced_foods={unpriced_foods}")
        print()
        print("coverage_summary")
        print(f"  usda_mapping_rate={usda_mapped_foods}/{total_generic_foods}")
        print(f"  usda_price_rate={usda_price_covered_foods}/{total_generic_foods}")
        print(f"  bls_mapping_rate={bls_mapped_foods}/{total_generic_foods}")
        print(f"  bls_price_rate={bls_price_covered_foods}/{total_generic_foods}")
        print(f"  total_priced_rate={priced_any_foods}/{total_generic_foods}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
