# Presentation Package

## 1. Project Understanding Summary
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

## 2. Presentation Outline

### Slide 1 - Title + value proposition
- Introduce the dashboard as a grocery-planning tool rather than a technical model.
- State the value proposition in one sentence and show the app home screen.

### Slide 2 - Who this is for
- Define a specific non-technical user: busy health-conscious shoppers, especially students and young professionals.
- Explain what they care about: easy choices, nearby stores, realistic costs, and goals they can trust.

### Slide 3 - The real-world problem
- Frame the gap between abstract nutrition advice and a real grocery trip.
- Show why local availability, cost, and convenience all matter at once.

### Slide 4 - What the tool does
- Explain the flow from inputs to basket generation to recommendation output.
- Translate the optimization logic into plain English: the app tries multiple baskets and picks a balanced one.

### Slide 5 - How a user interacts with it
- Show preset buttons, target fields, pantry choices, and nearby store lookup.
- Emphasize the one-click flow and user-friendly layout for non-specialists.

### Slide 6 - What changes when decisions change
- Compare live outputs when the user changes only one preference at a time.
- Show how cost, items, and store suggestions shift when the goal changes.

### Slide 7 - Key insight example
- Walk through one concrete recommendation and explain what the model is saying in plain English.
- Highlight the nutrition summary, price estimate, and store picks as decision support.

### Slide 8 - Limitations + improvements
- State the current limits clearly and tie them to observed behavior.
- Explain how user feedback and better data could improve the tool.

### Slide 9 - Stakeholders + ethics
- Discuss who benefits, who may be underserved, and where transparency matters.
- Treat health, accessibility, and fairness as design concerns, not side notes.

### Slide 10 - Takeaways + future use
- Close on why the tool matters and why this audience could use it.
- End with a roadmap for trust, adoption, and next-step improvement.

### Slide 11 - Demo backup
- Provide a backup screenshot walkthrough in case a live demo fails.

## 3. Full Transcript

### Slide 1 - Title + Value Proposition
Today I am presenting a grocery-planning dashboard that takes a nutrition goal and turns it into a practical shopping trip. Instead of asking a user to translate abstract advice like eat more protein or stay on budget into actual groceries, the tool gives them a starting basket, a rough price estimate, and nearby store suggestions. That makes the project easy to explain to a non-technical audience because its value is visible right away: it helps someone move from a goal to an action. As we go, I am going to focus less on code and more on the user decision this tool supports.

### Slide 2 - Who This Is For
The clearest audience for this tool is a busy, health-conscious shopper who is not a nutrition expert. I think the best example is a student or young professional who wants to shop in a way that supports muscle gain, fat loss, maintenance, or a healthier budget, but does not want to build a meal plan from scratch. This audience needs three things at once: simple choices, realistic prices, and recommendations that feel local and doable. So the dashboard is not trying to teach nutrition theory. It is trying to reduce friction and help a person make a better grocery decision in a few minutes.

### Slide 3 - The Real-World Problem
The real-world problem is that eating for a goal sounds simple until someone has to stand in a store and decide what to buy. Nutrition advice is usually abstract, grocery prices vary by place, and convenience matters just as much as protein or calories. A shopper might know they want to eat healthier, but they still have to answer practical questions like what basket gets me close to my goal, how much will it cost, and where should I go nearby. This project matters because it turns that messy decision into a clearer comparison instead of leaving the user to guess.

### Slide 4 - What The Tool Does
At a high level, the tool asks for a location, a daily target, a few food preferences, and any pantry items the user already has. Then it builds several possible grocery baskets and chooses one that best balances nutrition fit, practicality, and price-awareness. In plain English, the app is not hunting for one mathematically perfect meal plan. It is trying a few sensible baskets and selecting the one that seems most useful for a real shopper. The result is a shopping list, a nutrition summary, a typical basket cost, and store suggestions that help the user act on the recommendation.

### Slide 5 - How A User Interacts With It
This slide shows why the tool is accessible for a non-specialist audience. The user can start with a preset like muscle gain or budget-friendly healthy, keep the default city, and click a button to load nearby supermarkets. They can also fine-tune calories, protein, shopping window, dietary filters, and pantry items without needing any technical knowledge. That matters for grading because the dashboard is not just producing an answer. It is inviting exploration in a way that feels familiar, like filling out a guided shopping form rather than operating a model.

### Slide 6 - What Changes When Decisions Change
Here is the most important interaction story. I kept the same Mountain View location and the same 2,200 calorie, 130 gram protein target, and then changed one preference at a time. The base plan costs about eight dollars and uses familiar staples like chicken, bread, spinach, and carrots. When I turn on the budget preference, the basket drops closer to five and a half dollars and shifts toward lentils, eggs, rice, and cabbage. When I turn on low-prep, the tool leans more toward convenience foods like rotisserie chicken. So the model is making tradeoffs visible. Different choices really do change cost, basket composition, and even the suggested store fit.

### Slide 7 - Key Recommendation Example
This is a concrete example of the tool speaking in plain English. For the base scenario, the dashboard recommends two protein anchors, one carb base, two produce items, and a calorie booster. It estimates about 138 grams of protein against a 130 gram target, about 2,160 calories against a 2,200 calorie target, and a typical basket cost of about eight and a half dollars. The useful part is not the exact number. The useful part is the explanation: buy a small set of versatile staples that get you close to the goal, then use the nearby store suggestions to make the trip easier. That is decision support, not just prediction.

