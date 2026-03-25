#!/usr/bin/env -S uv run --extra ml python
"""Train and save the learned candidate-generator artifact."""

from __future__ import annotations

import argparse
import json
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
        help="Directory for model artifacts and reports.",
    )
    parser.add_argument(
        "--model-output",
        type=Path,
        default=None,
        help="Optional explicit model artifact output path.",
    )
    parser.add_argument(
        "--config-path",
        type=Path,
        default=None,
        help="Path to a tuning-selected config JSON. Defaults to the repo best-config file when present.",
    )
    parser.add_argument(
        "--backend",
        default="auto",
        help="Backend to train when no config file is supplied.",
    )
    parser.add_argument(
        "--hyperparameters-json",
        default=None,
        help="Optional JSON string with backend-specific hyperparameters when training without a config file.",
    )
    parser.add_argument(
        "--random-seed",
        type=int,
        default=model_candidate_generator.DEFAULT_RANDOM_SEED,
        help="Random seed used for fitting when training without a config file.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config_path = args.config_path
    default_best_config = model_candidate_tuning.default_best_config_path()
    if config_path is None and default_best_config.exists():
        config_path = default_best_config

    hyperparameters = json.loads(args.hyperparameters_json) if args.hyperparameters_json else None
    summary = model_candidate_training.train_and_save_model(
        dataset_path=args.dataset,
        output_dir=args.output_dir,
        model_output_path=args.model_output,
        backend=args.backend,
        hyperparameters=hyperparameters,
        config_path=config_path,
        random_seed=args.random_seed,
    )
    print(f"dataset_path={summary['dataset_path']}")
    print(f"model_path={summary['model_path']}")
    print(f"metrics_path={summary['metrics_path']}")
    print(f"feature_summary_path={summary['feature_summary_path']}")
    print(f"metrics={summary['metrics']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
