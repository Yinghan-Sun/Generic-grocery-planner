"""Nearby-store lookup for the generic-food MVP."""

from __future__ import annotations

import json
import math
import os
import re
import time
import urllib.error
import urllib.request
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path

import duckdb

EARTH_RADIUS_M = 6_371_000.0
DEFAULT_RADIUS_M = 10_000.0
DEFAULT_LIMIT = 5
MAX_RADIUS_M = 50_000.0
MAX_LIMIT = 25

STORE_DISCOVERY_MODE = os.getenv("STORE_DISCOVERY_MODE", "local").strip().lower()
OVERPASS_API_URL = os.getenv("OVERPASS_API_URL", "https://overpass-api.de/api/interpreter").strip()
OVERPASS_TIMEOUT_S = float(os.getenv("OVERPASS_TIMEOUT_S", "12"))
OVERPASS_USER_AGENT = os.getenv("OVERPASS_USER_AGENT", "generic-grocery-planner-demo-store-discovery/0.1")
STORE_DISCOVERY_CACHE_TTL_S = int(os.getenv("STORE_DISCOVERY_CACHE_TTL_S", "3600"))
STORE_DISCOVERY_PERSIST_LIVE = os.getenv("STORE_DISCOVERY_PERSIST_LIVE", "true").strip().lower() not in {"0", "false", "no"}
STORE_DISCOVERY_LIVE_INDEX_MAX_AGE_S = int(os.getenv("STORE_DISCOVERY_LIVE_INDEX_MAX_AGE_S", "2592000"))
STORE_DISCOVERY_LIVE_INDEX_MIN_RESULTS = int(os.getenv("STORE_DISCOVERY_LIVE_INDEX_MIN_RESULTS", "3"))
STORE_DISCOVERY_UNIFIED_REFRESH_TTL_S = int(os.getenv("STORE_DISCOVERY_UNIFIED_REFRESH_TTL_S", "300"))
STORE_DISCOVERY_READ_RETRY_COUNT = int(os.getenv("STORE_DISCOVERY_READ_RETRY_COUNT", "6"))
STORE_DISCOVERY_READ_RETRY_DELAY_MS = int(os.getenv("STORE_DISCOVERY_READ_RETRY_DELAY_MS", "150"))
STORE_DISCOVERY_DB_PATH = Path(
    os.getenv("STORE_DISCOVERY_DB_PATH", str(Path(__file__).resolve().parent.parent / "data" / "store_discovery.db"))
)
MAIN_DATA_DB_PATH = Path(os.getenv("STORE_DISCOVERY_MAIN_DB_PATH", str(Path(__file__).resolve().parent.parent / "data" / "data.db")))

_LAST_UNIFIED_REFRESH_AT: datetime | None = None
_LAST_UNIFIED_REFRESH_SUMMARY: dict[str, int] | None = None

SOURCE_PRIORITY = {
    "overpass": 100,
    "store_places_live": 95,
    "foursquare_os_places": 90,
    "foursquare_offline": 85,
    "foursquare_seed": 70,
    "seed": 65,
    "store_places": 60,
}

SOURCE_CONFIDENCE = {
    "overpass": 0.95,
    "store_places_live": 0.9,
    "foursquare_os_places": 0.9,
    "foursquare_offline": 0.88,
    "foursquare_seed": 0.8,
    "seed": 0.75,
    "store_places": 0.7,
}

FOURSQUARE_DISPLAY_CATEGORY_KEYWORDS = (
    "grocery store",
    "supermarket",
    "food market",
    "fruit and vegetable store",
    "produce market",
    "meat market",
    "meat and seafood store",
    "seafood market",
    "fish market",
    "warehouse club",
    "wholesale club",
)

FOURSQUARE_DISPLAY_CATEGORY_EXCLUSIONS = (
    "liquor store",
    "wine store",
    "beer store",
    "candy store",
    "dessert shop",
    "pharmacy",
    "market research",
    "night market",
    "street fair",
    "street food gathering",
    "convenience store",
)


def _normalized_store_text(value: object | None) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").strip().lower().replace("’", "'")).strip()


def _foursquare_category_labels_text(raw_record_json: object | None) -> str:
    if _is_blank_text(raw_record_json):
        return ""
    try:
        raw_record = json.loads(str(raw_record_json))
    except (TypeError, ValueError, json.JSONDecodeError):
        return ""

    labels = raw_record.get("fsq_category_labels") or raw_record.get("category_labels") or raw_record.get("categories")
    parts: list[str] = []
    if isinstance(labels, str):
        parts.append(labels)
    elif isinstance(labels, list):
        for item in labels:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                parts.append(str(item.get("name") or item.get("label") or ""))
    elif isinstance(labels, dict):
        parts.append(str(labels.get("name") or labels.get("label") or ""))
    return " | ".join(part for part in parts if part).strip().lower()


def _normalized_address_value(value: object | None) -> str:
    normalized = _normalized_store_text(value)
    if not normalized:
        return ""

    replacements = {
        "st": "street",
        "rd": "road",
        "blvd": "boulevard",
        "ave": "avenue",
        "dr": "drive",
        "ln": "lane",
        "hwy": "highway",
        "n": "north",
        "s": "south",
        "e": "east",
        "w": "west",
    }
    for source, target in replacements.items():
        normalized = re.sub(rf"\b{re.escape(source)}\b", target, normalized)
    return normalized.strip()


def _address_tokens(value: object | None) -> tuple[str, ...]:
    ignored_tokens = {"ca", "us", "usa"}
    return tuple(token for token in _normalized_address_value(value).split() if token and token not in ignored_tokens)


def _is_blank_text(value: object | None) -> bool:
    return value is None or str(value).strip() == ""


def _addresses_match(first: object | None, second: object | None) -> bool:
    first_normalized = _normalized_address_value(first)
    second_normalized = _normalized_address_value(second)
    if not first_normalized or not second_normalized:
        return False

    if (
        first_normalized == second_normalized
        or first_normalized in second_normalized
        or second_normalized in first_normalized
    ):
        return True

    first_tokens = set(_address_tokens(first))
    second_tokens = set(_address_tokens(second))
    if not first_tokens or not second_tokens:
        return False

    first_numbers = {token for token in first_tokens if token.isdigit()}
    second_numbers = {token for token in second_tokens if token.isdigit()}
    if first_numbers and second_numbers and not (first_numbers & second_numbers):
        return False

    overlap = len(first_tokens & second_tokens)
    required_overlap = max(3, math.ceil(min(len(first_tokens), len(second_tokens)) * 0.75))
    return overlap >= required_overlap


