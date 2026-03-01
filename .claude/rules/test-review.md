---
description: Test review criteria for plan and code reviews
---

# Test Review

When reviewing tests, evaluate these dimensions:

## Coverage Gaps
- Are there untested public functions or API endpoints?
- Is there unit coverage for business logic and edge cases?
- Are integration tests present for cross-package workflows?
- Are critical paths (auth, data mutation, error handling) fully tested?

## Test Quality
- Do assertions test behavior, not implementation details?
- Are test descriptions clear about what they verify?
- Do tests fail for the right reasons (not brittle/flaky)?
- Is each test independent (no shared mutable state between tests)?
- Do tests follow the Arrange-Act-Assert pattern?

## Edge Cases
- Are boundary values tested (empty, None, zero, max, negative)?
- Are error paths tested (invalid input, missing data, timeouts)?
- Are race conditions and concurrent access scenarios covered?
- Are Unicode, special characters, and encoding edge cases tested?

## Test Isolation
- Does each test clean up after itself?
- Are fixtures scoped appropriately (function, class, module, session)?
- Are external dependencies mocked at system boundaries?
- Can tests run in any order and still pass?

## Assertion Quality
- Are assertions specific (not just "no exception raised")?
- Do tests assert on the right thing (output, not side effects)?
- Are error messages helpful when assertions fail?
- Are there assertions that always pass (tautologies)?

## Test Maintenance
- Are test helpers/fixtures documented and reusable?
- Are pytest markers used appropriately (slow, integration, production)?
- Is test data realistic but minimal?
- Are parameterized tests used to reduce duplication?
