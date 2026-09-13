# Vendored fork ↔ upstream: fingerprint, drift, probe, report

Topical depth for the "Vendored third-party tools" section of SKILL.md. Load when the owner
shares an external article/repo/X post and asks "is this useful for us?", or when a vendored
tool under `D:/Hermes agent/tools/` may be behind upstream.

## 1. Intake triage: never evaluate a claim before fingerprinting the install

External posts pitch capability, not provenance. Before judging whether a shared tool is worth
anything, establish whether we already run it:

| Check | Command | Reading |
|---|---|---|
| Is the tool registered? | `grep -n -A5 '^  [a-z0-9-]*:$' ~/AppData/Local/hermes/config.yaml` | The MCP block gives server name → `command` + `args`, i.e. the real entry point on disk |
| Is the shared repo ours? | `git -C "<tools>/<tool>" remote -v` | If `origin` is the repo in the post, the post teaches something already deployed |
| How much do we carry on top? | `git status -sb \| head -1` + `git log origin/main..HEAD --oneline` | `ahead N` = owner commits to preserve; dirty tree = owner work to protect |

Outcome to report: the post's *workflow* is either already ours (zero delta) or irrelevant; the
post's *repo link* is the only part that can carry value. Say this plainly instead of restating
the post's tutorial back to the user.

## 2. Drift measurement (three independent axes)

```bash
cd "$REPO"
git fetch origin --tags
git rev-list --count HEAD..origin/main          # behind
git log origin/main..HEAD --oneline             # owner commits
git log HEAD..origin/main --oneline | grep -iE 'fix|feat'   # candidate fixes
```

Entry-surface diff (works without checking anything out):

```bash
# registration names on our side
grep -rhoE "tool\('([a-z_0-9]+)'" src/tools/*.js | sed "s/tool('//;s/'//" | sort -u > /tmp/ours.txt
# registration names upstream
for f in $(git ls-tree --name-only origin/main src/tools/ | sed 's#src/tools/##'); do
  git show "origin/main:src/tools/$f" 2>/dev/null
done | grep -ohE "tool\('([a-z_0-9]+)'" | sed "s/tool('//;s/'//" | sort -u > /tmp/up.txt
comm -13 /tmp/ours.txt /tmp/up.txt   # upstream-only  = genuinely missing capabilities
comm -23 /tmp/ours.txt /tmp/up.txt   # ours-only      = owner additions to re-verify after sync
```

Adapt the registration regex to the project's framework (`server.tool(`, `@mcp.tool`, decorator
lists). The point is to count **registrations**, because upstream adds tools inside existing
files — a file-level diff reports "identical" while capabilities are missing.

## 3. Probe, then report as a table

Run `scripts/upstream_sync_probe.sh <repo> <sha> ...` over the candidate fix commits. Report one
row per commit so the user can decide on evidence, not on a version number:

| Commit | What it fixes | Probe | Reaches a live path we use? |
|---|---|---|---|
| `<sha>` | one-line subject | CLEAN / CONFLICT (files) | yes → cherry-pick / no → skip |

Rank by whether the fix touches a path the analysis pipeline actually exercises (screenshot/render
waits, indicator read-back, symbol/chart switching, alert delivery, input schema) rather than by
upstream ordering. Security fixes (path traversal, injection hardening, dependency audit) upgrade
priority independently of how often the path runs.

## 4. Pitfalls that cost time

- **`behind N` is not "N things we lack".** Most commits are fixes to code paths already present;
only commit-level or registration-level comparison says what is actually missing.
- **Dirty tree + same-file upstream edits = guarantee of conflicts.** Expect conflicts exactly in
the files the owner patched; that is a signal about who touched what, not a reason to abandon the sync.
- **A cherry-pick probe needs a clean baseline each iteration.** Abort *and* `reset --hard` + `clean -fd`
between candidates, or the second commit is tested on top of the first one's changes and the
CLEAN/CONFLICT verdict is wrong (the probe script does this).
- **Editing or removing an owner's uncommitted work to make an upgrade "clean" is never acceptable.**
Stash/commit to a branch first; if the user's rule is "do not overwrite uncommitted changes", that
rule outranks finishing the upgrade in one pass.
- **A source edit is not a deployed change.** Fixes to a tool that a scheduler or MCP host keeps
loaded need cache clearing + an explicit reload before any verification claim.
- **"Newest upstream" is not automatically the target.** A fork may deliberately lag because the
owner pinned behavior; report the delta and recommend the smallest sync that captures the fixes
that matter, not a full rebase.