def haversine_distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return the great-circle distance between two coordinates in meters."""
    lat1_rad, lon1_rad = math.radians(lat1), math.radians(lon1)
    lat2_rad, lon2_rad = math.radians(lat2), math.radians(lon2)
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _utcnow_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _query_dicts(con: duckdb.DuckDBPyConnection, query: str, params: dict[str, float | int]) -> list[dict[str, object]]:
    con.execute(query, parameters=params)
    cols = [d[0] for d in con.description or []]
    return [{c: r for c, r in zip(cols, row, strict=True)} for row in con.fetchall()]


def _format_address(parts: Sequence[object]) -> str:
    return ", ".join(str(part) for part in parts if part not in (None, ""))


def _bounding_box(lat: float, lon: float, radius_m: float) -> tuple[float, float, float, float]:
    lat_delta = radius_m / 111_320.0
    lon_scale = max(math.cos(math.radians(lat)), 0.2)
    lon_delta = radius_m / (111_320.0 * lon_scale)
    return lat - lat_delta, lat + lat_delta, lon - lon_delta, lon + lon_delta


def _normalize_store(
    *,
    store_id: str,
    name: str,
    address: str,
    distance_m: float,
    lat: float,
    lon: float,
    category: str,
) -> dict[str, object]:
    return {
        "store_id": store_id,
        "name": name,
        "address": address,
        "distance_m": round(distance_m, 1),
        "lat": float(lat),
        "lon": float(lon),
        "category": category,
    }


def _brand_normalization_value(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.strip().lower().replace("’", "'")).strip()


def normalize_brand(name: str | None, brand: str | None = None) -> str | None:
    raw = brand or name
    if raw is None:
        return None

    normalized = _brand_normalization_value(str(raw))
    if not normalized:
        return None
    if "whole foods" in normalized:
        return "Whole Foods"
    if "trader joe" in normalized:
        return "Trader Joe's"
    if "safeway" in normalized:
        return "Safeway"
    if "costco" in normalized:
        return "Costco"
    if normalized.startswith("target") or " target " in f" {normalized} ":
        return "Target"
    if "walmart" in normalized:
        return "Walmart"
    if "kroger" in normalized:
        return "Kroger"
    if "h mart" in normalized or normalized == "hmart":
        return "H Mart"
    if "sprouts" in normalized:
        return "Sprouts"
    if "99 ranch" in normalized:
        return "99 Ranch Market"
    if "nob hill" in normalized:
        return "Nob Hill Foods"
    return str(raw).strip() or None


def _source_priority(source: str) -> int:
    return SOURCE_PRIORITY.get(source, 50)


def _source_confidence(source: str) -> float:
    return SOURCE_CONFIDENCE.get(source, 0.65)


def _store_id_source_priority(store_id: object | None) -> int:
    identifier = str(store_id or "").lower()
    if identifier.startswith("osm:"):
        return _source_priority("overpass")
    if identifier.startswith("foursquare_offline:"):
        return _source_priority("foursquare_offline")
    if identifier.startswith("foursquare_seed:"):
        return _source_priority("foursquare_seed")
    return _source_priority("store_places")


def _address_detail_score(address: object | None) -> int:
    text = str(address or "").strip()
    if not text:
        return 0
    segments = [segment.strip() for segment in text.split(",") if segment.strip()]
    score = len(segments)
    score += len(_address_tokens(text))
    if re.search(r"\d", text):
        score += 1
    if re.search(r"\b\d{5}(?:-\d{4})?\b", text):
        score += 1
    if re.search(r"\b[A-Z]{2}\b", text):
        score += 1
    return score


def _store_record_rank(record: dict[str, object]) -> tuple[int, int, int, float, str]:
    return (
        _address_detail_score(record.get("address")),
        int(record.get("source_priority") or _store_id_source_priority(record.get("store_id"))),
        int(bool(record.get("brand"))),
        -float(record.get("distance_m") or 0.0),
        str(record.get("store_id") or ""),
    )


def _metadata_score(record: dict[str, object]) -> int:
    score = 0
    if not _is_blank_text(record.get("city")):
        score += 4
    if not _is_blank_text(record.get("region")):
        score += 4
    if not _is_blank_text(record.get("postcode")):
        score += 2
    if not _is_blank_text(record.get("address")):
        score += min(_address_detail_score(record.get("address")), 8)
    return score


def _address_looks_like_store_name(record: dict[str, object]) -> bool:
    address = _normalized_address_value(record.get("address"))
    if not address:
        return False
    name = _normalized_store_text(record.get("brand") or record.get("name"))
    return bool(name) and (address == name or address in name or name in address)


def _latest_timestamp(first: object | None, second: object | None) -> object | None:
    if first is None:
        return second
    if second is None:
        return first
    return max(first, second)


def _preferred_address(primary: object | None, alternate: object | None) -> object | None:
    if _is_blank_text(primary):
        return alternate
    if _is_blank_text(alternate):
        return primary
    primary_score = _address_detail_score(primary)
    alternate_score = _address_detail_score(alternate)
    if alternate_score > primary_score + 1:
        return alternate
    return primary


def _preferred_record_address(primary: dict[str, object], alternate: dict[str, object]) -> object | None:
    if _address_looks_like_store_name(primary) and not _address_looks_like_store_name(alternate):
        return alternate.get("address") or primary.get("address")
    if _address_looks_like_store_name(alternate) and not _address_looks_like_store_name(primary):
        return primary.get("address") or alternate.get("address")
    return _preferred_address(primary.get("address"), alternate.get("address"))


def _merge_store_records(first: dict[str, object], second: dict[str, object]) -> dict[str, object]:
    preferred = first
    alternate = second
    if _store_record_rank(second) > _store_record_rank(first):
        preferred = second
        alternate = first

    metadata_owner = preferred
    metadata_fallback = alternate
    if _metadata_score(alternate) > _metadata_score(preferred):
        metadata_owner = alternate
        metadata_fallback = preferred

    merged = dict(preferred)
    merged["brand"] = preferred.get("brand") or alternate.get("brand")
    merged["address"] = _preferred_record_address(metadata_owner, metadata_fallback)
    for field in ("city", "region", "postcode"):
        merged[field] = (
            metadata_owner.get(field)
            or preferred.get(field)
            or metadata_fallback.get(field)
            or alternate.get(field)
        )
    merged["confidence"] = max(
        float(preferred.get("confidence") or 0.0),
        float(alternate.get("confidence") or 0.0),
    )
    merged["last_seen_at"] = _latest_timestamp(preferred.get("last_seen_at"), alternate.get("last_seen_at"))
    merged["metadata_source"] = str(metadata_owner.get("source") or preferred.get("source") or "")
    merged["metadata_confidence"] = float(metadata_owner.get("confidence") or preferred.get("confidence") or 0.0)
    return merged


def _merge_store_metadata(
    primary: dict[str, object],
    enrichment: dict[str, object],
) -> dict[str, object]:
    merged = dict(primary)
    merged["brand"] = primary.get("brand") or enrichment.get("brand")
    merged["address"] = _preferred_record_address(primary, enrichment)
    for field in ("city", "region", "postcode"):
        merged[field] = primary.get(field) or enrichment.get(field)
    merged["confidence"] = max(
        float(primary.get("confidence") or 0.0),
        float(enrichment.get("confidence") or 0.0),
    )
    merged["last_seen_at"] = _latest_timestamp(primary.get("last_seen_at"), enrichment.get("last_seen_at"))
    if _metadata_score(enrichment) > _metadata_score(primary):
        merged["metadata_source"] = str(enrichment.get("source") or primary.get("metadata_source") or primary.get("source") or "")
        merged["metadata_confidence"] = float(enrichment.get("confidence") or primary.get("metadata_confidence") or primary.get("confidence") or 0.0)
    else:
        merged["metadata_source"] = str(primary.get("metadata_source") or primary.get("source") or "")
        merged["metadata_confidence"] = float(primary.get("metadata_confidence") or primary.get("confidence") or 0.0)
    return merged


def _dedupe_bucket_ids(
    record: dict[str, object],
    *,
    grid_size: float = 0.002,
) -> tuple[tuple[str, int, int], list[tuple[str, int, int]]]:
    name = _normalized_store_text(record.get("brand") or record.get("name"))
    lat_bucket = int(round(float(record["lat"]) / grid_size))
    lon_bucket = int(round(float(record["lon"]) / grid_size))
    primary_bucket = (name, lat_bucket, lon_bucket)
    nearby = [
        (name, lat_bucket + lat_delta, lon_bucket + lon_delta)
        for lat_delta in (-1, 0, 1)
        for lon_delta in (-1, 0, 1)
    ]
    return primary_bucket, nearby


def _records_match_for_dedupe(first: dict[str, object], second: dict[str, object]) -> bool:
    first_name = _normalized_store_text(first.get("brand") or first.get("name"))
    second_name = _normalized_store_text(second.get("brand") or second.get("name"))
    if not first_name or first_name != second_name:
        return False

    distance_m = haversine_distance_m(
        float(first["lat"]),
        float(first["lon"]),
        float(second["lat"]),
        float(second["lon"]),
    )
    first_address = _normalized_address_value(first.get("address"))
    second_address = _normalized_address_value(second.get("address"))

    if first_address and second_address:
        addresses_match = _addresses_match(first_address, second_address)
        if addresses_match and distance_m <= 120.0:
            return True

        if distance_m <= 25.0:
            first_postcode = str(first.get("postcode") or "").strip()
            second_postcode = str(second.get("postcode") or "").strip()
            if first_postcode and second_postcode and first_postcode == second_postcode:
                return True

        if distance_m <= 20.0 and (_address_looks_like_store_name(first) or _address_looks_like_store_name(second)):
            return True

        return False

    return distance_m <= 60.0


def _dedupe_store_records(records: list[dict[str, object]]) -> tuple[list[dict[str, object]], int]:
    deduped: list[dict[str, object]] = []
    merged_duplicates = 0
    bucket_index: dict[tuple[str, int, int], list[int]] = {}

    for record in records:
        primary_bucket, nearby_buckets = _dedupe_bucket_ids(record)
        candidate_indices: list[int] = []
        seen_indices: set[int] = set()
        for bucket in nearby_buckets:
            for candidate_index in bucket_index.get(bucket, []):
                if candidate_index in seen_indices:
                    continue
                candidate_indices.append(candidate_index)
                seen_indices.add(candidate_index)

        matched_index = next(
            (index for index in candidate_indices if _records_match_for_dedupe(deduped[index], record)),
            None,
        )
        if matched_index is None:
            deduped.append(record)
            bucket_index.setdefault(primary_bucket, []).append(len(deduped) - 1)
            continue

        merged_duplicates += 1
        deduped[matched_index] = _merge_store_records(deduped[matched_index], record)
    return deduped, merged_duplicates


def _enrich_store_records(
    records: list[dict[str, object]],
    enrichment_records: list[dict[str, object]],
) -> tuple[list[dict[str, object]], int]:
    if not records or not enrichment_records:
        return records, 0

    enriched = [dict(record) for record in records]
    bucket_index: dict[tuple[str, int, int], list[int]] = {}
    for index, record in enumerate(enriched):
        primary_bucket, _ = _dedupe_bucket_ids(record)
        bucket_index.setdefault(primary_bucket, []).append(index)

    actual_enrichments = 0
    tracked_fields = ("address", "city", "region", "postcode", "metadata_source")
    for record in enrichment_records:
        _, nearby_buckets = _dedupe_bucket_ids(record)
        candidate_indices: list[int] = []
        seen_indices: set[int] = set()
        for bucket in nearby_buckets:
            for candidate_index in bucket_index.get(bucket, []):
                if candidate_index in seen_indices:
                    continue
                candidate_indices.append(candidate_index)
                seen_indices.add(candidate_index)

        matched_index = next(
            (index for index in candidate_indices if _records_match_for_dedupe(enriched[index], record)),
            None,
        )
        if matched_index is None:
            continue

        before = {field: enriched[matched_index].get(field) for field in tracked_fields}
        enriched[matched_index] = _merge_store_metadata(enriched[matched_index], record)
        after = {field: enriched[matched_index].get(field) for field in tracked_fields}
        if after != before:
            actual_enrichments += 1

    return enriched, actual_enrichments


def _finalize_store_results(stores: list[dict[str, object]], limit: int) -> list[dict[str, object]]:
    deduped, _ = _dedupe_store_records(stores)
    deduped.sort(key=lambda store: (float(store["distance_m"]), str(store["name"]), str(store["address"])))
    return deduped[:limit]


def _runtime_con() -> duckdb.DuckDBPyConnection:
    STORE_DISCOVERY_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(STORE_DISCOVERY_DB_PATH)
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
    con.execute("""ALTER TABLE store_places_live ADD COLUMN IF NOT EXISTS brand VARCHAR""")
    con.execute("""ALTER TABLE store_places_live ADD COLUMN IF NOT EXISTS city VARCHAR""")
    con.execute("""ALTER TABLE store_places_live ADD COLUMN IF NOT EXISTS region VARCHAR""")
    con.execute("""ALTER TABLE store_places_live ADD COLUMN IF NOT EXISTS postcode VARCHAR""")
    con.execute("""ALTER TABLE store_places_unified ADD COLUMN IF NOT EXISTS metadata_source VARCHAR""")
    con.execute("""ALTER TABLE store_places_unified ADD COLUMN IF NOT EXISTS metadata_confidence DOUBLE""")
    return con


def _readonly_runtime_con() -> duckdb.DuckDBPyConnection | None:
    if not STORE_DISCOVERY_DB_PATH.exists():
        return None

    attempts = max(1, STORE_DISCOVERY_READ_RETRY_COUNT)
    delay_s = max(0.0, STORE_DISCOVERY_READ_RETRY_DELAY_MS / 1000.0)
    for attempt in range(attempts):
        try:
            return duckdb.connect(STORE_DISCOVERY_DB_PATH, read_only=True)
        except duckdb.Error:
            if attempt + 1 >= attempts:
                break
            if delay_s > 0:
                time.sleep(delay_s)
    return None


def _unified_index_row_count() -> int:
    runtime_con = _readonly_runtime_con()
    if runtime_con is None:
        return 0

    try:
        row = runtime_con.execute("SELECT COUNT(*) FROM store_places_unified").fetchone()
    except duckdb.Error:
        return 0
    finally:
        runtime_con.close()

    if row is None:
        return 0
    return int(row[0] or 0)


def _ensure_unified_index_available(
    *,
    main_con: duckdb.DuckDBPyConnection | None = None,
    main_db_path: Path | None = None,
) -> bool:
    if _unified_index_row_count() > 0:
        return True

    summary = refresh_unified_store_index(main_con=main_con, main_db_path=main_db_path, force=True)
    return int(summary.get("unified_rows", 0)) > 0


def _cache_query_key(lat: float, lon: float, radius_m: float, limit: int, source: str = "overpass") -> str:
    rounded_lat = round(lat, 4)
    rounded_lon = round(lon, 4)
    rounded_radius = int(round(radius_m))
    return f"{source}:{rounded_lat:.4f}:{rounded_lon:.4f}:{rounded_radius}:{int(limit)}"


def _cache_lookup(lat: float, lon: float, radius_m: float, limit: int, source: str = "overpass") -> list[dict[str, object]] | None:
    query_key = _cache_query_key(lat, lon, radius_m, limit, source=source)
    row = None
    try:
        with _runtime_con() as con:
            row = con.execute(
                """
                SELECT results_json, fetched_at
                FROM store_search_cache
                WHERE query_key = $query_key
                """,
                {"query_key": query_key},
            ).fetchone()
    except duckdb.Error:
        readonly_con = _readonly_runtime_con()
        if readonly_con is None:
            return None
        try:
            row = readonly_con.execute(
                """
                SELECT results_json, fetched_at
                FROM store_search_cache
                WHERE query_key = $query_key
                """,
                {"query_key": query_key},
            ).fetchone()
        except duckdb.Error:
            return None
        finally:
            readonly_con.close()
    if row is None:
        return None

    results_json, fetched_at = row
    if fetched_at is None:
        return None
    age_s = (datetime.now(UTC) - _as_utc(fetched_at)).total_seconds()
    if age_s > STORE_DISCOVERY_CACHE_TTL_S:
        return None
    try:
        cached_results = json.loads(results_json)
    except (TypeError, json.JSONDecodeError):
        return None
    if not isinstance(cached_results, list):
        return None
    return _finalize_store_results(cached_results, limit)


def _cache_store(lat: float, lon: float, radius_m: float, limit: int, stores: list[dict[str, object]], source: str = "overpass") -> None:
    query_key = _cache_query_key(lat, lon, radius_m, limit, source=source)
    now = _utcnow_naive()
    stores = _finalize_store_results(stores, limit)
    try:
        with _runtime_con() as con:
            con.execute(
                """
                INSERT OR REPLACE INTO store_search_cache (
                  query_key, lat, lon, radius_m, result_limit, source, results_json, fetched_at
                )
                VALUES ($query_key, $lat, $lon, $radius_m, $limit, $source, $results_json, $fetched_at)
                """,
                {
                    "query_key": query_key,
                    "lat": lat,
                    "lon": lon,
                    "radius_m": radius_m,
                    "limit": limit,
                    "source": source,
                    "results_json": json.dumps(stores, separators=(",", ":")),
                    "fetched_at": now,
                },
            )
    except duckdb.Error:
        return


def _persist_live_stores(live_rows: list[tuple[dict[str, object], dict[str, object]]], source: str = "overpass") -> None:
    if not STORE_DISCOVERY_PERSIST_LIVE or not live_rows:
        return

    now = _utcnow_naive()
    try:
        with _runtime_con() as con:
            for store, raw_record in live_rows:
                store_id = str(store["store_id"])
                source_place_id = ":".join(store_id.split(":")[1:])
                con.execute(
                    """
                    INSERT OR REPLACE INTO store_places_live (
                      store_id, source, source_place_id, name, brand, address, city, region, postcode, category, lat, lon, last_seen_at,
                      raw_record_json
                    )
                    VALUES (
                      $store_id, $source, $source_place_id, $name, $brand, $address, $city, $region, $postcode, $category, $lat, $lon,
                      $last_seen_at, $raw_record_json
                    )
                    """,
                    {
                        "store_id": store_id,
                        "source": source,
                        "source_place_id": source_place_id,
                        "name": store["name"],
                        "brand": normalize_brand(str(store["name"]), str(raw_record.get("tags", {}).get("brand") or raw_record.get("tags", {}).get("operator") or "")),
                        "address": store["address"],
                        "city": raw_record.get("_city"),
                        "region": raw_record.get("_region"),
                        "postcode": raw_record.get("_postcode"),
                        "category": store["category"],
                        "lat": store["lat"],
                        "lon": store["lon"],
                        "last_seen_at": now,
                        "raw_record_json": json.dumps(raw_record, separators=(",", ":")),
                    },
                )
    except duckdb.Error:
        return


def persist_foursquare_stores(records: list[dict[str, object]], source: str = "foursquare_offline") -> dict[str, int]:
    if not records:
        return {"input_rows": 0, "new_rows": 0, "merged_rows": 0}

    try:
        with _runtime_con() as con:
            existing_ids = {
                str(row[0])
                for row in con.execute(
                    "SELECT store_id FROM store_places_foursquare WHERE store_id IN (SELECT UNNEST($store_ids))",
                    {"store_ids": [str(record["store_id"]) for record in records]},
                ).fetchall()
            }
            con.executemany(
                """
                INSERT OR REPLACE INTO store_places_foursquare (
                  store_id, name, brand, lat, lon, address, city, region, postcode, category,
                  source, source_priority, confidence, last_seen_at, raw_record_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        str(record["store_id"]),
                        str(record["name"]),
                        normalize_brand(str(record["name"]), str(record.get("brand") or "")),
                        float(record["lat"]),
                        float(record["lon"]),
                        str(record.get("address") or ""),
                        record.get("city"),
                        record.get("region"),
                        record.get("postcode"),
                        str(record["category"]),
                        str(record.get("source") or source),
                        int(record.get("source_priority") or _source_priority(source)),
                        float(record.get("confidence") or _source_confidence(source)),
                        record.get("last_seen_at") or _utcnow_naive(),
                        json.dumps(record.get("raw_record") or {}, separators=(",", ":")),
                    )
                    for record in records
                ],
            )
            merged_rows = len(existing_ids)
            return {
                "input_rows": len(records),
                "new_rows": len(records) - merged_rows,
                "merged_rows": merged_rows,
            }
    except duckdb.Error:
        return {"input_rows": len(records), "new_rows": 0, "merged_rows": 0}


