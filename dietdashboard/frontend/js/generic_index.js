import { LocationInput } from "./components/location_input";
import { buildFullPlanExport, buildShoppingListExport, GenericResults } from "./components/generic_results";
import { StoreResults } from "./components/store_results";

const NOMINATIM_URL = "https://nominatim.openstreetmap.org/search";
const DEFAULT_SCORER_CANDIDATE_COUNT = 6;
const DEFAULT_MODEL_CANDIDATE_COUNT = 4;
const DEFAULT_CANDIDATE_GENERATOR_BACKEND = "random_forest";
const ALLOWED_CANDIDATE_GENERATOR_BACKENDS = new Set([
  "auto",
  "logistic_regression",
  "random_forest",
  "hist_gradient_boosting"
]);

const GOAL_PRESETS = [
  {
    id: "muscle_gain",
    label: "Muscle Gain",
    values: {
      locationQuery: "Mountain View, CA",
      lat: "",
      lon: "",
      radius_m: "8000",
      store_limit: "5",
      days: "1",
      shopping_mode: "balanced",
      protein: "170",
      calories: "2800",
      carbohydrate: "330",
      fat: "85",
      fiber: "35",
      calcium: "",
      iron: "",
      vitamin_c: "",
      vegetarian: false,
      dairy_free: false,
      vegan: false,
      low_prep: false,
      budget_friendly: false,
      meal_style: "any"
    },
    notice: 'Loaded the muscle gain preset for "Mountain View, CA".'
  },
  {
    id: "fat_loss",
    label: "Fat Loss",
    values: {
      locationQuery: "Mountain View, CA",
      lat: "",
      lon: "",
      radius_m: "8000",
      store_limit: "5",
      days: "1",
      shopping_mode: "balanced",
      protein: "150",
      calories: "1800",
      carbohydrate: "160",
      fat: "55",
      fiber: "30",
      calcium: "",
      iron: "",
      vitamin_c: "",
      vegetarian: false,
      dairy_free: false,
      vegan: false,
      low_prep: false,
      budget_friendly: false,
      meal_style: "any"
    },
    notice: 'Loaded the fat loss preset for "Mountain View, CA".'
  },
  {
    id: "maintenance",
    label: "Maintenance",
    values: {
      locationQuery: "Mountain View, CA",
      lat: "",
      lon: "",
      radius_m: "8000",
      store_limit: "5",
      days: "1",
      shopping_mode: "balanced",
      protein: "130",
      calories: "2200",
      carbohydrate: "240",
      fat: "70",
      fiber: "30",
      calcium: "",
      iron: "",
      vitamin_c: "",
      vegetarian: false,
      dairy_free: false,
      vegan: false,
      low_prep: false,
      budget_friendly: false,
      meal_style: "any"
    },
    notice: 'Loaded the maintenance preset for "Mountain View, CA".'
  },
  {
    id: "high_protein_vegetarian",
    label: "High-Protein Vegetarian",
    values: {
      locationQuery: "Mountain View, CA",
      lat: "",
      lon: "",
      radius_m: "8000",
      store_limit: "5",
      days: "1",
      shopping_mode: "balanced",
      protein: "140",
      calories: "2100",
      carbohydrate: "220",
      fat: "70",
      fiber: "32",
      calcium: "",
      iron: "18",
      vitamin_c: "",
      vegetarian: true,
      dairy_free: false,
      vegan: false,
      low_prep: false,
      budget_friendly: false,
      meal_style: "any"
    },
    notice: 'Loaded the high-protein vegetarian preset for "Mountain View, CA".'
  },
  {
    id: "budget_friendly_healthy",
    label: "Budget-Friendly Healthy",
    values: {
      locationQuery: "Mountain View, CA",
      lat: "",
      lon: "",
      radius_m: "8000",
      store_limit: "5",
      days: "1",
      shopping_mode: "balanced",
      protein: "120",
      calories: "2100",
      carbohydrate: "230",
      fat: "65",
      fiber: "35",
      calcium: "",
      iron: "",
      vitamin_c: "",
      vegetarian: false,
      dairy_free: false,
      vegan: false,
      low_prep: false,
      budget_friendly: true,
      meal_style: "any"
    },
    notice: 'Loaded the budget-friendly healthy preset for "Mountain View, CA".'
  }
];

