#!/usr/bin/env python
"""Build the generic-food role training dataset."""

from __future__ import annotations

import argparse
from pathlib import Path

from dietdashboard import food_role_model


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--db-path",
        type=Path,
        default=food_role_model.project_root() / "data" / "data.db",
        help="Path to the generic planner DuckDB database.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=food_role_model.default_dataset_path(),
        help="Output CSV path for the generated training dataset.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    dataset_path, schema_path = food_role_model.write_training_dataset(args.output, db_path=args.db_path)
    rows = food_role_model.build_training_rows(db_path=args.db_path)
    summary = food_role_model.dataset_schema_summary(rows)
    print(f"dataset_path={dataset_path}")
    print(f"schema_path={schema_path}")
    print(f"row_count={summary['row_count']}")
    print(f"label_counts={summary['label_counts']}")
    print(f"label_sources={summary['label_sources']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
