#!/usr/bin/env -S uv run
"""Scenario-level regression checks for the /generic flow."""

from __future__ import annotations

import sys
import tempfile
from contextlib import ExitStack, contextmanager
from pathlib import Path
from typing import Any

import duckdb

import dietdashboard.app as app_module
import dietdashboard.generic_recommender as recommender_module
import dietdashboard.store_discovery as store_discovery
from dietdashboard.app import create_app

ROLE_SET = {"protein_anchor", "carb_base", "produce", "calorie_booster"}
PRICE_SOURCE_SET = {"usda_area", "bls_area", "bls_fallback"}
GOAL_PROFILE_SET = {
    "muscle_gain",
    "fat_loss",
    "maintenance",
    "high_protein_vegetarian",
    "budget_friendly_healthy",
    "generic_balanced",
}
EXPECTED_STORE_KEYS = {"address", "category", "distance_m", "lat", "lon", "name", "store_id"}
EXPECTED_GROUPED_STORE_PICK_KEYS = {"store_id", "store_name", "category", "distance_m", "note"}
EXPECTED_ITEM_KEYS = {
    "estimated_calories_kcal",
    "estimated_item_cost",
    "estimated_price_high",
    "estimated_price_low",
    "estimated_protein_g",
    "estimated_unit_price",
    "generic_food_id",
    "name",
    "price_efficiency_note",
    "price_source_used",
    "price_unit_display",
    "quantity_display",
    "quantity_g",
    "reason",
    "reason_short",
    "role",
    "substitution",
    "substitution_reason",
    "typical_item_cost",
    "typical_unit_price",
    "value_reason_short",
    "why_selected",
}
STUB_STORES = [
    {
        "store_id": "stub:costco",
        "name": "Costco Wholesale",
        "address": "100 Rengstorff Ave, Mountain View, CA 94040",
        "distance_m": 180.0,
        "lat": 37.3861,
        "lon": -122.0839,
        "category": "wholesale_club",
    },
    {
        "store_id": "stub:wholefoods",
        "name": "Whole Foods Market",
        "address": "200 El Camino Real, Mountain View, CA 94040",
        "distance_m": 320.0,
        "lat": 37.388,
        "lon": -122.082,
        "category": "supermarket",
    },
    {
        "store_id": "stub:traderjoes",
        "name": "Trader Joe's",
        "address": "590 Showers Dr, Mountain View, CA 94040",
        "distance_m": 520.0,
        "lat": 37.3891,
        "lon": -122.0852,
        "category": "grocery",
    },
]


def assert_equal(actual: Any, expected: Any, label: str) -> None:
    if actual != expected:
        raise AssertionError(f"{label}: expected {expected!r}, got {actual!r}")


def assert_true(value: bool, label: str) -> None:
    if not value:
        raise AssertionError(f"{label}: expected truthy value")


@contextmanager
def patched_attr(obj: object, attr: str, value: object):
    original = getattr(obj, attr)
    setattr(obj, attr, value)
    try:
        yield
    finally:
        setattr(obj, attr, original)


@contextmanager
def patched_attrs(obj: object, **replacements: object):
    with ExitStack() as stack:
        for attr, value in replacements.items():
            stack.enter_context(patched_attr(obj, attr, value))
        yield


def load_name_to_id() -> dict[str, str]:
    with duckdb.connect("data/data.db", read_only=True) as con:
        rows = con.execute("SELECT generic_food_id, display_name FROM generic_foods").fetchall()
    return {str(display_name): str(generic_food_id) for generic_food_id, display_name in rows}


def load_price_meta() -> dict[str, dict[str, float | str | None]]:
    with duckdb.connect("data/data.db", read_only=True) as con:
        rows = con.execute(
            """
            SELECT
              g.generic_food_id,
              g.default_serving_g,
              g.purchase_unit_size_g,
              p.price_basis_kind,
              p.price_basis_value,
              p.price_unit_display
            FROM generic_foods AS g
            LEFT JOIN generic_food_prices AS p USING (generic_food_id)
            """
        ).fetchall()
    return {
        str(generic_food_id): {
            "default_serving_g": default_serving_g,
            "purchase_unit_size_g": purchase_unit_size_g,
            "price_basis_kind": price_basis_kind,
            "price_basis_value": price_basis_value,
            "price_unit_display": price_unit_display,
        }
        for generic_food_id, default_serving_g, purchase_unit_size_g, price_basis_kind, price_basis_value, price_unit_display in rows
    }


def load_food_meta() -> dict[str, dict[str, object]]:
    with duckdb.connect("data/data.db", read_only=True) as con:
        rows = con.execute(
            """
            SELECT
              generic_food_id,
              prep_level,
              budget_score,
              microwave_friendly
            FROM generic_foods
            """
        ).fetchall()
    return {
        str(generic_food_id): {
            "prep_level": str(prep_level or ""),
            "budget_score": float(budget_score or 0.0),
            "microwave_friendly": bool(microwave_friendly),
        }
        for generic_food_id, prep_level, budget_score, microwave_friendly in rows
    }


def scenario_payloads() -> list[tuple[str, dict[str, Any], set[str], set[str]]]:
    return [
        (
            "balanced",
            {
                "location": {"lat": 37.3861, "lon": -122.0839},
                "targets": {"protein": 130, "energy_fibre_kcal": 2100},
                "preferences": {"vegetarian": False, "dairy_free": False},
                "store_limit": 2,
            },
            set(),
            set(),
        ),
        (
            "vegetarian",
            {
                "location": {"lat": 37.3861, "lon": -122.0839},
                "targets": {"protein": 120, "energy_fibre_kcal": 2000},
                "preferences": {"vegetarian": True, "dairy_free": False},
                "store_limit": 2,
            },
            {"chicken_breast", "tuna"},
            {"tofu", "eggs", "lentils", "beans", "oats", "bananas", "spinach", "broccoli"},
        ),
        (
            "vegan",
            {
                "location": {"lat": 37.3861, "lon": -122.0839},
                "targets": {"protein": 110, "energy_fibre_kcal": 2000},
                "preferences": {"vegan": True},
                "store_limit": 2,
            },
            {"eggs", "milk", "greek_yogurt", "cheese", "tuna", "chicken_breast"},
            {"tofu", "lentils", "beans", "oats", "bananas", "spinach", "broccoli"},
        ),
        (
            "dairy_free",
            {
                "location": {"lat": 37.3861, "lon": -122.0839},
                "targets": {"protein": 120, "energy_fibre_kcal": 2050},
                "preferences": {"dairy_free": True},
                "store_limit": 2,
            },
            {"milk", "greek_yogurt", "cheese"},
            {"chicken_breast", "tuna", "eggs", "tofu", "oats", "bananas", "spinach", "broccoli"},
        ),
        (
            "budget_friendly",
            {
                "location": {"lat": 37.3861, "lon": -122.0839},
                "targets": {"protein": 110, "energy_fibre_kcal": 2100},
                "preferences": {"budget_friendly": True},
                "store_limit": 2,
            },
            set(),
            {"lentils", "beans", "oats", "rice", "bananas", "broccoli", "potatoes"},
        ),
        (
            "breakfast",
            {
                "location": {"lat": 37.3861, "lon": -122.0839},
                "targets": {"protein": 100, "energy_fibre_kcal": 1900},
                "preferences": {"meal_style": "breakfast"},
                "store_limit": 2,
            },
            set(),
            {"eggs", "oats", "greek_yogurt", "protein_yogurt", "bananas", "bagel", "corn_flakes"},
        ),
        (
            "snack",
            {
                "location": {"lat": 37.3861, "lon": -122.0839},
                "targets": {"protein": 95, "energy_fibre_kcal": 1800},
                "preferences": {"meal_style": "snack"},
                "store_limit": 2,
            },
            set(),
            {"greek_yogurt", "protein_yogurt", "cottage_cheese", "peanut_butter", "nuts", "bananas", "apples"},
        ),
    ]


def verify_shopping_list(
    label: str,
    shopping_list: list[dict[str, Any]],
    name_to_id: dict[str, str],
    forbidden_ids: set[str],
    preferred_ids: set[str],
) -> tuple[str, ...]:
    assert_true(len(shopping_list) >= 1, f"{label} shopping list non-empty")
    roles = [str(item["role"]) for item in shopping_list]
    assert_true(any(role == "protein_anchor" for role in roles), f"{label} has protein anchor")
    assert_true(any(role == "carb_base" for role in roles), f"{label} has carb base")
    assert_true(any(role == "produce" for role in roles), f"{label} has produce")

    returned_ids: list[str] = []
    for item in shopping_list:
        assert_equal(set(item.keys()), EXPECTED_ITEM_KEYS, f"{label} item keys")
        assert_true(bool(item["generic_food_id"]), f"{label} generic_food_id present")
        assert_true(bool(item["quantity_display"]), f"{label} quantity_display present")
        assert_true(bool(item["reason_short"]), f"{label} reason_short present")
        assert_true(bool(item["why_selected"]), f"{label} why_selected present")
        assert_true(str(item["role"]) in ROLE_SET, f"{label} role value")
        food_id = str(item["generic_food_id"])
        returned_ids.append(food_id)
        if food_id in forbidden_ids:
            raise AssertionError(f"{label}: forbidden food returned: {food_id}")

        substitution = item["substitution"]
        if substitution is not None:
            assert_true(bool(item["substitution_reason"]), f"{label} substitution_reason present")
            substitute_id = name_to_id.get(str(substitution))
            if substitute_id is None:
                raise AssertionError(f"{label}: unknown substitution {substitution!r}")
            if substitute_id in forbidden_ids:
                raise AssertionError(f"{label}: forbidden substitution returned: {substitute_id}")
        else:
            assert_true(item["substitution_reason"] is None, f"{label} substitution_reason omitted with no substitution")

        estimated_item_cost = item["estimated_item_cost"]
        estimated_unit_price = item["estimated_unit_price"]
        price_unit_display = item["price_unit_display"]
        typical_item_cost = item["typical_item_cost"]
        typical_unit_price = item["typical_unit_price"]
        estimated_price_low = item["estimated_price_low"]
        estimated_price_high = item["estimated_price_high"]
        if estimated_item_cost is not None:
            assert_true(estimated_unit_price is not None, f"{label} estimated_unit_price present with item cost")
            assert_true(price_unit_display is not None, f"{label} price_unit_display present with item cost")
            assert_true(str(item["price_source_used"]) in PRICE_SOURCE_SET, f"{label} price_source_used present with item cost")
            assert_true(float(estimated_item_cost) > 0, f"{label} estimated_item_cost positive")
            assert_true(float(estimated_unit_price) > 0, f"{label} estimated_unit_price positive")
            assert_equal(typical_item_cost, estimated_item_cost, f"{label} typical_item_cost mirrors estimated_item_cost")
            assert_equal(typical_unit_price, estimated_unit_price, f"{label} typical_unit_price mirrors estimated_unit_price")
            if estimated_price_low is not None and estimated_price_high is not None:
                assert_true(float(estimated_price_low) > 0, f"{label} estimated_price_low positive")
                assert_true(float(estimated_price_high) > 0, f"{label} estimated_price_high positive")
                assert_true(float(estimated_price_low) <= float(estimated_item_cost), f"{label} estimated_price_low <= typical")
                assert_true(float(estimated_price_high) >= float(estimated_item_cost), f"{label} estimated_price_high >= typical")
            if item["value_reason_short"] is not None:
                assert_true(bool(item["price_efficiency_note"]), f"{label} price_efficiency_note present with value reason")
        else:
            assert_true(item["price_source_used"] is None, f"{label} price_source_used omitted when unpriced")
            assert_true(typical_item_cost is None, f"{label} typical_item_cost omitted when unpriced")
            assert_true(typical_unit_price is None or float(typical_unit_price) > 0, f"{label} typical_unit_price valid when present")
            assert_true(estimated_price_low is None, f"{label} estimated_price_low omitted when unpriced")
            assert_true(estimated_price_high is None, f"{label} estimated_price_high omitted when unpriced")
            assert_true(
                estimated_unit_price is None or float(estimated_unit_price) > 0,
                f"{label} estimated_unit_price valid when present",
            )
            assert_true(
                item["price_efficiency_note"] is None or bool(item["price_efficiency_note"]),
                f"{label} price_efficiency_note valid when unpriced",
            )

    if preferred_ids:
        assert_true(any(food_id in preferred_ids for food_id in returned_ids), f"{label} has preferred bias")
    return tuple(returned_ids)


