"""Shared local evaluation helpers for the frozen hybrid planner pipeline."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path

import duckdb

from dietdashboard import candidate_debug
from dietdashboard import model_candidate_training
from dietdashboard import plan_scorer
from dietdashboard import hybrid_pipeline_final
from dietdashboard.generic_recommender import recommend_generic_foods, resolve_price_context
from dietdashboard.hybrid_planner import _best_heuristic_candidate_by_generation, _build_candidate_pool
from dietdashboard.store_discovery import DEFAULT_LIMIT as DEFAULT_STORE_LIMIT
from dietdashboard.store_discovery import DEFAULT_RADIUS_M, nearby_stores


def default_db_path() -> Path:
    return model_candidate_training.default_db_path()


def load_store_context(
    con: duckdb.DuckDBPyConnection,
    *,
    lat: float,
    lon: float,
    radius_m: float = DEFAULT_RADIUS_M,
    store_limit: int = DEFAULT_STORE_LIMIT,
) -> tuple[list[dict[str, object]], dict[str, str]]:
    stores = nearby_stores(con, lat=lat, lon=lon, radius_m=radius_m, limit=store_limit)
    return stores, resolve_price_context(lat, lon, stores)


def merged_scorer_config(
    *,
    scorer_model_path: Path | None = None,
    candidate_count: int | None = None,
    debug: bool = True,
) -> dict[str, object]:
    return hybrid_pipeline_final.final_scorer_config(
        debug=debug,
        candidate_count=int(candidate_count or hybrid_pipeline_final.final_runtime_metadata()["candidate_count"]),
        scorer_model_path=scorer_model_path,
    )


def merged_candidate_generation_config(
    config: Mapping[str, object] | None = None,
    *,
    debug: bool = True,
) -> dict[str, object]:
    merged = hybrid_pipeline_final.final_candidate_generation_config(debug=debug)
    merged.update(dict(config or {}))
    merged["debug"] = bool(debug)
    return merged


def selected_source(payload: Mapping[str, object]) -> str:
    selected = str(payload.get("selected_candidate_source") or "").strip()
    if selected:
        return selected
    metadata = payload.get("candidate_metadata")
    if isinstance(metadata, Mapping):
        return str(metadata.get("source") or "heuristic")
    return "heuristic"


def selected_scorer_score(payload: Mapping[str, object]) -> float:
    try:
        if payload.get("offline_comparable_scorer_score") is not None:
            return round(float(payload.get("offline_comparable_scorer_score") or 0.0), 6)
    except (TypeError, ValueError):
        pass
    scoring_debug = payload.get("scoring_debug")
    if isinstance(scoring_debug, Mapping):
        candidates = scoring_debug.get("candidates")
        if isinstance(candidates, Sequence):
            for row in candidates:
                if isinstance(row, Mapping) and bool(row.get("selected")):
                    try:
                        return round(float(row.get("model_score") or 0.0), 6)
                    except (TypeError, ValueError):
                        return 0.0
    return 0.0


def protein_gap(payload: Mapping[str, object]) -> float:
    return round(float(candidate_debug.protein_gap_g(payload)), 6)


def calorie_gap(payload: Mapping[str, object]) -> float:
    return round(float(candidate_debug.calorie_gap_kcal(payload)), 6)


def estimated_basket_cost(payload: Mapping[str, object]) -> float:
    return round(float(candidate_debug.estimated_cost(payload)), 6)


def hybrid_planner_metadata(
    *,
    scorer_model_path: Path,
    candidate_generation_config: Mapping[str, object],
) -> dict[str, object]:
    return {
        **hybrid_pipeline_final.final_runtime_metadata(),
        "scorer_model_path": str(scorer_model_path),
        "algorithm_version": str(candidate_generation_config.get("algorithm_version") or hybrid_pipeline_final.FINAL_ALGORITHM_VERSION),
        "structured_complementarity_enabled": bool(candidate_generation_config.get("structured_complementarity_enabled", True)),
        "structured_materialization_enabled": bool(candidate_generation_config.get("structured_materialization_enabled", True)),
        "candidate_generator_model_path": str(
            candidate_generation_config.get("candidate_generator_model_path") or hybrid_pipeline_final.FINAL_CANDIDATE_GENERATOR_MODEL_PATH
        ),
        "candidate_generator_backend": str(candidate_generation_config.get("candidate_generator_backend") or "auto"),
        "model_candidates_enabled": bool(candidate_generation_config.get("enable_model_candidates", True)),
        "model_candidate_count": int(
            candidate_generation_config.get("model_candidate_count")
            or hybrid_pipeline_final.final_runtime_metadata()["model_candidate_count"]
        ),
    }


def run_scored_system(
    con: duckdb.DuckDBPyConnection,
    *,
    preset: Mapping[str, object],
    stores: Sequence[dict[str, object]],
    price_context: Mapping[str, str],
    scorer_model_path: Path | None = None,
    candidate_generation_config: Mapping[str, object] | None = None,
    candidate_count: int | None = None,
) -> dict[str, object]:
    merged_scorer = merged_scorer_config(
        scorer_model_path=scorer_model_path,
        candidate_count=candidate_count,
        debug=True,
    )
    merged_generation = merged_candidate_generation_config(candidate_generation_config, debug=True)
    response = recommend_generic_foods(
        con,
        protein_target_g=float(dict(preset["targets"])["protein"]),
        calorie_target_kcal=float(dict(preset["targets"])["energy_fibre_kcal"]),
        preferences=dict(preset["preferences"]),
        nutrition_targets={key: value for key, value in dict(preset["targets"]).items() if key not in {"protein", "energy_fibre_kcal"}},
        pantry_items=list(preset.get("pantry_items") or []),
        days=int(preset["days"]),
        shopping_mode=str(preset["shopping_mode"]),
        price_context=dict(price_context),
        stores=list(stores),
        scorer_config=merged_scorer,
        candidate_generation_config=merged_generation,
    )
    algorithm_metadata = hybrid_planner_metadata(
        scorer_model_path=Path(str(merged_scorer["scorer_model_path"])),
        candidate_generation_config=merged_generation,
    )
    runtime_algorithm = dict(response.get("hybrid_planner_algorithm") or {})
    response["hybrid_planner_algorithm"] = {
        **algorithm_metadata,
        **runtime_algorithm,
        "algorithm_version": str(algorithm_metadata["algorithm_version"]),
    }
    response["hybrid_planner_algorithm_version"] = str(response["hybrid_planner_algorithm"]["algorithm_version"])
    return response


def _candidate_score(
    scorer_bundle: Mapping[str, object],
    candidate: Mapping[str, object],
) -> float:
    feature_row = plan_scorer.build_request_feature_rows([candidate])[0]
    score = plan_scorer.score_feature_rows(scorer_bundle, [feature_row])[0]
    return round(float(score), 6)


def run_legacy_heuristic(
    con: duckdb.DuckDBPyConnection,
    *,
    preset: Mapping[str, object],
    stores: Sequence[dict[str, object]],
    price_context: Mapping[str, str],
    scorer_model_path: Path | None = None,
    candidate_count: int | None = None,
) -> dict[str, object]:
    scorer_path = Path(str(scorer_model_path or hybrid_pipeline_final.FINAL_SCORER_MODEL_PATH))
    merged_generation = merged_candidate_generation_config(
        {
            "enable_model_candidates": False,
            "algorithm_version": f"{hybrid_pipeline_final.FINAL_ALGORITHM_VERSION}__legacy_heuristic",
        },
        debug=True,
    )
    _raw_candidates, candidates, pool_debug = _build_candidate_pool(
        con,
        protein_target_g=float(dict(preset["targets"])["protein"]),
        calorie_target_kcal=float(dict(preset["targets"])["energy_fibre_kcal"]),
        preferences=dict(preset["preferences"]),
        nutrition_targets={key: value for key, value in dict(preset["targets"]).items() if key not in {"protein", "energy_fibre_kcal"}},
        pantry_items=list(preset.get("pantry_items") or []),
        days=int(preset["days"]),
        shopping_mode=str(preset["shopping_mode"]),
        price_context=dict(price_context),
        stores=list(stores),
        candidate_count=int(candidate_count or hybrid_pipeline_final.final_runtime_metadata()["candidate_count"]),
        candidate_generation_config=merged_generation,
    )
    selected_candidate = _best_heuristic_candidate_by_generation(candidates) or candidates[0]
    scorer_bundle = plan_scorer.load_bundle(scorer_path)
    response = dict(selected_candidate["recommendation"])
    response["scorer_used"] = False
    response["scorer_backend"] = str(scorer_bundle.get("backend") or "unknown")
    response["candidate_count_considered"] = len(candidates)
    response["selected_candidate_id"] = str(selected_candidate["candidate_id"])
    response["selected_candidate_source"] = selected_source(selected_candidate)
    response["selected_candidate_sources"] = list(
        selected_candidate["candidate_metadata"].get("source_labels") or [response["selected_candidate_source"]]
    )
    response["offline_comparable_scorer_score"] = _candidate_score(scorer_bundle, selected_candidate)
    response["heuristic_selection_score"] = round(
        float(selected_candidate["candidate_metadata"].get("heuristic_selection_score") or 0.0),
        6,
    )
    response["candidate_generation_debug"] = {
        **pool_debug,
        "selection_mode": "legacy_heuristic_best_by_generation",
    }
    response["hybrid_planner_algorithm"] = hybrid_planner_metadata(
        scorer_model_path=scorer_path,
        candidate_generation_config=merged_generation,
    )
    response["hybrid_planner_algorithm"]["selection_mode"] = "legacy_heuristic_best_by_generation"
    response["hybrid_planner_algorithm_version"] = str(response["hybrid_planner_algorithm"]["algorithm_version"])
    return response
