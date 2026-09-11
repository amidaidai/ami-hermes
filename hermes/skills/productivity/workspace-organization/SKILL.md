---
name: workspace-organization
description: "Use when organizing a user's working directory, Hermes configuration workspace, project folders, generated outputs, scripts, or local secrets. Establishes durable folder conventions, moves files safely, updates ignore rules, documents the layout, verifies git exposure, and saves only stable conventions."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [workspace, files, organization, gitignore, secrets, hermes-workspace]
    related_skills: [hermes-agent, github-repo-management]
---

# Workspace Organization

## Overview

Use this skill to turn a messy working directory into a stable, predictable workspace. The goal is not just to move files, but to create a durable convention the agent can reuse: where projects go, where temporary experiments go, where outputs go, where scripts live, and where local-only secrets must stay.

This skill is especially useful for Hermes personalization repositories, where the root directory often mixes durable configuration, scripts, generated artifacts, and sensitive local files. Treat the root as a control plane: keep it sparse, documented, and safe to inspect.

Session-specific examples and a concrete Hermes workspace layout are in `references/hermes-personal-workspace-layout.md`.

## When to Use

- User asks to clean up, sort, organize, or structure a folder.
- User asks whether a default workspace should be the root or a subdirectory.
- A Hermes personalization/configuration workspace contains scripts, memories, generated files, projects, and local credentials.
- You need to move sensitive files out of the root and ensure they are ignored by Git.
- You need to create a folder convention and remember it for future work.

Don't use this skill for:

- One-off file reads where no structure is being changed.
- Large codebase refactors where the primary task is application architecture rather than workspace hygiene.
- Cloud drive or note vault organization governed by a more specific skill.

## Recommended Folder Model

For a personal agent workspace, prefer a sparse root with clear child folders:

| Path | Purpose | Usually committed? |
|---|---|---|
| `hermes/` | Agent persona, memories, cron jobs, reusable scripts, profile-local config exports | Yes, except secrets |
| `hermes/scripts/` | Reusable maintenance scripts | Yes after review |
| `hermes/scripts/repo-maintenance/` | GitHub backup/reset/remote maintenance scripts | Yes after review |
| `hermes/secrets/` | Local credentials, token files, temporary secret material | No |
| `projects/` | Long-lived user projects | Usually no, or tracked in their own repos |
| `sandbox/` | Temporary experiments and disposable tests | No |
| `outputs/` | Reports, generated files, exports, deliverables | Usually no |
| `README.md` | Human-readable workspace map and rules | Yes |
| `.gitignore` | Protection for transient and sensitive paths | Yes |

Adjust names to the user's language and existing conventions. Do not force this exact shape when the repository already has a clear standard.

## Workflow

1. **Inspect before moving.** List root files and current Git status. Identify tracked, untracked, ignored, and sensitive-looking files.
2. **Classify by purpose.** Separate configuration, scripts, projects, temporary work, generated outputs, and secrets.
3. **Move conservatively.** Prefer creating subdirectories and moving untracked or clearly misplaced files. Do not move tracked code blindly if imports, scripts, or documentation may depend on paths.
4. **Protect local-only data.** Add secret and transient directories to `.gitignore`. Include broad secret patterns only if they do not hide important project files unintentionally.
5. **Document the convention.** Add or update a short `README.md` or similar root-level note explaining each directory and root rules.
6. **Verify exposure.** Check `git status` and `git check-ignore` for sensitive files and transient folders. Confirm the root now looks clean.
7. **Persist durable conventions.** Save stable folder rules to memory. Do not save a one-time move log or transient file list.

## Git Safety Checks

Before finalizing, verify:

```bash
git status --short
git check-ignore -v path/to/secret-file path/to/transient-dir || true
```

If a sensitive file was already tracked, `.gitignore` is not enough. Stop and explain that it needs explicit Git index removal, for example:

```bash
git rm --cached path/to/secret-file
```

Only run destructive or history-rewriting cleanup with explicit user approval.

## Memory Guidance

Good memory entries:

- `Workspace D:/Hermes agent is the Hermes personalization repo; long-term projects go in projects/, temporary experiments in sandbox/, generated outputs in outputs/, local secrets in hermes/secrets/.`
- `For this workspace, root stays sparse and documented; reusable maintenance scripts live under hermes/scripts/.`

