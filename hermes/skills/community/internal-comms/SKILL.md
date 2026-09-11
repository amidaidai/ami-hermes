---
name: internal-comms
category: community
description: 'A set of resources for all kinds of internal communications — status reports, newsletters, incident reports.'
tags:
  - internal-comms
  - status-report
  - newsletter
  - incident-report
  - communication
---

# Internal Communications

A comprehensive set of resources and templates for all types of internal communications — status reports, newsletters, incident reports, and team updates.

## Communication Types

### Status Reports
Keep stakeholders informed on project/team progress:
- **Daily standup** — What I did, what I'll do, blockers
- **Weekly status** — Accomplishments, metrics, upcoming priorities
- **Sprint report** — Completed stories, velocity, retrospective highlights
- **Project health** — Green/yellow/red status with risk assessment

### Newsletters
Regular updates for broader team/org awareness:
- **Team newsletter** — Wins, launches, team spotlights
- **Engineering blog** — Technical deep-dives, architecture decisions
- **Product updates** — Feature releases, roadmap progress
- **Culture/people** — New hires, birthdays, events

### Incident Reports
Post-mortem documentation after incidents:
- **What happened** — Timeline of events
- **Impact** — Users affected, duration, severity
- **Root cause** — Technical and process failures
- **Action items** — Fixes, monitoring, process improvements
- **Follow-ups** — Blameless post-mortem culture

## Templates

### Status Report Template
```
## Status: [Project Name]
**Period:** YYYY-MM-DD to YYYY-MM-DD
**Status:** 🟢 Green / 🟡 Yellow / 🔴 Red

### Accomplishments
- [ ] Deliverable 1 — completed
- [ ] Deliverable 2 — in progress

### Key Metrics
- Metric 1: value (trend)
- Metric 2: value (trend)

### Blockers / Risks
- [Blocker 1] — needs leadership decision

### Next Priorities
1. Task 1
2. Task 2
```

### Incident Report Template
```
## Incident Report: [Title]
**Date:** YYYY-MM-DD
**Severity:** P0/P1/P2
**Duration:** HH:MM
**Lead:** @name

### Summary
One-paragraph overview.

### Timeline
| Time | Event |
|------|-------|
| 14:00 | Alert triggered |
| 14:05 | Engineer paged |
| 14:30 | Root cause identified |
| 15:00 | Fix deployed |
| 15:15 | All clear |

### Root Cause
Detailed explanation.

### Action Items
- [ ] Monitoring alert added
- [ ] Runbook updated
- [ ] Post-mortem scheduled

### Lessons Learned
Key takeaways.
```

## Best Practices

1. **Know your audience** — Executives want metrics, engineers want details
2. **Be timely** — Stale status updates undermine trust
3. **Be honest** — If something is red, say it's red with clear reasoning
4. **Keep it skimmable** — Headers, bold key points, bullet lists
5. **Include concrete next steps** — Don't just report problems, propose solutions
6. **Maintain a blameless culture** — Focus on systems, not people

## Pitfalls

- Don't bury bad news in optimistic language — be direct
- Avoid jargon that different teams won't understand
- Don't report every minor detail — summarize meaningfully
- Include a way to ask questions or give feedback
- Keep distribution lists up to date
