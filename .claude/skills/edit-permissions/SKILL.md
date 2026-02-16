---
name: edit-permissions
description: Use this skill to view, add, remove, or modify permission rules in .claude/settings.json. Provides pattern syntax reference and safety rules.
---

# Edit Permissions Skill

Manage permission rules in `.claude/settings.json` for Claude Code.

## Quick Reference

Permission rules control which tool calls are automatically allowed, require user confirmation, or are denied.

### Rule Syntax

```
Tool(pattern)
```

- `Tool` = the tool name (e.g., `Bash`, `Read`, `Write`, `Edit`, `WebFetch`)
- `pattern` = what the tool call must match

### Pattern Syntax

| Pattern | Matches | Example |
|---------|---------|---------|
| `*` (space + wildcard) | Any arguments | `Bash(git status *)` matches `git status --short` |
| No wildcard | Exact match only | `WebFetch` matches only `WebFetch` with no args |
| Word boundary | Start of token | `Bash(git *)` matches `git status` but NOT `git-lfs` |

**IMPORTANT:** The deprecated `:*` syntax (e.g., `Bash(command:*)`) must NOT be used. Always use ` *` (space + wildcard).

### Shell Operator Protection

Claude Code's permission system blocks commands containing shell operators (`&&`, `||`, `;`, `|`) from matching `allow` rules. This means:

- `Bash(git add *)` will NOT auto-allow `git add . && git commit -m "msg"`
- Chained commands always require explicit user approval
- This is a security feature to prevent command injection via shell operators

**Workaround:** Use absolute paths and separate commands instead of `&&` chains.

### Evaluation Order

Rules are evaluated in this order:

1. **deny** -- checked first. If matched, the action is blocked.
2. **ask** -- checked second. If matched, the user is prompted.
3. **allow** -- checked last. If matched, the action proceeds automatically.

If no rule matches, the action follows the default permission mode.

### Common Patterns

```json
{
  "permissions": {
    "allow": [
      "Bash(git status *)",
      "Bash(uv run pytest *)",
      "Bash(ls *)",
      "WebSearch"
    ],
    "deny": [
      "Bash(gh secret *)"
    ],
    "ask": [
      "WebFetch",
      "Bash(docker *)"
    ]
  }
}
```

### Safety Rules

1. **Never allow `gh secret`** -- secrets must never be exposed in tool output
2. **Keep `WebFetch` in `ask`** -- it can access arbitrary URLs, so require confirmation
3. **Keep destructive commands in `ask`** -- `docker`, `terraform`, merge operations
4. **Test after editing** -- run `uv run pytest tests/test_permissions.py -v` to validate
5. **Use specific patterns** -- prefer `Bash(git add *)` over `Bash(git *)` for tighter control

### Editing Process

1. Read the current `.claude/settings.json`
2. Identify which list to modify (`allow`, `deny`, or `ask`)
3. Add/remove/move the rule using the correct pattern syntax
4. Verify the JSON is valid
5. Run permission tests if available
