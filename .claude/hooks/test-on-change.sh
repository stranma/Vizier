#!/bin/bash
# PostToolUse hook: Discovers and runs associated test files after code changes.
# Uses monorepo conventions: walks up from source file to find tests/ directory.
# Informational only -- returns systemMessage with pass/fail, never blocks.
# Requires jq for JSON parsing; degrades gracefully if missing.

if ! command -v jq &>/dev/null; then
    echo "WARNING: jq not found, test-on-change hook disabled" >&2
    exit 0
fi

INPUT=$(cat)
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty')

if [ "$TOOL_NAME" != "Edit" ] && [ "$TOOL_NAME" != "Write" ]; then
    exit 0
fi

FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

if [ -z "$FILE_PATH" ] || [ "$FILE_PATH" = "null" ]; then
    exit 0
fi

# Only run for Python source files (skip test files themselves)
if [[ "$FILE_PATH" != *.py ]]; then
    exit 0
fi

BASENAME=$(basename "$FILE_PATH" .py)

# Skip if already a test file
if [[ "$BASENAME" == test_* ]]; then
    exit 0
fi

# Skip __init__.py and conftest.py
if [ "$BASENAME" = "__init__" ] || [ "$BASENAME" = "conftest" ]; then
    exit 0
fi

DIRNAME=$(dirname "$FILE_PATH")
TEST_FILE=""

# Strategy 1: Adjacent tests/ directory (monorepo pattern)
# Walk up to find a tests/ directory at the package level
CHECK_DIR="$DIRNAME"
while [ "$CHECK_DIR" != "/" ] && [ "$CHECK_DIR" != "." ]; do
    if [ -d "$CHECK_DIR/tests" ] && [ -f "$CHECK_DIR/tests/test_${BASENAME}.py" ]; then
        TEST_FILE="$CHECK_DIR/tests/test_${BASENAME}.py"
        break
    fi
    # Also check sibling tests/ directory
    PARENT=$(dirname "$CHECK_DIR")
    if [ -d "$PARENT/tests" ] && [ -f "$PARENT/tests/test_${BASENAME}.py" ]; then
        TEST_FILE="$PARENT/tests/test_${BASENAME}.py"
        break
    fi
    CHECK_DIR="$PARENT"
done

# Strategy 2: Root tests/ directory
if [ -z "$TEST_FILE" ]; then
    PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
    if [ -f "$PROJECT_DIR/tests/test_${BASENAME}.py" ]; then
        TEST_FILE="$PROJECT_DIR/tests/test_${BASENAME}.py"
    fi
fi

# If no test file found, exit silently
if [ -z "$TEST_FILE" ]; then
    exit 0
fi

# Run the test
if command -v uv &>/dev/null; then
    TEST_OUTPUT=$(uv run pytest "$TEST_FILE" -x -q 2>&1)
    EXIT_CODE=$?

    if [ $EXIT_CODE -ne 0 ]; then
        TAIL=$(echo "$TEST_OUTPUT" | tail -20)
        jq -n --arg msg "Tests failed in $TEST_FILE: $TAIL" '{systemMessage: $msg}'
    fi
fi

exit 0
