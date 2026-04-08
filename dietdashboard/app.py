#!/usr/bin/env -S uv run
"""Flask app for the generic grocery planner demo."""

import math
import os
from pathlib import Path

import duckdb
from flask import Flask, g, render_template, request, url_for
from flask_compress import Compress

from dietdashboard.generic_recommender import recommend_generic_foods, resolve_price_context
from dietdashboard import hybrid_pipeline_final
from dietdashboard.model_candidate_generator import ModelCandidateArtifactError
from dietdashboard.plan_scorer import PlanScorerArtifactError
from dietdashboard.request_logging import setup_logging
from dietdashboard.store_discovery import DEFAULT_LIMIT as DEFAULT_STORE_LIMIT
from dietdashboard.store_discovery import (
    DEFAULT_RADIUS_M,
    MAX_LIMIT as MAX_STORE_LIMIT,
    MAX_RADIUS_M,
    nearby_stores,
    normalize_store_snapshot,
)
from dietdashboard.store_fit import recommend_store_fits

DEBUG_DIR = Path(__file__).parent.parent / "tmp"
DATA_DIR = Path(__file__).parent.parent / "data"
TEMPLATE_FOLDER = Path(__file__).parent / "frontend/html"
STATIC_FOLDER = Path(__file__).parent / "static"
IS_PROD = os.getenv("PROD", "0") == "1"
FINAL_RUNTIME_DEFAULTS = hybrid_pipeline_final.final_runtime_metadata()
DEFAULT_TRAINED_SCORER_CANDIDATE_COUNT = int(FINAL_RUNTIME_DEFAULTS["candidate_count"])
MAX_TRAINED_SCORER_CANDIDATE_COUNT = 12
DEFAULT_TRAINED_SCORER_MODEL_PATH = str(hybrid_pipeline_final.FINAL_SCORER_MODEL_PATH)
DEFAULT_MODEL_CANDIDATE_COUNT = int(FINAL_RUNTIME_DEFAULTS["model_candidate_count"])
MAX_MODEL_CANDIDATE_COUNT = 8
DEFAULT_CANDIDATE_GENERATOR_MODEL_PATH = str(hybrid_pipeline_final.FINAL_CANDIDATE_GENERATOR_MODEL_PATH)
DEFAULT_CANDIDATE_GENERATOR_BACKEND = str(FINAL_RUNTIME_DEFAULTS["candidate_generator_backend"])


def get_con() -> duckdb.DuckDBPyConnection:
    """Get a read-only connection to the main DuckDB database."""
    return duckdb.connect(DATA_DIR / "data.db", read_only=True)


def parse_float(value: object, field_name: str) -> float:
    """Parse a numeric field from a request payload."""
    try:
        out = float(value)
    except (TypeError, ValueError) as e:
        raise ValueError(f"Invalid {field_name}.") from e
    if not math.isfinite(out):
        raise ValueError(f"Invalid {field_name}.")
    return out


def parse_optional_float(value: object, field_name: str) -> float | None:
    if value is None or (isinstance(value, str) and value.strip() == ""):
        return None
    return parse_float(value, field_name)


def parse_bool(value: object, default: bool = False) -> bool:
    """Parse a boolean from a request payload."""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes"}:
            return True
        if normalized in {"false", "0", "no"}:
            return False
    if isinstance(value, (int, float)):
        return bool(value)
    raise ValueError("Invalid boolean value.")


def parse_choice(value: object, field_name: str, allowed: set[str], default: str) -> str:
    if value is None:
        return default
    out = str(value).strip().lower()
    if out in allowed:
        return out
    raise ValueError(f"Invalid {field_name}.")


def parse_int(value: object, field_name: str) -> int:
    """Parse an integer field from a request payload."""
    try:
        out = int(str(value))
    except (TypeError, ValueError) as e:
        raise ValueError(f"Invalid {field_name}.") from e
    return out


