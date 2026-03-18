#!/usr/bin/env -S uv run
"""Inspect and maintain the store discovery sidecar database."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime, timedelta
from pathlib import Path

import duckdb

from dietdashboard.store_discovery import STORE_DISCOVERY_CACHE_TTL_S, STORE_DISCOVERY_DB_PATH


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def connect(db_path: Path, *, read_only: bool) -> duckdb.DuckDBPyConnection:
    if read_only:
        return duckdb.connect(db_path, read_only=True)
    con = duckdb.connect(db_path)
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS store_search_cache (
          query_key VARCHAR PRIMARY KEY,
          lat DOUBLE,
          lon DOUBLE,
          radius_m DOUBLE,
          result_limit INTEGER,
          source VARCHAR,
          results_json VARCHAR,
          fetched_at TIMESTAMP
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS store_places_live (
          store_id VARCHAR PRIMARY KEY,
          source VARCHAR,
          source_place_id VARCHAR,
          name VARCHAR,
          brand VARCHAR,
          address VARCHAR,
          city VARCHAR,
          region VARCHAR,
          postcode VARCHAR,
          category VARCHAR,
          lat DOUBLE,
          lon DOUBLE,
          last_seen_at TIMESTAMP,
          raw_record_json VARCHAR
        )
        """
    )
    con.execute("""ALTER TABLE store_places_live ADD COLUMN IF NOT EXISTS brand VARCHAR""")
    con.execute("""ALTER TABLE store_places_live ADD COLUMN IF NOT EXISTS city VARCHAR""")
    con.execute("""ALTER TABLE store_places_live ADD COLUMN IF NOT EXISTS region VARCHAR""")
    con.execute("""ALTER TABLE store_places_live ADD COLUMN IF NOT EXISTS postcode VARCHAR""")
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS store_places_unified (
          store_id VARCHAR PRIMARY KEY,
          name VARCHAR,
          brand VARCHAR,
          lat DOUBLE,
          lon DOUBLE,
          address VARCHAR,
          city VARCHAR,
          region VARCHAR,
          postcode VARCHAR,
          category VARCHAR,
          source VARCHAR,
          source_priority INTEGER,
          confidence DOUBLE,
          metadata_source VARCHAR,
          metadata_confidence DOUBLE,
          last_seen_at TIMESTAMP
        )
        """
    )
    con.execute("""ALTER TABLE store_places_unified ADD COLUMN IF NOT EXISTS metadata_source VARCHAR""")
    con.execute("""ALTER TABLE store_places_unified ADD COLUMN IF NOT EXISTS metadata_confidence DOUBLE""")
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS store_places_foursquare (
          store_id VARCHAR PRIMARY KEY,
          name VARCHAR,
          brand VARCHAR,
          lat DOUBLE,
          lon DOUBLE,
          address VARCHAR,
          city VARCHAR,
          region VARCHAR,
          postcode VARCHAR,
          category VARCHAR,
          source VARCHAR,
          source_priority INTEGER,
          confidence DOUBLE,
          last_seen_at TIMESTAMP,
          raw_record_json VARCHAR
        )
        """
    )
    return con


