#!/usr/bin/env -S uv run
"""Ingest a local Foursquare-like store dataset into the store discovery sidecar DB."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

import dietdashboard.store_discovery as store_discovery

RELEVANT_CATEGORY_KEYWORDS = (
    "supermarket",
    "grocery",
    "food market",
    "market",
    "wholesale club",
    "warehouse club",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="Local Foursquare dataset file (CSV or JSONL).")
    parser.add_argument(
        "--db-path",
        type=Path,
        default=store_discovery.STORE_DISCOVERY_DB_PATH,
        help="Path to the store discovery sidecar DB.",
    )
    parser.add_argument(
        "--main-db-path",
        type=Path,
        default=store_discovery.MAIN_DATA_DB_PATH,
        help="Main DuckDB path used to refresh the unified local store index.",
    )
    parser.add_argument(
        "--source",
        default="foursquare_offline",
        help="Source label written into store_places_foursquare.",
    )
    return parser.parse_args()


def _first_non_empty(*values: object) -> str | None:
    for value in values:
        if value is None:
            continue
        if isinstance(value, str):
            cleaned = value.strip()
            if cleaned:
                return cleaned
        elif value != "":
            return str(value)
    return None


def _categories_text(row: dict[str, Any]) -> str:
    candidates = [
        row.get("category"),
        row.get("category_name"),
        row.get("category_primary"),
        row.get("category_labels"),
        row.get("fsq_category_labels"),
        row.get("categories"),
    ]
    parts: list[str] = []
    for candidate in candidates:
        if candidate is None:
            continue
        if isinstance(candidate, str):
            parts.append(candidate)
        elif isinstance(candidate, list):
            for item in candidate:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict):
                    parts.append(str(item.get("name") or item.get("label") or ""))
        elif isinstance(candidate, dict):
            parts.append(str(candidate.get("name") or candidate.get("label") or ""))
        else:
            parts.append(str(candidate))
    return " | ".join(part for part in parts if part).strip()


def _is_relevant_category(category_text: str) -> bool:
    normalized = category_text.strip().lower()
    if not normalized:
        return False
    if "convenience" in normalized and not any(keyword in normalized for keyword in ("grocery", "market", "supermarket")):
        return False
    return any(keyword in normalized for keyword in RELEVANT_CATEGORY_KEYWORDS)


def _normalize_category(category_text: str) -> str | None:
    normalized = category_text.strip().lower()
    if not _is_relevant_category(normalized):
        return None
    if any(keyword in normalized for keyword in ("wholesale club", "warehouse club", "costco", "sam's club")):
        return "wholesale_club"
    if "supermarket" in normalized:
        return "supermarket"
    if "market" in normalized or "grocery" in normalized:
        return "grocery"
    return "grocery"


def _parse_float(value: object) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _load_rows(path: Path) -> list[dict[str, Any]]:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        with path.open(newline="", encoding="utf-8") as fh:
            return [dict(row) for row in csv.DictReader(fh)]
    if suffix in {".jsonl", ".ndjson"}:
        rows: list[dict[str, Any]] = []
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                rows.append(json.loads(line))
        return rows
    raise ValueError(f"Unsupported input format: {path.suffix}")


def _normalize_row(row: dict[str, Any], source: str) -> dict[str, Any] | None:
    categories_text = _categories_text(row)
    category = _normalize_category(categories_text)
    if category is None:
        return None

    source_place_id = _first_non_empty(
        row.get("fsq_place_id"),
        row.get("place_id"),
        row.get("source_place_id"),
        row.get("id"),
    )
    if source_place_id is None:
        return None

    lat = _parse_float(
        _first_non_empty(
            row.get("latitude"),
            row.get("lat"),
            row.get("geocodes.main.latitude") if isinstance(row.get("geocodes"), dict) else None,
            row.get("geocodes", {}).get("main", {}).get("latitude") if isinstance(row.get("geocodes"), dict) else None,
        )
    )
    lon = _parse_float(
        _first_non_empty(
            row.get("longitude"),
            row.get("lon"),
            row.get("geocodes.main.longitude") if isinstance(row.get("geocodes"), dict) else None,
            row.get("geocodes", {}).get("main", {}).get("longitude") if isinstance(row.get("geocodes"), dict) else None,
        )
    )
    if lat is None or lon is None:
        return None

    name = _first_non_empty(row.get("name"), row.get("venue_name"))
    if name is None:
        return None

    if isinstance(row.get("location"), dict):
        location = row["location"]
    else:
        location = {}

    address = _first_non_empty(
        row.get("address"),
        row.get("address_line"),
        location.get("address"),
        location.get("formatted_address"),
    ) or ""
    city = _first_non_empty(row.get("locality"), row.get("city"), location.get("locality"), location.get("city"))
    region = _first_non_empty(row.get("region"), row.get("state"), location.get("region"), location.get("state"))
    postcode = _first_non_empty(row.get("postcode"), row.get("postal_code"), location.get("postcode"), location.get("postal_code"))
    brand = store_discovery.normalize_brand(str(name), _first_non_empty(row.get("brand"), row.get("chain_name")))

    return {
        "store_id": f"{source}:{source_place_id}",
        "name": str(name),
        "brand": brand,
        "lat": lat,
        "lon": lon,
        "address": address,
        "city": city,
        "region": region,
        "postcode": postcode,
        "category": category,
        "source": source,
        "source_priority": store_discovery.SOURCE_PRIORITY.get(source, 85),
        "confidence": store_discovery.SOURCE_CONFIDENCE.get(source, 0.88),
        "raw_record": row,
    }


def main() -> int:
    args = parse_args()
    rows = _load_rows(args.input)
    normalized: list[dict[str, Any]] = []
    skipped_irrelevant = 0
    skipped_invalid = 0
    for row in rows:
        try:
            normalized_row = _normalize_row(row, args.source)
        except Exception:  # noqa: BLE001
            normalized_row = None
        if normalized_row is None:
            category = _categories_text(row)
            if category and not _is_relevant_category(category):
                skipped_irrelevant += 1
            else:
                skipped_invalid += 1
            continue
        normalized.append(normalized_row)

    store_discovery.STORE_DISCOVERY_DB_PATH = args.db_path
    persistence = store_discovery.persist_foursquare_stores(normalized, source=args.source)
    unified_summary = store_discovery.refresh_unified_store_index(main_db_path=args.main_db_path)

    print(f"input={args.input}")
    print(f"db_path={args.db_path}")
    print(f"source={args.source}")
    print(f"rows_read={len(rows)}")
    print(f"rows_ingested={len(normalized)}")
    print(f"rows_skipped_irrelevant={skipped_irrelevant}")
    print(f"rows_skipped_invalid={skipped_invalid}")
    print(
        "persisted input_rows={input_rows} new_rows={new_rows} merged_rows={merged_rows}".format(
            **persistence
        )
    )
    print(
        "unified local_rows={local_rows} live_rows={live_rows} foursquare_rows={foursquare_rows} "
        "unified_rows={unified_rows} duplicates_merged={duplicates_merged}".format(**unified_summary)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
