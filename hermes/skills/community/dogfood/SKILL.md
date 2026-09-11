---
name: dogfood
category: community
description: "Exploratory QA of web apps: find bugs, evidence, reports."
---

# Dogfood — Exploratory QA of Web Apps

Perform exploratory quality assurance on web applications. Find bugs, collect evidence (screenshots, console logs), and generate structured bug reports.

## When to use

- You're testing a new web app or feature before release
- You need to find edge cases and unexpected behavior
- You're doing exploratory testing (not scripted test cases)
- You want to produce structured bug reports with evidence

## Methodology

### 1. Setup

```bash
# Open browser dev tools before starting
# Clear cache and cookies for a clean slate
# Set viewport to common sizes (375px, 768px, 1440px)
```

### 2. Exploratory Testing Checklist

#### Functionality
- [ ] Core user flows work end-to-end (signup, login, CRUD, payment)
- [ ] Form validation works (empty fields, invalid input, edge cases)
- [ ] Error states are handled gracefully (network error, 404, 500)
- [ ] Loading states are shown during async operations
- [ ] Pagination / infinite scroll works correctly
- [ ] Search and filtering returns correct results

#### UI/UX
- [ ] Layout is consistent across pages
- [ ] No visual glitches or overlapping elements
- [ ] Text is readable (contrast, font size, overflow)
- [ ] Interactive elements have hover/focus/active states
- [ ] Animations are smooth (no jank)
- [ ] Touch targets are large enough on mobile

#### Responsiveness
- [ ] Works on mobile (375px)
- [ ] Works on tablet (768px)
- [ ] Works on desktop (1440px+)
- [ ] No horizontal scrolling at any width

#### Edge Cases
- [ ] Rapid clicking / double-submit prevention
- [ ] Back/forward browser navigation
- [ ] Tab switching and returning
- [ ] Network throttling (Slow 3G)
- [ ] Empty states (no data, no results)
- [ ] Special characters in input fields

### 3. Bug Report Template

```markdown
## Bug Report

**Title**: [Brief, descriptive title]

**Severity**: [Critical / Major / Minor / Cosmetic]

**Environment**:
- Browser: [Chrome v123 / Firefox v124 / Safari v17]
- OS: [Windows / macOS / Linux / iOS / Android]
- Viewport: [375×812 / 1440×900]
- User: [Logged in as X / Anonymous]

**Steps to Reproduce**:
1. Go to [URL]
2. Click on [element]
3. Enter [value] into [field]
4. Observe [result]

**Expected**: [What should happen]

**Actual**: [What actually happens]

**Evidence**:
- Screenshot: [link or description]
- Console log: [relevant errors]
- Network tab: [failed requests]

**Additional notes**: [Frequency, workaround, related issues]
```

### 4. Evidence Collection

```python
# Pseudocode for collecting evidence
def collect_evidence():
    # Screenshot the current state
    # Capture console errors
    # Capture network requests (especially 4xx/5xx)
    # Note the URL, viewport, and user state
    return {
        "screenshot": "screenshot_001.png",
        "console_errors": ["Uncaught TypeError: ..."],
        "failed_requests": ["POST /api/data 500"],
        "url": "https://app.example.com/settings",
        "viewport": "1440x900"
    }
```

## Testing Heuristics

1. **First-time user** — what does a brand new visitor experience?
2. **Power user** — what happens with lots of data or rapid actions?
3. **Mistake-prone user** — what happens with typos, wrong formats?
4. **Adversarial user** — what happens with SQL injection, XSS attempts?
5. **Offline user** — what happens when network is slow or disconnected?

## Pitfalls

- Don't report cosmetic issues as critical — prioritize by user impact
- Always reproduce a bug at least twice before reporting
- Screenshots are good; screen recordings are better (use a GIF for UI bugs)
- Check if the bug is already known (search existing issues first)
- Don't suggest fixes in the bug report — describe the problem, not the solution (unless asked)

## Verification

After testing, produce a summary: total bugs found, severity distribution, and the top 3 issues that should be fixed before release.
