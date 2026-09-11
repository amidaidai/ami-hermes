---
name: code-simplification
description: Simplify code for clarity without changing behavior — reduce complexity, eliminate duplication, improve readability. Use when user asks to simplify code, refactor for clarity, reduce complexity, or clean up code.
---

# Code Simplification

Simplify code for clarity without changing behavior.

## Simplification Techniques

### 1. Reduce Nesting
Replace deeply nested conditionals with:
- Early returns / guard clauses
- Ternary operators (where clear)
- Extract method
- Polymorphism (replace conditionals with dispatch)

### 2. Eliminate Duplication
DRY Principle: Extract repeated code into:
- Functions (same logic, same level of abstraction)
- Loops (same logic, varying data)
- Generics/templates (same logic, varying types)

### 3. Simplify Conditionals
- Merge nested ifs with && / ||
- Replace flags with strategy objects
- Use switch/pattern matching when checking one variable
- Remove dead branches (conditions that are always true/false)

### 4. Name Things Well
- Variables: Noun or noun phrase describing what they hold
- Functions: Verb or verb phrase describing what they do
- Booleans: is/has/should prefix
- Avoid: temp, data, result, foo, bar

### 5. Reduce Function Length
Functions should do one thing at one level of abstraction:
- Extract sub-functions with descriptive names
- Aim for < 20 lines per function
- If you need a comment to explain what a block does, extract it

### 6. Simplify State Management
- Prefer immutable data (don't mutate, return new values)
- Reduce mutable shared state
- Make side effects explicit at the boundary

## Before/After Pattern

Always show the original and simplified code side by side so the user can verify no behavior changed.

## Verification

After simplification, verify:
1. Input/output behavior is identical for all test cases
2. No new dependencies were introduced
3. Code is at least as readable as before
