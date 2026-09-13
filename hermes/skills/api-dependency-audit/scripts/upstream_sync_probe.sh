#!/usr/bin/env bash
# Non-destructive cherry-pick probe for syncing a locally-patched fork with its upstream.
#
# For each candidate upstream commit, reports whether it applies cleanly onto the current
# checkout -- WITHOUT touching the working tree (uses a throwaway detached worktree).
#
# Usage:
#   upstream_sync_probe.sh <repo-path> <sha> [sha ...]
#   upstream_sync_probe.sh "D:/Hermes agent/tools/tradingview-mcp" abc1234 def5678
#
# Output: one block per commit, "CLEAN" (with changed files) or "CONFLICT" (with the
# conflicting files). Run this BEFORE deciding what to cherry-pick; never trial-merge
# in the live checkout.
set -u

if [ "$#" -lt 2 ]; then
  echo "usage: $(basename "$0") <repo-path> <sha> [sha ...]" >&2
  exit 2
fi

REPO_ARG="$1"; shift
REPO=$(cd "$REPO_ARG" 2>/dev/null && pwd) || { echo "not a directory: $REPO_ARG" >&2; exit 1; }
PROBE="$(mktemp -d)/probe"

# Clean up any stale probe worktree from an interrupted run.
git -C "$REPO" worktree remove --force "$PROBE" >/dev/null 2>&1
rm -rf "$PROBE"

if ! git -C "$REPO" worktree add --detach "$PROBE" HEAD >/dev/null 2>&1; then
  echo "worktree add failed (is $REPO a git repo with at least one commit?)" >&2
  exit 1
fi

BASE=$(git -C "$PROBE" rev-parse --short HEAD)
echo "baseline: $BASE   repo: $REPO"
echo

for c in "$@"; do
  subj=$(git -C "$PROBE" log -1 --format='%s' "$c" 2>/dev/null) || subj="<unresolvable>"
  if git -C "$PROBE" cherry-pick --no-commit "$c" >/dev/null 2>&1; then
    files=$(git -C "$PROBE" diff --cached --name-only | tr '\n' ' ')
    echo "CLEAN    $c  $subj"
    echo "         files: ${files:-<none>}"
  else
    conflicts=$(git -C "$PROBE" diff --name-only --diff-filter=U 2>/dev/null | tr '\n' ' ')
    echo "CONFLICT $c  $subj"
    echo "         conflicting: ${conflicts:-<none detected>}"
  fi
  # Always return the probe to the baseline before the next commit.
  git -C "$PROBE" cherry-pick --abort >/dev/null 2>&1
  git -C "$PROBE" reset --hard "$BASE" >/dev/null 2>&1
  git -C "$PROBE" clean -fd >/dev/null 2>&1
  echo
 done

git -C "$REPO" worktree remove --force "$PROBE" >/dev/null 2>&1 && echo "probe worktree removed"
