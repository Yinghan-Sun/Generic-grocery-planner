#!/usr/bin/env -S uv run python
"""Normalize offline USDA Food-at-Home Monthly Area Prices inputs into staged CSVs."""

from __future__ import annotations

import csv
import json
import re
import sys
import tempfile
import zipfile
from collections.abc import Iterable
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent.parent
USDA_DIR = ROOT / "data" / "usda"
RAW_STAGED_CSV = USDA_DIR / "usda_food_area_prices_raw_staged.csv"
NORMALIZED_STAGED_CSV = USDA_DIR / "usda_food_area_prices_normalized.csv"
IGNORED_NAMES = {"README.md", RAW_STAGED_CSV.name, NORMALIZED_STAGED_CSV.name, ".DS_Store"}

RAW_HEADERS = [
    "source_file",
    "source_sheet",
    "row_number",
    "year",
    "month",
    "area_code",
    "area_name",
    "food_code",
    "food_name",
    "purchase_dollars_wtd",
    "purchase_grams_wtd",
    "store_count",
    "unit_value_mean_wtd",
    "unit_value_mean_unwtd",
    "unit_value_se_wtd",
    "price_index_geks",
    "raw_record_json",
]

NORMALIZED_HEADERS = [
    "source_file",
    "source_sheet",
    "observed_year",
    "observed_month",
    "observed_month_label",
    "observed_at",
    "area_code",
    "area_name",
    "area_scope",
    "food_code",
    "food_name",
    "food_key",
    "purchase_dollars_wtd",
    "purchase_grams_wtd",
    "store_count",
    "unit_value_mean_wtd",
    "unit_value_mean_unwtd",
    "unit_value_se_wtd",
    "price_index_geks",
    "normalized_price_per_100g",
]

MONTH_LOOKUP = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}

FIELD_ALIASES = {
    "year": ["year", "obs_year", "calendar_year"],
    "month": ["month", "obs_month", "month_num", "month_number", "period_month", "month_name", "period"],
    "area_code": ["area_code", "market_area_code", "metroregion_code", "region_code", "geo_code"],
    "area_name": ["area_name", "market_area", "metroregion_name", "area", "geographic_area", "market_name", "region_name"],
    "food_code": ["food_code", "efpg_code", "group_code", "category_code", "food_group_code"],
    "food_name": ["food_name", "efpg_name", "food_group", "food_group_name", "category", "category_name"],
    "purchase_dollars_wtd": ["purchase_dollars_wtd", "weighted_purchase_dollars", "purchase_dollars"],
    "purchase_grams_wtd": ["purchase_grams_wtd", "weighted_purchase_grams", "purchase_grams", "purchase_quantity_grams"],
    "store_count": ["store_count", "number_stores", "stores", "sample_size"],
    "unit_value_mean_wtd": ["unit_value_mean_wtd", "weighted_mean_unit_value", "mean_unit_value", "unit_value", "mean_unit_value_per_100g"],
    "unit_value_mean_unwtd": ["unit_value_mean_unwtd", "unweighted_mean_unit_value"],
    "unit_value_se_wtd": ["unit_value_se_wtd", "weighted_unit_value_standard_error", "unit_value_se", "se_unit_value"],
    "price_index_geks": ["price_index_geks", "geks_index", "price_index"],
    "observed_at": ["observed_at", "date", "observation_date", "month_date"],
}

USDA_AREA_ALIASES = {
    "u_s_average": ("US", "U.S. average", "national"),
    "us_average": ("US", "U.S. average", "national"),
    "u_s": ("US", "U.S. average", "national"),
    "national": ("US", "U.S. average", "national"),
    "census_region_1_northeast": ("NORTHEAST", "Northeast", "region"),
    "northeast": ("NORTHEAST", "Northeast", "region"),
    "census_region_2_midwest": ("MIDWEST", "Midwest", "region"),
    "midwest": ("MIDWEST", "Midwest", "region"),
    "census_region_3_south": ("SOUTH", "South", "region"),
    "south": ("SOUTH", "South", "region"),
    "census_region_4_west": ("WEST", "West", "region"),
    "west": ("WEST", "West", "region"),
    "atlanta": ("ATLANTA", "Atlanta", "metro"),
    "boston": ("BOSTON", "Boston", "metro"),
    "chicago": ("CHICAGO", "Chicago", "metro"),
    "dallas": ("DALLAS", "Dallas", "metro"),
    "detroit": ("DETROIT", "Detroit", "metro"),
    "houston": ("HOUSTON", "Houston", "metro"),
    "los_angeles": ("LOS_ANGELES", "Los Angeles", "metro"),
    "miami": ("MIAMI", "Miami", "metro"),
    "new_york": ("NEW_YORK", "New York", "metro"),
    "philadelphia": ("PHILADELPHIA", "Philadelphia", "metro"),
}