Avoid memory entries like:

- `Moved reset_repo.py today.`
- `Created README.md on June 14.`
- `git status showed three untracked files.`

The durable lesson is the convention, not the task transcript.

## Common Pitfalls

1. **Leaving secrets in the root.** A root-level token file is easy to commit by accident. Move it into a local-only secrets directory and verify ignore behavior.
2. **Ignoring outputs too late.** Generated files accumulate quickly; create `outputs/` early and ignore it unless the user wants artifacts versioned.
3. **Making the root a junk drawer.** The default workspace can remain the root, but active work should happen in classified subdirectories.
4. **Overwriting project ownership.** A `projects/` child may contain separate Git repos. Do not force them into the parent repo's tracking model.
5. **Saving transient file inventories to memory.** Memory should describe reusable workspace policy, not today's cleanup details.
6. **Moving tracked files without path impact analysis.** For tracked scripts or code, check references first or keep compatibility wrappers if needed.

## Classifying Deletable Scripts by Reference Graph (not filename version)

When asked to "delete / clean up unused scripts," a script being *named like a version* (`foo_v2.py`) or *unreferenced in cron* does **NOT** make it deletable. Classify by the reference graph, and prefer **archive to `_archive/`** over hard delete when the file is git-tracked.

**Four-way protected set (NEVER touch):**
1. **Imported** — any script that another `.py` does `import`/`from x import` from. Compute with a regex pass over the script dir: `^\s*(?:from|import)\s+([A-Za-z_][A-Za-z0-9_]*)\s*` → if `mod.py` exists in dir, it's a live dependency.
2. **Cron-referenced** — any script named in `cron/jobs.json` (`os.path.basename(j['script'])`). Enables `cronjob`/`hermes cron list` to surface these; paused jobs still count (do not orphan them).
3. **Skill-documented** — any script mentioned in a skill `.md` under `skills/`. Note: skill text is noisy; a *loose* regex matches far too much (`auto_review` matches `auto_review_cron` prefix, `engine_orchestrator` matches comments). Use the candidate name as a **whole string**, not a substring: `if re.search(c + r'\.py', blob)` (free-text anywhere in repo) rather than bare substring. Treat this set as *protected-to-verify*, not auto-deletable.
4. **Core底座** — `binance_public`, `telegram_direct`, `telegram_reliable`, `logger`, `pipeline_router`, `render_v96`, `trading_system`, `fetch_tv_mcp`, etc. Delete these and the whole chain breaks.

**Truly deletable OR candidate** = in dir − (imported ∪ cron ∪ skill-documented ∪ core). Then verify each candidate is NOT an entry-point (runs standalone via cron/manually, never imported) and NOT a version of a live dep.

**Critical trap — `_v2` / `_v3` suffix does NOT mean "newer / the old one is dead":** In this repo the `_v2` files (`backtest_runner_v2`, `scoring_engine_v2`, `risk_constitution_v2`) are often the **unreferenced experimental/vNext branch**, while the un-suffixed `backtest_runner`/`scoring_engine`/`risk_constitution` are the **live ones imported by 3-7 scripts**. Reversed assumption would delete live dependencies. ALWAYS run the import-graph pass and read the top-of-file docstring (`"""vNext影子回测..."""`) before trusting the filename.

**Safer final action:** for git-tracked files, `mv <candidate> _archive/` instead of `rm`. Git history is a recovery net; archive name keeps a record. Then **regression-verify**: `python -m compileall -q .` over remaining `.py`, and re-run the import-graph pass to confirm no remaining script references a moved module.

## Verification Checklist

- [ ] Root directory is sparse and understandable.
- [ ] Scripts, secrets, projects, sandbox work, and outputs have separate homes.
- [ ] Sensitive/local-only paths are in `.gitignore`.
- [ ] `git check-ignore` confirms secret/local paths are ignored.
- [ ] `git status --short` contains only intentional changes.
- [ ] A root `README.md` or equivalent documents the layout.
- [ ] Memory captures the durable folder convention only.
- [ ] Before deleting/moving any `.py`: import-graph pass run, cron refs checked, skill-doc refs checked, core-base protected, `_v2`-≠-newer verified.
