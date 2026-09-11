---
name: matt-prototype
description: Build throwaway prototypes to validate ideas before committing to full implementation. Use when user wants to test an idea, explore a concept, or validate a design with minimal investment.
---

# Matt Prototype

Build throwaway prototypes to validate ideas before committing to full implementation.

## Prototyping Principles

### 1. Define the Question
Before writing any code, state clearly:
- What hypothesis are we testing?
- What's the minimum evidence needed to decide?
- What would "validated" look like?

### 2. Scope Aggressively
- What can we cut? (Error handling, edge cases, polish, auth, tests)
- What can we fake? (Mock data, hard-coded responses, manual input)
- What can we reuse? (Existing components, libraries, templates)

### 3. Timebox
Set a hard limit:
- 🧪 **Quick test**: 15-30 minutes (one feature, one interaction)
- 🧪 **Concept validation**: 1-2 hours (core flow end-to-end)
- 🧪 **Feasibility study**: 3-4 hours (architecture test)

### 4. Build Just Enough
- Wire up the core flow only
- Use stub/mock for everything else
- Hard-code data when it saves time
- Skip: tests, docs, error states, loading states, optimization

### 5. Evaluate and Decide
After the timebox, answer:
- Did we validate the hypothesis? Yes/No/Inconclusive
- What did we learn?
- Should we build the real version? If yes, what changed from our original assumptions?

### 6. Throw Away (or Nearly)
Prototypes are disposable. If moving to production:
- Start fresh with the learnings
- Don't refactor the prototype into production code
- Do document what was learned and why decisions were made

## Output Format

1. **Hypothesis statement**: What are we testing?
2. **Prototype scope**: What's in and out
3. **Build notes**: Key decisions made during building
4. **Results**: Does the concept work? What was learned?
5. **Recommendation**: Go / No-Go / Iterate