### Slide 8 - Limitations + How To Improve
The tool is useful, but it is important to state its limits clearly. First, it works with generic foods, not exact store inventory or exact product brands. Second, the prices are regional estimates rather than store quotes. Third, the long-window logic is approximate. In the live seven-day scenarios, fresh and bulk modes both drift away from the target because perishables are intentionally softened. The path forward is clear: add real inventory and pricing feeds, let users set a hard budget cap, support more dietary constraints, and use feedback from real shoppers to improve the confidence and realism of each recommendation.

### Slide 9 - Stakeholders + Ethics
Several groups are affected by this tool. Shoppers benefit from clearer planning, stores may benefit from more intentional trips, and nutrition educators could use it as a teaching aid. But there are also ethical concerns. Users with allergies, medical conditions, or very limited access to stores may be underserved if the tool is treated as more certain than it really is. That is why transparency matters. The dashboard should keep telling users when a result is approximate, when price data is regional, and when store recommendations are based on fit rather than live inventory. Used responsibly, the tool supports healthier choices; used carelessly, it could overstate confidence.

### Slide 10 - Takeaways + Future Use
The big takeaway is that this project makes nutrition goals more actionable. It gives a non-expert user a simple way to explore tradeoffs among health targets, convenience, and budget, and it does that with outputs they can immediately recognize: a shopping list, a cost estimate, and store suggestions. I would trust it as a practical starting point because it shows its reasoning in user-friendly terms and it does not pretend to be exact inventory or medical advice. The next step would be to test it with real student or young professional shoppers, collect feedback, and adapt the interface and rules around what those users say they actually need.

### Slide 11 - Demo Backup
This backup slide is here in case a live demo fails. It lets me walk through the same recommendation screen, point to the shopping list, the nutrition summary, the price notes, and the store suggestions, and still keep the presentation understandable.

## 4. Rubric Coverage Matrix

| Rubric item | Where it is covered (slide number) | How it is covered |
| --- | --- | --- |
| A1. Clearly identify the target audience | 2 | Slide 2 names busy non-expert shoppers, especially students and young professionals. |
| A2. Show understanding of the audience's needs and interests | 2, 3 | Slides 2 and 3 connect the audience to ease, affordability, local relevance, and decision stress. |
| A3. Provide a concise, high-level summary for a non-specialist audience | 1, 4 | Slide 1 gives the one-sentence value proposition and Slide 4 explains the workflow without jargon. |
| A4. Communicate key insights accessibly | 4, 6, 7 | These slides translate the planning logic and scenario changes into plain English. |
| A5. Show relevance of the model/tool to audience goals and challenges | 2, 3, 10 | The tool is tied to real grocery goals like health, budget, and convenience. |
| B6. Show that the tool is accessible and user-friendly for a non-specialist audience | 5 | Slide 5 uses real screenshots to show presets, simple controls, and one-click flow. |
| B7. Show how different choices affect outcomes | 6 | Slide 6 compares live outputs after changing preferences. |
| B8. Use the tool to engage the user in meaningful exploration and clearly explain model decisions | 5, 6, 7 | The deck shows interaction, scenario exploration, and plain-English interpretation of the recommendation. |
| C9. Clearly communicate limitations | 8 | Slide 8 lists concrete limits tied to observed app behavior. |
| C10. Discuss strategies for overcoming limitations | 8 | Slide 8 proposes better data, budget constraints, dietary support, and feedback loops. |
| C11. Discuss how the tool could be adapted based on audience feedback | 8, 10 | The presentation suggests piloting with real users and adapting the interface from feedback. |
| D12. Show real-world relevance | 3, 10 | Slides 3 and 10 connect the tool to actual grocery decisions. |
| D13. Analyze impact on different stakeholders | 9 | Slide 9 covers shoppers, stores, nutrition educators, and underserved users. |
| D14. Address ethical implications and societal impact thoughtfully | 8, 9 | Slides 8 and 9 address confidence, accessibility, health safety, and transparency. |
| E15. Ensure clarity and logical structure | 1-10 | The deck follows a problem-to-solution-to-evaluation arc with clear headings and visual grouping. |
| E16. Make the presentation engaging and appropriate for 8-10 minutes | 1-10 | Ten main slides support a paced 8-10 minute talk, with Slide 11 as backup. |
| E17. Demonstrate preparation and a strong understanding of the audience | 2-10 | Audience framing, live evidence, and concrete scenario comparisons show preparation. |
| F18. Use creative presentation choices that improve understanding | 4, 6, 7 | Workflow graphics, scenario cards, and screenshot-led explanation make the model easier to grasp. |
| F19. Show visible effort in making the model understandable and relevant | 5, 6, 11 | Real screenshots, observed outputs, and a demo backup slide signal strong effort. |

## 5. Files Created

- `presentation/indeng243_diet_planner_presentation.pptx`
- `presentation/indeng243_diet_planner_presentation.pdf`
- `presentation/indeng243_project_understanding.md`
- `presentation/indeng243_presentation_outline.md`
- `presentation/indeng243_presentation_transcript.md`
- `presentation/indeng243_rubric_coverage_matrix.md`
- `presentation/indeng243_presentation_package.md`