def verify_meal_suggestions(label: str, payload: dict[str, Any], shopping_list: list[dict[str, Any]]) -> tuple[tuple[str, tuple[str, ...]], ...]:
    suggestions = payload.get("meal_suggestions")
    assert_true(isinstance(suggestions, list), f"{label} meal_suggestions list")
    assert_true(len(suggestions) >= 2, f"{label} meal_suggestions non-trivial")
    basket_names = {str(item["name"]) for item in shopping_list}

    normalized: list[tuple[str, tuple[str, ...]]] = []
    for suggestion in suggestions:
        assert_true(isinstance(suggestion, dict), f"{label} meal_suggestion object")
        assert_equal(
            set(suggestion.keys()),
            {"meal_type", "title", "items", "description"},
            f"{label} meal_suggestion keys",
        )
        assert_true(bool(suggestion["meal_type"]), f"{label} meal_suggestion meal_type present")
        assert_true(bool(suggestion["title"]), f"{label} meal_suggestion title present")
        assert_true(bool(suggestion["description"]), f"{label} meal_suggestion description present")
        assert_true(isinstance(suggestion["items"], list), f"{label} meal_suggestion items list")
        assert_true(len(suggestion["items"]) >= 2, f"{label} meal_suggestion items non-trivial")
        for item_name in suggestion["items"]:
            assert_true(str(item_name) in basket_names, f"{label} meal_suggestion item comes from basket")
        normalized.append((str(suggestion["meal_type"]), tuple(str(item) for item in suggestion["items"])))
    return tuple(normalized)


def verify_store_fit_metadata(label: str, payload: dict[str, Any], stores: list[dict[str, Any]]) -> tuple[str, ...]:
    store_ids = {str(store["store_id"]) for store in stores}
    order = payload.get("recommended_store_order")
    notes = payload.get("store_fit_notes")
    assert_true(isinstance(order, list), f"{label} recommended_store_order list")
    assert_true(isinstance(notes, list), f"{label} store_fit_notes list")
    assert_true(len(order) >= 1, f"{label} recommended_store_order non-empty")
    assert_true(len(notes) >= 1, f"{label} store_fit_notes non-empty")
    assert_true(set(str(store_id) for store_id in order).issubset(store_ids), f"{label} store order uses nearby stores")
    assert_equal(str(notes[0]["store_id"]), str(order[0]), f"{label} top note matches top ordered store")

    note_ids: list[str] = []
    for note in notes:
        assert_equal(
            set(note.keys()),
            {"store_id", "store_name", "category", "distance_m", "fit_label", "note"},
            f"{label} store_fit_note keys",
        )
        assert_true(str(note["store_id"]) in store_ids, f"{label} store_fit_note store is nearby")
        assert_true(bool(note["store_name"]), f"{label} store_fit_note name present")
        assert_true(bool(note["fit_label"]), f"{label} store_fit_note fit_label present")
        assert_true(bool(note["note"]), f"{label} store_fit_note note present")
        note_ids.append(str(note["store_id"]))

    grouped_ids: list[str] = []
    for field_name in ("one_stop_pick", "budget_pick", "produce_pick", "bulk_pick"):
        grouped_pick = payload.get(field_name)
        if grouped_pick is None:
            continue
        assert_true(isinstance(grouped_pick, dict), f"{label} {field_name} object")
        assert_equal(set(grouped_pick.keys()), EXPECTED_GROUPED_STORE_PICK_KEYS, f"{label} {field_name} keys")
        assert_true(str(grouped_pick["store_id"]) in store_ids, f"{label} {field_name} store is nearby")
        assert_true(bool(grouped_pick["store_name"]), f"{label} {field_name} name present")
        assert_true(bool(grouped_pick["note"]), f"{label} {field_name} note present")
        grouped_ids.append(f"{field_name}:{grouped_pick['store_id']}")
    return tuple(note_ids + grouped_ids)


def run_recommendation_scenarios() -> list[str]:
    app = create_app()
    client = app.test_client()
    name_to_id = load_name_to_id()
    scenario_labels: list[str] = []

    def stub_nearby_stores(_con: duckdb.DuckDBPyConnection, *, limit: int, **_kwargs: object) -> list[dict[str, object]]:
        return STUB_STORES[:limit]

    with patched_attr(app_module, "nearby_stores", stub_nearby_stores):
        for label, payload, forbidden_ids, preferred_ids in scenario_payloads():
            first = client.post("/api/recommendations/generic", json=payload)
            second = client.post("/api/recommendations/generic", json=payload)
            assert_equal(first.status_code, 200, f"{label} status")
            assert_equal(second.status_code, 200, f"{label} repeat status")

            first_json = first.get_json()
            second_json = second.get_json()
            assert_true(isinstance(first_json, dict), f"{label} first json object")
            assert_true(isinstance(second_json, dict), f"{label} second json object")
            assert_equal(first_json["stores"], STUB_STORES[: payload["store_limit"]], f"{label} store payload")
            assert_equal(second_json["stores"], STUB_STORES[: payload["store_limit"]], f"{label} repeated store payload")
            assert_true(isinstance(first_json.get("unpriced_item_count"), int), f"{label} unpriced_item_count present")
            if "estimated_basket_cost" in first_json:
                assert_true(float(first_json["estimated_basket_cost"]) > 0, f"{label} estimated basket cost positive")
                assert_true(float(second_json["estimated_basket_cost"]) > 0, f"{label} repeated estimated basket cost positive")
                assert_true(bool(first_json.get("price_area_code")), f"{label} price_area_code present")
                assert_true(bool(first_json.get("price_area_name")), f"{label} price_area_name present")
                assert_true(bool(first_json.get("price_source_note")), f"{label} price_source_note present")
                assert_true(bool(first_json.get("price_confidence_note")), f"{label} price_confidence_note present")
                assert_true(isinstance(first_json.get("usda_priced_item_count"), int), f"{label} usda_priced_item_count present")
                assert_true(isinstance(first_json.get("bls_priced_item_count"), int), f"{label} bls_priced_item_count present")
                assert_true(bool(first_json.get("price_coverage_note")), f"{label} price_coverage_note present")
                if int(first_json["usda_priced_item_count"]) > 0:
                    assert_true(bool(first_json.get("price_adjustment_note")), f"{label} price_adjustment_note present for USDA pricing")
                assert_equal(
                    int(first_json["priced_item_count"]) + int(first_json["unpriced_item_count"]),
                    len(first_json["shopping_list"]),
                    f"{label} priced and unpriced counts cover basket",
                )
                assert_equal(
                    int(first_json["usda_priced_item_count"]) + int(first_json["bls_priced_item_count"]),
                    int(first_json["priced_item_count"]),
                    f"{label} USDA and BLS priced counts cover priced items",
                )
                assert_true(
                    isinstance(first_json.get("basket_cost_note"), str) and bool(first_json["basket_cost_note"]),
                    f"{label} basket_cost_note present",
                )
                estimated_total = round(
                    sum(float(item["estimated_item_cost"]) for item in first_json["shopping_list"] if item["estimated_item_cost"] is not None),
                    2,
                )
                assert_true(
                    abs(float(first_json["estimated_basket_cost"]) - estimated_total) <= 0.01,
                    f"{label} estimated basket cost matches priced items",
                )
                assert_equal(
                    float(first_json["typical_basket_cost"]),
                    float(first_json["estimated_basket_cost"]),
                    f"{label} typical_basket_cost mirrors estimated_basket_cost",
                )
                if "estimated_basket_cost_low" in first_json and "estimated_basket_cost_high" in first_json:
                    assert_true(
                        float(first_json["estimated_basket_cost_low"]) <= float(first_json["estimated_basket_cost"]),
                        f"{label} basket low <= basket cost",
                    )
                    assert_true(
                        float(first_json["estimated_basket_cost_high"]) >= float(first_json["estimated_basket_cost"]),
                        f"{label} basket high >= basket cost",
                    )

            first_ids = verify_shopping_list(label, first_json["shopping_list"], name_to_id, forbidden_ids, preferred_ids)
            second_ids = verify_shopping_list(f"{label} repeat", second_json["shopping_list"], name_to_id, forbidden_ids, preferred_ids)
            first_meal_suggestions = verify_meal_suggestions(label, first_json, first_json["shopping_list"])
            second_meal_suggestions = verify_meal_suggestions(f"{label} repeat", second_json, second_json["shopping_list"])
            first_store_fit = verify_store_fit_metadata(label, first_json, first_json["stores"])
            second_store_fit = verify_store_fit_metadata(f"{label} repeat", second_json, second_json["stores"])
            assert_equal(first_ids, second_ids, f"{label} deterministic item ids")
            assert_equal(
                [item["role"] for item in first_json["shopping_list"]],
                [item["role"] for item in second_json["shopping_list"]],
                f"{label} deterministic roles",
            )
            assert_equal(first_meal_suggestions, second_meal_suggestions, f"{label} deterministic meal suggestions")
            assert_equal(first_store_fit, second_store_fit, f"{label} deterministic store fit")
            scenario_labels.append(label)

    def unexpected_nearby_stores(_con: duckdb.DuckDBPyConnection, **_kwargs: object) -> list[dict[str, object]]:
        raise AssertionError("recommendation request should have reused the provided nearby-store snapshot")

    reuse_payload = {
        "location": {"lat": 37.3861, "lon": -122.0839},
        "targets": {"protein": 130, "energy_fibre_kcal": 2100},
        "preferences": {"vegetarian": False, "dairy_free": False},
        "store_limit": 2,
        "stores": STUB_STORES[:2],
    }
    with patched_attr(app_module, "nearby_stores", unexpected_nearby_stores):
        reused = client.post("/api/recommendations/generic", json=reuse_payload)
        assert_equal(reused.status_code, 200, "store snapshot reuse status")
        reused_json = reused.get_json()
        assert_equal(reused_json["stores"], STUB_STORES[:2], "store snapshot reuse payload")
        scenario_labels.append("store_snapshot_reuse")

    return scenario_labels


def run_price_consistency_scenario() -> list[str]:
    app = create_app()
    client = app.test_client()
    price_meta = load_price_meta()

    def stub_nearby_stores(_con: duckdb.DuckDBPyConnection, *, limit: int, **_kwargs: object) -> list[dict[str, object]]:
        return STUB_STORES[:limit]

    breakfast_payload = {
        "location": {"lat": 37.3861, "lon": -122.0839},
        "targets": {"protein": 100, "energy_fibre_kcal": 1900},
        "preferences": {"meal_style": "breakfast"},
        "store_limit": 2,
    }
    lunch_payload = {
        "location": {"lat": 37.3861, "lon": -122.0839},
        "targets": {"protein": 120, "energy_fibre_kcal": 2100, "carbohydrate": 230, "fiber": 35},
        "preferences": {"meal_style": "lunch_dinner", "budget_friendly": True},
        "store_limit": 2,
    }

    with patched_attr(app_module, "nearby_stores", stub_nearby_stores):
        breakfast = client.post("/api/recommendations/generic", json=breakfast_payload).get_json()
        lunch = client.post("/api/recommendations/generic", json=lunch_payload).get_json()

    breakfast_items = {item["generic_food_id"]: item for item in breakfast["shopping_list"]}
    lunch_items = {item["generic_food_id"]: item for item in lunch["shopping_list"]}

    eggs = breakfast_items["eggs"]
    eggs_meta = price_meta["eggs"]
    if eggs["price_source_used"] == "usda_area":
        expected_eggs_cost = round(float(eggs["estimated_unit_price"]) * (float(eggs["quantity_g"]) / 100.0), 2)
        assert_equal(eggs["price_unit_display"], "per 100 g", "price consistency eggs unit")
    else:
        expected_eggs_cost = round(
            float(eggs["estimated_unit_price"]) * (float(eggs["quantity_g"]) / float(eggs_meta["purchase_unit_size_g"])),
            2,
        )
        assert_equal(eggs["price_unit_display"], "per dozen", "price consistency eggs unit")
    assert_true("eggs" in str(eggs["quantity_display"]).lower(), "price consistency eggs display")
    assert_true(abs(float(eggs["estimated_item_cost"]) - expected_eggs_cost) <= 0.02, "price consistency eggs cost")

    yogurt = breakfast_items["protein_yogurt"]
    yogurt_meta = price_meta["protein_yogurt"]
    if yogurt["price_source_used"] == "usda_area":
        expected_yogurt_cost = round(float(yogurt["estimated_unit_price"]) * (float(yogurt["quantity_g"]) / 100.0), 2)
        assert_equal(yogurt["price_unit_display"], "per 100 g", "price consistency yogurt unit")
    else:
        expected_yogurt_cost = round(
            float(yogurt["estimated_unit_price"]) * (float(yogurt["quantity_g"]) / float(yogurt_meta["price_basis_value"])),
            2,
        )
        assert_equal(yogurt["price_unit_display"], "per 8 oz", "price consistency yogurt unit")
    assert_true(abs(float(yogurt["estimated_item_cost"]) - expected_yogurt_cost) <= 0.02, "price consistency yogurt cost")

    rice = lunch_items["rice"]
    rice_meta = price_meta["rice"]
    if rice["price_source_used"] == "usda_area":
        expected_rice_cost = round(float(rice["estimated_unit_price"]) * (float(rice["quantity_g"]) / 100.0), 2)
        assert_equal(rice["price_unit_display"], "per 100 g", "price consistency rice unit")
    else:
        expected_rice_cost = round(
            float(rice["estimated_unit_price"]) * (float(rice["quantity_g"]) / float(rice_meta["price_basis_value"])),
            2,
        )
        assert_equal(rice["price_unit_display"], "per lb", "price consistency rice unit")
    assert_true(abs(float(rice["estimated_item_cost"]) - expected_rice_cost) <= 0.06, "price consistency rice cost")
    assert_true(
        "bag" not in str(rice["quantity_display"]).lower() or float(rice["quantity_g"]) >= float(rice_meta["purchase_unit_size_g"]) * 0.75,
        "price consistency rice display avoids misleading full-bag rounding",
    )
    return ["price_consistency"]