function frontendAppConfig() {
  if (typeof window === "undefined") {
    return {};
  }
  return window.GENERIC_APP_CONFIG || {};
}

function developerModeEnabled() {
  return Boolean(frontendAppConfig().developerMode);
}

function hybridPlannerDefaults() {
  const defaults = frontendAppConfig().hybridPlannerDefaults || {};
  return {
    candidateCount: Number(defaults.candidateCount || DEFAULT_SCORER_CANDIDATE_COUNT),
    modelCandidateCount: Number(defaults.modelCandidateCount || DEFAULT_MODEL_CANDIDATE_COUNT),
    candidateGeneratorBackend: String(defaults.candidateGeneratorBackend || DEFAULT_CANDIDATE_GENERATOR_BACKEND)
  };
}

function defaultPlannerState() {
  const defaults = hybridPlannerDefaults();
  return {
    developerMode: developerModeEnabled(),
    enable_model_candidates: true,
    model_candidate_count: String(defaults.modelCandidateCount),
    candidate_generator_backend: defaults.candidateGeneratorBackend,
    debug_candidate_generation: false,
    debug_scorer: false,
    candidate_count: String(defaults.candidateCount)
  };
}

const state = {
  locationQuery: "Mountain View, CA",
  lat: "",
  lon: "",
  radius_m: "8000",
  store_limit: "5",
  days: "1",
  shopping_mode: "balanced",
  protein: "130",
  calories: "2200",
  carbohydrate: "240",
  fat: "70",
  fiber: "30",
  calcium: "",
  iron: "",
  vitamin_c: "",
  vegetarian: false,
  dairy_free: false,
  vegan: false,
  low_prep: false,
  budget_friendly: false,
  meal_style: "any",
  ...defaultPlannerState(),
  pantry_items: [],
  stores: [],
  storesLookupContext: null,
  recommendation: null,
  errors: {},
  formNotice: null,
  storeStatus: "",
  storeError: "",
  recommendationStatus: "",
  recommendationError: "",
  exportNotice: null,
  isLookingUpStores: false,
  isGeneratingRecommendations: false,
  isLocating: false,
  isResolvingAddress: false,
  hasLookedUpStores: false,
  hasRequestedRecommendation: false,
  presets: GOAL_PRESETS
};

