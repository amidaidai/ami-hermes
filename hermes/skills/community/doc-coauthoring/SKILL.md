---
name: doc-coauthoring
category: community
description: Co-author documentation with structured workflow for proposals, specs, decision docs.
---

# Doc Co-Authoring — Structured Documentation Workflow

Co-author documentation with a structured workflow for proposals, specifications, and decision documents. Designed for effective human-AI collaboration on technical and product docs.

## When to use

- You need to write a technical proposal, spec, or decision document
- You're collaborating with an AI to draft, review, and refine documentation
- You want a repeatable process for doc creation with defined stages
- You need RFC-style documents for team decision-making

## Workflow Stages

### Stage 1: Briefing

The human provides context:

```
## Doc Brief

**Type**: [Proposal / Spec / Decision Doc / Tutorial / API Reference]
**Audience**: [Engineers / PMs / Stakeholders / External]
**Goal**: [What should the reader know or decide after reading?]
**Key points to cover**: [3-5 bullet points]
**Existing references**: [Links to relevant docs, PRDs, tickets]
**Tone**: [Formal / Conversational / Technical / Executive]
```

### Stage 2: Outline (AI generates → Human approves)

```
# [Title]

## Problem Statement
## Proposed Solution
## Alternatives Considered
## Recommendations
## Next Steps
## Appendix
```

The human reviews and adjusts the outline before the AI writes.

### Stage 3: Draft (AI writes full content)

The AI writes the first draft following the approved outline, section by section. Each section starts with a clear thesis statement.

### Stage 4: Review (Human reviews → AI refines)

Human provides structured feedback:

```
## Review Feedback

### Section: [name]
- **Clarity**: [Good / Needs work / Unclear]
- **Completeness**: [Covers / Missing: ...]
- **Accuracy**: [Correct / Needs correction: ...]
- **Style**: [Matches tone / Needs adjustment]
- **Specific edits**: [Line-by-line suggestions]
```

### Stage 5: Polish (AI applies feedback)

AI incorporates all feedback and produces the final version.

### Stage 6: Final review (Human signs off)

Human does a final read-through and approves or requests minor changes.

## Document Types

### Proposal Template

```markdown
# Proposal: [Title]

**Status**: [Draft / Review / Approved / Rejected]
**Author**: [Name]
**Date**: [Date]

## Problem Statement
What problem are we solving?

## Proposed Solution
What are we proposing? How does it work?

## Success Criteria
How will we measure success?

## Resources Required
Time, people, tools, budget.

## Risks and Mitigations
What could go wrong? How do we handle it?

## Timeline
Key milestones and deadlines.
```

### Decision Doc Template

```markdown
# Decision: [Title]

## Context
What led to this decision?

## Options Considered
### Option A: [Name]
- Pros: [...]
- Cons: [...]

### Option B: [Name]
- Pros: [...]
- Cons: [...]

## Decision
What we chose and why.

## Consequences
What does this mean going forward?
```

## Pitfalls

- Skip the outline stage and AI may produce a document that doesn't match your mental model — always review the outline first
- Be specific in feedback; "this needs work" is less helpful than "the third paragraph assumes X, but actually Y"
- For long documents (>2000 words), work section by section rather than generating everything at once
- Save intermediate versions so you can revert if a direction doesn't work out

## Verification

After final review, ask yourself: does this document achieve the goal stated in the brief? Share with a colleague not involved in the writing to test clarity.
