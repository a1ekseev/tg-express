from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select

from app.domain.models import EventType
from app.infrastructure.db.models import ToExpressModel, ToTelegramModel

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession


class MappingQueries:
    @staticmethod
    async def find_express_sync_id(
        session: AsyncSession,
        tg_chat_id: int,
        tg_message_id: int,
    ) -> UUID | None:
        # First check to_express (message originated from TG)
        stmt = select(ToExpressModel.express_sync_id).where(
            ToExpressModel.tg_message_id == tg_message_id,
            ToExpressModel.tg_chat_id == tg_chat_id,
            ToExpressModel.event_type == EventType.NEW_MESSAGE,
            ToExpressModel.express_sync_id.isnot(None),
        )
        result = (await session.execute(stmt)).scalar_one_or_none()
        if result is not None:
            return result

        # Then check to_telegram (message originated from Express, sent to TG)
        stmt2 = select(ToTelegramModel.express_sync_id).where(
            ToTelegramModel.tg_message_id == tg_message_id,
            ToTelegramModel.tg_chat_id == tg_chat_id,
            ToTelegramModel.event_type == EventType.NEW_MESSAGE,
        )
        return (await session.execute(stmt2)).scalar_one_or_none()

    @staticmethod
    async def find_tg_message(
        session: AsyncSession,
        express_sync_id: UUID,
    ) -> tuple[int, int] | None:
        # First check to_telegram (message originated from Express)
        stmt = select(ToTelegramModel.tg_message_id, ToTelegramModel.tg_chat_id).where(
            ToTelegramModel.express_sync_id == express_sync_id,
            ToTelegramModel.event_type == EventType.NEW_MESSAGE,
            ToTelegramModel.tg_message_id.isnot(None),
        )
        row = (await session.execute(stmt)).one_or_none()
        if row is not None:
            return (row[0], row[1])

        # Then check to_express (message originated from TG, sent to Express)
        stmt2 = select(ToExpressModel.tg_message_id, ToExpressModel.tg_chat_id).where(
            ToExpressModel.express_sync_id == express_sync_id,
            ToExpressModel.event_type == EventType.NEW_MESSAGE,
        )
        row2 = (await session.execute(stmt2)).one_or_none()
        if row2 is not None:
            return (row2[0], row2[1])

        return None
