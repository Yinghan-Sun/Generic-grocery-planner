function checkboxChecked(form, name) {
  const input = form.querySelector(`[name="${name}"]`);
  if (!input) {
    return false;
  }
  if (input.type === "hidden") {
    return String(input.value || "").trim().toLowerCase() === "true";
  }
  return input.checked || false;
}

function checkedValues(form, name) {
  return [...form.querySelectorAll(`[name="${name}"]:checked`)].map(input => input.value);
}

const COMMON_PANTRY_ITEMS = [
  { id: "eggs", label: "Eggs" },
  { id: "milk", label: "Milk" },
  { id: "greek_yogurt", label: "Greek yogurt" },
  { id: "oats", label: "Oats" },
  { id: "rice", label: "Rice" },
  { id: "beans", label: "Beans" },
  { id: "lentils", label: "Lentils" },
  { id: "bananas", label: "Bananas" },
  { id: "broccoli", label: "Broccoli" },
  { id: "potatoes", label: "Potatoes" },
  { id: "olive_oil", label: "Olive oil" },
  { id: "peanut_butter", label: "Peanut butter" },
  { id: "tofu", label: "Tofu" },
  { id: "chicken_breast", label: "Chicken breast" },
];

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function fieldError(state, name) {
  return state.errors?.[name] || "";
}

function generalNotice(state) {
  if (!state.formNotice?.message) {
    return "";
  }
  return `
    <div class="generic-notice ${escapeHtml(state.formNotice.kind || "info")}" role="status">
      ${escapeHtml(state.formNotice.message)}
    </div>
  `;
}

/**
 * @param {HTMLElement} parent
 * @param {object} state
 * @param {{onChange: function, onLookupStores: function, onRecommend: function, onUseMyLocation: function, onApplyPreset: function}} actions
 */