def summary(db_path: Path) -> int:
    if not db_path.exists():
        print(f"No sidecar DB found at {db_path}")
        return 0

    con = connect(db_path, read_only=True)
    cache_rows = con.execute("SELECT COUNT(*) FROM store_search_cache").fetchone()[0]
    live_rows = con.execute("SELECT COUNT(*) FROM store_places_live").fetchone()[0]
    foursquare_rows = con.execute("SELECT COUNT(*) FROM store_places_foursquare").fetchone()[0]
    unified_rows = con.execute("SELECT COUNT(*) FROM store_places_unified").fetchone()[0]
    foursquare_distinct_city_regions = con.execute(
        """
        SELECT COUNT(DISTINCT city || '|' || region)
        FROM store_places_foursquare
        WHERE city IS NOT NULL AND TRIM(city) != ''
          AND region IS NOT NULL AND TRIM(region) != ''
        """
    ).fetchone()[0]
    unified_distinct_city_regions = con.execute(
        """
        SELECT COUNT(DISTINCT city || '|' || region)
        FROM store_places_unified
        WHERE city IS NOT NULL AND TRIM(city) != ''
          AND region IS NOT NULL AND TRIM(region) != ''
        """
    ).fetchone()[0]
    live_missing = con.execute(
        """
        SELECT
          SUM(CASE WHEN city IS NULL OR TRIM(city) = '' THEN 1 ELSE 0 END),
          SUM(CASE WHEN region IS NULL OR TRIM(region) = '' THEN 1 ELSE 0 END),
          SUM(CASE WHEN (city IS NULL OR TRIM(city) = '') AND (region IS NULL OR TRIM(region) = '') THEN 1 ELSE 0 END)
        FROM store_places_live
        """
    ).fetchone()
    foursquare_missing = con.execute(
        """
        SELECT
          SUM(CASE WHEN city IS NULL OR TRIM(city) = '' THEN 1 ELSE 0 END),
          SUM(CASE WHEN region IS NULL OR TRIM(region) = '' THEN 1 ELSE 0 END),
          SUM(CASE WHEN (city IS NULL OR TRIM(city) = '') AND (region IS NULL OR TRIM(region) = '') THEN 1 ELSE 0 END)
        FROM store_places_foursquare
        """
    ).fetchone()
    unified_missing = con.execute(
        """
        SELECT
          SUM(CASE WHEN city IS NULL OR TRIM(city) = '' THEN 1 ELSE 0 END),
          SUM(CASE WHEN region IS NULL OR TRIM(region) = '' THEN 1 ELSE 0 END),
          SUM(CASE WHEN (city IS NULL OR TRIM(city) = '') AND (region IS NULL OR TRIM(region) = '') THEN 1 ELSE 0 END)
        FROM store_places_unified
        """
    ).fetchone()
    oldest_newest = con.execute(
        """
        SELECT MIN(fetched_at), MAX(fetched_at)
        FROM store_search_cache
        """
    ).fetchone()
    live_oldest_newest = con.execute(
        """
        SELECT MIN(last_seen_at), MAX(last_seen_at)
        FROM store_places_live
        """
    ).fetchone()
    foursquare_oldest_newest = con.execute(
        """
        SELECT MIN(last_seen_at), MAX(last_seen_at)
        FROM store_places_foursquare
        """
    ).fetchone()
    unified_oldest_newest = con.execute(
        """
        SELECT MIN(last_seen_at), MAX(last_seen_at)
        FROM store_places_unified
        """
    ).fetchone()

    print(f"db_path={db_path}")
    print(f"cache_rows={cache_rows}")
    print(f"live_rows={live_rows}")
    print(f"foursquare_rows={foursquare_rows}")
    print(f"unified_rows={unified_rows}")
    print(f"foursquare_distinct_city_regions={foursquare_distinct_city_regions}")
    print(f"unified_distinct_city_regions={unified_distinct_city_regions}")
    print(f"live_missing_city={live_missing[0] or 0}")
    print(f"live_missing_region={live_missing[1] or 0}")
    print(f"live_missing_both={live_missing[2] or 0}")
    print(f"foursquare_missing_city={foursquare_missing[0] or 0}")
    print(f"foursquare_missing_region={foursquare_missing[1] or 0}")
    print(f"foursquare_missing_both={foursquare_missing[2] or 0}")
    print(f"unified_missing_city={unified_missing[0] or 0}")
    print(f"unified_missing_region={unified_missing[1] or 0}")
    print(f"unified_missing_both={unified_missing[2] or 0}")
    print(f"cache_oldest={oldest_newest[0]}")
    print(f"cache_newest={oldest_newest[1]}")
    print(f"live_oldest_seen={live_oldest_newest[0]}")
    print(f"live_newest_seen={live_oldest_newest[1]}")
    print(f"foursquare_oldest_seen={foursquare_oldest_newest[0]}")
    print(f"foursquare_newest_seen={foursquare_oldest_newest[1]}")
    print(f"unified_oldest_seen={unified_oldest_newest[0]}")
    print(f"unified_newest_seen={unified_oldest_newest[1]}")

    print("\ncache_by_source")
    for row in con.execute(
        """
        SELECT source, COUNT(*) AS count
        FROM store_search_cache
        GROUP BY source
        ORDER BY count DESC, source
        """
    ).fetchall():
        print(f"  {row[0]}: {row[1]}")

    print("\nlive_by_source")
    for row in con.execute(
        """
        SELECT source, COUNT(*) AS count
        FROM store_places_live
        GROUP BY source
        ORDER BY count DESC, source
        """
    ).fetchall():
        print(f"  {row[0]}: {row[1]}")

    print("\nlive_by_city_region")
    for row in con.execute(
        """
        SELECT COALESCE(city, '(unknown)') AS city, COALESCE(region, '(unknown)') AS region, COUNT(*) AS count
        FROM store_places_live
        GROUP BY city, region
        ORDER BY count DESC, city, region
        LIMIT 20
        """
    ).fetchall():
        print(f"  {row[0]}, {row[1]}: {row[2]}")

    print("\nfoursquare_by_source")
    for row in con.execute(
        """
        SELECT source, COUNT(*) AS count
        FROM store_places_foursquare
        GROUP BY source
        ORDER BY count DESC, source
        """
    ).fetchall():
        print(f"  {row[0]}: {row[1]}")

    print("\nfoursquare_by_city_region")
    for row in con.execute(
        """
        SELECT COALESCE(city, '(unknown)') AS city, COALESCE(region, '(unknown)') AS region, COUNT(*) AS count
        FROM store_places_foursquare
        GROUP BY city, region
        ORDER BY count DESC, city, region
        LIMIT 20
        """
    ).fetchall():
        print(f"  {row[0]}, {row[1]}: {row[2]}")

    print("\nunified_by_source")
    for row in con.execute(
        """
        SELECT source, COUNT(*) AS count
        FROM store_places_unified
        GROUP BY source
        ORDER BY count DESC, source
        """
    ).fetchall():
        print(f"  {row[0]}: {row[1]}")

    print("\nunified_by_metadata_source")
    for row in con.execute(
        """
        SELECT COALESCE(metadata_source, '(unknown)') AS metadata_source, COUNT(*) AS count
        FROM store_places_unified
        GROUP BY metadata_source
        ORDER BY count DESC, metadata_source
        """
    ).fetchall():
        print(f"  {row[0]}: {row[1]}")

    print("\nunified_by_city_region")
    for row in con.execute(
        """
        SELECT COALESCE(city, '(unknown)') AS city, COALESCE(region, '(unknown)') AS region, COUNT(*) AS count
        FROM store_places_unified
        GROUP BY city, region
        ORDER BY count DESC, city, region
        LIMIT 20
        """
    ).fetchall():
        print(f"  {row[0]}, {row[1]}: {row[2]}")

    con.close()
    return 0


