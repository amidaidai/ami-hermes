---
name: finishing-a-development-branch
category: community
description: "Complete development work: merge, PR, or cleanup options."
---

# Finishing a Development Branch

Complete development work on a branch — merge it, open a PR, or clean up. Provides structured options for taking a feature branch to completion.

## When to use

- You've finished implementing a feature or fix on a branch
- You need to merge changes back to the main branch
- You want to create a clean PR with proper description
- You need to clean up temporary branches after merging

## Workflow Options

### Option A: Merge to main (simple workflow)

```bash
# 1. Make sure main is up to date
git checkout main
git pull origin main

# 2. Merge your feature branch
git checkout feature-branch
git rebase main  # or git merge main
# Resolve any conflicts

# 3. Merge into main
git checkout main
git merge feature-branch --no-ff
git push origin main

# 4. Clean up
git branch -d feature-branch
git push origin --delete feature-branch
```

### Option B: Open a PR (collaborative)

```bash
# Push the branch
git push -u origin feature-branch

# Create PR (using gh CLI)
gh pr create \
  --title "feat: add user authentication" \
  --body "## Summary
Implemented OAuth2-based authentication with Google and GitHub providers.

## Changes
- Added auth providers for Google and GitHub
- Created login/signup UI components
- Added session management middleware
- Updated user model with OAuth fields

## Testing
- Added unit tests for auth service
- Manual tested login flow with both providers

Closes #123"
```

### Option C: Clean up and squash

```bash
# Squash commits before merging
git checkout feature-branch
git rebase -i main  # squash into meaningful commits

# Or use squash merge
git checkout main
git merge --squash feature-branch
git commit -m "feat: add user authentication (squashed)"
```

## PR Description Template

```markdown
## What does this PR do?

[Brief description of the change]

## Type of change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update
- [ ] Refactor

## How to test
1. Checkout branch
2. Run `npm test`
3. Verify [specific behavior]

## Screenshots / Demos
[If applicable]

## Related issues
Closes #[issue_number]
```

## Pre-Merge Checklist

- [ ] All tests pass
- [ ] Code reviewed by at least one person
- [ ] Documentation updated (if needed)
- [ ] CHANGELOG updated (if applicable)
- [ ] No debug code or commented-out code
- [ ] Commit messages are clean and descriptive
- [ ] Branch is up to date with main
- [ ] No merge conflicts

## Pitfalls

- Never force-push to shared branches without coordinating with the team
- Squash merging loses individual commit history — use with caution on complex features
- Always verify tests pass after merging, not just before
- Delete feature branches after merging to keep the branch list clean
- Update the PR description if scope changes during review

## Verification

After merging, verify the main branch is in a deployable state: tests pass, no regressions, and the feature works as expected in a staging environment.
