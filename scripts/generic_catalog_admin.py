#!/usr/bin/env -S uv run
"""Inspect the generic food catalog and materialized generic_foods table."""

from __future__ import annotations

import argparse
from pathlib import Path

import duckdb

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "data.db"
CRITICAL_METADATA_FIELDS = [
    "display_name",
    "food_family",
    "default_serving_g",
    "purchase_unit",
    "purchase_unit_size_g",
    "meal_type",
    "prep_level",
    "budget_score",
    "commonality_rank",
]
SCORE_FIELDS = [
    "protein_density_score",
    "fiber_score",
    "calcium_score",
    "iron_score",
    "vitamin_c_score",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db-path", type=Path, default=DEFAULT_DB_PATH, help="Path to the built DuckDB database.")
    parser.add_argument(
        "--show-incomplete-limit",
        type=int,
        default=15,
        help="Maximum number of incomplete rows to print.",
    )
    return parser.parse_args()


def require_table(con: duckdb.DuckDBPyConnection, table_name: str) -> None:
    found = con.execute(
        """
        SELECT COUNT(*)
        FROM information_schema.tables
        WHERE lower(table_name) = lower($table_name)
        """,
        {"table_name": table_name},
    ).fetchone()[0]
    if not found:
        raise RuntimeError(f"Required table not found: {table_name}")


def main() -> int:
    args = parse_args()
    if not args.db_path.exists():
        raise SystemExit(f"Database not found: {args.db_path}")

    con = duckdb.connect(args.db_path, read_only=True)
    try:
        for table_name in ("generic_food_catalog", "generic_food_source_map", "generic_foods"):
            require_table(con, table_name)

        catalog_count = con.execute("SELECT COUNT(*) FROM generic_food_catalog").fetchone()[0]
        source_map_count = con.execute("SELECT COUNT(*) FROM generic_food_source_map").fetchone()[0]
        materialized_count = con.execute("SELECT COUNT(*) FROM generic_foods").fetchone()[0]

        missing_source_map_rows = con.execute(
            """
            SELECT c.generic_food_id
            FROM generic_food_catalog AS c
            LEFT JOIN generic_food_source_map AS m USING (generic_food_id)
            WHERE m.generic_food_id IS NULL
            ORDER BY c.generic_food_id
            """
        ).fetchall()
        missing_materialized_rows = con.execute(
            """
            SELECT c.generic_food_id
            FROM generic_food_catalog AS c
            LEFT JOIN generic_foods AS g USING (generic_food_id)
            WHERE g.generic_food_id IS NULL
            ORDER BY c.generic_food_id
            """
        ).fetchall()

        print(f"db_path={args.db_path}")
        print(f"generic_food_catalog_rows={catalog_count}")
        print(f"generic_food_source_map_rows={source_map_count}")
        print(f"generic_foods_rows={materialized_count}")
        print(f"missing_source_map_rows={len(missing_source_map_rows)}")
        print(f"missing_materialized_rows={len(missing_materialized_rows)}")

        print("\ncounts_by_food_family")
        for food_family, count in con.execute(
            """
            SELECT food_family, COUNT(*) AS count
            FROM generic_food_catalog
            GROUP BY food_family
            ORDER BY count DESC, food_family
            """
        ).fetchall():
            print(f"  {food_family}: {count}")

        print("\nmissing_metadata_fields")
        for field_name in CRITICAL_METADATA_FIELDS:
            count = con.execute(
                f"""
                SELECT COUNT(*)
                FROM generic_food_catalog
                WHERE {field_name} IS NULL OR trim(CAST({field_name} AS VARCHAR)) = ''
                """
            ).fetchone()[0]
            print(f"  {field_name}: {count}")

        print("\nmissing_score_fields")
        for field_name in SCORE_FIELDS:
            count = con.execute(
                f"""
                SELECT COUNT(*)
                FROM generic_foods
                WHERE {field_name} IS NULL
                """
            ).fetchone()[0]
            print(f"  {field_name}: {count}")

        incomplete_rows = con.execute(
            """
            WITH issues AS (
              SELECT
                generic_food_id,
                ARRAY_FILTER([
                  CASE WHEN display_name IS NULL OR trim(display_name) = '' THEN 'display_name' END,
                  CASE WHEN food_family IS NULL OR trim(food_family) = '' THEN 'food_family' END,
                  CASE WHEN default_serving_g IS NULL OR default_serving_g <= 0 THEN 'default_serving_g' END,
                  CASE WHEN purchase_unit IS NULL OR trim(purchase_unit) = '' THEN 'purchase_unit' END,
                  CASE WHEN purchase_unit_size_g IS NULL OR purchase_unit_size_g <= 0 THEN 'purchase_unit_size_g' END,
                  CASE WHEN meal_type IS NULL OR trim(meal_type) = '' THEN 'meal_type' END,
                  CASE WHEN prep_level IS NULL OR trim(prep_level) = '' THEN 'prep_level' END,
                  CASE WHEN budget_score IS NULL OR budget_score < 1 THEN 'budget_score' END,
                  CASE WHEN commonality_rank IS NULL OR commonality_rank < 1 THEN 'commonality_rank' END,
                  CASE WHEN primary_source_food_code IS NULL THEN 'primary_source_food_code' END,
                  CASE WHEN protein_density_score IS NULL THEN 'protein_density_score' END,
                  CASE WHEN fiber_score IS NULL THEN 'fiber_score' END,
                  CASE WHEN calcium_score IS NULL THEN 'calcium_score' END,
                  CASE WHEN iron_score IS NULL THEN 'iron_score' END,
                  CASE WHEN vitamin_c_score IS NULL THEN 'vitamin_c_score' END
                ], x -> x IS NOT NULL) AS missing_fields
              FROM generic_foods
            )
            SELECT generic_food_id, missing_fields
            FROM issues
            WHERE array_length(missing_fields) > 0
            ORDER BY generic_food_id
            LIMIT $limit
            """,
            {"limit": args.show_incomplete_limit},
        ).fetchall()

        print(f"\nincomplete_row_count={len(incomplete_rows)} shown_limit={args.show_incomplete_limit}")
        for generic_food_id, missing_fields in incomplete_rows:
            print(f"  {generic_food_id}: {', '.join(missing_fields)}")

        if missing_source_map_rows:
            print("\nmissing_source_map_food_ids")
            for (generic_food_id,) in missing_source_map_rows[: args.show_incomplete_limit]:
                print(f"  {generic_food_id}")

        if missing_materialized_rows:
            print("\nmissing_materialized_food_ids")
            for (generic_food_id,) in missing_materialized_rows[: args.show_incomplete_limit]:
                print(f"  {generic_food_id}")
    finally:
        con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
