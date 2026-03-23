from __future__ import annotations

from typing import TYPE_CHECKING

from pybotx import Bot, BotAccountWithSecret, HandlerCollector

if TYPE_CHECKING:
    from uuid import UUID

    from app.infrastructure.settings import Settings

collector = HandlerCollector()


def create_express_bot(settings: Settings) -> Bot:
    account = BotAccountWithSecret(
        id=settings.express_bot_id,
        cts_url=settings.express_cts_url,  # type: ignore[arg-type]
        secret_key=settings.express_secret_key,
    )
    return Bot(
        collectors=[collector],
        bot_accounts=[account],
    )


async def send_to_express(
    bot: Bot,
    *,
    bot_id: UUID,
    chat_id: UUID,
    body: str,
    reply_to: UUID | None = None,  # noqa: ARG001 - reserved for future reply support
) -> UUID:
    """Send a message to Express and return the sync_id."""
    return await bot.send_message(
        bot_id=bot_id,
        chat_id=chat_id,
        body=body,
    )
