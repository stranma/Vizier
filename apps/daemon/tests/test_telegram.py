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
