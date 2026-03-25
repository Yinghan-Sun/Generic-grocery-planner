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

function formatDelta(estimated, target, unit) {
  const delta = Math.round((estimated - target) * 10) / 10;
  const prefix = delta > 0 ? "+" : "";
  return `${prefix}${delta} ${unit}`;
}

function roleLabel(role) {
  const labels = {
    protein_anchor: "Protein anchor",
    carb_base: "Carb base",
    produce: "Produce",
    calorie_booster: "Calorie booster"
  };
  return labels[role] || "Recommended item";
}

function normalizeCandidateSource(source) {
  const normalized = String(source || "heuristic").trim().toLowerCase();
  if (normalized === "model" || normalized === "hybrid" || normalized === "repaired_model") {
    return normalized;
  }
  return "heuristic";
}

function candidateSourceDisplay(source) {
  const labels = {
    heuristic: "Heuristic",
    model: "Model",
    hybrid: "Hybrid",
    repaired_model: "Repaired model"
  };
  return labels[normalizeCandidateSource(source)] || "Heuristic";
}

function candidateSourceBadgeLabel(source) {
  return `${candidateSourceDisplay(source)} result`;
}

function candidateSourceBadgeClass(source) {
  return `generic-badge-source-${normalizeCandidateSource(source)}`;
}

function normalizeSourceList(values, fallbackSource) {
  const items = Array.isArray(values) ? values : [];
  const normalized = [...new Set(items.map(value => normalizeCandidateSource(value)).filter(Boolean))];
  return normalized.length ? normalized : [normalizeCandidateSource(fallbackSource)];
}

function plannerSelectionOutcome(modelCandidatesEnabled, selectedSource) {
  const normalizedSource = normalizeCandidateSource(selectedSource);
  if (!modelCandidatesEnabled) {
    return "Model path disabled; the heuristic-only baseline produced this result.";
  }
  if (normalizedSource === "heuristic") {
    return "Model path was enabled, but the highest-ranked basket still came from the heuristic pool.";
  }
  if (normalizedSource === "model") {
    return "A model-generated candidate won the final ranking.";
  }
  if (normalizedSource === "repaired_model") {
    return "A model-generated basket needed repair and still won the final ranking.";
  }
  return "A fused hybrid candidate won the final ranking.";
}

function formatFoodIdList(values) {
  const items = Array.isArray(values) ? values.filter(Boolean) : [];
  return items.length ? items.join(", ") : "Not available";
}

function formatMetricValue(value, digits = 3) {
  if (value === null || value === undefined || value === "") {
    return "Not available";
  }
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) {
    return String(value);
  }
  return numeric.toFixed(digits);
}

const ROLE_SECTIONS = [
  { role: "protein_anchor", title: "Protein picks" },
  { role: "carb_base", title: "Carb base" },
  { role: "produce", title: "Produce" },
  { role: "calorie_booster", title: "Extras / boosters" }
];
const STORE_PICK_SECTIONS = [
  { key: "one_stop_pick", title: "One-stop pick" },
  { key: "budget_pick", title: "Budget pick" },
  { key: "produce_pick", title: "Produce pick" },
  { key: "bulk_pick", title: "Bulk pick" }
];

const SUMMARY_FIELDS = [
  { label: "Protein", targetKey: "protein_target_g", estimatedKey: "protein_estimated_g", unit: "g" },
  { label: "Calories", targetKey: "calorie_target_kcal", estimatedKey: "calorie_estimated_kcal", unit: "kcal" },
  { label: "Carbs", targetKey: "carbohydrate_target_g", estimatedKey: "carbohydrate_estimated_g", unit: "g" },
  { label: "Fat", targetKey: "fat_target_g", estimatedKey: "fat_estimated_g", unit: "g" },
  { label: "Fiber", targetKey: "fiber_target_g", estimatedKey: "fiber_estimated_g", unit: "g" },
  { label: "Calcium", targetKey: "calcium_target_mg", estimatedKey: "calcium_estimated_mg", unit: "mg" },
  { label: "Iron", targetKey: "iron_target_mg", estimatedKey: "iron_estimated_mg", unit: "mg" },
  { label: "Vitamin C", targetKey: "vitamin_c_target_mg", estimatedKey: "vitamin_c_estimated_mg", unit: "mg" }
];

function roleSectionTitle(role) {
  return ROLE_SECTIONS.find(section => section.role === role)?.title || "Recommended items";
}

function formatExportMetric(summary, metric) {
  if (!summary || summary[metric.targetKey] === undefined || summary[metric.estimatedKey] === undefined) {
    return null;
  }
  return `${metric.label}: ${summary[metric.estimatedKey]} ${metric.unit} (target ${summary[metric.targetKey]} ${metric.unit})`;
}