def _local_index_records(con: duckdb.DuckDBPyConnection) -> list[dict[str, object]]:
    rows = _query_dicts(
        con,
        """
        SELECT
          store_id,
          source,
          name,
          brand,
          category_primary,
          lat,
          lon,
          address_line,
          city,
          region,
          postcode
        FROM store_places
        WHERE is_grocery
        ORDER BY source, name
        """,
        {},
    )
    records: list[dict[str, object]] = []
    for row in rows:
        source = str(row["source"] or "store_places")
        records.append(
            {
                "store_id": str(row["store_id"]),
                "name": str(row["name"]),
                "brand": normalize_brand(str(row["name"]), str(row["brand"] or "")),
                "lat": float(row["lat"]),
                "lon": float(row["lon"]),
                "address": _format_address((row["address_line"], row["city"], row["region"], row["postcode"])),
                "city": str(row["city"] or "") or None,
                "region": str(row["region"] or "") or None,
                "postcode": str(row["postcode"] or "") or None,
                "category": str(row["category_primary"] or "grocery"),
                "source": source,
                "source_priority": _source_priority(source),
                "confidence": _source_confidence(source),
                "metadata_source": source,
                "metadata_confidence": _source_confidence(source),
                "last_seen_at": None,
            }
        )
    return records


def _live_index_records(runtime_con: duckdb.DuckDBPyConnection) -> list[dict[str, object]]:
    rows = runtime_con.execute(
        """
        SELECT
          store_id,
          source,
          name,
          brand,
          address,
          city,
          region,
          postcode,
          category,
          lat,
          lon,
          last_seen_at
        FROM store_places_live
        ORDER BY last_seen_at DESC, name
        """
    ).fetchall()
    records: list[dict[str, object]] = []
    for row in rows:
        source = str(row[1] or "store_places_live")
        records.append(
            {
                "store_id": str(row[0]),
                "name": str(row[2]),
                "brand": normalize_brand(str(row[2]), str(row[3] or "")),
                "address": str(row[4] or ""),
                "city": str(row[5] or "") or None,
                "region": str(row[6] or "") or None,
                "postcode": str(row[7] or "") or None,
                "category": str(row[8] or "grocery"),
                "lat": float(row[9]),
                "lon": float(row[10]),
                "source": source,
                "source_priority": _source_priority(source),
                "confidence": _source_confidence(source),
                "metadata_source": source,
                "metadata_confidence": _source_confidence(source),
                "last_seen_at": row[11],
            }
        )
    return records


