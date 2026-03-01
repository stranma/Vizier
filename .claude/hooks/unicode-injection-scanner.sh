#!/bin/bash
# PreToolUse hook: Blocks Unicode injection attacks in file edits.
# Detects zero-width characters, RTL overrides, ANSI escapes, null bytes,
# and Unicode tag characters that can hide malicious code.
# References: CVE-2025-53109, CVE-2025-53110
# Exit 2 = block the action, Exit 0 = allow.
# Requires jq for JSON parsing; degrades gracefully if missing.

if ! command -v jq &>/dev/null; then
    echo "WARNING: jq not found, unicode-injection-scanner hook disabled" >&2
    exit 0
fi

INPUT=$(cat)
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty')

if [ "$TOOL_NAME" != "Edit" ] && [ "$TOOL_NAME" != "Write" ]; then
    exit 0
fi

# Extract the content being written/edited
if [ "$TOOL_NAME" = "Write" ]; then
    CONTENT=$(echo "$INPUT" | jq -r '.tool_input.content // empty')
elif [ "$TOOL_NAME" = "Edit" ]; then
    CONTENT=$(echo "$INPUT" | jq -r '.tool_input.new_string // empty')
fi

if [ -z "$CONTENT" ]; then
    exit 0
fi

# Check for PCRE support (grep -P requires GNU grep with PCRE; not available on macOS/Alpine by default)
if ! echo "" | grep -qP '' 2>/dev/null; then
    echo "WARNING: grep -P (PCRE) not supported on this system, unicode-injection-scanner hook disabled" >&2
    exit 0
fi

# Zero-width characters (invisible text manipulation)
# U+200B Zero Width Space, U+200C ZWNJ, U+200D ZWJ, U+FEFF BOM
if echo "$CONTENT" | grep -qP '[\x{200B}\x{200C}\x{200D}\x{FEFF}]' 2>/dev/null; then
    echo '{"decision":"block","reason":"Blocked by unicode-injection-scanner: zero-width Unicode characters detected. These can hide malicious code. See CVE-2025-53109."}'
    exit 2
fi

# RTL/LTR override characters (can reorder displayed code)
# U+202A-U+202E, U+2066-U+2069
if echo "$CONTENT" | grep -qP '[\x{202A}\x{202B}\x{202C}\x{202D}\x{202E}\x{2066}\x{2067}\x{2068}\x{2069}]' 2>/dev/null; then
    echo '{"decision":"block","reason":"Blocked by unicode-injection-scanner: bidirectional text override characters detected. These can make code appear different than it executes. See CVE-2025-53110."}'
    exit 2
fi

# ANSI escape sequences (terminal injection)
if echo "$CONTENT" | grep -qP '\x1B\[' 2>/dev/null; then
    echo '{"decision":"block","reason":"Blocked by unicode-injection-scanner: ANSI escape sequences detected. These can manipulate terminal display."}'
    exit 2
fi

# Null bytes (can truncate strings in C-based parsers)
if echo "$CONTENT" | grep -qP '\x00' 2>/dev/null; then
    echo '{"decision":"block","reason":"Blocked by unicode-injection-scanner: null bytes detected in content."}'
    exit 2
fi

# Unicode tag characters (U+E0001-U+E007F, used for invisible tagging)
if echo "$CONTENT" | grep -qP '[\x{E0001}-\x{E007F}]' 2>/dev/null; then
    echo '{"decision":"block","reason":"Blocked by unicode-injection-scanner: Unicode tag characters detected. These can embed invisible instructions."}'
    exit 2
fi

exit 0
