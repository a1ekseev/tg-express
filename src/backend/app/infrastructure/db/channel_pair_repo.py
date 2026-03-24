from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.domain.models import ChannelPair
from app.infrastructure.db.models import ChannelPairModel

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession


class ChannelPairRepo:
    @staticmethod
    async def find_by_tg_chat_id(session: AsyncSession, tg_chat_id: int) -> ChannelPair | None:
        stmt = select(ChannelPairModel).where(ChannelPairModel.tg_chat_id == tg_chat_id)
        row = (await session.execute(stmt)).scalar_one_or_none()
        if row is None:
            return None
        return _to_domain(row)

    @staticmethod
    async def get(session: AsyncSession, pair_id: UUID) -> ChannelPair:
        stmt = select(ChannelPairModel).where(ChannelPairModel.id == pair_id)
        row = (await session.execute(stmt)).scalar_one()
        return _to_domain(row)

    @staticmethod
    async def find_by_express_chat_id(session: AsyncSession, express_chat_id: UUID) -> ChannelPair | None:
        stmt = select(ChannelPairModel).where(ChannelPairModel.express_chat_id == express_chat_id)
        row = (await session.execute(stmt)).scalar_one_or_none()
        if row is None:
            return None
        return _to_domain(row)

    @staticmethod
    async def get_or_create_unapproved(session: AsyncSession, tg_chat_id: int, name: str | None) -> ChannelPair:
        stmt = (
            pg_insert(ChannelPairModel)
            .values(id=uuid4(), tg_chat_id=tg_chat_id, name=name)
            .on_conflict_do_nothing(index_elements=["tg_chat_id"])
            .returning(ChannelPairModel)
        )
        row = (await session.execute(stmt)).scalar_one_or_none()
        if row is not None:
            return _to_domain(row)
        # Conflict — row already exists, fetch it
        select_stmt = select(ChannelPairModel).where(ChannelPairModel.tg_chat_id == tg_chat_id)
        row = (await session.execute(select_stmt)).scalar_one()
        return _to_domain(row)

    @staticmethod
    async def get_for_update(session: AsyncSession, pair_id: UUID) -> ChannelPair:
        """Get a channel pair with row-level lock (SELECT ... FOR UPDATE)."""
        stmt = select(ChannelPairModel).where(ChannelPairModel.id == pair_id).with_for_update()
        row = (await session.execute(stmt)).scalar_one()
        return _to_domain(row)

    @staticmethod
    async def approve(session: AsyncSession, pair_id: UUID, express_chat_id: UUID) -> None:
        """Set channel pair as approved. Must be called within a FOR UPDATE transaction."""
        stmt = select(ChannelPairModel).where(ChannelPairModel.id == pair_id)
        row = (await session.execute(stmt)).scalar_one()
        row.express_chat_id = express_chat_id
        row.is_approved = True
        await session.flush()

    @staticmethod
    async def list_all(session: AsyncSession) -> list[ChannelPair]:
        stmt = select(ChannelPairModel).order_by(ChannelPairModel.created_at.desc())
        rows = (await session.execute(stmt)).scalars().all()
        return [_to_domain(r) for r in rows]


def _to_domain(model: ChannelPairModel) -> ChannelPair:
    return ChannelPair(
        id=model.id,
        tg_chat_id=model.tg_chat_id,
        express_chat_id=model.express_chat_id,
        is_approved=model.is_approved,
        name=model.name,
    )
