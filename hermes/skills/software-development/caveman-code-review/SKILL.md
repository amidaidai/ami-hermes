---
name: caveman-code-review
description: "Caveman Code Review — brutally simple, brutally honest code review that strips away fluff and exposes real problems. Based on juliusbrussee/caveman (274.8K installs on skills.sh)"
version: 1.0.0
author: Hermes Agent (adapted from juliusbrussee/caveman)
tags: [code-review, quality, brutal, honest, simplicity]
---

# Caveman Code Review

> **Brutally simple. Brutally honest.**
> 
> Load this skill when code needs a real review — not a rubber stamp, not a list of nitpicks, but honest assessment of what's actually wrong.

## The Caveman Method

### Step 1: Read the code
Read it like you've never seen it before. No assumptions.

### Step 2: Answer 5 Caveman Questions

1. **"What does this do?"** — If you can't explain it in one sentence, it's too complex.
2. **"Why is this here?"** — Every line needs a reason. Delete unnecessary code.
3. **"Does this work?"** — Not "probably". Actually trace the logic. Find the edge cases.
4. **"Is this safe?"** — What breaks? What leaks? What's the worst input?
5. **"Is this maintainable?"** — Will the next person understand it? Will the next person curse the author?

### Step 3: Deliver the Verdict

| Verdict | Meaning |
|---------|---------|
| ✅ **CAVEMAN APPROVED** | Solid code. Ship it. |
| ⚠️ **CAVEMAN HAS CONCERNS** | Has issues but can be fixed. List them. |
| ❌ **CAVEMAN IS ANGRY** | Rewrite. Don't patch a broken design. |
| 🔥 **CAVEMAN IS VERY ANGRY** | This code is dangerous. Do not ship. Blocking. |

## Review Focus Areas (in priority order)

1. **Security** — Injection, auth bypass, data leaks, input validation
2. **Logic** — Does the algorithm actually work? Edge cases?
3. **Complexity** — Can this be simpler? Fewer branches, fewer states?
4. **Naming** — Is the intent clear? Would a new contributor understand?
5. **Structure** — Is the code in the right place? Right abstraction level?
6. **Tests** — Are there tests? Do they test the right things? Do they pass?

## Output Format

```caveman
FILE: path/to/file.ext

✅/⚠️/❌ [One-line verdict]

- Issue 1: [What's wrong + why it matters]
  Fix: [How to fix, one sentence]

- Issue 2: [What's wrong + why it matters]
  Fix: [How to fix, one sentence]

...

Priority: low/medium/high/critical
```

## Installation
```bash
npx skills add juliusbrussee/caveman
```

> *Based on the caveman skill with 274.8K+ installs on skills.sh — the most popular pure code-review skill in the ecosystem.*
