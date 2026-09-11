---
name: cohort-analysis
description: Cohort analysis with retention curves, feature adoption trends, and churn pattern identification. Use when user asks to perform cohort analysis, analyze retention, track user behavior over time, or understand customer lifecycle.
---

# Cohort Analysis

Analyze user behavior patterns across cohorts to identify retention trends, feature adoption, and churn signals.

## What Cohort Analysis Reveals

- **Retention curves**: Do users stick around over time?
- **Feature adoption**: Do specific features improve retention?
- **Seasonal effects**: Do certain months have worse retention?
- **Product changes**: Did the last release improve retention?
- **Channel quality**: Do different acquisition channels retain differently?

## Analysis Approach

### 1. Define Cohorts
Common cohort grouping methods:
- **Acquisition date**: Users who signed up in the same week/month
- **Behavioral**: Users who completed a key action (first purchase, invited a friend)
- **Channel**: Where users came from (organic, paid, referral)
- **Segment**: Free vs. paid, desktop vs. mobile, region

### 2. Define the Retention Metric
- **Classic retention**: % of users who return in period N
- **Rolling retention**: % of users who ever return (less noisy)
- **Unbounded retention**: Days active per period
- **Revenue retention**: NRGR or GRR

### 3. Build the Cohort Grid

```
Cohort    | Period 1 | Period 2 | Period 3 | Period 4 | Period 5 |
----------|----------|----------|----------|----------|----------|
Jan 2024  | 100%     | 45%      | 38%      | 32%      | 30%      |
Feb 2024  | 100%     | 48%      | 40%      | 35%      |          |
Mar 2024  | 100%     | 52%      | 42%      |          |          |
Apr 2024  | 100%     | 50%      |          |          |          |
```

### 4. Analyze Patterns
Look for:
- **Flattening curve**: Product-market fit signal (retention plateaus > 0)
- **Sloping curve**: Users try and leave (fixation problem)
- **Cohort improvement**: Later cohorts do better (product is improving)
- **Drop cliffs**: Specific period where retention drops sharply
- **Seasonal dips**: Same period each year

### 5. Feature Adoption Analysis
For each feature, analyze:
- % of new users who try the feature in week 1
- % of retained users who use the feature regularly
- Correlation: Do feature users have better retention?

## Output Format

Cohort grid table + retention curve (interpretation) + actionable recommendations:

1. **Key finding**: One sentence summary
2. **Cohort trends**: Directional changes over time
3. **Segment differences**: Best/worst performing segments
4. **Recommendations**: 3-5 actions based on data
