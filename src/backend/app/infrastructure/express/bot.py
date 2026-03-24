from __future__ import annotations

from typing import TYPE_CHECKING

from pybotx import Bot, BotAccountWithSecret, HandlerCollector
from pybotx.models.attachments import OutgoingAttachment  # noqa: TC002
from pydantic import AnyHttpUrl

if TYPE_CHECKING:
    from uuid import UUID

    from app.infrastructure.settings import Settings

collector = HandlerCollector()


def create_express_bot(settings: Settings) -> Bot:
    account = BotAccountWithSecret(
        id=settings.express_bot_id,
        cts_url=AnyHttpUrl(settings.express_cts_url),
        secret_key=settings.express_secret_key,
    )
    return Bot(
        collectors=[collector],
        bot_accounts=[account],
    )


async def edit_in_express(
    bot: Bot,
    *,
    bot_id: UUID,
    sync_id: UUID,
    body: str,
) -> None:
    """Edit an existing message in Express."""
    await bot.edit_message(
        bot_id=bot_id,
        sync_id=sync_id,
        body=body,
    )


async def send_to_express(
    bot: Bot,
    *,
    bot_id: UUID,
    chat_id: UUID,
    body: str,
    file: OutgoingAttachment | None = None,
    wait_callback: bool = False,
) -> UUID:
    """Send a message to Express and return the sync_id."""
    kwargs: dict[str, object] = {}
    if file is not None:
        kwargs["file"] = file
    return await bot.send_message(
        bot_id=bot_id,
        chat_id=chat_id,
        body=body,
        wait_callback=wait_callback,
        **kwargs,
    )
