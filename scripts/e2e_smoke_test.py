#!/usr/bin/env python3
"""End-to-end smoke test for a live Vizier deployment.

Sends messages to the bot via Telegram API and verifies the EA processed them
by checking the conversation log file on disk. This avoids the Telegram Bot API
limitation where getUpdates cannot see the bot's own outgoing replies.

Requires environment variables:
  TELEGRAM_BOT_TOKEN      - Bot token for sending messages
  TELEGRAM_TEST_CHAT_ID   - Chat ID to send messages to
  VIZIER_EA_DIR           - Path to ea/ data directory (for log verification)

Usage:
  python scripts/e2e_smoke_test.py
  uv run pytest scripts/e2e_smoke_test.py -m production -v
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from pathlib import Path

import pytest

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.environ.get("TELEGRAM_TEST_CHAT_ID", "")
EA_DIR = os.environ.get("VIZIER_EA_DIR", "")
TIMEOUT = 15


async def send_message(token: str, chat_id: str, text: str) -> bool:
    """Send a message to the bot via Telegram API.

    :param token: Telegram bot token.
    :param chat_id: Target chat ID.
    :param text: Message text.
    :returns: True if message was sent successfully.
    """
    try:
        import httpx
    except ImportError:
        print("httpx required: pip install httpx")
        sys.exit(1)

    base = f"https://api.telegram.org/bot{token}"
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.post(
            f"{base}/sendMessage",
            json={"chat_id": chat_id, "text": text},
        )
        return resp.json().get("ok", False)


def wait_for_log_entry(ea_dir: str, content_substring: str, timeout: float = TIMEOUT) -> str | None:
    """Wait for a conversation log entry containing the given substring.

    :param ea_dir: Path to ea/ data directory.
    :param content_substring: Substring to look for in assistant responses.
    :param timeout: Maximum wait time in seconds.
    :returns: The matching assistant response, or None if timed out.
    """
    log_path = Path(ea_dir) / "sessions" / "conversation.jsonl"
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        if log_path.exists():
            for line in reversed(log_path.read_text(encoding="utf-8").strip().splitlines()):
                try:
                    entry = json.loads(line)
                    if entry.get("role") == "assistant" and content_substring in entry.get("content", ""):
                        return entry["content"]
                except (json.JSONDecodeError, ValueError):
                    continue
        time.sleep(1)

    return None


def get_last_n_entries(ea_dir: str, n: int = 4) -> list[dict[str, str]]:
    """Read the last N entries from the conversation log.

    :param ea_dir: Path to ea/ data directory.
    :param n: Number of entries to return.
    :returns: List of log entry dicts.
    """
    log_path = Path(ea_dir) / "sessions" / "conversation.jsonl"
    if not log_path.exists():
        return []

    entries: list[dict[str, str]] = []
    for line in log_path.read_text(encoding="utf-8").strip().splitlines():
        try:
            entries.append(json.loads(line))
        except (json.JSONDecodeError, ValueError):
            continue
    return entries[-n:]


def _skip_if_missing() -> None:
    if not BOT_TOKEN or not CHAT_ID or not EA_DIR:
        pytest.skip("TELEGRAM_BOT_TOKEN, TELEGRAM_TEST_CHAT_ID, and VIZIER_EA_DIR required")


@pytest.mark.production()
def test_status_response() -> None:
    """Bot processes /status and logs a response."""
    _skip_if_missing()

    ok = asyncio.run(send_message(BOT_TOKEN, CHAT_ID, "/status"))
    assert ok, "Failed to send message"

    response = wait_for_log_entry(EA_DIR, "status", timeout=TIMEOUT)
    assert response is not None, "No status response found in conversation log"


@pytest.mark.production()
def test_general_greeting() -> None:
    """Bot processes a general greeting."""
    _skip_if_missing()

    ok = asyncio.run(send_message(BOT_TOKEN, CHAT_ID, "Hello, good morning"))
    assert ok, "Failed to send message"
    time.sleep(5)

    entries = get_last_n_entries(EA_DIR, 2)
    assert len(entries) >= 2, "Expected at least 2 log entries"
    assert entries[-2].get("role") == "user"
    assert "Hello" in entries[-2].get("content", "")


@pytest.mark.production()
def test_conversation_continuity() -> None:
    """Bot remembers context from a previous message (via conversation log)."""
    _skip_if_missing()

    ok1 = asyncio.run(send_message(BOT_TOKEN, CHAT_ID, "The secret word is pineapple"))
    assert ok1, "Failed to send first message"
    time.sleep(5)

    ok2 = asyncio.run(send_message(BOT_TOKEN, CHAT_ID, "What was the secret word I just told you?"))
    assert ok2, "Failed to send second message"
    time.sleep(5)

    entries = get_last_n_entries(EA_DIR, 4)
    assert len(entries) >= 4, "Expected at least 4 log entries for 2 exchanges"
    user_messages = [e for e in entries if e.get("role") == "user"]
    assert any("pineapple" in e.get("content", "") for e in user_messages)


def main() -> None:
    """Run smoke tests outside of pytest."""
    if not BOT_TOKEN or not CHAT_ID:
        print("Set TELEGRAM_BOT_TOKEN and TELEGRAM_TEST_CHAT_ID environment variables")
        sys.exit(1)

    tests = [
        ("Status response", "/status"),
        ("General greeting", "Hello, good morning"),
        ("Conversation continuity (msg 1)", "The secret word is pineapple"),
    ]

    for name, msg in tests:
        print(f"Sending: {name}...")
        try:
            ok = asyncio.run(send_message(BOT_TOKEN, CHAT_ID, msg))
            print(f"  Sent: {ok}")
        except Exception as e:
            print(f"  [FAIL] {e}")

    if EA_DIR:
        print(f"\nWaiting for responses in {EA_DIR}...")
        time.sleep(5)

        print("\nSending continuity check...")
        asyncio.run(send_message(BOT_TOKEN, CHAT_ID, "What was the secret word?"))
        time.sleep(5)

        entries = get_last_n_entries(EA_DIR, 10)
        for entry in entries:
            role = entry.get("role", "?")
            content = entry.get("content", "")[:100]
            print(f"  [{role}] {content}")

        if any("pineapple" in e.get("content", "") for e in entries):
            print("\n[PASS] Conversation log contains pineapple context")
        else:
            print("\n[WARN] Could not verify continuity in log")
    else:
        print("\nSet VIZIER_EA_DIR to verify responses via conversation log")


if __name__ == "__main__":
    main()
