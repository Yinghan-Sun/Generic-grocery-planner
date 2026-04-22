"""Frozen configuration for the final generalized hybrid planner pipeline."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

FINAL_ALGORITHM_VERSION = "hybrid_planner_generalized_v5_main"
FINAL_ALGORITHM_LABEL = "Generalized Hybrid Planner Main"
FINAL_ALGORITHM_DESCRIPTION = (
    "Generalized hybrid planner pipeline with structured complementarity, "
    "shared learned-seed materialization, and the fair scorer artifact."
)

FINAL_SCORER_MODEL_PATH = REPO_ROOT / "artifacts" / "plan_scorer" / "hybrid_planner_fair_v1" / "plan_candidate_scorer.joblib"
FINAL_CANDIDATE_GENERATOR_MODEL_PATH = REPO_ROOT / "artifacts" / "candidate_generator" / "candidate_generator_best.joblib"
FINAL_CANDIDATE_GENERATOR_BACKEND = "random_forest"
FINAL_OUTPUT_DIR = REPO_ROOT / "artifacts" / "plan_scorer" / "hybrid_planner_generalized_v5"

DEFAULT_LOCATION = {"label": "Mountain View, CA", "lat": 37.401, "lon": -122.09}
ALTERNATE_LOCATION = {"label": "Sacramento, CA", "lat": 38.5816, "lon": -121.4944}

MAIN_PRESETS = [
    {
        "preset_id": "muscle_gain",
        "label": "Muscle Gain",
        "targets": {"protein": 170.0, "energy_fibre_kcal": 2800.0, "carbohydrate": 330.0, "fat": 85.0, "fiber": 35.0},
        "preferences": {"vegetarian": False, "dairy_free": False, "vegan": False, "budget_friendly": False, "meal_style": "any"},
        "days": 1,
        "shopping_mode": "balanced",
    },
    {
        "preset_id": "fat_loss",
        "label": "Fat Loss",
        "targets": {"protein": 150.0, "energy_fibre_kcal": 1800.0, "carbohydrate": 160.0, "fat": 55.0, "fiber": 30.0},
        "preferences": {"vegetarian": False, "dairy_free": False, "vegan": False, "budget_friendly": False, "meal_style": "any"},
        "days": 1,
        "shopping_mode": "balanced",
    },
    {
        "preset_id": "maintenance",
        "label": "Maintenance",
        "targets": {"protein": 130.0, "energy_fibre_kcal": 2200.0, "carbohydrate": 240.0, "fat": 70.0, "fiber": 30.0},
        "preferences": {"vegetarian": False, "dairy_free": False, "vegan": False, "budget_friendly": False, "meal_style": "any"},
        "days": 1,
        "shopping_mode": "balanced",
    },
    {
        "preset_id": "high_protein_vegetarian",
        "label": "High-Protein Vegetarian",
        "targets": {"protein": 140.0, "energy_fibre_kcal": 2100.0, "carbohydrate": 220.0, "fat": 70.0, "fiber": 32.0},
        "preferences": {"vegetarian": True, "dairy_free": False, "vegan": False, "budget_friendly": False, "meal_style": "any"},
        "days": 1,
        "shopping_mode": "balanced",
    },
    {
        "preset_id": "budget_friendly_healthy",
        "label": "Budget-Friendly Healthy",
        "targets": {"protein": 120.0, "energy_fibre_kcal": 2100.0, "carbohydrate": 230.0, "fat": 65.0, "fiber": 35.0},
        "preferences": {"vegetarian": False, "dairy_free": False, "vegan": False, "budget_friendly": True, "meal_style": "any"},
        "days": 1,
        "shopping_mode": "balanced",
    },
    {
        "preset_id": "vegan",
        "label": "Vegan",
        "targets": {"protein": 125.0, "energy_fibre_kcal": 2200.0, "carbohydrate": 245.0, "fat": 68.0, "fiber": 36.0},
        "preferences": {"vegetarian": True, "dairy_free": True, "vegan": True, "budget_friendly": False, "meal_style": "any"},
        "days": 1,
        "shopping_mode": "balanced",
    },
    {
        "preset_id": "dairy_free",
        "label": "Dairy-free",
        "targets": {"protein": 135.0, "energy_fibre_kcal": 2150.0, "carbohydrate": 225.0, "fat": 68.0, "fiber": 28.0},
        "preferences": {"vegetarian": False, "dairy_free": True, "vegan": False, "budget_friendly": False, "meal_style": "any"},
        "days": 1,
        "shopping_mode": "balanced",
    },
]


def final_runtime_metadata() -> dict[str, object]:
    return {
        "algorithm_version": FINAL_ALGORITHM_VERSION,
        "algorithm_label": FINAL_ALGORITHM_LABEL,
        "algorithm_description": FINAL_ALGORITHM_DESCRIPTION,
        "scorer_model_path": str(FINAL_SCORER_MODEL_PATH),
        "candidate_generator_model_path": str(FINAL_CANDIDATE_GENERATOR_MODEL_PATH),
        "candidate_generator_backend": FINAL_CANDIDATE_GENERATOR_BACKEND,
        "model_candidates_enabled": True,
        "structured_complementarity_enabled": True,
        "structured_materialization_enabled": True,
        "candidate_count": 6,
        "model_candidate_count": 4,
    }


def final_scorer_config(*, debug: bool = True, candidate_count: int = 6, scorer_model_path: Path | None = None) -> dict[str, object]:
    return {
        "candidate_count": int(candidate_count),
        "scorer_model_path": str(scorer_model_path or FINAL_SCORER_MODEL_PATH),
        "debug": bool(debug),
    }


def final_candidate_generation_config(
    *,
    debug: bool = True,
    enable_model_candidates: bool = True,
    model_candidate_count: int = 4,
    candidate_generator_model_path: Path | None = None,
    candidate_generator_backend: str = FINAL_CANDIDATE_GENERATOR_BACKEND,
    algorithm_version: str = FINAL_ALGORITHM_VERSION,
    structured_complementarity_enabled: bool = True,
    structured_materialization_enabled: bool = True,
) -> dict[str, object]:
    return {
        "enable_model_candidates": bool(enable_model_candidates),
        "model_candidate_count": int(model_candidate_count),
        "candidate_generator_model_path": str(candidate_generator_model_path or FINAL_CANDIDATE_GENERATOR_MODEL_PATH),
        "candidate_generator_backend": str(candidate_generator_backend),
        "algorithm_version": str(algorithm_version),
        "structured_complementarity_enabled": bool(structured_complementarity_enabled),
        "structured_materialization_enabled": bool(structured_materialization_enabled),
        "debug": bool(debug),
    }


def ablation_specs() -> list[dict[str, object]]:
    return [
        {
            "system_id": "heuristic_legacy",
            "label": "Heuristic Legacy Baseline",
            "mode": "legacy_heuristic",
        },
        {
            "system_id": "heuristic_scorer_only",
            "label": "Heuristic + Scorer Only",
            "mode": "heuristic_scorer",
            "candidate_generation_config": final_candidate_generation_config(
                enable_model_candidates=False,
                algorithm_version=f"{FINAL_ALGORITHM_VERSION}__heuristic_scorer_only",
            ),
        },
        {
            "system_id": "hybrid_planner_no_structured_complementarity",
            "label": "Hybrid Planner Without Structured Complementarity",
            "mode": "hybrid",
            "candidate_generation_config": final_candidate_generation_config(
                algorithm_version=f"{FINAL_ALGORITHM_VERSION}__no_complementarity",
                structured_complementarity_enabled=False,
                structured_materialization_enabled=True,
            ),
        },
        {
            "system_id": "hybrid_planner_no_structured_materialization",
            "label": "Hybrid Planner Without Structured Materialization",
            "mode": "hybrid",
            "candidate_generation_config": final_candidate_generation_config(
                algorithm_version=f"{FINAL_ALGORITHM_VERSION}__no_structured_materialization",
                structured_complementarity_enabled=True,
                structured_materialization_enabled=False,
            ),
        },
        {
            "system_id": "hybrid_planner_generalized_main",
            "label": FINAL_ALGORITHM_LABEL,
            "mode": "hybrid",
            "candidate_generation_config": final_candidate_generation_config(),
        },
    ]