function parseNumber(value) {
  if (value === null || value === undefined || String(value).trim() === "") {
    return null;
  }
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

export function parseBooleanParam(value) {
  if (value === "true") {
    return true;
  }
  if (value === "false") {
    return false;
  }
  return undefined;
}

export function parsePositiveIntParam(value) {
  if (value === null || value === undefined || String(value).trim() === "") {
    return undefined;
  }
  const parsed = Number.parseInt(String(value), 10);
  if (!Number.isFinite(parsed) || parsed <= 0) {
    return undefined;
  }
  return parsed;
}

function parseChoiceParam(value, allowed) {
  if (value === null || value === undefined || String(value).trim() === "") {
    return undefined;
  }
  const normalized = String(value).trim().toLowerCase();
  return allowed.has(normalized) ? normalized : undefined;
}

function currentLocationSearch() {
  if (typeof window === "undefined" || !window.location || typeof window.location.search !== "string") {
    return "";
  }
  return window.location.search;
}

export function getScorerQueryOverrides(search = currentLocationSearch()) {
  if (!developerModeEnabled()) {
    return {};
  }
  const params = new URLSearchParams(search || "");
  const overrides = {};

  const enableModelCandidates = parseBooleanParam(params.get("enable_model_candidates"));
  if (enableModelCandidates !== undefined) {
    overrides.enable_model_candidates = enableModelCandidates;
  }

  const modelCandidateCount = parsePositiveIntParam(params.get("model_candidate_count"));
  if (modelCandidateCount !== undefined) {
    overrides.model_candidate_count = modelCandidateCount;
  }

  const candidateGeneratorBackend = parseChoiceParam(
    params.get("candidate_generator_backend"),
    ALLOWED_CANDIDATE_GENERATOR_BACKENDS
  );
  if (candidateGeneratorBackend !== undefined) {
    overrides.candidate_generator_backend = candidateGeneratorBackend;
  }

  const debugCandidateGeneration = parseBooleanParam(params.get("debug_candidate_generation"));
  if (debugCandidateGeneration !== undefined) {
    overrides.debug_candidate_generation = debugCandidateGeneration;
  }

  const debugScorer = parseBooleanParam(params.get("debug_scorer"));
  if (debugScorer !== undefined) {
    overrides.debug_scorer = debugScorer;
  }

  const candidateCount = parsePositiveIntParam(params.get("candidate_count"));
  if (candidateCount !== undefined) {
    overrides.candidate_count = candidateCount;
  }

  const scorerModelPath = String(params.get("scorer_model_path") || "").trim();
  if (scorerModelPath) {
    overrides.scorer_model_path = scorerModelPath;
  }

  const candidateGeneratorModelPath = String(params.get("candidate_generator_model_path") || "").trim();
  if (candidateGeneratorModelPath) {
    overrides.candidate_generator_model_path = candidateGeneratorModelPath;
  }

  return overrides;
}

Object.assign(state, getScorerQueryOverrides());

function hasValidCoordinates(currentState) {
  const lat = parseNumber(currentState.lat);
  const lon = parseNumber(currentState.lon);
  return lat !== null && lon !== null && lat >= -90 && lat <= 90 && lon >= -180 && lon <= 180;
}

function storeLookupContext(currentState) {
  const lat = parseNumber(currentState.lat);
  const lon = parseNumber(currentState.lon);
  const radius = parseNumber(currentState.radius_m);
  if (lat === null || lon === null || radius === null) {
    return null;
  }
  return {
    lat: Number(lat.toFixed(6)),
    lon: Number(lon.toFixed(6)),
    radius_m: Math.round(radius)
  };
}

function sameStoreLookupContext(first, second) {
  if (!first || !second) {
    return false;
  }
  return first.lat === second.lat && first.lon === second.lon && first.radius_m === second.radius_m;
}

export function buildRecommendationPayload(currentState, search = currentLocationSearch()) {
  const payload = {
    location: {
      lat: Number(currentState.lat),
      lon: Number(currentState.lon)
    },
    targets: {
      protein: Number(currentState.protein),
      energy_fibre_kcal: Number(currentState.calories)
    },
    preferences: {
      vegetarian: currentState.vegetarian,
      dairy_free: currentState.dairy_free,
      vegan: currentState.vegan,
      low_prep: currentState.low_prep,
      budget_friendly: currentState.budget_friendly,
      meal_style: currentState.meal_style || "any"
    },
    pantry_items: Array.isArray(currentState.pantry_items) ? currentState.pantry_items : [],
    store_limit: Number(currentState.store_limit),
    days: Number(currentState.days || 1),
    shopping_mode: currentState.shopping_mode || "balanced"
  };

  const currentStoreContext = storeLookupContext(currentState);
  if (
    currentState.hasLookedUpStores &&
    Array.isArray(currentState.stores) &&
    currentState.stores.length &&
    currentState.stores.length >= Number(currentState.store_limit) &&
    sameStoreLookupContext(currentState.storesLookupContext, currentStoreContext)
  ) {
    payload.stores = currentState.stores.slice(0, Number(currentState.store_limit));
  }

  for (const [fieldName, value] of Object.entries({
    carbohydrate: parseNumber(currentState.carbohydrate),
    fat: parseNumber(currentState.fat),
    fiber: parseNumber(currentState.fiber),
    calcium: parseNumber(currentState.calcium),
    iron: parseNumber(currentState.iron),
    vitamin_c: parseNumber(currentState.vitamin_c)
  })) {
    if (value !== null) {
      payload.targets[fieldName] = value;
    }
  }

  if (developerModeEnabled()) {
    const defaults = hybridPlannerDefaults();
    payload.enable_model_candidates = Boolean(currentState.enable_model_candidates);
    payload.model_candidate_count = Number(currentState.model_candidate_count || defaults.modelCandidateCount);
    payload.candidate_generator_backend = currentState.candidate_generator_backend || defaults.candidateGeneratorBackend;
    payload.debug_candidate_generation = Boolean(currentState.debug_candidate_generation);
    payload.debug_scorer = Boolean(currentState.debug_scorer);
    payload.candidate_count = Number(currentState.candidate_count || defaults.candidateCount);
    Object.assign(payload, getScorerQueryOverrides(search));
  }
  return payload;
}

export function validateFormState(currentState, mode = "recommend") {
  const errors = {};
  const locationQuery = String(currentState.locationQuery || "").trim();
  const lat = parseNumber(currentState.lat);
  const lon = parseNumber(currentState.lon);
  const protein = parseNumber(currentState.protein);
  const calories = parseNumber(currentState.calories);
  const optionalTargets = [
    ["carbohydrate", "carbohydrate"],
    ["fat", "fat"],
    ["fiber", "fiber"],
    ["calcium", "calcium"],
    ["iron", "iron"],
    ["vitamin_c", "vitamin C"]
  ];
  const hasCoords = hasValidCoordinates(currentState);

  if (!locationQuery && !hasCoords) {
    errors.locationQuery = "Enter a city or address, or provide coordinates in Advanced location settings.";
  }

  if (!locationQuery) {
    if (lat === null || lat < -90 || lat > 90) {
      errors.lat = "Enter a latitude between -90 and 90.";
    }
    if (lon === null || lon < -180 || lon > 180) {
      errors.lon = "Enter a longitude between -180 and 180.";
    }
  }

  if (mode === "recommend") {
    if (protein === null || protein <= 0) {
      errors.protein = "Enter a protein target greater than 0.";
    }
    if (calories === null || calories <= 0) {
      errors.calories = "Enter a calorie target greater than 0.";
    }
    for (const [fieldName, label] of optionalTargets) {
      const value = parseNumber(currentState[fieldName]);
      if (value !== null && value <= 0) {
        errors[fieldName] = `Enter a ${label} target greater than 0, or leave it blank.`;
      }
    }
  }

  return errors;
}

export async function geocodeAddress(query, fetchImpl = fetch) {
  const trimmedQuery = String(query || "").trim();
  if (!trimmedQuery) {
    throw new Error("Enter a city or address first.");
  }

  const params = new URLSearchParams({
    q: trimmedQuery,
    format: "jsonv2",
    limit: "1"
  });

  const response = await fetchImpl(`${NOMINATIM_URL}?${params.toString()}`, {
    headers: { Accept: "application/json" }
  });

  if (!response.ok) {
    throw new Error("Location search failed. Please try again.");
  }

  const results = await response.json();
  if (!Array.isArray(results) || results.length === 0) {
    throw new Error("Could not find that location. Please try a different city or address.");
  }

  const match = results[0];
  return {
    lat: Number(match.lat).toFixed(6),
    lon: Number(match.lon).toFixed(6),
    displayName: match.display_name || trimmedQuery
  };
}

function setFormNotice(message, kind = "info") {
  state.formNotice = message ? { message, kind } : null;
}

function setExportNotice(message, kind = "info") {
  state.exportNotice = message ? { message, kind } : null;
}

function updateState(nextState) {
  Object.assign(state, nextState);
  for (const key of Object.keys(nextState)) {
    if (state.errors[key]) {
      delete state.errors[key];
    }
  }
}

function applyValidation(mode) {
  const errors = validateFormState(state, mode);
  state.errors = errors;
  if (Object.keys(errors).length) {
    setFormNotice("Fix the highlighted fields before continuing.", "error");
    render();
    return false;
  }
  if (state.formNotice?.kind === "error") {
    setFormNotice(null);
  }
  return true;
}

function resetDerivedState() {
  state.stores = [];
  state.storesLookupContext = null;
  state.recommendation = null;
  state.storeStatus = "";
  state.storeError = "";
  state.recommendationStatus = "";
  state.recommendationError = "";
  state.exportNotice = null;
  state.hasLookedUpStores = false;
  state.hasRequestedRecommendation = false;
}

async function ensureCoordinates() {
  const locationQuery = String(state.locationQuery || "").trim();
  if (!locationQuery) {
    return hasValidCoordinates(state);
  }

  state.isResolvingAddress = true;
  setFormNotice(`Finding coordinates for "${locationQuery}"...`, "info");
  render();

  try {
    const match = await geocodeAddress(locationQuery);
    state.lat = match.lat;
    state.lon = match.lon;
    delete state.errors.locationQuery;
    delete state.errors.lat;
    delete state.errors.lon;
    setFormNotice(`Using coordinates for "${locationQuery}". Advanced settings were updated automatically.`, "success");
    return true;
  } catch (error) {
    state.errors.locationQuery = error.message || "Could not find that location. Please try a different city or address.";
    setFormNotice(state.errors.locationQuery, "error");
    render();
    return false;
  } finally {
    state.isResolvingAddress = false;
  }
}

async function fetchNearbyStores() {
  if (!applyValidation("stores")) {
    return;
  }

  const hasCoordinates = await ensureCoordinates();
  if (!hasCoordinates) {
    return;
  }

  state.hasLookedUpStores = true;
  state.storeError = "";
  state.storeStatus = "Looking up nearby supermarkets...";
  state.isLookingUpStores = true;
  render();

  const params = new URLSearchParams({
    lat: state.lat,
    lon: state.lon,
    radius_m: state.radius_m,
    limit: state.store_limit
  });

  try {
    const response = await fetch(`/api/stores/nearby?${params.toString()}`);
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || "Store lookup failed.");
    }
    state.stores = data.stores || [];
    state.storesLookupContext = storeLookupContext(state);
    state.storeStatus = state.stores.length
      ? `Loaded ${state.stores.length} nearby supermarket${state.stores.length === 1 ? "" : "s"}.`
      : "No nearby supermarkets found for this location.";
    if (state.recommendation && !state.recommendation.stores?.length) {
      state.recommendation.stores = state.stores;
    }
  } catch (error) {
    state.stores = [];
    state.storeError = error.message || "Store lookup failed.";
    state.storeStatus = "";
  } finally {
    state.isLookingUpStores = false;
  }

  render();
}

