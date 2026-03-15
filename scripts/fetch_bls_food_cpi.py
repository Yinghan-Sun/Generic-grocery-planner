#!/usr/bin/env -S uv run python
"""Fetch and stage local BLS CPI Food-at-Home data for offline USDA inflation adjustment."""

from __future__ import annotations

import csv
import json
import argparse
from datetime import date
from pathlib import Path
from urllib import request

API_URL = "https://api.bls.gov/publicAPI/v2/timeseries/data/"
SERIES_ID = "CUUR0000SAF11"
SERIES_TITLE = "Consumer Price Index for All Urban Consumers (CPI-U): Food at home in U.S. city average, all urban consumers, not seasonally adjusted"
ROOT = Path(__file__).resolve().parent.parent
OUTPUT_CSV = ROOT / "data" / "bls" / "cpi_food_at_home.csv"
RAW_JSON = ROOT / "data" / "bls" / "cpi_food_at_home_raw.json"
HEADERS = [
    "series_id",
    "series_title",
    "observed_year",
    "observed_month",
    "period",
    "period_name",
    "observed_at",
    "cpi_value",
    "footnotes_json",
]


def fetch_window(start_year: int, end_year: int) -> dict[str, object]:
    payload = json.dumps(
        {
            "seriesid": [SERIES_ID],
            "startyear": str(start_year),
            "endyear": str(end_year),
            "catalog": True,
        }
    ).encode("utf-8")
    req = request.Request(
        API_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def month_from_period(period: str) -> int | None:
    if not period.startswith("M") or period == "M13":
        return None
    try:
        month = int(period[1:])
    except ValueError:
        return None
    return month if 1 <= month <= 12 else None


def normalize_rows(payloads: list[dict[str, object]]) -> list[dict[str, object]]:
    dedup: dict[tuple[int, int], dict[str, object]] = {}
    series_title = SERIES_TITLE
    for payload in payloads:
        if payload.get("status") != "REQUEST_SUCCEEDED":
            raise RuntimeError(f"BLS CPI request failed: {payload}")
        series_list = (payload.get("Results") or {}).get("series") or []
        if not series_list:
            continue
        series = series_list[0]
        catalog = series.get("catalog") or {}
        series_title = str(catalog.get("series_title") or series_title)
        for row in series.get("data") or []:
            period = str(row.get("period") or "")
            month = month_from_period(period)
            if month is None:
                continue
            value = str(row.get("value") or "").strip()
            if not value or value == "-":
                continue
            year = int(row["year"])
            dedup[(year, month)] = {
                "series_id": SERIES_ID,
                "series_title": series_title,
                "observed_year": year,
                "observed_month": month,
                "period": period,
                "period_name": str(row.get("periodName") or ""),
                "observed_at": f"{year:04d}-{month:02d}",
                "cpi_value": float(value),
                "footnotes_json": json.dumps(row.get("footnotes") or [], ensure_ascii=True, sort_keys=True),
            }
    return [dedup[key] for key in sorted(dedup)]


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=HEADERS)
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from-json", type=Path, help="Normalize a previously downloaded BLS API JSON payload instead of fetching live.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.from_json:
        payloads = json.loads(args.from_json.read_text(encoding="utf-8"))
        if isinstance(payloads, dict):
            payloads = [payloads]
    else:
        current_year = date.today().year
        start_year = 2012
        payloads = []
        for window_start in range(start_year, current_year + 1, 10):
            window_end = min(window_start + 9, current_year)
            payloads.append(fetch_window(window_start, window_end))

    rows = normalize_rows(payloads)
    RAW_JSON.write_text(json.dumps(payloads, ensure_ascii=True, indent=2), encoding="utf-8")
    write_csv(OUTPUT_CSV, rows)

    latest = rows[-1] if rows else None
    print(f"series_id={SERIES_ID}")
    print(f"rows={len(rows)}")
    if latest:
        print(f"latest_observed_at={latest['observed_at']}")
        print(f"latest_cpi_value={latest['cpi_value']}")
    print(f"output_csv={OUTPUT_CSV}")
    print(f"raw_json={RAW_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
