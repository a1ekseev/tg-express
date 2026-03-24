from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.domain.models import MessageStatus
from app.infrastructure.db.models import MessageFileModel, ToTelegramModel

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.infrastructure.db.to_express_repo import MessageFileInsert


class ToTelegramInsert(BaseModel):
    model_config = ConfigDict(frozen=True)

    channel_pair_id: UUID
    express_sync_id: UUID
    express_chat_id: UUID
    express_user_huid: UUID
    reply_to_express_sync_id: UUID | None
    event_type: str


class ToTelegramRepo:
    @staticmethod
    async def bulk_insert(
        session: AsyncSession,
        records: list[ToTelegramInsert],
    ) -> list[UUID | None]:
        results: list[UUID | None] = []
        for rec in records:
            record_id = uuid4()
            insert_stmt = pg_insert(ToTelegramModel).values(
                id=record_id,
                channel_pair_id=rec.channel_pair_id,
                express_sync_id=rec.express_sync_id,
                express_chat_id=rec.express_chat_id,
                express_user_huid=rec.express_user_huid,
                reply_to_express_sync_id=rec.reply_to_express_sync_id,
                event_type=rec.event_type,
            )
            if rec.event_type in ("edit_message", "delete_message"):
                stmt = insert_stmt.on_conflict_do_update(
                    constraint="uq_to_telegram_idempotency",
                    set_={"status": "pending"},
                ).returning(ToTelegramModel.id)
            else:
                stmt = insert_stmt.on_conflict_do_nothing(constraint="uq_to_telegram_idempotency").returning(
                    ToTelegramModel.id
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
        stmt = select(ToTelegramModel.status).where(ToTelegramModel.id == record_id)
        status_str = (await session.execute(stmt)).scalar_one()
        return MessageStatus(status_str)

    @staticmethod
    async def mark_sent(
        session: AsyncSession,
        record_id: UUID,
        tg_message_id: int,
        tg_chat_id: int,
    ) -> None:
        stmt = select(ToTelegramModel).where(
            ToTelegramModel.id == record_id,
            ToTelegramModel.status == MessageStatus.PENDING,
        )
        row = (await session.execute(stmt)).scalar_one_or_none()
        if row is None:
            return  # already sent or missing
        row.tg_message_id = tg_message_id
        row.tg_chat_id = tg_chat_id
        row.status = MessageStatus.SENT
        await session.flush()