function cleanedSubstitutionReason(item) {
  const reason = String(item?.substitution_reason || "").trim();
  const substitution = String(item?.substitution || "").trim();
  if (!reason) {
    return "";
  }
  if (!substitution) {
    return reason;
  }
  if (reason.toLowerCase().startsWith(substitution.toLowerCase())) {
    return reason.slice(substitution.length).trim();
  }
  return reason;
}

function buildGroupedShoppingLines(recommendation, includeExtras = true) {
  return ROLE_SECTIONS.map(section => {
    const items = (recommendation.shopping_list || []).filter(item => item.role === section.role);
    if (!items.length) {
      return "";
    }
    const lines = items.map(item => {
      const parts = [`- ${item.name}: ${item.quantity_display}`];
      if (includeExtras && item.reason_short) {
        parts.push(`  ${item.reason_short}`);
      }
      if (includeExtras && item.typical_item_cost !== null && item.typical_item_cost !== undefined) {
        const rangePart = item.estimated_price_low !== null && item.estimated_price_low !== undefined &&
          item.estimated_price_high !== null && item.estimated_price_high !== undefined
          ? ` (range $${item.estimated_price_low}-$${item.estimated_price_high})`
          : "";
        parts.push(`  Typical cost: $${item.typical_item_cost}${rangePart}`);
      }
      return parts.join("\n");
    });
    return `${section.title}\n${lines.join("\n")}`;
  })
    .filter(Boolean)
    .join("\n\n");
}

function buildStorePickLines(recommendation) {
  return STORE_PICK_SECTIONS.map(section => {
    const pick = recommendation?.[section.key];
    if (!pick?.store_id) {
      return null;
    }
    const distancePart = pick.distance_m !== undefined && pick.distance_m !== null ? `, about ${Math.round(Number(pick.distance_m))} m away` : "";
    return `- ${section.title}: ${pick.store_name} (${pick.category || "store"}${distancePart})${pick.note ? ` - ${pick.note}` : ""}`;
  }).filter(Boolean);
}

export function buildShoppingListExport(recommendation) {
  if (!recommendation?.shopping_list?.length) {
    return "";
  }

  const days = Number(recommendation.days || 1);
  const shoppingMode = String(recommendation.shopping_mode || "balanced");
  const lines = [
    "Generic Grocery Plan",
    `Shopping window: ${days} ${days === 1 ? "day" : "days"}`,
    `Shopping mode: ${shoppingMode}`,
    "",
    buildGroupedShoppingLines(recommendation, false)
  ];

  if (recommendation.estimated_basket_cost !== undefined) {
    lines.push("", `Estimated typical basket cost: $${recommendation.estimated_basket_cost}`);
    if (recommendation.estimated_basket_cost_low !== undefined && recommendation.estimated_basket_cost_high !== undefined) {
      lines.push(`Typical basket range: $${recommendation.estimated_basket_cost_low}-$${recommendation.estimated_basket_cost_high}`);
    }
    if (recommendation.price_adjustment_note) {
      lines.push(recommendation.price_adjustment_note);
    }
    if (recommendation.price_coverage_note) {
      lines.push(recommendation.price_coverage_note);
    }
  }

  const storePicks = buildStorePickLines(recommendation);
  if (storePicks.length) {
    lines.push("", "Recommended store picks", ...storePicks);
  }

  return lines.filter(Boolean).join("\n");
}

export function buildFullPlanExport(recommendation) {
  if (!recommendation?.shopping_list?.length) {
    return "";
  }

  const days = Number(recommendation.days || 1);
  const shoppingMode = String(recommendation.shopping_mode || "balanced");
  const summary = recommendation.nutrition_summary || {};
  const targetLines = SUMMARY_FIELDS.map(metric => formatExportMetric(summary, metric)).filter(Boolean);
  const storePicks = buildStorePickLines(recommendation);
  const lines = [
    "Generic Grocery Plan",
    `Shopping window: ${days} ${days === 1 ? "day" : "days"}`,
    `Shopping mode: ${shoppingMode}`,
  ];

  if (targetLines.length) {
    lines.push("", "Key nutrition targets", ...targetLines);
  }

  if (recommendation.estimated_basket_cost !== undefined) {
    lines.push("", `Estimated typical basket cost: $${recommendation.estimated_basket_cost}`);
    if (recommendation.estimated_basket_cost_low !== undefined && recommendation.estimated_basket_cost_high !== undefined) {
      lines.push(`Typical basket range: $${recommendation.estimated_basket_cost_low}-$${recommendation.estimated_basket_cost_high}`);
    }
    if (recommendation.price_adjustment_note) {
      lines.push(recommendation.price_adjustment_note);
    }
    if (recommendation.price_coverage_note) {
      lines.push(recommendation.price_coverage_note);
    }
    if (recommendation.basket_cost_note) {
      lines.push(recommendation.basket_cost_note);
    }
    if (recommendation.price_confidence_note) {
      lines.push(recommendation.price_confidence_note);
    }
  }

  if (storePicks.length) {
    lines.push("", "Recommended store picks", ...storePicks);
  }

  lines.push("", "Shopping list", buildGroupedShoppingLines(recommendation, true));

  if (Array.isArray(recommendation.assumptions) && recommendation.assumptions.length) {
    lines.push("", "Approximate guidance", ...recommendation.assumptions.map(text => `- ${text}`));
  }

  return lines.filter(Boolean).join("\n");
}

