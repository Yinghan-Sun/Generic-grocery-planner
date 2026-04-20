#!/usr/bin/env -S uv run
"""Smoke checks for the /generic demo flow."""

from __future__ import annotations

import sys
import time
from unittest.mock import patch

import dietdashboard.app as app_module
from dietdashboard.app import create_app


def assert_equal(actual, expected, label: str) -> None:
    if actual != expected:
        raise AssertionError(f"{label}: expected {expected!r}, got {actual!r}")


def assert_true(value: bool, label: str) -> None:
    if not value:
        raise AssertionError(f"{label}: expected truthy value")


def assert_no_hybrid_debug_metadata(payload: dict[str, object], label: str) -> None:
    execution = payload.get("hybrid_planner_execution")
    assert_true(isinstance(execution, dict), f"{label} hybrid execution summary")
    assert_true(
        not any(
            key.endswith("_model_path") or key.endswith("_backend") or key.startswith("candidate_generator_")
            for key in execution
        ),
        f"{label} hybrid execution metadata sanitized",
    )
    algorithm = payload.get("hybrid_planner_algorithm")
    assert_true(isinstance(algorithm, dict), f"{label} hybrid algorithm summary")
    assert_true(
        not any(
            key.endswith("_model_path") or key.endswith("_backend") or key.startswith("candidate_generator_")
            for key in algorithm
        ),
        f"{label} hybrid algorithm metadata sanitized",
    )


