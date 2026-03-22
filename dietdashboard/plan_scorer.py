"""Local utilities for training and applying a candidate-plan scorer."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path

from joblib import dump, load
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.feature_extraction import DictVectorizer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import Pipeline


class PlanScorerArtifactError(RuntimeError):
    """Raised when the required trained scorer artifact is missing or invalid."""


NUMERIC_FEATURES = (
    "days",
    "target_protein_g",
    "target_calorie_kcal",
    "estimated_protein_g",
    "estimated_calorie_kcal",
    "estimated_carbohydrate_g",
    "estimated_fat_g",
    "estimated_fiber_g",
    "estimated_calcium_mg",
    "estimated_iron_mg",
    "estimated_vitamin_c_mg",
    "protein_abs_gap_g",
    "calorie_abs_gap_kcal",
    "carbohydrate_abs_gap_g",
    "fat_abs_gap_g",
    "fiber_abs_gap_g",
    "calcium_abs_gap_mg",
    "iron_abs_gap_mg",
    "vitamin_c_abs_gap_mg",
    "protein_gap_ratio",
    "calorie_gap_ratio",
    "macro_gap_ratio_sum",
    "estimated_basket_cost",
    "price_per_1000_kcal",
    "price_per_100g_protein",
    "priced_item_ratio",
    "unique_ingredient_count",
    "protein_anchor_count",
    "carb_base_count",
    "produce_count",
    "calorie_booster_count",
    "food_family_diversity_count",
    "role_diversity_count",
    "repetition_penalty",
    "unrealistic_basket_penalty",
    "preference_match_score",
    "heuristic_selection_score",
    "nearby_store_count",
    "warning_count",
    "realism_note_count",
    "pantry_note_count",
    "scaling_note_count",
)
BOOLEAN_FEATURES = (
    "adjusted_by_split",
    "has_price_estimate",
    "budget_friendly_preference",
    "low_prep_preference",
    "vegetarian_preference",
    "vegan_preference",
    "dairy_free_preference",
)
CATEGORICAL_FEATURES = (
    "goal_profile",
    "shopping_mode",
    "meal_style",
)
TRAINING_METADATA_FIELDS = (
    "request_id",
    "candidate_id",
    "label_score",
)
DEFAULT_RANDOM_SEED = 42


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def default_model_dir() -> Path:
    return project_root() / "artifacts" / "plan_scorer"


def default_model_path() -> Path:
    return default_model_dir() / "plan_candidate_scorer.joblib"


def default_dataset_path() -> Path:
    return default_model_dir() / "plan_candidate_training_dataset.csv"


def default_metrics_path() -> Path:
    return default_model_dir() / "plan_candidate_training_metrics.json"


def default_feature_summary_path() -> Path:
    return default_model_dir() / "plan_candidate_feature_summary.csv"


def _safe_float(value: object) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _safe_int(value: object) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _safe_bool(value: object) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, str):
        return int(value.strip().lower() in {"1", "true", "yes"})
    return int(bool(value))


def _nutrition_value(summary: Mapping[str, object], key: str) -> float:
    return _safe_float(summary.get(key))


def extract_candidate_features(candidate: Mapping[str, object]) -> dict[str, object]:
    recommendation = candidate.get("recommendation") if isinstance(candidate.get("recommendation"), Mapping) else {}
    recommendation = recommendation if isinstance(recommendation, Mapping) else {}
    metadata = candidate.get("candidate_metadata") if isinstance(candidate.get("candidate_metadata"), Mapping) else {}
    metadata = metadata if isinstance(metadata, Mapping) else {}
    request_context = candidate.get("request_context") if isinstance(candidate.get("request_context"), Mapping) else {}
    request_context = request_context if isinstance(request_context, Mapping) else {}
    preferences = request_context.get("preferences") if isinstance(request_context.get("preferences"), Mapping) else {}
    preferences = preferences if isinstance(preferences, Mapping) else {}
    nutrition_summary = recommendation.get("nutrition_summary") if isinstance(recommendation.get("nutrition_summary"), Mapping) else {}
    nutrition_summary = nutrition_summary if isinstance(nutrition_summary, Mapping) else {}

    estimated_calories = _nutrition_value(nutrition_summary, "calorie_estimated_kcal")
    estimated_protein = _nutrition_value(nutrition_summary, "protein_estimated_g")
    basket_cost = _safe_float(recommendation.get("estimated_basket_cost"))
    priced_item_count = max(_safe_int(recommendation.get("priced_item_count")), 0)
    shopping_list = recommendation.get("shopping_list") if isinstance(recommendation.get("shopping_list"), Sequence) else []
    item_count = len(shopping_list)
    total_price = basket_cost if basket_cost > 0 else 0.0

    protein_target = _nutrition_value(nutrition_summary, "protein_target_g")
    calorie_target = _nutrition_value(nutrition_summary, "calorie_target_kcal")
    carbohydrate_target = _nutrition_value(nutrition_summary, "carbohydrate_target_g")
    fat_target = _nutrition_value(nutrition_summary, "fat_target_g")
    fiber_target = _nutrition_value(nutrition_summary, "fiber_target_g")
    calcium_target = _nutrition_value(nutrition_summary, "calcium_target_mg")
    iron_target = _nutrition_value(nutrition_summary, "iron_target_mg")
    vitamin_c_target = _nutrition_value(nutrition_summary, "vitamin_c_target_mg")

    protein_gap = abs(estimated_protein - protein_target)
    calorie_gap = abs(estimated_calories - calorie_target)
    carbohydrate_gap = abs(_nutrition_value(nutrition_summary, "carbohydrate_estimated_g") - carbohydrate_target)
    fat_gap = abs(_nutrition_value(nutrition_summary, "fat_estimated_g") - fat_target)
    fiber_gap = abs(_nutrition_value(nutrition_summary, "fiber_estimated_g") - fiber_target)
    calcium_gap = abs(_nutrition_value(nutrition_summary, "calcium_estimated_mg") - calcium_target)
    iron_gap = abs(_nutrition_value(nutrition_summary, "iron_estimated_mg") - iron_target)
    vitamin_c_gap = abs(_nutrition_value(nutrition_summary, "vitamin_c_estimated_mg") - vitamin_c_target)

    def ratio(gap: float, target: float) -> float:
        if target <= 0:
            return 0.0
        return gap / max(target, 1.0)

    features: dict[str, object] = {
        "days": _safe_int(recommendation.get("days")) or _safe_int(request_context.get("days")) or 1,
        "target_protein_g": protein_target,
        "target_calorie_kcal": calorie_target,
        "estimated_protein_g": estimated_protein,
        "estimated_calorie_kcal": estimated_calories,
        "estimated_carbohydrate_g": _nutrition_value(nutrition_summary, "carbohydrate_estimated_g"),
        "estimated_fat_g": _nutrition_value(nutrition_summary, "fat_estimated_g"),
        "estimated_fiber_g": _nutrition_value(nutrition_summary, "fiber_estimated_g"),
        "estimated_calcium_mg": _nutrition_value(nutrition_summary, "calcium_estimated_mg"),
        "estimated_iron_mg": _nutrition_value(nutrition_summary, "iron_estimated_mg"),
        "estimated_vitamin_c_mg": _nutrition_value(nutrition_summary, "vitamin_c_estimated_mg"),
        "protein_abs_gap_g": protein_gap,
        "calorie_abs_gap_kcal": calorie_gap,
        "carbohydrate_abs_gap_g": carbohydrate_gap,
        "fat_abs_gap_g": fat_gap,
        "fiber_abs_gap_g": fiber_gap,
        "calcium_abs_gap_mg": calcium_gap,
        "iron_abs_gap_mg": iron_gap,
        "vitamin_c_abs_gap_mg": vitamin_c_gap,
        "protein_gap_ratio": ratio(protein_gap, protein_target),
        "calorie_gap_ratio": ratio(calorie_gap, calorie_target),
        "macro_gap_ratio_sum": (
            ratio(carbohydrate_gap, carbohydrate_target)
            + ratio(fat_gap, fat_target)
            + ratio(fiber_gap, fiber_target)
            + ratio(calcium_gap, calcium_target)
            + ratio(iron_gap, iron_target)
            + ratio(vitamin_c_gap, vitamin_c_target)
        ),
        "estimated_basket_cost": total_price,
        "price_per_1000_kcal": total_price / max(estimated_calories / 1000.0, 0.1) if total_price > 0 else 0.0,
        "price_per_100g_protein": total_price / max(estimated_protein / 100.0, 0.1) if total_price > 0 else 0.0,
        "priced_item_ratio": priced_item_count / max(item_count, 1),
        "unique_ingredient_count": item_count,
        "protein_anchor_count": _safe_int(metadata.get("role_counts", {}).get("protein_anchor") if isinstance(metadata.get("role_counts"), Mapping) else 0),
        "carb_base_count": _safe_int(metadata.get("role_counts", {}).get("carb_base") if isinstance(metadata.get("role_counts"), Mapping) else 0),
        "produce_count": _safe_int(metadata.get("role_counts", {}).get("produce") if isinstance(metadata.get("role_counts"), Mapping) else 0),
        "calorie_booster_count": _safe_int(metadata.get("role_counts", {}).get("calorie_booster") if isinstance(metadata.get("role_counts"), Mapping) else 0),
        "food_family_diversity_count": _safe_int(metadata.get("food_family_diversity_count")),
        "role_diversity_count": _safe_int(metadata.get("role_diversity_count")),
        "repetition_penalty": _safe_float(metadata.get("repetition_penalty")),
        "unrealistic_basket_penalty": _safe_float(metadata.get("unrealistic_basket_penalty")),
        "preference_match_score": _safe_float(metadata.get("preference_match_score")),
        "heuristic_selection_score": _safe_float(metadata.get("heuristic_selection_score")),
        "nearby_store_count": _safe_int(metadata.get("nearby_store_count")),
        "warning_count": len(recommendation.get("warnings") or []),
        "realism_note_count": len(recommendation.get("realism_notes") or []),
        "pantry_note_count": len(recommendation.get("pantry_notes") or []),
        "scaling_note_count": len(recommendation.get("scaling_notes") or []),
        "adjusted_by_split": _safe_bool(recommendation.get("adjusted_by_split")),
        "has_price_estimate": _safe_bool("estimated_basket_cost" in recommendation),
        "budget_friendly_preference": _safe_bool(preferences.get("budget_friendly")),
        "low_prep_preference": _safe_bool(preferences.get("low_prep")),
        "vegetarian_preference": _safe_bool(preferences.get("vegetarian")),
        "vegan_preference": _safe_bool(preferences.get("vegan")),
        "dairy_free_preference": _safe_bool(preferences.get("dairy_free")),
        "goal_profile": str(recommendation.get("goal_profile") or request_context.get("goal_profile") or "generic_balanced"),
        "shopping_mode": str(recommendation.get("shopping_mode") or request_context.get("shopping_mode") or "balanced"),
        "meal_style": str(preferences.get("meal_style") or "any"),
    }
    return features


def heuristic_candidate_label(feature_row: Mapping[str, object]) -> float:
    score = 0.0
    score += 4.0 * max(0.0, 1.0 - _safe_float(feature_row.get("protein_gap_ratio")))
    score += 3.4 * max(0.0, 1.0 - _safe_float(feature_row.get("calorie_gap_ratio")))
    score += 1.8 * max(0.0, 1.0 - (_safe_float(feature_row.get("macro_gap_ratio_sum")) / 6.0))
    score += 0.3 * _safe_float(feature_row.get("unique_ingredient_count"))
    score += 0.25 * _safe_float(feature_row.get("food_family_diversity_count"))
    score += 0.18 * _safe_float(feature_row.get("preference_match_score"))
    score += 0.06 * _safe_float(feature_row.get("heuristic_selection_score"))
    score -= 0.38 * _safe_float(feature_row.get("repetition_penalty"))
    score -= 0.65 * _safe_float(feature_row.get("unrealistic_basket_penalty"))
    score -= 0.15 * _safe_float(feature_row.get("warning_count"))

    estimated_cost = _safe_float(feature_row.get("estimated_basket_cost"))
    if estimated_cost > 0:
        score -= 0.05 * estimated_cost
        score -= 0.03 * _safe_float(feature_row.get("price_per_1000_kcal"))
        score -= 0.025 * _safe_float(feature_row.get("price_per_100g_protein"))
    if _safe_bool(feature_row.get("budget_friendly_preference")):
        score -= 0.03 * estimated_cost
        score -= 0.05 * _safe_float(feature_row.get("price_per_1000_kcal"))
    if _safe_bool(feature_row.get("low_prep_preference")):
        score -= 0.12 * _safe_float(feature_row.get("unrealistic_basket_penalty"))
    return round(score, 6)


def available_backends() -> list[str]:
    backends: list[str] = []
    try:
        import xgboost  # noqa: F401
    except Exception:  # noqa: BLE001
        pass
    else:
        backends.append("xgboost")

    try:
        import lightgbm  # noqa: F401
    except Exception:  # noqa: BLE001
        pass
    else:
        backends.append("lightgbm")

    backends.extend(["sklearn_gradient_boosting", "sklearn_random_forest", "sklearn_ridge"])
    return backends


def resolve_backend(requested: str = "auto") -> str:
    ordered = available_backends()
    if requested == "auto":
        return ordered[0]
    if requested not in ordered:
        raise ValueError(f"Unsupported scorer backend: {requested}")
    return requested


def _make_pipeline(
    *,
    backend: str,
    learning_rate: float,
    max_depth: int,
    n_estimators: int,
    random_seed: int,
) -> Pipeline:
    backend = resolve_backend(backend)
    if backend == "xgboost":
        from xgboost import XGBRegressor

        regressor = XGBRegressor(
            learning_rate=learning_rate,
            max_depth=max_depth,
            n_estimators=n_estimators,
            random_state=random_seed,
            objective="reg:squarederror",
            verbosity=0,
        )
    elif backend == "lightgbm":
        from lightgbm import LGBMRegressor

        regressor = LGBMRegressor(
            learning_rate=learning_rate,
            max_depth=max_depth,
            n_estimators=n_estimators,
            random_state=random_seed,
            verbose=-1,
        )
    elif backend == "sklearn_gradient_boosting":
        regressor = GradientBoostingRegressor(
            learning_rate=learning_rate,
            max_depth=max_depth,
            n_estimators=n_estimators,
            random_state=random_seed,
        )
    elif backend == "sklearn_random_forest":
        regressor = RandomForestRegressor(
            max_depth=max_depth,
            n_estimators=n_estimators,
            random_state=random_seed,
            n_jobs=-1,
        )
    else:
        regressor = Ridge(alpha=max(learning_rate, 0.001), random_state=random_seed)

    return Pipeline(
        [
            ("vectorizer", DictVectorizer(sparse=False)),
            ("regressor", regressor),
        ]
    )


def _group_top1_accuracy(groups: Sequence[str], y_true: Sequence[float], y_pred: Sequence[float]) -> float:
    grouped_true: dict[str, list[tuple[float, int]]] = defaultdict(list)
    grouped_pred: dict[str, list[tuple[float, int]]] = defaultdict(list)
    for index, (group_id, truth, pred) in enumerate(zip(groups, y_true, y_pred, strict=True)):
        grouped_true[group_id].append((truth, index))
        grouped_pred[group_id].append((pred, index))
    if not grouped_true:
        return 0.0

    correct = 0
    for group_id, truth_rows in grouped_true.items():
        true_best_index = sorted(truth_rows, key=lambda row: (-row[0], row[1]))[0][1]
        pred_best_index = sorted(grouped_pred[group_id], key=lambda row: (-row[0], row[1]))[0][1]
        correct += int(true_best_index == pred_best_index)
    return correct / len(grouped_true)


def _pairwise_accuracy(groups: Sequence[str], y_true: Sequence[float], y_pred: Sequence[float]) -> float:
    grouped_indices: dict[str, list[int]] = defaultdict(list)
    for index, group_id in enumerate(groups):
        grouped_indices[group_id].append(index)

    correct = 0
    total = 0
    for indices in grouped_indices.values():
        for left in range(len(indices)):
            for right in range(left + 1, len(indices)):
                left_index = indices[left]
                right_index = indices[right]
                truth_delta = y_true[left_index] - y_true[right_index]
                if abs(truth_delta) < 1e-9:
                    continue
                pred_delta = y_pred[left_index] - y_pred[right_index]
                total += 1
                correct += int((truth_delta > 0 and pred_delta > 0) or (truth_delta < 0 and pred_delta < 0))
    if total == 0:
        return 0.0
    return correct / total


def train_model(
    rows: Sequence[Mapping[str, object]],
    *,
    backend: str = "auto",
    learning_rate: float = 0.05,
    max_depth: int = 3,
    n_estimators: int = 250,
    validation_split: float = 0.25,
    random_seed: int = DEFAULT_RANDOM_SEED,
) -> tuple[dict[str, object], dict[str, object]]:
    if not rows:
        raise ValueError("Training rows are required.")
    if not 0 < validation_split < 1:
        raise ValueError("validation_split must be between 0 and 1.")

    X = [{field: row[field] for field in (*NUMERIC_FEATURES, *BOOLEAN_FEATURES, *CATEGORICAL_FEATURES)} for row in rows]
    y = [_safe_float(row["label_score"]) for row in rows]
    groups = [str(row["request_id"]) for row in rows]

    splitter = GroupShuffleSplit(n_splits=1, test_size=validation_split, random_state=random_seed)
    train_indices, valid_indices = next(splitter.split(X, y, groups))
    X_train = [X[index] for index in train_indices]
    y_train = [y[index] for index in train_indices]
    X_valid = [X[index] for index in valid_indices]
    y_valid = [y[index] for index in valid_indices]
    groups_valid = [groups[index] for index in valid_indices]

    resolved_backend = resolve_backend(backend)
    pipeline = _make_pipeline(
        backend=resolved_backend,
        learning_rate=learning_rate,
        max_depth=max_depth,
        n_estimators=n_estimators,
        random_seed=random_seed,
    )
    pipeline.fit(X_train, y_train)
    validation_predictions = list(pipeline.predict(X_valid))

    metrics = {
        "backend": resolved_backend,
        "learning_rate": learning_rate,
        "max_depth": max_depth,
        "n_estimators": n_estimators,
        "random_seed": random_seed,
        "validation_split": validation_split,
        "row_count": len(rows),
        "request_count": len(set(groups)),
        "train_row_count": len(X_train),
        "validation_row_count": len(X_valid),
        "validation_mae": round(float(mean_absolute_error(y_valid, validation_predictions)), 6),
        "validation_rmse": round(float(mean_squared_error(y_valid, validation_predictions) ** 0.5), 6),
        "validation_r2": round(float(r2_score(y_valid, validation_predictions)), 6),
        "validation_top1_accuracy": round(float(_group_top1_accuracy(groups_valid, y_valid, validation_predictions)), 6),
        "validation_pairwise_accuracy": round(float(_pairwise_accuracy(groups_valid, y_valid, validation_predictions)), 6),
    }

    final_pipeline = _make_pipeline(
        backend=resolved_backend,
        learning_rate=learning_rate,
        max_depth=max_depth,
        n_estimators=n_estimators,
        random_seed=random_seed,
    )
    final_pipeline.fit(X, y)

    bundle = {
        "pipeline": final_pipeline,
        "backend": resolved_backend,
        "feature_fields": {
            "numeric": list(NUMERIC_FEATURES),
            "boolean": list(BOOLEAN_FEATURES),
            "categorical": list(CATEGORICAL_FEATURES),
        },
        "training_metadata_fields": list(TRAINING_METADATA_FIELDS),
        "metrics": metrics,
        "created_at": datetime.now(UTC).isoformat(),
    }
    return bundle, metrics


def score_feature_rows(bundle: Mapping[str, object], rows: Sequence[Mapping[str, object]]) -> list[float]:
    pipeline = bundle.get("pipeline")
    if pipeline is None:
        raise PlanScorerArtifactError("Loaded trained plan scorer artifact is invalid: missing fitted pipeline.")
    X = [{field: row[field] for field in (*NUMERIC_FEATURES, *BOOLEAN_FEATURES, *CATEGORICAL_FEATURES)} for row in rows]
    try:
        return [float(score) for score in pipeline.predict(X)]
    except Exception as exc:  # noqa: BLE001
        raise PlanScorerArtifactError(f"Loaded trained plan scorer artifact could not score candidate plans: {exc}") from exc


def save_bundle(bundle: Mapping[str, object], output_path: str | Path) -> Path:
    resolved = Path(output_path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    dump(dict(bundle), resolved)
    return resolved


def load_bundle(model_path: str | Path) -> dict[str, object]:
    resolved_model_path = Path(model_path)
    try:
        bundle = dict(load(resolved_model_path))
    except FileNotFoundError as exc:
        raise PlanScorerArtifactError(
            f"Required trained plan scorer artifact is missing: {resolved_model_path}"
        ) from exc
    except Exception as exc:  # noqa: BLE001
        raise PlanScorerArtifactError(
            f"Required trained plan scorer artifact could not be loaded from {resolved_model_path}: {exc}"
        ) from exc

    if bundle.get("pipeline") is None:
        raise PlanScorerArtifactError(
            f"Loaded trained plan scorer artifact is invalid: {resolved_model_path} does not contain a fitted pipeline."
        )
    return bundle


def feature_summary_rows(bundle: Mapping[str, object]) -> list[dict[str, object]]:
    pipeline = bundle.get("pipeline")
    if pipeline is None:
        return []
    vectorizer = pipeline.named_steps["vectorizer"]
    regressor = pipeline.named_steps["regressor"]
    feature_names = vectorizer.get_feature_names_out()

    rows: list[dict[str, object]] = []
    if hasattr(regressor, "feature_importances_"):
        importances = list(regressor.feature_importances_)
        ranked = sorted(zip(feature_names, importances, strict=True), key=lambda row: row[1], reverse=True)
        rows.extend({"feature_name": str(name), "importance": round(float(value), 6)} for name, value in ranked)
    elif hasattr(regressor, "coef_"):
        coefficients = getattr(regressor, "coef_")
        flattened = coefficients.tolist() if hasattr(coefficients, "tolist") else list(coefficients)
        ranked = sorted(zip(feature_names, flattened, strict=True), key=lambda row: abs(float(row[1])), reverse=True)
        rows.extend({"feature_name": str(name), "coefficient": round(float(value), 6)} for name, value in ranked)
    return rows