def run_price_area_scenario() -> list[str]:
    app = create_app()
    client = app.test_client()

    west_stores = [
        {
            **STUB_STORES[0],
            "address": "123 Demo St, Mountain View, CA 94041",
        }
    ]
    northeast_stores = [
        {
            **STUB_STORES[0],
            "address": "123 Demo St, New York, NY 10001",
        }
    ]

    payload = {
        "location": {"lat": 37.3861, "lon": -122.0839},
        "targets": {"protein": 120, "energy_fibre_kcal": 2100},
        "preferences": {"meal_style": "lunch_dinner"},
        "store_limit": 1,
    }

    with patched_attr(app_module, "nearby_stores", lambda _con, *, limit, **_kwargs: west_stores[:limit]):
        west = client.post("/api/recommendations/generic", json=payload).get_json()
    with patched_attr(app_module, "nearby_stores", lambda _con, *, limit, **_kwargs: northeast_stores[:limit]):
        northeast = client.post("/api/recommendations/generic", json=payload).get_json()

    assert_equal(west["price_area_code"], "WEST", "price area west code")
    assert_equal(west["price_area_name"], "West", "price area west name")
    assert_true("West" in west["price_source_note"], "price area west note")
    assert_equal(northeast["price_area_code"], "NEW_YORK", "price area northeast code")
    assert_equal(northeast["price_area_name"], "New York", "price area northeast name")
    assert_true("New York" in northeast["price_source_note"], "price area northeast note")
    return ["price_area"]


def run_price_aware_budget_scenario() -> list[str]:
    app = create_app()
    client = app.test_client()

    west_stores = [
        {
            **STUB_STORES[0],
            "address": "123 Demo St, Mountain View, CA 94041",
        }
    ]
    payload = {
        "location": {"lat": 37.3861, "lon": -122.0839},
        "targets": {"protein": 110, "energy_fibre_kcal": 2100},
        "preferences": {"budget_friendly": True, "meal_style": "lunch_dinner"},
        "store_limit": 1,
    }

    original_load_candidates = recommender_module._load_candidates

    def no_price_candidates(
        con: duckdb.DuckDBPyConnection,
        vegetarian: bool,
        dairy_free: bool,
        vegan: bool,
        price_area_code: str = "0",
        usda_area_code: str = "US",
    ) -> dict[str, dict[str, object]]:
        rows = original_load_candidates(
            con,
            vegetarian=vegetarian,
            dairy_free=dairy_free,
            vegan=vegan,
            price_area_code=price_area_code,
            usda_area_code=usda_area_code,
        )
        stripped: dict[str, dict[str, object]] = {}
        for food_id, row in rows.items():
            stripped_row = dict(row)
            for field_name in (
                "bls_estimated_unit_price",
                "price_unit_display",
                "price_basis_kind",
                "price_basis_value",
                "bls_item_name",
                "bls_price_year",
                "bls_price_period",
                "bls_price_area_code",
                "regional_price_low",
                "regional_price_high",
                "regional_price_area_count",
                "price_reference_source",
                "usda_base_observed_at",
                "cpi_base_observed_at",
                "cpi_current_observed_at",
                "cpi_base_value",
                "cpi_current_value",
                "usda_inflation_multiplier",
                "_price_efficiency_signals",
            ):
                stripped_row[field_name] = None
            stripped[food_id] = stripped_row
        return stripped

    with patched_attr(app_module, "nearby_stores", lambda _con, *, limit, **_kwargs: west_stores[:limit]):
        priced_response = client.post("/api/recommendations/generic", json=payload)
        assert_equal(priced_response.status_code, 200, "price aware budget priced status")
        priced_body = priced_response.get_json()

        with patched_attr(recommender_module, "_load_candidates", no_price_candidates):
            unpriced_response = client.post("/api/recommendations/generic", json=payload)
        assert_equal(unpriced_response.status_code, 200, "price aware budget unpriced status")
        unpriced_body = unpriced_response.get_json()

    priced_ids = tuple(item["generic_food_id"] for item in priced_body["shopping_list"])
    unpriced_ids = tuple(item["generic_food_id"] for item in unpriced_body["shopping_list"])
    assert_true("estimated_basket_cost" in priced_body, "price aware budget priced basket cost present")
    assert_true("estimated_basket_cost" not in unpriced_body, "price aware budget unpriced basket cost omitted")
    assert_true(
        {"lentils", "beans", "rice"} & set(priced_ids),
        "price aware budget keeps at least one cheap staple in the priced basket",
    )
    assert_true(
        {"lentils", "beans", "rice"} & set(unpriced_ids),
        "price aware budget keeps at least one cheap staple in the unpriced basket",
    )
    priced_value_notes = [item["value_reason_short"] for item in priced_body["shopping_list"] if item["value_reason_short"]]
    unpriced_value_notes = [item["value_reason_short"] for item in unpriced_body["shopping_list"] if item["value_reason_short"]]
    assert_true(bool(priced_value_notes), "price aware budget has at least one value explanation")
    assert_true(not unpriced_value_notes, "price aware budget unpriced basket omits value explanations")
    assert_true(
        any(
            note in {
                "High protein per dollar",
                "Low-cost calorie base",
                "Good carbs per dollar",
                "Affordable fiber source",
                "Good vitamin C value",
                "Budget-friendly staple",
                "Low-cost calorie booster",
            }
            for note in priced_value_notes
        ),
        "price aware budget uses expected value explanation labels",
    )
    return ["price_aware_budget"]


def run_usda_price_layer_scenario() -> list[str]:
    app = create_app()
    client = app.test_client()

    west_stores = [
        {
            **STUB_STORES[0],
            "address": "123 Demo St, Mountain View, CA 94041",
        }
    ]
    payload = {
        "location": {"lat": 37.3861, "lon": -122.0839},
        "targets": {"protein": 120, "energy_fibre_kcal": 2100},
        "preferences": {"budget_friendly": True, "meal_style": "lunch_dinner"},
        "store_limit": 1,
    }

    original_load_candidates = recommender_module._load_candidates

    def mixed_price_candidates(
        con: duckdb.DuckDBPyConnection,
        vegetarian: bool,
        dairy_free: bool,
        vegan: bool,
        price_area_code: str = "0",
        usda_area_code: str = "US",
    ) -> dict[str, dict[str, object]]:
        rows = original_load_candidates(
            con,
            vegetarian=vegetarian,
            dairy_free=dairy_free,
            vegan=vegan,
            price_area_code=price_area_code,
            usda_area_code=usda_area_code,
        )
        for food_id in ("rice", "broccoli"):
            if food_id not in rows:
                continue
            row = dict(rows[food_id])
            row["bls_estimated_unit_price"] = 0.95 if food_id == "rice" else 1.2
            row["price_unit_display"] = "per 100 g"
            row["price_basis_kind"] = "weight_g"
            row["price_basis_value"] = 100.0
            row["regional_price_low"] = 0.82 if food_id == "rice" else 1.05
            row["regional_price_high"] = 1.08 if food_id == "rice" else 1.35
            row["regional_price_area_count"] = 3
            row["price_reference_source"] = "usda_area"
            row["bls_price_area_code"] = "WEST"
            row["cpi_base_observed_at"] = "2018-12"
            row["cpi_current_observed_at"] = "2026-02"
            row["usda_inflation_multiplier"] = 1.27
            rows[food_id] = row
        return rows

    with patched_attr(app_module, "nearby_stores", lambda _con, *, limit, **_kwargs: west_stores[:limit]):
        with patched_attr(recommender_module, "_load_candidates", mixed_price_candidates):
            response = client.post("/api/recommendations/generic", json=payload)

    assert_equal(response.status_code, 200, "usda_price_layer status")
    body = response.get_json()
    assert_true(int(body["usda_priced_item_count"]) >= 1, "usda_price_layer USDA count present")
    assert_true("USDA" in body["price_source_note"], "usda_price_layer note mentions USDA")
    assert_true("USDA" in body["price_coverage_note"], "usda_price_layer coverage note mentions USDA")
    assert_true("2018-12" in body["price_adjustment_note"], "usda_price_layer adjustment note mentions base period")
    assert_true("2026-02" in body["price_adjustment_note"], "usda_price_layer adjustment note mentions current period")
    if int(body["bls_priced_item_count"]) > 0:
        assert_true("BLS" in body["price_source_note"], "usda_price_layer note mentions BLS when fallback is used")
    assert_true(any(item["price_source_used"] == "usda_area" for item in body["shopping_list"]), "usda_price_layer item source used")
    return ["usda_price_layer"]


def run_multi_day_scaling_scenario() -> list[str]:
    app = create_app()
    client = app.test_client()

    def stub_nearby_stores(_con: duckdb.DuckDBPyConnection, *, limit: int, **_kwargs: object) -> list[dict[str, object]]:
        return STUB_STORES[:limit]

    one_day_payload = {
        "location": {"lat": 37.3861, "lon": -122.0839},
        "targets": {"protein": 130, "energy_fibre_kcal": 2100},
        "preferences": {"meal_style": "lunch_dinner"},
        "store_limit": 2,
        "days": 1,
    }
    three_day_payload = {**one_day_payload, "days": 3}

    with patched_attr(app_module, "nearby_stores", stub_nearby_stores):
        one_day_resp = client.post("/api/recommendations/generic", json=one_day_payload)
        three_day_resp = client.post("/api/recommendations/generic", json=three_day_payload)

    assert_equal(one_day_resp.status_code, 200, "multi_day one-day status")
    assert_equal(three_day_resp.status_code, 200, "multi_day three-day status")

    one_day = one_day_resp.get_json()
    three_day = three_day_resp.get_json()
    assert_equal(one_day["days"], 1, "multi_day one-day response days")
    assert_equal(three_day["days"], 3, "multi_day three-day response days")

    one_day_items = one_day["shopping_list"]
    three_day_items = three_day["shopping_list"]
    assert_equal(
        [item["role"] for item in one_day_items],
        [item["role"] for item in three_day_items],
        "multi_day stable roles",
    )
    one_day_by_food_id = {str(item["generic_food_id"]): item for item in one_day_items}
    three_day_by_food_id = {str(item["generic_food_id"]): item for item in three_day_items}
    shared_food_ids = sorted(set(one_day_by_food_id) & set(three_day_by_food_id))
    assert_true(len(shared_food_ids) >= max(3, len(one_day_items) - 2), "multi_day shared item ids")

    for food_id in shared_food_ids:
        one_item = one_day_by_food_id[food_id]
        three_item = three_day_by_food_id[food_id]
        ratio = float(three_item["quantity_g"]) / max(float(one_item["quantity_g"]), 1.0)
        upper_bound = 5.0 if str(one_item["role"]) == "calorie_booster" else 4.5
        assert_true(2.0 <= ratio <= upper_bound, f"multi_day scaled quantity for {one_item['generic_food_id']}")

    assert_equal(
        three_day["nutrition_summary"]["protein_target_g"],
        round(one_day["nutrition_summary"]["protein_target_g"] * 3, 1),
        "multi_day scaled protein target",
    )
    assert_equal(
        three_day["nutrition_summary"]["calorie_target_kcal"],
        round(one_day["nutrition_summary"]["calorie_target_kcal"] * 3, 1),
        "multi_day scaled calorie target",
    )
    return ["multi_day_scaling"]


