#!/bin/bash
# PreToolUse hook: Blocks dangerous shell commands before execution.
# Exit 2 = block the action, Exit 0 = allow.
# Requires jq for JSON parsing; degrades gracefully if missing.

if ! command -v jq &>/dev/null; then
    echo "WARNING: jq not found, dangerous-actions-blocker hook disabled" >&2
    exit 0
fi

INPUT=$(cat)
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty')

if [ "$TOOL_NAME" != "Bash" ]; then
    exit 0
fi

COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

if [ -z "$COMMAND" ]; then
    exit 0
fi

# Literal patterns that should be blocked outright (matched with grep -F for safety)
BLOCKED_LITERAL_PATTERNS=(
    'rm -rf /'
    'rm -rf /*'
    'rm -rf ~'
    'rm -rf $HOME'
    'sudo rm -rf'
    'dd if=/dev/zero'
    ':(){:|:&};:'
    'chmod -R 777 /'
    'chmod -R 777 /*'
    '> /dev/sda'
    'git push --force'
    'git push -f '
    'git push origin +master'
    'git push origin +main'
    'DROP DATABASE'
    'DROP TABLE'
    'TRUNCATE TABLE'
    'shutdown'
    'reboot'
    'init 0'
    'init 6'
    'halt'
    'poweroff'
)

# Regex patterns that require extended matching
BLOCKED_REGEX_PATTERNS=(
    'mkfs\.'
    'DELETE FROM .* WHERE 1'
)

for pattern in "${BLOCKED_LITERAL_PATTERNS[@]}"; do
    if echo "$COMMAND" | grep -qiF "$pattern"; then
        jq -n --arg reason "Blocked by dangerous-actions-blocker hook: command matches dangerous pattern '$pattern'" \
            '{"decision":"block","reason":$reason}'
        exit 2
    fi
done

for pattern in "${BLOCKED_REGEX_PATTERNS[@]}"; do
    if echo "$COMMAND" | grep -qiE "$pattern"; then
        jq -n --arg reason "Blocked by dangerous-actions-blocker hook: command matches dangerous pattern '$pattern'" \
            '{"decision":"block","reason":$reason}'
        exit 2
    fi
done

# Block commands containing secrets/tokens passed as arguments
# Literal key names use -F; patterns with wildcards use -E
SECRET_LITERAL_PATTERNS=(
    'ANTHROPIC_API_KEY='
    'OPENAI_API_KEY='
    'AWS_SECRET_ACCESS_KEY='
    'GITHUB_TOKEN='
    'GH_TOKEN='
    'password='
    'passwd='
    'secret='
    'token='
)

SECRET_REGEX_PATTERNS=(
    'DATABASE_URL=.*://.*:.*@'
)

for pattern in "${SECRET_LITERAL_PATTERNS[@]}"; do
    if echo "$COMMAND" | grep -qiF "$pattern"; then
        jq -n '{"decision":"block","reason":"Blocked by dangerous-actions-blocker hook: command appears to contain secrets or credentials. Use environment variables instead."}'
        exit 2
    fi
done

for pattern in "${SECRET_REGEX_PATTERNS[@]}"; do
    if echo "$COMMAND" | grep -qiE "$pattern"; then
        jq -n '{"decision":"block","reason":"Blocked by dangerous-actions-blocker hook: command appears to contain secrets or credentials. Use environment variables instead."}'
        exit 2
    fi
done

exit 0
