---
name: prioritize-features
description: Feature prioritization by impact, effort, risk, and strategic alignment — using RICE, MoSCoW, value-effort, and Kano models. Use when user asks to prioritize features, rank backlog items, or decide what to build first.
---

# Feature Prioritization

Prioritize features using multiple frameworks for a well-rounded decision.

## Prioritization Frameworks

### RICE Score
- **Reach**: How many users will this impact? (users per time period)
- **Impact**: How much will this move the needle? (1-5 scale)
- **Confidence**: How sure are we? (50%, 80%, 100%)
- **Effort**: How many person-months?

**RICE Score = (Reach × Impact × Confidence) / Effort**

### MoSCoW Method
- **M**ust-have: Critical for launch or current sprint
- **S**hould-have: Important but not critical
- **C**ould-have: Nice-to-have, lower impact
- **W**on't-have: Explicitly out of scope for now

### Value vs. Effort Matrix

```
              Effort
              Low        High
      +-----------------------+
High  | Quick Wins    | Major  |
      | (Do first!)   | Projects|
Value |               |        |
      +-----------------------+
Low   | Fill-Ins     | Money  |
      | (If capacity) | Pits   |
      +-----------------------+
```

### Kano Model
- **Basic needs**: Expected features (hygiene factors)
- **Performance features**: More = better (linear satisfaction)
- **Delighters**: Unexpected features (non-linear satisfaction)
- **Indifferent**: No impact on satisfaction

## Decision Criteria Matrix

Score each feature (1-10) on:

| Criterion | Weight | Rationale |
|-----------|--------|-----------|
| Strategic alignment | 25% | Does this support our OKRs? |
| User impact | 25% | How much value for users? |
| Business value | 20% | Revenue, retention, conversion |
| Effort | 15% | Development time and complexity |
| Risk | 10% | Technical or market uncertainty |
| Dependencies | 5% | Blocks or is blocked by others |

## Output Format

A prioritized feature list with:
1. Ranked list with scores and framework used
2. Justification for top/bottom items
3. "Now / Next / Later" time horizon grouping
4. Dependencies and sequencing notes
