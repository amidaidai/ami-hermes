---
name: code-review-architecture
description: Code Review & Architecture Improvement — review code architecture, detect anti-patterns, suggest improvements following patterns from grill-me and improve-codebase-architecture. Use when user asks for architectural code review, architecture improvement, or structural code analysis.
---

# Code Review & Architecture Improvement

Review code architecture, detect anti-patterns, and suggest structural improvements.

## Architectural Dimensions to Review

### 1. Separation of Concerns
- Do functions/classes/modules have a single responsibility?
- Are cross-cutting concerns (logging, auth, caching) properly separated?
- Is business logic mixed with infrastructure code?

### 2. Dependency Management
- Are dependencies injected rather than hard-coded?
- Is the dependency graph acyclic? (No circular imports)
- Do high-level modules depend on abstractions, not details?

### 3. Data Flow
- Is data flow unidirectional? (Side effects should be explicit)
- Are data transformations predictable and testable?
- Is state mutation localized and explicit?

### 4. Error Handling
- Are errors handled at the right abstraction level?
- Is there a consistent error model across the codebase?
- Are error paths tested?

### 5. Testability
- Can core logic be tested without mocks?
- Are I/O boundaries explicit and testable?
- Is the test coverage structural (integration tests for architecture, unit tests for logic)?

### 6. Scalability Patterns
- Are there obvious bottlenecks (sequential loops over large data, N+1 queries)?
- Is caching applied at appropriate layers?
- Are resource limits considered (memory, connections, file handles)?

## Review Process

1. **Understand the intent**: What problem does this code solve?
2. **Trace the critical path**: How does data flow through the system?
3. **Identify architectural layers**: Where are the boundaries?
4. **Find violations**: What principles are being broken?
5. **Prioritize**: P0 (blocks future work), P1 (increases maintenance cost), P2 (cosmetic)

## Output Format

For each finding:
- **Severity**: Critical / Major / Minor
- **Current code**: What's happening now
- **Problem**: Why this is problematic
- **Suggestion**: Concrete code example or refactoring approach
- **Trade-offs**: What changes might cost
