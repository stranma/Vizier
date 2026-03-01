---
description: Performance review criteria for plan and code reviews
---

# Performance Review

When reviewing performance, evaluate these dimensions:

## Database and I/O Access
- Are there N+1 query patterns (loop with individual queries)?
- Are queries using appropriate indexes?
- Is data fetched at the right granularity (not over-fetching)?
- Are bulk operations used where possible (batch inserts/updates)?
- Are file handles and connections properly closed (use context managers)?

## Memory
- Are large datasets streamed/iterated rather than loaded entirely in memory?
- Are there potential memory leaks (unclosed connections, growing caches)?
- Is object allocation minimized in hot paths?
- Are generators used where full lists are unnecessary?
- Is `__slots__` considered for data-heavy classes?

## Caching
- What data is expensive to compute and stable enough to cache?
- Are cache invalidation strategies defined?
- Is caching applied at the right layer?
- Are `functools.lru_cache` or `functools.cache` used for pure functions?

## Algorithmic Complexity
- Are there O(n^2) or worse algorithms that could be optimized?
- Are hot paths identified and optimized?
- Is unnecessary work being done (redundant computations, unused transforms)?
- Are appropriate data structures used (dict for lookups, set for membership)?
- Are list comprehensions preferred over manual loops where readable?

## Concurrency
- Are CPU-bound tasks using `multiprocessing` (not threading)?
- Are I/O-bound tasks using `asyncio` or thread pools?
- Are shared resources properly synchronized?
- Is there unnecessary serialization of parallel-capable work?