/**
 * @param {HTMLElement} parent
 * @param {object} state
 * @param {object} actions
 */
export function GenericResults(parent, state, actions = {}) {
  const {
    recommendation,
    recommendationStatus,
    recommendationError,
    isGeneratingRecommendations,
    hasRequestedRecommendation,
    exportNotice
  } = state;

  if (isGeneratingRecommendations) {
    parent.innerHTML = `
      ${statusNotice(recommendationStatus || "Generating recommendations...", "info")}
      <div class="generic-empty">Building a generic shopping list from the nutrition targets and food preferences.</div>
    `;
    return;
  }

  if (recommendationError) {
    parent.innerHTML = `
      ${statusNotice(recommendationError, "error")}
      <div class="generic-empty">The app could not build a shopping list for the current inputs. Adjust the targets or preferences and try again.</div>
    `;
    return;
  }

  if (!hasRequestedRecommendation) {
    parent.innerHTML = `
      <div class="generic-empty">
        Build a shopping list to see recommended food categories, rough quantities, and a simple nutrition summary.
      </div>
    `;
    return;
  }

  if (!recommendation) {
    parent.innerHTML = `
      ${statusNotice(recommendationStatus || "No recommendations available.", "info")}
      <div class="generic-empty">No shopping list could be generated from the current targets and preferences. Try lowering the targets or relaxing the filters.</div>
    `;
    return;
  }

  const summary = recommendation.nutrition_summary;
  const days = Number(recommendation.days || state.days || 1);
  const shoppingMode = String(recommendation.shopping_mode || state.shopping_mode || "balanced");
  const selectedCandidateSource = normalizeCandidateSource(recommendation.selected_candidate_source);
  const selectedCandidateSources = normalizeSourceList(recommendation.selected_candidate_sources, selectedCandidateSource);
  const candidateGenerationDebug = recommendation.candidate_generation_debug || {};
  const scoringDebug = recommendation.scoring_debug || {};
  const candidateComparisonDebug = recommendation.candidate_comparison_debug || {};
  const modelCandidatesEnabled = candidateGenerationDebug.model_candidates_enabled ?? Boolean(state.enable_model_candidates);
  const heuristicCandidateCount = candidateGenerationDebug.heuristic_candidate_count;
  const modelCandidateCount = candidateGenerationDebug.model_candidate_count;
  const fusedCandidateCount = candidateGenerationDebug.fused_candidate_count ?? recommendation.candidate_count_considered;
  const candidateGeneratorBackend = candidateGenerationDebug.candidate_generator_backend || state.candidate_generator_backend || "auto";
  const scorerBackend = recommendation.scorer_backend || "unknown";
  const selectedCandidateId = recommendation.selected_candidate_id || "unknown";
  const candidateCountConsidered = recommendation.candidate_count_considered ?? fusedCandidateCount;
  const hasPlannerDebug = Boolean(
    recommendation.candidate_generation_debug || recommendation.scoring_debug || recommendation.candidate_comparison_debug || recommendation.selected_candidate_source
  );
  const diagnosisText = candidateComparisonDebug.diagnosis_text || plannerSelectionOutcome(modelCandidatesEnabled, selectedCandidateSource);
  const selectedVsBestHeuristic = candidateComparisonDebug.selected_vs_best_heuristic || null;
  const selectedContrast = candidateComparisonDebug.selected_candidate_contrast || {};
  const bestHeuristicFoodIds = selectedContrast.best_heuristic_candidate_shopping_food_ids
    || candidateComparisonDebug.best_heuristic_candidate_shopping_food_ids
    || [];
  const bestModelFoodIds = selectedContrast.best_model_candidate_shopping_food_ids
    || candidateComparisonDebug.best_model_candidate_shopping_food_ids
    || [];
  const topCandidateRows = Array.isArray(scoringDebug.candidates)
    ? scoringDebug.candidates.slice(0, 5).map(candidate => `
        <tr>
          <td class="generic-debug-code">${escapeHtml(candidate.candidate_id)}</td>
          <td>${escapeHtml(candidateSourceDisplay(candidate.source))}</td>
          <td>${escapeHtml(formatMetricValue(candidate.model_score))}</td>
          <td>${escapeHtml(candidate.generator_score ?? "n/a")}</td>
          <td class="generic-debug-code">${escapeHtml(formatFoodIdList(candidate.shopping_food_ids))}</td>
          <td>${candidate.selected ? "Yes" : "No"}</td>
          <td>${escapeHtml(candidate.selection_reason_summary || "")}</td>
        </tr>
      `).join("")
    : "";
  const candidatePoolLine = heuristicCandidateCount !== undefined && modelCandidateCount !== undefined && fusedCandidateCount !== undefined
    ? `${heuristicCandidateCount} heuristic + ${modelCandidateCount} model -> ${fusedCandidateCount} fused`
    : candidateCountConsidered !== undefined
      ? `${candidateCountConsidered} total candidates ranked`
      : "Not available";
  const plannerDebugBlock = hasPlannerDebug
    ? `
      <div class="generic-list-item" style="margin-top: 1rem">
        <div class="generic-inline-group">
          <h3>Planner Debug / Model Participation</h3>
          <span class="generic-badge">Debug summary</span>
        </div>
        <div class="generic-debug-list">
          <div><strong>Selected candidate source:</strong> ${escapeHtml(candidateSourceDisplay(selectedCandidateSource))}</div>
          <div><strong>Selected candidate sources:</strong> ${escapeHtml(selectedCandidateSources.map(candidateSourceDisplay).join(" + "))}</div>
          <div><strong>Candidate pool:</strong> ${escapeHtml(candidatePoolLine)}</div>
          <div><strong>Candidates ranked:</strong> ${escapeHtml(candidateCountConsidered ?? "Not available")}</div>
          <div><strong>Model candidates enabled:</strong> ${escapeHtml(modelCandidatesEnabled ? "Yes" : "No")}</div>
          <div><strong>Candidate generator backend:</strong> ${escapeHtml(candidateGeneratorBackend || "Not used")}</div>
          <div><strong>Scorer backend:</strong> ${escapeHtml(scorerBackend)}</div>
          <div><strong>Selected candidate ID:</strong> ${escapeHtml(selectedCandidateId)}</div>
          <div><strong>Best heuristic candidate:</strong> ${escapeHtml(candidateComparisonDebug.best_heuristic_candidate_id || "Not available")} ${
            candidateComparisonDebug.best_heuristic_candidate_score !== null && candidateComparisonDebug.best_heuristic_candidate_score !== undefined
              ? `<span>(score ${escapeHtml(formatMetricValue(candidateComparisonDebug.best_heuristic_candidate_score))})</span>`
              : ""
          }</div>
          <div><strong>Best model candidate:</strong> ${escapeHtml(candidateComparisonDebug.best_model_candidate_id || "Not available")} ${
            candidateComparisonDebug.best_model_candidate_score !== null && candidateComparisonDebug.best_model_candidate_score !== undefined
              ? `<span>(score ${escapeHtml(formatMetricValue(candidateComparisonDebug.best_model_candidate_score))})</span>`
              : ""
          }</div>
          <div><strong>Model vs heuristic score gap:</strong> ${escapeHtml(
            candidateComparisonDebug.best_model_vs_best_heuristic_score_gap !== null && candidateComparisonDebug.best_model_vs_best_heuristic_score_gap !== undefined
              ? formatMetricValue(candidateComparisonDebug.best_model_vs_best_heuristic_score_gap)
              : "Not available"
          )}</div>
          <div><strong>Model candidates merged:</strong> ${escapeHtml(
            candidateComparisonDebug.model_candidates_merged_count !== null && candidateComparisonDebug.model_candidates_merged_count !== undefined
              ? `${candidateComparisonDebug.model_candidates_merged_count}`
              : "Not available"
          )}</div>
          <div><strong>Materially different model candidates surviving fusion:</strong> ${escapeHtml(
            candidateComparisonDebug.materially_different_model_candidates_surviving_after_fusion !== null
            && candidateComparisonDebug.materially_different_model_candidates_surviving_after_fusion !== undefined
              ? `${candidateComparisonDebug.materially_different_model_candidates_surviving_after_fusion}`
              : "Not available"
          )}</div>
          <div><strong>Average heuristic/model overlap:</strong> ${escapeHtml(
            candidateComparisonDebug.average_heuristic_model_overlap_jaccard !== null && candidateComparisonDebug.average_heuristic_model_overlap_jaccard !== undefined
              ? formatMetricValue(candidateComparisonDebug.average_heuristic_model_overlap_jaccard)
              : "Not available"
          )}</div>
          <div><strong>Best materially different model candidate:</strong> ${escapeHtml(
            candidateComparisonDebug.best_materially_different_model_candidate_id || "Not available"
          )} ${
            candidateComparisonDebug.best_materially_different_model_candidate_score !== null
            && candidateComparisonDebug.best_materially_different_model_candidate_score !== undefined
              ? `<span>(score ${escapeHtml(formatMetricValue(candidateComparisonDebug.best_materially_different_model_candidate_score))})</span>`
              : ""
          }</div>
          <div><strong>Winner vs best materially different model gap:</strong> ${escapeHtml(
            candidateComparisonDebug.best_materially_different_model_candidate_score_gap_to_selected !== null
            && candidateComparisonDebug.best_materially_different_model_candidate_score_gap_to_selected !== undefined
              ? formatMetricValue(candidateComparisonDebug.best_materially_different_model_candidate_score_gap_to_selected)
              : "Not available"
          )}</div>
          <div><strong>Why that model alternative lost:</strong> ${escapeHtml(
            candidateComparisonDebug.best_materially_different_model_candidate_loss_reason || "Not available"
          )}</div>
          <div><strong>Similarity diagnosis:</strong> ${escapeHtml(
            candidateComparisonDebug.model_candidates_mostly_near_duplicates
              ? "Model candidates were mostly near-duplicates."
              : modelCandidatesEnabled
                ? "Model candidates introduced materially different baskets."
                : "Model path disabled."
          )}</div>
          <div><strong>Selection outcome:</strong> ${escapeHtml(diagnosisText)}</div>
        </div>
        <div class="generic-debug-list" style="margin-top: 1rem">
          <div><strong>Selected vs heuristic baseline:</strong> ${escapeHtml(selectedContrast.difference_summary_vs_best_heuristic || candidateComparisonDebug.selected_candidate_difference_summary || "Not available")}</div>
          <div><strong>Materially different from heuristic baseline:</strong> ${escapeHtml(
            selectedVsBestHeuristic ? (selectedVsBestHeuristic.materially_different ? "Yes" : "No") : "Not available"
          )}</div>
          <div><strong>Selected candidate shopping_food_ids:</strong> <span class="generic-debug-code">${escapeHtml(formatFoodIdList(selectedContrast.selected_candidate_shopping_food_ids || candidateComparisonDebug.selected_candidate_shopping_food_ids || []))}</span></div>
          <div><strong>Best heuristic candidate shopping_food_ids:</strong> <span class="generic-debug-code">${escapeHtml(formatFoodIdList(bestHeuristicFoodIds))}</span></div>
          <div><strong>Best model candidate shopping_food_ids:</strong> <span class="generic-debug-code">${escapeHtml(formatFoodIdList(bestModelFoodIds))}</span></div>
        </div>
        ${
          topCandidateRows
            ? `<details class="generic-advanced" style="margin-top: 1rem">
                <summary>Top candidates</summary>
                <table class="generic-debug-table">
                  <thead>
                    <tr>
                      <th>Candidate</th>
                      <th>Source</th>
                      <th>Scorer score</th>
                      <th>Generator score</th>
                      <th>shopping_food_ids</th>
                      <th>Selected</th>
                      <th>Reason</th>
                    </tr>
                  </thead>
                  <tbody>${topCandidateRows}</tbody>
                </table>
              </details>`
            : ""
        }
      </div>
    `
    : "";
  let itemIndex = 0;
  const renderItem = item => `
        <div class="generic-list-item">
          <div class="generic-list-header">
            <div>
              <strong>${itemIndex += 1}. ${escapeHtml(item.name)}</strong>
              <div class="generic-muted">Suggested buy: ${escapeHtml(item.quantity_display)}</div>
            </div>
            <span class="generic-badge">${escapeHtml(roleLabel(item.role))}</span>
          </div>
          <div class="generic-muted" style="margin-top: 0.5rem"><strong>${escapeHtml(item.reason_short || "")}</strong></div>
          <div class="generic-muted" style="margin-top: 0.25rem">${escapeHtml(item.why_selected || item.reason)}</div>
          ${
            item.value_reason_short
              ? `<div class="generic-muted" style="margin-top: 0.25rem"><strong>Value note:</strong> ${escapeHtml(item.value_reason_short)}${
                  item.price_efficiency_note ? ` <span>${escapeHtml(item.price_efficiency_note)}</span>` : ""
                }</div>`
              : ""
          }
          <div class="generic-muted" style="margin-top: 0.25rem">${escapeHtml(item.reason)}</div>
          ${
            item.substitution
              ? `<div class="generic-muted" style="margin-top: 0.35rem"><strong>Swap option:</strong> ${escapeHtml(item.substitution)}${
                  cleanedSubstitutionReason(item) ? ` <span>${escapeHtml(cleanedSubstitutionReason(item))}</span>` : ""
                }</div>`
              : ""
          }
          <div class="generic-list-meta">
            <span><strong>Protein:</strong> ${escapeHtml(item.estimated_protein_g)} g</span>
            <span><strong>Calories:</strong> ${escapeHtml(item.estimated_calories_kcal)} kcal</span>
          </div>
          ${
            item.estimated_item_cost !== null && item.estimated_item_cost !== undefined
              ? `<div class="generic-muted" style="margin-top: 0.35rem"><strong>Typical regional price:</strong> $${escapeHtml(item.typical_unit_price ?? item.estimated_unit_price)} ${escapeHtml(item.price_unit_display || "")}; typical item cost about <strong>$${escapeHtml(item.typical_item_cost ?? item.estimated_item_cost)}</strong>${
                  item.estimated_price_low !== null && item.estimated_price_low !== undefined && item.estimated_price_high !== null && item.estimated_price_high !== undefined
                    ? ` <span>(regional range $${escapeHtml(item.estimated_price_low)}-$${escapeHtml(item.estimated_price_high)})</span>`
                    : ""
                }.</div>`
              : ""
          }
        </div>
      `;

  const shoppingList = ROLE_SECTIONS.map(section => {
    const items = recommendation.shopping_list.filter(item => item.role === section.role);
    if (!items.length) {
      return "";
    }
    return `
      <div class="generic-list-item" style="margin-top: 1rem">
        <div class="generic-inline-group">
          <h3>${escapeHtml(section.title)}</h3>
          <span class="generic-badge">${items.length} ${items.length === 1 ? "item" : "items"}</span>
        </div>
        <div class="generic-list">
          ${items.map(renderItem).join("")}
        </div>
      </div>
    `;
  })
    .join("");

  const assumptions = (recommendation.assumptions || []).map(text => `<li>${escapeHtml(text)}</li>`).join("");
  const pantryNotes = (recommendation.pantry_notes || []).map(text => `<li>${escapeHtml(text)}</li>`).join("");
  const scalingNotes = (recommendation.scaling_notes || []).map(text => `<li>${escapeHtml(text)}</li>`).join("");
  const warnings = (recommendation.warnings || []).map(text => `<li>${escapeHtml(text)}</li>`).join("");
  const splitNotes = (recommendation.split_notes || []).map(text => `<li>${escapeHtml(text)}</li>`).join("");
  const realismNotes = (recommendation.realism_notes || []).map(text => `<li>${escapeHtml(text)}</li>`).join("");
  const pricingNotes = [
    recommendation.estimated_basket_cost_low !== undefined && recommendation.estimated_basket_cost_high !== undefined
      ? `<p class="generic-muted"><strong>Typical basket range:</strong> about $${escapeHtml(recommendation.estimated_basket_cost_low)}-$${escapeHtml(recommendation.estimated_basket_cost_high)}</p>`
      : "",
    recommendation.price_area_name
      ? `<p class="generic-muted" style="margin-top: 0.5rem"><strong>Regional price area:</strong> ${escapeHtml(recommendation.price_area_name)} (${escapeHtml(recommendation.price_area_code || "")})</p>`
      : "",
    recommendation.price_source_note
      ? `<p class="generic-muted" style="margin-top: 0.5rem">${escapeHtml(recommendation.price_source_note)}</p>`
      : "",
    recommendation.price_adjustment_note
      ? `<p class="generic-muted" style="margin-top: 0.5rem">${escapeHtml(recommendation.price_adjustment_note)}</p>`
      : "",
    recommendation.basket_cost_note
      ? `<p class="generic-muted" style="margin-top: 0.5rem">${escapeHtml(recommendation.basket_cost_note)}</p>`
      : "",
    recommendation.price_confidence_note
      ? `<p class="generic-muted" style="margin-top: 0.5rem">${escapeHtml(recommendation.price_confidence_note)}</p>`
      : ""
  ].filter(Boolean).join("");
  const storeFitNotes = (recommendation.store_fit_notes || [])
    .map(
      note => `
        <div class="generic-list-item" style="margin-top: 0.75rem">
          <div class="generic-inline-group">
            <h3>${escapeHtml(note.store_name || "Nearby store")}</h3>
            <span class="generic-badge">${escapeHtml(note.fit_label || "Store fit")}</span>
          </div>
          <div class="generic-muted"><strong>${escapeHtml(note.category || "store")}</strong>${
            note.distance_m !== undefined && note.distance_m !== null
              ? ` • about ${escapeHtml(Number(note.distance_m).toFixed(0))} m away`
              : ""
          }</div>
          <div class="generic-muted" style="margin-top: 0.25rem">${escapeHtml(note.note || "")}</div>
        </div>
      `
    )
    .join("");
  const groupedStorePicks = STORE_PICK_SECTIONS
    .map(section => {
      const pick = recommendation[section.key];
      if (!pick?.store_id) {
        return "";
      }
      return `
        <div class="generic-list-item" style="margin-top: 0.75rem">
          <div class="generic-inline-group">
            <h3>${escapeHtml(section.title)}</h3>
            <span class="generic-badge">${escapeHtml(pick.store_name || "Nearby store")}</span>
          </div>
          <div class="generic-muted"><strong>${escapeHtml(pick.category || "store")}</strong>${
            pick.distance_m !== undefined && pick.distance_m !== null
              ? ` • about ${escapeHtml(Number(pick.distance_m).toFixed(0))} m away`
              : ""
          }</div>
          <div class="generic-muted" style="margin-top: 0.25rem">${escapeHtml(pick.note || "")}</div>
        </div>
      `;
    })
    .join("");
  const mealSuggestions = (recommendation.meal_suggestions || [])
    .map(
      suggestion => `
        <div class="generic-list-item" style="margin-top: 0.75rem">
          <div class="generic-inline-group">
            <h3>${escapeHtml(suggestion.title || "Meal idea")}</h3>
            <span class="generic-badge">${escapeHtml(String(suggestion.meal_type || "idea").replaceAll("_", " "))}</span>
          </div>
          <div class="generic-muted"><strong>${escapeHtml((suggestion.items || []).join(", "))}</strong></div>
          ${
            suggestion.description
              ? `<div class="generic-muted" style="margin-top: 0.25rem">${escapeHtml(suggestion.description)}</div>`
              : ""
          }
        </div>
      `
    )
    .join("");
  const summaryCards = SUMMARY_FIELDS.filter(
    metric => summary?.[metric.targetKey] !== undefined && summary?.[metric.estimatedKey] !== undefined
  )
    .map(
      metric => `
        <div class="generic-summary-metric">
          <div class="generic-muted">${escapeHtml(metric.label)}</div>
          <strong>${escapeHtml(summary[metric.estimatedKey])} ${escapeHtml(metric.unit)}</strong>
          <div>Target: ${escapeHtml(summary[metric.targetKey])} ${escapeHtml(metric.unit)}</div>
          <div class="generic-muted">Difference: ${escapeHtml(
            formatDelta(summary[metric.estimatedKey], summary[metric.targetKey], metric.unit)
          )}</div>
        </div>
      `
    )
    .join("");

  parent.innerHTML = `
    ${statusNotice(recommendationStatus || "Recommendation ready.", "success")}
    ${statusNotice(exportNotice?.message, exportNotice?.kind)}
    <div class="generic-list-item" style="margin-bottom: 1rem">
      <div class="generic-inline-group">
        <h3>Shopping List</h3>
        <div class="generic-badge-group">
          <span class="generic-badge ${escapeHtml(candidateSourceBadgeClass(selectedCandidateSource))}">
            ${escapeHtml(candidateSourceBadgeLabel(selectedCandidateSource))}
          </span>
          <span class="generic-badge">Suggested shopping list for ${days} ${days === 1 ? "day" : "days"}</span>
        </div>
      </div>
      <p class="generic-muted">Daily nutrition goals stay the same. Quantities below are scaled for the selected shopping window in <strong>${escapeHtml(shoppingMode)}</strong> shopping mode.</p>
      <div class="generic-actions" style="margin-top: 0.75rem">
        <button type="button" data-export-action="copy-shopping">Copy shopping list</button>
        <button type="button" data-export-action="copy-plan">Copy full plan</button>
        <button type="button" data-export-action="download-plan">Download as text</button>
      </div>
      ${
        recommendation.estimated_basket_cost !== undefined
          ? `<p class="generic-muted" style="margin-top: 0.5rem"><strong>Estimated typical basket cost:</strong> about $${escapeHtml(recommendation.estimated_basket_cost)}.</p>`
          : ""
      }
    </div>
    <div class="generic-list">
      ${shoppingList || `<div class="generic-empty">Your pantry already covers the suggested basket for this plan. Review the notes below if you still want a small top-up shop.</div>`}
    </div>
    ${plannerDebugBlock}
    ${
      groupedStorePicks
        ? `<div class="generic-list-item" style="margin-top: 1rem">
            <div class="generic-inline-group">
              <h3>Recommended store picks for this list</h3>
              <span class="generic-badge">${STORE_PICK_SECTIONS.filter(section => recommendation[section.key]?.store_id).length} picks</span>
            </div>
            <p class="generic-muted">These are quick store-type recommendations based on the basket style and nearby store mix. They do not reflect exact inventory.</p>
            ${groupedStorePicks}
          </div>`
        : ""
    }
    ${
      storeFitNotes
        ? `<div class="generic-list-item" style="margin-top: 1rem">
            <div class="generic-inline-group">
              <h3>Best nearby store fits for this list</h3>
              <span class="generic-badge">${(recommendation.store_fit_notes || []).length} suggestions</span>
            </div>
            <p class="generic-muted">These are coarse store-fit suggestions based on the basket style, shopping mode, and nearby store type. They do not reflect exact inventory.</p>
            ${storeFitNotes}
          </div>`
        : ""
    }
    ${
      mealSuggestions
        ? `<div class="generic-list-item" style="margin-top: 1rem">
            <div class="generic-inline-group">
              <h3>Example ways to use this list</h3>
              <span class="generic-badge">${(recommendation.meal_suggestions || []).length} ideas</span>
            </div>
            <p class="generic-muted">These are lightweight examples built from the same recommended items. They are not a full meal plan.</p>
            ${mealSuggestions}
          </div>`
        : ""
    }
    ${
      scalingNotes || warnings || splitNotes || realismNotes || pantryNotes
        ? `<div class="generic-list-item" style="margin-top: 1rem">
            <div class="generic-inline-group">
              <h3>Shopping Notes</h3>
              <span class="generic-badge">${
                recommendation.adjusted_by_split ? "Scaling and realism guidance" : "Scaling guidance"
              }</span>
            </div>
            ${
              scalingNotes
                ? `<p class="generic-muted"><strong>Scaling notes</strong></p><ul class="generic-assumptions">${scalingNotes}</ul>`
                : ""
            }
            ${
              splitNotes
                ? `<p class="generic-muted" style="margin-top: 0.75rem"><strong>Split notes</strong></p><ul class="generic-assumptions">${splitNotes}</ul>`
                : ""
            }
            ${
              realismNotes
                ? `<p class="generic-muted" style="margin-top: 0.75rem"><strong>Realism notes</strong></p><ul class="generic-assumptions">${realismNotes}</ul>`
                : ""
            }
            ${
              pantryNotes
                ? `<p class="generic-muted" style="margin-top: 0.75rem"><strong>Pantry adjustments</strong></p><ul class="generic-assumptions">${pantryNotes}</ul>`
                : ""
            }
            ${
              warnings
                ? `<p class="generic-muted" style="margin-top: 0.75rem"><strong>Warnings</strong></p><ul class="generic-assumptions">${warnings}</ul>`
                : ""
            }
          </div>`
        : ""
    }
    <div class="generic-list-item" style="margin-top: 1rem">
      <div class="generic-inline-group">
        <h3>Nutrition Summary</h3>
        <span class="generic-badge">${days === 1 ? "Daily total" : `${days}-day total`}</span>
      </div>
      <div class="generic-summary-grid">
        ${summaryCards}
      </div>
    </div>
    <div class="generic-list-item" style="margin-top: 1rem">
      <div class="generic-inline-group">
        <h3>Approximate Guidance</h3>
        <span class="generic-badge">Demo-friendly estimate</span>
      </div>
      <p class="generic-muted">Use this list as a practical starting point, not as exact store inventory or guaranteed product availability.</p>
      <ul class="generic-assumptions">${assumptions}</ul>
    </div>
    ${
      pricingNotes
        ? `<div class="generic-list-item" style="margin-top: 1rem">
            <div class="generic-inline-group">
              <h3>Pricing notes</h3>
              <span class="generic-badge">Typical regional estimate</span>
            </div>
            ${pricingNotes}
          </div>`
        : ""
    }
  `;

  parent.querySelector('[data-export-action="copy-shopping"]')?.addEventListener("click", () => {
    void actions.onCopyShoppingList?.();
  });
  parent.querySelector('[data-export-action="copy-plan"]')?.addEventListener("click", () => {
    void actions.onCopyFullPlan?.();
  });
  parent.querySelector('[data-export-action="download-plan"]')?.addEventListener("click", () => {
    actions.onDownloadPlan?.();
  });
}
