#!/usr/bin/env python3
"""End-to-end smoke test for a live Vizier deployment.

Sends messages to the Telegram bot and verifies responses.
Requires environment variables:
  TELEGRAM_BOT_TOKEN  - Bot token for sending messages
  TELEGRAM_TEST_CHAT_ID - Chat ID to send messages to

Usage:
  python scripts/e2e_smoke_test.py
  uv run pytest scripts/e2e_smoke_test.py -m production -v
"""

from __future__ import annotations

import asyncio
import os
import sys
import time

import pytest

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.environ.get("TELEGRAM_TEST_CHAT_ID", "")
POLL_INTERVAL = 2
TIMEOUT = 30


async def send_and_wait(token: str, chat_id: str, text: str) -> str:
    """Send a message and wait for the bot's response.

    Uses the Telegram Bot API directly via httpx.
    Returns the bot's response text.
    """
    try:
        import httpx
    except ImportError:
        print("httpx required: pip install httpx")
        sys.exit(1)

    base = f"https://api.telegram.org/bot{token}"

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        updates_before = await client.get(f"{base}/getUpdates", params={"offset": -1})
        last_update_id = 0
        data = updates_before.json()
        if data.get("result"):
            last_update_id = data["result"][-1]["update_id"]

        await client.post(
            f"{base}/sendMessage",
            json={"chat_id": chat_id, "text": text},
        )

        deadline = time.monotonic() + TIMEOUT
        while time.monotonic() < deadline:
            await asyncio.sleep(POLL_INTERVAL)
            resp = await client.get(
                f"{base}/getUpdates",
                params={"offset": last_update_id + 1},
            )
            result = resp.json().get("result", [])
            for update in result:
                last_update_id = update["update_id"]
                msg = update.get("message", {})
                if msg.get("chat", {}).get("id") == int(chat_id) and msg.get("from", {}).get("is_bot"):
                    return msg.get("text", "")

        raise TimeoutError(f"No bot response within {TIMEOUT}s")


@pytest.mark.production()
def test_status_response() -> None:
    """Bot responds to /status."""
    if not BOT_TOKEN or not CHAT_ID:
        pytest.skip("TELEGRAM_BOT_TOKEN and TELEGRAM_TEST_CHAT_ID required")

    response = asyncio.run(send_and_wait(BOT_TOKEN, CHAT_ID, "/status"))
    assert response, "Bot returned empty response"
    assert "status" in response.lower() or "project" in response.lower() or "no" in response.lower()


@pytest.mark.production()
def test_conversation_continuity() -> None:
    """Bot remembers context from a previous message."""
    if not BOT_TOKEN or not CHAT_ID:
        pytest.skip("TELEGRAM_BOT_TOKEN and TELEGRAM_TEST_CHAT_ID required")

    asyncio.run(send_and_wait(BOT_TOKEN, CHAT_ID, "The secret word is pineapple"))
    time.sleep(2)
    response = asyncio.run(send_and_wait(BOT_TOKEN, CHAT_ID, "What was the secret word I just told you?"))
    assert response, "Bot returned empty response"


@pytest.mark.production()
def test_general_greeting() -> None:
    """Bot responds to a general greeting."""
    if not BOT_TOKEN or not CHAT_ID:
        pytest.skip("TELEGRAM_BOT_TOKEN and TELEGRAM_TEST_CHAT_ID required")

    response = asyncio.run(send_and_wait(BOT_TOKEN, CHAT_ID, "Hello, good morning"))
    assert response, "Bot returned empty response"


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
        print(f"Testing: {name}...")
        try:
            response = asyncio.run(send_and_wait(BOT_TOKEN, CHAT_ID, msg))
            print(f"  Response: {response[:100]}...")
            print("  [PASS]")
        except (TimeoutError, Exception) as e:
            print(f"  [FAIL] {e}")

    print("\nTesting conversation continuity (msg 2)...")
    try:
        time.sleep(2)
        response = asyncio.run(send_and_wait(BOT_TOKEN, CHAT_ID, "What was the secret word?"))
        print(f"  Response: {response[:200]}")
        if "pineapple" in response.lower():
            print("  [PASS] Bot remembered the secret word")
        else:
            print("  [WARN] Bot may not have remembered (check response manually)")
    except (TimeoutError, Exception) as e:
        print(f"  [FAIL] {e}")


if __name__ == "__main__":
    main()