def main() -> int:
    app = create_app()
    client = app.test_client()

    homepage = client.get("/")
    assert_equal(homepage.status_code, 200, "/ status")
    homepage_html = homepage.get_data(as_text=True)
    assert_true("/static/generic_bundle.js" in homepage_html, "homepage bundle reference")
    assert_true('id="generic-form"' in homepage_html, "homepage form mount")
    assert_true("/legacy" not in homepage_html, "no legacy navigation")

    generic_page = client.get("/generic")
    assert_equal(generic_page.status_code, 200, "/generic status")
    generic_html = generic_page.get_data(as_text=True)
    assert_true("/static/generic_bundle.js" in generic_html, "/generic bundle reference")
    assert_true('"developerMode": false' in generic_html, "/generic developer mode disabled by default")

    developer_page = client.get("/generic?developer=1")
    assert_equal(developer_page.status_code, 200, "/generic developer page status")
    developer_html = developer_page.get_data(as_text=True)
    assert_true('"developerMode": true' in developer_html, "/generic developer mode opt-in")

    nearby = client.get("/api/stores/nearby?lat=37.401&lon=-122.09&radius_m=8000&limit=5")
    assert_equal(nearby.status_code, 200, "/api/stores/nearby status")
    nearby_json = nearby.get_json()
    assert_true(isinstance(nearby_json, dict), "/api/stores/nearby json object")
    stores = nearby_json["stores"]
    assert_true(len(stores) >= 1, "/api/stores/nearby store count")

    balanced_payload = {
        "location": {"lat": 37.401, "lon": -122.09},
        "targets": {"protein": 130, "energy_fibre_kcal": 2100},
        "preferences": {"vegetarian": False, "dairy_free": False},
        "store_limit": 5,
    }
    balanced = client.post("/api/recommendations/generic", json=balanced_payload)
    assert_equal(balanced.status_code, 200, "balanced recommendation status")
    balanced_json = balanced.get_json()
    assert_true(len(balanced_json["shopping_list"]) >= 1, "balanced recommendation items")
    assert_true(len(balanced_json["stores"]) >= 1, "balanced recommendation stores")
    assert_true(bool(balanced_json.get("scorer_used")), "balanced scorer used")
    assert_true("selected_candidate_source" in balanced_json, "balanced selected candidate source")
    assert_true(int(balanced_json.get("candidate_count_considered") or 0) >= 1, "balanced candidate count considered")
    assert_true("scoring_debug" not in balanced_json, "balanced scorer debug hidden by default")
    assert_true("candidate_generation_debug" not in balanced_json, "balanced candidate-generation debug hidden by default")
    assert_true("candidate_comparison_debug" not in balanced_json, "balanced candidate comparison debug hidden by default")
    hybrid_execution = balanced_json.get("hybrid_planner_execution")
    assert_true(isinstance(hybrid_execution, dict), "balanced hybrid execution summary")
    assert_equal(hybrid_execution.get("pipeline_mode"), "full_hybrid", "balanced pipeline mode")
    assert_true(bool(hybrid_execution.get("heuristic_candidate_generation_ran")), "balanced heuristic generation ran")
    assert_true(bool(hybrid_execution.get("learned_candidate_generation_ran")), "balanced learned generation ran")
    assert_true(bool(hybrid_execution.get("candidate_fusion_ran")), "balanced candidate fusion ran")
    assert_true(bool(hybrid_execution.get("scorer_reranking_used")), "balanced scorer reranking ran")
    assert_true(bool(hybrid_execution.get("store_fit_ranking_ran")), "balanced store fit ran")
    assert_true(bool(hybrid_execution.get("full_pipeline_completed")), "balanced full pipeline completed")
    assert_equal(hybrid_execution.get("candidate_generator_backend"), "random_forest", "balanced default candidate backend")

    vegetarian_payload = {
        "location": {"lat": 37.401, "lon": -122.09},
        "targets": {"protein": 110, "energy_fibre_kcal": 2000},
        "preferences": {"vegetarian": True, "dairy_free": False},
        "store_limit": 5,
    }
    vegetarian = client.post("/api/recommendations/generic", json=vegetarian_payload)
    assert_equal(vegetarian.status_code, 200, "vegetarian recommendation status")
    vegetarian_json = vegetarian.get_json()
    assert_true(len(vegetarian_json["shopping_list"]) >= 1, "vegetarian recommendation items")

    developer_debug_payload = {
        **balanced_payload,
        "debug_candidate_generation": True,
        "debug_scorer": True,
    }
    developer_debug = client.post("/api/recommendations/generic", json=developer_debug_payload)
    assert_equal(developer_debug.status_code, 200, "developer debug recommendation status")
    developer_debug_json = developer_debug.get_json()
    assert_true(isinstance(developer_debug_json.get("scoring_debug"), dict), "developer scorer debug")
    assert_true(isinstance(developer_debug_json.get("candidate_generation_debug"), dict), "developer candidate-generation debug")
    assert_true(isinstance(developer_debug_json.get("candidate_comparison_debug"), dict), "developer candidate comparison debug")

    missing_model_payload = {
        **balanced_payload,
        "scorer_model_path": "artifacts/plan_scorer/does_not_exist.joblib",
    }
    missing_model = client.post("/api/recommendations/generic", json=missing_model_payload)
    assert_equal(missing_model.status_code, 500, "missing model recommendation status")
    missing_model_json = missing_model.get_json()
    assert_true(
        "Required trained plan scorer artifact" in str(missing_model_json.get("error")),
        "missing model recommendation error",
    )

    invalid = client.get("/api/stores/nearby?lat=&lon=-122.09&radius_m=8000&limit=5")
    assert_equal(invalid.status_code, 400, "invalid nearby-store status")
    invalid_json = invalid.get_json()
    assert_equal(invalid_json["error"], "Invalid lat.", "invalid nearby-store error")

    prod_debug_payload = {
        **balanced_payload,
        "radius_m": 8000,
        "debug_candidate_generation": True,
        "debug_scorer": True,
    }
    with patch.object(app_module, "IS_PROD", True):
        prod_app = app_module.create_app()
        prod_client = prod_app.test_client()
        prod_debug = prod_client.post("/api/recommendations/generic", json=prod_debug_payload)
    assert_equal(prod_debug.status_code, 200, "prod debug recommendation status")
    prod_debug_json = prod_debug.get_json()
    assert_true("scoring_debug" not in prod_debug_json, "prod scorer debug removed")
    assert_true("candidate_generation_debug" not in prod_debug_json, "prod candidate-generation debug removed")
    assert_true("candidate_comparison_debug" not in prod_debug_json, "prod candidate comparison debug removed")
    assert_true("algorithmic_faithfulness_debug" not in prod_debug_json, "prod algorithmic faithfulness debug removed")
    assert_true("scorer_backend" not in prod_debug_json, "prod scorer backend removed")
    prod_execution = prod_debug_json.get("hybrid_planner_execution")
    assert_true(isinstance(prod_execution, dict), "prod hybrid execution summary")
    assert_true("candidate_generator_backend" not in prod_execution, "prod execution backend removed")
    assert_true("candidate_generator_model_path" not in prod_execution, "prod execution candidate-generator path removed")
    assert_true("scorer_backend" not in prod_execution, "prod execution scorer backend removed")
    assert_true("scorer_model_path" not in prod_execution, "prod execution scorer path removed")
    prod_algorithm = prod_debug_json.get("hybrid_planner_algorithm")
    assert_true(isinstance(prod_algorithm, dict), "prod hybrid algorithm summary")
    assert_true("candidate_generator_backend" not in prod_algorithm, "prod algorithm backend removed")
    assert_true("candidate_generator_model_path" not in prod_algorithm, "prod algorithm path removed")
    assert_no_hybrid_debug_metadata(prod_debug_json, "prod nested planner metadata")

    radius_calls: list[float] = []

    def fake_nearby_stores(_con, lat: float, lon: float, radius_m: float = 0.0, limit: int = 5):
        del lat, lon, limit
        radius_calls.append(float(radius_m))
        if radius_m <= 500.0:
            return []
        return [
            {
                "store_id": "stub:wide-radius",
                "name": "Wide Radius Store",
                "address": "100 Demo St, Mountain View, CA 94040",
                "distance_m": 750.0,
                "lat": 37.401,
                "lon": -122.09,
                "category": "supermarket",
            }
        ]

    with patch.object(app_module, "nearby_stores", side_effect=fake_nearby_stores):
        radius_app = app_module.create_app()
        radius_client = radius_app.test_client()
        nearby_small = radius_client.get("/api/stores/nearby?lat=37.401&lon=-122.09&radius_m=500&limit=5")
        assert_equal(nearby_small.status_code, 200, "small-radius nearby-store status")
        nearby_small_json = nearby_small.get_json()
        assert_equal(len(nearby_small_json["stores"]), 0, "small-radius nearby-store count")

        small_radius_payload = {
            **balanced_payload,
            "radius_m": 500,
        }
        small_radius_recommendation = radius_client.post("/api/recommendations/generic", json=small_radius_payload)
        assert_equal(small_radius_recommendation.status_code, 200, "small-radius recommendation status")
        small_radius_json = small_radius_recommendation.get_json()
        assert_equal(len(small_radius_json["stores"]), 0, "small-radius recommendation stores")

    assert_equal(radius_calls, [500.0, 500.0], "nearby-store radius reused for recommendation")

    def sleepy_nearby_stores(_con, lat: float, lon: float, radius_m: float = 0.0, limit: int = 5):
        del lat, lon, radius_m, limit
        time.sleep(0.3)
        return [
            {
                "store_id": "stub:slow-nearby",
                "name": "Slow Nearby Store",
                "address": "100 Demo St, Mountain View, CA 94040",
                "distance_m": 250.0,
                "lat": 37.401,
                "lon": -122.09,
                "category": "supermarket",
            }
        ]

    with (
        patch.object(app_module, "NEARBY_STORES_TIMEOUT_S", 0.05),
        patch.object(app_module, "RECOMMENDATION_STORE_LOOKUP_TIMEOUT_S", 0.05),
        patch.object(app_module, "nearby_stores", side_effect=sleepy_nearby_stores),
    ):
        timeout_app = app_module.create_app()
        timeout_client = timeout_app.test_client()

        nearby_start = time.perf_counter()
        timed_nearby = timeout_client.get("/api/stores/nearby?lat=37.401&lon=-122.09&radius_m=8000&limit=5")
        nearby_elapsed = time.perf_counter() - nearby_start
        assert_equal(timed_nearby.status_code, 200, "timed nearby-store status")
        timed_nearby_json = timed_nearby.get_json()
        assert_equal(timed_nearby_json["stores"], [], "timed nearby-store fallback")
        assert_true(nearby_elapsed < 0.2, "timed nearby-store bounded latency")

        timed_recommendation_start = time.perf_counter()
        timed_recommendation = timeout_client.post("/api/recommendations/generic", json=balanced_payload)
        timed_recommendation_elapsed = time.perf_counter() - timed_recommendation_start
        assert_equal(timed_recommendation.status_code, 200, "timed recommendation status")
        timed_recommendation_json = timed_recommendation.get_json()
        assert_equal(timed_recommendation_json["stores"], [], "timed recommendation store fallback")
        assert_true(len(timed_recommendation_json["shopping_list"]) >= 1, "timed recommendation still returns shopping list")
        assert_true(timed_recommendation_elapsed < 1.0, "timed recommendation bounded latency")

    def sleepy_store_fit(stores, shopping_list, *, preferences=None, days=1, shopping_mode="balanced"):
        del stores, shopping_list, preferences, days, shopping_mode
        time.sleep(0.3)
        return {"recommended_store_order": ["stub:slow"], "store_fit_notes": []}

    with (
        patch.object(app_module, "STORE_FIT_TIMEOUT_S", 0.05),
        patch.object(app_module, "recommend_store_fits", side_effect=sleepy_store_fit),
    ):
        timeout_app = app_module.create_app()
        timeout_client = timeout_app.test_client()
        store_fit_start = time.perf_counter()
        timed_store_fit = timeout_client.post("/api/recommendations/generic", json=balanced_payload)
        store_fit_elapsed = time.perf_counter() - store_fit_start
        assert_equal(timed_store_fit.status_code, 200, "timed store-fit recommendation status")
        timed_store_fit_json = timed_store_fit.get_json()
        assert_true(len(timed_store_fit_json["shopping_list"]) >= 1, "timed store-fit recommendation items")
        assert_equal(timed_store_fit_json["recommended_store_order"], [], "timed store-fit fallback order")
        assert_equal(timed_store_fit_json["store_fit_notes"], [], "timed store-fit fallback notes")
        assert_true(store_fit_elapsed < 1.0, "timed store-fit bounded latency")

    print("generic_page=ok")
    print(f"nearby_store_count={len(stores)}")
    print(f"balanced_item_count={len(balanced_json['shopping_list'])}")
    print(f"balanced_pipeline_mode={hybrid_execution['pipeline_mode']}")
    print(f"balanced_heuristic_candidates={hybrid_execution['heuristic_candidate_count']}")
    print(f"balanced_learned_candidates={hybrid_execution['learned_candidate_count']}")
    print(f"balanced_fused_candidates={hybrid_execution['fused_candidate_count']}")
    print(f"balanced_candidate_backend={hybrid_execution['candidate_generator_backend']}")
    print(f"vegetarian_item_count={len(vegetarian_json['shopping_list'])}")
    print("prod_debug_suppression=ok")
    print("prod_hybrid_metadata_sanitization=ok")
    print("recommendation_radius_reuse=ok")
    print("slow_dependency_fallbacks=ok")
    print("invalid_input_check=ok")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print(f"SMOKE TEST FAILED: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
