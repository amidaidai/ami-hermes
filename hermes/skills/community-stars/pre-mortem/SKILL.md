---
name: pre-mortem
description: Pre-mortem risk analysis on plans and launches — imagine the project has failed and work backwards to identify risks. Use when user asks to do a pre-mortem, risk assessment before launch, or failure mode analysis on a plan.
---

# Pre-Mortem Analysis

Imagine the project has failed spectacularly. Then work backwards to identify what went wrong — before you commit resources.

## Methodology

### Step 1: Frame the Exercise
State: "We are 6 months in the future. Our project/launch/initiative has failed completely. Goals were not met, customers are unhappy, and stakeholders are disappointed."

### Step 2: Individual Brainstorming (Silent)
Each participant writes down every possible reason for failure. Rules:
- No filtering or judging ideas
- Quantity over quality
- Include both obvious and far-fetched causes
- Be specific: "The API provider went down for 3 days" not "tech problems"

### Step 3: Group and Categorize
Organize failure modes into categories:

- **Market risk**: Competition, demand didn't materialize, timing wrong
- **Technical risk**: Architecture didn't scale, bugs, integration failures
- **Team risk**: Key person left, skill gaps, communication breakdowns
- **Process risk**: Delays, scope creep, decision paralysis
- **Financial risk**: Budget overrun, funding fell through, revenue shortfall
- **External risk**: Regulatory, economic, supply chain, force majeure

### Step 4: Score Each Risk

| Risk | Likelihood (1-5) | Impact (1-5) | Score | Mitigation |
|------|------------------|--------------|-------|------------|
| ...  | 4                | 5            | 20    | ...        |

### Step 5: Create Action Plan
For the top 5-10 risks by score, define:
- **Prevention**: What can we do now to prevent this?
- **Detection**: What leading indicator would warn us?
- **Contingency**: If it happens, what's our response?

## Output Format

A pre-mortem report with:
1. The premortem frame
2. Risk catalogue (all failure modes by category)
3. Scored risk matrix (top risks highlighted)
4. Action plan with owners and deadlines
5. Trigger log: Clear conditions that should escalate to leadership
