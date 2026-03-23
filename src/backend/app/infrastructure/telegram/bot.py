from __future__ import annotations

from typing import TYPE_CHECKING

from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession

if TYPE_CHECKING:
    from app.infrastructure.settings import Settings


def create_tg_bot(settings: Settings) -> Bot:
    session: AiohttpSession | None = None
    if settings.tg_proxy_url:
        session = AiohttpSession(proxy=settings.tg_proxy_url)
    return Bot(token=settings.tg_bot_token, session=session)


def create_dispatcher() -> Dispatcher:
    return Dispatcher()
