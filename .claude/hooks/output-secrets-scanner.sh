#!/bin/bash
# PostToolUse hook: Scans command output for leaked secrets.
# Always exits 0 (PostToolUse cannot block). Emits systemMessage warnings.
# Requires jq for JSON parsing; degrades gracefully if missing.

if ! command -v jq &>/dev/null; then
    echo "WARNING: jq not found, output-secrets-scanner hook disabled" >&2
    exit 0
fi

INPUT=$(cat)
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty')

if [ "$TOOL_NAME" != "Bash" ]; then
    exit 0
fi

STDOUT=$(echo "$INPUT" | jq -r '.tool_output.stdout // empty')
STDERR=$(echo "$INPUT" | jq -r '.tool_output.stderr // empty')
OUTPUT="${STDOUT}${STDERR}"

if [ -z "$OUTPUT" ]; then
    exit 0
fi

WARNINGS=""

# AWS Access Key ID (starts with AKIA)
if echo "$OUTPUT" | grep -qE 'AKIA[0-9A-Z]{16}'; then
    WARNINGS="${WARNINGS}[!] Possible AWS Access Key ID detected in output.\n"
fi

# AWS Secret Access Key (40-char base64)
if echo "$OUTPUT" | grep -qE '[^A-Za-z0-9/+=][A-Za-z0-9/+=]{40}[^A-Za-z0-9/+=]'; then
    if echo "$OUTPUT" | grep -qiE 'aws_secret|secret.?access'; then
        WARNINGS="${WARNINGS}[!] Possible AWS Secret Access Key detected in output.\n"
    fi
fi

# Anthropic API Key
if echo "$OUTPUT" | grep -qE 'sk-ant-[a-zA-Z0-9_-]{20,}'; then
    WARNINGS="${WARNINGS}[!] Possible Anthropic API key detected in output.\n"
fi

# OpenAI API Key
if echo "$OUTPUT" | grep -qE 'sk-[a-zA-Z0-9]{20,}'; then
    WARNINGS="${WARNINGS}[!] Possible OpenAI API key detected in output.\n"
fi

# GitHub Personal Access Token
if echo "$OUTPUT" | grep -qE 'ghp_[a-zA-Z0-9]{36}'; then
    WARNINGS="${WARNINGS}[!] Possible GitHub personal access token detected in output.\n"
fi

# GitHub OAuth Token
if echo "$OUTPUT" | grep -qE 'gho_[a-zA-Z0-9]{36}'; then
    WARNINGS="${WARNINGS}[!] Possible GitHub OAuth token detected in output.\n"
fi

# JWT Token
if echo "$OUTPUT" | grep -qE 'eyJ[a-zA-Z0-9_-]*\.eyJ[a-zA-Z0-9_-]*\.[a-zA-Z0-9_-]*'; then
    WARNINGS="${WARNINGS}[!] Possible JWT token detected in output.\n"
fi

# Private Key markers
if echo "$OUTPUT" | grep -qE '-----BEGIN (RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----'; then
    WARNINGS="${WARNINGS}[!] Private key material detected in output.\n"
fi

# Database connection strings with credentials
if echo "$OUTPUT" | grep -qiE '(postgres|mysql|mongodb|redis)://[^:]+:[^@]+@'; then
    WARNINGS="${WARNINGS}[!] Possible database connection string with credentials detected in output.\n"
fi

if [ -n "$WARNINGS" ]; then
    MSG=$(echo -e "SECURITY WARNING: ${WARNINGS}Avoid sharing or committing this output. Rotate any exposed credentials immediately.")
    jq -n --arg msg "$MSG" '{systemMessage: $msg}'
fi

exit 0
