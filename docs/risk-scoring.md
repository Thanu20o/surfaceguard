# Risk scoring

Risk score = technical severity × 0.40 + exposure × 0.25 + confidence × 0.20 + business impact × 0.15. Factors are values from 0 to 100, and the result is rounded to one decimal place. This is an illustrative, project-specific prioritization score, not an industry standard or probability of compromise.

The current scanner uses the maximum active finding severity as its technical-severity input (Critical 95, High 75, Medium 55, Low 30, Informational 10; no active finding 0). An asset with an observed IP receives exposure 80, otherwise 0. Confidence is 80 when an active finding exists and 40 otherwise. Business impact defaults to 50 for every asset. Weights and input values are returned with each asset's saved score for auditability.

Levels: 0–19 Informational, 20–39 Low, 40–59 Medium, 60–79 High, 80–100 Critical. Multiple findings do not sum severity; the maximum is used to avoid artificially inflating a score. Business impact configuration per asset is not implemented yet.