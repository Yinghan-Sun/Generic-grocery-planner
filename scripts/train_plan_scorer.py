#!/usr/bin/env -S uv run --extra ml python
"""Build a local candidate-plan dataset, train a scorer, and save artifacts."""

from __future__ import annotations

import argparse
from pathlib import Path

from dietdashboard import model_candidate_generator
from dietdashboard import plan_scorer
from dietdashboard import plan_scorer_training


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--db-path",
        type=Path,
        default=plan_scorer_training.default_db_path(),
        help="Path to the local DuckDB database.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=plan_scorer.default_model_dir(),
        help="Directory for the dataset, model artifact, and metrics.",
    )
    parser.add_argument(
        "--candidate-count",
        type=int,
        default=8,
        help="Number of heuristic candidate plans to generate per training request.",
    )
    parser.add_argument(
        "--model-candidate-count",
        type=int,
        default=4,
        help="Maximum number of learned candidates to add to each scorer-training request.",
    )
    parser.add_argument(
        "--disable-model-candidates",
        action="store_true",
        help="Build the scorer dataset from heuristic-only candidate pools.",
    )
    parser.add_argument(
        "--candidate-generator-model-path",
        type=Path,
        default=model_candidate_generator.default_model_path(),
        help="Path to the candidate-generator artifact used when building scorer-training pools.",
    )
    parser.add_argument(
        "--backend",
        default="auto",
        help="Model backend to train: auto, xgboost, lightgbm, sklearn_gradient_boosting, sklearn_random_forest, or sklearn_ridge.",
    )
    parser.add_argument("--learning-rate", type=float, default=0.05, help="Learning rate used by supported tree/linear models.")
    parser.add_argument("--max-depth", type=int, default=3, help="Max tree depth for supported backends.")
    parser.add_argument("--n-estimators", type=int, default=250, help="Number of estimators for supported ensemble backends.")
    parser.add_argument("--validation-split", type=float, default=0.25, help="Validation split ratio, grouped by request.")
    parser.add_argument("--random-seed", type=int, default=plan_scorer.DEFAULT_RANDOM_SEED, help="Random seed for splitting/training.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = plan_scorer_training.train_and_save_model(
        db_path=args.db_path,
        output_dir=args.output_dir,
        candidate_count=args.candidate_count,
        model_candidate_count=args.model_candidate_count,
        enable_model_candidates=not args.disable_model_candidates,
        candidate_generator_model_path=args.candidate_generator_model_path,
        backend=args.backend,
        learning_rate=args.learning_rate,
        max_depth=args.max_depth,
        n_estimators=args.n_estimators,
        validation_split=args.validation_split,
        random_seed=args.random_seed,
    )
    metrics = summary["metrics"]

    print(f"dataset_path={summary['dataset_path']}")
    print(f"schema_path={summary['schema_path']}")
    print(f"model_path={summary['model_path']}")
    print(f"metrics_path={summary['metrics_path']}")
    print(f"feature_summary_path={summary['feature_summary_path']}")
    print(f"row_count={summary['row_count']}")
    print(f"request_count={summary['request_count']}")

    print("\n=== Plan Scorer Configuration ===")
    print(f"Backend: {metrics['backend']}")
    print(f"Model Candidates Enabled: {not args.disable_model_candidates}")
    print(f"Candidate Generator Model Path: {args.candidate_generator_model_path}")
    print(f"Learning Rate: {args.learning_rate}")
    print(f"Max Depth: {args.max_depth}")
    print(f"Number of Estimators: {args.n_estimators}")
    print(f"Validation Split: {args.validation_split}")
    print(f"Random Seed: {args.random_seed}")

    print("\n=== Plan Scorer Results ===")
    print(f"MAE: {metrics['validation_mae']:.6f}")
    print(f"RMSE: {metrics['validation_rmse']:.6f}")
    print(f"R2: {metrics['validation_r2']:.6f}")
    print(f"Top-1 Accuracy: {metrics['validation_top1_accuracy']:.6f}")
    print(f"Pairwise Accuracy: {metrics['validation_pairwise_accuracy']:.6f}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())