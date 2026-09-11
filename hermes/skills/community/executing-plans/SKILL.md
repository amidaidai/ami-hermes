---
name: executing-plans
category: community
description: Execute written implementation plans with review checkpoints.
---

# Executing Plans — Implementation with Review Checkpoints

Execute written implementation plans systematically, with built-in review checkpoints at each stage to ensure progress aligns with the plan.

## When to use

- You have a written implementation plan (spec, PRD, or task list)
- You need to execute the plan step by step with verification at each stage
- You want to avoid scope creep or deviation from the agreed approach
- Multiple steps need to be completed in a specific order

## Workflow

### Step 1: Load the plan

Read the implementation plan:

```markdown
Implementation Plan: [Name]
1. [Step 1 description]
2. [Step 2 description]
3. [Step 3 description]
...
```

Confirm with the user what the plan is and that execution should begin.

### Step 2: Execute step by step

For each step:

1. **Do the work** — make the code change, write the file, run the command
2. **Verify** — check that the result matches what the plan expects
3. **Report** — state what was done and what the next step is
4. **Wait for confirmation** — let the user confirm before proceeding to the next step (unless directed otherwise)

### Step 3: Review checkpoints

At each checkpoint, ask:

- Does the result match the plan's expectation for this step?
- Are there any new files, changes, or outputs to show?
- Should the plan be adjusted based on what was learned?

### Step 4: Final verification

After all steps are complete:

- [ ] Every planned step has been executed
- [ ] Tests pass
- [ ] Edge cases from the plan are handled
- [ ] Documentation is updated if required by the plan
- [ ] No unplanned changes were introduced

### Step 5: Summary

Provide a completion summary:

```
## Execution Complete

Plan: [Name]
Steps completed: [N/M]
Files modified/created: [list]
Test results: [pass/fail summary]
Unplanned discoveries: [if any]
```

## Plan Format Compatibility

Works with any plan format:

- **PRD-style** — features, acceptance criteria, milestones
- **Task-list style** — numbered steps with dependencies
- **Agile-style** — user stories with acceptance criteria
- **Spike plan** — investigation questions, expected outputs

## Principles

1. **One step at a time** — complete and verify before moving on
2. **Show your work** — report what files were changed and what results were observed
3. **Flag deviations** — if something doesn't work as expected, pause and adjust the plan
4. **Don't skip verification** — running tests is part of the plan, not optional
5. **Document surprises** — anything unexpected becomes valuable context

## Pitfalls

- Don't combine multiple plan steps into one action — each step needs its own verification
- Don't assume the plan is perfect — real work often reveals missing steps or incorrect assumptions
- Don't skip reporting intermediate results — the user needs to see progress
- If a step fails, stop and report rather than trying to work around it silently

## Verification

At the end, re-read the original plan and confirm every line item is addressed. If any item was modified during execution, explain why.
