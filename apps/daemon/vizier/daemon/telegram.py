"""Telegram bot transport layer for EA communication.

Thin adapter between aiogram 3.x and the EA runtime. All message classification
and routing is handled by EARuntime; this module only handles I/O.
"""

from __future__ import annotations

import logging
from typing import Any

from vizier.core.ea.runtime import EARuntime  # noqa: TC001

logger = logging.getLogger(__name__)


class TelegramTransport:
    """Telegram bot transport wrapping aiogram 3.x.

    Connects Sultan's Telegram messages to the EA runtime and relays
    responses back.

    :param token: Telegram bot API token.
    :param ea: EA runtime instance for message handling.
    :param allowed_user_ids: List of authorized Sultan user IDs.
    """

    def __init__(
        self,
        token: str,
        ea: EARuntime,
        allowed_user_ids: list[int] | None = None,
    ) -> None:
        self._token = token
        self._ea = ea
        self._allowed_user_ids = set(allowed_user_ids or [])
        self._bot: Any = None
        self._dp: Any = None

    def setup(self) -> None:
        """Initialize the aiogram Bot and Dispatcher."""
        try:
            from aiogram import Bot, Dispatcher
            from aiogram.client.default import DefaultBotProperties
            from aiogram.enums import ParseMode
        except ImportError as e:
            logger.warning("aiogram not installed, Telegram transport disabled: %s", e)
            return

        self._bot = Bot(
            token=self._token,
            default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN),
        )
        self._dp = Dispatcher()
        self._register_handlers()

    def _register_handlers(self) -> None:
        """Register message handlers with the dispatcher."""
        from aiogram import F, Router, types

        router = Router()

        @router.message(F.text)
        async def handle_text(message: types.Message) -> None:
            if not message.from_user or not message.text:
                return

            if self._allowed_user_ids and message.from_user.id not in self._allowed_user_ids:
                logger.warning("Unauthorized message from user %d", message.from_user.id)
                return

            try:
                response = self._ea.handle_message(message.text)
                if response:
                    for chunk in self._split_message(response):
                        await message.answer(chunk)
            except Exception:
                logger.exception("Error handling message")
                await message.answer("An error occurred processing your message.")

        @router.message(F.document)
        async def handle_document(message: types.Message) -> None:
            if not message.from_user:
                return

            if self._allowed_user_ids and message.from_user.id not in self._allowed_user_ids:
                return

            if message.caption:
                response = self._ea.handle_message(f"[file attached] {message.caption}")
            else:
                response = self._ea.handle_message("[file attached]")

            if response:
                await message.answer(response)

        assert self._dp is not None
        self._dp.include_router(router)

    async def start(self) -> None:
        """Start polling for Telegram updates."""
        if self._dp is None or self._bot is None:
            logger.warning("Telegram transport not initialized, skipping start")
            return

        logger.info("Starting Telegram bot polling")
        await self._dp.start_polling(self._bot)

    async def stop(self) -> None:
        """Stop the Telegram bot."""
        if self._bot is not None:
            session = self._bot.session
            await session.close()
            logger.info("Telegram bot stopped")

    @staticmethod
    def _split_message(text: str, max_length: int = 4096) -> list[str]:
        """Split long messages into Telegram-safe chunks."""
        if len(text) <= max_length:
            return [text]

        chunks: list[str] = []
        while text:
            if len(text) <= max_length:
                chunks.append(text)
                break
            split_at = text.rfind("\n", 0, max_length)
            if split_at == -1:
                split_at = max_length
            chunks.append(text[:split_at])
            text = text[split_at:].lstrip("\n")
        return chunks