LONG_ATTRIBUTE_FIELDS = {
    "purchase_dollars_wtd": "purchase_dollars_wtd",
    "purchase_grams_wtd": "purchase_grams_wtd",
    "purchase_dollars_unwtd": "purchase_dollars_unwtd",
    "purchase_grams_unwtd": "purchase_grams_unwtd",
    "number_stores": "number_stores",
    "unit_value_mean_wtd": "unit_value_mean_wtd",
    "unit_value_se_wtd": "unit_value_se_wtd",
    "unit_value_mean_unwtd": "unit_value_mean_unwtd",
    "price_index_geks": "price_index_geks",
}

FOOD_KEY_ALIASES = {
    "whole_grain_breakfast_cereal": "whole_grain_breakfast_cereal",
    "all_other_breakfast_cereal": "all_other_breakfast_cereal",
    "egg_and_egg_substitutes": "egg_and_egg_substitutes",
}


def normalize_text(value: object) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return re.sub(r"_+", "_", text).strip("_")


def to_float(value: object) -> float | None:
    text = str(value or "").strip()
    if not text or text in {".", "-", "NA", "N/A"}:
        return None
    text = text.replace(",", "")
    try:
        return float(text)
    except ValueError:
        return None


def to_int(value: object) -> int | None:
    number = to_float(value)
    return int(number) if number is not None else None


def pick_field(row: dict[str, object], logical_name: str) -> object | None:
    for alias in FIELD_ALIASES.get(logical_name, []):
        if alias in row and str(row[alias]).strip() != "":
            return row[alias]
    return None


def parse_month(value: object) -> tuple[int | None, str | None]:
    text = str(value or "").strip()
    if not text:
        return None, None
    if text.isdigit():
        month = int(text)
        if 1 <= month <= 12:
            return month, text.zfill(2)
    normalized = normalize_text(text)
    if normalized in MONTH_LOOKUP:
        month = MONTH_LOOKUP[normalized]
        return month, text
    match = re.search(r"(\d{4})[-/](\d{1,2})", text)
    if match:
        month = int(match.group(2))
        if 1 <= month <= 12:
            return month, f"{match.group(1)}-{match.group(2).zfill(2)}"
    return None, text


def parse_observed_at(value: object) -> tuple[int | None, int | None, str | None]:
    text = str(value or "").strip()
    if not text:
        return None, None, None
    match = re.search(r"(\d{4})[-/](\d{1,2})", text)
    if match:
        year = int(match.group(1))
        month = int(match.group(2))
        if 1 <= month <= 12:
            return year, month, f"{year:04d}-{month:02d}"
    return None, None, None


def infer_area(area_code: object, area_name: object) -> tuple[str, str, str]:
    raw_name = str(area_name or area_code or "").strip()
    key = normalize_text(raw_name)
    if key in USDA_AREA_ALIASES:
        return USDA_AREA_ALIASES[key]
    for alias_key, triple in sorted(USDA_AREA_ALIASES.items(), key=lambda item: len(item[0]), reverse=True):
        if alias_key and alias_key in key:
            return triple
    return (str(area_code or key or "UNKNOWN").strip() or "UNKNOWN", raw_name or "Unknown area", "unknown")


def infer_food_key(food_code: object, food_name: object) -> str:
    raw_name = str(food_name or food_code or "").strip()
    key = normalize_text(raw_name)
    return FOOD_KEY_ALIASES.get(key, key)


def canonicalize_headers(row: dict[str, object]) -> dict[str, object]:
    return {normalize_text(key): value for key, value in row.items() if str(key).strip()}