def prune_cache(db_path: Path, older_than_s: int) -> int:
    con = connect(db_path, read_only=False)
    cutoff = utcnow() - timedelta(seconds=older_than_s)
    before = con.execute("SELECT COUNT(*) FROM store_search_cache").fetchone()[0]
    con.execute("DELETE FROM store_search_cache WHERE fetched_at < $cutoff", {"cutoff": cutoff})
    after = con.execute("SELECT COUNT(*) FROM store_search_cache").fetchone()[0]
    con.close()
    print(f"deleted_cache_rows={before - after}")
    print(f"remaining_cache_rows={after}")
    return 0


def dedupe_live(db_path: Path) -> int:
    con = connect(db_path, read_only=False)
    duplicates = con.execute(
        """
        SELECT COUNT(*)
        FROM (
          SELECT store_id,
                 ROW_NUMBER() OVER (
                   PARTITION BY source, lower(name), lower(COALESCE(address, '')), round(lat, 4), round(lon, 4)
                   ORDER BY last_seen_at DESC, store_id
                 ) AS rn
          FROM store_places_live
        )
        WHERE rn > 1
        """
    ).fetchone()[0]
    con.execute(
        """
        DELETE FROM store_places_live
        WHERE store_id IN (
          SELECT store_id
          FROM (
            SELECT store_id,
                   ROW_NUMBER() OVER (
                     PARTITION BY source, lower(name), lower(COALESCE(address, '')), round(lat, 4), round(lon, 4)
                     ORDER BY last_seen_at DESC, store_id
                   ) AS rn
            FROM store_places_live
          )
          WHERE rn > 1
        )
        """
    )
    remaining = con.execute("SELECT COUNT(*) FROM store_places_live").fetchone()[0]
    con.close()
    print(f"deduplicated_rows={duplicates}")
    print(f"remaining_live_rows={remaining}")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db-path", type=Path, default=STORE_DISCOVERY_DB_PATH, help="Path to the store discovery sidecar DB.")

    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("summary", help="Print coverage and freshness summaries.")

    prune_parser = subparsers.add_parser("prune-cache", help="Delete stale cache rows.")
    prune_parser.add_argument(
        "--older-than-s",
        type=int,
        default=STORE_DISCOVERY_CACHE_TTL_S,
        help="Delete cache rows older than this many seconds.",
    )

    subparsers.add_parser("dedupe-live", help="Delete duplicate persisted live-store rows.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    db_path = args.db_path

    if args.command == "summary":
        return summary(db_path)
    if args.command == "prune-cache":
        return prune_cache(db_path, args.older_than_s)
    if args.command == "dedupe-live":
        return dedupe_live(db_path)
    raise ValueError(f"Unknown command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
