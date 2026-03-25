#!/usr/bin/env -S uv run --extra ml python
"""Build the learned candidate-generator training dataset."""

from __future__ import annotations

import argparse
from pathlib import Path

from dietdashboard import model_candidate_training


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--db-path",
        type=Path,
        default=model_candidate_training.default_db_path(),
        help="Path to the local DuckDB database.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=model_candidate_training.default_dataset_path(),
        help="Output CSV path for the generated dataset.",
    )
    parser.add_argument(
        "--candidate-count",
        type=int,
        default=10,
        help="Number of deterministic heuristic candidates to generate per scenario before selecting labels.",
    )
    parser.add_argument(
        "--scenario-limit",
        type=int,
        default=None,
        help="Optional limit for smoke tests or faster local iteration.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    dataset_path, schema_path, scenarios_path, rows, scenarios = model_candidate_training.write_training_dataset(
        args.output,
        db_path=args.db_path,
        candidate_count=args.candidate_count,
        scenario_limit=args.scenario_limit,
    )
    summary = model_candidate_training.dataset_schema_summary(rows, scenarios)
    print(f"dataset_path={dataset_path}")
    print(f"schema_path={schema_path}")
    print(f"scenarios_path={scenarios_path}")
    print(f"row_count={summary['row_count']}")
    print(f"scenario_count={summary['scenario_count']}")
    print(f"split_row_counts={summary['split_row_counts']}")
    print(f"role_positive_rates={summary['role_positive_rates']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