export function LocationInput(parent, state, actions) {
  const presetButtons = (state.presets || [])
    .map(
      preset => `
        <button type="button" class="generic-preset-button" data-preset-id="${escapeHtml(preset.id)}">
          ${escapeHtml(preset.label)}
        </button>
      `
    )
    .join("");

  const controlsDisabled = state.isLocating || state.isResolvingAddress || state.isLookingUpStores || state.isGeneratingRecommendations;
  const developerMode = Boolean(state.developerMode);
  const pantryCheckboxes = COMMON_PANTRY_ITEMS
    .map(
      item => `
        <label>
          <input
            name="pantry_items"
            type="checkbox"
            value="${escapeHtml(item.id)}"
            ${(state.pantry_items || []).includes(item.id) ? "checked" : ""}
          />
          ${escapeHtml(item.label)}
        </label>
      `
    )
    .join("");
  const plannerControls = developerMode
    ? `
      <details class="generic-advanced">
        <summary>Developer planner overrides</summary>
        <p class="generic-help">These controls are hidden from the normal one-click flow. Use them only when you need to inspect or compare internal hybrid-planner behavior.</p>
        <div class="generic-form-grid">
          <label>
            Learned candidates to add
            <input
              name="model_candidate_count"
              type="number"
              min="1"
              max="8"
              step="1"
              value="${escapeHtml(state.model_candidate_count)}"
            />
            <span class="generic-help">How many learned candidate baskets to add before fusion and reranking.</span>
          </label>
          <label>
            Total candidates reranked
            <input
              name="candidate_count"
              type="number"
              min="1"
              max="12"
              step="1"
              value="${escapeHtml(state.candidate_count)}"
            />
            <span class="generic-help">How many fused candidates the trained scorer reranks before choosing the final basket.</span>
          </label>
          <label>
            Candidate generator backend
            <select name="candidate_generator_backend">
              <option value="auto" ${state.candidate_generator_backend === "auto" ? "selected" : ""}>Auto</option>
              <option value="logistic_regression" ${state.candidate_generator_backend === "logistic_regression" ? "selected" : ""}>Logistic regression</option>
              <option value="random_forest" ${state.candidate_generator_backend === "random_forest" ? "selected" : ""}>Random forest</option>
              <option value="hist_gradient_boosting" ${state.candidate_generator_backend === "hist_gradient_boosting" ? "selected" : ""}>HistGradientBoosting</option>
            </select>
            <span class="generic-help">Choose a backend only when comparing internal candidate-generator artifacts.</span>
          </label>
        </div>
        <div class="generic-checkboxes" style="margin-top: 0.75rem">
          <label>
            <input name="enable_model_candidates" type="checkbox" ${state.enable_model_candidates ? "checked" : ""} />
            Enable learned candidates
          </label>
          <label>
            <input name="debug_candidate_generation" type="checkbox" ${state.debug_candidate_generation ? "checked" : ""} />
            Show candidate-generation debug
          </label>
          <label>
            <input name="debug_scorer" type="checkbox" ${state.debug_scorer ? "checked" : ""} />
            Show scorer debug
          </label>
        </div>
      </details>
    `
    : `
      <div class="generic-list-item" style="margin-top: 1rem">
        <div class="generic-inline-group">
          <h3>How recommendations run</h3>
          <span class="generic-badge">Automatic hybrid pipeline</span>
        </div>
        <p class="generic-help">Click Recommend once and the app automatically runs heuristic candidate generation, learned candidate generation, candidate fusion, trained scorer reranking, and nearby store-fit ranking.</p>
        <input name="enable_model_candidates" type="hidden" value="true" />
        <input name="model_candidate_count" type="hidden" value="${escapeHtml(state.model_candidate_count)}" />
        <input name="candidate_generator_backend" type="hidden" value="${escapeHtml(state.candidate_generator_backend)}" />
        <input name="debug_candidate_generation" type="hidden" value="false" />
        <input name="debug_scorer" type="hidden" value="false" />
        <input name="candidate_count" type="hidden" value="${escapeHtml(state.candidate_count)}" />
      </div>
    `;

  parent.innerHTML = `
    <form id="generic-input-form" novalidate>
      ${generalNotice(state)}
      <div>
        <h3>Goal Presets</h3>
        <p class="generic-help">Start from a common goal or dietary preset, then fine-tune the everyday planning details if needed.</p>
        <div class="generic-presets">${presetButtons}</div>
      </div>

      <div class="generic-form-grid">
        <label class="generic-span-full">
          City or address
          <input
            name="locationQuery"
            type="text"
            placeholder="Mountain View, CA"
            value="${escapeHtml(state.locationQuery)}"
            aria-invalid="${fieldError(state, "locationQuery") ? "true" : "false"}"
          />
          <span class="generic-field-error">${escapeHtml(fieldError(state, "locationQuery"))}</span>
          <span class="generic-help">The app will geocode this into coordinates before store lookup or shopping-list generation.</span>
        </label>
      </div>

      <div class="generic-form-grid">
        <div class="generic-span-full">
          <h3>Daily targets</h3>
          <p class="generic-help">Calories and protein remain the main drivers. Carbs fat and fiber help shape the basket without turning this into a full nutrition optimizer.</p>
        </div>
        <label>
          Days
          <select name="days">
            <option value="1" ${state.days === "1" ? "selected" : ""}>1 day</option>
            <option value="3" ${state.days === "3" ? "selected" : ""}>3 days</option>
            <option value="5" ${state.days === "5" ? "selected" : ""}>5 days</option>
            <option value="7" ${state.days === "7" ? "selected" : ""}>7 days</option>
          </select>
          <span class="generic-help">Daily targets stay the same. Quantities are scaled for the selected shopping window.</span>
        </label>
        <label>
          Shopping mode
          <select name="shopping_mode">
            <option value="balanced" ${state.shopping_mode === "balanced" ? "selected" : ""}>Balanced</option>
            <option value="fresh" ${state.shopping_mode === "fresh" ? "selected" : ""}>Fresh</option>
            <option value="bulk" ${state.shopping_mode === "bulk" ? "selected" : ""}>Bulk</option>
          </select>
          <span class="generic-help">Fresh keeps perishables tighter. Bulk leans harder into pantry-friendly buys.</span>
        </label>
        <label>
          Calories (kcal)
          <input
            name="calories"
            type="number"
            min="1"
            step="1"
            value="${escapeHtml(state.calories)}"
            aria-invalid="${fieldError(state, "calories") ? "true" : "false"}"
            required
          />
          <span class="generic-field-error">${escapeHtml(fieldError(state, "calories"))}</span>
        </label>
        <label>
          Protein (g)
          <input
            name="protein"
            type="number"
            min="1"
            step="1"
            value="${escapeHtml(state.protein)}"
            aria-invalid="${fieldError(state, "protein") ? "true" : "false"}"
            required
          />
          <span class="generic-field-error">${escapeHtml(fieldError(state, "protein"))}</span>
        </label>
        <label>
          Carbs (g)
          <input
            name="carbohydrate"
            type="number"
            min="1"
            step="1"
            value="${escapeHtml(state.carbohydrate)}"
            aria-invalid="${fieldError(state, "carbohydrate") ? "true" : "false"}"
          />
          <span class="generic-field-error">${escapeHtml(fieldError(state, "carbohydrate"))}</span>
        </label>
        <label>
          Fat (g)
          <input
            name="fat"
            type="number"
            min="1"
            step="1"
            value="${escapeHtml(state.fat)}"
            aria-invalid="${fieldError(state, "fat") ? "true" : "false"}"
          />
          <span class="generic-field-error">${escapeHtml(fieldError(state, "fat"))}</span>
        </label>
        <label>
          Fiber (g)
          <input
            name="fiber"
            type="number"
            min="1"
            step="1"
            value="${escapeHtml(state.fiber)}"
            aria-invalid="${fieldError(state, "fiber") ? "true" : "false"}"
          />
          <span class="generic-field-error">${escapeHtml(fieldError(state, "fiber"))}</span>
        </label>
      </div>

      <div class="generic-form-grid">
        <div class="generic-span-full">
          <h3>Food preferences</h3>
          <label style="display: block; margin-bottom: 0.75rem">
            Meal or use case
            <select name="meal_style">
              <option value="any" ${state.meal_style === "any" ? "selected" : ""}>Any</option>
              <option value="breakfast" ${state.meal_style === "breakfast" ? "selected" : ""}>Breakfast</option>
              <option value="lunch_dinner" ${state.meal_style === "lunch_dinner" ? "selected" : ""}>Lunch / dinner</option>
              <option value="snack" ${state.meal_style === "snack" ? "selected" : ""}>Snack</option>
            </select>
          </label>
          <p class="generic-help">Dietary goals like Vegan, Dairy-free, and Budget-Friendly Healthy now live in Goal Presets. Recommendations stay generic and do not depend on exact store inventory or branded products.</p>
        </div>
      </div>

      <div class="generic-form-grid">
        <div class="generic-span-full">
          <h3>Already have</h3>
          <p class="generic-help">Mark common items already in your pantry or fridge. The shopping list will reduce or omit them where the basket still works.</p>
          <div class="generic-checkboxes">
            ${pantryCheckboxes}
          </div>
        </div>
      </div>

      ${plannerControls}

      <div class="generic-actions">
        <button type="button" id="use-location-button" ${controlsDisabled ? "disabled" : ""}>
          ${state.isLocating ? "Locating..." : "Use My Location"}
        </button>
        <button type="button" id="lookup-stores-button" ${controlsDisabled ? "disabled" : ""}>
          ${state.isResolvingAddress || state.isLookingUpStores ? "Looking Up..." : "Find Nearby Supermarkets"}
        </button>
        <button type="submit" ${controlsDisabled ? "disabled" : ""}>
          ${state.isResolvingAddress || state.isGeneratingRecommendations ? "Generating..." : "Recommend"}
        </button>
      </div>

      <details class="generic-advanced">
        <summary>Advanced location settings</summary>
        <div class="generic-form-grid">
          <label>
            Latitude
            <input
              name="lat"
              type="number"
              step="any"
              value="${escapeHtml(state.lat)}"
              aria-invalid="${fieldError(state, "lat") ? "true" : "false"}"
            />
            <span class="generic-field-error">${escapeHtml(fieldError(state, "lat"))}</span>
          </label>
          <label>
            Longitude
            <input
              name="lon"
              type="number"
              step="any"
              value="${escapeHtml(state.lon)}"
              aria-invalid="${fieldError(state, "lon") ? "true" : "false"}"
            />
            <span class="generic-field-error">${escapeHtml(fieldError(state, "lon"))}</span>
          </label>
          <label>
            Search radius (m)
            <input name="radius_m" type="number" min="1" step="100" value="${escapeHtml(state.radius_m)}" required />
            <span class="generic-help">How far to search for supermarkets around the selected point.</span>
          </label>
          <label>
            Nearby stores to show
            <input name="store_limit" type="number" min="1" max="25" step="1" value="${escapeHtml(state.store_limit)}" required />
            <span class="generic-help">The list is always sorted by distance.</span>
          </label>
        </div>
      </details>
    </form>
  `;

  const form = parent.querySelector("#generic-input-form");
  const syncState = () =>
    actions.onChange({
      locationQuery: form.locationQuery.value,
      lat: form.lat.value,
      lon: form.lon.value,
      radius_m: form.radius_m.value,
      store_limit: form.store_limit.value,
      days: form.days.value,
      shopping_mode: form.shopping_mode.value,
      protein: form.protein.value,
      calories: form.calories.value,
      carbohydrate: form.carbohydrate.value,
      fat: form.fat.value,
      fiber: form.fiber.value,
      meal_style: form.meal_style.value,
      enable_model_candidates: checkboxChecked(form, "enable_model_candidates"),
      model_candidate_count: form.model_candidate_count.value,
      candidate_generator_backend: form.candidate_generator_backend.value,
      debug_candidate_generation: checkboxChecked(form, "debug_candidate_generation"),
      debug_scorer: checkboxChecked(form, "debug_scorer"),
      candidate_count: form.candidate_count.value,
      pantry_items: checkedValues(form, "pantry_items")
    });

  form.addEventListener("change", syncState);
  form.addEventListener("input", syncState);
  form.addEventListener("submit", event => {
    event.preventDefault();
    syncState();
    actions.onRecommend();
  });

  parent.querySelector("#lookup-stores-button").addEventListener("click", () => {
    syncState();
    actions.onLookupStores();
  });

  parent.querySelector("#use-location-button").addEventListener("click", () => {
    syncState();
    actions.onUseMyLocation();
  });

  parent.querySelectorAll("[data-preset-id]").forEach(button => {
    button.addEventListener("click", () => {
      actions.onApplyPreset(button.dataset.presetId);
    });
  });
}
