---
name: receiving-code-review
category: community
description: "Use when receiving code review feedback: rigorous verification required."
---

# Receiving Code Review — Responding to Feedback

Use this skill whenever you receive code review feedback. Provides a structured process for understanding, evaluating, and implementing review comments.

## When to use

- A reviewer has left comments on your PR or code change
- You need to respond to feedback systematically
- You want to ensure all review points are addressed before re-requesting review

## Workflow

### Step 1: Acknowledge all comments

Read every comment. For each one, determine:
- Is it a **blocking issue** (must fix before merge)?
- Is it a **suggestion** (nice to have)?
- Is it a **question** (needs clarification)?
- Is it a **nitpick** (style preference)?

### Step 2: Before writing code, verify understanding

For each comment, restate it in your own words and confirm with the reviewer if unclear:

```
Reviewer: "This function is doing too much. Split it up."
Your restatement: "You want me to extract the validation logic and the formatting logic into separate helper functions."
```

### Step 3: Implement changes

1. Fix blocking issues first
2. Address suggestions if they improve the code
3. Respond to questions with explanations
4. For nits, either apply or politely explain your reasoning

### Step 4: Respond to each comment

Use this response structure:

| Comment Type | Response Pattern |
|-------------|-----------------|
| Blocking issue | "Fixed in abc123. Added error handling for the edge case you mentioned." |
| Suggestion accepted | "Good idea, applied in def456. Also cleaned up the adjacent line." |
| Suggestion declined | "I considered this but decided against because [reason]. Happy to discuss further." |
| Question | "Good question — this handles [edge case] by [mechanism]." |
| Nit accepted | "Done." |
| Nit declined | "I prefer the current formatting since it matches the project style in file X." |

### Step 5: Re-request review

After addressing all comments, reply to the reviewer:

```
Addressed all review feedback. Key changes:
- Extracted validation into validate_input() (blocking)
- Renamed ambiguous variable (suggestion)
- Added docstring explaining edge case (question)

PTAL when you get a chance.
```

## Principles

1. **Assume good intent.** The reviewer is spending time to make the codebase better.
2. **Don't take it personally.** Feedback is about the code, not you.
3. **Push back constructively.** If you disagree, explain with evidence, not ego.
4. **Fix the root cause.** A comment about a specific line might indicate a broader design issue.
5. **Check for cascading changes.** Fixing one thing might break other parts of the code.

## Pitfalls

- Don't dismiss comments as "nits" without considering them — nits sometimes reveal deeper issues
- Don't batch-push without re-testing — verify each fix independently
- Don't argue in comments — if disagreement persists, suggest a sync call
- Don't feel pressured to accept every suggestion — you own the change, but be open-minded
- Don't forget to update tests when you change implementation

## Verification

Before re-requesting review, run through this checklist:
- [ ] Every comment has a response
- [ ] All blocking issues are fixed
- [ ] Tests pass
- [ ] No regression introduced
- [ ] Commit messages reference the review feedback addressed
