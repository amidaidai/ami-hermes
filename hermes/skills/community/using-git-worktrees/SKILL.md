---
name: using-git-worktrees
category: community
description: Isolate feature work using git worktrees.
---

# Using Git Worktrees — Isolate Feature Work

Use `git worktree` to work on multiple branches simultaneously without stashing or switching contexts. Each worktree is an independent working directory linked to the same repository.

## When to use

- You need to work on a feature while keeping main branch ready for hotfixes
- You want to review a PR branch without disturbing your current work
- You need to run tests on multiple branches concurrently
- You're tired of stashing and switching contexts

## Basic Commands

### Create a new worktree

```bash
# Create a worktree for a new feature branch
git worktree add ../project-feature-x feature-x

# Create a worktree for an existing branch
git worktree add ../project-hotfix origin/hotfix-urgent

# Create a worktree and check out a new branch
git worktree add -b new-feature ../project-new-feature main
```

### List worktrees

```bash
git worktree list
# Output:
# /path/to/main-repo     (main)
# /path/to/project-feature-x  (feature-x)
# /path/to/project-hotfix     (hotfix-urgent)
```

### Remove a worktree

```bash
# After you're done with the branch
git worktree remove ../project-feature-x

# Or if the directory is already deleted
git worktree prune
```

### Lock/Unlock worktrees

```bash
# Prevent a worktree from being pruned (e.g., on removable media)
git worktree lock ../project-feature-x --reason "On external SSD"

git worktree unlock ../project-feature-x
```

## Workflow Example

```bash
# 1. In your main repo
cd ~/projects/my-app

# 2. Start a new feature in a worktree
git worktree add ../my-app-feature-login -b feature/login main

# 3. Work on the feature in the separate directory
cd ~/projects/my-app-feature-login
# ... make changes, commit, push ...

# 4. Meanwhile, a hotfix comes in — switch main repo to handle it
cd ~/projects/my-app
git checkout main
git pull
git checkout -b hotfix/critical-bug
# ... fix, commit, push, merge ...

# 5. Finish the feature worktree
cd ~/projects/my-app-feature-login
git push -u origin feature/login
cd ~/projects/my-app
git worktree remove ../my-app-feature-login
```

## Benefits Over `git stash`

| Scenario | Stash | Worktree |
|----------|-------|----------|
| Switch to another branch quickly | ✅ Possible | ✅ Instant |
| Keep working on both branches | ❌ No | ✅ Yes |
| Run tests on both simultaneously | ❌ No | ✅ Yes |
| Disk space | Less | More (one checkout per worktree) |
| Complexity | Low | Medium |

## Advanced Usage

### Worktree with bare repo

```bash
# Create a bare repo (good for central management)
git clone --bare https://github.com/user/repo.git ~/repos/repo.git

# Add worktrees from the bare repo
git --git-dir=~/repos/repo.git worktree add ~/work/feature-x feature-x
git --git-dir=~/repos/repo.git worktree add ~/work/feature-y feature-y
```

### Move a worktree

```bash
# Git doesn't have a direct move — re-add and remove
git worktree add ../new-location branch-name
git worktree remove ../old-location
```

## Pitfalls

- Worktrees use extra disk space (each one is a full checkout)
- You can't have the same branch checked out in two worktrees simultaneously
- Removing a worktree directory manually requires `git worktree prune` to clean up metadata
- Worktrees on removable drives need to be locked to prevent pruning
- Editor config files in the worktree root may conflict with the main repo's config
- The `.git` file in a worktree is a file (not a directory) pointing to the main repo's `.git` directory

## Verification

Create a worktree, verify `git worktree list` shows it, make a change in the worktree, confirm the main repo is unaffected, then clean up.