def run_shopping_mode_scenario() -> list[str]:
    app = create_app()
    client = app.test_client()

    def stub_nearby_stores(_con: duckdb.DuckDBPyConnection, *, limit: int, **_kwargs: object) -> list[dict[str, object]]:
        return STUB_STORES[:limit]

    fresh_payload = {
        "location": {"lat": 37.3861, "lon": -122.0839},
        "targets": {"protein": 130, "energy_fibre_kcal": 2100},
        "preferences": {"meal_style": "lunch_dinner"},
        "store_limit": 2,
        "days": 7,
        "shopping_mode": "fresh",
    }
    bulk_payload = {**fresh_payload, "shopping_mode": "bulk"}

    with patched_attr(app_module, "nearby_stores", stub_nearby_stores):
        fresh_resp = client.post("/api/recommendations/generic", json=fresh_payload)
        bulk_resp = client.post("/api/recommendations/generic", json=bulk_payload)

    assert_equal(fresh_resp.status_code, 200, "shopping_mode fresh status")
    assert_equal(bulk_resp.status_code, 200, "shopping_mode bulk status")

    fresh = fresh_resp.get_json()
    bulk = bulk_resp.get_json()
    assert_equal(fresh["shopping_mode"], "fresh", "shopping_mode fresh response")
    assert_equal(bulk["shopping_mode"], "bulk", "shopping_mode bulk response")
    assert_true(isinstance(fresh.get("adjusted_by_split"), bool), "shopping_mode fresh adjusted_by_split bool")
    assert_true(isinstance(bulk.get("adjusted_by_split"), bool), "shopping_mode bulk adjusted_by_split bool")
    assert_true(isinstance(fresh.get("scaling_notes", []), list), "shopping_mode fresh scaling_notes list")
    assert_true(isinstance(bulk.get("scaling_notes", []), list), "shopping_mode bulk scaling_notes list")
    assert_true(isinstance(fresh.get("warnings", []), list), "shopping_mode fresh warnings list")
    assert_true(isinstance(bulk.get("warnings", []), list), "shopping_mode bulk warnings list")
    assert_true(isinstance(fresh.get("split_notes", []), list), "shopping_mode fresh split_notes list")
    assert_true(isinstance(bulk.get("split_notes", []), list), "shopping_mode bulk split_notes list")
    assert_true(isinstance(fresh.get("realism_notes", []), list), "shopping_mode fresh realism_notes list")
    assert_true(isinstance(bulk.get("realism_notes", []), list), "shopping_mode bulk realism_notes list")

    fresh_items = fresh["shopping_list"]
    bulk_items = bulk["shopping_list"]
    assert_true(len(fresh_items) >= 4, "shopping_mode fresh non-trivial shopping list")
    assert_true(len(bulk_items) >= 4, "shopping_mode bulk non-trivial shopping list")

    def role_total(payload: dict[str, Any], role: str) -> float:
        return sum(float(item["quantity_g"]) for item in payload["shopping_list"] if item["role"] == role)

    assert_true(
        role_total(fresh, "produce") <= role_total(bulk, "produce"),
        "shopping_mode fresh softens perishable produce quantity",
    )
    assert_true(
        role_total(fresh, "carb_base") != role_total(bulk, "carb_base"),
        "shopping_mode changes pantry-item quantity behavior",
    )
    return ["shopping_mode"]


def run_result_realism_scenario() -> list[str]:
    app = create_app()
    client = app.test_client()

    def stub_nearby_stores(_con: duckdb.DuckDBPyConnection, *, limit: int, **_kwargs: object) -> list[dict[str, object]]:
        return STUB_STORES[:limit]

    payload = {
        "location": {"lat": 37.3861, "lon": -122.0839},
        "targets": {"protein": 130, "energy_fibre_kcal": 2100},
        "preferences": {"meal_style": "lunch_dinner"},
        "store_limit": 2,
        "days": 7,
        "shopping_mode": "fresh",
    }

    with patched_attr(app_module, "nearby_stores", stub_nearby_stores):
        response = client.post("/api/recommendations/generic", json=payload)

    assert_equal(response.status_code, 200, "result_realism status")
    body = response.get_json()
    assert_true(isinstance(body.get("adjusted_by_split"), bool), "result_realism adjusted_by_split bool")
    assert_true(isinstance(body.get("split_notes", []), list), "result_realism split_notes list")
    assert_true(isinstance(body.get("realism_notes", []), list), "result_realism realism_notes list")
    assert_true(body["adjusted_by_split"], "result_realism split triggered")
    assert_true(len(body.get("split_notes", [])) >= 1, "result_realism split note present")
    assert_true(len(body.get("realism_notes", [])) >= 1, "result_realism realism note present")

    role_counts: dict[str, int] = {}
    for item in body["shopping_list"]:
        role_counts[item["role"]] = role_counts.get(item["role"], 0) + 1
    assert_true(role_counts.get("produce", 0) >= 2, "result_realism keeps produce diversity")
    assert_true(
        role_counts.get("protein_anchor", 0) >= 2,
        "result_realism keeps at least two protein anchors for longer windows",
    )
    return ["result_realism"]


def run_diversity_scenario() -> list[str]:
    app = create_app()
    client = app.test_client()

    def stub_nearby_stores(_con: duckdb.DuckDBPyConnection, *, limit: int, **_kwargs: object) -> list[dict[str, object]]:
        return STUB_STORES[:limit]

    payloads = {
        "balanced": {
            "location": {"lat": 37.3861, "lon": -122.0839},
            "targets": {"protein": 130, "energy_fibre_kcal": 2100},
            "preferences": {},
            "store_limit": 2,
        },
        "breakfast": {
            "location": {"lat": 37.3861, "lon": -122.0839},
            "targets": {"protein": 100, "energy_fibre_kcal": 1900},
            "preferences": {"meal_style": "breakfast"},
            "store_limit": 2,
        },
        "snack": {
            "location": {"lat": 37.3861, "lon": -122.0839},
            "targets": {"protein": 95, "energy_fibre_kcal": 1800},
            "preferences": {"meal_style": "snack"},
            "store_limit": 2,
        },
        "vegetarian": {
            "location": {"lat": 37.3861, "lon": -122.0839},
            "targets": {"protein": 120, "energy_fibre_kcal": 2000},
            "preferences": {"vegetarian": True},
            "store_limit": 2,
        },
        "budget_friendly": {
            "location": {"lat": 37.3861, "lon": -122.0839},
            "targets": {"protein": 110, "energy_fibre_kcal": 2100},
            "preferences": {"budget_friendly": True},
            "store_limit": 2,
        },
    }

    with patched_attr(app_module, "nearby_stores", stub_nearby_stores):
        responses = {
            label: client.post("/api/recommendations/generic", json=payload).get_json()
            for label, payload in payloads.items()
        }

    baskets = {
        label: tuple(item["generic_food_id"] for item in body["shopping_list"])
        for label, body in responses.items()
    }
    produce_by_scenario = {
        label: [item["generic_food_id"] for item in body["shopping_list"] if item["role"] == "produce"]
        for label, body in responses.items()
    }
    carbs_by_scenario = {
        label: [item["generic_food_id"] for item in body["shopping_list"] if item["role"] == "carb_base"]
        for label, body in responses.items()
    }

    breakfast_produce_ids = {"bananas", "apples", "oranges", "berries", "grapes", "pears", "kiwi", "pineapple", "mango"}
    snack_produce_ids = breakfast_produce_ids | {"carrots", "cucumber", "celery", "tomatoes", "lettuce", "bell_peppers"}
    lunch_dinner_produce_ids = {
        "broccoli",
        "spinach",
        "kale",
        "brussels_sprouts",
        "green_beans",
        "frozen_vegetables",
        "bell_peppers",
        "cauliflower",
        "cabbage",
        "carrots",
        "zucchini",
        "asparagus",
        "mushrooms",
        "peas",
        "tomatoes",
        "cucumber",
        "sweet_potatoes",
        "potatoes",
        "lettuce",
        "celery",
    }
    breakfast_carb_ids = {"oats", "corn_flakes", "bagel", "wholemeal_bread", "pita"}
    budget_carb_ids = {"oats", "rice", "pasta", "barley", "wholemeal_bread", "potatoes", "sweet_potatoes", "beans", "lentils", "couscous"}

    assert_true(baskets["breakfast"] != baskets["balanced"], "diversity breakfast differs from balanced")
    assert_true(baskets["snack"] != baskets["balanced"], "diversity snack differs from balanced")
    assert_true(baskets["vegetarian"] != baskets["balanced"], "diversity vegetarian differs from balanced")
    assert_true(baskets["budget_friendly"] != baskets["balanced"], "diversity budget differs from balanced")
    assert_true(baskets["breakfast"] != baskets["snack"], "diversity breakfast differs from snack")

    assert_true(
        any(food_id in breakfast_produce_ids for food_id in produce_by_scenario["breakfast"]),
        "diversity breakfast produce is fruit-oriented",
    )
    assert_true(
        any(food_id in snack_produce_ids for food_id in produce_by_scenario["snack"]),
        "diversity snack produce is portable or low-prep",
    )
    assert_true(
        any(food_id in lunch_dinner_produce_ids for food_id in produce_by_scenario["balanced"]),
        "diversity balanced produce includes vegetable-oriented option",
    )
    assert_true(
        not any(food_id in lunch_dinner_produce_ids for food_id in produce_by_scenario["breakfast"]),
        "diversity breakfast produce is not dominated by lunch vegetables",
    )
    assert_true(
        carbs_by_scenario["breakfast"] and carbs_by_scenario["breakfast"][0] in breakfast_carb_ids,
        "diversity breakfast carb base is breakfast-friendly",
    )
    assert_true(
        carbs_by_scenario["budget_friendly"] and carbs_by_scenario["budget_friendly"][0] in budget_carb_ids,
        "diversity budget carb base is a staple-friendly option",
    )
    assert_true(
        carbs_by_scenario["breakfast"] != carbs_by_scenario["budget_friendly"],
        "diversity breakfast and budget carb bases differ",
    )
    return ["diversity"]


