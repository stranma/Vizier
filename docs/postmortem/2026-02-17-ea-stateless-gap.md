# Postmortem: EA Shipped Stateless Despite Architecture Requiring Continuity

**Date**: 2026-02-17
**Severity**: Medium (functionality gap, not data loss)
**Status**: Resolved (PR pending)

---

## Summary

The EA (Executive Assistant) shipped as a completely stateless agent -- every message was processed in isolation with no conversation history. The LLM received only `system prompt + current user message`, with zero prior context. This contradicted multiple architecture documents that specified session continuity as a core EA responsibility.

## What the Architecture Promised

1. **AGENT_SPECS.md:72** -- "Reads Pasha session summaries to maintain continuity"
2. **AGENT_SPECS.md:47** -- `ea/sessions/*.md` listed as an EA input
3. **AGENT_SPECS.md:54** -- "Session summaries (after Pasha sessions end)" listed as EA output
4. **ARCHITECTURE.md:428** -- "When session ends, Pasha writes a summary -> EA reads it for continuity"
5. **runtime.py:67-68** -- `sessions_dir` is created in `__init__`, proving the intent existed in code

## What Was Actually Shipped

- `handle_message()` was single-turn: `system prompt + 1 user message`
- No JSONL, YAML, or any conversation log existed
- `sessions_dir` was created but never read or written
- Telegram handler stripped all `reply_to_message`, `forward_origin`, and quote context
- No conversation persistence mechanism of any kind

## Impact

- Users referencing prior bot messages ("you sent me this") got nonsensical responses
- After bot restarts, all conversational context was lost
- The EA could not track evolving topics across a conversation
- Multi-message delegation workflows required users to repeat full context each time

## Root Cause Analysis

### Primary: No Explicit Acceptance Criteria for Conversation Continuity

Phase 6 (EA + Communication) had acceptance criteria covering individual features -- delegation, status queries, budget, check-ins, priorities, focus mode, briefings, commitments, relationships, and classification. Each feature was tested in isolation with single-turn message exchanges.

No acceptance criterion said: "EA must include prior conversation context in LLM calls" or "EA must persist conversation turns to disk."

### Secondary: Large Phase Scope Obscured the Gap

Phase 6 was one of the largest phases, implementing the classifier, JIT prompt assembly, budget enforcement, commitment tracking, relationship tracking, focus mode, briefings, and more. The volume of features pushed conversation history below the priority threshold.

### Contributing: "sessions_dir" Created a False Signal

The code at `runtime.py:67-68` created `ea/sessions/` during `__init__`, suggesting the feature was partially implemented. This dead code path may have suppressed questions about whether session persistence was working, since the directory structure existed.

### Contributing: Architecture Described Two Different "Continuity" Concepts

The architecture documents conflated two forms of continuity:
1. **Cross-session continuity** -- Pasha writes session summaries that EA reads (ARCHITECTURE.md:428)
2. **Within-conversation continuity** -- EA remembering what was said in the current Telegram exchange

The architecture focused heavily on (1) but (2) is what users actually need first. Since Pasha sessions are not yet implemented, continuity requirement (1) was deferred -- but (2) was never separately identified.

## Resolution

- **ConversationLog**: JSONL-based append-only log stored in `ea/sessions/conversation.jsonl`
- **Multi-turn LLM calls**: `_handle_general()` now loads last 10 turns as message history
- **Telegram reply context**: Reply-to-message text is prepended as `[Replying to: ...]`
- **Persistence across restarts**: JSONL on disk survives daemon restarts
- **Log rotation**: Rotates at 1000 lines to prevent unbounded growth

## Process Improvements

### For CLAUDE.md / PCC

1. **Multi-turn test requirement**: Any agent with LLM interaction must have at least one test that sends multiple messages and verifies the second response reflects awareness of the first.

2. **Dead code detection**: Code that creates directories, allocates resources, or establishes structures but never uses them should be flagged during code review as a potential incomplete implementation.

3. **Architecture claim verification**: Each factual claim in AGENT_SPECS.md and ARCHITECTURE.md (e.g., "maintains continuity") should map to at least one acceptance criterion. If a claim describes future behavior, it should be marked as "planned" rather than stated as present-tense fact.

4. **Realistic usage pattern tests**: Communication-facing agents should have integration tests that simulate realistic multi-message conversations, not just isolated single-turn exchanges.

### For Future Phase Planning

5. **Separate "transport fidelity" from "agent logic"**: The Telegram handler silently dropping `reply_to_message` context is a transport-layer bug independent of the EA logic. Transport layers should be tested for what context they preserve and what they discard.

6. **Feature vs. cross-feature testing**: Phase completion should include at least one test that exercises multiple features in sequence (e.g., delegate a task, then ask about status, then reference the delegation) to catch cross-feature state issues.