def sanitize_recommendation_response_for_prod(payload: dict[str, object]) -> dict[str, object]:
    """Strip debug-only planner details from production responses."""
    sanitized = dict(payload)
    for key in (
        "algorithmic_faithfulness_debug",
        "candidate_comparison_debug",
        "candidate_generation_debug",
        "scorer_backend",
        "scoring_debug",
    ):
        sanitized.pop(key, None)

    execution = sanitized.get("hybrid_planner_execution")
    if isinstance(execution, dict):
        sanitized_execution = dict(execution)
        for key in (
            "candidate_generator_backend",
            "candidate_generator_model_path",
            "scorer_backend",
            "scorer_model_path",
        ):
            sanitized_execution.pop(key, None)
        sanitized["hybrid_planner_execution"] = sanitized_execution

    algorithm = sanitized.get("hybrid_planner_algorithm")
    if isinstance(algorithm, dict):
        sanitized_algorithm = dict(algorithm)
        for key in (
            "candidate_generator_backend",
            "candidate_generator_model_path",
        ):
            sanitized_algorithm.pop(key, None)
        sanitized["hybrid_planner_algorithm"] = sanitized_algorithm

    return sanitized


def create_app() -> Flask:
    app = Flask(__name__, static_folder=STATIC_FOLDER, template_folder=TEMPLATE_FOLDER)
    app.config["COMPRESS_MIMETYPES"] = ["text/html", "text/css", "text/javascript", "text/csv", "text/plain"]
    Compress(app)
    setup_logging(app, DEBUG_DIR / "requests.db")

    @app.context_processor
    def inject_static_asset_url():
        def static_asset_url(filename: str) -> str:
            asset_path = STATIC_FOLDER / filename
            version = str(asset_path.stat().st_mtime_ns) if asset_path.exists() else "missing"
            return url_for("static", filename=filename, v=version)

        return {"static_asset_url": static_asset_url}

    def json_error(message: str, status: int = 400):
        return app.json.response({"error": message}), status

    def developer_ui_enabled() -> bool:
        if IS_PROD:
            return False
        try:
            return parse_bool(request.args.get("developer"), default=False)
        except ValueError:
            return False

    def frontend_app_config() -> dict[str, object]:
        return {
            "isProduction": IS_PROD,
            "developerMode": developer_ui_enabled(),
            "hybridPlannerDefaults": {
                "algorithmVersion": str(FINAL_RUNTIME_DEFAULTS["algorithm_version"]),
                "candidateCount": int(FINAL_RUNTIME_DEFAULTS["candidate_count"]),
                "modelCandidateCount": int(FINAL_RUNTIME_DEFAULTS["model_candidate_count"]),
                "candidateGeneratorBackend": str(FINAL_RUNTIME_DEFAULTS["candidate_generator_backend"]),
            },
        }

    @app.route("/")
    def index():
        return render_template("generic_dashboard.html", is_production=IS_PROD, generic_app_config=frontend_app_config())

    @app.route("/generic")
    def generic():
        return render_template("generic_dashboard.html", is_production=IS_PROD, generic_app_config=frontend_app_config())

    @app.route("/about")
    def about():
        return render_template("about.html", is_production=IS_PROD)

    @app.route("/api/stores/nearby", methods=["GET"])
    def api_stores_nearby():
        try:
            lat = parse_float(request.args.get("lat"), "lat")
            lon = parse_float(request.args.get("lon"), "lon")
            radius_m = parse_float(request.args.get("radius_m", DEFAULT_RADIUS_M), "radius_m")
            limit = parse_int(request.args.get("limit", DEFAULT_STORE_LIMIT), "limit")
        except ValueError as e:
            return json_error(str(e))

        if radius_m <= 0 or radius_m > MAX_RADIUS_M:
            return json_error(f"radius_m must be between 0 and {int(MAX_RADIUS_M)}.")
        if limit <= 0 or limit > MAX_STORE_LIMIT:
            return json_error(f"limit must be between 1 and {MAX_STORE_LIMIT}.")

        with get_con() as con:
            stores = nearby_stores(con, lat=lat, lon=lon, radius_m=radius_m, limit=limit)

        g.request_metadata["store_count"] = len(stores)
        g.request_metadata["radius_m"] = radius_m
        return app.json.response({"stores": stores})

    @app.route("/api/recommendations/generic", methods=["POST"])
    def api_recommendations_generic():
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return json_error("Expected a JSON object request body.")

        location = data.get("location")
        targets = data.get("targets")
        preferences_raw = data.get("preferences", {})
        pantry_items_raw = data.get("pantry_items", [])
        stores_raw = data.get("stores")
        if not isinstance(location, dict):
            return json_error("location must be an object with lat and lon.")
        if not isinstance(targets, dict):
            return json_error("targets must be an object with protein and energy_fibre_kcal.")
        if preferences_raw is not None and not isinstance(preferences_raw, dict):
            return json_error("preferences must be an object.")
        if pantry_items_raw is not None and not isinstance(pantry_items_raw, list):
            return json_error("pantry_items must be a list of generic food ids.")
        if stores_raw is not None and not isinstance(stores_raw, list):
            return json_error("stores must be a list when provided.")

        try:
            final_runtime_defaults = hybrid_pipeline_final.final_runtime_metadata()
            lat = parse_float(location.get("lat"), "location.lat")
            lon = parse_float(location.get("lon"), "location.lon")
            protein_target_g = parse_float(targets.get("protein"), "targets.protein")
            calorie_target_kcal = parse_float(targets.get("energy_fibre_kcal"), "targets.energy_fibre_kcal")
            radius_m = parse_float(data.get("radius_m", DEFAULT_RADIUS_M), "radius_m")
            nutrition_targets = {
                "carbohydrate": parse_optional_float(targets.get("carbohydrate"), "targets.carbohydrate"),
                "fat": parse_optional_float(targets.get("fat"), "targets.fat"),
                "fiber": parse_optional_float(targets.get("fiber"), "targets.fiber"),
                "calcium": parse_optional_float(targets.get("calcium"), "targets.calcium"),
                "iron": parse_optional_float(targets.get("iron"), "targets.iron"),
                "vitamin_c": parse_optional_float(targets.get("vitamin_c"), "targets.vitamin_c"),
            }
            store_limit = parse_int(data.get("store_limit", DEFAULT_STORE_LIMIT), "store_limit")
            days = parse_int(data.get("days", 1), "days")
            shopping_mode = parse_choice(data.get("shopping_mode"), "shopping_mode", {"fresh", "balanced", "bulk"}, "balanced")
            candidate_count = parse_int(
                data.get(
                    "candidate_count",
                    os.getenv("TRAINED_SCORER_CANDIDATE_COUNT", str(final_runtime_defaults["candidate_count"])),
                ),
                "candidate_count",
            )
            debug_scorer = (
                False
                if IS_PROD
                else parse_bool(data.get("debug_scorer"), default=os.getenv("TRAINED_SCORER_DEBUG", "0") == "1")
            )
            enable_model_candidates = parse_bool(
                data.get("enable_model_candidates"),
                default=parse_bool(os.getenv("ENABLE_MODEL_CANDIDATES"), default=bool(final_runtime_defaults["model_candidates_enabled"])),
            )
            model_candidate_count = parse_int(
                data.get(
                    "model_candidate_count",
                    os.getenv("MODEL_CANDIDATE_COUNT", str(final_runtime_defaults["model_candidate_count"])),
                ),
                "model_candidate_count",
            )
            candidate_generator_backend = parse_choice(
                data.get(
                    "candidate_generator_backend",
                    os.getenv("CANDIDATE_GENERATOR_BACKEND", str(final_runtime_defaults["candidate_generator_backend"])),
                ),
                "candidate_generator_backend",
                {"auto", "logistic_regression", "random_forest", "hist_gradient_boosting"},
                DEFAULT_CANDIDATE_GENERATOR_BACKEND,
            )
            debug_candidate_generation = (
                False
                if IS_PROD
                else parse_bool(
                    data.get("debug_candidate_generation"),
                    default=os.getenv("MODEL_CANDIDATE_DEBUG", "0") == "1",
                )
            )
            preferences = {
                "vegetarian": parse_bool(preferences_raw.get("vegetarian"), default=False),
                "dairy_free": parse_bool(preferences_raw.get("dairy_free"), default=False),
                "vegan": parse_bool(preferences_raw.get("vegan"), default=False),
                "low_prep": parse_bool(preferences_raw.get("low_prep"), default=False),
                "budget_friendly": parse_bool(preferences_raw.get("budget_friendly"), default=False),
                "meal_style": parse_choice(
                    preferences_raw.get("meal_style"),
                    "preferences.meal_style",
                    {"breakfast", "lunch_dinner", "snack", "any"},
                    "any",
                ),
            }
            pantry_items = [str(food_id).strip() for food_id in pantry_items_raw if str(food_id).strip()]
            scorer_model_path_raw = data.get(
                "scorer_model_path",
                os.getenv("TRAINED_SCORER_MODEL_PATH", str(final_runtime_defaults["scorer_model_path"])),
            )
            scorer_model_path = str(scorer_model_path_raw).strip() if scorer_model_path_raw is not None and str(scorer_model_path_raw).strip() else None
            candidate_generator_model_path_raw = data.get(
                "candidate_generator_model_path",
                os.getenv("CANDIDATE_GENERATOR_MODEL_PATH", str(final_runtime_defaults["candidate_generator_model_path"])),
            )
            candidate_generator_model_path = (
                str(candidate_generator_model_path_raw).strip()
                if candidate_generator_model_path_raw is not None and str(candidate_generator_model_path_raw).strip()
                else None
            )
        except ValueError as e:
            return json_error(str(e))

        if protein_target_g <= 0:
            return json_error("targets.protein must be greater than 0.")
        if calorie_target_kcal <= 0:
            return json_error("targets.energy_fibre_kcal must be greater than 0.")
        if radius_m <= 0 or radius_m > MAX_RADIUS_M:
            return json_error(f"radius_m must be between 0 and {int(MAX_RADIUS_M)}.")
        invalid_optional_targets = [name for name, value in nutrition_targets.items() if value is not None and value <= 0]
        if invalid_optional_targets:
            return json_error(f"targets.{invalid_optional_targets[0]} must be greater than 0 when provided.")
        if store_limit <= 0 or store_limit > MAX_STORE_LIMIT:
            return json_error(f"store_limit must be between 1 and {MAX_STORE_LIMIT}.")
        if days not in {1, 3, 5, 7}:
            return json_error("days must be one of 1 3 5 or 7.")
        if candidate_count < 1 or candidate_count > MAX_TRAINED_SCORER_CANDIDATE_COUNT:
            return json_error(f"candidate_count must be between 1 and {MAX_TRAINED_SCORER_CANDIDATE_COUNT}.")
        if model_candidate_count < 1 or model_candidate_count > MAX_MODEL_CANDIDATE_COUNT:
            return json_error(f"model_candidate_count must be between 1 and {MAX_MODEL_CANDIDATE_COUNT}.")

        with get_con() as con:
            stores = normalize_store_snapshot(stores_raw, limit=store_limit) if stores_raw is not None else []
            if not stores:
                stores = nearby_stores(con, lat=lat, lon=lon, radius_m=radius_m, limit=store_limit)
            price_context = resolve_price_context(lat, lon, stores)
            try:
                scorer_config = hybrid_pipeline_final.final_scorer_config(
                    debug=debug_scorer,
                    candidate_count=candidate_count,
                    scorer_model_path=Path(scorer_model_path) if scorer_model_path else None,
                )
                candidate_generation_config = hybrid_pipeline_final.final_candidate_generation_config(
                    debug=debug_candidate_generation,
                    enable_model_candidates=enable_model_candidates,
                    model_candidate_count=model_candidate_count,
                    candidate_generator_model_path=Path(candidate_generator_model_path) if candidate_generator_model_path else None,
                    candidate_generator_backend=candidate_generator_backend,
                )
                recommendation = recommend_generic_foods(
                    con,
                    protein_target_g=protein_target_g,
                    calorie_target_kcal=calorie_target_kcal,
                    preferences=preferences,
                    nutrition_targets=nutrition_targets,
                    pantry_items=pantry_items,
                    days=days,
                    shopping_mode=shopping_mode,
                    price_context=price_context,
                    stores=stores,
                    scorer_config=scorer_config,
                    candidate_generation_config=candidate_generation_config,
                )
            except PlanScorerArtifactError as e:
                return json_error(str(e), status=500)
            except ModelCandidateArtifactError as e:
                return json_error(str(e), status=500)
            except ValueError as e:
                return json_error(str(e), status=422)

        g.request_metadata["store_count"] = len(stores)
        g.request_metadata["shopping_list_count"] = len(recommendation["shopping_list"])
        g.request_metadata["protein_target_g"] = protein_target_g
        g.request_metadata["calorie_target_kcal"] = calorie_target_kcal
        g.request_metadata["days"] = days
        g.request_metadata["radius_m"] = radius_m
        g.request_metadata["shopping_mode"] = shopping_mode
        g.request_metadata["pantry_item_count"] = len(pantry_items)
        g.request_metadata["price_area_code"] = recommendation.get("price_area_code")
        g.request_metadata["candidate_count"] = candidate_count
        g.request_metadata["model_candidates_enabled"] = bool(enable_model_candidates)
        g.request_metadata["model_candidate_count"] = model_candidate_count
        execution_summary = recommendation.get("hybrid_planner_execution")
        execution_summary = dict(execution_summary) if isinstance(execution_summary, dict) else {}
        candidate_generation_debug = recommendation.get("candidate_generation_debug")
        candidate_generation_debug = candidate_generation_debug if isinstance(candidate_generation_debug, dict) else {}
        actual_candidate_generator_backend = (
            execution_summary.get("candidate_generator_backend")
            or candidate_generation_debug.get("candidate_generator_backend")
            or candidate_generator_backend
        )
        heuristic_candidate_total = execution_summary.get("heuristic_candidate_count")
        model_candidate_total = execution_summary.get("learned_candidate_count")
        fused_candidate_total = execution_summary.get("fused_candidate_count") or recommendation.get("candidate_count_considered")
        if "scorer_used" in recommendation:
            g.request_metadata["scorer_used"] = bool(recommendation.get("scorer_used"))
        if recommendation.get("scorer_backend"):
            g.request_metadata["scorer_backend"] = recommendation.get("scorer_backend")
        if execution_summary.get("pipeline_mode"):
            g.request_metadata["pipeline_mode"] = execution_summary["pipeline_mode"]
        if actual_candidate_generator_backend:
            g.request_metadata["candidate_generator_backend"] = actual_candidate_generator_backend
        if recommendation.get("selected_candidate_source"):
            g.request_metadata["selected_candidate_source"] = recommendation.get("selected_candidate_source")
        if recommendation.get("selected_candidate_id"):
            g.request_metadata["selected_candidate_id"] = recommendation.get("selected_candidate_id")
        if heuristic_candidate_total is not None:
            g.request_metadata["heuristic_candidate_count"] = heuristic_candidate_total
        if model_candidate_total is not None:
            g.request_metadata["generated_model_candidate_count"] = model_candidate_total
        if fused_candidate_total is not None:
            g.request_metadata["fused_candidate_count"] = fused_candidate_total
        app.logger.info(
            "generic recommendation: pipeline_mode=%s model_enabled=%s candidate_generator_backend=%s heuristic_candidates=%s model_candidates=%s fused_candidates=%s selected_source=%s selected_id=%s",
            execution_summary.get("pipeline_mode") or ("full_hybrid" if enable_model_candidates else "heuristic_only"),
            bool(enable_model_candidates),
            actual_candidate_generator_backend or "unknown",
            heuristic_candidate_total if heuristic_candidate_total is not None else "n/a",
            model_candidate_total if model_candidate_total is not None else "n/a",
            fused_candidate_total if fused_candidate_total is not None else "n/a",
            recommendation.get("selected_candidate_source") or "unknown",
            recommendation.get("selected_candidate_id") or "unknown",
        )
        store_fit = recommend_store_fits(
            stores,
            recommendation["shopping_list"],
            preferences=preferences,
            days=days,
            shopping_mode=shopping_mode,
        )
        execution_summary.update(
            {
                "store_fit_ranking_ran": True,
                "stores_evaluated_count": len(stores),
                "store_fit_ranked_store_count": len(store_fit["recommended_store_order"]),
                "full_pipeline_completed": bool(execution_summary.get("scorer_reranking_used", recommendation.get("scorer_used"))),
            }
        )
        recommendation["hybrid_planner_execution"] = execution_summary
        g.request_metadata["recommended_store_count"] = len(store_fit["recommended_store_order"])
        response_payload = {"stores": stores, **recommendation, **store_fit}
        return app.json.response(
            sanitize_recommendation_response_for_prod(response_payload) if IS_PROD else response_payload
        )

    return app


def main() -> None:
    """Run the generic planner demo app."""
    app = create_app()
    port = int(os.getenv("PORT", "8000"))
    app.run(debug=not IS_PROD, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