def run_preference_overlap_scenario() -> list[str]:
    app = create_app()
    client = app.test_client()
    food_meta = load_food_meta()

    def stub_nearby_stores(_con: duckdb.DuckDBPyConnection, *, limit: int, **_kwargs: object) -> list[dict[str, object]]:
        return STUB_STORES[:limit]

    payloads = {
        "base": {
            "location": {"lat": 37.3861, "lon": -122.0839},
            "targets": {"protein": 130, "energy_fibre_kcal": 2200, "carbohydrate": 240, "fat": 70, "fiber": 30},
            "preferences": {"meal_style": "lunch_dinner"},
            "store_limit": 2,
        },
        "budget": {
            "location": {"lat": 37.3861, "lon": -122.0839},
            "targets": {"protein": 130, "energy_fibre_kcal": 2200, "carbohydrate": 240, "fat": 70, "fiber": 30},
            "preferences": {"meal_style": "lunch_dinner", "budget_friendly": True},
            "store_limit": 2,
        },
        "vegan": {
            "location": {"lat": 37.3861, "lon": -122.0839},
            "targets": {"protein": 125, "energy_fibre_kcal": 2200, "carbohydrate": 245, "fat": 68, "fiber": 36},
            "preferences": {"meal_style": "any", "vegan": True},
            "store_limit": 2,
        },
    }

    with patched_attr(app_module, "nearby_stores", stub_nearby_stores):
        responses = {
            label: client.post("/api/recommendations/generic", json=payload).get_json()
            for label, payload in payloads.items()
        }

    baskets = {
        label: [str(item["generic_food_id"]) for item in body["shopping_list"]]
        for label, body in responses.items()
    }

    def jaccard(left: list[str], right: list[str]) -> float:
        left_ids = set(left)
        right_ids = set(right)
        union = left_ids | right_ids
        if not union:
            return 0.0
        return len(left_ids & right_ids) / len(union)

    budget_staples = {
        "lentils",
        "beans",
        "black_beans",
        "chickpeas",
        "eggs",
        "tofu",
        "peanut_butter",
        "oats",
        "rice",
        "pasta",
        "potatoes",
        "wholemeal_bread",
        "bananas",
        "apples",
        "carrots",
        "cabbage",
        "lettuce",
        "onions",
        "frozen_vegetables",
        "olive_oil",
    }

    def budget_staple_count(body: dict[str, Any]) -> int:
        return sum(
            1
            for item in body["shopping_list"]
            if str(item["generic_food_id"]) in budget_staples or float(food_meta[str(item["generic_food_id"])]["budget_score"]) >= 4.0
        )

    base_overlap_budget = jaccard(baskets["base"], baskets["budget"])
    base_overlap_vegan = jaccard(baskets["base"], baskets["vegan"])
    assert_true(base_overlap_budget <= 0.35, "preference overlap base-budget materially reduced")
    assert_true(base_overlap_vegan <= 0.5, "preference overlap base-vegan materially reduced")
    assert_true(len(set(baskets["base"]) ^ set(baskets["budget"])) >= 4, "preference overlap budget differs by at least two foods")
    assert_true(len(set(baskets["base"]) ^ set(baskets["vegan"])) >= 4, "preference overlap vegan differs by at least two foods")

    base_budget_staples = budget_staple_count(responses["base"])
    budget_budget_staples = budget_staple_count(responses["budget"])
    assert_true(budget_budget_staples >= base_budget_staples + 1, "preference overlap budget increases staple count")
    assert_true(
        float(responses["budget"]["estimated_basket_cost"]) <= float(responses["base"]["estimated_basket_cost"]) + 0.25,
        "preference overlap budget keeps cost sensible",
    )

    for label, body in responses.items():
        summary = body["nutrition_summary"]
        protein_gap = abs(float(summary["protein_estimated_g"]) - float(summary["protein_target_g"]))
        calorie_gap = abs(float(summary["calorie_estimated_kcal"]) - float(summary["calorie_target_kcal"]))
        assert_true(protein_gap <= 25.0, f"{label} preference overlap protein gap acceptable")
        assert_true(calorie_gap <= (380.0 if label == "budget" else 300.0), f"{label} preference overlap calorie gap acceptable")

    vegan_ids = set(baskets["vegan"])
    assert_true(
        not bool(vegan_ids & {"eggs", "milk", "greek_yogurt", "cheese", "cottage_cheese", "protein_yogurt", "tuna", "chicken_breast"}),
        "preference overlap vegan excludes animal foods",
    )
    vegan_unique_ids = vegan_ids - set(baskets["base"])
    vegan_unique_items = [
        item
        for item in responses["vegan"]["shopping_list"]
        if str(item["generic_food_id"]) in vegan_unique_ids
    ]
    assert_true(
        any(
            str(item["generic_food_id"]) in {"tofu", "lentils", "beans", "black_beans", "chickpeas", "oats"}
            for item in vegan_unique_items
        ),
        "preference overlap vegan unique items reflect plant-based substitutions",
    )

    budget_unique_ids = set(baskets["budget"]) - set(baskets["base"])
    budget_unique_items = [
        item
        for item in responses["budget"]["shopping_list"]
        if str(item["generic_food_id"]) in budget_unique_ids
    ]
    assert_true(
        any(
            "lower-cost staple" in str(item["why_selected"]).lower()
            or "budget-friendly" in str(item["reason_short"]).lower()
            for item in budget_unique_items
        ),
        "preference overlap budget explanations reflect lower-cost substitutions",
    )
    return ["preference_overlap"]


def run_goal_policy_scenario() -> list[str]:
    app = create_app()
    client = app.test_client()

    def stub_nearby_stores(_con: duckdb.DuckDBPyConnection, *, limit: int, **_kwargs: object) -> list[dict[str, object]]:
        return STUB_STORES[:limit]

    payloads = {
        "muscle_gain": {
            "location": {"lat": 37.3861, "lon": -122.0839},
            "targets": {"protein": 170, "energy_fibre_kcal": 2800, "carbohydrate": 330, "fat": 85, "fiber": 35},
            "preferences": {},
            "store_limit": 2,
        },
        "fat_loss": {
            "location": {"lat": 37.3861, "lon": -122.0839},
            "targets": {"protein": 150, "energy_fibre_kcal": 1800, "carbohydrate": 160, "fat": 55, "fiber": 30},
            "preferences": {},
            "store_limit": 2,
        },
        "maintenance": {
            "location": {"lat": 37.3861, "lon": -122.0839},
            "targets": {"protein": 130, "energy_fibre_kcal": 2200, "carbohydrate": 240, "fat": 70, "fiber": 30},
            "preferences": {},
            "store_limit": 2,
        },
        "budget_friendly_healthy": {
            "location": {"lat": 37.3861, "lon": -122.0839},
            "targets": {"protein": 120, "energy_fibre_kcal": 2100, "carbohydrate": 230, "fat": 65, "fiber": 35},
            "preferences": {"budget_friendly": True},
            "store_limit": 2,
        },
        "high_protein_vegetarian": {
            "location": {"lat": 37.3861, "lon": -122.0839},
            "targets": {"protein": 140, "energy_fibre_kcal": 2100, "carbohydrate": 220, "fat": 70, "fiber": 32},
            "preferences": {"vegetarian": True},
            "store_limit": 2,
        },
    }

    with patched_attr(app_module, "nearby_stores", stub_nearby_stores):
        responses = {
            label: client.post("/api/recommendations/generic", json=payload).get_json()
            for label, payload in payloads.items()
        }

    for label, body in responses.items():
        assert_true(str(body.get("goal_profile")) in GOAL_PROFILE_SET, f"{label} goal_profile present")

    assert_equal(responses["muscle_gain"]["goal_profile"], "muscle_gain", "goal policy muscle_gain detected")
    assert_equal(responses["fat_loss"]["goal_profile"], "fat_loss", "goal policy fat_loss detected")
    assert_equal(responses["maintenance"]["goal_profile"], "maintenance", "goal policy maintenance detected")
    assert_equal(responses["budget_friendly_healthy"]["goal_profile"], "budget_friendly_healthy", "goal policy budget detected")
    assert_equal(
        responses["high_protein_vegetarian"]["goal_profile"],
        "high_protein_vegetarian",
        "goal policy high_protein_vegetarian detected",
    )

    baskets = {
        label: tuple(item["generic_food_id"] for item in body["shopping_list"])
        for label, body in responses.items()
    }
    roles = {
        label: {item["role"]: [entry["generic_food_id"] for entry in body["shopping_list"] if entry["role"] == item["role"]] for item in body["shopping_list"]}
        for label, body in responses.items()
    }

    assert_true(baskets["muscle_gain"] != baskets["fat_loss"], "goal policy muscle and fat-loss baskets differ")
    assert_true(baskets["muscle_gain"] != baskets["maintenance"], "goal policy muscle and maintenance baskets differ")
    assert_true(baskets["maintenance"] != baskets["budget_friendly_healthy"], "goal policy maintenance and budget baskets differ")
    assert_true(
        baskets["high_protein_vegetarian"] != baskets["budget_friendly_healthy"],
        "goal policy high-protein vegetarian and budget baskets differ",
    )

    muscle_proteins = set(roles["muscle_gain"].get("protein_anchor", []))
    muscle_carb = roles["muscle_gain"].get("carb_base", [])
    muscle_produce = set(roles["muscle_gain"].get("produce", []))
    assert_true(
        bool(muscle_proteins & {"eggs", "greek_yogurt", "protein_yogurt", "cottage_cheese", "milk"})
        or len(muscle_proteins & {"turkey", "chicken_breast"}) >= 2,
        "goal policy muscle includes either a dairy/egg training anchor or a stronger double-lean-meat hybrid winner",
    )
    assert_true(
        bool(muscle_proteins & {"turkey", "chicken_breast"}),
        "goal policy muscle includes a lean training protein anchor",
    )
    assert_true(
        not bool(muscle_proteins & {"lentils", "beans", "black_beans", "chickpeas"}),
        "goal policy muscle avoids defaulting to budget legumes",
    )
    assert_true(
        bool(muscle_carb) and muscle_carb[0] in {"rice", "pasta", "oats", "potatoes", "sweet_potatoes", "bagel", "wholemeal_bread"},
        "goal policy muscle picks training-friendly carb base",
    )
    assert_true(
        bool(muscle_produce & {"berries", "bananas", "oranges", "bell_peppers", "spinach", "frozen_vegetables"}),
        "goal policy muscle produce differs from generic default vegetables",
    )

    fat_loss_body = responses["fat_loss"]
    fat_proteins = set(roles["fat_loss"].get("protein_anchor", []))
    fat_carb = roles["fat_loss"].get("carb_base", [])
    fat_produce = set(roles["fat_loss"].get("produce", []))
    assert_true(
        bool(fat_proteins & {"tuna", "chicken_breast", "tofu", "greek_yogurt", "protein_yogurt", "cottage_cheese", "eggs"}),
        "goal policy fat loss picks lean proteins",
    )
    assert_true(
        bool(fat_carb) and fat_carb[0] in {"oats", "potatoes", "sweet_potatoes", "quinoa", "wholemeal_bread"},
        "goal policy fat loss picks conservative carb base",
    )
    assert_true(
        bool(fat_produce & {"spinach", "bell_peppers", "lettuce", "cucumber", "tomatoes", "broccoli", "cauliflower", "berries"}),
        "goal policy fat loss biases high-volume produce",
    )
    assert_true(
        not any(item["role"] == "calorie_booster" for item in fat_loss_body["shopping_list"]),
        "goal policy fat loss avoids calorie boosters",
    )
    assert_true(
        float(fat_loss_body["nutrition_summary"]["calorie_estimated_kcal"]) <= float(fat_loss_body["nutrition_summary"]["calorie_target_kcal"]) + 120.0,
        "goal policy fat loss keeps calorie overshoot controlled",
    )

    maintenance_proteins = set(roles["maintenance"].get("protein_anchor", []))
    maintenance_carb = roles["maintenance"].get("carb_base", [])
    maintenance_produce = set(roles["maintenance"].get("produce", []))
    assert_true(
        bool(maintenance_proteins & {"eggs", "tofu", "chicken_breast", "rotisserie_chicken", "greek_yogurt", "tuna"}),
        "goal policy maintenance uses balanced proteins",
    )
    assert_true(
        bool(maintenance_carb) and maintenance_carb[0] in {"wholemeal_bread", "potatoes", "oats", "quinoa", "rice"},
        "goal policy maintenance uses middle-path carb",
    )
    assert_true(
        bool(maintenance_produce & {"carrots", "apples", "lettuce", "bell_peppers", "spinach", "bananas"}),
        "goal policy maintenance produce is broader than broccoli-only",
    )

    budget_proteins = set(roles["budget_friendly_healthy"].get("protein_anchor", []))
    budget_carb = roles["budget_friendly_healthy"].get("carb_base", [])
    budget_produce = set(roles["budget_friendly_healthy"].get("produce", []))
    assert_true(
        bool(budget_proteins & {"lentils", "beans", "black_beans", "chickpeas"}),
        "goal policy budget basket keeps at least one cheap staple protein",
    )
    assert_true(
        bool(budget_proteins & {"eggs", "tofu", "peanut_butter"})
        or budget_proteins.issuperset({"lentils", "beans"}),
        "goal policy budget basket adds either a non-legume support protein or a distinct two-legume hybrid winner",
    )
    assert_true(
        not budget_proteins.issubset({"lentils", "black_beans", "chickpeas"})
        and not budget_proteins.issubset({"beans", "black_beans", "chickpeas"}),
        "goal policy budget basket avoids collapsing to a single cheap legume family",
    )
    assert_true(
        bool(budget_carb) and budget_carb[0] in {"oats", "rice", "pasta", "potatoes", "wholemeal_bread"},
        "goal policy budget basket uses staple carb",
    )
    assert_true(
        bool(budget_produce & {"cabbage", "carrots", "potatoes", "bananas", "frozen_vegetables", "apples", "lettuce"}),
        "goal policy budget basket uses cheaper produce",
    )

    vegetarian_proteins = set(roles["high_protein_vegetarian"].get("protein_anchor", []))
    vegetarian_carb = roles["high_protein_vegetarian"].get("carb_base", [])
    assert_true(
        bool(vegetarian_proteins & {"eggs", "tofu", "greek_yogurt", "protein_yogurt", "cottage_cheese", "edamame", "milk"}),
        "goal policy high-protein vegetarian uses higher-protein vegetarian anchors",
    )
    assert_true(
        bool(vegetarian_carb) and vegetarian_carb[0] in {"oats", "wholemeal_bread", "quinoa", "rice", "bagel"},
        "goal policy high-protein vegetarian uses supporting carb base",
    )
    return ["goal_policy"]


