---
description: Architecture review criteria for plan and code reviews
---

# Architecture Review

When reviewing architecture (plans or code), evaluate these dimensions:

## System Design

- Are component boundaries clear and well-defined?
- Does each component have a single, well-understood responsibility?
- Are interfaces between components minimal and well-documented?
- Is the monorepo package split respected?

## Dependencies

- Is the dependency graph acyclic and manageable?
- Are there circular dependencies between packages?
- Are external dependencies justified (not adding a library for one function)?

## Data Flow

- Is data ownership clear (which component is source of truth)?
- Are there potential bottlenecks in the data pipeline?
- Is data transformation happening at the right layer?
- Are internal representations separated from external API contracts?

## Security Boundaries

- Are authentication and authorization properly layered?
- Is data access controlled at the right boundaries?
- Are API boundaries validated (input sanitization, rate limiting)?
- Are secrets managed via environment variables (not hardcoded)?
- Is the principle of least privilege followed?

## Scaling Considerations

- What are the single points of failure?
- Are stateless and stateful components properly separated?
- Can components be tested and deployed independently?