async function fetchRecommendations() {
  if (!applyValidation("recommend")) {
    return;
  }

  const hasCoordinates = await ensureCoordinates();
  if (!hasCoordinates) {
    return;
  }

  state.hasRequestedRecommendation = true;
  state.recommendation = null;
  state.recommendationError = "";
  state.recommendationStatus = "Generating recommendations...";
  state.exportNotice = null;
  state.isGeneratingRecommendations = true;
  render();

  const currentStoreContext = storeLookupContext(state);
  const payload = buildRecommendationPayload(state);

  try {
    const response = await fetch("/api/recommendations/generic", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || "Recommendation request failed.");
    }
    state.recommendation = data;
    state.stores = data.stores || [];
    state.storesLookupContext = state.stores.length ? currentStoreContext : null;
    state.hasLookedUpStores = true;
    state.storeError = "";
    state.storeStatus = state.stores.length
      ? `Loaded ${state.stores.length} nearby supermarket${state.stores.length === 1 ? "" : "s"}.`
      : "No nearby supermarkets found for this location.";
    state.recommendationStatus = data.shopping_list?.length
      ? "Shopping list ready."
      : "No shopping list was generated for the current inputs.";
  } catch (error) {
    state.recommendation = null;
    state.recommendationError = error.message || "Recommendation request failed.";
    state.recommendationStatus = "";
  } finally {
    state.isGeneratingRecommendations = false;
  }

  render();
}

