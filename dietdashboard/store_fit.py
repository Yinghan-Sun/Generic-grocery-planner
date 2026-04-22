"""Heuristic store-fit annotations for the /generic flow."""

from __future__ import annotations

from collections.abc import Sequence

from dietdashboard.store_discovery import normalize_brand

SPECIALTY_BRANDS = {
    "Whole Foods",
    "Trader Joe's",
    "H Mart",
    "Sprouts",
    "99 Ranch Market",
    "Berkeley Bowl",
}
VALUE_BRANDS = {
    "Costco",
    "Safeway",
    "Target",
    "Walmart",
    "Kroger",
    "Grocery Outlet",
}
GROUPED_PICK_FIELDS = (
    "one_stop_pick",
    "budget_pick",
    "produce_pick",
    "bulk_pick",
)


def _store_source(store: dict[str, object]) -> str:
    store_id = str(store.get("store_id") or "")
    if ":" not in store_id:
        return "unknown"
    return store_id.split(":", maxsplit=1)[0]


def _store_brand(store: dict[str, object]) -> str | None:
    return normalize_brand(str(store.get("name") or ""))


def _store_type(store: dict[str, object]) -> str:
    category = str(store.get("category") or "").strip().lower()
    brand = _store_brand(store)
    if category == "wholesale_club" or brand == "Costco":
        return "wholesale_club"
    if brand in SPECIALTY_BRANDS:
        return "specialty_grocery"
    if category in {"grocery", "grocery_store", "market"}:
        return "grocery"
    return "supermarket"


def _basket_profile(
    shopping_list: Sequence[dict[str, object]],
    preferences: dict[str, object],
    *,
    days: int,
    shopping_mode: str,
) -> dict[str, bool]:
    produce_items = [item for item in shopping_list if str(item.get("role")) == "produce"]
    carb_items = [item for item in shopping_list if str(item.get("role")) == "carb_base"]
    booster_items = [item for item in shopping_list if str(item.get("role")) == "calorie_booster"]
    protein_items = [item for item in shopping_list if str(item.get("role")) == "protein_anchor"]

    produce_total_g = sum(float(item.get("quantity_g") or 0.0) for item in produce_items)
    total_g = sum(float(item.get("quantity_g") or 0.0) for item in shopping_list)
    item_ids = {str(item.get("generic_food_id") or "") for item in shopping_list}
    meal_style = str(preferences.get("meal_style") or "any")
    budget_friendly = bool(preferences.get("budget_friendly"))
    vegetarian = bool(preferences.get("vegetarian"))
    vegan = bool(preferences.get("vegan"))

    specialty_ids = {
        "tofu",
        "edamame",
        "hummus",
        "veggie_burger",
        "quinoa",
        "berries",
        "kale",
        "mushrooms",
        "salmon",
        "shrimp",
    }

    return {
        "produce_heavy": len(produce_items) >= 2 or (total_g > 0 and (produce_total_g / total_g) >= 0.22),
        "staple_heavy": (
            shopping_mode == "bulk"
            or days >= 5
            or budget_friendly
            or (len(carb_items) >= 1 and len(protein_items) >= 2)
            or (len(carb_items) >= 1 and len(booster_items) >= 1)
        ),
        "plant_forward": vegetarian or vegan or bool(item_ids & specialty_ids),
        "quick_trip": meal_style in {"breakfast", "snack"},
        "meal_style_lunch": meal_style == "lunch_dinner",
        "budget_friendly": budget_friendly,
    }


def _store_fit_score(
    store: dict[str, object],
    profile: dict[str, bool],
    *,
    shopping_mode: str,
) -> tuple[float, list[str]]:
    store_type = _store_type(store)
    brand = _store_brand(store)
    source = _store_source(store)
    score = {"supermarket": 2.0, "grocery": 1.7, "specialty_grocery": 1.6, "wholesale_club": 1.4}[store_type]
    reasons: list[str] = []

    if profile["staple_heavy"]:
        if store_type == "wholesale_club":
            score += 3.6
            reasons.append("Fits a bulk or staple-heavy basket.")
        elif store_type == "supermarket":
            score += 2.0
            reasons.append("Handles a mixed staple and pantry list well.")
        elif store_type == "grocery":
            score += 0.5
        if brand in VALUE_BRANDS and profile["budget_friendly"]:
            score += 1.2
            reasons.append("Brand profile leans practical for a budget-oriented trip.")

    if profile["produce_heavy"]:
        if store_type in {"grocery", "supermarket"}:
            score += 2.0
            reasons.append("Good fit for a produce-forward basket.")
        elif store_type == "specialty_grocery":
            score += 2.2
            reasons.append("Strong fit for produce and specialty grocery items.")
        elif store_type == "wholesale_club":
            score += 0.4

    if profile["plant_forward"]:
        if store_type == "specialty_grocery":
            score += 2.8
            reasons.append("Likely better for plant-forward or specialty pantry items.")
        elif store_type == "supermarket":
            score += 1.2
        elif store_type == "grocery":
            score += 1.0
        if brand in SPECIALTY_BRANDS:
            score += 1.0

    if profile["quick_trip"]:
        if store_type == "grocery":
            score += 1.1
            reasons.append("Works well for a quick in-and-out grocery stop.")
        elif store_type == "specialty_grocery":
            score += 0.9
        elif store_type == "supermarket":
            score += 0.4

    if profile["meal_style_lunch"] and store_type == "supermarket":
        score += 0.8

    if shopping_mode == "fresh":
        if store_type in {"grocery", "supermarket"}:
            score += 0.9
            reasons.append("Better aligned with a fresher, shorter-window shop.")
        if store_type == "wholesale_club":
            score -= 0.4
    elif shopping_mode == "bulk":
        if store_type == "wholesale_club":
            score += 2.3
        elif store_type == "supermarket":
            score += 0.8

    if source.startswith("foursquare"):
        score += 0.15
    distance_km = float(store.get("distance_m") or 0.0) / 1000.0
    score -= distance_km * 0.18
    return score, reasons


