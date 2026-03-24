"""Shared approval logic for channel pairs."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from pybotx import ChatTypes

from app.application.utils.message_formatter import build_express_chat_name
from app.domain.models import ChannelPair

if TYPE_CHECKING:
    from uuid import UUID

    from pybotx import Bot
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.infrastructure.db.channel_pair_repo import ChannelPairRepo

logger = logging.getLogger(__name__)


async def approve_channel_pair(
    *,
    session: AsyncSession,
    channel_pair_repo: ChannelPairRepo,
    express_bot: Bot,
    bot_id: UUID,
    pair_id: UUID,
    group_prefix: str,
    admin_huids: list[UUID],
) -> ChannelPair | None:
    """Approve a channel pair under FOR UPDATE lock.

    Creates an Express chat, promotes admins, and marks the pair as approved.
    Returns the approved ChannelPair, or None if already approved (concurrent).
    Must be called within an active transaction.
    """
    locked_pair = await channel_pair_repo.get_for_update(session, pair_id)

    if locked_pair.is_approved:
        logger.info("Channel pair=%s already approved (concurrent), skipping", pair_id)
        return None

    chat_name = build_express_chat_name(group_prefix, locked_pair.name or str(locked_pair.tg_chat_id))

    express_chat_id = await express_bot.create_chat(
        bot_id=bot_id,
        name=chat_name,
        chat_type=ChatTypes.GROUP_CHAT,
        huids=admin_huids,
    )

    if admin_huids:
        await express_bot.promote_to_chat_admins(
            bot_id=bot_id,
            chat_id=express_chat_id,
            huids=admin_huids,
        )

    await channel_pair_repo.approve(session, pair_id, express_chat_id)

    logger.info("Approved channel pair=%s, express_chat_id=%s, name=%s", pair_id, express_chat_id, chat_name)

    return ChannelPair(
        id=locked_pair.id,
        tg_chat_id=locked_pair.tg_chat_id,
        express_chat_id=express_chat_id,
        is_approved=True,
        name=locked_pair.name,
    )
