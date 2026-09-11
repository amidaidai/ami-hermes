---
name: code-quality-verification
description: "Pre-commit verification pipeline and post-implementation code quality review — security scan, static analysis, independent reviewer subagent, auto-fix loop, and three-reviewer parallel cleanup pass."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [code-review, security, verification, quality, cleanup, pre-commit, auto-fix, refactor]
    related_skills: [github-code-review, test-driven-development, plan]
---

# Code Quality Verification

Two complementary code-verification workflows for different phases of development.

## Phase 1: Pre-Commit Verification (Gate)

Run before `git commit` or `git push`. Verifies your changes don't introduce regressions, security issues, or quality problems.

**Core principle:** No agent should verify its own work. Fresh context finds what you miss.

### When to Use
- After implementing a feature or bug fix, before `git commit` or `git push`
- When user says "commit", "push", "ship", "done", "verify", or "review before merge"
- After completing a task with 2+ file edits in a git repo

**Skip for:** documentation-only changes, pure config tweaks, or when user says "skip verification".

**This skill vs github-code-review:** This phase verifies YOUR changes before committing. `github-code-review` reviews OTHER people's PRs on GitHub with inline comments.

### Step 1 — Get the Diff

```bash
git diff --cached
```

If empty, try `git diff` then `git diff HEAD~1 HEAD`. If still empty, run `git status` — nothing to verify.

### Step 2 — Static Security Scan

```bash
git diff --cached | grep "^+" | grep -iE "(api_key|secret|password|token|passwd)\s*=\s*['\"][^'\"]{6,}['\"]"
git diff --cached | grep "^+" | grep -E "os\.system\(|subprocess.*shell=True"
git diff --cached | grep "^+" | grep -E "\beval\(|\bexec\("
git diff --cached | grep "^+" | grep -E "execute\(f\"|\.format\(.*SELECT"
```

### Step 3 — Baseline Tests and Linting

Capture baseline failures BEFORE your changes (stash changes, run, pop). Only NEW failures block the commit.

```bash
# Python
python -m pytest --tb=no -q 2>&1 | tail -5
which ruff && ruff check . 2>&1 | tail -10

# JS/TS
npm test -- --passWithNoTests 2>&1 | tail -5
which npx && npx eslint . 2>&1 | tail -10
```

### Step 4 — Self-Review Checklist

- [ ] No hardcoded secrets, API keys, or credentials
- [ ] Input validation on user-provided data
- [ ] SQL queries use parameterized statements
- [ ] File operations validate paths (no traversal)
- [ ] External calls have error handling (try/catch)
- [ ] No debug print/console.log left behind

### Step 5 — Independent Reviewer Subagent

Use `delegate_task` to spawn an independent reviewer. Give it the diff and static scan results. Fail-closed: unparseable response = fail.

```python
delegate_task(
    goal="""You are an independent code reviewer. Review the git diff and return ONLY valid JSON.

FAIL-CLOSED: security_concerns non-empty → passed=false, logic_errors non-empty → passed=false.

Return: {"passed": bool, "security_concerns": [], "logic_errors": [], "suggestions": [], "summary": "one sentence"}""",
    context="[INSERT GIT DIFF]",
    toolsets=["terminal"]
)
```

### Step 6 — Evaluate

**All passed:** Proceed to commit.
**Any failures:** Report what failed, then proceed to auto-fix (max 2 cycles).

### Step 7 — Auto-Fix Loop

Spawn a fix agent that fixes ONLY reported issues:

```python
delegate_task(
    goal="Fix ONLY the specific issues listed. Do NOT refactor or add features.",
    context="[Issues to fix...]",
    toolsets=["terminal", "file"]
)
```

After fix, re-run steps 1-6. Max 2 cycles, then escalate to user.

### Step 8 — Commit

```bash
git add -A && git commit -m "[verified] <description>"
```

---

## Phase 2: Post-Implementation Cleanup (Simplify)

Review recent code changes with three focused reviewers running in parallel, aggregate findings, and apply safe fixes.

**Core principle:** Three narrow reviewers beat one broad reviewer. Each one searches for a single class of problem — reuse, quality, efficiency.

### When to Use

Trigger when the user says "simplify", "simplify my changes", "review my code", "clean up my changes", or "/simplify".

Optional modifiers: `focus on efficiency` (run only that reviewer), `dry run` (report only), `scope: last commit/staged/file`.

### Phase 2a — Capture the Diff

```bash
git diff                    # working tree
git diff HEAD               # with staged
git diff --staged           # staged only
git diff HEAD~1             # last commit
git diff main...HEAD        # this branch
```

### Phase 2b — Launch Three Reviewers (Parallel)

Use `delegate_task` batch mode. Give EVERY reviewer the complete diff plus the repo path. Each gets `terminal`, `file`, `search` toolsets.

**Reviewer 1 — Code Reuse:** Search for existing utilities the new code duplicates. Require `file:line` evidence. Flag: new functions duplicating existing ones; hand-rolled logic that a utility already does.

**Reviewer 2 — Code Quality:** Look for: redundant state, parameter sprawl, copy-paste-with-variation, leaky abstractions, stringly-typed code, AI-generated slop patterns (obvious comments, unnecessary null checks). Give concrete refactors.

**Reviewer 3 — Efficiency:** Look for: N+1 patterns, missed concurrency, hot-path bloat, TOCTOU anti-patterns, overly broad reads, silent failures (`except: pass`, `.catch(() => {})`).

All reviewers apply Chesterton's Fence: `git blame` before flagging removal. Report with confidence (high/medium/low) and risk (SAFE/CAREFUL/RISKY).

### Phase 2c — Aggregate and Apply

1. Merge findings, dedup overlaps.
2. Discard false positives (you have the most context).
3. Resolve conflicts: correctness > user's focus > readability/reuse > micro-perf.
4. Apply in risk-tier order: SAFE (auto-apply, run tests), CAREFUL (apply with verification one file at a time), RISKY (flag for human review only).
5. Verify with targeted tests. Revert any fix that breaks.
6. Summarize what changed, grouped by category and risk tier.

### Pitfalls (Phase 2)
- Don't fan out wider than ~3 reviewers.
- Give the WHOLE diff to each reviewer.
- Require `file:line` evidence; drop findings lacking it.
- Apply ≠ rewrite. Keep edits scoped to what the diff touched.
- Over-trusting dead code tools (`knip`, `ts-prune`, `depcheck`) — always grep for the symbol before removing.
- Renaming without checking public contracts — tag as RISKY, never auto-rename.
- Removing "unnecessary" error handling — flag it, don't remove it.

## Common Pitfalls (Both Phases)

- **Empty diff** — check `git status`, tell user nothing to verify.
- **Not a git repo** — skip git-specific steps.
- **Large diff (>15k chars)** — split by file, review each separately.
- **delegate_task returns non-JSON** — retry once, then treat as FAIL.
- **No test framework found** — skip regression check, reviewer verdict still runs.
- **False positives** — if reviewer flags something intentional, note in fix prompt.
- **Auto-fix introduces new issues** — counts as new failure, cycle continues.

## Related Skills

- `github-code-review` — reviewing other people's PRs with inline comments.
- `test-driven-development` — TDD discipline complements verification.
- `plan` — validates implementation matches the plan.
