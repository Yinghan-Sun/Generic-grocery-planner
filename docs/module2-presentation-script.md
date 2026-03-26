# Module 2 Presentation Script

## 3-5 Minute Talk Track

### 1. Problem
Our original Generic Grocery Planner was deterministic and explainable, but it only searched the candidate space through heuristic beams. That made it stable, but it also meant the planner could miss strong alternative baskets.

### 2. Why Heuristic-Only Was Not Enough
For Module 2, the goal was not just to add a model, but to define a complete modeling package: objective, methods, alternatives, tuning, evaluation, and limitations. A pure heuristic planner could not demonstrate a real training pipeline or a meaningful learned search component.

### 3. Why We Chose the Hybrid Planner Pipeline
We chose a hybrid planner pipeline. The deterministic planner stays in place as the baseline. A learned local candidate generator proposes extra structured basket seeds. Then one fair scorer ranks both heuristic and learned candidates together. This kept the system local-only, explainable, and backward compatible.

### 4. What A Normal User Experiences
A normal user now clicks Recommend once. The app does not ask them to choose learned versus heuristic paths, candidate-generator backends, candidate counts, scorer paths, or debug modes. The backend always runs the full hybrid stack internally.

### 5. What the Learned Candidate Generator Does
The learned model predicts promising foods for planner roles like protein anchor, carb base, produce, and calorie booster using structured local features. At runtime, it proposes candidate baskets, and those candidates are fused with heuristic ones before scoring.

### 6. What the Fair Scorer Does
We also had to reduce heuristic bias in ranking. The fair scorer was retrained so that materially different but still practical baskets are treated more fairly instead of always preferring the heuristic-looking option. That was important because otherwise the learned generator could produce valid alternatives that still never win.

### 7. Final Results
With the frozen final algorithm `hybrid_planner_generalized_v5_main`, the hybrid planner improved scorer outcome on 4 of the 5 main presets and selected a model or hybrid winner on 4 presets. The current model wins are muscle_gain, maintenance, high_protein_vegetarian, budget_friendly_healthy.

### 8. Why the Generalized Final Version Matters
Earlier iterations included narrower fixes for specific failure modes. The final version is better because it uses generalized complementarity, generalized seed-preserving materialization, and the fair scorer instead of accumulating more preset-specific patches. The ablation study shows those shared components matter: removing complementarity or structured materialization each drops one of the current model wins.

### 9. Robustness
We also tested the frozen algorithm on 30 local perturbation scenarios such as target changes, multi-day shopping, and an alternate location. The hybrid planner pipeline still improved over heuristic+scorer on 16 cases, and we found 0 brittle cases in this sweep.

### 10. Limitation
The remaining limitation is `fat_loss`, which still selects the heuristic basket. The gap to the best materially different model candidate is 0.441382, so the model path is competitive there, but not yet best. That suggests a real limitation in learned candidate quality for that goal rather than missing routing or missing model participation.

### 11. Future Work
A principled next step would be a richer learned pair or set proposal model, especially for low-calorie, high-satiety combinations, rather than more preset-specific tuning. That would keep the system faithful to the general algorithmic direction established in the final hybrid planner version.
