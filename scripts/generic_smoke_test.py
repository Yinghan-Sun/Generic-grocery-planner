#!/usr/bin/env -S uv run
"""Smoke checks for the /generic demo flow."""

from __future__ import annotations

import sys

from dietdashboard.app import create_app


def assert_equal(actual, expected, label: str) -> None:
    if actual != expected:
        raise AssertionError(f"{label}: expected {expected!r}, got {actual!r}")


def assert_true(value: bool, label: str) -> None:
    if not value:
        raise AssertionError(f"{label}: expected truthy value")


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

    print("generic_page=ok")
    print(f"nearby_store_count={len(stores)}")
    print(f"balanced_item_count={len(balanced_json['shopping_list'])}")
    print(f"balanced_pipeline_mode={hybrid_execution['pipeline_mode']}")
    print(f"balanced_heuristic_candidates={hybrid_execution['heuristic_candidate_count']}")
    print(f"balanced_learned_candidates={hybrid_execution['learned_candidate_count']}")
    print(f"balanced_fused_candidates={hybrid_execution['fused_candidate_count']}")
    print(f"balanced_candidate_backend={hybrid_execution['candidate_generator_backend']}")
    print(f"vegetarian_item_count={len(vegetarian_json['shopping_list'])}")
    print("invalid_input_check=ok")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print(f"SMOKE TEST FAILED: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
