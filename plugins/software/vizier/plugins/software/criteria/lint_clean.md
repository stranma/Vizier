## lint_clean

Code must pass the project's linter without errors or warnings.

Verification:
1. Run `uv run ruff check .` (or the project's lint command)
2. Exit code must be 0
3. No new lint warnings introduced
4. Auto-fixable issues should be fixed before review
