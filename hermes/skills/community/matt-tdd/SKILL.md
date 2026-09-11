---
name: matt-tdd
description: Test-driven development with red-green-refactor loop. Use when user asks to write tests first, do TDD, or develop feature with test-driven approach.
---

# Matt TDD

Test-driven development following the Red-Green-Refactor loop.

## The TDD Cycle

### 🔴 Red: Write a Failing Test
1. Write a test for the behavior you want
2. The test should fail because the code doesn't exist yet
3. The test is your specification — it describes ONE behavior

**Test quality checklist:**
- Tests one thing (single assertion or group of related assertions)
- Descriptive name explaining what's being tested
- Independent of other tests
- Fast to run (< 100ms)
- No external dependencies (mock/stub I/O)

### 🟢 Green: Make It Pass
1. Write the minimum code to pass the test
2. It can be ugly, slow, or hard-coded — that's fine
3. The goal is to make the test pass, not production-ready code

**What "minimum" means:**
- Return a hard-coded value if that passes
- Don't handle edge cases not covered by tests
- If you're tempted to add error handling not tested — don't

### 🔵 Refactor: Improve the Code
1. Clean up the implementation now that tests pass
2. Remove duplication, improve naming, simplify logic
3. The tests stay green throughout refactoring
4. Extract duplication between tests (test helpers, fixtures)

**Refactoring targets:**
- Duplicate code
- Poor naming
- Long functions
- Inline magic numbers/strings
- Overly complex conditionals

## Rhythm
- Cycle duration: 30 seconds to a few minutes
- If you spend > 5 minutes in any phase, you're doing too much
- Run tests every 10-30 seconds
- Commit after each green phase (tiny commits)

## When TDD Fits Best

| Great for | Poor fit for |
|-----------|-------------|
| Business logic | UI/Visual layout |
| Data transformations | Exploratory code |
| API endpoints | One-off scripts |
| Validation rules | Prototypes |
| Algorithms | Migrations |
