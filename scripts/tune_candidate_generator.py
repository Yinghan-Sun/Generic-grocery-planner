#!/usr/bin/env -S uv run --extra ml python
"""Run local hyperparameter tuning for the learned candidate generator."""

from __future__ import annotations

import argparse
from pathlib import Path

from dietdashboard import model_candidate_generator
from dietdashboard import model_candidate_training
from dietdashboard import model_candidate_tuning


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset",
        type=Path,
        default=model_candidate_training.default_dataset_path(),
        help="Path to the candidate-generator dataset CSV.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=model_candidate_generator.default_model_dir(),
        help="Directory for tuning reports and selected configuration files.",
    )
    parser.add_argument(
        "--random-seed",
        type=int,
        default=model_candidate_generator.DEFAULT_RANDOM_SEED,
        help="Random seed used for model fitting during tuning.",
    )
    parser.add_argument(
        "--max-trials-per-backend",
        type=int,
        default=None,
        help="Optional cap on trials per backend for faster smoke runs.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = model_candidate_tuning.run_tuning(
        dataset_path=args.dataset,
        output_dir=args.output_dir,
        random_seed=args.random_seed,
        max_trials_per_backend=args.max_trials_per_backend,
    )
    print(f"results_path={summary['results_path']}")
    print(f"summary_path={summary['summary_path']}")
    print(f"best_config_path={summary['best_config_path']}")
    print(f"comparison_path={summary['comparison_path']}")
    print(f"selected_backend={summary['selected_backend']}")
    print(f"selected_hyperparameters={summary['selected_hyperparameters']}")
    print(f"backend_best_config_paths={summary['backend_best_config_paths']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
