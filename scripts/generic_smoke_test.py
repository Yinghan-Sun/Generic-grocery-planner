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

    invalid = client.get("/api/stores/nearby?lat=&lon=-122.09&radius_m=8000&limit=5")
    assert_equal(invalid.status_code, 400, "invalid nearby-store status")
    invalid_json = invalid.get_json()
    assert_equal(invalid_json["error"], "Invalid lat.", "invalid nearby-store error")

    print("generic_page=ok")
    print(f"nearby_store_count={len(stores)}")
    print(f"balanced_item_count={len(balanced_json['shopping_list'])}")
    print(f"vegetarian_item_count={len(vegetarian_json['shopping_list'])}")
    print("invalid_input_check=ok")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print(f"SMOKE TEST FAILED: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
