---
description: Code quality review criteria for plan and code reviews
---

# Code Quality Review

When reviewing code quality, evaluate these dimensions:

## Organization
- Is the module structure logical and consistent?
- Are files in the right directories?
- Is the naming convention consistent across the codebase?
- Are imports organized (stdlib, third-party, local)?

## DRY Violations
- Flag duplicated logic (3+ similar lines = candidate for extraction)
- Identify copy-paste patterns that should be abstracted
- Check for repeated magic values (use constants or config)
- Look for repeated error handling that could be centralized

## Error Handling
- Are errors handled at the right level (not swallowed, not over-caught)?
- Are edge cases explicitly handled or documented as out-of-scope?
- Do error messages provide enough context for debugging?
- Are there silent failures (bare except, empty except blocks)?
- Is `assert` used only for invariants, never for input validation?

## Type Annotations
- Are public function signatures fully typed?
- Are return types specified (not just parameters)?
- Is `Any` avoided where a specific type is possible?
- Are `TypeVar`, `Protocol`, or `Generic` used appropriately?

## Complexity
- Are there functions exceeding 30 lines that should be split?
- Is nesting depth kept to 3 levels or fewer?
- Are conditional chains (if/elif/elif) candidates for polymorphism or dispatch?
- Does the complexity match the actual requirements (no over-engineering)?
