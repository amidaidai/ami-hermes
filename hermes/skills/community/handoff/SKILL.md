---
name: handoff
category: community
description: Compact conversation into handoff document for another agent.
---

# Handoff — Compact Conversation for Agent Transfer

Compact the current conversation into a handoff document designed for another agent to pick up and continue seamlessly.

## When to use

- You need to transfer context to another AI agent
- The conversation is getting long and needs to be summarized
- You're splitting work across multiple agents
- A task needs to be continued in a new session or by a different system

## Handoff Document Template

```markdown
# Handoff: [Task/Project Name]

## Context
[3-5 sentences describing what was being worked on, what state things are in]

## Current State
- **Working directory**: [path]
- **Branch**: [git branch if applicable]
- **Key files**: [file paths and their purpose]
- **Environment**: [relevant env vars, config, tools]

## What Has Been Done
- [ ] [Completed item 1]
- [ ] [Completed item 2]
- [ ] [Completed item 3]

## What Remains
- [ ] [Next task 1] — [details]
- [ ] [Next task 2] — [details]
- [ ] [Blocking issue] — [what's needed to unblock]

## Decisions Made
| Decision | Rationale |
|----------|-----------|
| [Decision 1] | [Why] |
| [Decision 2] | [Why] |

## Known Issues / Gotchas
- [Issue or pitfall discovered]
- [Workaround or mitigation]

## Data / Credentials
- [Any API keys, tokens needed — NOT included here, refer to vault or env]
- [File paths to important data]

## The Next Agent Should...
1. [First action the next agent should take]
2. [Second action]
3. [How to verify success]

---
*Handoff generated: [timestamp]*
```

## Compact Version (for simple handoffs)

```
## HANDOFF

**Task**: [short description]
**Status**: [done / in-progress / blocked]
**Dir**: [working directory]
**Branch**: [branch name]
**Done**: [list of completed items]
**Next**: [next action to take]
**Blockers**: [any issues]
**Key files**: [important files to look at]

The next agent should:
1. [action]
2. [action]
```

## When to Generate a Handoff

1. **Context limit approaching** — conversation is getting long; consolidate before losing context
2. **Switching agents** — moving from one agent type to another (e.g., planning agent → coding agent)
3. **Session end** — wrapping up a session that will continue later
4. **Task delegation** — spawning a sub-agent to handle a specific subtask
5. **Error recovery** — after a crash or timeout, provide condensed context to the new instance

## Pitfalls

- Don't include full conversation history — the handoff is a summary, not a transcript
- Don't include sensitive credentials — refer to environment variables or a vault
- Be specific about file paths — relative paths depend on the working directory
- Include the terminal state — what commands were run and what their outputs were
- A handoff should be readable in 30 seconds — if it's longer, it needs more compression

## Verification

Before finalizing a handoff, ask: if another agent read only this document, could it continue the work without asking additional clarifying questions?
