function $(e,n){let i=e.querySelector(`[name="${n}"]`);return i?i.type==="hidden"?String(i.value||"").trim().toLowerCase()==="true":i.checked||!1:!1}function Ue(e,n){return[...e.querySelectorAll(`[name="${n}"]:checked`)].map(i=>i.value)}var Oe=[{id:"eggs",label:"Eggs"},{id:"milk",label:"Milk"},{id:"greek_yogurt",label:"Greek yogurt"},{id:"oats",label:"Oats"},{id:"rice",label:"Rice"},{id:"beans",label:"Beans"},{id:"lentils",label:"Lentils"},{id:"bananas",label:"Bananas"},{id:"broccoli",label:"Broccoli"},{id:"potatoes",label:"Potatoes"},{id:"olive_oil",label:"Olive oil"},{id:"peanut_butter",label:"Peanut butter"},{id:"tofu",label:"Tofu"},{id:"chicken_breast",label:"Chicken breast"}];function u(e){return String(e??"").replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;").replaceAll('"',"&quot;").replaceAll("'","&#39;")}function m(e,n){return e.errors?.[n]||""}function Ie(e){return e.formNotice?.message?`
    <div class="generic-notice ${u(e.formNotice.kind||"info")}" role="status">
      ${u(e.formNotice.message)}
    </div>
  `:""}function ae(e,n,i){let t=(n.presets||[]).map(g=>`
        <button type="button" class="generic-preset-button" data-preset-id="${u(g.id)}">
          ${u(g.label)}
        </button>
      `).join(""),d=n.isLocating||n.isResolvingAddress||n.isLookingUpStores||n.isGeneratingRecommendations,l=!!n.developerMode,p=Oe.map(g=>`
        <label>
          <input
            name="pantry_items"
            type="checkbox"
            value="${u(g.id)}"
            ${(n.pantry_items||[]).includes(g.id)?"checked":""}
          />
          ${u(g.label)}
        </label>
      `).join(""),f=l?`
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
              value="${u(n.model_candidate_count)}"
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
              value="${u(n.candidate_count)}"
            />
            <span class="generic-help">How many fused candidates the trained scorer reranks before choosing the final basket.</span>
          </label>
          <label>
            Candidate generator backend
            <select name="candidate_generator_backend">
              <option value="auto" ${n.candidate_generator_backend==="auto"?"selected":""}>Auto</option>
              <option value="logistic_regression" ${n.candidate_generator_backend==="logistic_regression"?"selected":""}>Logistic regression</option>
              <option value="random_forest" ${n.candidate_generator_backend==="random_forest"?"selected":""}>Random forest</option>
              <option value="hist_gradient_boosting" ${n.candidate_generator_backend==="hist_gradient_boosting"?"selected":""}>HistGradientBoosting</option>
            </select>
            <span class="generic-help">Choose a backend only when comparing internal candidate-generator artifacts.</span>
          </label>
        </div>
        <div class="generic-checkboxes" style="margin-top: 0.75rem">
          <label>
            <input name="enable_model_candidates" type="checkbox" ${n.enable_model_candidates?"checked":""} />
            Enable learned candidates
          </label>
          <label>
            <input name="debug_candidate_generation" type="checkbox" ${n.debug_candidate_generation?"checked":""} />
            Show candidate-generation debug
          </label>
          <label>
            <input name="debug_scorer" type="checkbox" ${n.debug_scorer?"checked":""} />
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
        <input name="model_candidate_count" type="hidden" value="${u(n.model_candidate_count)}" />
        <input name="candidate_generator_backend" type="hidden" value="${u(n.candidate_generator_backend)}" />
        <input name="debug_candidate_generation" type="hidden" value="false" />
        <input name="debug_scorer" type="hidden" value="false" />
        <input name="candidate_count" type="hidden" value="${u(n.candidate_count)}" />
      </div>
    `;e.innerHTML=`
    <form id="generic-input-form" novalidate>
      ${Ie(n)}
      <div>
        <h3>Goal Presets</h3>
        <p class="generic-help">Start from a common goal, then fine-tune the location targets or preferences if needed.</p>
        <div class="generic-presets">${t}</div>
      </div>

      <div class="generic-form-grid">
        <label class="generic-span-full">
          City or address
          <input
            name="locationQuery"
            type="text"
            placeholder="Mountain View, CA"
            value="${u(n.locationQuery)}"
            aria-invalid="${m(n,"locationQuery")?"true":"false"}"
          />
          <span class="generic-field-error">${u(m(n,"locationQuery"))}</span>
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
            <option value="1" ${n.days==="1"?"selected":""}>1 day</option>
            <option value="3" ${n.days==="3"?"selected":""}>3 days</option>
            <option value="5" ${n.days==="5"?"selected":""}>5 days</option>
            <option value="7" ${n.days==="7"?"selected":""}>7 days</option>
          </select>
          <span class="generic-help">Daily targets stay the same. Quantities are scaled for the selected shopping window.</span>
        </label>
        <label>
          Shopping mode
          <select name="shopping_mode">
            <option value="balanced" ${n.shopping_mode==="balanced"?"selected":""}>Balanced</option>
            <option value="fresh" ${n.shopping_mode==="fresh"?"selected":""}>Fresh</option>
            <option value="bulk" ${n.shopping_mode==="bulk"?"selected":""}>Bulk</option>
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
            value="${u(n.calories)}"
            aria-invalid="${m(n,"calories")?"true":"false"}"
            required
          />
          <span class="generic-field-error">${u(m(n,"calories"))}</span>
        </label>
        <label>
          Protein (g)
          <input
            name="protein"
            type="number"
            min="1"
            step="1"
            value="${u(n.protein)}"
            aria-invalid="${m(n,"protein")?"true":"false"}"
            required
          />
          <span class="generic-field-error">${u(m(n,"protein"))}</span>
        </label>
        <label>
          Carbs (g)
          <input
            name="carbohydrate"
            type="number"
            min="1"
            step="1"
            value="${u(n.carbohydrate)}"
            aria-invalid="${m(n,"carbohydrate")?"true":"false"}"
          />
          <span class="generic-field-error">${u(m(n,"carbohydrate"))}</span>
        </label>
        <label>
          Fat (g)
          <input
            name="fat"
            type="number"
            min="1"
            step="1"
            value="${u(n.fat)}"
            aria-invalid="${m(n,"fat")?"true":"false"}"
          />
          <span class="generic-field-error">${u(m(n,"fat"))}</span>
        </label>
        <label>
          Fiber (g)
          <input
            name="fiber"
            type="number"
            min="1"
            step="1"
            value="${u(n.fiber)}"
            aria-invalid="${m(n,"fiber")?"true":"false"}"
          />
          <span class="generic-field-error">${u(m(n,"fiber"))}</span>
        </label>
      </div>

      <div class="generic-form-grid">
        <div class="generic-span-full">
          <h3>Food preferences</h3>
          <label style="display: block; margin-bottom: 0.75rem">
            Meal or use case
            <select name="meal_style">
              <option value="any" ${n.meal_style==="any"?"selected":""}>Any</option>
              <option value="breakfast" ${n.meal_style==="breakfast"?"selected":""}>Breakfast</option>
              <option value="lunch_dinner" ${n.meal_style==="lunch_dinner"?"selected":""}>Lunch / dinner</option>
              <option value="snack" ${n.meal_style==="snack"?"selected":""}>Snack</option>
            </select>
          </label>
          <div class="generic-checkboxes">
            <label>
              <input name="vegetarian" type="checkbox" ${n.vegetarian?"checked":""} />
              Vegetarian (includes eggs and dairy)
            </label>
            <label><input name="vegan" type="checkbox" ${n.vegan?"checked":""} /> Vegan</label>
            <label><input name="dairy_free" type="checkbox" ${n.dairy_free?"checked":""} /> Dairy-free</label>
            <label><input name="low_prep" type="checkbox" ${n.low_prep?"checked":""} /> Low prep</label>
            <label><input name="budget_friendly" type="checkbox" ${n.budget_friendly?"checked":""} /> Budget friendly</label>
          </div>
          <p class="generic-help">Recommendations stay generic. They do not depend on exact store inventory or branded products.</p>
        </div>
      </div>

      <div class="generic-form-grid">
        <div class="generic-span-full">
          <h3>Already have</h3>
          <p class="generic-help">Mark common items already in your pantry or fridge. The shopping list will reduce or omit them where the basket still works.</p>
          <div class="generic-checkboxes">
            ${p}
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
              value="${u(n.calcium)}"
              aria-invalid="${m(n,"calcium")?"true":"false"}"
            />
            <span class="generic-field-error">${u(m(n,"calcium"))}</span>
          </label>
          <label>
            Iron (mg)
            <input
              name="iron"
              type="number"
              min="1"
              step="0.1"
              value="${u(n.iron)}"
              aria-invalid="${m(n,"iron")?"true":"false"}"
            />
            <span class="generic-field-error">${u(m(n,"iron"))}</span>
          </label>
          <label>
            Vitamin C (mg)
            <input
              name="vitamin_c"
              type="number"
              min="1"
              step="1"
              value="${u(n.vitamin_c)}"
              aria-invalid="${m(n,"vitamin_c")?"true":"false"}"
            />
            <span class="generic-field-error">${u(m(n,"vitamin_c"))}</span>
          </label>
        </div>
      </details>

      ${f}

      <div class="generic-actions">
        <button type="button" id="use-location-button" ${d?"disabled":""}>
          ${n.isLocating?"Locating...":"Use My Location"}
        </button>
        <button type="button" id="lookup-stores-button" ${d?"disabled":""}>
          ${n.isResolvingAddress||n.isLookingUpStores?"Looking Up...":"Find Nearby Supermarkets"}
        </button>
        <button type="submit" ${d?"disabled":""}>
          ${n.isResolvingAddress||n.isGeneratingRecommendations?"Generating...":"Recommend"}
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
              value="${u(n.lat)}"
              aria-invalid="${m(n,"lat")?"true":"false"}"
            />
            <span class="generic-field-error">${u(m(n,"lat"))}</span>
          </label>
          <label>
            Longitude
            <input
              name="lon"
              type="number"
              step="any"
              value="${u(n.lon)}"
              aria-invalid="${m(n,"lon")?"true":"false"}"
            />
            <span class="generic-field-error">${u(m(n,"lon"))}</span>
          </label>
          <label>
            Search radius (m)
            <input name="radius_m" type="number" min="1" step="100" value="${u(n.radius_m)}" required />
            <span class="generic-help">How far to search for supermarkets around the selected point.</span>
          </label>
          <label>
            Nearby stores to show
            <input name="store_limit" type="number" min="1" max="25" step="1" value="${u(n.store_limit)}" required />
            <span class="generic-help">The list is always sorted by distance.</span>
          </label>
        </div>
      </details>
    </form>
  `;let s=e.querySelector("#generic-input-form"),_=()=>i.onChange({locationQuery:s.locationQuery.value,lat:s.lat.value,lon:s.lon.value,radius_m:s.radius_m.value,store_limit:s.store_limit.value,days:s.days.value,shopping_mode:s.shopping_mode.value,protein:s.protein.value,calories:s.calories.value,carbohydrate:s.carbohydrate.value,fat:s.fat.value,fiber:s.fiber.value,calcium:s.calcium.value,iron:s.iron.value,vitamin_c:s.vitamin_c.value,vegetarian:$(s,"vegetarian"),dairy_free:$(s,"dairy_free"),vegan:$(s,"vegan"),low_prep:$(s,"low_prep"),budget_friendly:$(s,"budget_friendly"),meal_style:s.meal_style.value,enable_model_candidates:$(s,"enable_model_candidates"),model_candidate_count:s.model_candidate_count.value,candidate_generator_backend:s.candidate_generator_backend.value,debug_candidate_generation:$(s,"debug_candidate_generation"),debug_scorer:$(s,"debug_scorer"),candidate_count:s.candidate_count.value,pantry_items:Ue(s,"pantry_items")});s.addEventListener("change",_),s.addEventListener("input",_),s.addEventListener("submit",g=>{g.preventDefault(),_(),i.onRecommend()}),e.querySelector("#lookup-stores-button").addEventListener("click",()=>{_(),i.onLookupStores()}),e.querySelector("#use-location-button").addEventListener("click",()=>{_(),i.onUseMyLocation()}),e.querySelectorAll("[data-preset-id]").forEach(g=>{g.addEventListener("click",()=>{i.onApplyPreset(g.dataset.presetId)})})}function o(e){return String(e??"").replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;").replaceAll('"',"&quot;").replaceAll("'","&#39;")}function x(e,n){return e?`<div class="generic-notice ${o(n||"info")}">${o(e)}</div>`:""}function Ke(e,n,i){let t=Math.round((e-n)*10)/10;return`${t>0?"+":""}${t} ${i}`}function qe(e){return{protein_anchor:"Protein anchor",carb_base:"Carb base",produce:"Produce",calorie_booster:"Calorie booster"}[e]||"Recommended item"}function L(e){let n=String(e||"heuristic").trim().toLowerCase();return n==="model"||n==="hybrid"||n==="repaired_model"?n:"heuristic"}function T(e){return{heuristic:"Heuristic",model:"Model",hybrid:"Hybrid",repaired_model:"Repaired model"}[L(e)]||"Heuristic"}function He(e){return`${T(e)} result`}function Qe(e){return`generic-badge-source-${L(e)}`}function Ve(e,n){let i=Array.isArray(e)?e:[],t=[...new Set(i.map(d=>L(d)).filter(Boolean))];return t.length?t:[L(n)]}function ze(e,n){let i=L(n);return e?i==="heuristic"?"Model path was enabled, but the highest-ranked basket still came from the heuristic pool.":i==="model"?"A model-generated candidate won the final ranking.":i==="repaired_model"?"A model-generated basket needed repair and still won the final ranking.":"A fused hybrid candidate won the final ranking.":"Model path disabled; the heuristic-only baseline produced this result."}function R(e){let n=Array.isArray(e)?e.filter(Boolean):[];return n.length?n.join(", "):"Not available"}function w(e,n=3){if(e==null||e==="")return"Not available";let i=Number(e);return Number.isFinite(i)?i.toFixed(n):String(e)}var re=[{role:"protein_anchor",title:"Protein picks"},{role:"carb_base",title:"Carb base"},{role:"produce",title:"Produce"},{role:"calorie_booster",title:"Extras / boosters"}],Q=[{key:"one_stop_pick",title:"One-stop pick"},{key:"budget_pick",title:"Budget pick"},{key:"produce_pick",title:"Produce pick"},{key:"bulk_pick",title:"Bulk pick"}],se=[{label:"Protein",targetKey:"protein_target_g",estimatedKey:"protein_estimated_g",unit:"g"},{label:"Calories",targetKey:"calorie_target_kcal",estimatedKey:"calorie_estimated_kcal",unit:"kcal"},{label:"Carbs",targetKey:"carbohydrate_target_g",estimatedKey:"carbohydrate_estimated_g",unit:"g"},{label:"Fat",targetKey:"fat_target_g",estimatedKey:"fat_estimated_g",unit:"g"},{label:"Fiber",targetKey:"fiber_target_g",estimatedKey:"fiber_estimated_g",unit:"g"},{label:"Calcium",targetKey:"calcium_target_mg",estimatedKey:"calcium_estimated_mg",unit:"mg"},{label:"Iron",targetKey:"iron_target_mg",estimatedKey:"iron_estimated_mg",unit:"mg"},{label:"Vitamin C",targetKey:"vitamin_c_target_mg",estimatedKey:"vitamin_c_estimated_mg",unit:"mg"}];function Ye(e,n){return!e||e[n.targetKey]===void 0||e[n.estimatedKey]===void 0?null:`${n.label}: ${e[n.estimatedKey]} ${n.unit} (target ${e[n.targetKey]} ${n.unit})`}function oe(e){let n=String(e?.substitution_reason||"").trim(),i=String(e?.substitution||"").trim();return n?i&&n.toLowerCase().startsWith(i.toLowerCase())?n.slice(i.length).trim():n:""}function de(e,n=!0){return re.map(i=>{let t=(e.shopping_list||[]).filter(l=>l.role===i.role);if(!t.length)return"";let d=t.map(l=>{let p=[`- ${l.name}: ${l.quantity_display}`];if(n&&l.reason_short&&p.push(`  ${l.reason_short}`),n&&l.typical_item_cost!==null&&l.typical_item_cost!==void 0){let f=l.estimated_price_low!==null&&l.estimated_price_low!==void 0&&l.estimated_price_high!==null&&l.estimated_price_high!==void 0?` (range $${l.estimated_price_low}-$${l.estimated_price_high})`:"";p.push(`  Typical cost: $${l.typical_item_cost}${f}`)}return p.join(`
`)});return`${i.title}
${d.join(`
`)}`}).filter(Boolean).join(`

`)}function le(e){return Q.map(n=>{let i=e?.[n.key];if(!i?.store_id)return null;let t=i.distance_m!==void 0&&i.distance_m!==null?`, about ${Math.round(Number(i.distance_m))} m away`:"";return`- ${n.title}: ${i.store_name} (${i.category||"store"}${t})${i.note?` - ${i.note}`:""}`}).filter(Boolean)}function ce(e){if(!e?.shopping_list?.length)return"";let n=Number(e.days||1),i=String(e.shopping_mode||"balanced"),t=["Generic Grocery Plan",`Shopping window: ${n} ${n===1?"day":"days"}`,`Shopping mode: ${i}`,"",de(e,!1)];e.estimated_basket_cost!==void 0&&(t.push("",`Estimated typical basket cost: $${e.estimated_basket_cost}`),e.estimated_basket_cost_low!==void 0&&e.estimated_basket_cost_high!==void 0&&t.push(`Typical basket range: $${e.estimated_basket_cost_low}-$${e.estimated_basket_cost_high}`),e.price_adjustment_note&&t.push(e.price_adjustment_note),e.price_coverage_note&&t.push(e.price_coverage_note));let d=le(e);return d.length&&t.push("","Recommended store picks",...d),t.filter(Boolean).join(`
`)}function V(e){if(!e?.shopping_list?.length)return"";let n=Number(e.days||1),i=String(e.shopping_mode||"balanced"),t=e.nutrition_summary||{},d=se.map(f=>Ye(t,f)).filter(Boolean),l=le(e),p=["Generic Grocery Plan",`Shopping window: ${n} ${n===1?"day":"days"}`,`Shopping mode: ${i}`];return d.length&&p.push("","Key nutrition targets",...d),e.estimated_basket_cost!==void 0&&(p.push("",`Estimated typical basket cost: $${e.estimated_basket_cost}`),e.estimated_basket_cost_low!==void 0&&e.estimated_basket_cost_high!==void 0&&p.push(`Typical basket range: $${e.estimated_basket_cost_low}-$${e.estimated_basket_cost_high}`),e.price_adjustment_note&&p.push(e.price_adjustment_note),e.price_coverage_note&&p.push(e.price_coverage_note),e.basket_cost_note&&p.push(e.basket_cost_note),e.price_confidence_note&&p.push(e.price_confidence_note)),l.length&&p.push("","Recommended store picks",...l),p.push("","Shopping list",de(e,!0)),Array.isArray(e.assumptions)&&e.assumptions.length&&p.push("","Approximate guidance",...e.assumptions.map(f=>`- ${f}`)),p.filter(Boolean).join(`
`)}function ue(e,n,i={}){let{recommendation:t,recommendationStatus:d,recommendationError:l,isGeneratingRecommendations:p,hasRequestedRecommendation:f,exportNotice:s}=n;if(p){e.innerHTML=`
      ${x(d||"Generating recommendations...","info")}
      <div class="generic-empty">Building a generic shopping list from the nutrition targets and food preferences.</div>
    `;return}if(l){e.innerHTML=`
      ${x(l,"error")}
      <div class="generic-empty">The app could not build a shopping list for the current inputs. Adjust the targets or preferences and try again.</div>
    `;return}if(!f){e.innerHTML=`
      <div class="generic-empty">
        Build a shopping list to see recommended food categories, rough quantities, and a simple nutrition summary.
      </div>
    `;return}if(!t){e.innerHTML=`
      ${x(d||"No recommendations available.","info")}
      <div class="generic-empty">No shopping list could be generated from the current targets and preferences. Try lowering the targets or relaxing the filters.</div>
    `;return}let _=t.nutrition_summary,g=Number(t.days||n.days||1),B=String(t.shopping_mode||n.shopping_mode||"balanced"),E=!!n.developerMode,N=L(t.selected_candidate_source),we=Ve(t.selected_candidate_sources,N),k=t.hybrid_planner_execution||{},A=t.candidate_generation_debug||{},J=t.scoring_debug||{},c=t.candidate_comparison_debug||{},j=A.model_candidates_enabled??k.learned_candidate_generation_ran??!!n.enable_model_candidates,D=A.heuristic_candidate_count??k.heuristic_candidate_count,F=A.model_candidate_count??k.learned_candidate_count,G=A.fused_candidate_count??k.fused_candidate_count??t.candidate_count_considered,Ce=A.candidate_generator_backend||k.candidate_generator_backend||n.candidate_generator_backend||"auto",Le=t.scorer_backend||"unknown",Se=t.selected_candidate_id||"unknown",U=t.candidate_count_considered??k.candidates_ranked_count??G,Ne=E&&!!(t.candidate_generation_debug||t.scoring_debug||t.candidate_comparison_debug),Ae=c.diagnosis_text||ze(j,N),X=c.selected_vs_best_heuristic||null,M=c.selected_candidate_contrast||{},xe=M.best_heuristic_candidate_shopping_food_ids||c.best_heuristic_candidate_shopping_food_ids||[],Ee=M.best_model_candidate_shopping_food_ids||c.best_model_candidate_shopping_food_ids||[],Z=Array.isArray(J.candidates)?J.candidates.slice(0,5).map(r=>`
        <tr>
          <td class="generic-debug-code">${o(r.candidate_id)}</td>
          <td>${o(T(r.source))}</td>
          <td>${o(w(r.model_score))}</td>
          <td>${o(r.generator_score??"n/a")}</td>
          <td class="generic-debug-code">${o(R(r.shopping_food_ids))}</td>
          <td>${r.selected?"Yes":"No"}</td>
          <td>${o(r.selection_reason_summary||"")}</td>
        </tr>
      `).join(""):"",Me=D!==void 0&&F!==void 0&&G!==void 0?`${D} heuristic + ${F} model -> ${G} fused`:U!==void 0?`${U} total candidates ranked`:"Not available",Re=k.pipeline_mode==="full_hybrid"?`${D??"?"} heuristic candidates + ${F??"?"} learned candidates were fused, reranked by the trained scorer, and matched against nearby store fits automatically.`:"This request used the heuristic-only planner path.",Te=Ne?`
      <div class="generic-list-item" style="margin-top: 1rem">
        <div class="generic-inline-group">
          <h3>Planner Debug / Model Participation</h3>
          <span class="generic-badge">Debug summary</span>
        </div>
        <div class="generic-debug-list">
          <div><strong>Selected candidate source:</strong> ${o(T(N))}</div>
          <div><strong>Selected candidate sources:</strong> ${o(we.map(T).join(" + "))}</div>
          <div><strong>Candidate pool:</strong> ${o(Me)}</div>
          <div><strong>Candidates ranked:</strong> ${o(U??"Not available")}</div>
          <div><strong>Model candidates enabled:</strong> ${o(j?"Yes":"No")}</div>
          <div><strong>Candidate generator backend:</strong> ${o(Ce||"Not used")}</div>
          <div><strong>Scorer backend:</strong> ${o(Le)}</div>
          <div><strong>Selected candidate ID:</strong> ${o(Se)}</div>
          <div><strong>Best heuristic candidate:</strong> ${o(c.best_heuristic_candidate_id||"Not available")} ${c.best_heuristic_candidate_score!==null&&c.best_heuristic_candidate_score!==void 0?`<span>(score ${o(w(c.best_heuristic_candidate_score))})</span>`:""}</div>
          <div><strong>Best model candidate:</strong> ${o(c.best_model_candidate_id||"Not available")} ${c.best_model_candidate_score!==null&&c.best_model_candidate_score!==void 0?`<span>(score ${o(w(c.best_model_candidate_score))})</span>`:""}</div>
          <div><strong>Model vs heuristic score gap:</strong> ${o(c.best_model_vs_best_heuristic_score_gap!==null&&c.best_model_vs_best_heuristic_score_gap!==void 0?w(c.best_model_vs_best_heuristic_score_gap):"Not available")}</div>
          <div><strong>Model candidates merged:</strong> ${o(c.model_candidates_merged_count!==null&&c.model_candidates_merged_count!==void 0?`${c.model_candidates_merged_count}`:"Not available")}</div>
          <div><strong>Materially different model candidates surviving fusion:</strong> ${o(c.materially_different_model_candidates_surviving_after_fusion!==null&&c.materially_different_model_candidates_surviving_after_fusion!==void 0?`${c.materially_different_model_candidates_surviving_after_fusion}`:"Not available")}</div>
          <div><strong>Average heuristic/model overlap:</strong> ${o(c.average_heuristic_model_overlap_jaccard!==null&&c.average_heuristic_model_overlap_jaccard!==void 0?w(c.average_heuristic_model_overlap_jaccard):"Not available")}</div>
          <div><strong>Best materially different model candidate:</strong> ${o(c.best_materially_different_model_candidate_id||"Not available")} ${c.best_materially_different_model_candidate_score!==null&&c.best_materially_different_model_candidate_score!==void 0?`<span>(score ${o(w(c.best_materially_different_model_candidate_score))})</span>`:""}</div>
          <div><strong>Winner vs best materially different model gap:</strong> ${o(c.best_materially_different_model_candidate_score_gap_to_selected!==null&&c.best_materially_different_model_candidate_score_gap_to_selected!==void 0?w(c.best_materially_different_model_candidate_score_gap_to_selected):"Not available")}</div>
          <div><strong>Why that model alternative lost:</strong> ${o(c.best_materially_different_model_candidate_loss_reason||"Not available")}</div>
          <div><strong>Similarity diagnosis:</strong> ${o(c.model_candidates_mostly_near_duplicates?"Model candidates were mostly near-duplicates.":j?"Model candidates introduced materially different baskets.":"Model path disabled.")}</div>
          <div><strong>Selection outcome:</strong> ${o(Ae)}</div>
        </div>
        <div class="generic-debug-list" style="margin-top: 1rem">
          <div><strong>Selected vs heuristic baseline:</strong> ${o(M.difference_summary_vs_best_heuristic||c.selected_candidate_difference_summary||"Not available")}</div>
          <div><strong>Materially different from heuristic baseline:</strong> ${o(X?X.materially_different?"Yes":"No":"Not available")}</div>
          <div><strong>Selected candidate shopping_food_ids:</strong> <span class="generic-debug-code">${o(R(M.selected_candidate_shopping_food_ids||c.selected_candidate_shopping_food_ids||[]))}</span></div>
          <div><strong>Best heuristic candidate shopping_food_ids:</strong> <span class="generic-debug-code">${o(R(xe))}</span></div>
          <div><strong>Best model candidate shopping_food_ids:</strong> <span class="generic-debug-code">${o(R(Ee))}</span></div>
        </div>
        ${Z?`<details class="generic-advanced" style="margin-top: 1rem">
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
                  <tbody>${Z}</tbody>
                </table>
              </details>`:""}
      </div>
    `:"",Pe=0,Be=r=>`
        <div class="generic-list-item">
          <div class="generic-list-header">
            <div>
              <strong>${Pe+=1}. ${o(r.name)}</strong>
              <div class="generic-muted">Suggested buy: ${o(r.quantity_display)}</div>
            </div>
            <span class="generic-badge">${o(qe(r.role))}</span>
          </div>
          <div class="generic-muted" style="margin-top: 0.5rem"><strong>${o(r.reason_short||"")}</strong></div>
          <div class="generic-muted" style="margin-top: 0.25rem">${o(r.why_selected||r.reason)}</div>
          ${r.value_reason_short?`<div class="generic-muted" style="margin-top: 0.25rem"><strong>Value note:</strong> ${o(r.value_reason_short)}${r.price_efficiency_note?` <span>${o(r.price_efficiency_note)}</span>`:""}</div>`:""}
          <div class="generic-muted" style="margin-top: 0.25rem">${o(r.reason)}</div>
          ${r.substitution?`<div class="generic-muted" style="margin-top: 0.35rem"><strong>Swap option:</strong> ${o(r.substitution)}${oe(r)?` <span>${o(oe(r))}</span>`:""}</div>`:""}
          <div class="generic-list-meta">
            <span><strong>Protein:</strong> ${o(r.estimated_protein_g)} g</span>
            <span><strong>Calories:</strong> ${o(r.estimated_calories_kcal)} kcal</span>
          </div>
          ${r.estimated_item_cost!==null&&r.estimated_item_cost!==void 0?`<div class="generic-muted" style="margin-top: 0.35rem"><strong>Typical regional price:</strong> $${o(r.typical_unit_price??r.estimated_unit_price)} ${o(r.price_unit_display||"")}; typical item cost about <strong>$${o(r.typical_item_cost??r.estimated_item_cost)}</strong>${r.estimated_price_low!==null&&r.estimated_price_low!==void 0&&r.estimated_price_high!==null&&r.estimated_price_high!==void 0?` <span>(regional range $${o(r.estimated_price_low)}-$${o(r.estimated_price_high)})</span>`:""}.</div>`:""}
        </div>
      `,je=re.map(r=>{let h=t.shopping_list.filter(Ge=>Ge.role===r.role);return h.length?`
      <div class="generic-list-item" style="margin-top: 1rem">
        <div class="generic-inline-group">
          <h3>${o(r.title)}</h3>
          <span class="generic-badge">${h.length} ${h.length===1?"item":"items"}</span>
        </div>
        <div class="generic-list">
          ${h.map(Be).join("")}
        </div>
      </div>
    `:""}).join(""),De=(t.assumptions||[]).map(r=>`<li>${o(r)}</li>`).join(""),O=(t.pantry_notes||[]).map(r=>`<li>${o(r)}</li>`).join(""),I=(t.scaling_notes||[]).map(r=>`<li>${o(r)}</li>`).join(""),K=(t.warnings||[]).map(r=>`<li>${o(r)}</li>`).join(""),q=(t.split_notes||[]).map(r=>`<li>${o(r)}</li>`).join(""),H=(t.realism_notes||[]).map(r=>`<li>${o(r)}</li>`).join(""),ee=[t.estimated_basket_cost_low!==void 0&&t.estimated_basket_cost_high!==void 0?`<p class="generic-muted"><strong>Typical basket range:</strong> about $${o(t.estimated_basket_cost_low)}-$${o(t.estimated_basket_cost_high)}</p>`:"",t.price_area_name?`<p class="generic-muted" style="margin-top: 0.5rem"><strong>Regional price area:</strong> ${o(t.price_area_name)} (${o(t.price_area_code||"")})</p>`:"",t.price_source_note?`<p class="generic-muted" style="margin-top: 0.5rem">${o(t.price_source_note)}</p>`:"",t.price_adjustment_note?`<p class="generic-muted" style="margin-top: 0.5rem">${o(t.price_adjustment_note)}</p>`:"",t.basket_cost_note?`<p class="generic-muted" style="margin-top: 0.5rem">${o(t.basket_cost_note)}</p>`:"",t.price_confidence_note?`<p class="generic-muted" style="margin-top: 0.5rem">${o(t.price_confidence_note)}</p>`:""].filter(Boolean).join(""),ne=(t.store_fit_notes||[]).map(r=>`
        <div class="generic-list-item" style="margin-top: 0.75rem">
          <div class="generic-inline-group">
            <h3>${o(r.store_name||"Nearby store")}</h3>
            <span class="generic-badge">${o(r.fit_label||"Store fit")}</span>
          </div>
          <div class="generic-muted"><strong>${o(r.category||"store")}</strong>${r.distance_m!==void 0&&r.distance_m!==null?` \u2022 about ${o(Number(r.distance_m).toFixed(0))} m away`:""}</div>
          <div class="generic-muted" style="margin-top: 0.25rem">${o(r.note||"")}</div>
        </div>
      `).join(""),te=Q.map(r=>{let h=t[r.key];return h?.store_id?`
        <div class="generic-list-item" style="margin-top: 0.75rem">
          <div class="generic-inline-group">
            <h3>${o(r.title)}</h3>
            <span class="generic-badge">${o(h.store_name||"Nearby store")}</span>
          </div>
          <div class="generic-muted"><strong>${o(h.category||"store")}</strong>${h.distance_m!==void 0&&h.distance_m!==null?` \u2022 about ${o(Number(h.distance_m).toFixed(0))} m away`:""}</div>
          <div class="generic-muted" style="margin-top: 0.25rem">${o(h.note||"")}</div>
        </div>
      `:""}).join(""),ie=(t.meal_suggestions||[]).map(r=>`
        <div class="generic-list-item" style="margin-top: 0.75rem">
          <div class="generic-inline-group">
            <h3>${o(r.title||"Meal idea")}</h3>
            <span class="generic-badge">${o(String(r.meal_type||"idea").replaceAll("_"," "))}</span>
          </div>
          <div class="generic-muted"><strong>${o((r.items||[]).join(", "))}</strong></div>
          ${r.description?`<div class="generic-muted" style="margin-top: 0.25rem">${o(r.description)}</div>`:""}
        </div>
      `).join(""),Fe=se.filter(r=>_?.[r.targetKey]!==void 0&&_?.[r.estimatedKey]!==void 0).map(r=>`
        <div class="generic-summary-metric">
          <div class="generic-muted">${o(r.label)}</div>
          <strong>${o(_[r.estimatedKey])} ${o(r.unit)}</strong>
          <div>Target: ${o(_[r.targetKey])} ${o(r.unit)}</div>
          <div class="generic-muted">Difference: ${o(Ke(_[r.estimatedKey],_[r.targetKey],r.unit))}</div>
        </div>
      `).join("");e.innerHTML=`
    ${x(d||"Recommendation ready.","success")}
    ${x(s?.message,s?.kind)}
    <div class="generic-list-item" style="margin-bottom: 1rem">
      <div class="generic-inline-group">
        <h3>Shopping List</h3>
        <div class="generic-badge-group">
          <span class="generic-badge ${o(Qe(N))}">
            ${o(He(N))}
          </span>
          <span class="generic-badge">Suggested shopping list for ${g} ${g===1?"day":"days"}</span>
        </div>
      </div>
      <p class="generic-muted">Daily nutrition goals stay the same. Quantities below are scaled for the selected shopping window in <strong>${o(B)}</strong> shopping mode.</p>
      <p class="generic-muted" style="margin-top: 0.5rem"><strong>Planning pipeline:</strong> ${o(Re)}</p>
      <div class="generic-actions" style="margin-top: 0.75rem">
        <button type="button" data-export-action="copy-shopping">Copy shopping list</button>
        <button type="button" data-export-action="copy-plan">Copy full plan</button>
        <button type="button" data-export-action="download-plan">Download as text</button>
      </div>
      ${t.estimated_basket_cost!==void 0?`<p class="generic-muted" style="margin-top: 0.5rem"><strong>Estimated typical basket cost:</strong> about $${o(t.estimated_basket_cost)}.</p>`:""}
    </div>
    <div class="generic-list">
      ${je||'<div class="generic-empty">Your pantry already covers the suggested basket for this plan. Review the notes below if you still want a small top-up shop.</div>'}
    </div>
    ${Te}
    ${te?`<div class="generic-list-item" style="margin-top: 1rem">
            <div class="generic-inline-group">
              <h3>Recommended store picks for this list</h3>
              <span class="generic-badge">${Q.filter(r=>t[r.key]?.store_id).length} picks</span>
            </div>
            <p class="generic-muted">These are quick store-type recommendations based on the basket style and nearby store mix. They do not reflect exact inventory.</p>
            ${te}
          </div>`:""}
    ${ne?`<div class="generic-list-item" style="margin-top: 1rem">
            <div class="generic-inline-group">
              <h3>Best nearby store fits for this list</h3>
              <span class="generic-badge">${(t.store_fit_notes||[]).length} suggestions</span>
            </div>
            <p class="generic-muted">These are coarse store-fit suggestions based on the basket style, shopping mode, and nearby store type. They do not reflect exact inventory.</p>
            ${ne}
          </div>`:""}
    ${ie?`<div class="generic-list-item" style="margin-top: 1rem">
            <div class="generic-inline-group">
              <h3>Example ways to use this list</h3>
              <span class="generic-badge">${(t.meal_suggestions||[]).length} ideas</span>
            </div>
            <p class="generic-muted">These are lightweight examples built from the same recommended items. They are not a full meal plan.</p>
            ${ie}
          </div>`:""}
    ${I||K||q||H||O?`<div class="generic-list-item" style="margin-top: 1rem">
            <div class="generic-inline-group">
              <h3>Shopping Notes</h3>
              <span class="generic-badge">${t.adjusted_by_split?"Scaling and realism guidance":"Scaling guidance"}</span>
            </div>
            ${I?`<p class="generic-muted"><strong>Scaling notes</strong></p><ul class="generic-assumptions">${I}</ul>`:""}
            ${q?`<p class="generic-muted" style="margin-top: 0.75rem"><strong>Split notes</strong></p><ul class="generic-assumptions">${q}</ul>`:""}
            ${H?`<p class="generic-muted" style="margin-top: 0.75rem"><strong>Realism notes</strong></p><ul class="generic-assumptions">${H}</ul>`:""}
            ${O?`<p class="generic-muted" style="margin-top: 0.75rem"><strong>Pantry adjustments</strong></p><ul class="generic-assumptions">${O}</ul>`:""}
            ${K?`<p class="generic-muted" style="margin-top: 0.75rem"><strong>Warnings</strong></p><ul class="generic-assumptions">${K}</ul>`:""}
          </div>`:""}
    <div class="generic-list-item" style="margin-top: 1rem">
      <div class="generic-inline-group">
        <h3>Nutrition Summary</h3>
        <span class="generic-badge">${g===1?"Daily total":`${g}-day total`}</span>
      </div>
      <div class="generic-summary-grid">
        ${Fe}
      </div>
    </div>
    <div class="generic-list-item" style="margin-top: 1rem">
      <div class="generic-inline-group">
        <h3>Approximate Guidance</h3>
        <span class="generic-badge">Demo-friendly estimate</span>
      </div>
      <p class="generic-muted">Use this list as a practical starting point, not as exact store inventory or guaranteed product availability.</p>
      <ul class="generic-assumptions">${De}</ul>
    </div>
    ${ee?`<div class="generic-list-item" style="margin-top: 1rem">
            <div class="generic-inline-group">
              <h3>Pricing notes</h3>
              <span class="generic-badge">Typical regional estimate</span>
            </div>
            ${ee}
          </div>`:""}
  `,e.querySelector('[data-export-action="copy-shopping"]')?.addEventListener("click",()=>{i.onCopyShoppingList?.()}),e.querySelector('[data-export-action="copy-plan"]')?.addEventListener("click",()=>{i.onCopyFullPlan?.()}),e.querySelector('[data-export-action="download-plan"]')?.addEventListener("click",()=>{i.onDownloadPlan?.()})}function C(e){return String(e??"").replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;").replaceAll('"',"&quot;").replaceAll("'","&#39;")}function P(e,n){return e?`<div class="generic-notice ${C(n||"info")}">${C(e)}</div>`:""}function pe(e,n){let{stores:i,storeStatus:t,storeError:d,isLookingUpStores:l,hasLookedUpStores:p}=n;if(l){e.innerHTML=`
      ${P(t||"Looking up nearby supermarkets...","info")}
      <div class="generic-empty">Searching for nearby supermarkets. This usually takes a moment.</div>
    `;return}if(d){e.innerHTML=`
      ${P(d,"error")}
      <div class="generic-empty">Check the location fields and try the store lookup again.</div>
    `;return}if(!p){e.innerHTML=`
      <div class="generic-empty">
        Start with a location or preset, then use <strong>Find Nearby Supermarkets</strong> to load stores for the area.
      </div>
    `;return}if(!i.length){e.innerHTML=`
      ${P(t||"No nearby stores found.","info")}
      <div class="generic-empty">No supermarkets were found within the current search radius. Try increasing the radius or switching to a different location.</div>
    `;return}let f=i.map((s,_)=>`
        <div class="generic-list-item">
          <div class="generic-list-header">
            <div>
              <strong>${_+1}. ${C(s.name)}</strong>
              <div class="generic-muted">${C(s.address)}</div>
            </div>
            <span class="generic-badge">${Math.round(s.distance_m)} m</span>
          </div>
          <div class="generic-list-meta">
            <span><strong>Category:</strong> ${C(s.category)}</span>
            <span><strong>Coordinates:</strong> ${C(s.lat)}, ${C(s.lon)}</span>
          </div>
        </div>
      `).join("");e.innerHTML=`
    ${P(t||`Loaded ${i.length} nearby store${i.length===1?"":"s"}.`,"success")}
    <div class="generic-list">${f}</div>
  `}var We="https://nominatim.openstreetmap.org/search",Je=6,Xe=4,Ze="random_forest",en=new Set(["auto","logistic_regression","random_forest","hist_gradient_boosting"]),me=[{id:"muscle_gain",label:"Muscle Gain",values:{locationQuery:"Mountain View, CA",lat:"",lon:"",radius_m:"8000",store_limit:"5",days:"1",shopping_mode:"balanced",protein:"170",calories:"2800",carbohydrate:"330",fat:"85",fiber:"35",calcium:"",iron:"",vitamin_c:"",vegetarian:!1,dairy_free:!1,vegan:!1,low_prep:!1,budget_friendly:!1,meal_style:"any"},notice:'Loaded the muscle gain preset for "Mountain View, CA".'},{id:"fat_loss",label:"Fat Loss",values:{locationQuery:"Mountain View, CA",lat:"",lon:"",radius_m:"8000",store_limit:"5",days:"1",shopping_mode:"balanced",protein:"150",calories:"1800",carbohydrate:"160",fat:"55",fiber:"30",calcium:"",iron:"",vitamin_c:"",vegetarian:!1,dairy_free:!1,vegan:!1,low_prep:!1,budget_friendly:!1,meal_style:"any"},notice:'Loaded the fat loss preset for "Mountain View, CA".'},{id:"maintenance",label:"Maintenance",values:{locationQuery:"Mountain View, CA",lat:"",lon:"",radius_m:"8000",store_limit:"5",days:"1",shopping_mode:"balanced",protein:"130",calories:"2200",carbohydrate:"240",fat:"70",fiber:"30",calcium:"",iron:"",vitamin_c:"",vegetarian:!1,dairy_free:!1,vegan:!1,low_prep:!1,budget_friendly:!1,meal_style:"any"},notice:'Loaded the maintenance preset for "Mountain View, CA".'},{id:"high_protein_vegetarian",label:"High-Protein Vegetarian",values:{locationQuery:"Mountain View, CA",lat:"",lon:"",radius_m:"8000",store_limit:"5",days:"1",shopping_mode:"balanced",protein:"140",calories:"2100",carbohydrate:"220",fat:"70",fiber:"32",calcium:"",iron:"18",vitamin_c:"",vegetarian:!0,dairy_free:!1,vegan:!1,low_prep:!1,budget_friendly:!1,meal_style:"any"},notice:'Loaded the high-protein vegetarian preset for "Mountain View, CA".'},{id:"budget_friendly_healthy",label:"Budget-Friendly Healthy",values:{locationQuery:"Mountain View, CA",lat:"",lon:"",radius_m:"8000",store_limit:"5",days:"1",shopping_mode:"balanced",protein:"120",calories:"2100",carbohydrate:"230",fat:"65",fiber:"35",calcium:"",iron:"",vitamin_c:"",vegetarian:!1,dairy_free:!1,vegan:!1,low_prep:!1,budget_friendly:!0,meal_style:"any"},notice:'Loaded the budget-friendly healthy preset for "Mountain View, CA".'}];function _e(){return typeof window>"u"?{}:window.GENERIC_APP_CONFIG||{}}function Y(){return!!_e().developerMode}function fe(){let e=_e().hybridPlannerDefaults||{};return{candidateCount:Number(e.candidateCount||Je),modelCandidateCount:Number(e.modelCandidateCount||Xe),candidateGeneratorBackend:String(e.candidateGeneratorBackend||Ze)}}function nn(){let e=fe();return{developerMode:Y(),enable_model_candidates:!0,model_candidate_count:String(e.modelCandidateCount),candidate_generator_backend:e.candidateGeneratorBackend,debug_candidate_generation:!1,debug_scorer:!1,candidate_count:String(e.candidateCount)}}var a={locationQuery:"Mountain View, CA",lat:"",lon:"",radius_m:"8000",store_limit:"5",days:"1",shopping_mode:"balanced",protein:"130",calories:"2200",carbohydrate:"240",fat:"70",fiber:"30",calcium:"",iron:"",vitamin_c:"",vegetarian:!1,dairy_free:!1,vegan:!1,low_prep:!1,budget_friendly:!1,meal_style:"any",...nn(),pantry_items:[],stores:[],storesLookupContext:null,recommendation:null,errors:{},formNotice:null,storeStatus:"",storeError:"",recommendationStatus:"",recommendationError:"",exportNotice:null,isLookingUpStores:!1,isGeneratingRecommendations:!1,isLocating:!1,isResolvingAddress:!1,hasLookedUpStores:!1,hasRequestedRecommendation:!1,presets:me};function b(e){if(e==null||String(e).trim()==="")return null;let n=Number(e);return Number.isFinite(n)?n:null}function z(e){if(e==="true")return!0;if(e==="false")return!1}function ge(e){if(e==null||String(e).trim()==="")return;let n=Number.parseInt(String(e),10);if(!(!Number.isFinite(n)||n<=0))return n}function tn(e,n){if(e==null||String(e).trim()==="")return;let i=String(e).trim().toLowerCase();return n.has(i)?i:void 0}function be(){return typeof window>"u"||!window.location||typeof window.location.search!="string"?"":window.location.search}function ye(e=be()){if(!Y())return{};let n=new URLSearchParams(e||""),i={},t=z(n.get("enable_model_candidates"));t!==void 0&&(i.enable_model_candidates=t);let d=ge(n.get("model_candidate_count"));d!==void 0&&(i.model_candidate_count=d);let l=tn(n.get("candidate_generator_backend"),en);l!==void 0&&(i.candidate_generator_backend=l);let p=z(n.get("debug_candidate_generation"));p!==void 0&&(i.debug_candidate_generation=p);let f=z(n.get("debug_scorer"));f!==void 0&&(i.debug_scorer=f);let s=ge(n.get("candidate_count"));s!==void 0&&(i.candidate_count=s);let _=String(n.get("scorer_model_path")||"").trim();_&&(i.scorer_model_path=_);let g=String(n.get("candidate_generator_model_path")||"").trim();return g&&(i.candidate_generator_model_path=g),i}Object.assign(a,ye());function he(e){let n=b(e.lat),i=b(e.lon);return n!==null&&i!==null&&n>=-90&&n<=90&&i>=-180&&i<=180}function W(e){let n=b(e.lat),i=b(e.lon),t=b(e.radius_m);return n===null||i===null||t===null?null:{lat:Number(n.toFixed(6)),lon:Number(i.toFixed(6)),radius_m:Math.round(t)}}function an(e,n){return!e||!n?!1:e.lat===n.lat&&e.lon===n.lon&&e.radius_m===n.radius_m}function on(e,n=be()){let i=b(e.radius_m),t={location:{lat:Number(e.lat),lon:Number(e.lon)},targets:{protein:Number(e.protein),energy_fibre_kcal:Number(e.calories)},preferences:{vegetarian:e.vegetarian,dairy_free:e.dairy_free,vegan:e.vegan,low_prep:e.low_prep,budget_friendly:e.budget_friendly,meal_style:e.meal_style||"any"},pantry_items:Array.isArray(e.pantry_items)?e.pantry_items:[],store_limit:Number(e.store_limit),days:Number(e.days||1),shopping_mode:e.shopping_mode||"balanced"};i!==null&&(t.radius_m=i);let d=W(e);e.hasLookedUpStores&&Array.isArray(e.stores)&&e.stores.length&&e.stores.length>=Number(e.store_limit)&&an(e.storesLookupContext,d)&&(t.stores=e.stores.slice(0,Number(e.store_limit)));for(let[l,p]of Object.entries({carbohydrate:b(e.carbohydrate),fat:b(e.fat),fiber:b(e.fiber),calcium:b(e.calcium),iron:b(e.iron),vitamin_c:b(e.vitamin_c)}))p!==null&&(t.targets[l]=p);if(Y()){let l=fe();t.enable_model_candidates=!!e.enable_model_candidates,t.model_candidate_count=Number(e.model_candidate_count||l.modelCandidateCount),t.candidate_generator_backend=e.candidate_generator_backend||l.candidateGeneratorBackend,t.debug_candidate_generation=!!e.debug_candidate_generation,t.debug_scorer=!!e.debug_scorer,t.candidate_count=Number(e.candidate_count||l.candidateCount),Object.assign(t,ye(n))}return t}function rn(e,n="recommend"){let i={},t=String(e.locationQuery||"").trim(),d=b(e.lat),l=b(e.lon),p=b(e.protein),f=b(e.calories),s=[["carbohydrate","carbohydrate"],["fat","fat"],["fiber","fiber"],["calcium","calcium"],["iron","iron"],["vitamin_c","vitamin C"]],_=he(e);if(!t&&!_&&(i.locationQuery="Enter a city or address, or provide coordinates in Advanced location settings."),t||((d===null||d<-90||d>90)&&(i.lat="Enter a latitude between -90 and 90."),(l===null||l<-180||l>180)&&(i.lon="Enter a longitude between -180 and 180.")),n==="recommend"){(p===null||p<=0)&&(i.protein="Enter a protein target greater than 0."),(f===null||f<=0)&&(i.calories="Enter a calorie target greater than 0.");for(let[g,B]of s){let E=b(e[g]);E!==null&&E<=0&&(i[g]=`Enter a ${B} target greater than 0, or leave it blank.`)}}return i}async function sn(e,n=fetch){let i=String(e||"").trim();if(!i)throw new Error("Enter a city or address first.");let t=new URLSearchParams({q:i,format:"jsonv2",limit:"1"}),d=await n(`${We}?${t.toString()}`,{headers:{Accept:"application/json"}});if(!d.ok)throw new Error("Location search failed. Please try again.");let l=await d.json();if(!Array.isArray(l)||l.length===0)throw new Error("Could not find that location. Please try a different city or address.");let p=l[0];return{lat:Number(p.lat).toFixed(6),lon:Number(p.lon).toFixed(6),displayName:p.display_name||i}}function v(e,n="info"){a.formNotice=e?{message:e,kind:n}:null}function S(e,n="info"){a.exportNotice=e?{message:e,kind:n}:null}function dn(e){Object.assign(a,e);for(let n of Object.keys(e))a.errors[n]&&delete a.errors[n]}function ve(e){let n=rn(a,e);return a.errors=n,Object.keys(n).length?(v("Fix the highlighted fields before continuing.","error"),y(),!1):(a.formNotice?.kind==="error"&&v(null),!0)}function ln(){a.stores=[],a.storesLookupContext=null,a.recommendation=null,a.storeStatus="",a.storeError="",a.recommendationStatus="",a.recommendationError="",a.exportNotice=null,a.hasLookedUpStores=!1,a.hasRequestedRecommendation=!1}async function $e(){let e=String(a.locationQuery||"").trim();if(!e)return he(a);a.isResolvingAddress=!0,v(`Finding coordinates for "${e}"...`,"info"),y();try{let n=await sn(e);return a.lat=n.lat,a.lon=n.lon,delete a.errors.locationQuery,delete a.errors.lat,delete a.errors.lon,v(`Using coordinates for "${e}". Advanced settings were updated automatically.`,"success"),!0}catch(n){return a.errors.locationQuery=n.message||"Could not find that location. Please try a different city or address.",v(a.errors.locationQuery,"error"),y(),!1}finally{a.isResolvingAddress=!1}}async function cn(){if(!ve("stores")||!await $e())return;a.hasLookedUpStores=!0,a.storeError="",a.storeStatus="Looking up nearby supermarkets...",a.isLookingUpStores=!0,y();let n=new URLSearchParams({lat:a.lat,lon:a.lon,radius_m:a.radius_m,limit:a.store_limit});try{let i=await fetch(`/api/stores/nearby?${n.toString()}`),t=await i.json();if(!i.ok)throw new Error(t.error||"Store lookup failed.");a.stores=t.stores||[],a.storesLookupContext=W(a),a.storeStatus=a.stores.length?`Loaded ${a.stores.length} nearby supermarket${a.stores.length===1?"":"s"}.`:"No nearby supermarkets found for this location.",a.recommendation&&!a.recommendation.stores?.length&&(a.recommendation.stores=a.stores)}catch(i){a.stores=[],a.storeError=i.message||"Store lookup failed.",a.storeStatus=""}finally{a.isLookingUpStores=!1}y()}async function un(){if(!ve("recommend")||!await $e())return;a.hasRequestedRecommendation=!0,a.recommendation=null,a.recommendationError="",a.recommendationStatus="Generating recommendations...",a.exportNotice=null,a.isGeneratingRecommendations=!0,y();let n=W(a),i=on(a);try{let t=await fetch("/api/recommendations/generic",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(i)}),d=await t.json();if(!t.ok)throw new Error(d.error||"Recommendation request failed.");a.recommendation=d,a.stores=d.stores||[],a.storesLookupContext=a.stores.length?n:null,a.hasLookedUpStores=!0,a.storeError="",a.storeStatus=a.stores.length?`Loaded ${a.stores.length} nearby supermarket${a.stores.length===1?"":"s"}.`:"No nearby supermarkets found for this location.",a.recommendationStatus=d.shopping_list?.length?"Shopping list ready.":"No shopping list was generated for the current inputs."}catch(t){a.recommendation=null,a.recommendationError=t.message||"Recommendation request failed.",a.recommendationStatus=""}finally{a.isGeneratingRecommendations=!1}y()}function pn(){if(!navigator.geolocation){v("Browser geolocation is not available here. Enter coordinates in Advanced location settings.","error"),y();return}a.isLocating=!0,v("Requesting your current location...","info"),y(),navigator.geolocation.getCurrentPosition(e=>{a.isLocating=!1,a.locationQuery="",a.lat=e.coords.latitude.toFixed(6),a.lon=e.coords.longitude.toFixed(6),delete a.errors.locationQuery,delete a.errors.lat,delete a.errors.lon,v("Location loaded from your browser. Advanced settings were updated automatically.","success"),y()},e=>{a.isLocating=!1,v({1:"Location access was denied. Enter a city, address, or coordinates manually.",2:"Your location could not be determined. Enter a city, address, or coordinates manually.",3:"Location lookup timed out. Enter a city, address, or coordinates manually."}[e.code]||"Location lookup failed. Enter a city, address, or coordinates manually.","error"),y()},{enableHighAccuracy:!1,timeout:1e4,maximumAge:3e5})}function gn(e){let n=me.find(i=>i.id===e);n&&(Object.assign(a,n.values),a.pantry_items=Array.isArray(n.values?.pantry_items)?[...n.values.pantry_items]:[],a.errors={},ln(),v(n.notice,"success"),y())}async function ke(e){if(!e)throw new Error("There is no recommendation to export yet.");if(navigator.clipboard?.writeText){await navigator.clipboard.writeText(e);return}let n=document.createElement("textarea");n.value=e,n.setAttribute("readonly","readonly"),n.style.position="fixed",n.style.opacity="0",document.body.appendChild(n),n.select();let i=document.execCommand("copy");if(document.body.removeChild(n),!i)throw new Error("Copy is not available in this browser.")}function mn(e,n){if(!n)throw new Error("There is no recommendation to export yet.");let i=new Blob([n],{type:"text/plain;charset=utf-8"}),t=URL.createObjectURL(i),d=document.createElement("a");d.href=t,d.download=e,document.body.appendChild(d),d.click(),document.body.removeChild(d),URL.revokeObjectURL(t)}async function _n(){try{await ke(ce(a.recommendation)),S("Copied the grouped shopping list.","success")}catch(e){S(e.message||"Could not copy the shopping list.","error")}y()}async function fn(){try{await ke(V(a.recommendation)),S("Copied the full grocery plan.","success")}catch(e){S(e.message||"Could not copy the full plan.","error")}y()}function bn(){try{mn("generic-grocery-plan.txt",V(a.recommendation)),S("Downloaded the grocery plan as text.","success")}catch(e){S(e.message||"Could not download the grocery plan.","error")}y()}function y(){ae(document.getElementById("generic-form"),a,{onChange:dn,onLookupStores:cn,onRecommend:un,onUseMyLocation:pn,onApplyPreset:gn}),pe(document.getElementById("generic-stores"),a),ue(document.getElementById("generic-results"),a,{onCopyShoppingList:_n,onCopyFullPlan:fn,onDownloadPlan:bn})}typeof document<"u"&&y();export{on as buildRecommendationPayload,sn as geocodeAddress,ye as getScorerQueryOverrides,z as parseBooleanParam,ge as parsePositiveIntParam,rn as validateFormState};
