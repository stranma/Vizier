## tests_pass

All existing and new tests must pass when running the project's test suite (e.g., `pytest`).

Verification:
1. Run `uv run pytest -q` (or the project's test command)
2. Exit code must be 0
3. No test regressions -- previously passing tests must still pass
4. New functionality must have corresponding tests