def run_goal_quantity_policy_scenario() -> list[str]:
    app = create_app()
    client = app.test_client()

    def stub_nearby_stores(_con: duckdb.DuckDBPyConnection, *, limit: int, **_kwargs: object) -> list[dict[str, object]]:
        return STUB_STORES[:limit]

    payloads = {
        "budget_friendly_healthy": {
            "location": {"lat": 37.3861, "lon": -122.0839},
            "targets": {"protein": 120, "energy_fibre_kcal": 2100, "carbohydrate": 230, "fat": 65, "fiber": 35},
            "preferences": {"budget_friendly": True},
            "store_limit": 2,
        },
        "fat_loss": {
            "location": {"lat": 37.3861, "lon": -122.0839},
            "targets": {"protein": 150, "energy_fibre_kcal": 1800, "carbohydrate": 160, "fat": 55, "fiber": 30},
            "preferences": {},
            "store_limit": 2,
        },
        "muscle_gain": {
            "location": {"lat": 37.3861, "lon": -122.0839},
            "targets": {"protein": 170, "energy_fibre_kcal": 2800, "carbohydrate": 330, "fat": 85, "fiber": 35},
            "preferences": {},
            "store_limit": 2,
        },
    }

    with patched_attr(app_module, "nearby_stores", stub_nearby_stores):
        responses = {
            label: client.post("/api/recommendations/generic", json=payload).get_json()
            for label, payload in payloads.items()
        }

    budget_body = responses["budget_friendly_healthy"]
    budget_items = {item["generic_food_id"]: item for item in budget_body["shopping_list"]}
    budget_legume_proteins = {
        item["generic_food_id"]
        for item in budget_body["shopping_list"]
        if item["role"] == "protein_anchor" and item["generic_food_id"] in {"lentils", "beans", "black_beans", "chickpeas"}
    }
    budget_legume_quantity_g = sum(
        float(item["quantity_g"])
        for item in budget_body["shopping_list"]
        if item["role"] == "protein_anchor" and item["generic_food_id"] in {"lentils", "beans", "black_beans", "chickpeas"}
    )
    assert_true(
        len(budget_legume_proteins) <= 2 and budget_legume_quantity_g <= 320.0,
        "goal quantity budget keeps total legume loading practical even when the hybrid winner uses two staples",
    )
    assert_true(
        float(budget_body["nutrition_summary"]["calorie_estimated_kcal"]) <= float(budget_body["nutrition_summary"]["calorie_target_kcal"]) + 300.0,
        "goal quantity budget keeps calorie overshoot practical",
    )
    if "rice" in budget_items:
        assert_true(float(budget_items["rice"]["quantity_g"]) <= 300.0, "goal quantity budget rice stays practical")
    if "oats" in budget_items:
        assert_true(float(budget_items["oats"]["quantity_g"]) <= 260.0, "goal quantity budget oats stays practical")
    if "olive_oil" in budget_items:
        assert_true(float(budget_items["olive_oil"]["quantity_g"]) <= 20.0, "goal quantity budget oil stays practical")

    fat_loss_body = responses["fat_loss"]
    fat_loss_items = {item["generic_food_id"]: item for item in fat_loss_body["shopping_list"]}
    assert_true(
        not any(item["role"] == "calorie_booster" for item in fat_loss_body["shopping_list"]),
        "goal quantity fat loss avoids calorie boosters",
    )
    assert_true(
        float(fat_loss_body["nutrition_summary"]["calorie_estimated_kcal"]) <= float(fat_loss_body["nutrition_summary"]["calorie_target_kcal"]) + 80.0,
        "goal quantity fat loss keeps overshoot tight",
    )
    if "wholemeal_bread" in fat_loss_items:
        assert_true(float(fat_loss_items["wholemeal_bread"]["quantity_g"]) <= 260.0, "goal quantity fat loss bread stays practical")
    if "oats" in fat_loss_items:
        assert_true(float(fat_loss_items["oats"]["quantity_g"]) <= 260.0, "goal quantity fat loss oats stay practical")

    muscle_body = responses["muscle_gain"]
    assert_true(
        float(muscle_body["nutrition_summary"]["calorie_estimated_kcal"]) >= float(muscle_body["nutrition_summary"]["calorie_target_kcal"]) * 0.95,
        "goal quantity muscle gain stays generous enough",
    )
    assert_true(
        float(muscle_body["nutrition_summary"]["calorie_estimated_kcal"]) <= float(muscle_body["nutrition_summary"]["calorie_target_kcal"]) + 150.0,
        "goal quantity muscle gain stays shopper-realistic",
    )
    return ["goal_quantity_policy"]


def run_high_calorie_target_scaling_scenario() -> list[str]:
    app = create_app()
    client = app.test_client()

    def stub_nearby_stores(_con: duckdb.DuckDBPyConnection, *, limit: int, **_kwargs: object) -> list[dict[str, object]]:
        return STUB_STORES[:limit]

    base_payload = {
        "location": {"lat": 37.3861, "lon": -122.0839},
        "targets": {"protein": 180, "energy_fibre_kcal": 5000, "carbohydrate": 330, "fat": 85, "fiber": 35},
        "preferences": {"meal_style": "lunch_dinner"},
        "store_limit": 2,
    }
    higher_payload = {
        **base_payload,
        "targets": {**base_payload["targets"], "energy_fibre_kcal": 10000},
    }

    with patched_attr(app_module, "nearby_stores", stub_nearby_stores):
        base_response = client.post("/api/recommendations/generic", json=base_payload)
        higher_response = client.post("/api/recommendations/generic", json=higher_payload)

    assert_equal(base_response.status_code, 200, "high_calorie_target base status")
    assert_equal(higher_response.status_code, 200, "high_calorie_target higher status")

    base_body = base_response.get_json()
    higher_body = higher_response.get_json()
    base_items = {str(item["generic_food_id"]): item for item in base_body["shopping_list"]}
    higher_items = {str(item["generic_food_id"]): item for item in higher_body["shopping_list"]}
    shared_food_ids = sorted(set(base_items) & set(higher_items))
    assert_true(len(shared_food_ids) >= 4, "high_calorie_target shared foods remain substantial")

    materially_scaled_food_ids = [
        food_id
        for food_id in shared_food_ids
        if float(higher_items[food_id]["quantity_g"]) >= max(float(base_items[food_id]["quantity_g"]) * 1.35, float(base_items[food_id]["quantity_g"]) + 80.0)
    ]
    assert_true(bool(materially_scaled_food_ids), "high_calorie_target shared item quantity scales materially")

    priced_scaled_food_ids = [
        food_id
        for food_id in shared_food_ids
        if (
            base_items[food_id]["estimated_item_cost"] is not None
            and higher_items[food_id]["estimated_item_cost"] is not None
            and float(higher_items[food_id]["estimated_item_cost"]) > float(base_items[food_id]["estimated_item_cost"]) * 1.25
        )
    ]
    assert_true(bool(priced_scaled_food_ids), "high_calorie_target shared priced item cost scales with quantity")

    assert_true(
        float(higher_body["nutrition_summary"]["calorie_estimated_kcal"]) > float(base_body["nutrition_summary"]["calorie_estimated_kcal"]) + 3000.0,
        "high_calorie_target higher target materially increases estimated calories",
    )
    assert_true(
        float(higher_body["estimated_basket_cost"]) > float(base_body["estimated_basket_cost"]) + 5.0,
        "high_calorie_target higher target materially increases basket cost",
    )
    assert_true(
        tuple((str(item["generic_food_id"]), float(item["quantity_g"])) for item in base_body["shopping_list"])
        != tuple((str(item["generic_food_id"]), float(item["quantity_g"])) for item in higher_body["shopping_list"]),
        "high_calorie_target final basket quantities differ",
    )

    for label, payload in (("high_calorie_target base", base_body), ("high_calorie_target higher", higher_body)):
        summary = payload["nutrition_summary"]
        estimated_item_calories = round(sum(float(item["estimated_calories_kcal"]) for item in payload["shopping_list"]), 1)
        estimated_item_protein = round(sum(float(item["estimated_protein_g"]) for item in payload["shopping_list"]), 1)
        estimated_item_cost = round(
            sum(float(item["estimated_item_cost"]) for item in payload["shopping_list"] if item["estimated_item_cost"] is not None),
            2,
        )
        assert_true(
            abs(float(summary["calorie_estimated_kcal"]) - estimated_item_calories) <= 0.2,
            f"{label} calorie summary matches final basket quantities",
        )
        assert_true(
            abs(float(summary["protein_estimated_g"]) - estimated_item_protein) <= 0.2,
            f"{label} protein summary matches final basket quantities",
        )
        assert_true(
            abs(float(payload["estimated_basket_cost"]) - estimated_item_cost) <= 0.01,
            f"{label} basket cost matches final item costs",
        )

    return ["high_calorie_target_scaling"]


def run_meal_suggestion_realism_scenario() -> list[str]:
    app = create_app()
    client = app.test_client()
    name_to_id = load_name_to_id()

    def stub_nearby_stores(_con: duckdb.DuckDBPyConnection, *, limit: int, **_kwargs: object) -> list[dict[str, object]]:
        return STUB_STORES[:limit]

    breakfast_payload = {
        "location": {"lat": 37.3861, "lon": -122.0839},
        "targets": {"protein": 100, "energy_fibre_kcal": 1900},
        "preferences": {"meal_style": "breakfast"},
        "store_limit": 2,
    }
    snack_payload = {
        "location": {"lat": 37.3861, "lon": -122.0839},
        "targets": {"protein": 95, "energy_fibre_kcal": 1800},
        "preferences": {"meal_style": "snack"},
        "store_limit": 2,
    }

    with patched_attr(app_module, "nearby_stores", stub_nearby_stores):
        breakfast = client.post("/api/recommendations/generic", json=breakfast_payload).get_json()
        snack = client.post("/api/recommendations/generic", json=snack_payload).get_json()

    breakfast_suggestions = {suggestion["meal_type"]: suggestion for suggestion in breakfast["meal_suggestions"]}
    snack_suggestions = {suggestion["meal_type"]: suggestion for suggestion in snack["meal_suggestions"]}

    breakfast_breakfast = breakfast_suggestions.get("breakfast")
    assert_true(bool(breakfast_breakfast), "meal suggestion realism breakfast idea present")
    breakfast_breakfast_items = {food_id for food_id in map(name_to_id.get, breakfast_breakfast["items"]) if food_id}
    breakfast_core_ids = {"eggs", "greek_yogurt", "protein_yogurt", "cottage_cheese", "oats", "corn_flakes", "bagel", "wholemeal_bread", "pita", "bananas", "apples", "oranges", "berries", "grapes", "pears", "kiwi", "pineapple", "mango"}
    breakfast_blocked_ids = {"lentils", "beans", "black_beans", "chickpeas", "broccoli", "kale", "rotisserie_chicken", "chicken_breast", "ground_beef", "turkey", "salmon", "shrimp"}
    assert_true(bool(breakfast_breakfast_items & breakfast_core_ids), "meal suggestion realism breakfast uses breakfast-friendly items")
    assert_true(not (breakfast_breakfast_items & breakfast_blocked_ids), "meal suggestion realism breakfast avoids heavy dinner-like items")

    breakfast_snack = breakfast_suggestions.get("snack")
    if breakfast_snack:
        breakfast_snack_items = {food_id for food_id in map(name_to_id.get, breakfast_snack["items"]) if food_id}
        assert_true(breakfast_breakfast_items != breakfast_snack_items, "meal suggestion realism breakfast and snack differ")

    snack_snack = snack_suggestions.get("snack")
    assert_true(bool(snack_snack), "meal suggestion realism snack idea present")
    snack_ids = {food_id for food_id in map(name_to_id.get, snack_snack["items"]) if food_id}
    snack_core_ids = {"greek_yogurt", "protein_yogurt", "cottage_cheese", "cheese", "nuts", "peanut_butter", "almond_butter", "bananas", "apples", "berries", "grapes", "kiwi", "carrots", "cucumber", "celery", "bell_peppers", "tomatoes", "corn_flakes", "bagel", "wholemeal_bread", "pita", "tortilla"}
    snack_blocked_ids = {"rotisserie_chicken", "chicken_breast", "ground_beef", "turkey", "salmon", "shrimp", "broccoli", "kale", "lentils", "beans", "rice", "pasta"}
    assert_true(len(snack_snack["items"]) <= 3, "meal suggestion realism snack stays compact")
    assert_true(bool(snack_ids & snack_core_ids), "meal suggestion realism snack uses snack-friendly items")
    assert_true(not (snack_ids & snack_blocked_ids), "meal suggestion realism snack avoids heavy dinner-like items")

    snack_breakfast = snack_suggestions.get("breakfast")
    if snack_breakfast:
        snack_breakfast_items = {food_id for food_id in map(name_to_id.get, snack_breakfast["items"]) if food_id}
        assert_true(snack_breakfast_items != snack_ids, "meal suggestion realism snack and breakfast differ")

    return ["meal_suggestion_realism"]


