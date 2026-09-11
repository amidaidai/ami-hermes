---
name: writing-plans
description: Use when you have a spec or requirements for a multi-step task and need to write an actionable implementation plan before touching code. Output a structured plan with ordered tasks, dependencies, and verification steps. (superpowers version)
---

# Writing Plans

Write an actionable implementation plan when given a spec, requirements, or multi-step task.

## When to Use This Skill

When the user provides:
- A specification document
- A PRD or feature request
- A set of requirements to implement
- A multi-step task that needs decomposition
- Any situation where coding should happen after planning

## Plan Structure

### 1. Overview
One paragraph explaining what needs to be built, at a high level, in plain language.

### 2. Prerequisites
- Any setup required before starting
- Dependencies that must be installed
- Environment variables or configuration needed

### 3. Ordered Task List

Each task should include:

- **Task name**: Clear, actionable name (e.g., "Create database schema for users table")
- **Files to modify**: Exact file paths
- **Implementation details**: What code to write, what logic to implement
- **Edge cases**: What edge cases to handle
- **Dependencies**: Tasks that must be completed before this one
- **Verification**: How to check this task is done (e.g., "Run `pytest tests/test_users.py`")

### 4. Verification Steps
- How to verify the overall implementation works
- Test commands with expected outcomes
- Manual verification if applicable

### 5. Risks and Mitigations
- Known challenges
- Fallback approaches if something doesn't work

## Plan Quality Checklist

- [ ] Each task is independently testable
- [ ] Tasks are ordered by dependency, not convenience
- [ ] All file paths are exact (not relative guesses)
- [ ] Edge cases are explicitly called out
- [ ] Verification steps are executable commands, not vague descriptions
- [ ] The plan can be handed to another developer/agent and executed without clarification

## Output Format

Save the plan to `.hermes/plans/` with a descriptive filename (e.g., `add-user-auth-plan.md`). Present the plan to the user for approval before executing.
