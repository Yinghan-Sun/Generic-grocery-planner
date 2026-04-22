function Q(e,t){let i=e.querySelector(`[name="${t}"]`);return i?i.type==="hidden"?String(i.value||"").trim().toLowerCase()==="true":i.checked||!1:!1}function Ke(e,t){return[...e.querySelectorAll(`[name="${t}"]:checked`)].map(i=>i.value)}var qe=[{id:"eggs",label:"Eggs"},{id:"milk",label:"Milk"},{id:"greek_yogurt",label:"Greek yogurt"},{id:"oats",label:"Oats"},{id:"rice",label:"Rice"},{id:"beans",label:"Beans"},{id:"lentils",label:"Lentils"},{id:"bananas",label:"Bananas"},{id:"broccoli",label:"Broccoli"},{id:"potatoes",label:"Potatoes"},{id:"olive_oil",label:"Olive oil"},{id:"peanut_butter",label:"Peanut butter"},{id:"tofu",label:"Tofu"},{id:"chicken_breast",label:"Chicken breast"}];function p(e){return String(e??"").replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;").replaceAll('"',"&quot;").replaceAll("'","&#39;")}function f(e,t){return e.errors?.[t]||""}function Ie(e){return e.formNotice?.message?`
    <div class="generic-notice ${p(e.formNotice.kind||"info")}" role="status">
      ${p(e.formNotice.message)}
    </div>
  `:""}function oe(e,t,i){let n=(t.presets||[]).map(g=>`
        <button type="button" class="generic-preset-button" data-preset-id="${p(g.id)}">
          ${p(g.label)}
        </button>
      `).join(""),s=t.isLocating||t.isResolvingAddress||t.isLookingUpStores||t.isGeneratingRecommendations,d=!!t.developerMode,u=qe.map(g=>`
        <label>
          <input
            name="pantry_items"
            type="checkbox"
            value="${p(g.id)}"
            ${(t.pantry_items||[]).includes(g.id)?"checked":""}
          />
          ${p(g.label)}
        </label>
      `).join(""),_=d?`
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
              value="${p(t.model_candidate_count)}"
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
              value="${p(t.candidate_count)}"
            />
            <span class="generic-help">How many fused candidates the trained scorer reranks before choosing the final basket.</span>
          </label>
          <label>
            Candidate generator backend
            <select name="candidate_generator_backend">
              <option value="auto" ${t.candidate_generator_backend==="auto"?"selected":""}>Auto</option>
              <option value="logistic_regression" ${t.candidate_generator_backend==="logistic_regression"?"selected":""}>Logistic regression</option>
              <option value="random_forest" ${t.candidate_generator_backend==="random_forest"?"selected":""}>Random forest</option>
              <option value="hist_gradient_boosting" ${t.candidate_generator_backend==="hist_gradient_boosting"?"selected":""}>HistGradientBoosting</option>
            </select>
            <span class="generic-help">Choose a backend only when comparing internal candidate-generator artifacts.</span>
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
    `:`
      <div class="generic-list-item" style="margin-top: 1rem">
        <div class="generic-inline-group">
          <h3>How recommendations run</h3>
          <span class="generic-badge">Automatic hybrid pipeline</span>
        </div>
        <p class="generic-help">Click Recommend once and the app automatically runs heuristic candidate generation, learned candidate generation, candidate fusion, trained scorer reranking, and nearby store-fit ranking.</p>
        <input name="enable_model_candidates" type="hidden" value="true" />
        <input name="model_candidate_count" type="hidden" value="${p(t.model_candidate_count)}" />
        <input name="candidate_generator_backend" type="hidden" value="${p(t.candidate_generator_backend)}" />
        <input name="debug_candidate_generation" type="hidden" value="false" />
        <input name="debug_scorer" type="hidden" value="false" />
        <input name="candidate_count" type="hidden" value="${p(t.candidate_count)}" />
      </div>
    `;e.innerHTML=`
    <form id="generic-input-form" novalidate>
      ${Ie(t)}
      <div>
        <h3>Goal Presets</h3>
        <p class="generic-help">Start from a common goal or dietary preset, then fine-tune the everyday planning details if needed.</p>
        <div class="generic-presets">${n}</div>
      </div>

      <div class="generic-form-grid">
        <label class="generic-span-full">
          City or address
          <input
            name="locationQuery"
            type="text"
            placeholder="Mountain View, CA"
            value="${p(t.locationQuery)}"
            aria-invalid="${f(t,"locationQuery")?"true":"false"}"
          />
          <span class="generic-field-error">${p(f(t,"locationQuery"))}</span>
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
            value="${p(t.calories)}"
            aria-invalid="${f(t,"calories")?"true":"false"}"
            required
          />
          <span class="generic-field-error">${p(f(t,"calories"))}</span>
        </label>
        <label>
          Protein (g)
          <input
            name="protein"
            type="number"
            min="1"
            step="1"
            value="${p(t.protein)}"
            aria-invalid="${f(t,"protein")?"true":"false"}"
            required
          />
          <span class="generic-field-error">${p(f(t,"protein"))}</span>
        </label>
        <label>
          Carbs (g)
          <input
            name="carbohydrate"
            type="number"
            min="1"
            step="1"
            value="${p(t.carbohydrate)}"
            aria-invalid="${f(t,"carbohydrate")?"true":"false"}"
          />
          <span class="generic-field-error">${p(f(t,"carbohydrate"))}</span>
        </label>
        <label>
          Fat (g)
          <input
            name="fat"
            type="number"
            min="1"
            step="1"
            value="${p(t.fat)}"
            aria-invalid="${f(t,"fat")?"true":"false"}"
          />
          <span class="generic-field-error">${p(f(t,"fat"))}</span>
        </label>
        <label>
          Fiber (g)
          <input
            name="fiber"
            type="number"
            min="1"
            step="1"
            value="${p(t.fiber)}"
            aria-invalid="${f(t,"fiber")?"true":"false"}"
          />
          <span class="generic-field-error">${p(f(t,"fiber"))}</span>
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
          <p class="generic-help">Dietary goals like Vegan, Dairy-free, and Budget-Friendly Healthy now live in Goal Presets. Recommendations stay generic and do not depend on exact store inventory or branded products.</p>
        </div>
      </div>

      <div class="generic-form-grid">
        <div class="generic-span-full">
          <h3>Already have</h3>
          <p class="generic-help">Mark common items already in your pantry or fridge. The shopping list will reduce or omit them where the basket still works.</p>
          <div class="generic-checkboxes">
            ${u}
          </div>
        </div>
      </div>

      ${_}

      <div class="generic-actions">
        <button type="button" id="use-location-button" ${s?"disabled":""}>
          ${t.isLocating?"Locating...":"Use My Location"}
        </button>
        <button type="button" id="lookup-stores-button" ${s?"disabled":""}>
          ${t.isResolvingAddress||t.isLookingUpStores?"Looking Up...":"Find Nearby Supermarkets"}
        </button>
        <button type="submit" ${s?"disabled":""}>
          ${t.isResolvingAddress||t.isGeneratingRecommendations?"Generating...":"Recommend"}
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
              value="${p(t.lat)}"
              aria-invalid="${f(t,"lat")?"true":"false"}"
            />
            <span class="generic-field-error">${p(f(t,"lat"))}</span>
          </label>
          <label>
            Longitude
            <input
              name="lon"
              type="number"
              step="any"
              value="${p(t.lon)}"
              aria-invalid="${f(t,"lon")?"true":"false"}"
            />
            <span class="generic-field-error">${p(f(t,"lon"))}</span>
          </label>
          <label>
            Search radius (m)
            <input name="radius_m" type="number" min="1" step="100" value="${p(t.radius_m)}" required />
            <span class="generic-help">How far to search for supermarkets around the selected point.</span>
          </label>
          <label>
            Nearby stores to show
            <input name="store_limit" type="number" min="1" max="25" step="1" value="${p(t.store_limit)}" required />
            <span class="generic-help">The list is always sorted by distance.</span>
          </label>
        </div>
      </details>
    </form>
  `;let l=e.querySelector("#generic-input-form"),m=()=>i.onChange({locationQuery:l.locationQuery.value,lat:l.lat.value,lon:l.lon.value,radius_m:l.radius_m.value,store_limit:l.store_limit.value,days:l.days.value,shopping_mode:l.shopping_mode.value,protein:l.protein.value,calories:l.calories.value,carbohydrate:l.carbohydrate.value,fat:l.fat.value,fiber:l.fiber.value,meal_style:l.meal_style.value,enable_model_candidates:Q(l,"enable_model_candidates"),model_candidate_count:l.model_candidate_count.value,candidate_generator_backend:l.candidate_generator_backend.value,debug_candidate_generation:Q(l,"debug_candidate_generation"),debug_scorer:Q(l,"debug_scorer"),candidate_count:l.candidate_count.value,pantry_items:Ke(l,"pantry_items")});l.addEventListener("change",m),l.addEventListener("input",m),l.addEventListener("submit",g=>{g.preventDefault(),m(),i.onRecommend()}),e.querySelector("#lookup-stores-button").addEventListener("click",()=>{m(),i.onLookupStores()}),e.querySelector("#use-location-button").addEventListener("click",()=>{m(),i.onUseMyLocation()}),e.querySelectorAll("[data-preset-id]").forEach(g=>{g.addEventListener("click",()=>{i.onApplyPreset(g.dataset.presetId)})})}function o(e){return String(e??"").replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;").replaceAll('"',"&quot;").replaceAll("'","&#39;")}function E(e,t){return e?`<div class="generic-notice ${o(t||"info")}">${o(e)}</div>`:""}function He(e,t,i){let n=Math.round((e-t)*10)/10;return`${n>0?"+":""}${n} ${i}`}function Qe(e){return{protein_anchor:"Protein anchor",carb_base:"Carb base",produce:"Produce",calorie_booster:"Calorie booster"}[e]||"Recommended item"}function L(e){let t=String(e||"heuristic").trim().toLowerCase();return t==="model"||t==="hybrid"||t==="repaired_model"?t:"heuristic"}function T(e){return{heuristic:"Heuristic",model:"Model",hybrid:"Hybrid",repaired_model:"Repaired model"}[L(e)]||"Heuristic"}function Ve(e){return`${T(e)} result`}function ze(e){return`generic-badge-source-${L(e)}`}function Ye(e,t){let i=Array.isArray(e)?e:[],n=[...new Set(i.map(s=>L(s)).filter(Boolean))];return n.length?n:[L(t)]}function We(e,t){let i=L(t);return e?i==="heuristic"?"Model path was enabled, but the highest-ranked basket still came from the heuristic pool.":i==="model"?"A model-generated candidate won the final ranking.":i==="repaired_model"?"A model-generated basket needed repair and still won the final ranking.":"A fused hybrid candidate won the final ranking.":"Model path disabled; the heuristic-only baseline produced this result."}function R(e){let t=Array.isArray(e)?e.filter(Boolean):[];return t.length?t.join(", "):"Not available"}function k(e,t=3){if(e==null||e==="")return"Not available";let i=Number(e);return Number.isFinite(i)?i.toFixed(t):String(e)}var se=[{role:"protein_anchor",title:"Protein picks"},{role:"carb_base",title:"Carb base"},{role:"produce",title:"Produce"},{role:"calorie_booster",title:"Extras / boosters"}],V=[{key:"one_stop_pick",title:"One-stop pick"},{key:"budget_pick",title:"Budget pick"},{key:"produce_pick",title:"Produce pick"},{key:"bulk_pick",title:"Bulk pick"}],de=[{label:"Protein",targetKey:"protein_target_g",estimatedKey:"protein_estimated_g",unit:"g"},{label:"Calories",targetKey:"calorie_target_kcal",estimatedKey:"calorie_estimated_kcal",unit:"kcal"},{label:"Carbs",targetKey:"carbohydrate_target_g",estimatedKey:"carbohydrate_estimated_g",unit:"g"},{label:"Fat",targetKey:"fat_target_g",estimatedKey:"fat_estimated_g",unit:"g"},{label:"Fiber",targetKey:"fiber_target_g",estimatedKey:"fiber_estimated_g",unit:"g"},{label:"Calcium",targetKey:"calcium_target_mg",estimatedKey:"calcium_estimated_mg",unit:"mg"},{label:"Iron",targetKey:"iron_target_mg",estimatedKey:"iron_estimated_mg",unit:"mg"},{label:"Vitamin C",targetKey:"vitamin_c_target_mg",estimatedKey:"vitamin_c_estimated_mg",unit:"mg"}];function Je(e,t){return!e||e[t.targetKey]===void 0||e[t.estimatedKey]===void 0?null:`${t.label}: ${e[t.estimatedKey]} ${t.unit} (target ${e[t.targetKey]} ${t.unit})`}function re(e){let t=String(e?.substitution_reason||"").trim(),i=String(e?.substitution||"").trim();return t?i&&t.toLowerCase().startsWith(i.toLowerCase())?t.slice(i.length).trim():t:""}function le(e,t=!0){return se.map(i=>{let n=(e.shopping_list||[]).filter(d=>d.role===i.role);if(!n.length)return"";let s=n.map(d=>{let u=[`- ${d.name}: ${d.quantity_display}`];if(t&&d.reason_short&&u.push(`  ${d.reason_short}`),t&&d.typical_item_cost!==null&&d.typical_item_cost!==void 0){let _=d.estimated_price_low!==null&&d.estimated_price_low!==void 0&&d.estimated_price_high!==null&&d.estimated_price_high!==void 0?` (range $${d.estimated_price_low}-$${d.estimated_price_high})`:"";u.push(`  Typical cost: $${d.typical_item_cost}${_}`)}return u.join(`
`)});return`${i.title}
${s.join(`
`)}`}).filter(Boolean).join(`

`)}function ce(e){return V.map(t=>{let i=e?.[t.key];if(!i?.store_id)return null;let n=i.distance_m!==void 0&&i.distance_m!==null?`, about ${Math.round(Number(i.distance_m))} m away`:"";return`- ${t.title}: ${i.store_name} (${i.category||"store"}${n})${i.note?` - ${i.note}`:""}`}).filter(Boolean)}function ue(e){if(!e?.shopping_list?.length)return"";let t=Number(e.days||1),i=String(e.shopping_mode||"balanced"),n=["Generic Grocery Plan",`Shopping window: ${t} ${t===1?"day":"days"}`,`Shopping mode: ${i}`,"",le(e,!1)];e.estimated_basket_cost!==void 0&&(n.push("",`Estimated typical basket cost: $${e.estimated_basket_cost}`),e.estimated_basket_cost_low!==void 0&&e.estimated_basket_cost_high!==void 0&&n.push(`Typical basket range: $${e.estimated_basket_cost_low}-$${e.estimated_basket_cost_high}`),e.price_adjustment_note&&n.push(e.price_adjustment_note),e.price_coverage_note&&n.push(e.price_coverage_note));let s=ce(e);return s.length&&n.push("","Recommended store picks",...s),n.filter(Boolean).join(`
`)}function z(e){if(!e?.shopping_list?.length)return"";let t=Number(e.days||1),i=String(e.shopping_mode||"balanced"),n=e.nutrition_summary||{},s=de.map(_=>Je(n,_)).filter(Boolean),d=ce(e),u=["Generic Grocery Plan",`Shopping window: ${t} ${t===1?"day":"days"}`,`Shopping mode: ${i}`];return s.length&&u.push("","Key nutrition targets",...s),e.estimated_basket_cost!==void 0&&(u.push("",`Estimated typical basket cost: $${e.estimated_basket_cost}`),e.estimated_basket_cost_low!==void 0&&e.estimated_basket_cost_high!==void 0&&u.push(`Typical basket range: $${e.estimated_basket_cost_low}-$${e.estimated_basket_cost_high}`),e.price_adjustment_note&&u.push(e.price_adjustment_note),e.price_coverage_note&&u.push(e.price_coverage_note),e.basket_cost_note&&u.push(e.basket_cost_note),e.price_confidence_note&&u.push(e.price_confidence_note)),d.length&&u.push("","Recommended store picks",...d),u.push("","Shopping list",le(e,!0)),Array.isArray(e.assumptions)&&e.assumptions.length&&u.push("","Approximate guidance",...e.assumptions.map(_=>`- ${_}`)),u.filter(Boolean).join(`
`)}function pe(e,t,i={}){let{recommendation:n,recommendationStatus:s,recommendationError:d,isGeneratingRecommendations:u,hasRequestedRecommendation:_,exportNotice:l}=t;if(u){e.innerHTML=`
      ${E(s||"Generating recommendations...","info")}
      <div class="generic-empty">Building a generic shopping list from the nutrition targets and food preferences.</div>
    `;return}if(d){e.innerHTML=`
      ${E(d,"error")}
      <div class="generic-empty">The app could not build a shopping list for the current inputs. Adjust the targets or preferences and try again.</div>
    `;return}if(!_){e.innerHTML=`
      <div class="generic-empty">
        Build a shopping list to see recommended food categories, rough quantities, and a simple nutrition summary.
      </div>
    `;return}if(!n){e.innerHTML=`
      ${E(s||"No recommendations available.","info")}
      <div class="generic-empty">No shopping list could be generated from the current targets and preferences. Try lowering the targets or relaxing the filters.</div>
    `;return}let m=n.nutrition_summary,g=Number(n.days||t.days||1),B=String(n.shopping_mode||t.shopping_mode||"balanced"),x=!!t.developerMode,N=L(n.selected_candidate_source),Le=Ye(n.selected_candidate_sources,N),$=n.hybrid_planner_execution||{},A=n.candidate_generation_debug||{},X=n.scoring_debug||{},c=n.candidate_comparison_debug||{},j=A.model_candidates_enabled??$.learned_candidate_generation_ran??!!t.enable_model_candidates,D=A.heuristic_candidate_count??$.heuristic_candidate_count,F=A.model_candidate_count??$.learned_candidate_count,G=A.fused_candidate_count??$.fused_candidate_count??n.candidate_count_considered,Se=A.candidate_generator_backend||$.candidate_generator_backend||t.candidate_generator_backend||"auto",Ne=n.scorer_backend||"unknown",Ae=n.selected_candidate_id||"unknown",U=n.candidate_count_considered??$.candidates_ranked_count??G,Ee=x&&!!(n.candidate_generation_debug||n.scoring_debug||n.candidate_comparison_debug),xe=c.diagnosis_text||We(j,N),Z=c.selected_vs_best_heuristic||null,M=c.selected_candidate_contrast||{},Me=M.best_heuristic_candidate_shopping_food_ids||c.best_heuristic_candidate_shopping_food_ids||[],Re=M.best_model_candidate_shopping_food_ids||c.best_model_candidate_shopping_food_ids||[],ee=Array.isArray(X.candidates)?X.candidates.slice(0,5).map(r=>`
        <tr>
          <td class="generic-debug-code">${o(r.candidate_id)}</td>
          <td>${o(T(r.source))}</td>
          <td>${o(k(r.model_score))}</td>
          <td>${o(r.generator_score??"n/a")}</td>
          <td class="generic-debug-code">${o(R(r.shopping_food_ids))}</td>
          <td>${r.selected?"Yes":"No"}</td>
          <td>${o(r.selection_reason_summary||"")}</td>
        </tr>
      `).join(""):"",Te=D!==void 0&&F!==void 0&&G!==void 0?`${D} heuristic + ${F} model -> ${G} fused`:U!==void 0?`${U} total candidates ranked`:"Not available",Pe=$.pipeline_mode==="full_hybrid"?`${D??"?"} heuristic candidates + ${F??"?"} learned candidates were fused, reranked by the trained scorer, and matched against nearby store fits automatically.`:"This request used the heuristic-only planner path.",Be=Ee?`
      <div class="generic-list-item" style="margin-top: 1rem">
        <div class="generic-inline-group">
          <h3>Planner Debug / Model Participation</h3>
          <span class="generic-badge">Debug summary</span>
        </div>
        <div class="generic-debug-list">
          <div><strong>Selected candidate source:</strong> ${o(T(N))}</div>
          <div><strong>Selected candidate sources:</strong> ${o(Le.map(T).join(" + "))}</div>
          <div><strong>Candidate pool:</strong> ${o(Te)}</div>
          <div><strong>Candidates ranked:</strong> ${o(U??"Not available")}</div>
          <div><strong>Model candidates enabled:</strong> ${o(j?"Yes":"No")}</div>
          <div><strong>Candidate generator backend:</strong> ${o(Se||"Not used")}</div>
          <div><strong>Scorer backend:</strong> ${o(Ne)}</div>
          <div><strong>Selected candidate ID:</strong> ${o(Ae)}</div>
          <div><strong>Best heuristic candidate:</strong> ${o(c.best_heuristic_candidate_id||"Not available")} ${c.best_heuristic_candidate_score!==null&&c.best_heuristic_candidate_score!==void 0?`<span>(score ${o(k(c.best_heuristic_candidate_score))})</span>`:""}</div>
          <div><strong>Best model candidate:</strong> ${o(c.best_model_candidate_id||"Not available")} ${c.best_model_candidate_score!==null&&c.best_model_candidate_score!==void 0?`<span>(score ${o(k(c.best_model_candidate_score))})</span>`:""}</div>
          <div><strong>Model vs heuristic score gap:</strong> ${o(c.best_model_vs_best_heuristic_score_gap!==null&&c.best_model_vs_best_heuristic_score_gap!==void 0?k(c.best_model_vs_best_heuristic_score_gap):"Not available")}</div>
          <div><strong>Model candidates merged:</strong> ${o(c.model_candidates_merged_count!==null&&c.model_candidates_merged_count!==void 0?`${c.model_candidates_merged_count}`:"Not available")}</div>
          <div><strong>Materially different model candidates surviving fusion:</strong> ${o(c.materially_different_model_candidates_surviving_after_fusion!==null&&c.materially_different_model_candidates_surviving_after_fusion!==void 0?`${c.materially_different_model_candidates_surviving_after_fusion}`:"Not available")}</div>
          <div><strong>Average heuristic/model overlap:</strong> ${o(c.average_heuristic_model_overlap_jaccard!==null&&c.average_heuristic_model_overlap_jaccard!==void 0?k(c.average_heuristic_model_overlap_jaccard):"Not available")}</div>
          <div><strong>Best materially different model candidate:</strong> ${o(c.best_materially_different_model_candidate_id||"Not available")} ${c.best_materially_different_model_candidate_score!==null&&c.best_materially_different_model_candidate_score!==void 0?`<span>(score ${o(k(c.best_materially_different_model_candidate_score))})</span>`:""}</div>
          <div><strong>Winner vs best materially different model gap:</strong> ${o(c.best_materially_different_model_candidate_score_gap_to_selected!==null&&c.best_materially_different_model_candidate_score_gap_to_selected!==void 0?k(c.best_materially_different_model_candidate_score_gap_to_selected):"Not available")}</div>
          <div><strong>Why that model alternative lost:</strong> ${o(c.best_materially_different_model_candidate_loss_reason||"Not available")}</div>
          <div><strong>Similarity diagnosis:</strong> ${o(c.model_candidates_mostly_near_duplicates?"Model candidates were mostly near-duplicates.":j?"Model candidates introduced materially different baskets.":"Model path disabled.")}</div>
          <div><strong>Selection outcome:</strong> ${o(xe)}</div>
        </div>
        <div class="generic-debug-list" style="margin-top: 1rem">
          <div><strong>Selected vs heuristic baseline:</strong> ${o(M.difference_summary_vs_best_heuristic||c.selected_candidate_difference_summary||"Not available")}</div>
          <div><strong>Materially different from heuristic baseline:</strong> ${o(Z?Z.materially_different?"Yes":"No":"Not available")}</div>
          <div><strong>Selected candidate shopping_food_ids:</strong> <span class="generic-debug-code">${o(R(M.selected_candidate_shopping_food_ids||c.selected_candidate_shopping_food_ids||[]))}</span></div>
          <div><strong>Best heuristic candidate shopping_food_ids:</strong> <span class="generic-debug-code">${o(R(Me))}</span></div>
          <div><strong>Best model candidate shopping_food_ids:</strong> <span class="generic-debug-code">${o(R(Re))}</span></div>
        </div>
        ${ee?`<details class="generic-advanced" style="margin-top: 1rem">
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
                  <tbody>${ee}</tbody>
                </table>
              </details>`:""}
      </div>
    `:"",je=0,De=r=>`
        <div class="generic-list-item">
          <div class="generic-list-header">
            <div>
              <strong>${je+=1}. ${o(r.name)}</strong>
              <div class="generic-muted">Suggested buy: ${o(r.quantity_display)}</div>
            </div>
            <span class="generic-badge">${o(Qe(r.role))}</span>
          </div>
          <div class="generic-muted" style="margin-top: 0.5rem"><strong>${o(r.reason_short||"")}</strong></div>
          <div class="generic-muted" style="margin-top: 0.25rem">${o(r.why_selected||r.reason)}</div>
          ${r.value_reason_short?`<div class="generic-muted" style="margin-top: 0.25rem"><strong>Value note:</strong> ${o(r.value_reason_short)}${r.price_efficiency_note?` <span>${o(r.price_efficiency_note)}</span>`:""}</div>`:""}
          <div class="generic-muted" style="margin-top: 0.25rem">${o(r.reason)}</div>
          ${r.substitution?`<div class="generic-muted" style="margin-top: 0.35rem"><strong>Swap option:</strong> ${o(r.substitution)}${re(r)?` <span>${o(re(r))}</span>`:""}</div>`:""}
          <div class="generic-list-meta">
            <span><strong>Protein:</strong> ${o(r.estimated_protein_g)} g</span>
            <span><strong>Calories:</strong> ${o(r.estimated_calories_kcal)} kcal</span>
          </div>
          ${r.estimated_item_cost!==null&&r.estimated_item_cost!==void 0?`<div class="generic-muted" style="margin-top: 0.35rem"><strong>Typical regional price:</strong> $${o(r.typical_unit_price??r.estimated_unit_price)} ${o(r.price_unit_display||"")}; typical item cost about <strong>$${o(r.typical_item_cost??r.estimated_item_cost)}</strong>${r.estimated_price_low!==null&&r.estimated_price_low!==void 0&&r.estimated_price_high!==null&&r.estimated_price_high!==void 0?` <span>(regional range $${o(r.estimated_price_low)}-$${o(r.estimated_price_high)})</span>`:""}.</div>`:""}
        </div>
      `,Fe=se.map(r=>{let y=n.shopping_list.filter(Oe=>Oe.role===r.role);return y.length?`
      <div class="generic-list-item" style="margin-top: 1rem">
        <div class="generic-inline-group">
          <h3>${o(r.title)}</h3>
          <span class="generic-badge">${y.length} ${y.length===1?"item":"items"}</span>
        </div>
        <div class="generic-list">
          ${y.map(De).join("")}
        </div>
      </div>
    `:""}).join(""),Ge=(n.assumptions||[]).map(r=>`<li>${o(r)}</li>`).join(""),O=(n.pantry_notes||[]).map(r=>`<li>${o(r)}</li>`).join(""),K=(n.scaling_notes||[]).map(r=>`<li>${o(r)}</li>`).join(""),q=(n.warnings||[]).map(r=>`<li>${o(r)}</li>`).join(""),I=(n.split_notes||[]).map(r=>`<li>${o(r)}</li>`).join(""),H=(n.realism_notes||[]).map(r=>`<li>${o(r)}</li>`).join(""),te=[n.estimated_basket_cost_low!==void 0&&n.estimated_basket_cost_high!==void 0?`<p class="generic-muted"><strong>Typical basket range:</strong> about $${o(n.estimated_basket_cost_low)}-$${o(n.estimated_basket_cost_high)}</p>`:"",n.price_area_name?`<p class="generic-muted" style="margin-top: 0.5rem"><strong>Regional price area:</strong> ${o(n.price_area_name)} (${o(n.price_area_code||"")})</p>`:"",n.price_source_note?`<p class="generic-muted" style="margin-top: 0.5rem">${o(n.price_source_note)}</p>`:"",n.price_adjustment_note?`<p class="generic-muted" style="margin-top: 0.5rem">${o(n.price_adjustment_note)}</p>`:"",n.basket_cost_note?`<p class="generic-muted" style="margin-top: 0.5rem">${o(n.basket_cost_note)}</p>`:"",n.price_confidence_note?`<p class="generic-muted" style="margin-top: 0.5rem">${o(n.price_confidence_note)}</p>`:""].filter(Boolean).join(""),ne=(n.store_fit_notes||[]).map(r=>`
        <div class="generic-list-item" style="margin-top: 0.75rem">
          <div class="generic-inline-group">
            <h3>${o(r.store_name||"Nearby store")}</h3>
            <span class="generic-badge">${o(r.fit_label||"Store fit")}</span>
          </div>
          <div class="generic-muted"><strong>${o(r.category||"store")}</strong>${r.distance_m!==void 0&&r.distance_m!==null?` \u2022 about ${o(Number(r.distance_m).toFixed(0))} m away`:""}</div>
          <div class="generic-muted" style="margin-top: 0.25rem">${o(r.note||"")}</div>
        </div>
      `).join(""),ie=V.map(r=>{let y=n[r.key];return y?.store_id?`
        <div class="generic-list-item" style="margin-top: 0.75rem">
          <div class="generic-inline-group">
            <h3>${o(r.title)}</h3>
            <span class="generic-badge">${o(y.store_name||"Nearby store")}</span>
          </div>
          <div class="generic-muted"><strong>${o(y.category||"store")}</strong>${y.distance_m!==void 0&&y.distance_m!==null?` \u2022 about ${o(Number(y.distance_m).toFixed(0))} m away`:""}</div>
          <div class="generic-muted" style="margin-top: 0.25rem">${o(y.note||"")}</div>
        </div>
      `:""}).join(""),ae=(n.meal_suggestions||[]).map(r=>`
        <div class="generic-list-item" style="margin-top: 0.75rem">
          <div class="generic-inline-group">
            <h3>${o(r.title||"Meal idea")}</h3>
            <span class="generic-badge">${o(String(r.meal_type||"idea").replaceAll("_"," "))}</span>
          </div>
          <div class="generic-muted"><strong>${o((r.items||[]).join(", "))}</strong></div>
          ${r.description?`<div class="generic-muted" style="margin-top: 0.25rem">${o(r.description)}</div>`:""}
        </div>
      `).join(""),Ue=de.filter(r=>m?.[r.targetKey]!==void 0&&m?.[r.estimatedKey]!==void 0).map(r=>`
        <div class="generic-summary-metric">
          <div class="generic-muted">${o(r.label)}</div>
          <strong>${o(m[r.estimatedKey])} ${o(r.unit)}</strong>
          <div>Target: ${o(m[r.targetKey])} ${o(r.unit)}</div>
          <div class="generic-muted">Difference: ${o(He(m[r.estimatedKey],m[r.targetKey],r.unit))}</div>
        </div>
      `).join("");e.innerHTML=`
    ${E(s||"Recommendation ready.","success")}
    ${E(l?.message,l?.kind)}
    <div class="generic-list-item" style="margin-bottom: 1rem">
      <div class="generic-inline-group">
        <h3>Shopping List</h3>
        <div class="generic-badge-group">
          <span class="generic-badge ${o(ze(N))}">
            ${o(Ve(N))}
          </span>
          <span class="generic-badge">Suggested shopping list for ${g} ${g===1?"day":"days"}</span>
        </div>
      </div>
      <p class="generic-muted">Daily nutrition goals stay the same. Quantities below are scaled for the selected shopping window in <strong>${o(B)}</strong> shopping mode.</p>
      <p class="generic-muted" style="margin-top: 0.5rem"><strong>Planning pipeline:</strong> ${o(Pe)}</p>
      <div class="generic-actions" style="margin-top: 0.75rem">
        <button type="button" data-export-action="copy-shopping">Copy shopping list</button>
        <button type="button" data-export-action="copy-plan">Copy full plan</button>
        <button type="button" data-export-action="download-plan">Download as text</button>
      </div>
      ${n.estimated_basket_cost!==void 0?`<p class="generic-muted" style="margin-top: 0.5rem"><strong>Estimated typical basket cost:</strong> about $${o(n.estimated_basket_cost)}.</p>`:""}
    </div>
    <div class="generic-list">
      ${Fe||'<div class="generic-empty">Your pantry already covers the suggested basket for this plan. Review the notes below if you still want a small top-up shop.</div>'}
    </div>
    ${Be}
    ${ie?`<div class="generic-list-item" style="margin-top: 1rem">
            <div class="generic-inline-group">
              <h3>Recommended store picks for this list</h3>
              <span class="generic-badge">${V.filter(r=>n[r.key]?.store_id).length} picks</span>
            </div>
            <p class="generic-muted">These are quick store-type recommendations based on the basket style and nearby store mix. They do not reflect exact inventory.</p>
            ${ie}
          </div>`:""}
    ${ne?`<div class="generic-list-item" style="margin-top: 1rem">
            <div class="generic-inline-group">
              <h3>Best nearby store fits for this list</h3>
              <span class="generic-badge">${(n.store_fit_notes||[]).length} suggestions</span>
            </div>
            <p class="generic-muted">These are coarse store-fit suggestions based on the basket style, shopping mode, and nearby store type. They do not reflect exact inventory.</p>
            ${ne}
          </div>`:""}
    ${ae?`<div class="generic-list-item" style="margin-top: 1rem">
            <div class="generic-inline-group">
              <h3>Example ways to use this list</h3>
              <span class="generic-badge">${(n.meal_suggestions||[]).length} ideas</span>
            </div>
            <p class="generic-muted">These are lightweight examples built from the same recommended items. They are not a full meal plan.</p>
            ${ae}
          </div>`:""}
    ${K||q||I||H||O?`<div class="generic-list-item" style="margin-top: 1rem">
            <div class="generic-inline-group">
              <h3>Shopping Notes</h3>
              <span class="generic-badge">${n.adjusted_by_split?"Scaling and realism guidance":"Scaling guidance"}</span>
            </div>
            ${K?`<p class="generic-muted"><strong>Scaling notes</strong></p><ul class="generic-assumptions">${K}</ul>`:""}
            ${I?`<p class="generic-muted" style="margin-top: 0.75rem"><strong>Split notes</strong></p><ul class="generic-assumptions">${I}</ul>`:""}
            ${H?`<p class="generic-muted" style="margin-top: 0.75rem"><strong>Realism notes</strong></p><ul class="generic-assumptions">${H}</ul>`:""}
            ${O?`<p class="generic-muted" style="margin-top: 0.75rem"><strong>Pantry adjustments</strong></p><ul class="generic-assumptions">${O}</ul>`:""}
            ${q?`<p class="generic-muted" style="margin-top: 0.75rem"><strong>Warnings</strong></p><ul class="generic-assumptions">${q}</ul>`:""}
          </div>`:""}
    <div class="generic-list-item" style="margin-top: 1rem">
      <div class="generic-inline-group">
        <h3>Nutrition Summary</h3>
        <span class="generic-badge">${g===1?"Daily total":`${g}-day total`}</span>
      </div>
      <div class="generic-summary-grid">
        ${Ue}
      </div>
    </div>
    <div class="generic-list-item" style="margin-top: 1rem">
      <div class="generic-inline-group">
        <h3>Approximate Guidance</h3>
        <span class="generic-badge">Demo-friendly estimate</span>
      </div>
      <p class="generic-muted">Use this list as a practical starting point, not as exact store inventory or guaranteed product availability.</p>
      <ul class="generic-assumptions">${Ge}</ul>
    </div>
    ${te?`<div class="generic-list-item" style="margin-top: 1rem">
            <div class="generic-inline-group">
              <h3>Pricing notes</h3>
              <span class="generic-badge">Typical regional estimate</span>
            </div>
            ${te}
          </div>`:""}
  `,e.querySelector('[data-export-action="copy-shopping"]')?.addEventListener("click",()=>{i.onCopyShoppingList?.()}),e.querySelector('[data-export-action="copy-plan"]')?.addEventListener("click",()=>{i.onCopyFullPlan?.()}),e.querySelector('[data-export-action="download-plan"]')?.addEventListener("click",()=>{i.onDownloadPlan?.()})}function w(e){return String(e??"").replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;").replaceAll('"',"&quot;").replaceAll("'","&#39;")}function P(e,t){return e?`<div class="generic-notice ${w(t||"info")}">${w(e)}</div>`:""}function ge(e,t){let{stores:i,storeStatus:n,storeError:s,isLookingUpStores:d,hasLookedUpStores:u}=t;if(d){e.innerHTML=`
      ${P(n||"Looking up nearby supermarkets...","info")}
      <div class="generic-empty">Searching for nearby supermarkets. This usually takes a moment.</div>
    `;return}if(s){e.innerHTML=`
      ${P(s,"error")}
      <div class="generic-empty">Check the location fields and try the store lookup again.</div>
    `;return}if(!u){e.innerHTML=`
      <div class="generic-empty">
        Start with a location or preset, then use <strong>Find Nearby Supermarkets</strong> to load stores for the area.
      </div>
    `;return}if(!i.length){e.innerHTML=`
      ${P(n||"No nearby stores found.","info")}
      <div class="generic-empty">No supermarkets were found within the current search radius. Try increasing the radius or switching to a different location.</div>
    `;return}let _=i.map((l,m)=>`
        <div class="generic-list-item">
          <div class="generic-list-header">
            <div>
              <strong>${m+1}. ${w(l.name)}</strong>
              <div class="generic-muted">${w(l.address)}</div>
            </div>
            <span class="generic-badge">${Math.round(l.distance_m)} m</span>
          </div>
          <div class="generic-list-meta">
            <span><strong>Category:</strong> ${w(l.category)}</span>
            <span><strong>Coordinates:</strong> ${w(l.lat)}, ${w(l.lon)}</span>
          </div>
        </div>
      `).join("");e.innerHTML=`
    ${P(n||`Loaded ${i.length} nearby store${i.length===1?"":"s"}.`,"success")}
    <div class="generic-list">${_}</div>
  `}var Xe="https://nominatim.openstreetmap.org/search",Ze=6,et=4,tt="random_forest",nt=new Set(["auto","logistic_regression","random_forest","hist_gradient_boosting"]),_e={locationQuery:"Mountain View, CA",lat:"",lon:"",radius_m:"8000",store_limit:"5",days:"1",shopping_mode:"balanced",protein:"130",calories:"2200",carbohydrate:"240",fat:"70",fiber:"30",vegetarian:!1,dairy_free:!1,vegan:!1,budget_friendly:!1,meal_style:"any"};function C(e){return{..._e,...e}}var fe=[{id:"muscle_gain",label:"Muscle Gain",values:C({protein:"170",calories:"2800",carbohydrate:"330",fat:"85",fiber:"35"}),notice:'Loaded the muscle gain preset for "Mountain View, CA".'},{id:"fat_loss",label:"Fat Loss",values:C({protein:"150",calories:"1800",carbohydrate:"160",fat:"55",fiber:"30"}),notice:'Loaded the fat loss preset for "Mountain View, CA".'},{id:"maintenance",label:"Maintenance",values:C({protein:"130",calories:"2200",carbohydrate:"240",fat:"70",fiber:"30"}),notice:'Loaded the maintenance preset for "Mountain View, CA".'},{id:"high_protein_vegetarian",label:"High-Protein Vegetarian",values:C({protein:"140",calories:"2100",carbohydrate:"220",fat:"70",fiber:"32",vegetarian:!0}),notice:'Loaded the high-protein vegetarian preset for "Mountain View, CA".'},{id:"budget_friendly_healthy",label:"Budget-Friendly Healthy",values:C({protein:"120",calories:"2100",carbohydrate:"230",fat:"65",fiber:"35",budget_friendly:!0}),notice:'Loaded the budget-friendly healthy preset for "Mountain View, CA".'},{id:"vegan",label:"Vegan",values:C({protein:"125",calories:"2200",carbohydrate:"245",fat:"68",fiber:"36",vegan:!0,vegetarian:!0,dairy_free:!0}),notice:'Loaded the vegan preset for "Mountain View, CA".'},{id:"dairy_free",label:"Dairy-free",values:C({protein:"135",calories:"2150",carbohydrate:"225",fat:"68",fiber:"28",dairy_free:!0}),notice:'Loaded the dairy-free preset for "Mountain View, CA".'}];function be(){return typeof window>"u"?{}:window.GENERIC_APP_CONFIG||{}}function W(){return!!be().developerMode}function he(){let e=be().hybridPlannerDefaults||{};return{candidateCount:Number(e.candidateCount||Ze),modelCandidateCount:Number(e.modelCandidateCount||et),candidateGeneratorBackend:String(e.candidateGeneratorBackend||tt)}}function it(){let e=he();return{developerMode:W(),enable_model_candidates:!0,model_candidate_count:String(e.modelCandidateCount),candidate_generator_backend:e.candidateGeneratorBackend,debug_candidate_generation:!1,debug_scorer:!1,candidate_count:String(e.candidateCount)}}var a={..._e,...it(),pantry_items:[],stores:[],storesLookupContext:null,recommendation:null,errors:{},formNotice:null,storeStatus:"",storeError:"",recommendationStatus:"",recommendationError:"",exportNotice:null,isLookingUpStores:!1,isGeneratingRecommendations:!1,isLocating:!1,isResolvingAddress:!1,hasLookedUpStores:!1,hasRequestedRecommendation:!1,presets:fe};function h(e){if(e==null||String(e).trim()==="")return null;let t=Number(e);return Number.isFinite(t)?t:null}function Y(e){if(e==="true")return!0;if(e==="false")return!1}function me(e){if(e==null||String(e).trim()==="")return;let t=Number.parseInt(String(e),10);if(!(!Number.isFinite(t)||t<=0))return t}function at(e,t){if(e==null||String(e).trim()==="")return;let i=String(e).trim().toLowerCase();return t.has(i)?i:void 0}function ye(){return typeof window>"u"||!window.location||typeof window.location.search!="string"?"":window.location.search}function ve(e=ye()){if(!W())return{};let t=new URLSearchParams(e||""),i={},n=Y(t.get("enable_model_candidates"));n!==void 0&&(i.enable_model_candidates=n);let s=me(t.get("model_candidate_count"));s!==void 0&&(i.model_candidate_count=s);let d=at(t.get("candidate_generator_backend"),nt);d!==void 0&&(i.candidate_generator_backend=d);let u=Y(t.get("debug_candidate_generation"));u!==void 0&&(i.debug_candidate_generation=u);let _=Y(t.get("debug_scorer"));_!==void 0&&(i.debug_scorer=_);let l=me(t.get("candidate_count"));l!==void 0&&(i.candidate_count=l);let m=String(t.get("scorer_model_path")||"").trim();m&&(i.scorer_model_path=m);let g=String(t.get("candidate_generator_model_path")||"").trim();return g&&(i.candidate_generator_model_path=g),i}Object.assign(a,ve());function $e(e){let t=h(e.lat),i=h(e.lon);return t!==null&&i!==null&&t>=-90&&t<=90&&i>=-180&&i<=180}function J(e){let t=h(e.lat),i=h(e.lon),n=h(e.radius_m);return t===null||i===null||n===null?null:{lat:Number(t.toFixed(6)),lon:Number(i.toFixed(6)),radius_m:Math.round(n)}}function ot(e,t){return!e||!t?!1:e.lat===t.lat&&e.lon===t.lon&&e.radius_m===t.radius_m}function rt(e,t=ye()){let i=h(e.radius_m),n={location:{lat:Number(e.lat),lon:Number(e.lon)},targets:{protein:Number(e.protein),energy_fibre_kcal:Number(e.calories)},preferences:{vegetarian:e.vegetarian,dairy_free:e.dairy_free,vegan:e.vegan,budget_friendly:e.budget_friendly,meal_style:e.meal_style||"any"},pantry_items:Array.isArray(e.pantry_items)?e.pantry_items:[],store_limit:Number(e.store_limit),days:Number(e.days||1),shopping_mode:e.shopping_mode||"balanced"};i!==null&&(n.radius_m=i);let s=J(e);e.hasLookedUpStores&&Array.isArray(e.stores)&&e.stores.length&&e.stores.length>=Number(e.store_limit)&&ot(e.storesLookupContext,s)&&(n.stores=e.stores.slice(0,Number(e.store_limit)));for(let[d,u]of Object.entries({carbohydrate:h(e.carbohydrate),fat:h(e.fat),fiber:h(e.fiber)}))u!==null&&(n.targets[d]=u);if(W()){let d=he();n.enable_model_candidates=!!e.enable_model_candidates,n.model_candidate_count=Number(e.model_candidate_count||d.modelCandidateCount),n.candidate_generator_backend=e.candidate_generator_backend||d.candidateGeneratorBackend,n.debug_candidate_generation=!!e.debug_candidate_generation,n.debug_scorer=!!e.debug_scorer,n.candidate_count=Number(e.candidate_count||d.candidateCount),Object.assign(n,ve(t))}return n}function st(e,t="recommend"){let i={},n=String(e.locationQuery||"").trim(),s=h(e.lat),d=h(e.lon),u=h(e.protein),_=h(e.calories),l=[["carbohydrate","carbohydrate"],["fat","fat"],["fiber","fiber"]],m=$e(e);if(!n&&!m&&(i.locationQuery="Enter a city or address, or provide coordinates in Advanced location settings."),n||((s===null||s<-90||s>90)&&(i.lat="Enter a latitude between -90 and 90."),(d===null||d<-180||d>180)&&(i.lon="Enter a longitude between -180 and 180.")),t==="recommend"){(u===null||u<=0)&&(i.protein="Enter a protein target greater than 0."),(_===null||_<=0)&&(i.calories="Enter a calorie target greater than 0.");for(let[g,B]of l){let x=h(e[g]);x!==null&&x<=0&&(i[g]=`Enter a ${B} target greater than 0, or leave it blank.`)}}return i}async function dt(e,t=fetch){let i=String(e||"").trim();if(!i)throw new Error("Enter a city or address first.");let n=new URLSearchParams({q:i,format:"jsonv2",limit:"1"}),s=await t(`${Xe}?${n.toString()}`,{headers:{Accept:"application/json"}});if(!s.ok)throw new Error("Location search failed. Please try again.");let d=await s.json();if(!Array.isArray(d)||d.length===0)throw new Error("Could not find that location. Please try a different city or address.");let u=d[0];return{lat:Number(u.lat).toFixed(6),lon:Number(u.lon).toFixed(6),displayName:u.display_name||i}}function v(e,t="info"){a.formNotice=e?{message:e,kind:t}:null}function S(e,t="info"){a.exportNotice=e?{message:e,kind:t}:null}function lt(e){Object.assign(a,e);for(let t of Object.keys(e))a.errors[t]&&delete a.errors[t]}function ke(e){let t=st(a,e);return a.errors=t,Object.keys(t).length?(v("Fix the highlighted fields before continuing.","error"),b(),!1):(a.formNotice?.kind==="error"&&v(null),!0)}function ct(){a.stores=[],a.storesLookupContext=null,a.recommendation=null,a.storeStatus="",a.storeError="",a.recommendationStatus="",a.recommendationError="",a.exportNotice=null,a.hasLookedUpStores=!1,a.hasRequestedRecommendation=!1}async function we(){let e=String(a.locationQuery||"").trim();if(!e)return $e(a);a.isResolvingAddress=!0,v(`Finding coordinates for "${e}"...`,"info"),b();try{let t=await dt(e);return a.lat=t.lat,a.lon=t.lon,delete a.errors.locationQuery,delete a.errors.lat,delete a.errors.lon,v(`Using coordinates for "${e}". Advanced settings were updated automatically.`,"success"),!0}catch(t){return a.errors.locationQuery=t.message||"Could not find that location. Please try a different city or address.",v(a.errors.locationQuery,"error"),b(),!1}finally{a.isResolvingAddress=!1}}async function ut(){if(!ke("stores")||!await we())return;a.hasLookedUpStores=!0,a.storeError="",a.storeStatus="Looking up nearby supermarkets...",a.isLookingUpStores=!0,b();let t=new URLSearchParams({lat:a.lat,lon:a.lon,radius_m:a.radius_m,limit:a.store_limit});try{let i=await fetch(`/api/stores/nearby?${t.toString()}`),n=await i.json();if(!i.ok)throw new Error(n.error||"Store lookup failed.");a.stores=n.stores||[],a.storesLookupContext=J(a),a.storeStatus=a.stores.length?`Loaded ${a.stores.length} nearby supermarket${a.stores.length===1?"":"s"}.`:"No nearby supermarkets found for this location.",a.recommendation&&!a.recommendation.stores?.length&&(a.recommendation.stores=a.stores)}catch(i){a.stores=[],a.storeError=i.message||"Store lookup failed.",a.storeStatus=""}finally{a.isLookingUpStores=!1}b()}async function pt(){if(!ke("recommend")||!await we())return;a.hasRequestedRecommendation=!0,a.recommendation=null,a.recommendationError="",a.recommendationStatus="Generating recommendations...",a.exportNotice=null,a.isGeneratingRecommendations=!0,b();let t=J(a),i=rt(a);try{let n=await fetch("/api/recommendations/generic",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(i)}),s=await n.json();if(!n.ok)throw new Error(s.error||"Recommendation request failed.");a.recommendation=s,a.stores=s.stores||[],a.storesLookupContext=a.stores.length?t:null,a.hasLookedUpStores=!0,a.storeError="",a.storeStatus=a.stores.length?`Loaded ${a.stores.length} nearby supermarket${a.stores.length===1?"":"s"}.`:"No nearby supermarkets found for this location.",a.recommendationStatus=s.shopping_list?.length?"Shopping list ready.":"No shopping list was generated for the current inputs."}catch(n){a.recommendation=null,a.recommendationError=n.message||"Recommendation request failed.",a.recommendationStatus=""}finally{a.isGeneratingRecommendations=!1}b()}function gt(){if(!navigator.geolocation){v("Browser geolocation is not available here. Enter coordinates in Advanced location settings.","error"),b();return}a.isLocating=!0,v("Requesting your current location...","info"),b(),navigator.geolocation.getCurrentPosition(e=>{a.isLocating=!1,a.locationQuery="",a.lat=e.coords.latitude.toFixed(6),a.lon=e.coords.longitude.toFixed(6),delete a.errors.locationQuery,delete a.errors.lat,delete a.errors.lon,v("Location loaded from your browser. Advanced settings were updated automatically.","success"),b()},e=>{a.isLocating=!1,v({1:"Location access was denied. Enter a city, address, or coordinates manually.",2:"Your location could not be determined. Enter a city, address, or coordinates manually.",3:"Location lookup timed out. Enter a city, address, or coordinates manually."}[e.code]||"Location lookup failed. Enter a city, address, or coordinates manually.","error"),b()},{enableHighAccuracy:!1,timeout:1e4,maximumAge:3e5})}function mt(e){let t=fe.find(i=>i.id===e);t&&(Object.assign(a,t.values),a.pantry_items=Array.isArray(t.values?.pantry_items)?[...t.values.pantry_items]:[],a.errors={},ct(),v(t.notice,"success"),b())}async function Ce(e){if(!e)throw new Error("There is no recommendation to export yet.");if(navigator.clipboard?.writeText){await navigator.clipboard.writeText(e);return}let t=document.createElement("textarea");t.value=e,t.setAttribute("readonly","readonly"),t.style.position="fixed",t.style.opacity="0",document.body.appendChild(t),t.select();let i=document.execCommand("copy");if(document.body.removeChild(t),!i)throw new Error("Copy is not available in this browser.")}function _t(e,t){if(!t)throw new Error("There is no recommendation to export yet.");let i=new Blob([t],{type:"text/plain;charset=utf-8"}),n=URL.createObjectURL(i),s=document.createElement("a");s.href=n,s.download=e,document.body.appendChild(s),s.click(),document.body.removeChild(s),URL.revokeObjectURL(n)}async function ft(){try{await Ce(ue(a.recommendation)),S("Copied the grouped shopping list.","success")}catch(e){S(e.message||"Could not copy the shopping list.","error")}b()}async function bt(){try{await Ce(z(a.recommendation)),S("Copied the full grocery plan.","success")}catch(e){S(e.message||"Could not copy the full plan.","error")}b()}function ht(){try{_t("generic-grocery-plan.txt",z(a.recommendation)),S("Downloaded the grocery plan as text.","success")}catch(e){S(e.message||"Could not download the grocery plan.","error")}b()}function b(){oe(document.getElementById("generic-form"),a,{onChange:lt,onLookupStores:ut,onRecommend:pt,onUseMyLocation:gt,onApplyPreset:mt}),ge(document.getElementById("generic-stores"),a),pe(document.getElementById("generic-results"),a,{onCopyShoppingList:ft,onCopyFullPlan:bt,onDownloadPlan:ht})}typeof document<"u"&&b();export{rt as buildRecommendationPayload,dt as geocodeAddress,ve as getScorerQueryOverrides,Y as parseBooleanParam,me as parsePositiveIntParam,st as validateFormState};
