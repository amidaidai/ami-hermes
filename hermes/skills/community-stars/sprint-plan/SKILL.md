---
name: sprint-plan
description: Sprint planning with capacity, story selection, dependency mapping, and risk assessment. Use when user asks to plan a sprint, create a sprint backlog, estimate sprint capacity, or organize development work.
---

# Sprint Plan Generator

Plan a development sprint with capacity estimation, story selection, dependency mapping, and risk identification.

## Planning Process

### 1. Calculate Team Capacity
- Team size × sprint days × availability factor (meetings, PTO, support)
- Deduct known non-sprint work (ceremonies, bug fixes, code reviews)
- Result: Total available person-days

### 2. Prioritize Work
Use the following criteria to select stories:
- **Business value**: ROI or customer impact
- **Dependency order**: Stories that unblock others
- **Risk reduction**: High-uncertainty items early
- **Team fit**: Match stories to available skills

### 3. Estimate Effort
- Use story points (Fibonacci: 1, 2, 3, 5, 8, 13, 21) or time estimates
- Compare against historical velocity
- Flag stories > 8 points for splitting
- Note estimation confidence

### 4. Map Dependencies
Identify and document:
- Story-to-story dependencies (this blocks that)
- Cross-team dependencies (API teams, design, QA)
- External dependencies (vendors, customers, data sources)

### 5. Risk Assessment
For each story, note:
- **Complexity**: Low / Medium / High
- **Clarity**: Well-defined / Needs discovery / Ambiguous
- **Novelty**: Similar to past work / New territory

### 6. Define Sprint Goal
One sentence that captures the sprint's purpose: "By end of sprint, users can [accomplish outcome]."

## Output Format

| Item | Points | Owner | Dependencies | Risk | Notes |
|------|--------|-------|-------------|------|-------|
| ...  | 5      | Alice | #42 (API)   | Med  | ...   |

Include: Sprint goal, total committed points, capacity buffer, and a "stretch goal" list.