def _foursquare_index_records(runtime_con: duckdb.DuckDBPyConnection) -> list[dict[str, object]]:
    rows = runtime_con.execute(
        """
        SELECT
          store_id,
          name,
          brand,
          lat,
          lon,
          address,
          city,
          region,
          postcode,
          category,
          source,
          source_priority,
          confidence,
          last_seen_at,
          raw_record_json
        FROM store_places_foursquare
        ORDER BY last_seen_at DESC, name
        """
    ).fetchall()
    return [
        {
            "store_id": str(row[0]),
            "name": str(row[1]),
            "brand": normalize_brand(str(row[1]), str(row[2] or "")),
            "lat": float(row[3]),
            "lon": float(row[4]),
            "address": str(row[5] or ""),
            "city": str(row[6] or "") or None,
            "region": str(row[7] or "") or None,
            "postcode": str(row[8] or "") or None,
            "category": str(row[9] or "grocery"),
            "source": str(row[10] or "foursquare_offline"),
            "source_priority": int(row[11] or _source_priority("foursquare_offline")),
            "confidence": float(row[12] or _source_confidence("foursquare_offline")),
            "metadata_source": str(row[10] or "foursquare_offline"),
            "metadata_confidence": float(row[12] or _source_confidence("foursquare_offline")),
            "last_seen_at": row[13],
            "category_labels_text": _foursquare_category_labels_text(row[14]),
        }
        for row in rows
    ]


