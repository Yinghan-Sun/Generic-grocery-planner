# Project Understanding Summary

- **Stack:** Python Flask app with a vanilla JavaScript frontend, DuckDB data store, trained scoring artifacts, and public regional price plus nearby-store data inputs.
- **App purpose:** Convert a nutrition goal into a practical generic grocery basket, a rough regional cost estimate, and nearby store suggestions.
- **Inferred audience:** Busy non-expert grocery shoppers, especially students or young professionals balancing health, convenience, and budget.
- **Key inputs:** Location, calorie and protein targets, optional macro and micronutrient targets, shopping window, shopping mode, dietary flags, and pantry items.
- **Key outputs:** Suggested shopping list by food role, nutrition-versus-target summary, typical basket cost and range, nearby stores, recommended store picks, meal ideas, and guidance notes.
- **Main tradeoff or objective:** The planner appears to balance closeness to nutrition targets with practicality, price-awareness, preference fit, and store convenience rather than solving a single exact minimum-cost problem.
- **Evidence-based uncertainties:**
  - The deployed app hides most debug metadata, so exact learned-model weights are inferred from code paths and output behavior rather than directly visible in production.
  - Store-fit suggestions appear to use store type, brand, and distance, but not exact live inventory.
  - Long-window quantity scaling is heuristic; observed 7-day fresh and bulk scenarios drift from the target because perishables are intentionally softened.