function useMyLocation() {
  if (!navigator.geolocation) {
    setFormNotice("Browser geolocation is not available here. Enter coordinates in Advanced location settings.", "error");
    render();
    return;
  }

  state.isLocating = true;
  setFormNotice("Requesting your current location...", "info");
  render();

  navigator.geolocation.getCurrentPosition(
    position => {
      state.isLocating = false;
      state.locationQuery = "";
      state.lat = position.coords.latitude.toFixed(6);
      state.lon = position.coords.longitude.toFixed(6);
      delete state.errors.locationQuery;
      delete state.errors.lat;
      delete state.errors.lon;
      setFormNotice("Location loaded from your browser. Advanced settings were updated automatically.", "success");
      render();
    },
    error => {
      state.isLocating = false;
      const messages = {
        1: "Location access was denied. Enter a city, address, or coordinates manually.",
        2: "Your location could not be determined. Enter a city, address, or coordinates manually.",
        3: "Location lookup timed out. Enter a city, address, or coordinates manually."
      };
      setFormNotice(messages[error.code] || "Location lookup failed. Enter a city, address, or coordinates manually.", "error");
      render();
    },
    { enableHighAccuracy: false, timeout: 10000, maximumAge: 300000 }
  );
}

function applyPreset(presetId) {
  const preset = GOAL_PRESETS.find(item => item.id === presetId);
  if (!preset) {
    return;
  }
  Object.assign(state, preset.values);
  state.pantry_items = Array.isArray(preset.values?.pantry_items) ? [...preset.values.pantry_items] : [];
  state.errors = {};
  resetDerivedState();
  setFormNotice(preset.notice, "success");
  render();
}