def load_fmap_readme_maps(readme_path: Path) -> tuple[dict[str, str], dict[str, str]]:
    food_names: dict[str, str] = {}
    area_names: dict[str, str] = {}
    if not readme_path.exists():
        return food_names, area_names

    mode: str | None = None
    for raw_line in readme_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip("\ufeff")
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("EFPG_code") and "EFPG_name" in stripped:
            mode = "food"
            continue
        if stripped.startswith("Metroregion_code") and "Metroregion_name" in stripped:
            mode = "area"
            continue

        parts = [part.strip() for part in raw_line.split("\t") if part.strip()]
        if len(parts) < 2 or not parts[0].isdigit():
            continue
        if mode == "food":
            food_names[parts[0]] = parts[1]
        elif mode == "area":
            area_names[parts[0]] = parts[1]
    return food_names, area_names


def pivot_fmap_long_rows(path: Path, reader: csv.DictReader) -> list[dict[str, object]]:
    readme_path = path.parent / "FMAP-ReadMe.txt"
    food_names, area_names = load_fmap_readme_maps(readme_path)
    grouped: dict[tuple[str, str, str, str], dict[str, object]] = {}

    for row in reader:
        record = canonicalize_headers(row)
        year = str(record.get("year") or "").strip()
        month = str(record.get("month") or "").strip()
        food_code = str(record.get("efpg_code") or "").strip()
        area_code = str(record.get("metroregion_code") or "").strip()
        attribute = normalize_text(record.get("attribute"))
        value = record.get("value")
        if not (year and month and food_code and area_code and attribute):
            continue

        field_name = LONG_ATTRIBUTE_FIELDS.get(attribute)
        if field_name is None:
            continue

        key = (year, month, food_code, area_code)
        row_out = grouped.setdefault(
            key,
            {
                "year": year,
                "month": month,
                "area_code": area_code,
                "area_name": area_names.get(area_code, area_code),
                "food_code": food_code,
                "food_name": food_names.get(food_code, food_code),
            },
        )
        row_out[field_name] = value

    return list(grouped.values())


def iter_csv_rows(path: Path) -> Iterable[tuple[str, list[dict[str, object]]]]:
    delimiter = "\t" if path.suffix.lower() == ".tsv" else ","
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, delimiter=delimiter)
        fieldnames = [normalize_text(name) for name in (reader.fieldnames or [])]
        if {"year", "month", "efpg_code", "metroregion_code", "attribute", "value"}.issubset(fieldnames):
            rows = pivot_fmap_long_rows(path, reader)
        else:
            rows = [canonicalize_headers(row) for row in reader]
    yield "csv", rows


def load_shared_strings(zf: zipfile.ZipFile) -> list[str]:
    try:
        xml_data = zf.read("xl/sharedStrings.xml")
    except KeyError:
        return []
    root = ET.fromstring(xml_data)
    namespace = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    strings: list[str] = []
    for si in root.findall("a:si", namespace):
        parts = [node.text or "" for node in si.findall(".//a:t", namespace)]
        strings.append("".join(parts))
    return strings


