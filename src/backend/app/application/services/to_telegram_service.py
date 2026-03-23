"""Service: Express webhook → DB → S3 → Telegram API (merged ingress + egress)."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from aiogram.types import BufferedInputFile, ReplyParameters

from app.application.utils.message_filter import should_forward_express_message
from app.application.utils.message_formatter import format_header_to_telegram
from app.application.utils.message_splitter import split_to_telegram
from app.application.utils.retry import with_retry
from app.application.utils.sanitize import sanitize_to_telegram
from app.domain.models import Employee, EventType, MessageDirection, MessageStatus
from app.infrastructure.db.to_express_repo import MessageFileInsert
from app.infrastructure.db.to_telegram_repo import ToTelegramInsert

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from uuid import UUID

    from aiogram import Bot
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from app.application.dto import ExpressIncomingDTO
    from app.infrastructure.db.channel_pair_repo import ChannelPairRepo
    from app.infrastructure.db.employee_repo import EmployeeRepo
    from app.infrastructure.db.mapping_queries import MappingQueries
    from app.infrastructure.db.to_telegram_repo import ToTelegramRepo
    from app.infrastructure.s3.storage import S3Storage


class ToTelegramService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        to_telegram_repo: ToTelegramRepo,
        channel_pair_repo: ChannelPairRepo,
        mapping_queries: MappingQueries,
        employee_repo: EmployeeRepo,
        s3_storage: S3Storage,
        tg_bot: Bot,
        retry_max_attempts: int = 3,
        retry_base_delay: float = 1.0,
        retry_max_delay: float = 30.0,
    ) -> None:
        self._session_factory = session_factory
        self._to_telegram_repo = to_telegram_repo
        self._channel_pair_repo = channel_pair_repo
        self._mapping_queries = mapping_queries
        self._employee_repo = employee_repo
        self._s3_storage = s3_storage
        self._tg_bot = tg_bot
        self._retry_max_attempts = retry_max_attempts
        self._retry_base_delay = retry_base_delay
        self._retry_max_delay = retry_max_delay

    async def handle_batch(self, messages: list[ExpressIncomingDTO]) -> None:
        if not messages:
            return

        logger.info("Processing %d Express messages for chat_id=%s", len(messages), messages[0].chat_id)

        # 0. Filter: only forward-eligible messages
        eligible = [
            m
            for m in messages
            if should_forward_express_message(has_sticker=m.has_sticker, has_location=m.has_location)
        ]
        if not eligible:
            return

        # 0.1. Sanitize text
        sanitized_bodies: dict[UUID, str | None] = {}
        for msg in eligible:
            sanitized_bodies[msg.sync_id] = sanitize_to_telegram(msg.body)

        # 0.2. Lookup channel_pair by express_chat_id
        async with self._session_factory() as session, session.begin():
            channel_pair = await self._channel_pair_repo.find_by_express_chat_id(session, eligible[0].chat_id)

        if channel_pair is None or not channel_pair.is_approved:
            logger.warning("No approved channel pair for express chat_id=%s", eligible[0].chat_id)
            return

        # 1. Upload files to S3 (outside transaction)
        s3_keys: dict[UUID, str] = {}
        for msg in eligible:
            if msg.file_data is not None and msg.file_name is not None:
                s3_key = self._s3_storage.generate_s3_key(msg.file_name)
                await self._s3_storage.upload(
                    s3_key, msg.file_data, msg.file_content_type or "application/octet-stream"
                )
                s3_keys[msg.sync_id] = s3_key

        # 2. DB transaction: bulk_insert + bulk_insert_files → commit + close
        records = [
            ToTelegramInsert(
                channel_pair_id=channel_pair.id,
                express_sync_id=msg.sync_id,
                express_chat_id=msg.chat_id,
                express_user_huid=msg.user_huid,
                reply_to_express_sync_id=msg.source_sync_id,
                event_type=EventType(msg.event_type),
            )
            for msg in eligible
        ]

        async with self._session_factory() as session, session.begin():
            inserted_ids = await self._to_telegram_repo.bulk_insert(session, records)

            files_to_insert: list[MessageFileInsert] = []
            for msg, record_id in zip(eligible, inserted_ids, strict=True):
                if record_id is not None and msg.sync_id in s3_keys:
                    files_to_insert.append(
                        MessageFileInsert(
                            direction=MessageDirection.EXPRESS_TO_TG,
                            message_record_id=record_id,
                            file_type=msg.file_type or "document",
                            file_name=msg.file_name,
                            file_content_type=msg.file_content_type,
                            file_size=None,
                            s3_key=s3_keys[msg.sync_id],
                        )
                    )
            if files_to_insert:
                await self._to_telegram_repo.bulk_insert_files(session, files_to_insert)

        # 3. Send each inserted record to Telegram
        sent_count = 0
        for msg, record_id in zip(eligible, inserted_ids, strict=True):
            if record_id is None:
                continue

            event_type = EventType(msg.event_type)
            logger.info("Handling TO_TELEGRAM record_id=%s event_type=%s", record_id, event_type)

            async with self._session_factory() as session, session.begin():
                status = await self._to_telegram_repo.get_status(session, record_id)
                if status == MessageStatus.SENT:
                    logger.info("Skipping already sent record_id=%s", record_id)
                    continue

            try:
                if event_type == EventType.NEW_MESSAGE:
                    await self._handle_new_message(
                        msg,
                        record_id,
                        channel_pair.tg_chat_id,
                        sanitized_bodies.get(msg.sync_id),
                        s3_keys,
                    )
                elif event_type == EventType.EDIT_MESSAGE:
                    await self._handle_edit_message(msg, record_id, sanitized_bodies.get(msg.sync_id))
                elif event_type == EventType.DELETE_MESSAGE:
                    await self._handle_delete_message(msg, record_id)
                sent_count += 1
            except Exception:
                logger.exception("Failed to send record_id=%s to TG", record_id)

        if sent_count:
            logger.info("Sent %d messages to TG for channel_pair_id=%s", sent_count, channel_pair.id)

    async def _handle_new_message(
        self,
        msg: ExpressIncomingDTO,
        record_id: UUID,
        tg_chat_id: int,
        body: str | None,
        s3_keys: dict[UUID, str],
    ) -> None:
        async with self._session_factory() as session, session.begin():
            # Resolve reply
            reply_to_message_id: int | None = None
            if msg.source_sync_id is not None:
                result = await self._mapping_queries.find_tg_message(session, msg.source_sync_id)
                if result is not None:
                    reply_to_message_id = result[0]

            # Employee for header (auto-create if first message)
            employee = await self._employee_repo.find_or_create_by_express_huid(session, msg.user_huid)

        emp = employee if isinstance(employee, Employee) else None
        header = format_header_to_telegram(emp)
        parts = split_to_telegram(header, body)

        # Prepare file data (use in-memory bytes from DTO, avoid S3 re-download)
        file_data = msg.file_data if msg.sync_id in s3_keys else None
        file_type = msg.file_type or "document"
        file_name = msg.file_name

        first_msg_id: int | None = None
        first_chat_id: int | None = None

        for i, part in enumerate(parts):
            msg_id, chat_id = await with_retry(
                self._send_to_telegram,
                chat_id=tg_chat_id,
                text=part,
                reply_to_message_id=reply_to_message_id if i == 0 else None,
                file_data=file_data if i == 0 else None,
                file_type=file_type,
                file_name=file_name,
                max_attempts=self._retry_max_attempts,
                base_delay=self._retry_base_delay,
                max_delay=self._retry_max_delay,
            )
            if i == 0:
                first_msg_id = msg_id
                first_chat_id = chat_id

        if first_msg_id is not None and first_chat_id is not None:
            logger.info(
                "Sent to TG tg_message_id=%d tg_chat_id=%d record_id=%s",
                first_msg_id,
                first_chat_id,
                record_id,
            )
            async with self._session_factory() as session, session.begin():
                await self._to_telegram_repo.mark_sent(session, record_id, first_msg_id, first_chat_id)

    async def _handle_edit_message(
        self,
        msg: ExpressIncomingDTO,
        record_id: UUID,
        body: str | None,
    ) -> None:
        async with self._session_factory() as session, session.begin():
            result = await self._mapping_queries.find_tg_message(session, msg.sync_id)

        if result is None:
            return

        tg_message_id, tg_chat_id = result
        await with_retry(
            self._tg_bot.edit_message_text,
            chat_id=tg_chat_id,
            message_id=tg_message_id,
            text=body or "",
            max_attempts=self._retry_max_attempts,
            base_delay=self._retry_base_delay,
            max_delay=self._retry_max_delay,
        )

        async with self._session_factory() as session, session.begin():
            await self._to_telegram_repo.mark_sent(session, record_id, tg_message_id, tg_chat_id)

    async def _handle_delete_message(self, msg: ExpressIncomingDTO, record_id: UUID) -> None:
        async with self._session_factory() as session, session.begin():
            result = await self._mapping_queries.find_tg_message(session, msg.sync_id)

        if result is None:
            return

        tg_message_id, tg_chat_id = result
        await with_retry(
            self._tg_bot.delete_message,
            chat_id=tg_chat_id,
            message_id=tg_message_id,
            max_attempts=self._retry_max_attempts,
            base_delay=self._retry_base_delay,
            max_delay=self._retry_max_delay,
        )

        async with self._session_factory() as session, session.begin():
            await self._to_telegram_repo.mark_sent(session, record_id, tg_message_id, tg_chat_id)

    async def _send_to_telegram(
        self,
        *,
        chat_id: int,
        text: str,
        reply_to_message_id: int | None = None,
        file_data: bytes | None = None,
        file_type: str = "document",
        file_name: str | None = None,
    ) -> tuple[int, int]:
        reply_params = ReplyParameters(message_id=reply_to_message_id) if reply_to_message_id else None

        if file_data is not None:
            input_file = BufferedInputFile(file_data, filename=file_name or "file")
            match file_type:
                case "image":
                    result = await self._tg_bot.send_photo(
                        chat_id=chat_id,
                        photo=input_file,
                        caption=text or None,
                        reply_parameters=reply_params,
                    )
                case "video":
                    result = await self._tg_bot.send_video(
                        chat_id=chat_id,
                        video=input_file,
                        caption=text or None,
                        reply_parameters=reply_params,
                    )
                case "voice":
                    result = await self._tg_bot.send_voice(
                        chat_id=chat_id,
                        voice=input_file,
                        caption=text or None,
                        reply_parameters=reply_params,
                    )
                case _:
                    result = await self._tg_bot.send_document(
                        chat_id=chat_id,
                        document=input_file,
                        caption=text or None,
                        reply_parameters=reply_params,
                    )
        else:
            result = await self._tg_bot.send_message(
                chat_id=chat_id,
                text=text,
                reply_parameters=reply_params,
            )
        return result.message_id, result.chat.id