def run_store_fit_scenario() -> list[str]:
    app = create_app()
    client = app.test_client()

    def stub_nearby_stores(_con: duckdb.DuckDBPyConnection, *, limit: int, **_kwargs: object) -> list[dict[str, object]]:
        return STUB_STORES[:limit]

    bulk_payload = {
        "location": {"lat": 37.3861, "lon": -122.0839},
        "targets": {"protein": 130, "energy_fibre_kcal": 2100},
        "preferences": {"budget_friendly": True, "meal_style": "lunch_dinner"},
        "store_limit": 3,
        "days": 7,
        "shopping_mode": "bulk",
    }
    plant_payload = {
        "location": {"lat": 37.3861, "lon": -122.0839},
        "targets": {"protein": 110, "energy_fibre_kcal": 2000},
        "preferences": {"vegan": True, "meal_style": "snack"},
        "store_limit": 3,
    }

    with patched_attr(app_module, "nearby_stores", stub_nearby_stores):
        bulk_body = client.post("/api/recommendations/generic", json=bulk_payload).get_json()
        plant_body = client.post("/api/recommendations/generic", json=plant_payload).get_json()

    assert_equal(bulk_body["recommended_store_order"][0], "stub:costco", "store_fit bulk prefers wholesale club")
    assert_true(
        bulk_body["store_fit_notes"][0]["fit_label"] in {"Best bulk fit", "Best overall fit"},
        "store_fit bulk label",
    )
    assert_true(
        bulk_body["store_fit_notes"][0]["note"],
        "store_fit bulk note present",
    )
    assert_equal(bulk_body["bulk_pick"]["store_id"], "stub:costco", "store_fit bulk_pick prefers wholesale club")
    assert_equal(
        bulk_body["budget_pick"]["store_id"],
        "stub:costco",
        "store_fit budget_pick prefers value-oriented nearby wholesale club",
    )
    assert_true(
        plant_body["recommended_store_order"][0] in {"stub:wholefoods", "stub:traderjoes"},
        "store_fit plant-forward prefers grocery or specialty-oriented nearby store",
    )
    assert_true(
        plant_body["produce_pick"]["store_id"] in {"stub:wholefoods", "stub:traderjoes"},
        "store_fit produce_pick prefers produce-oriented nearby store",
    )
    assert_true(
        plant_body["one_stop_pick"]["store_id"] in {"stub:wholefoods", "stub:costco"},
        "store_fit one_stop_pick stays near a broad-fit nearby store",
    )
    return ["store_fit"]


def run_pantry_scenario() -> list[str]:
    app = create_app()
    client = app.test_client()

    def stub_nearby_stores(_con: duckdb.DuckDBPyConnection, *, limit: int, **_kwargs: object) -> list[dict[str, object]]:
        return STUB_STORES[:limit]

    payload = {
        "location": {"lat": 37.3861, "lon": -122.0839},
        "targets": {"protein": 120, "energy_fibre_kcal": 2100},
        "preferences": {"budget_friendly": True, "meal_style": "lunch_dinner"},
        "store_limit": 3,
        "days": 3,
        "shopping_mode": "balanced",
    }

    with patched_attr(app_module, "nearby_stores", stub_nearby_stores):
        baseline_resp = client.post("/api/recommendations/generic", json=payload)
        assert_equal(baseline_resp.status_code, 200, "pantry baseline status")
        baseline_body = baseline_resp.get_json()
        baseline_items = {item["generic_food_id"]: item for item in baseline_body["shopping_list"]}
        pantry_ids = [food_id for food_id in ("rice", "broccoli", "lentils") if food_id in baseline_items][:2]
        assert_true(bool(pantry_ids), "pantry scenario has stable pantry candidates")

        pantry_payload = {**payload, "pantry_items": pantry_ids}
        first_pantry_resp = client.post("/api/recommendations/generic", json=pantry_payload)
        second_pantry_resp = client.post("/api/recommendations/generic", json=pantry_payload)

    assert_equal(first_pantry_resp.status_code, 200, "pantry status")
    assert_equal(second_pantry_resp.status_code, 200, "pantry repeat status")

    pantry_body = first_pantry_resp.get_json()
    pantry_repeat_body = second_pantry_resp.get_json()
    assert_true(isinstance(pantry_body.get("pantry_notes"), list), "pantry notes list")
    assert_true(len(pantry_body["pantry_notes"]) >= 1, "pantry notes non-empty")
    assert_true(
        "already available" in " ".join(str(note) for note in pantry_body["pantry_notes"]).lower(),
        "pantry notes mention already available items",
    )
    assert_true(
        abs(float(pantry_body["nutrition_summary"]["protein_estimated_g"]) - float(baseline_body["nutrition_summary"]["protein_estimated_g"])) <= 30.0,
        "pantry keeps protein summary close to the full-plan totals even if hybrid reranking swaps candidates",
    )
    assert_true(
        abs(float(pantry_body["nutrition_summary"]["calorie_estimated_kcal"]) - float(baseline_body["nutrition_summary"]["calorie_estimated_kcal"])) <= 300.0,
        "pantry keeps calorie summary close to the full-plan totals even if hybrid reranking swaps candidates",
    )
    assert_true(
        tuple(item["generic_food_id"] for item in pantry_body["shopping_list"])
        == tuple(item["generic_food_id"] for item in pantry_repeat_body["shopping_list"]),
        "pantry response remains deterministic",
    )

    pantry_items = {item["generic_food_id"]: item for item in pantry_body["shopping_list"]}
    changed = False
    for pantry_id in pantry_ids:
        baseline_quantity = float(baseline_items[pantry_id]["quantity_g"])
        pantry_item = pantry_items.get(pantry_id)
        if pantry_item is None:
            changed = True
            continue
        if float(pantry_item["quantity_g"]) < baseline_quantity:
            changed = True
    assert_true(changed, "pantry reduces or removes at least one already-available item")
    return ["pantry"]


def sample_live_rows(lat: float, lon: float) -> list[tuple[dict[str, object], dict[str, object]]]:
    rows: list[tuple[dict[str, object], dict[str, object]]] = []
    samples = [
        ("osm:node:101", "Alpha Market", "100 Main St, Demo City, CA 94041", "supermarket", lat + 0.0010, lon + 0.0010),
        ("osm:node:102", "Beta Grocery", "200 Main St, Demo City, CA 94041", "grocery", lat + 0.0018, lon + 0.0005),
        ("osm:node:103", "Gamma Foods", "300 Main St, Demo City, CA 94041", "supermarket", lat - 0.0012, lon - 0.0007),
    ]
    for store_id, name, address, category, store_lat, store_lon in samples:
        rows.append(
            (
                store_discovery._normalize_store(  # noqa: SLF001
                    store_id=store_id,
                    name=name,
                    address=address,
                    distance_m=store_discovery.haversine_distance_m(lat, lon, store_lat, store_lon),
                    lat=store_lat,
                    lon=store_lon,
                    category=category,
                ),
                {
                    "id": int(store_id.rsplit(":", maxsplit=1)[1]),
                    "type": "node",
                    "_city": "Demo City",
                    "_region": "CA",
                    "_postcode": "94041",
                },
            )
        )
    rows.sort(key=lambda item: (float(item[0]["distance_m"]), str(item[0]["name"])))
    return rows


