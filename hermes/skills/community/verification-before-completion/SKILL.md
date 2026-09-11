---
name: verification-before-completion
category: community
description: "Verify work before claiming completion: evidence before assertions."
---

# Verification Before Completion

Verify work thoroughly before claiming completion. Evidence must precede assertions — never declare a task done without demonstrable proof.

## When to use

- You're about to claim a task is complete
- You need to run final checks before presenting results
- You want to ensure no detail was missed
- The task involves code, configuration, or data

## Mandatory Checks

### 1. Code tasks

- [ ] All files referenced in the plan exist at the expected paths
- [ ] The code runs without errors (`python script.py` or equivalent)
- [ ] Tests pass (`pytest`, `npm test`, or equivalent)
- [ ] No obvious bugs in the logic
- [ ] No debug prints, TODO comments, or commented-out code left behind
- [ ] File contents look correct (cat/head the output)

### 2. Configuration tasks

- [ ] Config file is syntactically valid (JSON/YAML parse check)
- [ ] All required keys are present
- [ ] Values are in the expected format
- [ ] The configured tool/service recognizes the config

### 3. Data tasks

- [ ] Output file exists with expected content
- [ ] Data format is correct (column count, row count, types)
- [ ] No corruption or truncation
- [ ] Content matches what was requested

### 4. Research/analysis tasks

- [ ] All sources referenced are actually accessible
- [ ] Claims are supported by evidence
- [ ] No hallucinated data or sources
- [ ] Quantitative claims have verifiable basis

## Verification Process

### Step 1: State what you'll verify

"I'll verify by:
1. Running the script to confirm the output
2. Checking that output.json exists and is valid JSON
3. Confirming the schema matches requirements"

### Step 2: Actually run verification

Use real tool calls (not descriptions):

```bash
# Check file exists
ls -la output.json

# Check content
cat output.json | head -20

# Validate syntax
python -c "import json; json.load(open('output.json'))"

# Run tests
pytest tests/
```

### Step 3: Show evidence

Present concrete results:

```
## Verification Results

- ✅ Script ran successfully (exit code 0)
- ✅ output.json exists (2.3 KB, 42 records)
- ✅ JSON is valid
- ✅ Schema matches: all 5 required fields present
- 🚫 Tests: 3 failed, 12 passed — fixing failures before claiming complete
```

### Step 4: Only then claim completion

"If verification passes, I'll state: 'Task complete. [What was done]. Verified by [evidence].'"

## What NOT to Do

❌ "The code should work" — run it and show the output
❌ "I'll create the file" — actually create it and show it exists
❌ "Tests would pass" — run them and show the results
❌ "The API probably returns this" — call it and show the response

## Pitfalls

- Don't confuse "I wrote the code" with "the code works" — they are different states
- Don't skip edge cases — test with empty input, invalid input, and boundary values
- Don't assume earlier verification covers later changes — re-verify after any fix
- If verification fails, don't hand-wave — investigate the root cause and fix it
- Real error output is better than fabricated success — report blockers honestly

## Verification

The ultimate verification of this skill: when you complete a task, can you point to specific tool outputs that prove every claimed result exists and works?