async function writeTextToClipboard(text) {
  if (!text) {
    throw new Error("There is no recommendation to export yet.");
  }

  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text);
    return;
  }

  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.setAttribute("readonly", "readonly");
  textarea.style.position = "fixed";
  textarea.style.opacity = "0";
  document.body.appendChild(textarea);
  textarea.select();
  const succeeded = document.execCommand("copy");
  document.body.removeChild(textarea);
  if (!succeeded) {
    throw new Error("Copy is not available in this browser.");
  }
}

function downloadText(filename, text) {
  if (!text) {
    throw new Error("There is no recommendation to export yet.");
  }
  const blob = new Blob([text], { type: "text/plain;charset=utf-8" });
  const href = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = href;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(href);
}

async function copyShoppingList() {
  try {
    await writeTextToClipboard(buildShoppingListExport(state.recommendation));
    setExportNotice("Copied the grouped shopping list.", "success");
  } catch (error) {
    setExportNotice(error.message || "Could not copy the shopping list.", "error");
  }
  render();
}

async function copyFullPlan() {
  try {
    await writeTextToClipboard(buildFullPlanExport(state.recommendation));
    setExportNotice("Copied the full grocery plan.", "success");
  } catch (error) {
    setExportNotice(error.message || "Could not copy the full plan.", "error");
  }
  render();
}

function downloadFullPlan() {
  try {
    downloadText("generic-grocery-plan.txt", buildFullPlanExport(state.recommendation));
    setExportNotice("Downloaded the grocery plan as text.", "success");
  } catch (error) {
    setExportNotice(error.message || "Could not download the grocery plan.", "error");
  }
  render();
}

function render() {
  LocationInput(document.getElementById("generic-form"), state, {
    onChange: updateState,
    onLookupStores: fetchNearbyStores,
    onRecommend: fetchRecommendations,
    onUseMyLocation: useMyLocation,
    onApplyPreset: applyPreset
  });
  StoreResults(document.getElementById("generic-stores"), state);
  GenericResults(document.getElementById("generic-results"), state, {
    onCopyShoppingList: copyShoppingList,
    onCopyFullPlan: copyFullPlan,
    onDownloadPlan: downloadFullPlan
  });
}

if (typeof document !== "undefined") {
  render();
}
