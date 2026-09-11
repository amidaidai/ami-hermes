---
name: ab-test-analysis
description: A/B test analysis with statistical significance testing and actionable recommendations. Use when user asks to analyze A/B test results, evaluate experiment data, or determine if a test result is statistically significant.
---

# A/B Test Analysis

Analyze A/B test results with proper statistical methodology and clear recommendations.

## Analysis Process

### 1. Validate the Test Design
Before interpreting results, check:
- **Sample size**: Was the test powered to detect the observed effect?
- **Duration**: Did it run long enough (at least 1-2 full business cycles)?
- **Peeking**: Was the result checked repeatedly? (If so, adjust for multiple looks)
- **Segmentation**: Were segments balanced (mobile/web, new/returning)?
- **Novelty effect**: Did behavior change because it was new?

### 2. Calculate Key Metrics

For each variant (control & treatment):
- **Conversion rate**: Conversions / Visitors
- **Relative lift**: (Treatment rate - Control rate) / Control rate
- **Absolute lift**: Treatment rate - Control rate

### 3. Statistical Significance

**Z-test for proportions:**
- Calculate z-score: z = (p₁ - p₀) / √(p·(1-p)·(1/n₀ + 1/n₁))
- Where p = (x₀ + x₁) / (n₀ + n₁)
- Compare to critical value (1.96 for 95% confidence)

**Bayesian approach (recommended):**
- Use Beta distribution for prior (typically Beta(1,1) uninformative)
- Posterior = Beta(α₀ + conversions, β₀ + non-conversions)
- P(Treatment > Control) = probability treatment is better
- Report credible interval (95% likely true value in this range)

### 4. Check for Gotchas

- **Simpson's Paradox**: Overall result reverses when segmented
- **Multiple comparison problem**: Running many metrics inflates false positives
- **Regression to the mean**: Extreme values tend to normalize
- **Primacy/Novelty effects**: Early results may not persist
- **Sample ratio mismatch**: Actual vs. expected traffic split differs

### 5. Decision Framework

| Scenario | Action |
|----------|--------|
| Significant improvement | Ship it (but monitor for 1-2 weeks post-launch) |
| Significant degradation | Kill it (don't ship) |
| Flat / Inconclusive | Consider iteration, more power, or stop |
| Borderline | Run longer, Bayesian analysis, or launch with guardrails |

## Output Format

A concise experiment report:
1. **Executive summary**: Ship / Kill / Iterate decision
2. **Results table**: Lift, significance, confidence intervals
3. **Segmentation**: Any interesting segment differences
4. **Recommended action**: Specific next steps
