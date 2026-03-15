function k(t,e){return t.querySelector(`[name="${e}"]`)?.checked||!1}function re(t,e){return[...t.querySelectorAll(`[name="${e}"]:checked`)].map(a=>a.value)}var ae=[{id:"eggs",label:"Eggs"},{id:"milk",label:"Milk"},{id:"greek_yogurt",label:"Greek yogurt"},{id:"oats",label:"Oats"},{id:"rice",label:"Rice"},{id:"beans",label:"Beans"},{id:"lentils",label:"Lentils"},{id:"bananas",label:"Bananas"},{id:"broccoli",label:"Broccoli"},{id:"potatoes",label:"Potatoes"},{id:"olive_oil",label:"Olive oil"},{id:"peanut_butter",label:"Peanut butter"},{id:"tofu",label:"Tofu"},{id:"chicken_breast",label:"Chicken breast"}];function d(t){return String(t??"").replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;").replaceAll('"',"&quot;").replaceAll("'","&#39;")}function p(t,e){return t.errors?.[e]||""}function se(t){return t.formNotice?.message?`
    <div class="generic-notice ${d(t.formNotice.kind||"info")}" role="status">
      ${d(t.formNotice.message)}
    </div>
  `:""}function K(t,e,a){let n=(e.presets||[]).map(u=>`
        <button type="button" class="generic-preset-button" data-preset-id="${d(u.id)}">
          ${d(u.label)}
        </button>
      `).join(""),l=e.isLocating||e.isResolvingAddress||e.isLookingUpStores||e.isGeneratingRecommendations,c=ae.map(u=>`
        <label>
          <input
            name="pantry_items"
            type="checkbox"
            value="${d(u.id)}"
            ${(e.pantry_items||[]).includes(u.id)?"checked":""}
          />
          ${d(u.label)}
        </label>
      `).join("");t.innerHTML=`
    <form id="generic-input-form" novalidate>
      ${se(e)}
      <div>
        <h3>Goal Presets</h3>
        <p class="generic-help">Start from a common goal, then fine-tune the location targets or preferences if needed.</p>
        <div class="generic-presets">${n}</div>
      </div>

      <div class="generic-form-grid">
        <label class="generic-span-full">
          City or address
          <input
            name="locationQuery"
            type="text"
            placeholder="Mountain View, CA"
            value="${d(e.locationQuery)}"
            aria-invalid="${p(e,"locationQuery")?"true":"false"}"
          />
          <span class="generic-field-error">${d(p(e,"locationQuery"))}</span>
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
            <option value="1" ${e.days==="1"?"selected":""}>1 day</option>
            <option value="3" ${e.days==="3"?"selected":""}>3 days</option>
            <option value="5" ${e.days==="5"?"selected":""}>5 days</option>
            <option value="7" ${e.days==="7"?"selected":""}>7 days</option>
          </select>
          <span class="generic-help">Daily targets stay the same. Quantities are scaled for the selected shopping window.</span>
        </label>
        <label>
          Shopping mode
          <select name="shopping_mode">
            <option value="balanced" ${e.shopping_mode==="balanced"?"selected":""}>Balanced</option>
            <option value="fresh" ${e.shopping_mode==="fresh"?"selected":""}>Fresh</option>
            <option value="bulk" ${e.shopping_mode==="bulk"?"selected":""}>Bulk</option>
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
            value="${d(e.calories)}"
            aria-invalid="${p(e,"calories")?"true":"false"}"
            required
          />
          <span class="generic-field-error">${d(p(e,"calories"))}</span>
        </label>
        <label>
          Protein (g)
          <input
            name="protein"
            type="number"
            min="1"
            step="1"
            value="${d(e.protein)}"
            aria-invalid="${p(e,"protein")?"true":"false"}"
            required
          />
          <span class="generic-field-error">${d(p(e,"protein"))}</span>
        </label>
        <label>
          Carbs (g)
          <input
            name="carbohydrate"
            type="number"
            min="1"
            step="1"
            value="${d(e.carbohydrate)}"
            aria-invalid="${p(e,"carbohydrate")?"true":"false"}"
          />
          <span class="generic-field-error">${d(p(e,"carbohydrate"))}</span>
        </label>
        <label>
          Fat (g)
          <input
            name="fat"
            type="number"
            min="1"
            step="1"
            value="${d(e.fat)}"
            aria-invalid="${p(e,"fat")?"true":"false"}"
          />
          <span class="generic-field-error">${d(p(e,"fat"))}</span>
        </label>
        <label>
          Fiber (g)
          <input
            name="fiber"
            type="number"
            min="1"
            step="1"
            value="${d(e.fiber)}"
            aria-invalid="${p(e,"fiber")?"true":"false"}"
          />
          <span class="generic-field-error">${d(p(e,"fiber"))}</span>
        </label>
      </div>

      <div class="generic-form-grid">
        <div class="generic-span-full">
          <h3>Food preferences</h3>
          <label style="display: block; margin-bottom: 0.75rem">
            Meal or use case
            <select name="meal_style">
              <option value="any" ${e.meal_style==="any"?"selected":""}>Any</option>
              <option value="breakfast" ${e.meal_style==="breakfast"?"selected":""}>Breakfast</option>
              <option value="lunch_dinner" ${e.meal_style==="lunch_dinner"?"selected":""}>Lunch / dinner</option>
              <option value="snack" ${e.meal_style==="snack"?"selected":""}>Snack</option>
            </select>
          </label>
          <div class="generic-checkboxes">
            <label>
              <input name="vegetarian" type="checkbox" ${e.vegetarian?"checked":""} />
              Vegetarian (includes eggs and dairy)
            </label>
            <label><input name="vegan" type="checkbox" ${e.vegan?"checked":""} /> Vegan</label>
            <label><input name="dairy_free" type="checkbox" ${e.dairy_free?"checked":""} /> Dairy-free</label>
            <label><input name="low_prep" type="checkbox" ${e.low_prep?"checked":""} /> Low prep</label>
            <label><input name="budget_friendly" type="checkbox" ${e.budget_friendly?"checked":""} /> Budget friendly</label>
          </div>
          <p class="generic-help">Recommendations stay generic. They do not depend on exact store inventory or branded products.</p>
        </div>
      </div>

      <div class="generic-form-grid">
        <div class="generic-span-full">
          <h3>Already have</h3>
          <p class="generic-help">Mark common items already in your pantry or fridge. The shopping list will reduce or omit them where the basket still works.</p>
          <div class="generic-checkboxes">
            ${c}
          </div>
        </div>
      </div>

      <details class="generic-advanced">
        <summary>Advanced nutrition</summary>
        <div class="generic-form-grid">
          <label>
            Calcium (mg)
            <input
              name="calcium"
              type="number"
              min="1"
              step="1"
              value="${d(e.calcium)}"
              aria-invalid="${p(e,"calcium")?"true":"false"}"
            />
            <span class="generic-field-error">${d(p(e,"calcium"))}</span>
          </label>
          <label>
            Iron (mg)
            <input
              name="iron"
              type="number"
              min="1"
              step="0.1"
              value="${d(e.iron)}"
              aria-invalid="${p(e,"iron")?"true":"false"}"
            />
            <span class="generic-field-error">${d(p(e,"iron"))}</span>
          </label>
          <label>
            Vitamin C (mg)
            <input
              name="vitamin_c"
              type="number"
              min="1"
              step="1"
              value="${d(e.vitamin_c)}"
              aria-invalid="${p(e,"vitamin_c")?"true":"false"}"
            />
            <span class="generic-field-error">${d(p(e,"vitamin_c"))}</span>
          </label>
        </div>
      </details>

      <div class="generic-actions">
        <button type="button" id="use-location-button" ${l?"disabled":""}>
          ${e.isLocating?"Locating...":"Use My Location"}
        </button>
        <button type="button" id="lookup-stores-button" ${l?"disabled":""}>
          ${e.isResolvingAddress||e.isLookingUpStores?"Looking Up...":"Find Nearby Supermarkets"}
        </button>
        <button type="submit" ${l?"disabled":""}>
          ${e.isResolvingAddress||e.isGeneratingRecommendations?"Generating...":"Build Shopping List"}
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
              value="${d(e.lat)}"
              aria-invalid="${p(e,"lat")?"true":"false"}"
            />
            <span class="generic-field-error">${d(p(e,"lat"))}</span>
          </label>
          <label>
            Longitude
            <input
              name="lon"
              type="number"
              step="any"
              value="${d(e.lon)}"
              aria-invalid="${p(e,"lon")?"true":"false"}"
            />
            <span class="generic-field-error">${d(p(e,"lon"))}</span>
          </label>
          <label>
            Search radius (m)
            <input name="radius_m" type="number" min="1" step="100" value="${d(e.radius_m)}" required />
            <span class="generic-help">How far to search for supermarkets around the selected point.</span>
          </label>
          <label>
            Nearby stores to show
            <input name="store_limit" type="number" min="1" max="25" step="1" value="${d(e.store_limit)}" required />
            <span class="generic-help">The list is always sorted by distance.</span>
          </label>
        </div>
      </details>
    </form>
  `;let o=t.querySelector("#generic-input-form"),g=()=>a.onChange({locationQuery:o.locationQuery.value,lat:o.lat.value,lon:o.lon.value,radius_m:o.radius_m.value,store_limit:o.store_limit.value,days:o.days.value,shopping_mode:o.shopping_mode.value,protein:o.protein.value,calories:o.calories.value,carbohydrate:o.carbohydrate.value,fat:o.fat.value,fiber:o.fiber.value,calcium:o.calcium.value,iron:o.iron.value,vitamin_c:o.vitamin_c.value,vegetarian:k(o,"vegetarian"),dairy_free:k(o,"dairy_free"),vegan:k(o,"vegan"),low_prep:k(o,"low_prep"),budget_friendly:k(o,"budget_friendly"),meal_style:o.meal_style.value,pantry_items:re(o,"pantry_items")});o.addEventListener("change",g),o.addEventListener("input",g),o.addEventListener("submit",u=>{u.preventDefault(),g(),a.onRecommend()}),t.querySelector("#lookup-stores-button").addEventListener("click",()=>{g(),a.onLookupStores()}),t.querySelector("#use-location-button").addEventListener("click",()=>{g(),a.onUseMyLocation()}),t.querySelectorAll("[data-preset-id]").forEach(u=>{u.addEventListener("click",()=>{a.onApplyPreset(u.dataset.presetId)})})}function s(t){return String(t??"").replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;").replaceAll('"',"&quot;").replaceAll("'","&#39;")}function w(t,e){return t?`<div class="generic-notice ${s(e||"info")}">${s(t)}</div>`:""}function oe(t,e,a){let n=Math.round((t-e)*10)/10;return`${n>0?"+":""}${n} ${a}`}function le(t){return{protein_anchor:"Protein anchor",carb_base:"Carb base",produce:"Produce",calorie_booster:"Calorie booster"}[t]||"Recommended item"}var U=[{role:"protein_anchor",title:"Protein picks"},{role:"carb_base",title:"Carb base"},{role:"produce",title:"Produce"},{role:"calorie_booster",title:"Extras / boosters"}],T=[{key:"one_stop_pick",title:"One-stop pick"},{key:"budget_pick",title:"Budget pick"},{key:"produce_pick",title:"Produce pick"},{key:"bulk_pick",title:"Bulk pick"}],Q=[{label:"Protein",targetKey:"protein_target_g",estimatedKey:"protein_estimated_g",unit:"g"},{label:"Calories",targetKey:"calorie_target_kcal",estimatedKey:"calorie_estimated_kcal",unit:"kcal"},{label:"Carbs",targetKey:"carbohydrate_target_g",estimatedKey:"carbohydrate_estimated_g",unit:"g"},{label:"Fat",targetKey:"fat_target_g",estimatedKey:"fat_estimated_g",unit:"g"},{label:"Fiber",targetKey:"fiber_target_g",estimatedKey:"fiber_estimated_g",unit:"g"},{label:"Calcium",targetKey:"calcium_target_mg",estimatedKey:"calcium_estimated_mg",unit:"mg"},{label:"Iron",targetKey:"iron_target_mg",estimatedKey:"iron_estimated_mg",unit:"mg"},{label:"Vitamin C",targetKey:"vitamin_c_target_mg",estimatedKey:"vitamin_c_estimated_mg",unit:"mg"}];function ce(t,e){return!t||t[e.targetKey]===void 0||t[e.estimatedKey]===void 0?null:`${e.label}: ${t[e.estimatedKey]} ${e.unit} (target ${t[e.targetKey]} ${e.unit})`}function B(t){let e=String(t?.substitution_reason||"").trim(),a=String(t?.substitution||"").trim();return e?a&&e.toLowerCase().startsWith(a.toLowerCase())?e.slice(a.length).trim():e:""}function G(t,e=!0){return U.map(a=>{let n=(t.shopping_list||[]).filter(c=>c.role===a.role);if(!n.length)return"";let l=n.map(c=>{let o=[`- ${c.name}: ${c.quantity_display}`];if(e&&c.reason_short&&o.push(`  ${c.reason_short}`),e&&c.typical_item_cost!==null&&c.typical_item_cost!==void 0){let g=c.estimated_price_low!==null&&c.estimated_price_low!==void 0&&c.estimated_price_high!==null&&c.estimated_price_high!==void 0?` (range $${c.estimated_price_low}-$${c.estimated_price_high})`:"";o.push(`  Typical cost: $${c.typical_item_cost}${g}`)}return o.join(`
`)});return`${a.title}
${l.join(`
`)}`}).filter(Boolean).join(`

`)}function V(t){return T.map(e=>{let a=t?.[e.key];if(!a?.store_id)return null;let n=a.distance_m!==void 0&&a.distance_m!==null?`, about ${Math.round(Number(a.distance_m))} m away`:"";return`- ${e.title}: ${a.store_name} (${a.category||"store"}${n})${a.note?` - ${a.note}`:""}`}).filter(Boolean)}function O(t){if(!t?.shopping_list?.length)return"";let e=Number(t.days||1),a=String(t.shopping_mode||"balanced"),n=["Generic Grocery Plan",`Shopping window: ${e} ${e===1?"day":"days"}`,`Shopping mode: ${a}`,"",G(t,!1)];t.estimated_basket_cost!==void 0&&(n.push("",`Estimated typical basket cost: $${t.estimated_basket_cost}`),t.estimated_basket_cost_low!==void 0&&t.estimated_basket_cost_high!==void 0&&n.push(`Typical basket range: $${t.estimated_basket_cost_low}-$${t.estimated_basket_cost_high}`),t.price_adjustment_note&&n.push(t.price_adjustment_note),t.price_coverage_note&&n.push(t.price_coverage_note));let l=V(t);return l.length&&n.push("","Recommended store picks",...l),n.filter(Boolean).join(`
`)}function M(t){if(!t?.shopping_list?.length)return"";let e=Number(t.days||1),a=String(t.shopping_mode||"balanced"),n=t.nutrition_summary||{},l=Q.map(g=>ce(n,g)).filter(Boolean),c=V(t),o=["Generic Grocery Plan",`Shopping window: ${e} ${e===1?"day":"days"}`,`Shopping mode: ${a}`];return l.length&&o.push("","Key nutrition targets",...l),t.estimated_basket_cost!==void 0&&(o.push("",`Estimated typical basket cost: $${t.estimated_basket_cost}`),t.estimated_basket_cost_low!==void 0&&t.estimated_basket_cost_high!==void 0&&o.push(`Typical basket range: $${t.estimated_basket_cost_low}-$${t.estimated_basket_cost_high}`),t.price_adjustment_note&&o.push(t.price_adjustment_note),t.price_coverage_note&&o.push(t.price_coverage_note),t.basket_cost_note&&o.push(t.basket_cost_note),t.price_confidence_note&&o.push(t.price_confidence_note)),c.length&&o.push("","Recommended store picks",...c),o.push("","Shopping list",G(t,!0)),Array.isArray(t.assumptions)&&t.assumptions.length&&o.push("","Approximate guidance",...t.assumptions.map(g=>`- ${g}`)),o.filter(Boolean).join(`
`)}function H(t,e,a={}){let{recommendation:n,recommendationStatus:l,recommendationError:c,isGeneratingRecommendations:o,hasRequestedRecommendation:g,exportNotice:u}=e;if(o){t.innerHTML=`
      ${w(l||"Generating recommendations...","info")}
      <div class="generic-empty">Building a generic shopping list from the nutrition targets and food preferences.</div>
    `;return}if(c){t.innerHTML=`
      ${w(c,"error")}
      <div class="generic-empty">The app could not build a shopping list for the current inputs. Adjust the targets or preferences and try again.</div>
    `;return}if(!g){t.innerHTML=`
      <div class="generic-empty">
        Build a shopping list to see recommended food categories, rough quantities, and a simple nutrition summary.
      </div>
    `;return}if(!n){t.innerHTML=`
      ${w(l||"No recommendations available.","info")}
      <div class="generic-empty">No shopping list could be generated from the current targets and preferences. Try lowering the targets or relaxing the filters.</div>
    `;return}let h=n.nutrition_summary,b=Number(n.days||e.days||1),C=String(n.shopping_mode||e.shopping_mode||"balanced"),S=0,Z=r=>`
        <div class="generic-list-item">
          <div class="generic-list-header">
            <div>
              <strong>${S+=1}. ${s(r.name)}</strong>
              <div class="generic-muted">Suggested buy: ${s(r.quantity_display)}</div>
            </div>
            <span class="generic-badge">${s(le(r.role))}</span>
          </div>
          <div class="generic-muted" style="margin-top: 0.5rem"><strong>${s(r.reason_short||"")}</strong></div>
          <div class="generic-muted" style="margin-top: 0.25rem">${s(r.why_selected||r.reason)}</div>
          ${r.value_reason_short?`<div class="generic-muted" style="margin-top: 0.25rem"><strong>Value note:</strong> ${s(r.value_reason_short)}${r.price_efficiency_note?` <span>${s(r.price_efficiency_note)}</span>`:""}</div>`:""}
          <div class="generic-muted" style="margin-top: 0.25rem">${s(r.reason)}</div>
          ${r.substitution?`<div class="generic-muted" style="margin-top: 0.35rem"><strong>Swap option:</strong> ${s(r.substitution)}${B(r)?` <span>${s(B(r))}</span>`:""}</div>`:""}
          <div class="generic-list-meta">
            <span><strong>Protein:</strong> ${s(r.estimated_protein_g)} g</span>
            <span><strong>Calories:</strong> ${s(r.estimated_calories_kcal)} kcal</span>
          </div>
          ${r.estimated_item_cost!==null&&r.estimated_item_cost!==void 0?`<div class="generic-muted" style="margin-top: 0.35rem"><strong>Typical regional price:</strong> $${s(r.typical_unit_price??r.estimated_unit_price)} ${s(r.price_unit_display||"")}; typical item cost about <strong>$${s(r.typical_item_cost??r.estimated_item_cost)}</strong>${r.estimated_price_low!==null&&r.estimated_price_low!==void 0&&r.estimated_price_high!==null&&r.estimated_price_high!==void 0?` <span>(regional range $${s(r.estimated_price_low)}-$${s(r.estimated_price_high)})</span>`:""}.</div>`:""}
        </div>
      `,ee=U.map(r=>{let f=n.shopping_list.filter(ne=>ne.role===r.role);return f.length?`
      <div class="generic-list-item" style="margin-top: 1rem">
        <div class="generic-inline-group">
          <h3>${s(r.title)}</h3>
          <span class="generic-badge">${f.length} ${f.length===1?"item":"items"}</span>
        </div>
        <div class="generic-list">
          ${f.map(Z).join("")}
        </div>
      </div>
    `:""}).join(""),te=(n.assumptions||[]).map(r=>`<li>${s(r)}</li>`).join(""),x=(n.pantry_notes||[]).map(r=>`<li>${s(r)}</li>`).join(""),A=(n.scaling_notes||[]).map(r=>`<li>${s(r)}</li>`).join(""),N=(n.warnings||[]).map(r=>`<li>${s(r)}</li>`).join(""),E=(n.split_notes||[]).map(r=>`<li>${s(r)}</li>`).join(""),R=(n.realism_notes||[]).map(r=>`<li>${s(r)}</li>`).join(""),j=[n.estimated_basket_cost_low!==void 0&&n.estimated_basket_cost_high!==void 0?`<p class="generic-muted"><strong>Typical basket range:</strong> about $${s(n.estimated_basket_cost_low)}-$${s(n.estimated_basket_cost_high)}</p>`:"",n.price_area_name?`<p class="generic-muted" style="margin-top: 0.5rem"><strong>Regional price area:</strong> ${s(n.price_area_name)} (${s(n.price_area_code||"")})</p>`:"",n.price_source_note?`<p class="generic-muted" style="margin-top: 0.5rem">${s(n.price_source_note)}</p>`:"",n.price_adjustment_note?`<p class="generic-muted" style="margin-top: 0.5rem">${s(n.price_adjustment_note)}</p>`:"",n.basket_cost_note?`<p class="generic-muted" style="margin-top: 0.5rem">${s(n.basket_cost_note)}</p>`:"",n.price_confidence_note?`<p class="generic-muted" style="margin-top: 0.5rem">${s(n.price_confidence_note)}</p>`:""].filter(Boolean).join(""),P=(n.store_fit_notes||[]).map(r=>`
        <div class="generic-list-item" style="margin-top: 0.75rem">
          <div class="generic-inline-group">
            <h3>${s(r.store_name||"Nearby store")}</h3>
            <span class="generic-badge">${s(r.fit_label||"Store fit")}</span>
          </div>
          <div class="generic-muted"><strong>${s(r.category||"store")}</strong>${r.distance_m!==void 0&&r.distance_m!==null?` \u2022 about ${s(Number(r.distance_m).toFixed(0))} m away`:""}</div>
          <div class="generic-muted" style="margin-top: 0.25rem">${s(r.note||"")}</div>
        </div>
      `).join(""),F=T.map(r=>{let f=n[r.key];return f?.store_id?`
        <div class="generic-list-item" style="margin-top: 0.75rem">
          <div class="generic-inline-group">
            <h3>${s(r.title)}</h3>
            <span class="generic-badge">${s(f.store_name||"Nearby store")}</span>
          </div>
          <div class="generic-muted"><strong>${s(f.category||"store")}</strong>${f.distance_m!==void 0&&f.distance_m!==null?` \u2022 about ${s(Number(f.distance_m).toFixed(0))} m away`:""}</div>
          <div class="generic-muted" style="margin-top: 0.25rem">${s(f.note||"")}</div>
        </div>
      `:""}).join(""),q=(n.meal_suggestions||[]).map(r=>`
        <div class="generic-list-item" style="margin-top: 0.75rem">
          <div class="generic-inline-group">
            <h3>${s(r.title||"Meal idea")}</h3>
            <span class="generic-badge">${s(String(r.meal_type||"idea").replaceAll("_"," "))}</span>
          </div>
          <div class="generic-muted"><strong>${s((r.items||[]).join(", "))}</strong></div>
          ${r.description?`<div class="generic-muted" style="margin-top: 0.25rem">${s(r.description)}</div>`:""}
        </div>
      `).join(""),ie=Q.filter(r=>h?.[r.targetKey]!==void 0&&h?.[r.estimatedKey]!==void 0).map(r=>`
        <div class="generic-summary-metric">
          <div class="generic-muted">${s(r.label)}</div>
          <strong>${s(h[r.estimatedKey])} ${s(r.unit)}</strong>
          <div>Target: ${s(h[r.targetKey])} ${s(r.unit)}</div>
          <div class="generic-muted">Difference: ${s(oe(h[r.estimatedKey],h[r.targetKey],r.unit))}</div>
        </div>
      `).join("");t.innerHTML=`
    ${w(l||"Recommendation ready.","success")}
    ${w(u?.message,u?.kind)}
    <div class="generic-list-item" style="margin-bottom: 1rem">
      <div class="generic-inline-group">
        <h3>Shopping List</h3>
        <span class="generic-badge">Suggested shopping list for ${b} ${b===1?"day":"days"}</span>
      </div>
      <p class="generic-muted">Daily nutrition goals stay the same. Quantities below are scaled for the selected shopping window in <strong>${s(C)}</strong> shopping mode.</p>
      <div class="generic-actions" style="margin-top: 0.75rem">
        <button type="button" data-export-action="copy-shopping">Copy shopping list</button>
        <button type="button" data-export-action="copy-plan">Copy full plan</button>
        <button type="button" data-export-action="download-plan">Download as text</button>
      </div>
      ${n.estimated_basket_cost!==void 0?`<p class="generic-muted" style="margin-top: 0.5rem"><strong>Estimated typical basket cost:</strong> about $${s(n.estimated_basket_cost)}.</p>`:""}
    </div>
    <div class="generic-list">
      ${ee||'<div class="generic-empty">Your pantry already covers the suggested basket for this plan. Review the notes below if you still want a small top-up shop.</div>'}
    </div>
    ${F?`<div class="generic-list-item" style="margin-top: 1rem">
            <div class="generic-inline-group">
              <h3>Recommended store picks for this list</h3>
              <span class="generic-badge">${T.filter(r=>n[r.key]?.store_id).length} picks</span>
            </div>
            <p class="generic-muted">These are quick store-type recommendations based on the basket style and nearby store mix. They do not reflect exact inventory.</p>
            ${F}
          </div>`:""}
    ${P?`<div class="generic-list-item" style="margin-top: 1rem">
            <div class="generic-inline-group">
              <h3>Best nearby store fits for this list</h3>
              <span class="generic-badge">${(n.store_fit_notes||[]).length} suggestions</span>
            </div>
            <p class="generic-muted">These are coarse store-fit suggestions based on the basket style, shopping mode, and nearby store type. They do not reflect exact inventory.</p>
            ${P}
          </div>`:""}
    ${q?`<div class="generic-list-item" style="margin-top: 1rem">
            <div class="generic-inline-group">
              <h3>Example ways to use this list</h3>
              <span class="generic-badge">${(n.meal_suggestions||[]).length} ideas</span>
            </div>
            <p class="generic-muted">These are lightweight examples built from the same recommended items. They are not a full meal plan.</p>
            ${q}
          </div>`:""}
    ${A||N||E||R||x?`<div class="generic-list-item" style="margin-top: 1rem">
            <div class="generic-inline-group">
              <h3>Shopping Notes</h3>
              <span class="generic-badge">${n.adjusted_by_split?"Scaling and realism guidance":"Scaling guidance"}</span>
            </div>
            ${A?`<p class="generic-muted"><strong>Scaling notes</strong></p><ul class="generic-assumptions">${A}</ul>`:""}
            ${E?`<p class="generic-muted" style="margin-top: 0.75rem"><strong>Split notes</strong></p><ul class="generic-assumptions">${E}</ul>`:""}
            ${R?`<p class="generic-muted" style="margin-top: 0.75rem"><strong>Realism notes</strong></p><ul class="generic-assumptions">${R}</ul>`:""}
            ${x?`<p class="generic-muted" style="margin-top: 0.75rem"><strong>Pantry adjustments</strong></p><ul class="generic-assumptions">${x}</ul>`:""}
            ${N?`<p class="generic-muted" style="margin-top: 0.75rem"><strong>Warnings</strong></p><ul class="generic-assumptions">${N}</ul>`:""}
          </div>`:""}
    <div class="generic-list-item" style="margin-top: 1rem">
      <div class="generic-inline-group">
        <h3>Nutrition Summary</h3>
        <span class="generic-badge">${b===1?"Daily total":`${b}-day total`}</span>
      </div>
      <div class="generic-summary-grid">
        ${ie}
      </div>
    </div>
    <div class="generic-list-item" style="margin-top: 1rem">
      <div class="generic-inline-group">
        <h3>Approximate Guidance</h3>
        <span class="generic-badge">Demo-friendly estimate</span>
      </div>
      <p class="generic-muted">Use this list as a practical starting point, not as exact store inventory or guaranteed product availability.</p>
      <ul class="generic-assumptions">${te}</ul>
    </div>
    ${j?`<div class="generic-list-item" style="margin-top: 1rem">
            <div class="generic-inline-group">
              <h3>Pricing notes</h3>
              <span class="generic-badge">Typical regional estimate</span>
            </div>
            ${j}
          </div>`:""}
  `,t.querySelector('[data-export-action="copy-shopping"]')?.addEventListener("click",()=>{a.onCopyShoppingList?.()}),t.querySelector('[data-export-action="copy-plan"]')?.addEventListener("click",()=>{a.onCopyFullPlan?.()}),t.querySelector('[data-export-action="download-plan"]')?.addEventListener("click",()=>{a.onDownloadPlan?.()})}function v(t){return String(t??"").replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;").replaceAll('"',"&quot;").replaceAll("'","&#39;")}function L(t,e){return t?`<div class="generic-notice ${v(e||"info")}">${v(t)}</div>`:""}function D(t,e){let{stores:a,storeStatus:n,storeError:l,isLookingUpStores:c,hasLookedUpStores:o}=e;if(c){t.innerHTML=`
      ${L(n||"Looking up nearby supermarkets...","info")}
      <div class="generic-empty">Searching for nearby supermarkets. This usually takes a moment.</div>
    `;return}if(l){t.innerHTML=`
      ${L(l,"error")}
      <div class="generic-empty">Check the location fields and try the store lookup again.</div>
    `;return}if(!o){t.innerHTML=`
      <div class="generic-empty">
        Start with a location or preset, then use <strong>Find Nearby Supermarkets</strong> to load stores for the area.
      </div>
    `;return}if(!a.length){t.innerHTML=`
      ${L(n||"No nearby stores found.","info")}
      <div class="generic-empty">No supermarkets were found within the current search radius. Try increasing the radius or switching to a different location.</div>
    `;return}let g=a.map((u,h)=>`
        <div class="generic-list-item">
          <div class="generic-list-header">
            <div>
              <strong>${h+1}. ${v(u.name)}</strong>
              <div class="generic-muted">${v(u.address)}</div>
            </div>
            <span class="generic-badge">${Math.round(u.distance_m)} m</span>
          </div>
          <div class="generic-list-meta">
            <span><strong>Category:</strong> ${v(u.category)}</span>
            <span><strong>Coordinates:</strong> ${v(u.lat)}, ${v(u.lon)}</span>
          </div>
        </div>
      `).join("");t.innerHTML=`
    ${L(n||`Loaded ${a.length} nearby store${a.length===1?"":"s"}.`,"success")}
    <div class="generic-list">${g}</div>
  `}var de="https://nominatim.openstreetmap.org/search",I=[{id:"muscle_gain",label:"Muscle Gain",values:{locationQuery:"Mountain View, CA",lat:"",lon:"",radius_m:"8000",store_limit:"5",days:"1",shopping_mode:"balanced",protein:"170",calories:"2800",carbohydrate:"330",fat:"85",fiber:"35",calcium:"",iron:"",vitamin_c:"",vegetarian:!1,dairy_free:!1,vegan:!1,low_prep:!1,budget_friendly:!1,meal_style:"any"},notice:'Loaded the muscle gain preset for "Mountain View, CA".'},{id:"fat_loss",label:"Fat Loss",values:{locationQuery:"Mountain View, CA",lat:"",lon:"",radius_m:"8000",store_limit:"5",days:"1",shopping_mode:"balanced",protein:"150",calories:"1800",carbohydrate:"160",fat:"55",fiber:"30",calcium:"",iron:"",vitamin_c:"",vegetarian:!1,dairy_free:!1,vegan:!1,low_prep:!1,budget_friendly:!1,meal_style:"any"},notice:'Loaded the fat loss preset for "Mountain View, CA".'},{id:"maintenance",label:"Maintenance",values:{locationQuery:"Mountain View, CA",lat:"",lon:"",radius_m:"8000",store_limit:"5",days:"1",shopping_mode:"balanced",protein:"130",calories:"2200",carbohydrate:"240",fat:"70",fiber:"30",calcium:"",iron:"",vitamin_c:"",vegetarian:!1,dairy_free:!1,vegan:!1,low_prep:!1,budget_friendly:!1,meal_style:"any"},notice:'Loaded the maintenance preset for "Mountain View, CA".'},{id:"high_protein_vegetarian",label:"High-Protein Vegetarian",values:{locationQuery:"Mountain View, CA",lat:"",lon:"",radius_m:"8000",store_limit:"5",days:"1",shopping_mode:"balanced",protein:"140",calories:"2100",carbohydrate:"220",fat:"70",fiber:"32",calcium:"",iron:"18",vitamin_c:"",vegetarian:!0,dairy_free:!1,vegan:!1,low_prep:!1,budget_friendly:!1,meal_style:"any"},notice:'Loaded the high-protein vegetarian preset for "Mountain View, CA".'},{id:"budget_friendly_healthy",label:"Budget-Friendly Healthy",values:{locationQuery:"Mountain View, CA",lat:"",lon:"",radius_m:"8000",store_limit:"5",days:"1",shopping_mode:"balanced",protein:"120",calories:"2100",carbohydrate:"230",fat:"65",fiber:"35",calcium:"",iron:"",vitamin_c:"",vegetarian:!1,dairy_free:!1,vegan:!1,low_prep:!1,budget_friendly:!0,meal_style:"any"},notice:'Loaded the budget-friendly healthy preset for "Mountain View, CA".'}],i={locationQuery:"Mountain View, CA",lat:"",lon:"",radius_m:"8000",store_limit:"5",days:"1",shopping_mode:"balanced",protein:"130",calories:"2200",carbohydrate:"240",fat:"70",fiber:"30",calcium:"",iron:"",vitamin_c:"",vegetarian:!1,dairy_free:!1,vegan:!1,low_prep:!1,budget_friendly:!1,meal_style:"any",pantry_items:[],stores:[],storesLookupContext:null,recommendation:null,errors:{},formNotice:null,storeStatus:"",storeError:"",recommendationStatus:"",recommendationError:"",exportNotice:null,isLookingUpStores:!1,isGeneratingRecommendations:!1,isLocating:!1,isResolvingAddress:!1,hasLookedUpStores:!1,hasRequestedRecommendation:!1,presets:I};function m(t){if(t==null||String(t).trim()==="")return null;let e=Number(t);return Number.isFinite(e)?e:null}function Y(t){let e=m(t.lat),a=m(t.lon);return e!==null&&a!==null&&e>=-90&&e<=90&&a>=-180&&a<=180}function W(t){let e=m(t.lat),a=m(t.lon),n=m(t.radius_m);return e===null||a===null||n===null?null:{lat:Number(e.toFixed(6)),lon:Number(a.toFixed(6)),radius_m:Math.round(n)}}function ue(t,e){return!t||!e?!1:t.lat===e.lat&&t.lon===e.lon&&t.radius_m===e.radius_m}function pe(t,e="recommend"){let a={},n=String(t.locationQuery||"").trim(),l=m(t.lat),c=m(t.lon),o=m(t.protein),g=m(t.calories),u=[["carbohydrate","carbohydrate"],["fat","fat"],["fiber","fiber"],["calcium","calcium"],["iron","iron"],["vitamin_c","vitamin C"]],h=Y(t);if(!n&&!h&&(a.locationQuery="Enter a city or address, or provide coordinates in Advanced location settings."),n||((l===null||l<-90||l>90)&&(a.lat="Enter a latitude between -90 and 90."),(c===null||c<-180||c>180)&&(a.lon="Enter a longitude between -180 and 180.")),e==="recommend"){(o===null||o<=0)&&(a.protein="Enter a protein target greater than 0."),(g===null||g<=0)&&(a.calories="Enter a calorie target greater than 0.");for(let[b,C]of u){let S=m(t[b]);S!==null&&S<=0&&(a[b]=`Enter a ${C} target greater than 0, or leave it blank.`)}}return a}async function ge(t,e=fetch){let a=String(t||"").trim();if(!a)throw new Error("Enter a city or address first.");let n=new URLSearchParams({q:a,format:"jsonv2",limit:"1"}),l=await e(`${de}?${n.toString()}`,{headers:{Accept:"application/json"}});if(!l.ok)throw new Error("Location search failed. Please try again.");let c=await l.json();if(!Array.isArray(c)||c.length===0)throw new Error("Could not find that location. Please try a different city or address.");let o=c[0];return{lat:Number(o.lat).toFixed(6),lon:Number(o.lon).toFixed(6),displayName:o.display_name||a}}function _(t,e="info"){i.formNotice=t?{message:t,kind:e}:null}function $(t,e="info"){i.exportNotice=t?{message:t,kind:e}:null}function me(t){Object.assign(i,t);for(let e of Object.keys(t))i.errors[e]&&delete i.errors[e]}function z(t){let e=pe(i,t);return i.errors=e,Object.keys(e).length?(_("Fix the highlighted fields before continuing.","error"),y(),!1):(i.formNotice?.kind==="error"&&_(null),!0)}function ye(){i.stores=[],i.storesLookupContext=null,i.recommendation=null,i.storeStatus="",i.storeError="",i.recommendationStatus="",i.recommendationError="",i.exportNotice=null,i.hasLookedUpStores=!1,i.hasRequestedRecommendation=!1}async function J(){let t=String(i.locationQuery||"").trim();if(!t)return Y(i);i.isResolvingAddress=!0,_(`Finding coordinates for "${t}"...`,"info"),y();try{let e=await ge(t);return i.lat=e.lat,i.lon=e.lon,delete i.errors.locationQuery,delete i.errors.lat,delete i.errors.lon,_(`Using coordinates for "${t}". Advanced settings were updated automatically.`,"success"),!0}catch(e){return i.errors.locationQuery=e.message||"Could not find that location. Please try a different city or address.",_(i.errors.locationQuery,"error"),y(),!1}finally{i.isResolvingAddress=!1}}async function fe(){if(!z("stores")||!await J())return;i.hasLookedUpStores=!0,i.storeError="",i.storeStatus="Looking up nearby supermarkets...",i.isLookingUpStores=!0,y();let e=new URLSearchParams({lat:i.lat,lon:i.lon,radius_m:i.radius_m,limit:i.store_limit});try{let a=await fetch(`/api/stores/nearby?${e.toString()}`),n=await a.json();if(!a.ok)throw new Error(n.error||"Store lookup failed.");i.stores=n.stores||[],i.storesLookupContext=W(i),i.storeStatus=i.stores.length?`Loaded ${i.stores.length} nearby supermarket${i.stores.length===1?"":"s"}.`:"No nearby supermarkets found for this location.",i.recommendation&&!i.recommendation.stores?.length&&(i.recommendation.stores=i.stores)}catch(a){i.stores=[],i.storeError=a.message||"Store lookup failed.",i.storeStatus=""}finally{i.isLookingUpStores=!1}y()}async function he(){if(!z("recommend")||!await J())return;i.hasRequestedRecommendation=!0,i.recommendation=null,i.recommendationError="",i.recommendationStatus="Generating recommendations...",i.exportNotice=null,i.isGeneratingRecommendations=!0,y();let e={location:{lat:Number(i.lat),lon:Number(i.lon)},targets:{protein:Number(i.protein),energy_fibre_kcal:Number(i.calories)},preferences:{vegetarian:i.vegetarian,dairy_free:i.dairy_free,vegan:i.vegan,low_prep:i.low_prep,budget_friendly:i.budget_friendly,meal_style:i.meal_style||"any"},pantry_items:Array.isArray(i.pantry_items)?i.pantry_items:[],store_limit:Number(i.store_limit),days:Number(i.days||1),shopping_mode:i.shopping_mode||"balanced"},a=W(i);i.hasLookedUpStores&&Array.isArray(i.stores)&&i.stores.length&&i.stores.length>=Number(i.store_limit)&&ue(i.storesLookupContext,a)&&(e.stores=i.stores.slice(0,Number(i.store_limit)));for(let[n,l]of Object.entries({carbohydrate:m(i.carbohydrate),fat:m(i.fat),fiber:m(i.fiber),calcium:m(i.calcium),iron:m(i.iron),vitamin_c:m(i.vitamin_c)}))l!==null&&(e.targets[n]=l);try{let n=await fetch("/api/recommendations/generic",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(e)}),l=await n.json();if(!n.ok)throw new Error(l.error||"Recommendation request failed.");i.recommendation=l,i.stores=l.stores||[],i.storesLookupContext=i.stores.length?a:null,i.hasLookedUpStores=!0,i.storeError="",i.storeStatus=i.stores.length?`Loaded ${i.stores.length} nearby supermarket${i.stores.length===1?"":"s"}.`:"No nearby supermarkets found for this location.",i.recommendationStatus=l.shopping_list?.length?"Shopping list ready.":"No shopping list was generated for the current inputs."}catch(n){i.recommendation=null,i.recommendationError=n.message||"Recommendation request failed.",i.recommendationStatus=""}finally{i.isGeneratingRecommendations=!1}y()}function _e(){if(!navigator.geolocation){_("Browser geolocation is not available here. Enter coordinates in Advanced location settings.","error"),y();return}i.isLocating=!0,_("Requesting your current location...","info"),y(),navigator.geolocation.getCurrentPosition(t=>{i.isLocating=!1,i.locationQuery="",i.lat=t.coords.latitude.toFixed(6),i.lon=t.coords.longitude.toFixed(6),delete i.errors.locationQuery,delete i.errors.lat,delete i.errors.lon,_("Location loaded from your browser. Advanced settings were updated automatically.","success"),y()},t=>{i.isLocating=!1,_({1:"Location access was denied. Enter a city, address, or coordinates manually.",2:"Your location could not be determined. Enter a city, address, or coordinates manually.",3:"Location lookup timed out. Enter a city, address, or coordinates manually."}[t.code]||"Location lookup failed. Enter a city, address, or coordinates manually.","error"),y()},{enableHighAccuracy:!1,timeout:1e4,maximumAge:3e5})}function be(t){let e=I.find(a=>a.id===t);e&&(Object.assign(i,e.values),i.pantry_items=Array.isArray(e.values?.pantry_items)?[...e.values.pantry_items]:[],i.errors={},ye(),_(e.notice,"success"),y())}async function X(t){if(!t)throw new Error("There is no recommendation to export yet.");if(navigator.clipboard?.writeText){await navigator.clipboard.writeText(t);return}let e=document.createElement("textarea");e.value=t,e.setAttribute("readonly","readonly"),e.style.position="fixed",e.style.opacity="0",document.body.appendChild(e),e.select();let a=document.execCommand("copy");if(document.body.removeChild(e),!a)throw new Error("Copy is not available in this browser.")}function ve(t,e){if(!e)throw new Error("There is no recommendation to export yet.");let a=new Blob([e],{type:"text/plain;charset=utf-8"}),n=URL.createObjectURL(a),l=document.createElement("a");l.href=n,l.download=t,document.body.appendChild(l),l.click(),document.body.removeChild(l),URL.revokeObjectURL(n)}async function $e(){try{await X(O(i.recommendation)),$("Copied the grouped shopping list.","success")}catch(t){$(t.message||"Could not copy the shopping list.","error")}y()}async function ke(){try{await X(M(i.recommendation)),$("Copied the full grocery plan.","success")}catch(t){$(t.message||"Could not copy the full plan.","error")}y()}function we(){try{ve("generic-grocery-plan.txt",M(i.recommendation)),$("Downloaded the grocery plan as text.","success")}catch(t){$(t.message||"Could not download the grocery plan.","error")}y()}function y(){K(document.getElementById("generic-form"),i,{onChange:me,onLookupStores:fe,onRecommend:he,onUseMyLocation:_e,onApplyPreset:be}),D(document.getElementById("generic-stores"),i),H(document.getElementById("generic-results"),i,{onCopyShoppingList:$e,onCopyFullPlan:ke,onDownloadPlan:we})}typeof document<"u"&&y();export{ge as geocodeAddress,pe as validateFormState};
