function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function statusNotice(message, kind) {
  if (!message) {
    return "";
  }
  return `<div class="generic-notice ${escapeHtml(kind || "info")}">${escapeHtml(message)}</div>`;
}

/**
 * @param {HTMLElement} parent
 * @param {object} state
 */
export function StoreResults(parent, state) {
  const { stores, storeStatus, storeError, isLookingUpStores, hasLookedUpStores } = state;

  if (isLookingUpStores) {
    parent.innerHTML = `
      ${statusNotice(storeStatus || "Looking up nearby supermarkets...", "info")}
      <div class="generic-empty">Searching for nearby supermarkets. This usually takes a moment.</div>
    `;
    return;
  }

  if (storeError) {
    parent.innerHTML = `
      ${statusNotice(storeError, "error")}
      <div class="generic-empty">Check the location fields and try the store lookup again.</div>
    `;
    return;
  }

  if (!hasLookedUpStores) {
    parent.innerHTML = `
      <div class="generic-empty">
        Start with a location or preset, then use <strong>Find Nearby Supermarkets</strong> to load stores for the area.
      </div>
    `;
    return;
  }

  if (!stores.length) {
    parent.innerHTML = `
      ${statusNotice(storeStatus || "No nearby stores found.", "info")}
      <div class="generic-empty">No supermarkets were found within the current search radius. Try increasing the radius or switching to a different location.</div>
    `;
    return;
  }

  const items = stores
    .map(
      (store, index) => `
        <div class="generic-list-item">
          <div class="generic-list-header">
            <div>
              <strong>${index + 1}. ${escapeHtml(store.name)}</strong>
              <div class="generic-muted">${escapeHtml(store.address)}</div>
            </div>
            <span class="generic-badge">${Math.round(store.distance_m)} m</span>
          </div>
          <div class="generic-list-meta">
            <span><strong>Category:</strong> ${escapeHtml(store.category)}</span>
            <span><strong>Coordinates:</strong> ${escapeHtml(store.lat)}, ${escapeHtml(store.lon)}</span>
          </div>
        </div>
      `
    )
    .join("");

  parent.innerHTML = `
    ${statusNotice(storeStatus || `Loaded ${stores.length} nearby store${stores.length === 1 ? "" : "s"}.`, "success")}
    <div class="generic-list">${items}</div>
  `;
}
