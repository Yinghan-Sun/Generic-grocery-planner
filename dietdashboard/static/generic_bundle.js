function k(e,t){return e.querySelector(`[name="${t}"]`)?.checked||!1}function ae(e,t){return[...e.querySelectorAll(`[name="${t}"]:checked`)].map(r=>r.value)}var se=[{id:"eggs",label:"Eggs"},{id:"milk",label:"Milk"},{id:"greek_yogurt",label:"Greek yogurt"},{id:"oats",label:"Oats"},{id:"rice",label:"Rice"},{id:"beans",label:"Beans"},{id:"lentils",label:"Lentils"},{id:"bananas",label:"Bananas"},{id:"broccoli",label:"Broccoli"},{id:"potatoes",label:"Potatoes"},{id:"olive_oil",label:"Olive oil"},{id:"peanut_butter",label:"Peanut butter"},{id:"tofu",label:"Tofu"},{id:"chicken_breast",label:"Chicken breast"}];function d(e){return String(e??"").replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;").replaceAll('"',"&quot;").replaceAll("'","&#39;")}function u(e,t){return e.errors?.[t]||""}function oe(e){return e.formNotice?.message?`
    <div class="generic-notice ${d(e.formNotice.kind||"info")}" role="status">
      ${d(e.formNotice.message)}
    </div>
  `:""}function K(e,t,r){let n=(t.presets||[]).map(p=>`
        <button type="button" class="generic-preset-button" data-preset-id="${d(p.id)}">
          ${d(p.label)}
        </button>
      `).join(""),l=t.isLocating||t.isResolvingAddress||t.isLookingUpStores||t.isGeneratingRecommendations,c=se.map(p=>`
        <label>
          <input
            name="pantry_items"
            type="checkbox"
            value="${d(p.id)}"
            ${(t.pantry_items||[]).includes(p.id)?"checked":""}
          />
          ${d(p.label)}
        </label>
      `).join("");e.innerHTML=`
    <form id="generic-input-form" novalidate>
      ${oe(t)}
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
            value="${d(t.locationQuery)}"
            aria-invalid="${u(t,"locationQuery")?"true":"false"}"
          />
          <span class="generic-field-error">${d(u(t,"locationQuery"))}</span>
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
            <option value="1" ${t.days==="1"?"selected":""}>1 day</option>
            <option value="3" ${t.days==="3"?"selected":""}>3 days</option>
            <option value="5" ${t.days==="5"?"selected":""}>5 days</option>
            <option value="7" ${t.days==="7"?"selected":""}>7 days</option>
          </select>
          <span class="generic-help">Daily targets stay the same. Quantities are scaled for the selected shopping window.</span>
        </label>
        <label>
          Shopping mode
          <select name="shopping_mode">
            <option value="balanced" ${t.shopping_mode==="balanced"?"selected":""}>Balanced</option>
            <option value="fresh" ${t.shopping_mode==="fresh"?"selected":""}>Fresh</option>
            <option value="bulk" ${t.shopping_mode==="bulk"?"selected":""}>Bulk</option>
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
            value="${d(t.calories)}"
            aria-invalid="${u(t,"calories")?"true":"false"}"
            required
          />
          <span class="generic-field-error">${d(u(t,"calories"))}</span>
        </label>
        <label>
          Protein (g)
          <input
            name="protein"
            type="number"
            min="1"
            step="1"
            value="${d(t.protein)}"
            aria-invalid="${u(t,"protein")?"true":"false"}"
            required
          />
          <span class="generic-field-error">${d(u(t,"protein"))}</span>
        </label>
        <label>
          Carbs (g)
          <input
            name="carbohydrate"
            type="number"
            min="1"
            step="1"
            value="${d(t.carbohydrate)}"
            aria-invalid="${u(t,"carbohydrate")?"true":"false"}"
          />
          <span class="generic-field-error">${d(u(t,"carbohydrate"))}</span>
        </label>
        <label>
          Fat (g)
          <input
            name="fat"
            type="number"
            min="1"
            step="1"
            value="${d(t.fat)}"
            aria-invalid="${u(t,"fat")?"true":"false"}"
          />
          <span class="generic-field-error">${d(u(t,"fat"))}</span>
        </label>
        <label>
          Fiber (g)
          <input
            name="fiber"
            type="number"
            min="1"
            step="1"
            value="${d(t.fiber)}"
            aria-invalid="${u(t,"fiber")?"true":"false"}"
          />
          <span class="generic-field-error">${d(u(t,"fiber"))}</span>
        </label>
      </div>

      <div class="generic-form-grid">
        <div class="generic-span-full">
          <h3>Food preferences</h3>
          <label style="display: block; margin-bottom: 0.75rem">
            Meal or use case
            <select name="meal_style">
              <option value="any" ${t.meal_style==="any"?"selected":""}>Any</option>
              <option value="breakfast" ${t.meal_style==="breakfast"?"selected":""}>Breakfast</option>
              <option value="lunch_dinner" ${t.meal_style==="lunch_dinner"?"selected":""}>Lunch / dinner</option>
              <option value="snack" ${t.meal_style==="snack"?"selected":""}>Snack</option>
            </select>
          </label>
          <div class="generic-checkboxes">
            <label>
              <input name="vegetarian" type="checkbox" ${t.vegetarian?"checked":""} />
              Vegetarian (includes eggs and dairy)
            </label>
            <label><input name="vegan" type="checkbox" ${t.vegan?"checked":""} /> Vegan</label>
            <label><input name="dairy_free" type="checkbox" ${t.dairy_free?"checked":""} /> Dairy-free</label>
            <label><input name="low_prep" type="checkbox" ${t.low_prep?"checked":""} /> Low prep</label>
            <label><input name="budget_friendly" type="checkbox" ${t.budget_friendly?"checked":""} /> Budget friendly</label>
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
              value="${d(t.calcium)}"
              aria-invalid="${u(t,"calcium")?"true":"false"}"
            />
            <span class="generic-field-error">${d(u(t,"calcium"))}</span>
          </label>
          <label>
            Iron (mg)
            <input
              name="iron"
              type="number"
              min="1"
              step="0.1"
              value="${d(t.iron)}"
              aria-invalid="${u(t,"iron")?"true":"false"}"
            />
            <span class="generic-field-error">${d(u(t,"iron"))}</span>
          </label>
          <label>
            Vitamin C (mg)
            <input
              name="vitamin_c"
              type="number"
              min="1"
              step="1"
              value="${d(t.vitamin_c)}"
              aria-invalid="${u(t,"vitamin_c")?"true":"false"}"
            />
            <span class="generic-field-error">${d(u(t,"vitamin_c"))}</span>
          </label>
        </div>
      </details>

      <div class="generic-actions">
        <button type="button" id="use-location-button" ${l?"disabled":""}>
          ${t.isLocating?"Locating...":"Use My Location"}
        </button>
        <button type="button" id="lookup-stores-button" ${l?"disabled":""}>
          ${t.isResolvingAddress||t.isLookingUpStores?"Looking Up...":"Find Nearby Supermarkets"}
        </button>
        <button type="submit" ${l?"disabled":""}>
          ${t.isResolvingAddress||t.isGeneratingRecommendations?"Generating...":"Build Shopping List"}
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
              value="${d(t.lat)}"
              aria-invalid="${u(t,"lat")?"true":"false"}"
            />
            <span class="generic-field-error">${d(u(t,"lat"))}</span>
          </label>
          <label>
            Longitude
            <input
              name="lon"
              type="number"
              step="any"
              value="${d(t.lon)}"
              aria-invalid="${u(t,"lon")?"true":"false"}"
            />
            <span class="generic-field-error">${d(u(t,"lon"))}</span>
          </label>
          <label>
            Search radius (m)
            <input name="radius_m" type="number" min="1" step="100" value="${d(t.radius_m)}" required />
            <span class="generic-help">How far to search for supermarkets around the selected point.</span>
          </label>
          <label>
            Nearby stores to show
            <input name="store_limit" type="number" min="1" max="25" step="1" value="${d(t.store_limit)}" required />
            <span class="generic-help">The list is always sorted by distance.</span>
          </label>
        </div>
      </details>
    </form>
  `;let o=e.querySelector("#generic-input-form"),g=()=>r.onChange({locationQuery:o.locationQuery.value,lat:o.lat.value,lon:o.lon.value,radius_m:o.radius_m.value,store_limit:o.store_limit.value,days:o.days.value,shopping_mode:o.shopping_mode.value,protein:o.protein.value,calories:o.calories.value,carbohydrate:o.carbohydrate.value,fat:o.fat.value,fiber:o.fiber.value,calcium:o.calcium.value,iron:o.iron.value,vitamin_c:o.vitamin_c.value,vegetarian:k(o,"vegetarian"),dairy_free:k(o,"dairy_free"),vegan:k(o,"vegan"),low_prep:k(o,"low_prep"),budget_friendly:k(o,"budget_friendly"),meal_style:o.meal_style.value,pantry_items:ae(o,"pantry_items")});o.addEventListener("change",g),o.addEventListener("input",g),o.addEventListener("submit",p=>{p.preventDefault(),g(),r.onRecommend()}),e.querySelector("#lookup-stores-button").addEventListener("click",()=>{g(),r.onLookupStores()}),e.querySelector("#use-location-button").addEventListener("click",()=>{g(),r.onUseMyLocation()}),e.querySelectorAll("[data-preset-id]").forEach(p=>{p.addEventListener("click",()=>{r.onApplyPreset(p.dataset.presetId)})})}function s(e){return String(e??"").replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;").replaceAll('"',"&quot;").replaceAll("'","&#39;")}function w(e,t){return e?`<div class="generic-notice ${s(t||"info")}">${s(e)}</div>`:""}function le(e,t,r){let n=Math.round((e-t)*10)/10;return`${n>0?"+":""}${n} ${r}`}function ce(e){return{protein_anchor:"Protein anchor",carb_base:"Carb base",produce:"Produce",calorie_booster:"Calorie booster"}[e]||"Recommended item"}var Q=[{role:"protein_anchor",title:"Protein picks"},{role:"carb_base",title:"Carb base"},{role:"produce",title:"Produce"},{role:"calorie_booster",title:"Extras / boosters"}],T=[{key:"one_stop_pick",title:"One-stop pick"},{key:"budget_pick",title:"Budget pick"},{key:"produce_pick",title:"Produce pick"},{key:"bulk_pick",title:"Bulk pick"}],O=[{label:"Protein",targetKey:"protein_target_g",estimatedKey:"protein_estimated_g",unit:"g"},{label:"Calories",targetKey:"calorie_target_kcal",estimatedKey:"calorie_estimated_kcal",unit:"kcal"},{label:"Carbs",targetKey:"carbohydrate_target_g",estimatedKey:"carbohydrate_estimated_g",unit:"g"},{label:"Fat",targetKey:"fat_target_g",estimatedKey:"fat_estimated_g",unit:"g"},{label:"Fiber",targetKey:"fiber_target_g",estimatedKey:"fiber_estimated_g",unit:"g"},{label:"Calcium",targetKey:"calcium_target_mg",estimatedKey:"calcium_estimated_mg",unit:"mg"},{label:"Iron",targetKey:"iron_target_mg",estimatedKey:"iron_estimated_mg",unit:"mg"},{label:"Vitamin C",targetKey:"vitamin_c_target_mg",estimatedKey:"vitamin_c_estimated_mg",unit:"mg"}];function de(e,t){return!e||e[t.targetKey]===void 0||e[t.estimatedKey]===void 0?null:`${t.label}: ${e[t.estimatedKey]} ${t.unit} (target ${e[t.targetKey]} ${t.unit})`}function U(e){let t=String(e?.substitution_reason||"").trim(),r=String(e?.substitution||"").trim();return t?r&&t.toLowerCase().startsWith(r.toLowerCase())?t.slice(r.length).trim():t:""}function G(e,t=!0){return Q.map(r=>{let n=(e.shopping_list||[]).filter(c=>c.role===r.role);if(!n.length)return"";let l=n.map(c=>{let o=[`- ${c.name}: ${c.quantity_display}`];if(t&&c.reason_short&&o.push(`  ${c.reason_short}`),t&&c.typical_item_cost!==null&&c.typical_item_cost!==void 0){let g=c.estimated_price_low!==null&&c.estimated_price_low!==void 0&&c.estimated_price_high!==null&&c.estimated_price_high!==void 0?` (range $${c.estimated_price_low}-$${c.estimated_price_high})`:"";o.push(`  Typical cost: $${c.typical_item_cost}${g}`)}return o.join(`
`)});return`${r.title}
${l.join(`
`)}`}).filter(Boolean).join(`

`)}function V(e){return T.map(t=>{let r=e?.[t.key];if(!r?.store_id)return null;let n=r.distance_m!==void 0&&r.distance_m!==null?`, about ${Math.round(Number(r.distance_m))} m away`:"";return`- ${t.title}: ${r.store_name} (${r.category||"store"}${n})${r.note?` - ${r.note}`:""}`}).filter(Boolean)}function I(e){if(!e?.shopping_list?.length)return"";let t=Number(e.days||1),r=String(e.shopping_mode||"balanced"),n=["Generic Grocery Plan",`Shopping window: ${t} ${t===1?"day":"days"}`,`Shopping mode: ${r}`,"",G(e,!1)];e.estimated_basket_cost!==void 0&&(n.push("",`Estimated typical basket cost: $${e.estimated_basket_cost}`),e.estimated_basket_cost_low!==void 0&&e.estimated_basket_cost_high!==void 0&&n.push(`Typical basket range: $${e.estimated_basket_cost_low}-$${e.estimated_basket_cost_high}`),e.price_adjustment_note&&n.push(e.price_adjustment_note),e.price_coverage_note&&n.push(e.price_coverage_note));let l=V(e);return l.length&&n.push("","Recommended store picks",...l),n.filter(Boolean).join(`
`)}function M(e){if(!e?.shopping_list?.length)return"";let t=Number(e.days||1),r=String(e.shopping_mode||"balanced"),n=e.nutrition_summary||{},l=O.map(g=>de(n,g)).filter(Boolean),c=V(e),o=["Generic Grocery Plan",`Shopping window: ${t} ${t===1?"day":"days"}`,`Shopping mode: ${r}`];return l.length&&o.push("","Key nutrition targets",...l),e.estimated_basket_cost!==void 0&&(o.push("",`Estimated typical basket cost: $${e.estimated_basket_cost}`),e.estimated_basket_cost_low!==void 0&&e.estimated_basket_cost_high!==void 0&&o.push(`Typical basket range: $${e.estimated_basket_cost_low}-$${e.estimated_basket_cost_high}`),e.price_adjustment_note&&o.push(e.price_adjustment_note),e.price_coverage_note&&o.push(e.price_coverage_note),e.basket_cost_note&&o.push(e.basket_cost_note),e.price_confidence_note&&o.push(e.price_confidence_note)),c.length&&o.push("","Recommended store picks",...c),o.push("","Shopping list",G(e,!0)),Array.isArray(e.assumptions)&&e.assumptions.length&&o.push("","Approximate guidance",...e.assumptions.map(g=>`- ${g}`)),o.filter(Boolean).join(`
`)}function H(e,t,r={}){let{recommendation:n,recommendationStatus:l,recommendationError:c,isGeneratingRecommendations:o,hasRequestedRecommendation:g,exportNotice:p}=t;if(o){e.innerHTML=`
      ${w(l||"Generating recommendations...","info")}
      <div class="generic-empty">Building a generic shopping list from the nutrition targets and food preferences.</div>
    `;return}if(c){e.innerHTML=`
      ${w(c,"error")}
      <div class="generic-empty">The app could not build a shopping list for the current inputs. Adjust the targets or preferences and try again.</div>
    `;return}if(!g){e.innerHTML=`
      <div class="generic-empty">
        Build a shopping list to see recommended food categories, rough quantities, and a simple nutrition summary.
      </div>
    `;return}if(!n){e.innerHTML=`
      ${w(l||"No recommendations available.","info")}
      <div class="generic-empty">No shopping list could be generated from the current targets and preferences. Try lowering the targets or relaxing the filters.</div>
    `;return}let h=n.nutrition_summary,b=Number(n.days||t.days||1),C=String(n.shopping_mode||t.shopping_mode||"balanced"),L=0,ee=a=>`
        <div class="generic-list-item">
          <div class="generic-list-header">
            <div>
              <strong>${L+=1}. ${s(a.name)}</strong>
              <div class="generic-muted">Suggested buy: ${s(a.quantity_display)}</div>
            </div>
            <span class="generic-badge">${s(ce(a.role))}</span>
          </div>
          <div class="generic-muted" style="margin-top: 0.5rem"><strong>${s(a.reason_short||"")}</strong></div>
          <div class="generic-muted" style="margin-top: 0.25rem">${s(a.why_selected||a.reason)}</div>
          ${a.value_reason_short?`<div class="generic-muted" style="margin-top: 0.25rem"><strong>Value note:</strong> ${s(a.value_reason_short)}${a.price_efficiency_note?` <span>${s(a.price_efficiency_note)}</span>`:""}</div>`:""}
          <div class="generic-muted" style="margin-top: 0.25rem">${s(a.reason)}</div>
          ${a.substitution?`<div class="generic-muted" style="margin-top: 0.35rem"><strong>Swap option:</strong> ${s(a.substitution)}${U(a)?` <span>${s(U(a))}</span>`:""}</div>`:""}
          <div class="generic-list-meta">
            <span><strong>Protein:</strong> ${s(a.estimated_protein_g)} g</span>
            <span><strong>Calories:</strong> ${s(a.estimated_calories_kcal)} kcal</span>
          </div>
          ${a.estimated_item_cost!==null&&a.estimated_item_cost!==void 0?`<div class="generic-muted" style="margin-top: 0.35rem"><strong>Typical regional price:</strong> $${s(a.typical_unit_price??a.estimated_unit_price)} ${s(a.price_unit_display||"")}; typical item cost about <strong>$${s(a.typical_item_cost??a.estimated_item_cost)}</strong>${a.estimated_price_low!==null&&a.estimated_price_low!==void 0&&a.estimated_price_high!==null&&a.estimated_price_high!==void 0?` <span>(regional range $${s(a.estimated_price_low)}-$${s(a.estimated_price_high)})</span>`:""}.</div>`:""}
        </div>
      `,te=Q.map(a=>{let f=n.shopping_list.filter(re=>re.role===a.role);return f.length?`
      <div class="generic-list-item" style="margin-top: 1rem">
        <div class="generic-inline-group">
          <h3>${s(a.title)}</h3>
          <span class="generic-badge">${f.length} ${f.length===1?"item":"items"}</span>
        </div>
        <div class="generic-list">
          ${f.map(ee).join("")}
        </div>
      </div>
    `:""}).join(""),ie=(n.assumptions||[]).map(a=>`<li>${s(a)}</li>`).join(""),S=(n.pantry_notes||[]).map(a=>`<li>${s(a)}</li>`).join(""),N=(n.scaling_notes||[]).map(a=>`<li>${s(a)}</li>`).join(""),A=(n.warnings||[]).map(a=>`<li>${s(a)}</li>`).join(""),E=(n.split_notes||[]).map(a=>`<li>${s(a)}</li>`).join(""),R=(n.realism_notes||[]).map(a=>`<li>${s(a)}</li>`).join(""),j=[n.estimated_basket_cost_low!==void 0&&n.estimated_basket_cost_high!==void 0?`<p class="generic-muted"><strong>Typical basket range:</strong> about $${s(n.estimated_basket_cost_low)}-$${s(n.estimated_basket_cost_high)}</p>`:"",n.price_area_name?`<p class="generic-muted" style="margin-top: 0.5rem"><strong>Regional price area:</strong> ${s(n.price_area_name)} (${s(n.price_area_code||"")})</p>`:"",n.price_source_note?`<p class="generic-muted" style="margin-top: 0.5rem">${s(n.price_source_note)}</p>`:"",n.price_adjustment_note?`<p class="generic-muted" style="margin-top: 0.5rem">${s(n.price_adjustment_note)}</p>`:"",n.basket_cost_note?`<p class="generic-muted" style="margin-top: 0.5rem">${s(n.basket_cost_note)}</p>`:"",n.price_confidence_note?`<p class="generic-muted" style="margin-top: 0.5rem">${s(n.price_confidence_note)}</p>`:""].filter(Boolean).join(""),F=(n.store_fit_notes||[]).map(a=>`
        <div class="generic-list-item" style="margin-top: 0.75rem">
          <div class="generic-inline-group">
            <h3>${s(a.store_name||"Nearby store")}</h3>
            <span class="generic-badge">${s(a.fit_label||"Store fit")}</span>
          </div>
          <div class="generic-muted"><strong>${s(a.category||"store")}</strong>${a.distance_m!==void 0&&a.distance_m!==null?` \u2022 about ${s(Number(a.distance_m).toFixed(0))} m away`:""}</div>
          <div class="generic-muted" style="margin-top: 0.25rem">${s(a.note||"")}</div>
        </div>
      `).join(""),q=T.map(a=>{let f=n[a.key];return f?.store_id?`
        <div class="generic-list-item" style="margin-top: 0.75rem">
          <div class="generic-inline-group">
            <h3>${s(a.title)}</h3>
            <span class="generic-badge">${s(f.store_name||"Nearby store")}</span>
          </div>
          <div class="generic-muted"><strong>${s(f.category||"store")}</strong>${f.distance_m!==void 0&&f.distance_m!==null?` \u2022 about ${s(Number(f.distance_m).toFixed(0))} m away`:""}</div>
          <div class="generic-muted" style="margin-top: 0.25rem">${s(f.note||"")}</div>
        </div>
      `:""}).join(""),B=(n.meal_suggestions||[]).map(a=>`
        <div class="generic-list-item" style="margin-top: 0.75rem">
          <div class="generic-inline-group">
            <h3>${s(a.title||"Meal idea")}</h3>
            <span class="generic-badge">${s(String(a.meal_type||"idea").replaceAll("_"," "))}</span>
          </div>
          <div class="generic-muted"><strong>${s((a.items||[]).join(", "))}</strong></div>
          ${a.description?`<div class="generic-muted" style="margin-top: 0.25rem">${s(a.description)}</div>`:""}
        </div>
      `).join(""),ne=O.filter(a=>h?.[a.targetKey]!==void 0&&h?.[a.estimatedKey]!==void 0).map(a=>`
        <div class="generic-summary-metric">
          <div class="generic-muted">${s(a.label)}</div>
          <strong>${s(h[a.estimatedKey])} ${s(a.unit)}</strong>
          <div>Target: ${s(h[a.targetKey])} ${s(a.unit)}</div>
          <div class="generic-muted">Difference: ${s(le(h[a.estimatedKey],h[a.targetKey],a.unit))}</div>
        </div>
      `).join("");e.innerHTML=`
    ${w(l||"Recommendation ready.","success")}
    ${w(p?.message,p?.kind)}
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
      ${te||'<div class="generic-empty">Your pantry already covers the suggested basket for this plan. Review the notes below if you still want a small top-up shop.</div>'}
    </div>
    ${q?`<div class="generic-list-item" style="margin-top: 1rem">
            <div class="generic-inline-group">
              <h3>Recommended store picks for this list</h3>
              <span class="generic-badge">${T.filter(a=>n[a.key]?.store_id).length} picks</span>
            </div>
            <p class="generic-muted">These are quick store-type recommendations based on the basket style and nearby store mix. They do not reflect exact inventory.</p>
            ${q}
          </div>`:""}
    ${F?`<div class="generic-list-item" style="margin-top: 1rem">
            <div class="generic-inline-group">
              <h3>Best nearby store fits for this list</h3>
              <span class="generic-badge">${(n.store_fit_notes||[]).length} suggestions</span>
            </div>
            <p class="generic-muted">These are coarse store-fit suggestions based on the basket style, shopping mode, and nearby store type. They do not reflect exact inventory.</p>
            ${F}
          </div>`:""}
    ${B?`<div class="generic-list-item" style="margin-top: 1rem">
            <div class="generic-inline-group">
              <h3>Example ways to use this list</h3>
              <span class="generic-badge">${(n.meal_suggestions||[]).length} ideas</span>
            </div>
            <p class="generic-muted">These are lightweight examples built from the same recommended items. They are not a full meal plan.</p>
            ${B}
          </div>`:""}
    ${N||A||E||R||S?`<div class="generic-list-item" style="margin-top: 1rem">
            <div class="generic-inline-group">
              <h3>Shopping Notes</h3>
              <span class="generic-badge">${n.adjusted_by_split?"Scaling and realism guidance":"Scaling guidance"}</span>
            </div>
            ${N?`<p class="generic-muted"><strong>Scaling notes</strong></p><ul class="generic-assumptions">${N}</ul>`:""}
            ${E?`<p class="generic-muted" style="margin-top: 0.75rem"><strong>Split notes</strong></p><ul class="generic-assumptions">${E}</ul>`:""}
            ${R?`<p class="generic-muted" style="margin-top: 0.75rem"><strong>Realism notes</strong></p><ul class="generic-assumptions">${R}</ul>`:""}
            ${S?`<p class="generic-muted" style="margin-top: 0.75rem"><strong>Pantry adjustments</strong></p><ul class="generic-assumptions">${S}</ul>`:""}
            ${A?`<p class="generic-muted" style="margin-top: 0.75rem"><strong>Warnings</strong></p><ul class="generic-assumptions">${A}</ul>`:""}
          </div>`:""}
    <div class="generic-list-item" style="margin-top: 1rem">
      <div class="generic-inline-group">
        <h3>Nutrition Summary</h3>
        <span class="generic-badge">${b===1?"Daily total":`${b}-day total`}</span>
      </div>
      <div class="generic-summary-grid">
        ${ne}
      </div>
    </div>
    <div class="generic-list-item" style="margin-top: 1rem">
      <div class="generic-inline-group">
        <h3>Approximate Guidance</h3>
        <span class="generic-badge">Demo-friendly estimate</span>
      </div>
      <p class="generic-muted">Use this list as a practical starting point, not as exact store inventory or guaranteed product availability.</p>
      <ul class="generic-assumptions">${ie}</ul>
    </div>
    ${j?`<div class="generic-list-item" style="margin-top: 1rem">
            <div class="generic-inline-group">
              <h3>Pricing notes</h3>
              <span class="generic-badge">Typical regional estimate</span>
            </div>
            ${j}
          </div>`:""}
  `,e.querySelector('[data-export-action="copy-shopping"]')?.addEventListener("click",()=>{r.onCopyShoppingList?.()}),e.querySelector('[data-export-action="copy-plan"]')?.addEventListener("click",()=>{r.onCopyFullPlan?.()}),e.querySelector('[data-export-action="download-plan"]')?.addEventListener("click",()=>{r.onDownloadPlan?.()})}function v(e){return String(e??"").replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;").replaceAll('"',"&quot;").replaceAll("'","&#39;")}function x(e,t){return e?`<div class="generic-notice ${v(t||"info")}">${v(e)}</div>`:""}function D(e,t){let{stores:r,storeStatus:n,storeError:l,isLookingUpStores:c,hasLookedUpStores:o}=t;if(c){e.innerHTML=`
      ${x(n||"Looking up nearby supermarkets...","info")}
      <div class="generic-empty">Searching for nearby supermarkets. This usually takes a moment.</div>
    `;return}if(l){e.innerHTML=`
      ${x(l,"error")}
      <div class="generic-empty">Check the location fields and try the store lookup again.</div>
    `;return}if(!o){e.innerHTML=`
      <div class="generic-empty">
        Start with a location or preset, then use <strong>Find Nearby Supermarkets</strong> to load stores for the area.
      </div>
    `;return}if(!r.length){e.innerHTML=`
      ${x(n||"No nearby stores found.","info")}
      <div class="generic-empty">No supermarkets were found within the current search radius. Try increasing the radius or switching to a different location.</div>
    `;return}let g=r.map((p,h)=>`
        <div class="generic-list-item">
          <div class="generic-list-header">
            <div>
              <strong>${h+1}. ${v(p.name)}</strong>
              <div class="generic-muted">${v(p.address)}</div>
            </div>
            <span class="generic-badge">${Math.round(p.distance_m)} m</span>
          </div>
          <div class="generic-list-meta">
            <span><strong>Category:</strong> ${v(p.category)}</span>
            <span><strong>Coordinates:</strong> ${v(p.lat)}, ${v(p.lon)}</span>
          </div>
        </div>
      `).join("");e.innerHTML=`
    ${x(n||`Loaded ${r.length} nearby store${r.length===1?"":"s"}.`,"success")}
    <div class="generic-list">${g}</div>
  `}var pe="https://nominatim.openstreetmap.org/search",Y=[{id:"muscle_gain",label:"Muscle Gain",values:{locationQuery:"Mountain View, CA",lat:"",lon:"",radius_m:"8000",store_limit:"5",days:"1",shopping_mode:"balanced",protein:"170",calories:"2800",carbohydrate:"330",fat:"85",fiber:"35",calcium:"",iron:"",vitamin_c:"",vegetarian:!1,dairy_free:!1,vegan:!1,low_prep:!1,budget_friendly:!1,meal_style:"any"},notice:'Loaded the muscle gain preset for "Mountain View, CA".'},{id:"fat_loss",label:"Fat Loss",values:{locationQuery:"Mountain View, CA",lat:"",lon:"",radius_m:"8000",store_limit:"5",days:"1",shopping_mode:"balanced",protein:"150",calories:"1800",carbohydrate:"160",fat:"55",fiber:"30",calcium:"",iron:"",vitamin_c:"",vegetarian:!1,dairy_free:!1,vegan:!1,low_prep:!1,budget_friendly:!1,meal_style:"any"},notice:'Loaded the fat loss preset for "Mountain View, CA".'},{id:"maintenance",label:"Maintenance",values:{locationQuery:"Mountain View, CA",lat:"",lon:"",radius_m:"8000",store_limit:"5",days:"1",shopping_mode:"balanced",protein:"130",calories:"2200",carbohydrate:"240",fat:"70",fiber:"30",calcium:"",iron:"",vitamin_c:"",vegetarian:!1,dairy_free:!1,vegan:!1,low_prep:!1,budget_friendly:!1,meal_style:"any"},notice:'Loaded the maintenance preset for "Mountain View, CA".'},{id:"high_protein_vegetarian",label:"High-Protein Vegetarian",values:{locationQuery:"Mountain View, CA",lat:"",lon:"",radius_m:"8000",store_limit:"5",days:"1",shopping_mode:"balanced",protein:"140",calories:"2100",carbohydrate:"220",fat:"70",fiber:"32",calcium:"",iron:"18",vitamin_c:"",vegetarian:!0,dairy_free:!1,vegan:!1,low_prep:!1,budget_friendly:!1,meal_style:"any"},notice:'Loaded the high-protein vegetarian preset for "Mountain View, CA".'},{id:"budget_friendly_healthy",label:"Budget-Friendly Healthy",values:{locationQuery:"Mountain View, CA",lat:"",lon:"",radius_m:"8000",store_limit:"5",days:"1",shopping_mode:"balanced",protein:"120",calories:"2100",carbohydrate:"230",fat:"65",fiber:"35",calcium:"",iron:"",vitamin_c:"",vegetarian:!1,dairy_free:!1,vegan:!1,low_prep:!1,budget_friendly:!0,meal_style:"any"},notice:'Loaded the budget-friendly healthy preset for "Mountain View, CA".'}],i={locationQuery:"Mountain View, CA",lat:"",lon:"",radius_m:"8000",store_limit:"5",days:"1",shopping_mode:"balanced",protein:"130",calories:"2200",carbohydrate:"240",fat:"70",fiber:"30",calcium:"",iron:"",vitamin_c:"",vegetarian:!1,dairy_free:!1,vegan:!1,low_prep:!1,budget_friendly:!1,meal_style:"any",pantry_items:[],stores:[],storesLookupContext:null,recommendation:null,errors:{},formNotice:null,storeStatus:"",storeError:"",recommendationStatus:"",recommendationError:"",exportNotice:null,isLookingUpStores:!1,isGeneratingRecommendations:!1,isLocating:!1,isResolvingAddress:!1,hasLookedUpStores:!1,hasRequestedRecommendation:!1,presets:Y};function m(e){if(e==null||String(e).trim()==="")return null;let t=Number(e);return Number.isFinite(t)?t:null}function ue(e){if(e==="true")return!0;if(e==="false")return!1}function ge(e){if(e==null||String(e).trim()==="")return;let t=Number.parseInt(String(e),10);if(!(!Number.isFinite(t)||t<=0))return t}function W(){return typeof window>"u"||!window.location||typeof window.location.search!="string"?"":window.location.search}function me(e=W()){let t=new URLSearchParams(e||""),r={},n=ue(t.get("debug_scorer"));n!==void 0&&(r.debug_scorer=n);let l=ge(t.get("candidate_count"));l!==void 0&&(r.candidate_count=l);let c=String(t.get("scorer_model_path")||"").trim();return c&&(r.scorer_model_path=c),r}function z(e){let t=m(e.lat),r=m(e.lon);return t!==null&&r!==null&&t>=-90&&t<=90&&r>=-180&&r<=180}function P(e){let t=m(e.lat),r=m(e.lon),n=m(e.radius_m);return t===null||r===null||n===null?null:{lat:Number(t.toFixed(6)),lon:Number(r.toFixed(6)),radius_m:Math.round(n)}}function ye(e,t){return!e||!t?!1:e.lat===t.lat&&e.lon===t.lon&&e.radius_m===t.radius_m}function fe(e,t=W()){let r={location:{lat:Number(e.lat),lon:Number(e.lon)},targets:{protein:Number(e.protein),energy_fibre_kcal:Number(e.calories)},preferences:{vegetarian:e.vegetarian,dairy_free:e.dairy_free,vegan:e.vegan,low_prep:e.low_prep,budget_friendly:e.budget_friendly,meal_style:e.meal_style||"any"},pantry_items:Array.isArray(e.pantry_items)?e.pantry_items:[],store_limit:Number(e.store_limit),days:Number(e.days||1),shopping_mode:e.shopping_mode||"balanced"},n=P(e);e.hasLookedUpStores&&Array.isArray(e.stores)&&e.stores.length&&e.stores.length>=Number(e.store_limit)&&ye(e.storesLookupContext,n)&&(r.stores=e.stores.slice(0,Number(e.store_limit)));for(let[l,c]of Object.entries({carbohydrate:m(e.carbohydrate),fat:m(e.fat),fiber:m(e.fiber),calcium:m(e.calcium),iron:m(e.iron),vitamin_c:m(e.vitamin_c)}))c!==null&&(r.targets[l]=c);return Object.assign(r,me(t)),r}function he(e,t="recommend"){let r={},n=String(e.locationQuery||"").trim(),l=m(e.lat),c=m(e.lon),o=m(e.protein),g=m(e.calories),p=[["carbohydrate","carbohydrate"],["fat","fat"],["fiber","fiber"],["calcium","calcium"],["iron","iron"],["vitamin_c","vitamin C"]],h=z(e);if(!n&&!h&&(r.locationQuery="Enter a city or address, or provide coordinates in Advanced location settings."),n||((l===null||l<-90||l>90)&&(r.lat="Enter a latitude between -90 and 90."),(c===null||c<-180||c>180)&&(r.lon="Enter a longitude between -180 and 180.")),t==="recommend"){(o===null||o<=0)&&(r.protein="Enter a protein target greater than 0."),(g===null||g<=0)&&(r.calories="Enter a calorie target greater than 0.");for(let[b,C]of p){let L=m(e[b]);L!==null&&L<=0&&(r[b]=`Enter a ${C} target greater than 0, or leave it blank.`)}}return r}async function _e(e,t=fetch){let r=String(e||"").trim();if(!r)throw new Error("Enter a city or address first.");let n=new URLSearchParams({q:r,format:"jsonv2",limit:"1"}),l=await t(`${pe}?${n.toString()}`,{headers:{Accept:"application/json"}});if(!l.ok)throw new Error("Location search failed. Please try again.");let c=await l.json();if(!Array.isArray(c)||c.length===0)throw new Error("Could not find that location. Please try a different city or address.");let o=c[0];return{lat:Number(o.lat).toFixed(6),lon:Number(o.lon).toFixed(6),displayName:o.display_name||r}}function _(e,t="info"){i.formNotice=e?{message:e,kind:t}:null}function $(e,t="info"){i.exportNotice=e?{message:e,kind:t}:null}function be(e){Object.assign(i,e);for(let t of Object.keys(e))i.errors[t]&&delete i.errors[t]}function J(e){let t=he(i,e);return i.errors=t,Object.keys(t).length?(_("Fix the highlighted fields before continuing.","error"),y(),!1):(i.formNotice?.kind==="error"&&_(null),!0)}function ve(){i.stores=[],i.storesLookupContext=null,i.recommendation=null,i.storeStatus="",i.storeError="",i.recommendationStatus="",i.recommendationError="",i.exportNotice=null,i.hasLookedUpStores=!1,i.hasRequestedRecommendation=!1}async function X(){let e=String(i.locationQuery||"").trim();if(!e)return z(i);i.isResolvingAddress=!0,_(`Finding coordinates for "${e}"...`,"info"),y();try{let t=await _e(e);return i.lat=t.lat,i.lon=t.lon,delete i.errors.locationQuery,delete i.errors.lat,delete i.errors.lon,_(`Using coordinates for "${e}". Advanced settings were updated automatically.`,"success"),!0}catch(t){return i.errors.locationQuery=t.message||"Could not find that location. Please try a different city or address.",_(i.errors.locationQuery,"error"),y(),!1}finally{i.isResolvingAddress=!1}}async function $e(){if(!J("stores")||!await X())return;i.hasLookedUpStores=!0,i.storeError="",i.storeStatus="Looking up nearby supermarkets...",i.isLookingUpStores=!0,y();let t=new URLSearchParams({lat:i.lat,lon:i.lon,radius_m:i.radius_m,limit:i.store_limit});try{let r=await fetch(`/api/stores/nearby?${t.toString()}`),n=await r.json();if(!r.ok)throw new Error(n.error||"Store lookup failed.");i.stores=n.stores||[],i.storesLookupContext=P(i),i.storeStatus=i.stores.length?`Loaded ${i.stores.length} nearby supermarket${i.stores.length===1?"":"s"}.`:"No nearby supermarkets found for this location.",i.recommendation&&!i.recommendation.stores?.length&&(i.recommendation.stores=i.stores)}catch(r){i.stores=[],i.storeError=r.message||"Store lookup failed.",i.storeStatus=""}finally{i.isLookingUpStores=!1}y()}async function ke(){if(!J("recommend")||!await X())return;i.hasRequestedRecommendation=!0,i.recommendation=null,i.recommendationError="",i.recommendationStatus="Generating recommendations...",i.exportNotice=null,i.isGeneratingRecommendations=!0,y();let t=P(i),r=fe(i);try{let n=await fetch("/api/recommendations/generic",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(r)}),l=await n.json();if(!n.ok)throw new Error(l.error||"Recommendation request failed.");i.recommendation=l,i.stores=l.stores||[],i.storesLookupContext=i.stores.length?t:null,i.hasLookedUpStores=!0,i.storeError="",i.storeStatus=i.stores.length?`Loaded ${i.stores.length} nearby supermarket${i.stores.length===1?"":"s"}.`:"No nearby supermarkets found for this location.",i.recommendationStatus=l.shopping_list?.length?"Shopping list ready.":"No shopping list was generated for the current inputs."}catch(n){i.recommendation=null,i.recommendationError=n.message||"Recommendation request failed.",i.recommendationStatus=""}finally{i.isGeneratingRecommendations=!1}y()}function we(){if(!navigator.geolocation){_("Browser geolocation is not available here. Enter coordinates in Advanced location settings.","error"),y();return}i.isLocating=!0,_("Requesting your current location...","info"),y(),navigator.geolocation.getCurrentPosition(e=>{i.isLocating=!1,i.locationQuery="",i.lat=e.coords.latitude.toFixed(6),i.lon=e.coords.longitude.toFixed(6),delete i.errors.locationQuery,delete i.errors.lat,delete i.errors.lon,_("Location loaded from your browser. Advanced settings were updated automatically.","success"),y()},e=>{i.isLocating=!1,_({1:"Location access was denied. Enter a city, address, or coordinates manually.",2:"Your location could not be determined. Enter a city, address, or coordinates manually.",3:"Location lookup timed out. Enter a city, address, or coordinates manually."}[e.code]||"Location lookup failed. Enter a city, address, or coordinates manually.","error"),y()},{enableHighAccuracy:!1,timeout:1e4,maximumAge:3e5})}function Le(e){let t=Y.find(r=>r.id===e);t&&(Object.assign(i,t.values),i.pantry_items=Array.isArray(t.values?.pantry_items)?[...t.values.pantry_items]:[],i.errors={},ve(),_(t.notice,"success"),y())}async function Z(e){if(!e)throw new Error("There is no recommendation to export yet.");if(navigator.clipboard?.writeText){await navigator.clipboard.writeText(e);return}let t=document.createElement("textarea");t.value=e,t.setAttribute("readonly","readonly"),t.style.position="fixed",t.style.opacity="0",document.body.appendChild(t),t.select();let r=document.execCommand("copy");if(document.body.removeChild(t),!r)throw new Error("Copy is not available in this browser.")}function xe(e,t){if(!t)throw new Error("There is no recommendation to export yet.");let r=new Blob([t],{type:"text/plain;charset=utf-8"}),n=URL.createObjectURL(r),l=document.createElement("a");l.href=n,l.download=e,document.body.appendChild(l),l.click(),document.body.removeChild(l),URL.revokeObjectURL(n)}async function Ce(){try{await Z(I(i.recommendation)),$("Copied the grouped shopping list.","success")}catch(e){$(e.message||"Could not copy the shopping list.","error")}y()}async function Se(){try{await Z(M(i.recommendation)),$("Copied the full grocery plan.","success")}catch(e){$(e.message||"Could not copy the full plan.","error")}y()}function Ne(){try{xe("generic-grocery-plan.txt",M(i.recommendation)),$("Downloaded the grocery plan as text.","success")}catch(e){$(e.message||"Could not download the grocery plan.","error")}y()}function y(){K(document.getElementById("generic-form"),i,{onChange:be,onLookupStores:$e,onRecommend:ke,onUseMyLocation:we,onApplyPreset:Le}),D(document.getElementById("generic-stores"),i),H(document.getElementById("generic-results"),i,{onCopyShoppingList:Ce,onCopyFullPlan:Se,onDownloadPlan:Ne})}typeof document<"u"&&y();export{fe as buildRecommendationPayload,_e as geocodeAddress,me as getScorerQueryOverrides,ue as parseBooleanParam,ge as parsePositiveIntParam,he as validateFormState};