def run_store_discovery_scenarios() -> list[str]:
    labels: list[str] = []
    formatted_duplicates = [
        {
            "store_id": "foursquare_seed:nob_hill",
            "name": "Nob Hill Foods",
            "address": "1250 Grant Rd, Mountain View, CA, 94040",
            "distance_m": 1200.0,
            "lat": 37.3789,
            "lon": -122.0796,
            "category": "supermarket",
            "brand": "Nob Hill Foods",
            "source_priority": 70,
        },
        {
            "store_id": "osm:node:12345",
            "name": "Nob Hill Foods",
            "address": "1250, Grant Road, Mountain View, 94040",
            "distance_m": 1201.0,
            "lat": 37.3789005,
            "lon": -122.0796003,
            "category": "supermarket",
            "brand": "Nob Hill Foods",
            "source_priority": 100,
        },
    ]
    deduped = store_discovery._finalize_store_results(formatted_duplicates, limit=10)
    assert_equal(len(deduped), 1, "store dedupe collapses formatted duplicate addresses")
    assert_true("CA" in deduped[0]["address"], "store dedupe prefers more complete address")
    labels.append("formatted_duplicate_dedupe")

    with tempfile.TemporaryDirectory(prefix="store-discovery-tests-") as temp_dir:
        sidecar_path = Path(temp_dir) / "store_discovery.db"

        with patched_attrs(store_discovery, STORE_DISCOVERY_DB_PATH=sidecar_path):
            with store_discovery._runtime_con() as runtime_con:  # noqa: SLF001
                runtime_con.execute(
                    """
                    INSERT INTO store_places_unified (
                      store_id, name, brand, lat, lon, address, city, region, postcode, category,
                      source, source_priority, confidence, last_seen_at
                    )
                    VALUES (
                      'prefilled:nob_hill', 'Nob Hill Foods', 'Nob Hill Foods', 37.3789, -122.0796,
                      '1250 Grant Rd, Mountain View, CA, 94040', 'Mountain View', 'CA', '94040',
                      'supermarket', 'prefilled', 90, 0.9, CURRENT_TIMESTAMP
                    )
                    """
                )

        def unexpected_refresh(**_kwargs: object) -> dict[str, int]:
            raise AssertionError("nearby_stores should not refresh a populated unified index during normal requests")

        with patched_attrs(
            store_discovery,
            STORE_DISCOVERY_DB_PATH=sidecar_path,
            STORE_DISCOVERY_MODE="auto",
            refresh_unified_store_index=unexpected_refresh,
        ):
            with duckdb.connect("data/data.db", read_only=True) as con:
                prefilled = store_discovery.nearby_stores(con, lat=37.3789, lon=-122.0796, radius_m=500, limit=3)
            assert_equal(len(prefilled), 1, "prefilled unified index returns store without refresh")
            assert_equal(prefilled[0]["name"], "Nob Hill Foods", "prefilled unified index store name")
            labels.append("prefilled_unified_reuse")

        flaky_unified_calls = {"count": 0}
        real_unified_nearby = store_discovery._unified_nearby_stores  # noqa: SLF001

        def flaky_unified_nearby(*, lat: float, lon: float, radius_m: float, limit: int) -> list[dict[str, object]] | None:
            flaky_unified_calls["count"] += 1
            if flaky_unified_calls["count"] == 1:
                return None
            return real_unified_nearby(lat=lat, lon=lon, radius_m=radius_m, limit=limit)

        with patched_attrs(
            store_discovery,
            STORE_DISCOVERY_DB_PATH=sidecar_path,
            STORE_DISCOVERY_MODE="local",
            STORE_DISCOVERY_READ_RETRY_COUNT=2,
            STORE_DISCOVERY_READ_RETRY_DELAY_MS=0,
            _unified_nearby_stores=flaky_unified_nearby,
        ):
            with duckdb.connect("data/data.db", read_only=True) as con:
                retried = store_discovery.nearby_stores(con, lat=37.3789, lon=-122.0796, radius_m=500, limit=3)
            assert_equal(len(retried), 1, "transient unified-sidecar failure still returns unified store")
            assert_equal(retried[0]["name"], "Nob Hill Foods", "transient unified-sidecar failure keeps unified coverage")
            assert_equal(flaky_unified_calls["count"], 2, "transient unified-sidecar failure retries once before fallback")
            labels.append("transient_unified_retry")

        with patched_attrs(store_discovery, STORE_DISCOVERY_DB_PATH=sidecar_path):
            with store_discovery._runtime_con() as runtime_con:  # noqa: SLF001
                runtime_con.execute("DELETE FROM store_places_unified")
                runtime_con.execute("DELETE FROM store_places_live")
                runtime_con.execute("DELETE FROM store_places_foursquare")
                runtime_con.execute(
                    """
                    INSERT INTO store_places_live (
                      store_id, source, source_place_id, name, brand, address, city, region, postcode, category,
                      lat, lon, last_seen_at, raw_record_json
                    )
                    VALUES (
                      'osm:node:99ranch', 'overpass', 'node:99ranch', '99 Ranch Market', '99 Ranch Market',
                      '99 Ranch Market', NULL, NULL, NULL, 'supermarket',
                      37.8951, -122.3042, CURRENT_TIMESTAMP, '{}'
                    )
                    """
                )
                runtime_con.execute(
                    """
                    INSERT INTO store_places_foursquare (
                      store_id, name, brand, lat, lon, address, city, region, postcode, category,
                      source, source_priority, confidence, last_seen_at, raw_record_json
                    )
                    VALUES (
                      'foursquare_os_places:99ranch', '99 Ranch Market', '99 Ranch Market', 37.89511, -122.30418,
                      '3288 Pierce St', 'Richmond', 'CA', '94804', 'supermarket',
                      'foursquare_os_places', 90, 0.90, CURRENT_TIMESTAMP, '{}'
                    )
                    """
                )

            with duckdb.connect("data/data.db", read_only=True) as con:
                summary = store_discovery.refresh_unified_store_index(main_con=con, force=True)
            assert_true(summary["unified_rows"] >= 1, "foursquare metadata enrichment refresh returns unified rows")

            with duckdb.connect(sidecar_path, read_only=True) as sidecar_con:
                row = sidecar_con.execute(
                    """
                    SELECT address, city, region, postcode, source, metadata_source
                    FROM store_places_unified
                    WHERE name = '99 Ranch Market'
                    """
                ).fetchone()
                match_count = sidecar_con.execute(
                    "SELECT COUNT(*) FROM store_places_unified WHERE name = '99 Ranch Market'"
                ).fetchone()[0]
            assert_equal(match_count, 1, "foursquare metadata enrichment collapses matching rows")
            assert_true(row is not None, "foursquare metadata enrichment creates unified row")
            assert_equal(row[0], "3288 Pierce St", "foursquare metadata enrichment prefers richer address")
            assert_equal(row[1], "Richmond", "foursquare metadata enrichment fills city")
            assert_equal(row[2], "CA", "foursquare metadata enrichment fills region")
            assert_equal(row[3], "94804", "foursquare metadata enrichment fills postcode")
            assert_equal(row[4], "overpass", "foursquare metadata enrichment keeps primary overpass source")
            assert_equal(
                row[5],
                "foursquare_os_places",
                "foursquare metadata enrichment records metadata source",
            )
            labels.append("foursquare_metadata_enrichment")

        with patched_attrs(store_discovery, STORE_DISCOVERY_DB_PATH=sidecar_path):
            with store_discovery._runtime_con() as runtime_con:  # noqa: SLF001
                runtime_con.execute("DELETE FROM store_places_unified")
                runtime_con.execute("DELETE FROM store_places_live")
                runtime_con.execute("DELETE FROM store_places_foursquare")
                runtime_con.execute(
                    """
                    INSERT INTO store_places_foursquare (
                      store_id, name, brand, lat, lon, address, city, region, postcode, category,
                      source, source_priority, confidence, last_seen_at, raw_record_json
                    )
                    VALUES
                    (
                      'foursquare_os_places:display_quality',
                      'Green Valley Market',
                      'Green Valley Market',
                      40.7342,
                      -73.9911,
                      '101 1st Ave',
                      'New York',
                      'NY',
                      '10003',
                      'grocery',
                      'foursquare_os_places',
                      90,
                      0.90,
                      CURRENT_TIMESTAMP,
                      '{}'
                    ),
                    (
                      'foursquare_os_places:enrichment_only',
                      'Example Market',
                      'Example Market',
                      40.7343,
                      -73.9912,
                      'Example Market',
                      'New York',
                      'NY',
                      NULL,
                      'grocery',
                      'foursquare_os_places',
                      90,
                      0.90,
                      CURRENT_TIMESTAMP,
                      '{}'
                    )
                    """
                )

            with duckdb.connect("data/data.db", read_only=True) as con:
                summary = store_discovery.refresh_unified_store_index(main_con=con, force=True)
            assert_true(summary["unified_rows"] >= 1, "foursquare coverage expansion refresh returns unified rows")

            with duckdb.connect(sidecar_path, read_only=True) as sidecar_con:
                display_row = sidecar_con.execute(
                    """
                    SELECT source, city, region, postcode
                    FROM store_places_unified
                    WHERE store_id = 'foursquare_os_places:display_quality'
                    """
                ).fetchone()
                enrichment_only_row = sidecar_con.execute(
                    """
                    SELECT store_id
                    FROM store_places_unified
                    WHERE store_id = 'foursquare_os_places:enrichment_only'
                    """
                ).fetchone()
            assert_true(display_row is not None, "foursquare coverage expansion keeps high-quality standalone rows")
            assert_equal(display_row[0], "foursquare_os_places", "foursquare coverage expansion preserves Foursquare source")
            assert_equal(display_row[1], "New York", "foursquare coverage expansion keeps city")
            assert_equal(display_row[2], "NY", "foursquare coverage expansion keeps region")
            assert_equal(display_row[3], "10003", "foursquare coverage expansion keeps postcode")
            assert_true(enrichment_only_row is None, "foursquare coverage expansion filters low-quality standalone rows")
            labels.append("foursquare_coverage_expansion")

        live_call_count = {"count": 0}

        def fake_live(*, lat: float, lon: float, radius_m: float, limit: int) -> list[tuple[dict[str, object], dict[str, object]]]:
            live_call_count["count"] += 1
            return sample_live_rows(lat, lon)[:limit]

        def dead_live(*, lat: float, lon: float, radius_m: float, limit: int) -> list[tuple[dict[str, object], dict[str, object]]]:
            raise RuntimeError("simulated live failure")

        with patched_attrs(
            store_discovery,
            STORE_DISCOVERY_DB_PATH=sidecar_path,
            STORE_DISCOVERY_MODE="live",
            STORE_DISCOVERY_CACHE_TTL_S=3600,
            STORE_DISCOVERY_PERSIST_LIVE=True,
            STORE_DISCOVERY_LIVE_INDEX_MAX_AGE_S=3600,
            STORE_DISCOVERY_LIVE_INDEX_MIN_RESULTS=3,
            _live_overpass_nearby_stores=fake_live,
        ):
            with duckdb.connect("data/data.db", read_only=True) as con:
                first = store_discovery.nearby_stores(con, lat=37.3861, lon=-122.0839, radius_m=5000, limit=3)
            assert_equal(live_call_count["count"], 1, "cache scenario live call count after first request")
            assert_equal(len(first), 3, "cache scenario first result count")
            assert_equal(set(first[0].keys()), EXPECTED_STORE_KEYS, "cache scenario first store shape")
            with duckdb.connect(sidecar_path, read_only=True) as sidecar_con:
                assert_equal(sidecar_con.execute("SELECT COUNT(*) FROM store_search_cache").fetchone()[0], 1, "cache rows after live fetch")
                assert_equal(sidecar_con.execute("SELECT COUNT(*) FROM store_places_live").fetchone()[0], 3, "persisted rows after live fetch")

        with patched_attrs(
            store_discovery,
            STORE_DISCOVERY_DB_PATH=sidecar_path,
            STORE_DISCOVERY_MODE="live",
            STORE_DISCOVERY_CACHE_TTL_S=3600,
            STORE_DISCOVERY_PERSIST_LIVE=True,
            STORE_DISCOVERY_LIVE_INDEX_MAX_AGE_S=3600,
            STORE_DISCOVERY_LIVE_INDEX_MIN_RESULTS=3,
            _live_overpass_nearby_stores=dead_live,
        ):
            with duckdb.connect("data/data.db", read_only=True) as con:
                cached = store_discovery.nearby_stores(con, lat=37.3861, lon=-122.0839, radius_m=5000, limit=3)
            assert_equal(cached, first, "cache reuse results")
            labels.append("cache_reuse")

        with duckdb.connect(sidecar_path) as sidecar_con:
            sidecar_con.execute("DELETE FROM store_search_cache")

        with patched_attrs(
            store_discovery,
            STORE_DISCOVERY_DB_PATH=sidecar_path,
            STORE_DISCOVERY_MODE="auto",
            STORE_DISCOVERY_CACHE_TTL_S=3600,
            STORE_DISCOVERY_PERSIST_LIVE=True,
            STORE_DISCOVERY_LIVE_INDEX_MAX_AGE_S=3600,
            STORE_DISCOVERY_LIVE_INDEX_MIN_RESULTS=3,
            _live_overpass_nearby_stores=dead_live,
        ):
            with duckdb.connect("data/data.db", read_only=True) as con:
                persisted = store_discovery.nearby_stores(con, lat=37.3861, lon=-122.0839, radius_m=5000, limit=3)
            assert_equal(persisted, first, "persisted live reuse results")
            labels.append("persisted_live_reuse")

        fallback_sidecar = Path(temp_dir) / "fallback_store_discovery.db"
        with patched_attrs(
            store_discovery,
            STORE_DISCOVERY_DB_PATH=fallback_sidecar,
            STORE_DISCOVERY_MODE="auto",
            STORE_DISCOVERY_CACHE_TTL_S=3600,
            STORE_DISCOVERY_PERSIST_LIVE=True,
            STORE_DISCOVERY_LIVE_INDEX_MAX_AGE_S=3600,
            STORE_DISCOVERY_LIVE_INDEX_MIN_RESULTS=3,
            _live_overpass_nearby_stores=dead_live,
        ):
            with duckdb.connect("data/data.db", read_only=True) as con:
                fallback = store_discovery.nearby_stores(con, lat=37.401, lon=-122.09, radius_m=8000, limit=5)
            assert_true(len(fallback) >= 1, "local fallback non-empty")
            assert_equal(set(fallback[0].keys()), EXPECTED_STORE_KEYS, "local fallback store shape")
            labels.append("seed_fallback")

    return labels


def main() -> int:
    recommendation_labels = run_recommendation_scenarios()
    recommendation_labels.extend(run_price_consistency_scenario())
    recommendation_labels.extend(run_price_area_scenario())
    recommendation_labels.extend(run_price_aware_budget_scenario())
    recommendation_labels.extend(run_usda_price_layer_scenario())
    recommendation_labels.extend(run_multi_day_scaling_scenario())
    recommendation_labels.extend(run_shopping_mode_scenario())
    recommendation_labels.extend(run_result_realism_scenario())
    recommendation_labels.extend(run_diversity_scenario())
    recommendation_labels.extend(run_preference_overlap_scenario())
    recommendation_labels.extend(run_goal_policy_scenario())
    recommendation_labels.extend(run_goal_quantity_policy_scenario())
    recommendation_labels.extend(run_high_calorie_target_scaling_scenario())
    recommendation_labels.extend(run_meal_suggestion_realism_scenario())
    recommendation_labels.extend(run_store_fit_scenario())
    recommendation_labels.extend(run_pantry_scenario())
    store_labels = run_store_discovery_scenarios()
    print("recommendation_scenarios=" + ",".join(recommendation_labels))
    print("store_discovery_scenarios=" + ",".join(store_labels))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print(f"BEHAVIOR TEST FAILED: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