def _fit_label(store_type: str, profile: dict[str, bool]) -> str:
    if profile["staple_heavy"] and store_type == "wholesale_club":
        return "Best bulk fit"
    if profile["produce_heavy"] and store_type in {"grocery", "supermarket", "specialty_grocery"}:
        return "Best produce fit"
    if profile["plant_forward"] and store_type == "specialty_grocery":
        return "Best specialty fit"
    return "Best overall fit"


def _build_ranked_entries(
    stores: Sequence[dict[str, object]],
    profile: dict[str, bool],
    *,
    shopping_mode: str,
) -> list[dict[str, object]]:
    ranked_entries: list[dict[str, object]] = []
    for store in stores:
        score, reasons = _store_fit_score(store, profile, shopping_mode=shopping_mode)
        ranked_entries.append(
            {
                "store": store,
                "score": score,
                "reasons": reasons,
                "store_type": _store_type(store),
                "brand": _store_brand(store),
                "source": _store_source(store),
            }
        )

    ranked_entries.sort(
        key=lambda entry: (
            -float(entry["score"]),
            float(entry["store"].get("distance_m") or 0.0),
            str(entry["store"].get("name") or ""),
        )
    )
    return ranked_entries


def _pick_note(
    pick_name: str,
    entry: dict[str, object],
    profile: dict[str, bool],
) -> str:
    store_type = str(entry["store_type"])
    brand = entry["brand"]

    if pick_name == "one_stop_pick":
        if store_type == "supermarket":
            return "Strong general fit for a mixed grocery basket."
        if store_type == "wholesale_club":
            return "Good one-stop option for staples, pantry items, and larger shopping windows."
        return "Reasonable all-around fit for this grocery list."

    if pick_name == "budget_pick":
        if store_type == "wholesale_club":
            return "Best fit for budget-oriented staple shopping and larger basket sizes."
        if brand in VALUE_BRANDS:
            return "Brand profile leans practical for lower-cost staple shopping."
        return "Useful budget-minded fallback for this list."

    if pick_name == "produce_pick":
        if brand in SPECIALTY_BRANDS or store_type == "specialty_grocery":
            return "Strong produce and specialty grocery fit for this basket."
        if store_type in {"grocery", "supermarket"}:
            return "Good fit for a produce-forward shopping trip."
        return "Reasonable produce stop for this list."

    if pick_name == "bulk_pick":
        if store_type == "wholesale_club":
            return "Best fit for bulk staples and pantry-heavy shopping."
        if store_type == "supermarket":
            return "Best fallback when you want a larger pantry-friendly trip without a club store."
        return "Can handle a larger shopping trip when bulk options are limited."

    if profile["budget_friendly"]:
        return "General fit for a budget-oriented list."
    return "General nearby fit for this list."


