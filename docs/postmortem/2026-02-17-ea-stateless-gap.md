# Postmortem: EA Stateless Gap

**Date**: 2026-02-17
**Severity**: Medium (functional gap, not data loss)
**Status**: Resolved

## Summary

The EA (Executive Assistant) shipped as completely stateless -- every message was processed in isolation with zero conversation history. The architecture docs specified conversation continuity, the code created the `ea/sessions/` directory for this purpose, but no conversation logging or multi-turn LLM context was ever implemented.

## What the Architecture Promised

1. **AGENT_SPECS.md:72** -- "Reads Pasha session summaries to maintain continuity"
2. **AGENT_SPECS.md:47** -- `ea/sessions/*.md` listed as an EA input
3. **ARCHITECTURE.md:428** -- "When session ends, Pasha writes a summary -> EA reads it for continuity"
4. **runtime.py:67-68** -- `sessions_dir = self._ea_dir / "sessions"` is created in `__init__`, proving the intent existed in code

## What Was Actually Shipped

- `handle_message()` was single-turn: system prompt + 1 user message per LLM call
- No JSONL, YAML, or any conversation log existed anywhere
- `sessions_dir` was created in `__init__` but never read or written to
- Telegram handler discarded all reply/forward context from aiogram `Message` objects
- No conversation persistence mechanism of any kind

## Impact

- Users referencing prior bot messages ("you sent me this") received responses with no awareness of prior context
- After bot restart, all conversational context was lost (no persistence)
- The EA could not build rapport or maintain working relationships across messages
- Multi-step interactions (e.g., "delegate this" -> "actually change the project") required repeating full context

## Root Cause Analysis

### Primary Cause: Scope-driven omission

Phase 6 (EA + Communication) had an ambitious scope:
- Deterministic message classifier with 10+ categories
- JIT prompt assembly with 9 conditional modules
- Budget enforcement (D33)
- Commitment tracking
- Relationship tracking
- Focus mode
- Morning briefings
- Check-in/check-out records
- Quick queries, control commands, delegation routing

Conversation history was implicitly assumed via the "sessions" directory but never had explicit acceptance criteria or a dedicated implementation task.

### Contributing Factors

1. **No explicit acceptance criterion for multi-turn interaction**: The PIRR and acceptance criteria focused on individual features (delegation works, status works, budget works) but not on cross-feature continuity. Each feature was tested in isolation with single-turn messages.

2. **Unused code not flagged**: `sessions_dir` was created but never used. No static analysis or review process caught this as a "dead intent" -- code that signals an unfulfilled design goal.

3. **Architecture docs treated as aspirational, not contractual**: AGENT_SPECS described the EA's *desired* behavior, but there was no mechanism to verify that implemented behavior matched the spec claims.

4. **Telegram transport treated as a pure passthrough**: The aiogram `Message` object contains rich context (reply_to_message, forward_origin, quote), all of which was discarded. The handler extracted only `message.text`.

5. **Test isolation masked the gap**: Every test created a fresh `EARuntime`, sent one message, and checked the response. No test ever sent two messages to the same instance and verified the second was aware of the first.

## Resolution

### Code Changes

1. **ConversationLog** (`libs/core/vizier/core/ea/conversation_log.py`): New JSONL-based conversation log with append, recent retrieval, and rotation at 1000 lines. Stored in `ea/sessions/conversation.jsonl`.

2. **EARuntime** (`libs/core/vizier/core/ea/runtime.py`): All message categories now log both user and assistant turns. `_handle_general()` includes the last 10 conversation turns in LLM calls for multi-turn context.

3. **TelegramTransport** (`apps/daemon/vizier/daemon/telegram.py`): When the user replies to a bot message, the quoted text is prepended as `[Replying to: <text>]` context.

4. **Tests**: 14 new tests covering conversation log persistence, rotation, corrupt line handling, multi-turn LLM calls, restart persistence, and reply context forwarding.

5. **E2E smoke test** (`scripts/e2e_smoke_test.py`): Live deployment test script that verifies conversation continuity against a running bot.

## Process Improvements

### For CLAUDE.md / PCC

1. **Multi-turn test requirement**: For any agent with LLM interaction, acceptance criteria must include at least one multi-turn test scenario. Suggested criterion template: "Send message A, then send message B that references A. Verify B's response demonstrates awareness of A."

2. **Unused code detection**: During code review (PCC step 9), reviewers should flag code that creates structures (directories, files, objects) but never uses them. This is a signal of unfulfilled design intent.

3. **Architecture claim verification**: Add a PIRR dimension: "Do architecture/spec doc claims about this component have corresponding acceptance criteria?" If AGENT_SPECS says "maintains continuity," there must be a test that verifies continuity.

4. **Transport layer context preservation**: When integrating with messaging platforms, document which message metadata is preserved vs discarded. Reviewers should check that relevant context (replies, forwards, threads) reaches the application layer.

5. **Integration test mandate**: For communication-facing agents, at least one test should simulate a realistic multi-message conversation pattern, not just isolated command-response pairs.

## Timeline

| Date | Event |
|------|-------|
| Phase 6 | EA + Communication implemented. `sessions_dir` created, conversation history omitted |
| Phases 7-12 | Multiple phases shipped without noticing the gap |
| 2026-02-17 | Gap identified during deployment testing |
| 2026-02-17 | Fix implemented: ConversationLog + multi-turn LLM + reply context |
