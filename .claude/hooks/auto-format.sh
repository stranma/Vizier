#!/bin/bash
# PostToolUse hook: Auto-formats Python files after edits.
# Runs ruff format and ruff check --fix synchronously so Claude sees formatted code.
# Requires jq for JSON parsing; degrades gracefully if missing.

if ! command -v jq &>/dev/null; then
    echo "WARNING: jq not found, auto-format hook disabled" >&2
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

# Only format Python files
if [[ "$FILE_PATH" != *.py ]]; then
    exit 0
fi

# Only format if the file exists
if [ ! -f "$FILE_PATH" ]; then
    exit 0
fi

# Run ruff format (auto-fixes formatting)
if ! command -v uv &>/dev/null; then
    echo "WARNING: uv not found, auto-format hook disabled" >&2
    exit 0
fi

uv run ruff format "$FILE_PATH" 2>/dev/null
uv run ruff check --fix "$FILE_PATH" 2>/dev/null

exit 0