def _is_high_quality_foursquare_record(record: dict[str, object]) -> bool:
    if _is_blank_text(record.get("name")):
        return False
    if _is_blank_text(record.get("city")) or _is_blank_text(record.get("region")):
        return False
    if _is_blank_text(record.get("address")):
        return False
    if _address_looks_like_store_name(record) and _is_blank_text(record.get("postcode")):
        return False
    labels_text = str(record.get("category_labels_text") or "").lower()
    if labels_text:
        if any(keyword in labels_text for keyword in FOURSQUARE_DISPLAY_CATEGORY_EXCLUSIONS):
            return False
        if not any(keyword in labels_text for keyword in FOURSQUARE_DISPLAY_CATEGORY_KEYWORDS):
            return False
    return True


def _split_foursquare_records_for_unified(
    records: list[dict[str, object]],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    display_records: list[dict[str, object]] = []
    enrichment_records: list[dict[str, object]] = []
    for record in records:
        source = str(record.get("source") or "")
        if source.startswith("foursquare_os_places"):
            if _is_high_quality_foursquare_record(record):
                display_records.append(record)
            else:
                enrichment_records.append(record)
            continue
        display_records.append(record)
    return display_records, enrichment_records


def refresh_unified_store_index(
    main_con: duckdb.DuckDBPyConnection | None = None,
    *,
    main_db_path: Path | None = None,
    force: bool = True,
) -> dict[str, int]:
    global _LAST_UNIFIED_REFRESH_AT, _LAST_UNIFIED_REFRESH_SUMMARY
    main_db_path = MAIN_DATA_DB_PATH if main_db_path is None else main_db_path
    if not force and _LAST_UNIFIED_REFRESH_AT is not None and _LAST_UNIFIED_REFRESH_SUMMARY is not None:
        age_s = (_utcnow_naive() - _LAST_UNIFIED_REFRESH_AT).total_seconds()
        if age_s < STORE_DISCOVERY_UNIFIED_REFRESH_TTL_S:
            return dict(_LAST_UNIFIED_REFRESH_SUMMARY)

    local_records: list[dict[str, object]] = []

    if main_con is not None:
        local_records = _local_index_records(main_con)
    elif main_db_path.exists():
        with duckdb.connect(main_db_path, read_only=True) as local_con:
            local_records = _local_index_records(local_con)

    try:
        with _runtime_con() as runtime_con:
            live_records = _live_index_records(runtime_con)
            foursquare_records = _foursquare_index_records(runtime_con)
            foursquare_display_records, foursquare_enrichment_records = _split_foursquare_records_for_unified(
                foursquare_records
            )
            combined = live_records + foursquare_display_records + local_records
            combined.sort(
                key=lambda record: (
                    -int(record["source_priority"]),
                    str(record.get("last_seen_at") or ""),
                    str(record["name"]).lower(),
                    str(record["store_id"]).lower(),
                )
            )

            deduped, merged_duplicates = _dedupe_store_records(combined)
            deduped, enriched_matches = _enrich_store_records(deduped, foursquare_enrichment_records)

            runtime_con.execute("DELETE FROM store_places_unified")
            runtime_con.executemany(
                """
                INSERT INTO store_places_unified (
                  store_id, name, brand, lat, lon, address, city, region, postcode, category,
                  source, source_priority, confidence, metadata_source, metadata_confidence, last_seen_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        record["store_id"],
                        record["name"],
                        record.get("brand"),
                        record["lat"],
                        record["lon"],
                        record.get("address"),
                        record.get("city"),
                        record.get("region"),
                        record.get("postcode"),
                        record["category"],
                        record["source"],
                        record["source_priority"],
                        record["confidence"],
                        record.get("metadata_source"),
                        record.get("metadata_confidence"),
                        record.get("last_seen_at"),
                    )
                    for record in deduped
                ],
            )
            summary = {
                "local_rows": len(local_records),
                "live_rows": len(live_records),
                "foursquare_rows": len(foursquare_display_records),
                "foursquare_enrichment_rows": len(foursquare_enrichment_records),
                "unified_rows": len(deduped),
                "duplicates_merged": merged_duplicates,
                "metadata_enriched": enriched_matches,
            }
            _LAST_UNIFIED_REFRESH_AT = _utcnow_naive()
            _LAST_UNIFIED_REFRESH_SUMMARY = dict(summary)
            return summary
    except duckdb.Error:
        summary = {
            "local_rows": len(local_records),
            "live_rows": 0,
            "foursquare_rows": 0,
            "foursquare_enrichment_rows": 0,
            "unified_rows": 0,
            "duplicates_merged": 0,
            "metadata_enriched": 0,
        }
        if force:
            _LAST_UNIFIED_REFRESH_AT = None
            _LAST_UNIFIED_REFRESH_SUMMARY = None
        return summary


def normalize_store_snapshot(stores: Sequence[object] | None, *, limit: int) -> list[dict[str, object]]:
    if not stores:
        return []

    normalized: list[dict[str, object]] = []
    for raw_store in stores:
        if not isinstance(raw_store, dict):
            continue

        name = str(raw_store.get("name") or "").strip()
        if not name:
            continue

        try:
            lat = float(raw_store["lat"])
            lon = float(raw_store["lon"])
        except (KeyError, TypeError, ValueError):
            continue

        distance_value = raw_store.get("distance_m")
        try:
            distance_m = float(distance_value if distance_value is not None else 0.0)
        except (TypeError, ValueError):
            distance_m = 0.0

        record = _normalize_store(
            store_id=str(raw_store.get("store_id") or f"snapshot:{_normalized_store_text(name)}:{round(lat, 4)}:{round(lon, 4)}"),
            name=name,
            address=str(raw_store.get("address") or "").strip(),
            distance_m=distance_m,
            lat=lat,
            lon=lon,
            category=str(raw_store.get("category") or "grocery").strip() or "grocery",
        )
        brand = normalize_brand(name, str(raw_store.get("brand") or ""))
        if brand:
            record["brand"] = brand
        source_priority = raw_store.get("source_priority")
        try:
            if source_priority is not None:
                record["source_priority"] = int(source_priority)
        except (TypeError, ValueError):
            pass
        normalized.append(record)

    finalized = _finalize_store_results(normalized, limit)
    for record in finalized:
        record.pop("brand", None)
        record.pop("source_priority", None)
    return finalized


def _unified_nearby_stores(
    lat: float,
    lon: float,
    radius_m: float,
    limit: int,
) -> list[dict[str, object]] | None:
    lat_min, lat_max, lon_min, lon_max = _bounding_box(lat, lon, radius_m)
    runtime_con = _readonly_runtime_con()
    if runtime_con is None:
        return None

    try:
        rows = runtime_con.execute(
            """
            SELECT
              store_id,
              name,
              address,
              category,
              lat,
              lon,
              source_priority
            FROM store_places_unified
            WHERE lat BETWEEN $lat_min AND $lat_max
              AND lon BETWEEN $lon_min AND $lon_max
            ORDER BY source_priority DESC, name
            """,
            {
                "lat_min": lat_min,
                "lat_max": lat_max,
                "lon_min": lon_min,
                "lon_max": lon_max,
            },
        ).fetchall()
    except duckdb.Error:
        return None
    finally:
        runtime_con.close()

    stores: list[dict[str, object]] = []
    for row in rows:
        distance_m = haversine_distance_m(lat, lon, float(row[4]), float(row[5]))
        if distance_m > radius_m:
            continue
        stores.append(
            _normalize_store(
                store_id=str(row[0]),
                name=str(row[1]),
                address=str(row[2] or ""),
                distance_m=distance_m,
                lat=float(row[4]),
                lon=float(row[5]),
                category=str(row[3] or "grocery"),
            )
        )

    return _finalize_store_results(stores, limit)


def _unified_nearby_stores_with_retry(
    lat: float,
    lon: float,
    radius_m: float,
    limit: int,
) -> list[dict[str, object]] | None:
    attempts = max(1, STORE_DISCOVERY_READ_RETRY_COUNT)
    delay_s = max(0.0, STORE_DISCOVERY_READ_RETRY_DELAY_MS / 1000.0)
    for attempt in range(attempts):
        stores = _unified_nearby_stores(lat=lat, lon=lon, radius_m=radius_m, limit=limit)
        if stores is not None:
            return stores
        if attempt + 1 >= attempts:
            break
        if delay_s > 0:
            time.sleep(delay_s)
    return None


def _local_nearby_stores(
    con: duckdb.DuckDBPyConnection,
    lat: float,
    lon: float,
    radius_m: float,
    limit: int,
) -> list[dict[str, object]]:
    lat_min, lat_max, lon_min, lon_max = _bounding_box(lat, lon, radius_m)
    rows = _query_dicts(
        con,
        """
        SELECT
          store_id,
          name,
          category_primary,
          lat,
          lon,
          address_line,
          city,
          region,
          postcode
        FROM store_places
        WHERE is_grocery
          AND lat BETWEEN $lat_min AND $lat_max
          AND lon BETWEEN $lon_min AND $lon_max
        ORDER BY name
        """,
        {
            "lat_min": lat_min,
            "lat_max": lat_max,
            "lon_min": lon_min,
            "lon_max": lon_max,
        },
    )

    stores: list[dict[str, object]] = []
    for row in rows:
        distance_m = haversine_distance_m(lat, lon, float(row["lat"]), float(row["lon"]))
        if distance_m > radius_m:
            continue
        stores.append(
            _normalize_store(
                store_id=str(row["store_id"]),
                name=str(row["name"]),
                address=_format_address((row["address_line"], row["city"], row["region"], row["postcode"])),
                distance_m=distance_m,
                lat=float(row["lat"]),
                lon=float(row["lon"]),
                category=str(row["category_primary"]),
            )
        )

    return _finalize_store_results(stores, limit)


def _persisted_live_nearby_stores(
    lat: float,
    lon: float,
    radius_m: float,
    limit: int,
    *,
    max_age_s: int | None = None,
) -> list[dict[str, object]]:
    max_age_s = STORE_DISCOVERY_LIVE_INDEX_MAX_AGE_S if max_age_s is None else max_age_s
    cutoff = _utcnow_naive() - timedelta(seconds=max_age_s)
    lat_min, lat_max, lon_min, lon_max = _bounding_box(lat, lon, radius_m)

    runtime_con = _readonly_runtime_con()
    if runtime_con is None:
        return []

    try:
        rows = runtime_con.execute(
            """
            SELECT
              store_id,
              name,
              address,
              category,
              lat,
              lon,
              last_seen_at
            FROM store_places_live
            WHERE lat BETWEEN $lat_min AND $lat_max
              AND lon BETWEEN $lon_min AND $lon_max
              AND last_seen_at >= $cutoff
            ORDER BY last_seen_at DESC, name
            """,
            {
                "lat_min": lat_min,
                "lat_max": lat_max,
                "lon_min": lon_min,
                "lon_max": lon_max,
                "cutoff": cutoff,
            },
        ).fetchall()
    except duckdb.Error:
        runtime_con.close()
        return []
    finally:
        runtime_con.close()

    stores: list[dict[str, object]] = []
    for row in rows:
        distance_m = haversine_distance_m(lat, lon, float(row[4]), float(row[5]))
        if distance_m > radius_m:
            continue
        stores.append(
            _normalize_store(
                store_id=str(row[0]),
                name=str(row[1]),
                address=str(row[2] or ""),
                distance_m=distance_m,
                lat=float(row[4]),
                lon=float(row[5]),
                category=str(row[3]),
            )
        )

    return _finalize_store_results(stores, limit)


def _has_sufficient_persisted_results(stores: list[dict[str, object]], limit: int) -> bool:
    required_results = max(1, min(limit, STORE_DISCOVERY_LIVE_INDEX_MIN_RESULTS))
    return len(stores) >= required_results


def _overpass_query(lat: float, lon: float, radius_m: float) -> str:
    radius = int(round(radius_m))
    return f"""
[out:json][timeout:{int(max(5, min(OVERPASS_TIMEOUT_S, 60)))}];
(
  node["shop"~"^(supermarket|grocery)$"](around:{radius},{lat},{lon});
  way["shop"~"^(supermarket|grocery)$"](around:{radius},{lat},{lon});
  relation["shop"~"^(supermarket|grocery)$"](around:{radius},{lat},{lon});
);
out center tags;
""".strip()


def _overpass_address(tags: dict[str, object]) -> str:
    street = _format_address((tags.get("addr:housenumber"), tags.get("addr:street")))
    city = tags.get("addr:city") or tags.get("addr:town") or tags.get("addr:village")
    region = tags.get("addr:state")
    postcode = tags.get("addr:postcode")
    address = _format_address((street, city, region, postcode))
    if address:
        return address
    return _format_address((tags.get("brand"), tags.get("operator"), tags.get("addr:suburb")))


def _overpass_location_parts(tags: dict[str, object]) -> tuple[str | None, str | None, str | None]:
    city = tags.get("addr:city") or tags.get("addr:town") or tags.get("addr:village")
    region = tags.get("addr:state")
    postcode = tags.get("addr:postcode")
    return (
        str(city) if city else None,
        str(region) if region else None,
        str(postcode) if postcode else None,
    )


def _overpass_coordinates(element: dict[str, object]) -> tuple[float, float] | None:
    if "lat" in element and "lon" in element:
        return float(element["lat"]), float(element["lon"])
    center = element.get("center")
    if isinstance(center, dict) and "lat" in center and "lon" in center:
        return float(center["lat"]), float(center["lon"])
    return None


def _dedupe_key(name: str, address: str, lat: float, lon: float) -> tuple[str, str, float, float]:
    return (name.strip().lower(), address.strip().lower(), round(lat, 4), round(lon, 4))


def _live_overpass_nearby_stores(
    lat: float,
    lon: float,
    radius_m: float,
    limit: int,
) -> list[tuple[dict[str, object], dict[str, object]]]:
    query = _overpass_query(lat, lon, radius_m)
    request = urllib.request.Request(
        OVERPASS_API_URL,
        data=query.encode("utf-8"),
        headers={
            "Content-Type": "text/plain; charset=utf-8",
            "Accept": "application/json",
            "User-Agent": OVERPASS_USER_AGENT,
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=OVERPASS_TIMEOUT_S) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError("Live Overpass lookup failed.") from exc

    elements = payload.get("elements", [])
    if not isinstance(elements, list):
        return []

    live_rows: list[tuple[dict[str, object], dict[str, object]]] = []
    seen: set[tuple[str, str, float, float]] = set()
    for element in elements:
        if not isinstance(element, dict):
            continue
        tags = element.get("tags")
        if not isinstance(tags, dict):
            continue
        coordinates = _overpass_coordinates(element)
        if coordinates is None:
            continue
        store_lat, store_lon = coordinates
        distance_m = haversine_distance_m(lat, lon, store_lat, store_lon)
        if distance_m > radius_m:
            continue

        category = str(tags.get("shop", "grocery"))
        name = str(tags.get("name") or tags.get("brand") or "Unnamed grocery store")
        address = _overpass_address(tags)
        dedupe = _dedupe_key(name, address, store_lat, store_lon)
        if dedupe in seen:
            continue
        seen.add(dedupe)

        osm_type = str(element.get("type", "node"))
        osm_id = element.get("id")
        city, region, postcode = _overpass_location_parts(tags)
        raw_record = dict(element)
        raw_record["_city"] = city
        raw_record["_region"] = region
        raw_record["_postcode"] = postcode
        store = _normalize_store(
            store_id=f"osm:{osm_type}:{osm_id}",
            name=name,
            address=address,
            distance_m=distance_m,
            lat=store_lat,
            lon=store_lon,
            category=category,
        )
        live_rows.append((store, raw_record))

    live_rows.sort(key=lambda item: (float(item[0]["distance_m"]), str(item[0]["name"])))
    return live_rows[:limit]


def nearby_stores(
    con: duckdb.DuckDBPyConnection,
    lat: float,
    lon: float,
    radius_m: float = DEFAULT_RADIUS_M,
    limit: int = DEFAULT_LIMIT,
) -> list[dict[str, object]]:
    """Return nearby stores sorted by distance.

    Lookup order:
    - ``local`` mode: unified local index, then seed ``store_places``
    - ``auto`` mode: unified local index if present, then cache,
      then live Overpass, then seed ``store_places``
    - ``live`` mode: cache, then live Overpass
    """
    mode = STORE_DISCOVERY_MODE if STORE_DISCOVERY_MODE in {"auto", "live", "local"} else "auto"

    if mode in {"auto", "local"}:
        _ensure_unified_index_available(main_con=con)

    if mode == "local":
        unified_stores = _unified_nearby_stores_with_retry(lat=lat, lon=lon, radius_m=radius_m, limit=limit)
        if unified_stores:
            return unified_stores
        return _local_nearby_stores(con=con, lat=lat, lon=lon, radius_m=radius_m, limit=limit)

    if mode == "auto":
        unified_stores = _unified_nearby_stores_with_retry(lat=lat, lon=lon, radius_m=radius_m, limit=limit)
        if unified_stores:
            return unified_stores

    cached_stores = _cache_lookup(lat=lat, lon=lon, radius_m=radius_m, limit=limit, source="overpass")
    if cached_stores is not None:
        return cached_stores

    if mode in {"auto", "live"}:
        try:
            live_rows = _live_overpass_nearby_stores(lat=lat, lon=lon, radius_m=radius_m, limit=limit)
            live_stores = _finalize_store_results([row[0] for row in live_rows], limit)
            if live_stores:
                _cache_store(lat=lat, lon=lon, radius_m=radius_m, limit=limit, stores=live_stores, source="overpass")
                _persist_live_stores(live_rows, source="overpass")
                refresh_unified_store_index(main_con=con, force=True)
                return live_stores
            if mode == "live":
                return []
        except RuntimeError:
            if mode == "live":
                return []

    if mode == "auto":
        unified_stores = _unified_nearby_stores_with_retry(lat=lat, lon=lon, radius_m=radius_m, limit=limit)
        if unified_stores:
            return unified_stores

    return _local_nearby_stores(con=con, lat=lat, lon=lon, radius_m=radius_m, limit=limit)
