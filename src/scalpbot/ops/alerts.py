"""Telegram alerts on halts, fills, errors, watchdog events (PLAN.md §10).

Fire-and-forget with local queueing — an alert failure must never block or
crash the trading path.
"""

from __future__ import annotations


class TelegramAlerter:
    def __init__(self, bot_token: str, chat_id: str) -> None:
        raise NotImplementedError("Phase 1")

    async def send(self, text: str, *, critical: bool = False) -> None:
        raise NotImplementedError