def _group_pick_score(
    pick_name: str,
    entry: dict[str, object],
    profile: dict[str, bool],
    *,
    shopping_mode: str,
) -> float:
    score = float(entry["score"])
    store_type = str(entry["store_type"])
    brand = entry["brand"]
    source = str(entry["source"])

    if pick_name == "one_stop_pick":
        if store_type == "supermarket":
            score += 2.8
        elif store_type == "wholesale_club":
            score += 1.8
        elif store_type == "grocery":
            score += 0.9
        else:
            score += 0.5
        if profile["staple_heavy"] and store_type in {"supermarket", "wholesale_club"}:
            score += 0.9
        if profile["produce_heavy"] and store_type in {"supermarket", "grocery", "specialty_grocery"}:
            score += 0.7
        if brand in VALUE_BRANDS:
            score += 0.35
    elif pick_name == "budget_pick":
        if store_type == "wholesale_club":
            score += 3.6
        elif store_type == "supermarket":
            score += 1.4
        elif store_type == "grocery":
            score += 0.5
        else:
            score -= 0.3
        if brand in VALUE_BRANDS:
            score += 1.8
        if not profile["budget_friendly"] and not profile["staple_heavy"] and shopping_mode != "bulk":
            score -= 0.6
    elif pick_name == "produce_pick":
        if store_type == "specialty_grocery":
            score += 3.2
        elif store_type == "grocery":
            score += 2.5
        elif store_type == "supermarket":
            score += 1.9
        else:
            score -= 0.4
        if brand in SPECIALTY_BRANDS:
            score += 1.4
        if profile["produce_heavy"] or profile["plant_forward"]:
            score += 0.8
    elif pick_name == "bulk_pick":
        if store_type == "wholesale_club":
            score += 4.0
        elif store_type == "supermarket":
            score += 1.5
        elif store_type == "grocery":
            score += 0.2
        else:
            score -= 0.5
        if brand in VALUE_BRANDS:
            score += 1.1
        if shopping_mode == "bulk" or profile["staple_heavy"]:
            score += 0.8

    if source.startswith("foursquare"):
        score += 0.05
    return score


def _should_include_group_pick(
    pick_name: str,
    ranked_entries: Sequence[dict[str, object]],
    profile: dict[str, bool],
    *,
    shopping_mode: str,
) -> bool:
    if not ranked_entries:
        return False
    if pick_name == "one_stop_pick":
        return True
    if pick_name == "budget_pick":
        return (
            profile["budget_friendly"]
            or profile["staple_heavy"]
            or shopping_mode == "bulk"
            or any(entry["store_type"] == "wholesale_club" for entry in ranked_entries)
            or any(entry["brand"] in VALUE_BRANDS for entry in ranked_entries)
        )
    if pick_name == "produce_pick":
        return (
            profile["produce_heavy"]
            or profile["plant_forward"]
            or any(entry["store_type"] in {"grocery", "specialty_grocery"} for entry in ranked_entries)
            or any(entry["brand"] in SPECIALTY_BRANDS for entry in ranked_entries)
        )
    if pick_name == "bulk_pick":
        return (
            shopping_mode == "bulk"
            or profile["staple_heavy"]
            or any(entry["store_type"] == "wholesale_club" for entry in ranked_entries)
        )
    return False


def _build_grouped_pick(
    pick_name: str,
    ranked_entries: Sequence[dict[str, object]],
    profile: dict[str, bool],
    *,
    shopping_mode: str,
) -> dict[str, object] | None:
    if not _should_include_group_pick(pick_name, ranked_entries, profile, shopping_mode=shopping_mode):
        return None

    best_entry = min(
        ranked_entries,
        key=lambda entry: (
            -_group_pick_score(pick_name, entry, profile, shopping_mode=shopping_mode),
            float(entry["store"].get("distance_m") or 0.0),
            str(entry["store"].get("name") or ""),
        ),
    )
    store = best_entry["store"]
    return {
        "store_id": str(store["store_id"]),
        "store_name": str(store["name"]),
        "category": str(store.get("category") or ""),
        "distance_m": float(store.get("distance_m") or 0.0),
        "note": _pick_note(pick_name, best_entry, profile),
    }


def recommend_store_fits(
    stores: Sequence[dict[str, object]],
    shopping_list: Sequence[dict[str, object]],
    *,
    preferences: dict[str, object] | None = None,
    days: int = 1,
    shopping_mode: str = "balanced",
) -> dict[str, object]:
    if not stores:
        return {
            "recommended_store_order": [],
            "store_fit_notes": [],
            **{pick_name: None for pick_name in GROUPED_PICK_FIELDS},
        }

    profile = _basket_profile(shopping_list, preferences or {}, days=days, shopping_mode=shopping_mode)
    ranked_entries = _build_ranked_entries(stores, profile, shopping_mode=shopping_mode)
    ordered_stores = [entry["store"] for entry in ranked_entries]
    notes: list[dict[str, object]] = []
    for entry in ranked_entries[: min(3, len(ranked_entries))]:
        store = entry["store"]
        reasons = entry["reasons"]
        note = reasons[0] if reasons else "Reasonable fit for a mixed grocery basket."
        notes.append(
            {
                "store_id": str(store["store_id"]),
                "store_name": str(store["name"]),
                "category": str(store.get("category") or ""),
                "distance_m": float(store.get("distance_m") or 0.0),
                "fit_label": _fit_label(str(entry["store_type"]), profile),
                "note": note,
            }
        )

    grouped_picks = {
        pick_name: _build_grouped_pick(pick_name, ranked_entries, profile, shopping_mode=shopping_mode)
        for pick_name in GROUPED_PICK_FIELDS
    }

    return {
        "recommended_store_order": [str(store["store_id"]) for store in ordered_stores],
        "store_fit_notes": notes,
        **grouped_picks,
    }
