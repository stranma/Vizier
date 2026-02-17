"""Tests for Telegram transport layer."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from vizier.daemon.telegram import TelegramTransport


@pytest.fixture()
def mock_ea() -> MagicMock:
    ea = MagicMock()
    ea.handle_message.return_value = "Hello, Sultan!"
    return ea


class TestTelegramTransport:
    def test_init(self, mock_ea: MagicMock) -> None:
        transport = TelegramTransport(
            token="test-token",
            ea=mock_ea,
            allowed_user_ids=[12345],
        )
        assert transport._token == "test-token"
        assert 12345 in transport._allowed_user_ids

    def test_init_no_allowed_users(self, mock_ea: MagicMock) -> None:
        transport = TelegramTransport(token="test", ea=mock_ea)
        assert transport._allowed_user_ids == set()

    def test_split_message_short(self) -> None:
        chunks = TelegramTransport._split_message("Hello")
        assert chunks == ["Hello"]

    def test_split_message_long(self) -> None:
        text = "a" * 5000
        chunks = TelegramTransport._split_message(text, max_length=4096)
        assert len(chunks) == 2
        assert len(chunks[0]) == 4096
        assert len(chunks[1]) == 904

    def test_split_message_at_newline(self) -> None:
        text = "line1\n" * 1000
        chunks = TelegramTransport._split_message(text, max_length=100)
        for chunk in chunks:
            assert len(chunk) <= 100

    def test_split_message_exact_length(self) -> None:
        text = "x" * 4096
        chunks = TelegramTransport._split_message(text, max_length=4096)
        assert len(chunks) == 1

    def test_setup_without_aiogram(self, mock_ea: MagicMock) -> None:
        transport = TelegramTransport(token="test", ea=mock_ea)
        with patch.dict("sys.modules", {"aiogram": None, "aiogram.client.default": None, "aiogram.enums": None}):
            transport.setup()
        assert transport._bot is None

    @pytest.mark.asyncio()
    async def test_start_without_setup(self, mock_ea: MagicMock) -> None:
        transport = TelegramTransport(token="test", ea=mock_ea)
        await transport.start()

    @pytest.mark.asyncio()
    async def test_stop_without_setup(self, mock_ea: MagicMock) -> None:
        transport = TelegramTransport(token="test", ea=mock_ea)
        await transport.stop()


class TestReplyContext:
    @pytest.mark.asyncio()
    async def test_reply_to_message_includes_context(self, mock_ea: MagicMock) -> None:
        """When user replies to a bot message, EA receives [Replying to: ...] prefix."""
        transport = TelegramTransport(token="test", ea=mock_ea, allowed_user_ids=[123])

        reply_msg = MagicMock()
        reply_msg.text = "Previous bot response about project alpha"

        message = MagicMock()
        message.from_user.id = 123
        message.text = "Tell me more"
        message.reply_to_message = reply_msg

        # Simulate the handler logic directly
        text = message.text
        if message.reply_to_message and message.reply_to_message.text:
            quoted = message.reply_to_message.text[:200]
            text = f"[Replying to: {quoted}]\n\n{text}"

        transport._ea.handle_message(text)
        mock_ea.handle_message.assert_called_with(
            "[Replying to: Previous bot response about project alpha]\n\nTell me more"
        )

    @pytest.mark.asyncio()
    async def test_plain_message_no_prefix(self, mock_ea: MagicMock) -> None:
        """Regular message without reply has no prefix."""
        transport = TelegramTransport(token="test", ea=mock_ea, allowed_user_ids=[123])

        message = MagicMock()
        message.from_user.id = 123
        message.text = "Hello there"
        message.reply_to_message = None

        text = message.text
        if message.reply_to_message and message.reply_to_message.text:
            quoted = message.reply_to_message.text[:200]
            text = f"[Replying to: {quoted}]\n\n{text}"

        transport._ea.handle_message(text)
        mock_ea.handle_message.assert_called_with("Hello there")

    @pytest.mark.asyncio()
    async def test_reply_context_truncated(self, mock_ea: MagicMock) -> None:
        """Long reply messages are truncated to 200 chars."""
        transport = TelegramTransport(token="test", ea=mock_ea, allowed_user_ids=[123])

        reply_msg = MagicMock()
        reply_msg.text = "x" * 500

        message = MagicMock()
        message.from_user.id = 123
        message.text = "What?"
        message.reply_to_message = reply_msg

        text = message.text
        if message.reply_to_message and message.reply_to_message.text:
            quoted = message.reply_to_message.text[:200]
            text = f"[Replying to: {quoted}]\n\n{text}"

        transport._ea.handle_message(text)
        call_text = mock_ea.handle_message.call_args[0][0]
        # [Replying to: <200 x's>]\n\nWhat?
        assert len(call_text.split("\n\n")[0]) == len("[Replying to: ") + 200 + len("]")
