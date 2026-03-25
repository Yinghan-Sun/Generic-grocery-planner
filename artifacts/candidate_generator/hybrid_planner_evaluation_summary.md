# Hybrid Planner Evaluation

## System Summary

| system | scenarios | avg scorer | avg protein gap g | avg calorie gap kcal | avg cost | avg time ms | model selected rate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| heuristic_only | 113 | 8.271185 | 27.660177 | 1025.2 | 33.243894 | 60.785991 | 0.0 |
| hybrid_best | 113 | 8.614313 | 26.533628 | 996.113274 | 32.329027 | 385.25077 | 0.628319 |
| hybrid_hist_gradient_boosting | 113 | 8.612209 | 26.359292 | 1020.183186 | 32.303274 | 125.059841 | 0.654867 |
| hybrid_logistic_regression | 113 | 8.800139 | 28.613274 | 1025.457522 | 32.650088 | 86.875708 | 0.539823 |
| hybrid_random_forest | 113 | 8.614313 | 26.533628 | 996.113274 | 32.329027 | 368.430177 | 0.628319 |

## Baseline Comparison

| system | beat rate | avg scorer delta | avg protein gap delta g | avg calorie gap delta kcal | avg cost delta | model candidate win rate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| hybrid_best | 0.292035 | 0.343128 | 1.126549 | 29.086726 | -0.914867 | 0.628319 |
| hybrid_logistic_regression | 0.300885 | 0.528954 | -0.953097 | -0.257522 | -0.593805 | 0.539823 |
| hybrid_random_forest | 0.292035 | 0.343128 | 1.126549 | 29.086726 | -0.914867 | 0.628319 |
| hybrid_hist_gradient_boosting | 0.283186 | 0.341024 | 1.300885 | 5.016814 | -0.940619 | 0.654867 |
