## type_check

Code must pass the project's type checker without errors.

Verification:
1. Run `uv run pyright` (or the project's type check command)
2. Exit code must be 0
3. All new functions and methods must have type annotations
4. No `Any` overuse -- use specific types where possible
