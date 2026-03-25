function k(e,t){return e.querySelector(`[name="${t}"]`)?.checked||!1}function Fe(e,t){return[...e.querySelectorAll(`[name="${t}"]:checked`)].map(i=>i.value)}var De=[{id:"eggs",label:"Eggs"},{id:"milk",label:"Milk"},{id:"greek_yogurt",label:"Greek yogurt"},{id:"oats",label:"Oats"},{id:"rice",label:"Rice"},{id:"beans",label:"Beans"},{id:"lentils",label:"Lentils"},{id:"bananas",label:"Bananas"},{id:"broccoli",label:"Broccoli"},{id:"potatoes",label:"Potatoes"},{id:"olive_oil",label:"Olive oil"},{id:"peanut_butter",label:"Peanut butter"},{id:"tofu",label:"Tofu"},{id:"chicken_breast",label:"Chicken breast"}];function u(e){return String(e??"").replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;").replaceAll('"',"&quot;").replaceAll("'","&#39;")}function g(e,t){return e.errors?.[t]||""}function Ge(e){return e.formNotice?.message?`
    <div class="generic-notice ${u(e.formNotice.kind||"info")}" role="status">
      ${u(e.formNotice.message)}
    </div>
  `:""}function te(e,t,i){let n=(t.presets||[]).map(p=>`
        <button type="button" class="generic-preset-button" data-preset-id="${u(p.id)}">
          ${u(p.label)}
        </button>
      `).join(""),l=t.isLocating||t.isResolvingAddress||t.isLookingUpStores||t.isGeneratingRecommendations,d=De.map(p=>`
        <label>
          <input
            name="pantry_items"
            type="checkbox"
            value="${u(p.id)}"
            ${(t.pantry_items||[]).includes(p.id)?"checked":""}
          />
          ${u(p.label)}
        </label>
      `).join("");e.innerHTML=`
    <form id="generic-input-form" novalidate>
      ${Ge(t)}
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
            value="${u(t.locationQuery)}"
            aria-invalid="${g(t,"locationQuery")?"true":"false"}"
          />
          <span class="generic-field-error">${u(g(t,"locationQuery"))}</span>
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
            value="${u(t.calories)}"
            aria-invalid="${g(t,"calories")?"true":"false"}"
            required
          />
          <span class="generic-field-error">${u(g(t,"calories"))}</span>
        </label>
        <label>
          Protein (g)
          <input
            name="protein"
            type="number"
            min="1"
            step="1"
            value="${u(t.protein)}"
            aria-invalid="${g(t,"protein")?"true":"false"}"
            required
          />
          <span class="generic-field-error">${u(g(t,"protein"))}</span>
        </label>
        <label>
          Carbs (g)
          <input
            name="carbohydrate"
            type="number"
            min="1"
            step="1"
            value="${u(t.carbohydrate)}"
            aria-invalid="${g(t,"carbohydrate")?"true":"false"}"
          />
          <span class="generic-field-error">${u(g(t,"carbohydrate"))}</span>
        </label>
        <label>
          Fat (g)
          <input
            name="fat"
            type="number"
            min="1"
            step="1"
            value="${u(t.fat)}"
            aria-invalid="${g(t,"fat")?"true":"false"}"
          />
          <span class="generic-field-error">${u(g(t,"fat"))}</span>
        </label>
        <label>
          Fiber (g)
          <input
            name="fiber"
            type="number"
            min="1"
            step="1"
            value="${u(t.fiber)}"
            aria-invalid="${g(t,"fiber")?"true":"false"}"
          />
          <span class="generic-field-error">${u(g(t,"fiber"))}</span>
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
            ${d}
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
              value="${u(t.calcium)}"
              aria-invalid="${g(t,"calcium")?"true":"false"}"
            />
            <span class="generic-field-error">${u(g(t,"calcium"))}</span>
          </label>
          <label>
            Iron (mg)
            <input
              name="iron"
              type="number"
              min="1"
              step="0.1"
              value="${u(t.iron)}"
              aria-invalid="${g(t,"iron")?"true":"false"}"
            />
            <span class="generic-field-error">${u(g(t,"iron"))}</span>
          </label>
          <label>
            Vitamin C (mg)
            <input
              name="vitamin_c"
              type="number"
              min="1"
              step="1"
              value="${u(t.vitamin_c)}"
              aria-invalid="${g(t,"vitamin_c")?"true":"false"}"
            />
            <span class="generic-field-error">${u(g(t,"vitamin_c"))}</span>
          </label>
        </div>
      </details>

      <details class="generic-advanced">
        <summary>Advanced planner settings</summary>
        <p class="generic-help">Local demo mode keeps Route B enabled by default so learned candidates join the heuristic pool. Turn it off here only when you want a clean heuristic-only baseline comparison.</p>
        <div class="generic-form-grid">
          <label>
            Model candidates to add
            <input
              name="model_candidate_count"
              type="number"
              min="1"
              max="8"
              step="1"
              value="${u(t.model_candidate_count)}"
            />
            <span class="generic-help">How many learned candidate baskets to add before fusion and ranking.</span>
          </label>
          <label>
            Total candidates ranked
            <input
              name="candidate_count"
              type="number"
              min="1"
              max="12"
              step="1"
              value="${u(t.candidate_count)}"
            />
            <span class="generic-help">How many fused candidates the scorer ranks before choosing the final basket.</span>
          </label>
          <label>
            Candidate generator backend
            <select name="candidate_generator_backend">
              <option value="auto" ${t.candidate_generator_backend==="auto"?"selected":""}>Auto</option>
              <option value="logistic_regression" ${t.candidate_generator_backend==="logistic_regression"?"selected":""}>Logistic regression</option>
              <option value="random_forest" ${t.candidate_generator_backend==="random_forest"?"selected":""}>Random forest</option>
              <option value="hist_gradient_boosting" ${t.candidate_generator_backend==="hist_gradient_boosting"?"selected":""}>HistGradientBoosting</option>
            </select>
            <span class="generic-help">Auto uses the selected local artifact backend. Pick one explicitly if you want to compare backends.</span>
          </label>
        </div>
        <div class="generic-checkboxes" style="margin-top: 0.75rem">
          <label>
            <input name="enable_model_candidates" type="checkbox" ${t.enable_model_candidates?"checked":""} />
            Enable learned candidates
          </label>
          <label>
            <input name="debug_candidate_generation" type="checkbox" ${t.debug_candidate_generation?"checked":""} />
            Show candidate-generation debug
          </label>
          <label>
            <input name="debug_scorer" type="checkbox" ${t.debug_scorer?"checked":""} />
            Show scorer debug
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
              value="${u(t.lat)}"
              aria-invalid="${g(t,"lat")?"true":"false"}"
            />
            <span class="generic-field-error">${u(g(t,"lat"))}</span>
          </label>
          <label>
            Longitude
            <input
              name="lon"
              type="number"
              step="any"
              value="${u(t.lon)}"
              aria-invalid="${g(t,"lon")?"true":"false"}"
            />
            <span class="generic-field-error">${u(g(t,"lon"))}</span>
          </label>
          <label>
            Search radius (m)
            <input name="radius_m" type="number" min="1" step="100" value="${u(t.radius_m)}" required />
            <span class="generic-help">How far to search for supermarkets around the selected point.</span>
          </label>
          <label>
            Nearby stores to show
            <input name="store_limit" type="number" min="1" max="25" step="1" value="${u(t.store_limit)}" required />
            <span class="generic-help">The list is always sorted by distance.</span>
          </label>
        </div>
      </details>
    </form>
  `;let s=e.querySelector("#generic-input-form"),m=()=>i.onChange({locationQuery:s.locationQuery.value,lat:s.lat.value,lon:s.lon.value,radius_m:s.radius_m.value,store_limit:s.store_limit.value,days:s.days.value,shopping_mode:s.shopping_mode.value,protein:s.protein.value,calories:s.calories.value,carbohydrate:s.carbohydrate.value,fat:s.fat.value,fiber:s.fiber.value,calcium:s.calcium.value,iron:s.iron.value,vitamin_c:s.vitamin_c.value,vegetarian:k(s,"vegetarian"),dairy_free:k(s,"dairy_free"),vegan:k(s,"vegan"),low_prep:k(s,"low_prep"),budget_friendly:k(s,"budget_friendly"),meal_style:s.meal_style.value,enable_model_candidates:k(s,"enable_model_candidates"),model_candidate_count:s.model_candidate_count.value,candidate_generator_backend:s.candidate_generator_backend.value,debug_candidate_generation:k(s,"debug_candidate_generation"),debug_scorer:k(s,"debug_scorer"),candidate_count:s.candidate_count.value,pantry_items:Fe(s,"pantry_items")});s.addEventListener("change",m),s.addEventListener("input",m),s.addEventListener("submit",p=>{p.preventDefault(),m(),i.onRecommend()}),e.querySelector("#lookup-stores-button").addEventListener("click",()=>{m(),i.onLookupStores()}),e.querySelector("#use-location-button").addEventListener("click",()=>{m(),i.onUseMyLocation()}),e.querySelectorAll("[data-preset-id]").forEach(p=>{p.addEventListener("click",()=>{i.onApplyPreset(p.dataset.presetId)})})}function o(e){return String(e??"").replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;").replaceAll('"',"&quot;").replaceAll("'","&#39;")}function A(e,t){return e?`<div class="generic-notice ${o(t||"info")}">${o(e)}</div>`:""}function Oe(e,t,i){let n=Math.round((e-t)*10)/10;return`${n>0?"+":""}${n} ${i}`}function Ue(e){return{protein_anchor:"Protein anchor",carb_base:"Carb base",produce:"Produce",calorie_booster:"Calorie booster"}[e]||"Recommended item"}function L(e){let t=String(e||"heuristic").trim().toLowerCase();return t==="model"||t==="hybrid"||t==="repaired_model"?t:"heuristic"}function R(e){return{heuristic:"Heuristic",model:"Model",hybrid:"Hybrid",repaired_model:"Repaired model"}[L(e)]||"Heuristic"}function Ie(e){return`${R(e)} result`}function Ke(e){return`generic-badge-source-${L(e)}`}function qe(e,t){let i=Array.isArray(e)?e:[],n=[...new Set(i.map(l=>L(l)).filter(Boolean))];return n.length?n:[L(t)]}function He(e,t){let i=L(t);return e?i==="heuristic"?"Model path was enabled, but the highest-ranked basket still came from the heuristic pool.":i==="model"?"A model-generated candidate won the final ranking.":i==="repaired_model"?"A model-generated basket needed repair and still won the final ranking.":"A fused hybrid candidate won the final ranking.":"Model path disabled; the heuristic-only baseline produced this result."}function E(e){let t=Array.isArray(e)?e.filter(Boolean):[];return t.length?t.join(", "):"Not available"}function w(e,t=3){if(e==null||e==="")return"Not available";let i=Number(e);return Number.isFinite(i)?i.toFixed(t):String(e)}var ie=[{role:"protein_anchor",title:"Protein picks"},{role:"carb_base",title:"Carb base"},{role:"produce",title:"Produce"},{role:"calorie_booster",title:"Extras / boosters"}],I=[{key:"one_stop_pick",title:"One-stop pick"},{key:"budget_pick",title:"Budget pick"},{key:"produce_pick",title:"Produce pick"},{key:"bulk_pick",title:"Bulk pick"}],ae=[{label:"Protein",targetKey:"protein_target_g",estimatedKey:"protein_estimated_g",unit:"g"},{label:"Calories",targetKey:"calorie_target_kcal",estimatedKey:"calorie_estimated_kcal",unit:"kcal"},{label:"Carbs",targetKey:"carbohydrate_target_g",estimatedKey:"carbohydrate_estimated_g",unit:"g"},{label:"Fat",targetKey:"fat_target_g",estimatedKey:"fat_estimated_g",unit:"g"},{label:"Fiber",targetKey:"fiber_target_g",estimatedKey:"fiber_estimated_g",unit:"g"},{label:"Calcium",targetKey:"calcium_target_mg",estimatedKey:"calcium_estimated_mg",unit:"mg"},{label:"Iron",targetKey:"iron_target_mg",estimatedKey:"iron_estimated_mg",unit:"mg"},{label:"Vitamin C",targetKey:"vitamin_c_target_mg",estimatedKey:"vitamin_c_estimated_mg",unit:"mg"}];function Qe(e,t){return!e||e[t.targetKey]===void 0||e[t.estimatedKey]===void 0?null:`${t.label}: ${e[t.estimatedKey]} ${t.unit} (target ${e[t.targetKey]} ${t.unit})`}function ne(e){let t=String(e?.substitution_reason||"").trim(),i=String(e?.substitution||"").trim();return t?i&&t.toLowerCase().startsWith(i.toLowerCase())?t.slice(i.length).trim():t:""}function oe(e,t=!0){return ie.map(i=>{let n=(e.shopping_list||[]).filter(d=>d.role===i.role);if(!n.length)return"";let l=n.map(d=>{let s=[`- ${d.name}: ${d.quantity_display}`];if(t&&d.reason_short&&s.push(`  ${d.reason_short}`),t&&d.typical_item_cost!==null&&d.typical_item_cost!==void 0){let m=d.estimated_price_low!==null&&d.estimated_price_low!==void 0&&d.estimated_price_high!==null&&d.estimated_price_high!==void 0?` (range $${d.estimated_price_low}-$${d.estimated_price_high})`:"";s.push(`  Typical cost: $${d.typical_item_cost}${m}`)}return s.join(`
`)});return`${i.title}
${l.join(`
`)}`}).filter(Boolean).join(`

`)}function re(e){return I.map(t=>{let i=e?.[t.key];if(!i?.store_id)return null;let n=i.distance_m!==void 0&&i.distance_m!==null?`, about ${Math.round(Number(i.distance_m))} m away`:"";return`- ${t.title}: ${i.store_name} (${i.category||"store"}${n})${i.note?` - ${i.note}`:""}`}).filter(Boolean)}function se(e){if(!e?.shopping_list?.length)return"";let t=Number(e.days||1),i=String(e.shopping_mode||"balanced"),n=["Generic Grocery Plan",`Shopping window: ${t} ${t===1?"day":"days"}`,`Shopping mode: ${i}`,"",oe(e,!1)];e.estimated_basket_cost!==void 0&&(n.push("",`Estimated typical basket cost: $${e.estimated_basket_cost}`),e.estimated_basket_cost_low!==void 0&&e.estimated_basket_cost_high!==void 0&&n.push(`Typical basket range: $${e.estimated_basket_cost_low}-$${e.estimated_basket_cost_high}`),e.price_adjustment_note&&n.push(e.price_adjustment_note),e.price_coverage_note&&n.push(e.price_coverage_note));let l=re(e);return l.length&&n.push("","Recommended store picks",...l),n.filter(Boolean).join(`
`)}function K(e){if(!e?.shopping_list?.length)return"";let t=Number(e.days||1),i=String(e.shopping_mode||"balanced"),n=e.nutrition_summary||{},l=ae.map(m=>Qe(n,m)).filter(Boolean),d=re(e),s=["Generic Grocery Plan",`Shopping window: ${t} ${t===1?"day":"days"}`,`Shopping mode: ${i}`];return l.length&&s.push("","Key nutrition targets",...l),e.estimated_basket_cost!==void 0&&(s.push("",`Estimated typical basket cost: $${e.estimated_basket_cost}`),e.estimated_basket_cost_low!==void 0&&e.estimated_basket_cost_high!==void 0&&s.push(`Typical basket range: $${e.estimated_basket_cost_low}-$${e.estimated_basket_cost_high}`),e.price_adjustment_note&&s.push(e.price_adjustment_note),e.price_coverage_note&&s.push(e.price_coverage_note),e.basket_cost_note&&s.push(e.basket_cost_note),e.price_confidence_note&&s.push(e.price_confidence_note)),d.length&&s.push("","Recommended store picks",...d),s.push("","Shopping list",oe(e,!0)),Array.isArray(e.assumptions)&&e.assumptions.length&&s.push("","Approximate guidance",...e.assumptions.map(m=>`- ${m}`)),s.filter(Boolean).join(`
`)}function le(e,t,i={}){let{recommendation:n,recommendationStatus:l,recommendationError:d,isGeneratingRecommendations:s,hasRequestedRecommendation:m,exportNotice:p}=t;if(s){e.innerHTML=`
      ${A(l||"Generating recommendations...","info")}
      <div class="generic-empty">Building a generic shopping list from the nutrition targets and food preferences.</div>
    `;return}if(d){e.innerHTML=`
      ${A(d,"error")}
      <div class="generic-empty">The app could not build a shopping list for the current inputs. Adjust the targets or preferences and try again.</div>
    `;return}if(!m){e.innerHTML=`
      <div class="generic-empty">
        Build a shopping list to see recommended food categories, rough quantities, and a simple nutrition summary.
      </div>
    `;return}if(!n){e.innerHTML=`
      ${A(l||"No recommendations available.","info")}
      <div class="generic-empty">No shopping list could be generated from the current targets and preferences. Try lowering the targets or relaxing the filters.</div>
    `;return}let b=n.nutrition_summary,h=Number(n.days||t.days||1),T=String(n.shopping_mode||t.shopping_mode||"balanced"),$=L(n.selected_candidate_source),$e=qe(n.selected_candidate_sources,$),N=n.candidate_generation_debug||{},Q=n.scoring_debug||{},c=n.candidate_comparison_debug||{},P=N.model_candidates_enabled??!!t.enable_model_candidates,V=N.heuristic_candidate_count,z=N.model_candidate_count,j=N.fused_candidate_count??n.candidate_count_considered,ke=N.candidate_generator_backend||t.candidate_generator_backend||"auto",we=n.scorer_backend||"unknown",Ce=n.selected_candidate_id||"unknown",B=n.candidate_count_considered??j,Le=!!(n.candidate_generation_debug||n.scoring_debug||n.candidate_comparison_debug||n.selected_candidate_source),Se=c.diagnosis_text||He(P,$),Y=c.selected_vs_best_heuristic||null,x=c.selected_candidate_contrast||{},Ne=x.best_heuristic_candidate_shopping_food_ids||c.best_heuristic_candidate_shopping_food_ids||[],Ae=x.best_model_candidate_shopping_food_ids||c.best_model_candidate_shopping_food_ids||[],W=Array.isArray(Q.candidates)?Q.candidates.slice(0,5).map(r=>`
        <tr>
          <td class="generic-debug-code">${o(r.candidate_id)}</td>
          <td>${o(R(r.source))}</td>
          <td>${o(w(r.model_score))}</td>
          <td>${o(r.generator_score??"n/a")}</td>
          <td class="generic-debug-code">${o(E(r.shopping_food_ids))}</td>
          <td>${r.selected?"Yes":"No"}</td>
          <td>${o(r.selection_reason_summary||"")}</td>
        </tr>
      `).join(""):"",xe=V!==void 0&&z!==void 0&&j!==void 0?`${V} heuristic + ${z} model -> ${j} fused`:B!==void 0?`${B} total candidates ranked`:"Not available",Ee=Le?`
      <div class="generic-list-item" style="margin-top: 1rem">
        <div class="generic-inline-group">
          <h3>Planner Debug / Model Participation</h3>
          <span class="generic-badge">Debug summary</span>
        </div>
        <div class="generic-debug-list">
          <div><strong>Selected candidate source:</strong> ${o(R($))}</div>
          <div><strong>Selected candidate sources:</strong> ${o($e.map(R).join(" + "))}</div>
          <div><strong>Candidate pool:</strong> ${o(xe)}</div>
          <div><strong>Candidates ranked:</strong> ${o(B??"Not available")}</div>
          <div><strong>Model candidates enabled:</strong> ${o(P?"Yes":"No")}</div>
          <div><strong>Candidate generator backend:</strong> ${o(ke||"Not used")}</div>
          <div><strong>Scorer backend:</strong> ${o(we)}</div>
          <div><strong>Selected candidate ID:</strong> ${o(Ce)}</div>
          <div><strong>Best heuristic candidate:</strong> ${o(c.best_heuristic_candidate_id||"Not available")} ${c.best_heuristic_candidate_score!==null&&c.best_heuristic_candidate_score!==void 0?`<span>(score ${o(w(c.best_heuristic_candidate_score))})</span>`:""}</div>
          <div><strong>Best model candidate:</strong> ${o(c.best_model_candidate_id||"Not available")} ${c.best_model_candidate_score!==null&&c.best_model_candidate_score!==void 0?`<span>(score ${o(w(c.best_model_candidate_score))})</span>`:""}</div>
          <div><strong>Model vs heuristic score gap:</strong> ${o(c.best_model_vs_best_heuristic_score_gap!==null&&c.best_model_vs_best_heuristic_score_gap!==void 0?w(c.best_model_vs_best_heuristic_score_gap):"Not available")}</div>
          <div><strong>Model candidates merged:</strong> ${o(c.model_candidates_merged_count!==null&&c.model_candidates_merged_count!==void 0?`${c.model_candidates_merged_count}`:"Not available")}</div>
          <div><strong>Materially different model candidates surviving fusion:</strong> ${o(c.materially_different_model_candidates_surviving_after_fusion!==null&&c.materially_different_model_candidates_surviving_after_fusion!==void 0?`${c.materially_different_model_candidates_surviving_after_fusion}`:"Not available")}</div>
          <div><strong>Average heuristic/model overlap:</strong> ${o(c.average_heuristic_model_overlap_jaccard!==null&&c.average_heuristic_model_overlap_jaccard!==void 0?w(c.average_heuristic_model_overlap_jaccard):"Not available")}</div>
          <div><strong>Best materially different model candidate:</strong> ${o(c.best_materially_different_model_candidate_id||"Not available")} ${c.best_materially_different_model_candidate_score!==null&&c.best_materially_different_model_candidate_score!==void 0?`<span>(score ${o(w(c.best_materially_different_model_candidate_score))})</span>`:""}</div>
          <div><strong>Winner vs best materially different model gap:</strong> ${o(c.best_materially_different_model_candidate_score_gap_to_selected!==null&&c.best_materially_different_model_candidate_score_gap_to_selected!==void 0?w(c.best_materially_different_model_candidate_score_gap_to_selected):"Not available")}</div>
          <div><strong>Why that model alternative lost:</strong> ${o(c.best_materially_different_model_candidate_loss_reason||"Not available")}</div>
          <div><strong>Similarity diagnosis:</strong> ${o(c.model_candidates_mostly_near_duplicates?"Model candidates were mostly near-duplicates.":P?"Model candidates introduced materially different baskets.":"Model path disabled.")}</div>
          <div><strong>Selection outcome:</strong> ${o(Se)}</div>
        </div>
        <div class="generic-debug-list" style="margin-top: 1rem">
          <div><strong>Selected vs heuristic baseline:</strong> ${o(x.difference_summary_vs_best_heuristic||c.selected_candidate_difference_summary||"Not available")}</div>
          <div><strong>Materially different from heuristic baseline:</strong> ${o(Y?Y.materially_different?"Yes":"No":"Not available")}</div>
          <div><strong>Selected candidate shopping_food_ids:</strong> <span class="generic-debug-code">${o(E(x.selected_candidate_shopping_food_ids||c.selected_candidate_shopping_food_ids||[]))}</span></div>
          <div><strong>Best heuristic candidate shopping_food_ids:</strong> <span class="generic-debug-code">${o(E(Ne))}</span></div>
          <div><strong>Best model candidate shopping_food_ids:</strong> <span class="generic-debug-code">${o(E(Ae))}</span></div>
        </div>
        ${W?`<details class="generic-advanced" style="margin-top: 1rem">
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
                  <tbody>${W}</tbody>
                </table>
              </details>`:""}
      </div>
    `:"",Re=0,Me=r=>`
        <div class="generic-list-item">
          <div class="generic-list-header">
            <div>
              <strong>${Re+=1}. ${o(r.name)}</strong>
              <div class="generic-muted">Suggested buy: ${o(r.quantity_display)}</div>
            </div>
            <span class="generic-badge">${o(Ue(r.role))}</span>
          </div>
          <div class="generic-muted" style="margin-top: 0.5rem"><strong>${o(r.reason_short||"")}</strong></div>
          <div class="generic-muted" style="margin-top: 0.25rem">${o(r.why_selected||r.reason)}</div>
          ${r.value_reason_short?`<div class="generic-muted" style="margin-top: 0.25rem"><strong>Value note:</strong> ${o(r.value_reason_short)}${r.price_efficiency_note?` <span>${o(r.price_efficiency_note)}</span>`:""}</div>`:""}
          <div class="generic-muted" style="margin-top: 0.25rem">${o(r.reason)}</div>
          ${r.substitution?`<div class="generic-muted" style="margin-top: 0.35rem"><strong>Swap option:</strong> ${o(r.substitution)}${ne(r)?` <span>${o(ne(r))}</span>`:""}</div>`:""}
          <div class="generic-list-meta">
            <span><strong>Protein:</strong> ${o(r.estimated_protein_g)} g</span>
            <span><strong>Calories:</strong> ${o(r.estimated_calories_kcal)} kcal</span>
          </div>
          ${r.estimated_item_cost!==null&&r.estimated_item_cost!==void 0?`<div class="generic-muted" style="margin-top: 0.35rem"><strong>Typical regional price:</strong> $${o(r.typical_unit_price??r.estimated_unit_price)} ${o(r.price_unit_display||"")}; typical item cost about <strong>$${o(r.typical_item_cost??r.estimated_item_cost)}</strong>${r.estimated_price_low!==null&&r.estimated_price_low!==void 0&&r.estimated_price_high!==null&&r.estimated_price_high!==void 0?` <span>(regional range $${o(r.estimated_price_low)}-$${o(r.estimated_price_high)})</span>`:""}.</div>`:""}
        </div>
      `,Te=ie.map(r=>{let y=n.shopping_list.filter(Be=>Be.role===r.role);return y.length?`
      <div class="generic-list-item" style="margin-top: 1rem">
        <div class="generic-inline-group">
          <h3>${o(r.title)}</h3>
          <span class="generic-badge">${y.length} ${y.length===1?"item":"items"}</span>
        </div>
        <div class="generic-list">
          ${y.map(Me).join("")}
        </div>
      </div>
    `:""}).join(""),Pe=(n.assumptions||[]).map(r=>`<li>${o(r)}</li>`).join(""),F=(n.pantry_notes||[]).map(r=>`<li>${o(r)}</li>`).join(""),D=(n.scaling_notes||[]).map(r=>`<li>${o(r)}</li>`).join(""),G=(n.warnings||[]).map(r=>`<li>${o(r)}</li>`).join(""),O=(n.split_notes||[]).map(r=>`<li>${o(r)}</li>`).join(""),U=(n.realism_notes||[]).map(r=>`<li>${o(r)}</li>`).join(""),J=[n.estimated_basket_cost_low!==void 0&&n.estimated_basket_cost_high!==void 0?`<p class="generic-muted"><strong>Typical basket range:</strong> about $${o(n.estimated_basket_cost_low)}-$${o(n.estimated_basket_cost_high)}</p>`:"",n.price_area_name?`<p class="generic-muted" style="margin-top: 0.5rem"><strong>Regional price area:</strong> ${o(n.price_area_name)} (${o(n.price_area_code||"")})</p>`:"",n.price_source_note?`<p class="generic-muted" style="margin-top: 0.5rem">${o(n.price_source_note)}</p>`:"",n.price_adjustment_note?`<p class="generic-muted" style="margin-top: 0.5rem">${o(n.price_adjustment_note)}</p>`:"",n.basket_cost_note?`<p class="generic-muted" style="margin-top: 0.5rem">${o(n.basket_cost_note)}</p>`:"",n.price_confidence_note?`<p class="generic-muted" style="margin-top: 0.5rem">${o(n.price_confidence_note)}</p>`:""].filter(Boolean).join(""),X=(n.store_fit_notes||[]).map(r=>`
        <div class="generic-list-item" style="margin-top: 0.75rem">
          <div class="generic-inline-group">
            <h3>${o(r.store_name||"Nearby store")}</h3>
            <span class="generic-badge">${o(r.fit_label||"Store fit")}</span>
          </div>
          <div class="generic-muted"><strong>${o(r.category||"store")}</strong>${r.distance_m!==void 0&&r.distance_m!==null?` \u2022 about ${o(Number(r.distance_m).toFixed(0))} m away`:""}</div>
          <div class="generic-muted" style="margin-top: 0.25rem">${o(r.note||"")}</div>
        </div>
      `).join(""),Z=I.map(r=>{let y=n[r.key];return y?.store_id?`
        <div class="generic-list-item" style="margin-top: 0.75rem">
          <div class="generic-inline-group">
            <h3>${o(r.title)}</h3>
            <span class="generic-badge">${o(y.store_name||"Nearby store")}</span>
          </div>
          <div class="generic-muted"><strong>${o(y.category||"store")}</strong>${y.distance_m!==void 0&&y.distance_m!==null?` \u2022 about ${o(Number(y.distance_m).toFixed(0))} m away`:""}</div>
          <div class="generic-muted" style="margin-top: 0.25rem">${o(y.note||"")}</div>
        </div>
      `:""}).join(""),ee=(n.meal_suggestions||[]).map(r=>`
        <div class="generic-list-item" style="margin-top: 0.75rem">
          <div class="generic-inline-group">
            <h3>${o(r.title||"Meal idea")}</h3>
            <span class="generic-badge">${o(String(r.meal_type||"idea").replaceAll("_"," "))}</span>
          </div>
          <div class="generic-muted"><strong>${o((r.items||[]).join(", "))}</strong></div>
          ${r.description?`<div class="generic-muted" style="margin-top: 0.25rem">${o(r.description)}</div>`:""}
        </div>
      `).join(""),je=ae.filter(r=>b?.[r.targetKey]!==void 0&&b?.[r.estimatedKey]!==void 0).map(r=>`
        <div class="generic-summary-metric">
          <div class="generic-muted">${o(r.label)}</div>
          <strong>${o(b[r.estimatedKey])} ${o(r.unit)}</strong>
          <div>Target: ${o(b[r.targetKey])} ${o(r.unit)}</div>
          <div class="generic-muted">Difference: ${o(Oe(b[r.estimatedKey],b[r.targetKey],r.unit))}</div>
        </div>
      `).join("");e.innerHTML=`
    ${A(l||"Recommendation ready.","success")}
    ${A(p?.message,p?.kind)}
    <div class="generic-list-item" style="margin-bottom: 1rem">
      <div class="generic-inline-group">
        <h3>Shopping List</h3>
        <div class="generic-badge-group">
          <span class="generic-badge ${o(Ke($))}">
            ${o(Ie($))}
          </span>
          <span class="generic-badge">Suggested shopping list for ${h} ${h===1?"day":"days"}</span>
        </div>
      </div>
      <p class="generic-muted">Daily nutrition goals stay the same. Quantities below are scaled for the selected shopping window in <strong>${o(T)}</strong> shopping mode.</p>
      <div class="generic-actions" style="margin-top: 0.75rem">
        <button type="button" data-export-action="copy-shopping">Copy shopping list</button>
        <button type="button" data-export-action="copy-plan">Copy full plan</button>
        <button type="button" data-export-action="download-plan">Download as text</button>
      </div>
      ${n.estimated_basket_cost!==void 0?`<p class="generic-muted" style="margin-top: 0.5rem"><strong>Estimated typical basket cost:</strong> about $${o(n.estimated_basket_cost)}.</p>`:""}
    </div>
    <div class="generic-list">
      ${Te||'<div class="generic-empty">Your pantry already covers the suggested basket for this plan. Review the notes below if you still want a small top-up shop.</div>'}
    </div>
    ${Ee}
    ${Z?`<div class="generic-list-item" style="margin-top: 1rem">
            <div class="generic-inline-group">
              <h3>Recommended store picks for this list</h3>
              <span class="generic-badge">${I.filter(r=>n[r.key]?.store_id).length} picks</span>
            </div>
            <p class="generic-muted">These are quick store-type recommendations based on the basket style and nearby store mix. They do not reflect exact inventory.</p>
            ${Z}
          </div>`:""}
    ${X?`<div class="generic-list-item" style="margin-top: 1rem">
            <div class="generic-inline-group">
              <h3>Best nearby store fits for this list</h3>
              <span class="generic-badge">${(n.store_fit_notes||[]).length} suggestions</span>
            </div>
            <p class="generic-muted">These are coarse store-fit suggestions based on the basket style, shopping mode, and nearby store type. They do not reflect exact inventory.</p>
            ${X}
          </div>`:""}
    ${ee?`<div class="generic-list-item" style="margin-top: 1rem">
            <div class="generic-inline-group">
              <h3>Example ways to use this list</h3>
              <span class="generic-badge">${(n.meal_suggestions||[]).length} ideas</span>
            </div>
            <p class="generic-muted">These are lightweight examples built from the same recommended items. They are not a full meal plan.</p>
            ${ee}
          </div>`:""}
    ${D||G||O||U||F?`<div class="generic-list-item" style="margin-top: 1rem">
            <div class="generic-inline-group">
              <h3>Shopping Notes</h3>
              <span class="generic-badge">${n.adjusted_by_split?"Scaling and realism guidance":"Scaling guidance"}</span>
            </div>
            ${D?`<p class="generic-muted"><strong>Scaling notes</strong></p><ul class="generic-assumptions">${D}</ul>`:""}
            ${O?`<p class="generic-muted" style="margin-top: 0.75rem"><strong>Split notes</strong></p><ul class="generic-assumptions">${O}</ul>`:""}
            ${U?`<p class="generic-muted" style="margin-top: 0.75rem"><strong>Realism notes</strong></p><ul class="generic-assumptions">${U}</ul>`:""}
            ${F?`<p class="generic-muted" style="margin-top: 0.75rem"><strong>Pantry adjustments</strong></p><ul class="generic-assumptions">${F}</ul>`:""}
            ${G?`<p class="generic-muted" style="margin-top: 0.75rem"><strong>Warnings</strong></p><ul class="generic-assumptions">${G}</ul>`:""}
          </div>`:""}
    <div class="generic-list-item" style="margin-top: 1rem">
      <div class="generic-inline-group">
        <h3>Nutrition Summary</h3>
        <span class="generic-badge">${h===1?"Daily total":`${h}-day total`}</span>
      </div>
      <div class="generic-summary-grid">
        ${je}
      </div>
    </div>
    <div class="generic-list-item" style="margin-top: 1rem">
      <div class="generic-inline-group">
        <h3>Approximate Guidance</h3>
        <span class="generic-badge">Demo-friendly estimate</span>
      </div>
      <p class="generic-muted">Use this list as a practical starting point, not as exact store inventory or guaranteed product availability.</p>
      <ul class="generic-assumptions">${Pe}</ul>
    </div>
    ${J?`<div class="generic-list-item" style="margin-top: 1rem">
            <div class="generic-inline-group">
              <h3>Pricing notes</h3>
              <span class="generic-badge">Typical regional estimate</span>
            </div>
            ${J}
          </div>`:""}
  `,e.querySelector('[data-export-action="copy-shopping"]')?.addEventListener("click",()=>{i.onCopyShoppingList?.()}),e.querySelector('[data-export-action="copy-plan"]')?.addEventListener("click",()=>{i.onCopyFullPlan?.()}),e.querySelector('[data-export-action="download-plan"]')?.addEventListener("click",()=>{i.onDownloadPlan?.()})}function C(e){return String(e??"").replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;").replaceAll('"',"&quot;").replaceAll("'","&#39;")}function M(e,t){return e?`<div class="generic-notice ${C(t||"info")}">${C(e)}</div>`:""}function de(e,t){let{stores:i,storeStatus:n,storeError:l,isLookingUpStores:d,hasLookedUpStores:s}=t;if(d){e.innerHTML=`
      ${M(n||"Looking up nearby supermarkets...","info")}
      <div class="generic-empty">Searching for nearby supermarkets. This usually takes a moment.</div>
    `;return}if(l){e.innerHTML=`
      ${M(l,"error")}
      <div class="generic-empty">Check the location fields and try the store lookup again.</div>
    `;return}if(!s){e.innerHTML=`
      <div class="generic-empty">
        Start with a location or preset, then use <strong>Find Nearby Supermarkets</strong> to load stores for the area.
      </div>
    `;return}if(!i.length){e.innerHTML=`
      ${M(n||"No nearby stores found.","info")}
      <div class="generic-empty">No supermarkets were found within the current search radius. Try increasing the radius or switching to a different location.</div>
    `;return}let m=i.map((p,b)=>`
        <div class="generic-list-item">
          <div class="generic-list-header">
            <div>
              <strong>${b+1}. ${C(p.name)}</strong>
              <div class="generic-muted">${C(p.address)}</div>
            </div>
            <span class="generic-badge">${Math.round(p.distance_m)} m</span>
          </div>
          <div class="generic-list-meta">
            <span><strong>Category:</strong> ${C(p.category)}</span>
            <span><strong>Coordinates:</strong> ${C(p.lat)}, ${C(p.lon)}</span>
          </div>
        </div>
      `).join("");e.innerHTML=`
    ${M(n||`Loaded ${i.length} nearby store${i.length===1?"":"s"}.`,"success")}
    <div class="generic-list">${m}</div>
  `}var Ve="https://nominatim.openstreetmap.org/search",ue=6,pe=4,ge="auto",ze=new Set(["auto","logistic_regression","random_forest","hist_gradient_boosting"]),me=[{id:"muscle_gain",label:"Muscle Gain",values:{locationQuery:"Mountain View, CA",lat:"",lon:"",radius_m:"8000",store_limit:"5",days:"1",shopping_mode:"balanced",protein:"170",calories:"2800",carbohydrate:"330",fat:"85",fiber:"35",calcium:"",iron:"",vitamin_c:"",vegetarian:!1,dairy_free:!1,vegan:!1,low_prep:!1,budget_friendly:!1,meal_style:"any"},notice:'Loaded the muscle gain preset for "Mountain View, CA".'},{id:"fat_loss",label:"Fat Loss",values:{locationQuery:"Mountain View, CA",lat:"",lon:"",radius_m:"8000",store_limit:"5",days:"1",shopping_mode:"balanced",protein:"150",calories:"1800",carbohydrate:"160",fat:"55",fiber:"30",calcium:"",iron:"",vitamin_c:"",vegetarian:!1,dairy_free:!1,vegan:!1,low_prep:!1,budget_friendly:!1,meal_style:"any"},notice:'Loaded the fat loss preset for "Mountain View, CA".'},{id:"maintenance",label:"Maintenance",values:{locationQuery:"Mountain View, CA",lat:"",lon:"",radius_m:"8000",store_limit:"5",days:"1",shopping_mode:"balanced",protein:"130",calories:"2200",carbohydrate:"240",fat:"70",fiber:"30",calcium:"",iron:"",vitamin_c:"",vegetarian:!1,dairy_free:!1,vegan:!1,low_prep:!1,budget_friendly:!1,meal_style:"any"},notice:'Loaded the maintenance preset for "Mountain View, CA".'},{id:"high_protein_vegetarian",label:"High-Protein Vegetarian",values:{locationQuery:"Mountain View, CA",lat:"",lon:"",radius_m:"8000",store_limit:"5",days:"1",shopping_mode:"balanced",protein:"140",calories:"2100",carbohydrate:"220",fat:"70",fiber:"32",calcium:"",iron:"18",vitamin_c:"",vegetarian:!0,dairy_free:!1,vegan:!1,low_prep:!1,budget_friendly:!1,meal_style:"any"},notice:'Loaded the high-protein vegetarian preset for "Mountain View, CA".'},{id:"budget_friendly_healthy",label:"Budget-Friendly Healthy",values:{locationQuery:"Mountain View, CA",lat:"",lon:"",radius_m:"8000",store_limit:"5",days:"1",shopping_mode:"balanced",protein:"120",calories:"2100",carbohydrate:"230",fat:"65",fiber:"35",calcium:"",iron:"",vitamin_c:"",vegetarian:!1,dairy_free:!1,vegan:!1,low_prep:!1,budget_friendly:!0,meal_style:"any"},notice:'Loaded the budget-friendly healthy preset for "Mountain View, CA".'}];function Ye(){return typeof window>"u"?{}:window.GENERIC_APP_CONFIG||{}}function We(){let e=!!Ye().isProduction;return{enable_model_candidates:!e,model_candidate_count:String(pe),candidate_generator_backend:ge,debug_candidate_generation:!e,debug_scorer:!e,candidate_count:String(ue)}}var a={locationQuery:"Mountain View, CA",lat:"",lon:"",radius_m:"8000",store_limit:"5",days:"1",shopping_mode:"balanced",protein:"130",calories:"2200",carbohydrate:"240",fat:"70",fiber:"30",calcium:"",iron:"",vitamin_c:"",vegetarian:!1,dairy_free:!1,vegan:!1,low_prep:!1,budget_friendly:!1,meal_style:"any",...We(),pantry_items:[],stores:[],storesLookupContext:null,recommendation:null,errors:{},formNotice:null,storeStatus:"",storeError:"",recommendationStatus:"",recommendationError:"",exportNotice:null,isLookingUpStores:!1,isGeneratingRecommendations:!1,isLocating:!1,isResolvingAddress:!1,hasLookedUpStores:!1,hasRequestedRecommendation:!1,presets:me};function _(e){if(e==null||String(e).trim()==="")return null;let t=Number(e);return Number.isFinite(t)?t:null}function q(e){if(e==="true")return!0;if(e==="false")return!1}function ce(e){if(e==null||String(e).trim()==="")return;let t=Number.parseInt(String(e),10);if(!(!Number.isFinite(t)||t<=0))return t}function Je(e,t){if(e==null||String(e).trim()==="")return;let i=String(e).trim().toLowerCase();return t.has(i)?i:void 0}function _e(){return typeof window>"u"||!window.location||typeof window.location.search!="string"?"":window.location.search}function fe(e=_e()){let t=new URLSearchParams(e||""),i={},n=q(t.get("enable_model_candidates"));n!==void 0&&(i.enable_model_candidates=n);let l=ce(t.get("model_candidate_count"));l!==void 0&&(i.model_candidate_count=l);let d=Je(t.get("candidate_generator_backend"),ze);d!==void 0&&(i.candidate_generator_backend=d);let s=q(t.get("debug_candidate_generation"));s!==void 0&&(i.debug_candidate_generation=s);let m=q(t.get("debug_scorer"));m!==void 0&&(i.debug_scorer=m);let p=ce(t.get("candidate_count"));p!==void 0&&(i.candidate_count=p);let b=String(t.get("scorer_model_path")||"").trim();b&&(i.scorer_model_path=b);let h=String(t.get("candidate_generator_model_path")||"").trim();return h&&(i.candidate_generator_model_path=h),i}Object.assign(a,fe());function be(e){let t=_(e.lat),i=_(e.lon);return t!==null&&i!==null&&t>=-90&&t<=90&&i>=-180&&i<=180}function H(e){let t=_(e.lat),i=_(e.lon),n=_(e.radius_m);return t===null||i===null||n===null?null:{lat:Number(t.toFixed(6)),lon:Number(i.toFixed(6)),radius_m:Math.round(n)}}function Xe(e,t){return!e||!t?!1:e.lat===t.lat&&e.lon===t.lon&&e.radius_m===t.radius_m}function Ze(e,t=_e()){let i={location:{lat:Number(e.lat),lon:Number(e.lon)},targets:{protein:Number(e.protein),energy_fibre_kcal:Number(e.calories)},preferences:{vegetarian:e.vegetarian,dairy_free:e.dairy_free,vegan:e.vegan,low_prep:e.low_prep,budget_friendly:e.budget_friendly,meal_style:e.meal_style||"any"},pantry_items:Array.isArray(e.pantry_items)?e.pantry_items:[],store_limit:Number(e.store_limit),days:Number(e.days||1),shopping_mode:e.shopping_mode||"balanced",enable_model_candidates:!!e.enable_model_candidates,model_candidate_count:Number(e.model_candidate_count||pe),candidate_generator_backend:e.candidate_generator_backend||ge,debug_candidate_generation:!!e.debug_candidate_generation,debug_scorer:!!e.debug_scorer,candidate_count:Number(e.candidate_count||ue)},n=H(e);e.hasLookedUpStores&&Array.isArray(e.stores)&&e.stores.length&&e.stores.length>=Number(e.store_limit)&&Xe(e.storesLookupContext,n)&&(i.stores=e.stores.slice(0,Number(e.store_limit)));for(let[l,d]of Object.entries({carbohydrate:_(e.carbohydrate),fat:_(e.fat),fiber:_(e.fiber),calcium:_(e.calcium),iron:_(e.iron),vitamin_c:_(e.vitamin_c)}))d!==null&&(i.targets[l]=d);return Object.assign(i,fe(t)),i}function et(e,t="recommend"){let i={},n=String(e.locationQuery||"").trim(),l=_(e.lat),d=_(e.lon),s=_(e.protein),m=_(e.calories),p=[["carbohydrate","carbohydrate"],["fat","fat"],["fiber","fiber"],["calcium","calcium"],["iron","iron"],["vitamin_c","vitamin C"]],b=be(e);if(!n&&!b&&(i.locationQuery="Enter a city or address, or provide coordinates in Advanced location settings."),n||((l===null||l<-90||l>90)&&(i.lat="Enter a latitude between -90 and 90."),(d===null||d<-180||d>180)&&(i.lon="Enter a longitude between -180 and 180.")),t==="recommend"){(s===null||s<=0)&&(i.protein="Enter a protein target greater than 0."),(m===null||m<=0)&&(i.calories="Enter a calorie target greater than 0.");for(let[h,T]of p){let $=_(e[h]);$!==null&&$<=0&&(i[h]=`Enter a ${T} target greater than 0, or leave it blank.`)}}return i}async function tt(e,t=fetch){let i=String(e||"").trim();if(!i)throw new Error("Enter a city or address first.");let n=new URLSearchParams({q:i,format:"jsonv2",limit:"1"}),l=await t(`${Ve}?${n.toString()}`,{headers:{Accept:"application/json"}});if(!l.ok)throw new Error("Location search failed. Please try again.");let d=await l.json();if(!Array.isArray(d)||d.length===0)throw new Error("Could not find that location. Please try a different city or address.");let s=d[0];return{lat:Number(s.lat).toFixed(6),lon:Number(s.lon).toFixed(6),displayName:s.display_name||i}}function v(e,t="info"){a.formNotice=e?{message:e,kind:t}:null}function S(e,t="info"){a.exportNotice=e?{message:e,kind:t}:null}function nt(e){Object.assign(a,e);for(let t of Object.keys(e))a.errors[t]&&delete a.errors[t]}function ye(e){let t=et(a,e);return a.errors=t,Object.keys(t).length?(v("Fix the highlighted fields before continuing.","error"),f(),!1):(a.formNotice?.kind==="error"&&v(null),!0)}function it(){a.stores=[],a.storesLookupContext=null,a.recommendation=null,a.storeStatus="",a.storeError="",a.recommendationStatus="",a.recommendationError="",a.exportNotice=null,a.hasLookedUpStores=!1,a.hasRequestedRecommendation=!1}async function he(){let e=String(a.locationQuery||"").trim();if(!e)return be(a);a.isResolvingAddress=!0,v(`Finding coordinates for "${e}"...`,"info"),f();try{let t=await tt(e);return a.lat=t.lat,a.lon=t.lon,delete a.errors.locationQuery,delete a.errors.lat,delete a.errors.lon,v(`Using coordinates for "${e}". Advanced settings were updated automatically.`,"success"),!0}catch(t){return a.errors.locationQuery=t.message||"Could not find that location. Please try a different city or address.",v(a.errors.locationQuery,"error"),f(),!1}finally{a.isResolvingAddress=!1}}async function at(){if(!ye("stores")||!await he())return;a.hasLookedUpStores=!0,a.storeError="",a.storeStatus="Looking up nearby supermarkets...",a.isLookingUpStores=!0,f();let t=new URLSearchParams({lat:a.lat,lon:a.lon,radius_m:a.radius_m,limit:a.store_limit});try{let i=await fetch(`/api/stores/nearby?${t.toString()}`),n=await i.json();if(!i.ok)throw new Error(n.error||"Store lookup failed.");a.stores=n.stores||[],a.storesLookupContext=H(a),a.storeStatus=a.stores.length?`Loaded ${a.stores.length} nearby supermarket${a.stores.length===1?"":"s"}.`:"No nearby supermarkets found for this location.",a.recommendation&&!a.recommendation.stores?.length&&(a.recommendation.stores=a.stores)}catch(i){a.stores=[],a.storeError=i.message||"Store lookup failed.",a.storeStatus=""}finally{a.isLookingUpStores=!1}f()}async function ot(){if(!ye("recommend")||!await he())return;a.hasRequestedRecommendation=!0,a.recommendation=null,a.recommendationError="",a.recommendationStatus="Generating recommendations...",a.exportNotice=null,a.isGeneratingRecommendations=!0,f();let t=H(a),i=Ze(a);try{let n=await fetch("/api/recommendations/generic",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(i)}),l=await n.json();if(!n.ok)throw new Error(l.error||"Recommendation request failed.");a.recommendation=l,a.stores=l.stores||[],a.storesLookupContext=a.stores.length?t:null,a.hasLookedUpStores=!0,a.storeError="",a.storeStatus=a.stores.length?`Loaded ${a.stores.length} nearby supermarket${a.stores.length===1?"":"s"}.`:"No nearby supermarkets found for this location.",a.recommendationStatus=l.shopping_list?.length?"Shopping list ready.":"No shopping list was generated for the current inputs."}catch(n){a.recommendation=null,a.recommendationError=n.message||"Recommendation request failed.",a.recommendationStatus=""}finally{a.isGeneratingRecommendations=!1}f()}function rt(){if(!navigator.geolocation){v("Browser geolocation is not available here. Enter coordinates in Advanced location settings.","error"),f();return}a.isLocating=!0,v("Requesting your current location...","info"),f(),navigator.geolocation.getCurrentPosition(e=>{a.isLocating=!1,a.locationQuery="",a.lat=e.coords.latitude.toFixed(6),a.lon=e.coords.longitude.toFixed(6),delete a.errors.locationQuery,delete a.errors.lat,delete a.errors.lon,v("Location loaded from your browser. Advanced settings were updated automatically.","success"),f()},e=>{a.isLocating=!1,v({1:"Location access was denied. Enter a city, address, or coordinates manually.",2:"Your location could not be determined. Enter a city, address, or coordinates manually.",3:"Location lookup timed out. Enter a city, address, or coordinates manually."}[e.code]||"Location lookup failed. Enter a city, address, or coordinates manually.","error"),f()},{enableHighAccuracy:!1,timeout:1e4,maximumAge:3e5})}function st(e){let t=me.find(i=>i.id===e);t&&(Object.assign(a,t.values),a.pantry_items=Array.isArray(t.values?.pantry_items)?[...t.values.pantry_items]:[],a.errors={},it(),v(t.notice,"success"),f())}async function ve(e){if(!e)throw new Error("There is no recommendation to export yet.");if(navigator.clipboard?.writeText){await navigator.clipboard.writeText(e);return}let t=document.createElement("textarea");t.value=e,t.setAttribute("readonly","readonly"),t.style.position="fixed",t.style.opacity="0",document.body.appendChild(t),t.select();let i=document.execCommand("copy");if(document.body.removeChild(t),!i)throw new Error("Copy is not available in this browser.")}function lt(e,t){if(!t)throw new Error("There is no recommendation to export yet.");let i=new Blob([t],{type:"text/plain;charset=utf-8"}),n=URL.createObjectURL(i),l=document.createElement("a");l.href=n,l.download=e,document.body.appendChild(l),l.click(),document.body.removeChild(l),URL.revokeObjectURL(n)}async function dt(){try{await ve(se(a.recommendation)),S("Copied the grouped shopping list.","success")}catch(e){S(e.message||"Could not copy the shopping list.","error")}f()}async function ct(){try{await ve(K(a.recommendation)),S("Copied the full grocery plan.","success")}catch(e){S(e.message||"Could not copy the full plan.","error")}f()}function ut(){try{lt("generic-grocery-plan.txt",K(a.recommendation)),S("Downloaded the grocery plan as text.","success")}catch(e){S(e.message||"Could not download the grocery plan.","error")}f()}function f(){te(document.getElementById("generic-form"),a,{onChange:nt,onLookupStores:at,onRecommend:ot,onUseMyLocation:rt,onApplyPreset:st}),de(document.getElementById("generic-stores"),a),le(document.getElementById("generic-results"),a,{onCopyShoppingList:dt,onCopyFullPlan:ct,onDownloadPlan:ut})}typeof document<"u"&&f();export{Ze as buildRecommendationPayload,tt as geocodeAddress,fe as getScorerQueryOverrides,q as parseBooleanParam,ce as parsePositiveIntParam,et as validateFormState};
