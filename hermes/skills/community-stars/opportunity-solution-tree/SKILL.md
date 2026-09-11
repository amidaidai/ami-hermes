---
name: opportunity-solution-tree
description: Build Opportunity Solution Trees (OST) for product discovery — linking desired outcomes to solutions via opportunities. Use when user asks to create an OST, opportunity solution tree, product discovery tree, or map outcomes to solutions.
---

# Opportunity Solution Tree

Build an Opportunity Solution Tree (OST) for product discovery following Teresa Torres' methodology.

## The OST Structure

```
Desired Outcome
  ├── Opportunity 1
  │   ├── Solution 1a → Assumption
  │   ├── Solution 1b → Assumption
  │   └── Solution 1c → Assumption
  ├── Opportunity 2
  │   ├── Solution 2a → Assumption
  │   └── Solution 2b → Assumption
  └── Opportunity 3
      └── Solution 3a → Assumption
```

## Methodology

### 1. Define the Desired Outcome
Start with a measurable business outcome (not a feature): e.g., "Increase weekly active users by 20%"

### 2. Identify Opportunities
Opportunities are customer needs, pains, desires, or goals that, if addressed, move the desired outcome. They come from:
- User research (interviews, surveys, usability tests)
- Data analysis (funnel drops, churn segments)
- Support tickets and feedback
- Competitive analysis

**Format each opportunity as**: "Our users need/want/struggle with..."

### 3. Generate Solutions
For each opportunity, brainstorm potential solutions. Solutions are specific features or changes. Include the key assumption behind each solution (what must be true for it to work).

### 4. Prioritize for Testing
Rank opportunities by:
- **Impact**: How much this opportunity matters to the outcome
- **Confidence**: How sure we are the opportunity is real
- **Ease**: How easy to test/validate

## Output Format

Present the tree as a markdown hierarchy (indented lists). For each opportunity, include:
- Description with user evidence (quotes, data)
- Impact score (High/Medium/Low)
- Number of solutions generated

For each solution, include:
- Name and brief description
- Key assumption to test
- Suggested test method (prototype, A/B test, interview, etc.)
