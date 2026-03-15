#!/usr/bin/env -S uv run --script
"""This script reformats the fetched nutrient_map_recipe_estimator."""

import csv
import re
from collections.abc import Generator
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).parent.parent.parent / "data"


def extract_ciqual_cols(header: list[str]) -> Generator[tuple[str, str, str]]:
    """Extract the columns from the ciqual database."""
    key_pattern = re.compile(r"(.+)\s+\(((\w*g)|kJ|kcal)\/100g\)")
    for col in header:
        pattern_match = key_pattern.match(col)
        if pattern_match is None:
            print(f"Skipping ciqual {col=}")
            continue
        name = pattern_match.group(1).split(" or ")[0]  # Take first or option
        unit = pattern_match.group(2).replace("kJ", "kj")
        yield col, name, unit


def create_reformatted_csv(file, ciqual_cols: Generator[tuple[str, str, str]], prev_nutrient_map: list[dict[str, Any]]):
    header = ("name", "ciqual_const_name_eng", "ciqual_unit", "off_id", "count", "nnr2023_id", "comments")
    writer = csv.writer(file)
    writer.writerow(header)  # Write header

    # First write all rows with a matching ciqual_const_name_eng, but sorted
    for ciqual_const_name_eng, name, ciqual_unit in ciqual_cols:
        matching_rows = [row_dict for row_dict in prev_nutrient_map if row_dict["ciqual_id"] == ciqual_const_name_eng]
        if matching_rows:
            for row_dict in matching_rows:
                assert row_dict["ciqual_id"] == ciqual_const_name_eng
                assert row_dict["ciqual_unit"] == ciqual_unit
                row_dict["name"] = name
                writer.writerow([row_dict.get(col) for col in header])
        else:
            row_dict = {"ciqual_const_name_eng": ciqual_const_name_eng, "ciqual_unit": ciqual_unit, "name": name}
            # Find possible off_id match and add it.
            for possible_match_row_dict in prev_nutrient_map:
                if name.lower() == possible_match_row_dict["off_id"]:
                    print("Adding matched", name, possible_match_row_dict["off_id"])
                    row_dict["off_id"] = possible_match_row_dict["off_id"]
                    row_dict["count"] = possible_match_row_dict["countprep"]
                    break
            writer.writerow([row_dict.get(col) for col in header])
    # Then write possible other rows (with comments).
    for row_dict in prev_nutrient_map:
        if row_dict["ciqual_id"] != "" or (row_dict["ciqual_unit"] == "" and row_dict["comments"] == ""):
            continue
        writer.writerow([row_dict.get(col) for col in header])


if __name__ == "__main__":
    with (DATA_DIR / "ciqual2020.csv").open("r") as file:
        ciqual_cols = extract_ciqual_cols(next(csv.reader(file, delimiter="\t")))

    with (DATA_DIR / "nutrient_map_recipe_estimator.csv").open("r") as file:
        prev_nutrient_map = list(csv.DictReader(file))

    with (DATA_DIR / "nutrient_map.csv").open("w") as file:
        create_reformatted_csv(file, ciqual_cols, prev_nutrient_map)
