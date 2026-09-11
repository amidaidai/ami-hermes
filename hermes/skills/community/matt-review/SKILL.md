---
name: matt-review
description: Review changes since a fixed point along Standards and Spec axes. Use when user asks to review code changes, review a branch, or check if implementation matches specification and standards.
---

# Matt Review

Review changes since a fixed point along two axes: Standards and Spec.

## The Two Axes

### Standards Axis
Is the code well-written according to language and framework conventions?
- Follows established patterns
- Uses idiomatic language features
- Consistent naming and structure
- Proper error handling
- Adequate testing

### Spec Axis
Does the implementation match the specification or requirements?
- All specified features implemented
- Edge cases handled per spec
- Input/output contracts maintained
- API surface matches documentation
- No scope creep (unrequested features)

## Review Process

1. **Establish the baseline**: What commit or state are we comparing against?
2. **Gather the spec**: What requirements exist (PRD, issue, user story, comments)?
3. **Review along Standards axis**: Code quality, patterns, conventions
4. **Review along Spec axis**: Requirements vs. implementation mapping
5. **Cross-check**: Anything that passes one axis but fails the other

## Scoring

For each finding, note which axis it affects:
- **Standards issue**: "This uses a callback instead of async/await" (S)
- **Spec issue**: "This feature was not in the requirements" (Sp)
- **Both**: "This error case from the spec is not handled AND the code is unreadable" (S+Sp)

## Output Format

A review document with:
- What was reviewed (baseline, changeset size)
- Key findings grouped by axis
- Prioritized action items
- Questions for the author