def load_workbook_sheets(zf: zipfile.ZipFile) -> list[tuple[str, str]]:
    wb = ET.fromstring(zf.read("xl/workbook.xml"))
    rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
    ns_main = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    ns_rel = {"r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}
    rel_map = {
        rel.attrib.get("Id"): rel.attrib.get("Target")
        for rel in rels
        if rel.attrib.get("Id") and rel.attrib.get("Target")
    }
    sheets: list[tuple[str, str]] = []
    for sheet in wb.findall("a:sheets/a:sheet", ns_main):
        name = sheet.attrib.get("name", "Sheet")
        rel_id = sheet.attrib.get(f"{{{ns_rel['r']}}}id")
        target = rel_map.get(rel_id)
        if target:
            sheets.append((name, f"xl/{target.lstrip('/')}"))
    return sheets


def column_index(cell_ref: str) -> int:
    letters = re.sub(r"[^A-Z]", "", cell_ref.upper())
    index = 0
    for char in letters:
        index = index * 26 + (ord(char) - 64)
    return max(index - 1, 0)


def sheet_rows(zf: zipfile.ZipFile, shared_strings: list[str], sheet_path: str) -> list[dict[str, object]]:
    namespace = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    root = ET.fromstring(zf.read(sheet_path))
    rows: list[list[str]] = []
    for row in root.findall(".//a:sheetData/a:row", namespace):
        values: list[str] = []
        for cell in row.findall("a:c", namespace):
            ref = cell.attrib.get("r", "A1")
            idx = column_index(ref)
            while len(values) <= idx:
                values.append("")
            cell_type = cell.attrib.get("t")
            value = ""
            if cell_type == "inlineStr":
                value = "".join(node.text or "" for node in cell.findall(".//a:t", namespace))
            else:
                v = cell.find("a:v", namespace)
                if v is not None and v.text is not None:
                    if cell_type == "s":
                        string_index = int(v.text)
                        value = shared_strings[string_index] if 0 <= string_index < len(shared_strings) else ""
                    else:
                        value = v.text
            values[idx] = value
        if any(str(value).strip() for value in values):
            rows.append(values)
    if not rows:
        return []
    header_idx = 0
    for i, row in enumerate(rows):
        normalized = [normalize_text(value) for value in row]
        if any(token in normalized for token in ("year", "month", "area", "area_name", "food_name", "food_group", "efpg_name")):
            header_idx = i
            break
    header = [normalize_text(value) or f"column_{idx+1}" for idx, value in enumerate(rows[header_idx])]
    out: list[dict[str, object]] = []
    for row in rows[header_idx + 1 :]:
        padded = row + [""] * max(0, len(header) - len(row))
        out.append({header[idx]: padded[idx] for idx in range(len(header))})
    return out


def iter_xlsx_rows(path: Path) -> Iterable[tuple[str, list[dict[str, object]]]]:
    with zipfile.ZipFile(path) as zf:
        shared_strings = load_shared_strings(zf)
        for sheet_name, sheet_path in load_workbook_sheets(zf):
            rows = sheet_rows(zf, shared_strings, sheet_path)
            if rows:
                yield sheet_name, rows


def iter_rows_from_path(path: Path) -> Iterable[tuple[str, list[dict[str, object]]]]:
    suffix = path.suffix.lower()
    if suffix in {".csv", ".tsv"}:
        yield from iter_csv_rows(path)
        return
    if suffix == ".xlsx":
        yield from iter_xlsx_rows(path)
        return
    if suffix == ".zip":
        with tempfile.TemporaryDirectory(prefix="usda-fmap-") as tmp_dir:
            with zipfile.ZipFile(path) as zf:
                zf.extractall(tmp_dir)
            for nested in sorted(Path(tmp_dir).rglob("*")):
                if nested.is_file() and nested.suffix.lower() in {".csv", ".tsv", ".xlsx"}:
                    yield from iter_rows_from_path(nested)
        return


def iter_input_files() -> list[Path]:
    candidates: list[Path] = []
    for path in sorted(USDA_DIR.rglob("*")):
        if not path.is_file():
            continue
        if path.name in IGNORED_NAMES:
            continue
        if path.suffix.lower() not in {".csv", ".tsv", ".xlsx", ".zip"}:
            continue
        candidates.append(path)
    return candidates


def raw_row_from_input(source_file: str, source_sheet: str, row_number: int, row: dict[str, object]) -> dict[str, object] | None:
    row = canonicalize_headers(row)
    year = pick_field(row, "year")
    month = pick_field(row, "month")
    observed_at = pick_field(row, "observed_at")
    if (year is None or str(year).strip() == "") and observed_at:
        parsed_year, parsed_month, _ = parse_observed_at(observed_at)
        year = parsed_year
        month = month or parsed_month
    area_name = pick_field(row, "area_name")
    food_name = pick_field(row, "food_name")
    unit_value = pick_field(row, "unit_value_mean_wtd")
    if not area_name or not food_name or unit_value is None:
        return None
    return {
        "source_file": source_file,
        "source_sheet": source_sheet,
        "row_number": row_number,
        "year": year,
        "month": month,
        "area_code": pick_field(row, "area_code") or "",
        "area_name": area_name,
        "food_code": pick_field(row, "food_code") or "",
        "food_name": food_name,
        "purchase_dollars_wtd": pick_field(row, "purchase_dollars_wtd") or "",
        "purchase_grams_wtd": pick_field(row, "purchase_grams_wtd") or "",
        "store_count": pick_field(row, "store_count") or "",
        "unit_value_mean_wtd": unit_value,
        "unit_value_mean_unwtd": pick_field(row, "unit_value_mean_unwtd") or "",
        "unit_value_se_wtd": pick_field(row, "unit_value_se_wtd") or "",
        "price_index_geks": pick_field(row, "price_index_geks") or "",
        "raw_record_json": json.dumps(row, ensure_ascii=True, sort_keys=True),
    }


def normalize_raw_row(raw_row: dict[str, object]) -> dict[str, object] | None:
    year = to_int(raw_row.get("year"))
    month, month_label = parse_month(raw_row.get("month"))
    if (year is None or month is None) and raw_row.get("raw_record_json"):
        observed_year, observed_month, observed_label = parse_observed_at(raw_row.get("month"))
        year = year or observed_year
        month = month or observed_month
        month_label = month_label or observed_label
    if year is None or month is None:
        return None

    area_code, area_name, area_scope = infer_area(raw_row.get("area_code"), raw_row.get("area_name"))
    food_name = str(raw_row.get("food_name") or "").strip()
    food_code = str(raw_row.get("food_code") or "").strip()
    normalized_price = to_float(raw_row.get("unit_value_mean_wtd"))
    if normalized_price is None:
        return None
    return {
        "source_file": raw_row["source_file"],
        "source_sheet": raw_row["source_sheet"],
        "observed_year": year,
        "observed_month": month,
        "observed_month_label": month_label or f"{month:02d}",
        "observed_at": f"{year:04d}-{month:02d}",
        "area_code": area_code,
        "area_name": area_name,
        "area_scope": area_scope,
        "food_code": food_code,
        "food_name": food_name,
        "food_key": infer_food_key(food_code, food_name),
        "purchase_dollars_wtd": to_float(raw_row.get("purchase_dollars_wtd")),
        "purchase_grams_wtd": to_float(raw_row.get("purchase_grams_wtd")),
        "store_count": to_int(raw_row.get("store_count")),
        "unit_value_mean_wtd": normalized_price,
        "unit_value_mean_unwtd": to_float(raw_row.get("unit_value_mean_unwtd")),
        "unit_value_se_wtd": to_float(raw_row.get("unit_value_se_wtd")),
        "price_index_geks": to_float(raw_row.get("price_index_geks")),
        "normalized_price_per_100g": normalized_price,
    }


def write_csv(path: Path, headers: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers)
        writer.writeheader()
        for row in rows:
            writer.writerow({header: row.get(header, "") for header in headers})


def main() -> int:
    raw_rows: list[dict[str, object]] = []
    normalized_rows: list[dict[str, object]] = []
    input_files = iter_input_files()

    for path in input_files:
        try:
            sheets = list(iter_rows_from_path(path))
        except (OSError, zipfile.BadZipFile, ET.ParseError) as exc:
            print(f"Skipping unreadable USDA file {path}: {exc}", file=sys.stderr)
            continue
        for sheet_name, rows in sheets:
            for index, row in enumerate(rows, start=1):
                raw_row = raw_row_from_input(path.name, sheet_name, index, row)
                if raw_row is None:
                    continue
                normalized_row = normalize_raw_row(raw_row)
                if normalized_row is None:
                    continue
                raw_rows.append(raw_row)
                normalized_rows.append(normalized_row)

    raw_rows.sort(key=lambda row: (str(row["source_file"]), str(row["source_sheet"]), int(row["row_number"])))
    normalized_rows.sort(
        key=lambda row: (
            str(row["area_code"]),
            str(row["food_key"]),
            int(row["observed_year"]),
            int(row["observed_month"]),
            str(row["source_file"]),
        )
    )

    write_csv(RAW_STAGED_CSV, RAW_HEADERS, raw_rows)
    write_csv(NORMALIZED_STAGED_CSV, NORMALIZED_HEADERS, normalized_rows)

    print(f"usda_input_files={len(input_files)}")
    print(f"usda_raw_rows={len(raw_rows)}")
    print(f"usda_normalized_rows={len(normalized_rows)}")
    print(f"raw_staged_csv={RAW_STAGED_CSV}")
    print(f"normalized_staged_csv={NORMALIZED_STAGED_CSV}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
