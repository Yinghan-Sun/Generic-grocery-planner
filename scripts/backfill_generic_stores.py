#!/usr/bin/env -S uv run
"""Backfill the live store index for a list of cities."""

from __future__ import annotations

import argparse
import csv
import json
import urllib.parse
import urllib.request
from pathlib import Path

import dietdashboard.store_discovery as store_discovery

DEFAULT_RADIUS_M = 15_000.0
DEFAULT_LIMIT = 120
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
NOMINATIM_USER_AGENT = "generic-grocery-planner-demo-store-backfill/0.1"
DEFAULT_CITY_CONFIG = Path(__file__).resolve().parent.parent / "data" / "store_backfill_cities.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cities", nargs="*", help="City names to backfill. Defaults to the built-in starter list.")
    parser.add_argument("--radius-m", type=float, default=DEFAULT_RADIUS_M, help="Search radius in meters around each city center.")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT, help="Maximum live stores to fetch per city.")
    parser.add_argument(
        "--db-path",
        type=Path,
        default=store_discovery.STORE_DISCOVERY_DB_PATH,
        help="Path to the store discovery sidecar DB.",
    )
    parser.add_argument(
        "--city-config",
        type=Path,
        default=DEFAULT_CITY_CONFIG,
        help="CSV file defining the default city backfill list.",
    )
    parser.add_argument(
        "--main-db-path",
        type=Path,
        default=store_discovery.MAIN_DATA_DB_PATH,
        help="Main DuckDB path used to merge seeded/local stores into the unified index.",
    )
    return parser.parse_args()


def geocode_city(city: str) -> tuple[float, float, str]:
    params = urllib.parse.urlencode({"q": city, "format": "jsonv2", "limit": 1})
    request = urllib.request.Request(
        f"{NOMINATIM_URL}?{params}",
        headers={"Accept": "application/json", "User-Agent": NOMINATIM_USER_AGENT},
        method="GET",
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        results = json.loads(response.read().decode("utf-8"))
    if not isinstance(results, list) or not results:
        raise RuntimeError(f"Could not geocode city: {city}")
    top = results[0]
    return float(top["lat"]), float(top["lon"]), str(top.get("display_name") or city)


def _enabled(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y"}


def load_city_specs(config_path: Path) -> list[dict[str, object]]:
    with config_path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))

    specs: list[dict[str, object]] = []
    for row in rows:
        if not _enabled(row.get("enabled")):
            continue
        city_name = str(row.get("city_name") or "").strip()
        region = str(row.get("region") or "").strip()
        country = str(row.get("country") or "").strip()
        if not city_name:
            continue
        query = ", ".join(part for part in (city_name, region, country) if part)
        specs.append(
            {
                "city_name": city_name,
                "region": region,
                "country": country,
                "query": query,
                "radius_m": float(row.get("radius_m") or DEFAULT_RADIUS_M),
                "limit": int(row.get("limit") or DEFAULT_LIMIT),
                "priority": int(row.get("priority") or 999),
            }
        )

    specs.sort(key=lambda spec: (int(spec["priority"]), str(spec["city_name"])))
    return specs


def existing_store_ids(db_path: Path, store_ids: set[str]) -> set[str]:
    if not db_path.exists() or not store_ids:
        return set()
    con = store_discovery._readonly_runtime_con()  # noqa: SLF001
    if con is None:
        return set()
    try:
        rows = con.execute(
            "SELECT store_id FROM store_places_live WHERE store_id IN (SELECT UNNEST($store_ids))",
            {"store_ids": list(store_ids)},
        ).fetchall()
        return {str(row[0]) for row in rows}
    finally:
        con.close()


def total_live_rows(db_path: Path) -> int:
    if not db_path.exists():
        return 0
    readonly = store_discovery._readonly_runtime_con()  # noqa: SLF001
    if readonly is None:
        return 0
    try:
        return int(readonly.execute("SELECT COUNT(*) FROM store_places_live").fetchone()[0])
    finally:
        readonly.close()


