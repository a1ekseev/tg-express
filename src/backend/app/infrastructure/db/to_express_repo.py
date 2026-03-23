from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.domain.models import MessageStatus
from app.infrastructure.db.models import MessageFileModel, ToExpressModel

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class ToExpressInsert(BaseModel):
    model_config = ConfigDict(frozen=True)

    channel_pair_id: UUID
    tg_message_id: int
    tg_chat_id: int
    tg_user_id: int
    tg_media_group_id: str | None
    reply_to_tg_message_id: int | None
    event_type: str


class MessageFileInsert(BaseModel):
    model_config = ConfigDict(frozen=True)

    direction: str
    message_record_id: UUID
    file_type: str
    file_name: str | None
    file_content_type: str | None
    file_size: int | None
    s3_key: str | None


class ToExpressRepo:
    @staticmethod
    async def bulk_insert(
        session: AsyncSession,
        records: list[ToExpressInsert],
    ) -> list[UUID | None]:
        results: list[UUID | None] = []
        for rec in records:
            record_id = uuid4()
            stmt = (
                pg_insert(ToExpressModel)
                .values(
                    id=record_id,
                    channel_pair_id=rec.channel_pair_id,
                    tg_message_id=rec.tg_message_id,
                    tg_chat_id=rec.tg_chat_id,
                    tg_user_id=rec.tg_user_id,
                    tg_media_group_id=rec.tg_media_group_id,
                    reply_to_tg_message_id=rec.reply_to_tg_message_id,
                    event_type=rec.event_type,
                )
                .on_conflict_do_nothing(constraint="uq_to_express_idempotency")
                .returning(ToExpressModel.id)
            )
            row = (await session.execute(stmt)).scalar_one_or_none()
            results.append(row)
        return results

    @staticmethod
    async def bulk_insert_files(
        session: AsyncSession,
        files: list[MessageFileInsert],
    ) -> None:
        for f in files:
            model = MessageFileModel(
                id=uuid4(),
                direction=f.direction,
                message_record_id=f.message_record_id,
                file_type=f.file_type,
                file_name=f.file_name,
                file_content_type=f.file_content_type,
                file_size=f.file_size,
                s3_key=f.s3_key,
            )
            session.add(model)
        await session.flush()

    @staticmethod
    async def get_status(session: AsyncSession, record_id: UUID) -> MessageStatus:
        stmt = select(ToExpressModel.status).where(ToExpressModel.id == record_id)
        status_str = (await session.execute(stmt)).scalar_one()
        return MessageStatus(status_str)

    @staticmethod
    async def mark_sent(session: AsyncSession, record_id: UUID, express_sync_id: UUID) -> None:
        stmt = select(ToExpressModel).where(
            ToExpressModel.id == record_id,
            ToExpressModel.status == MessageStatus.PENDING,
        )
        row = (await session.execute(stmt)).scalar_one_or_none()
        if row is None:
            return  # already sent or missing
        row.express_sync_id = express_sync_id
        row.status = MessageStatus.SENT
        await session.flush()