def total_unified_rows(db_path: Path) -> int:
    if not db_path.exists():
        return 0
    readonly = store_discovery._readonly_runtime_con()  # noqa: SLF001
    if readonly is None:
        return 0
    try:
        return int(readonly.execute("SELECT COUNT(*) FROM store_places_unified").fetchone()[0])
    finally:
        readonly.close()


def main() -> int:
    args = parse_args()
    city_specs = (
        [
            {
                "city_name": city,
                "region": "",
                "country": "",
                "query": city,
                "radius_m": args.radius_m,
                "limit": args.limit,
                "priority": idx + 1,
            }
            for idx, city in enumerate(args.cities)
        ]
        if args.cities
        else load_city_specs(args.city_config)
    )

    store_discovery.STORE_DISCOVERY_DB_PATH = args.db_path
    store_discovery.STORE_DISCOVERY_PERSIST_LIVE = True

    cities_processed = 0
    total_found = 0
    total_new = 0
    total_merged = 0

    print(f"db_path={args.db_path}")
    print(f"city_config={args.city_config}")
    print(f"default_radius_m={int(args.radius_m)}")
    print(f"default_limit={args.limit}")

    unified_summary = store_discovery.refresh_unified_store_index(main_db_path=args.main_db_path)
    print(
        "initial_unified_rows={unified_rows} local_rows={local_rows} live_rows={live_rows} merged_duplicates={duplicates_merged}".format(
            **unified_summary
        )
    )

    for city_spec in city_specs:
        city = str(city_spec["query"])
        radius_m = float(city_spec["radius_m"])
        limit = int(city_spec["limit"])
        try:
            lat, lon, display_name = geocode_city(city)
            live_rows = store_discovery._live_overpass_nearby_stores(  # noqa: SLF001
                lat=lat,
                lon=lon,
                radius_m=radius_m,
                limit=limit,
            )
        except Exception as exc:  # noqa: BLE001
            print(f"city={city} status=error error={exc}")
            continue

        stores = [row[0] for row in live_rows]
        store_ids = {str(store["store_id"]) for store in stores}
        merged_ids = existing_store_ids(args.db_path, store_ids)
        new_count = len(store_ids - merged_ids)
        merged_count = len(merged_ids)

        store_discovery._persist_live_stores(live_rows, source="overpass")  # noqa: SLF001
        store_discovery._cache_store(  # noqa: SLF001
            lat=lat,
            lon=lon,
            radius_m=radius_m,
            limit=limit,
            stores=stores,
            source="overpass",
        )
        unified_summary = store_discovery.refresh_unified_store_index(main_db_path=args.main_db_path)

        cities_processed += 1
        total_found += len(stores)
        total_new += new_count
        total_merged += merged_count

        print(
            "city={city} status=ok display_name={display_name!r} lat={lat:.4f} lon={lon:.4f} "
            "radius_m={radius_m} limit={limit} stores_found={stores_found} new_rows={new_rows} merged_rows={merged_rows} "
            "unified_rows={unified_rows} merged_duplicates={duplicates_merged}".format(
                city=city,
                display_name=display_name,
                lat=lat,
                lon=lon,
                radius_m=int(radius_m),
                limit=limit,
                stores_found=len(stores),
                new_rows=new_count,
                merged_rows=merged_count,
                **unified_summary,
            )
        )

    print(
        "summary cities_processed={cities_processed} total_found={total_found} total_new={total_new} "
        "duplicates_merged={duplicates_merged} total_persisted_rows={total_persisted_rows} total_unified_rows={total_unified_rows}".format(
            cities_processed=cities_processed,
            total_found=total_found,
            total_new=total_new,
            duplicates_merged=total_merged,
            total_persisted_rows=total_live_rows(args.db_path),
            total_unified_rows=total_unified_rows(args.db_path),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
