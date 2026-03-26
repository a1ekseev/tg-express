"""Service: TG polling → DB → S3 → Express API (merged ingress + egress)."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from pybotx.models.attachments import OutgoingAttachment

from app.application.services.approve_service import approve_channel_pair
from app.application.utils.message_filter import classify_tg_message
from app.application.utils.message_formatter import format_attachments_block, format_header_to_express
from app.application.utils.message_splitter import split_to_express
from app.application.utils.retry import with_retry
from app.application.utils.sanitize import sanitize_to_express
from app.domain.models import EventType, MessageDirection, MessageStatus, SystemChannelReason, TgMessageAction
from app.infrastructure.db.to_express_repo import MessageFileInsert, ToExpressInsert
from app.infrastructure.express.bot import edit_in_express, send_to_express

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from uuid import UUID

    from pybotx import Bot
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from app.application.dto import TgIncomingDTO
    from app.domain.models import ChannelPair
    from app.infrastructure.db.channel_pair_repo import ChannelPairRepo
    from app.infrastructure.db.employee_repo import EmployeeRepo
    from app.infrastructure.db.mapping_queries import MappingQueries
    from app.infrastructure.db.to_express_repo import ToExpressRepo
    from app.infrastructure.s3.storage import S3Storage
    from app.infrastructure.settings import Settings


class ToExpressService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        to_express_repo: ToExpressRepo,
        channel_pair_repo: ChannelPairRepo,
        mapping_queries: MappingQueries,
        employee_repo: EmployeeRepo,
        s3_storage: S3Storage,
        settings: Settings,
        express_bot: Bot,
    ) -> None:
        self._session_factory = session_factory
        self._to_express_repo = to_express_repo
        self._channel_pair_repo = channel_pair_repo
        self._mapping_queries = mapping_queries
        self._employee_repo = employee_repo
        self._s3_storage = s3_storage
        self._settings = settings
        self._express_bot = express_bot

    async def handle_batch(self, messages: list[TgIncomingDTO]) -> None:
        if not messages:
            return

        logger.info("Processing %d TG messages for tg_chat_id=%d", len(messages), messages[0].tg_chat_id)

        # 0. Classify each message
        classified = [(msg, classify_tg_message(msg.content_type)) for msg in messages]
        forward_msgs = [m for m, action in classified if action == TgMessageAction.FORWARD]
        system_msgs = [m for m, action in classified if action == TgMessageAction.SYSTEM]
        skip_msgs = [m for m, action in classified if action == TgMessageAction.SKIP]
        if skip_msgs:
            types = ", ".join(m.content_type for m in skip_msgs)
            logger.debug("Skipped %d messages (types: %s)", len(skip_msgs), types)

        # 0.1. Lookup/create channel_pair (upsert — safe under concurrency)
        async with self._session_factory() as session, session.begin():
            channel_pair = await self._channel_pair_repo.get_or_create_unapproved(
                session,
                tg_chat_id=messages[0].tg_chat_id,
                name=messages[0].chat_title,
            )

        # 0.2. Unapproved -> auto-approve or system channel
        if not channel_pair.is_approved:
            if self._settings.auto_approve_channels:
                channel_pair = await self._auto_approve(channel_pair)
            else:
                logger.warning("Unapproved channel tg_chat_id=%d, routing to system channel", messages[0].tg_chat_id)
                for msg in forward_msgs + system_msgs:
                    await self._send_system_channel(
                        tg_chat_title=msg.chat_title or "",
                        tg_user_name=msg.sender_name,
                        content_type=msg.content_type,
                        reason=SystemChannelReason.UNAPPROVED_CHANNEL,
                    )
                return

        # 0.3. Approved, but SYSTEM messages -> system channel
        for msg in system_msgs:
            await self._send_system_channel(
                tg_chat_title=msg.chat_title or "",
                tg_user_name=msg.sender_name,
                content_type=msg.content_type,
                reason=SystemChannelReason.UNSUPPORTED_TYPE,
            )

        if not forward_msgs:
            return

        # 0.4. Sanitize FORWARD messages
        sanitized_bodies: dict[int, str | None] = {}
        for msg in forward_msgs:
            sanitized_bodies[msg.tg_message_id] = sanitize_to_express(msg.body, msg.entities)

        # 0.5. Filter out empty messages (no text after sanitize, no file)
        non_empty = [m for m in forward_msgs if sanitized_bodies.get(m.tg_message_id) or m.file_data is not None]
        skipped_empty = len(forward_msgs) - len(non_empty)
        if skipped_empty:
            logger.warning("Skipped %d empty TG messages (no text after sanitize, no file)", skipped_empty)
        if not non_empty:
            return
        forward_msgs = non_empty

        # 1. Upload files to S3 (outside transaction)
        s3_keys: dict[int, str] = {}
        for msg in forward_msgs:
            if msg.file_data is not None and msg.file_name is not None:
                s3_key = self._s3_storage.generate_s3_key(msg.file_name)
                await self._s3_storage.upload(
                    s3_key,
                    msg.file_data,
                    msg.file_content_type or "application/octet-stream",
                    filename=msg.file_name,
                )
                s3_keys[msg.tg_message_id] = s3_key

        # 2. DB transaction: bulk_insert + bulk_insert_files → commit + close
        records = [
            ToExpressInsert(
                channel_pair_id=channel_pair.id,
                tg_message_id=msg.tg_message_id,
                tg_chat_id=msg.tg_chat_id,
                tg_user_id=msg.tg_user_id,
                tg_media_group_id=msg.media_group_id,
                reply_to_tg_message_id=msg.reply_to_message_id,
                event_type=EventType(msg.event_type),
            )
            for msg in forward_msgs
        ]

        async with self._session_factory() as session, session.begin():
            inserted_ids = await self._to_express_repo.bulk_insert(session, records)

            files_to_insert: list[MessageFileInsert] = []
            for msg, record_id in zip(forward_msgs, inserted_ids, strict=True):
                if record_id is not None and msg.tg_message_id in s3_keys:
                    files_to_insert.append(
                        MessageFileInsert(
                            direction=MessageDirection.TG_TO_EXPRESS,
                            message_record_id=record_id,
                            file_type=msg.content_type,
                            file_name=msg.file_name,
                            file_content_type=msg.file_content_type,
                            file_size=msg.file_size,
                            s3_key=s3_keys[msg.tg_message_id],
                        )
                    )
            if files_to_insert:
                await self._to_express_repo.bulk_insert_files(session, files_to_insert)

        # 3. Send each inserted record to Express
        if channel_pair.express_chat_id is None:
            logger.error("express_chat_id is None for approved pair=%s, skipping send", channel_pair.id)
            return
        sent_count = 0
        for msg, record_id in zip(forward_msgs, inserted_ids, strict=True):
            if record_id is None:
                continue

            try:
                await self._send_record_to_express(
                    msg,
                    record_id,
                    channel_pair.express_chat_id,
                    sanitized_bodies,
                    s3_keys,
                )
                sent_count += 1
            except Exception:
                logger.exception("Failed to send record_id=%s to Express", record_id)

        if sent_count:
            logger.info(
                "Sent %d messages to Express chat_id=%s (pair=%s, name=%s)",
                sent_count,
                channel_pair.express_chat_id,
                channel_pair.id,
                channel_pair.name,
            )

    async def _send_record_to_express(
        self,
        msg: TgIncomingDTO,
        record_id: UUID,
        express_chat_id: UUID,
        sanitized_bodies: dict[int, str | None],
        s3_keys: dict[int, str],
    ) -> None:
        event_type = EventType(msg.event_type)

        if event_type == EventType.EDIT_MESSAGE:
            await self._handle_edit_to_express(msg, record_id, sanitized_bodies)
            return

        async with self._session_factory() as session, session.begin():
            status = await self._to_express_repo.get_status(session, record_id)
            if status == MessageStatus.SENT:
                logger.info("Skipping already sent record_id=%s", record_id)
                return

            # Employee for header (auto-create if first message, update tg_name)
            employee = await self._employee_repo.find_or_create_by_tg_user_id(
                session, msg.tg_user_id, name=msg.sender_name
            )

        header = format_header_to_express(employee, tg_sender_name=msg.sender_name)
        body = sanitized_bodies.get(msg.tg_message_id)
        has_file = msg.tg_message_id in s3_keys

        # Send text (header + body) only if there's actual body content
        # Skip header-only message when it's a file-only message (e.g. media_group photo without caption)
        first_sync_id: UUID | None = None
        if body or not has_file:
            parts = split_to_express(header, body, None)
            for i, part in enumerate(parts):
                sync_id = await with_retry(
                    send_to_express,
                    self._express_bot,
                    bot_id=self._settings.express_bot_id,
                    chat_id=express_chat_id,
                    body=part,
                    wait_callback=self._settings.express_wait_callback,
                    max_attempts=self._settings.retry_max_attempts,
                    base_delay=self._settings.retry_base_delay,
                    max_delay=self._settings.retry_max_delay,
                )
                if i == 0:
                    first_sync_id = sync_id

        if first_sync_id is not None:
            logger.info("Sent to Express sync_id=%s record_id=%s", first_sync_id, record_id)
            async with self._session_factory() as session, session.begin():
                await self._to_express_repo.mark_sent(session, record_id, first_sync_id)

        # Files: try API attachment first, fallback to Markdown link
        if has_file:
            file_sent = False
            if msg.file_data is not None:
                try:
                    attachment = OutgoingAttachment(
                        content=msg.file_data,
                        filename=msg.file_name or "file",
                    )
                    await with_retry(
                        send_to_express,
                        self._express_bot,
                        bot_id=self._settings.express_bot_id,
                        chat_id=express_chat_id,
                        body="",
                        file=attachment,
                        wait_callback=self._settings.express_wait_callback,
                        max_attempts=self._settings.retry_max_attempts,
                        base_delay=self._settings.retry_base_delay,
                        max_delay=self._settings.retry_max_delay,
                    )
                    file_sent = True
                except Exception:  # noqa: BLE001
                    logger.warning("Failed to send file via Express API, falling back to link")

            if not file_sent:
                files = [(self._s3_storage.get_download_url(s3_keys[msg.tg_message_id]), msg.file_name)]
                attachments_block = format_attachments_block(files)
                await with_retry(
                    send_to_express,
                    self._express_bot,
                    bot_id=self._settings.express_bot_id,
                    chat_id=express_chat_id,
                    body=attachments_block,
                    wait_callback=self._settings.express_wait_callback,
                    max_attempts=self._settings.retry_max_attempts,
                    base_delay=self._settings.retry_base_delay,
                    max_delay=self._settings.retry_max_delay,
                )

    async def _handle_edit_to_express(
        self,
        msg: TgIncomingDTO,
        record_id: UUID,
        sanitized_bodies: dict[int, str | None],
    ) -> None:
        """Edit an existing Express message (TG message was edited)."""
        async with self._session_factory() as session, session.begin():
            express_sync_id = await self._mapping_queries.find_express_sync_id(
                session, msg.tg_chat_id, msg.tg_message_id
            )
            employee = await self._employee_repo.find_or_create_by_tg_user_id(
                session, msg.tg_user_id, name=msg.sender_name
            )

        if express_sync_id is None:
            logger.warning("Cannot edit: original express_sync_id not found for tg_message_id=%d", msg.tg_message_id)
            return

        body = sanitized_bodies.get(msg.tg_message_id)
        if not body:
            logger.warning("Skipping edit with empty body for tg_message_id=%d", msg.tg_message_id)
            return

        header = format_header_to_express(employee, tg_sender_name=msg.sender_name)
        full_text = header + "\n" + body

        await with_retry(
            edit_in_express,
            self._express_bot,
            bot_id=self._settings.express_bot_id,
            sync_id=express_sync_id,
            body=full_text,
            max_attempts=self._settings.retry_max_attempts,
            base_delay=self._settings.retry_base_delay,
            max_delay=self._settings.retry_max_delay,
        )

        logger.info("Edited Express sync_id=%s record_id=%s", express_sync_id, record_id)
        async with self._session_factory() as session, session.begin():
            await self._to_express_repo.mark_sent(session, record_id, express_sync_id)

    async def _auto_approve(self, channel_pair: ChannelPair) -> ChannelPair:
        """Auto-approve channel pair under FOR UPDATE lock."""
        async with self._session_factory() as session, session.begin():
            result = await approve_channel_pair(
                session=session,
                channel_pair_repo=self._channel_pair_repo,
                express_bot=self._express_bot,
                bot_id=self._settings.express_bot_id,
                pair_id=channel_pair.id,
                group_prefix=self._settings.express_group_prefix,
                admin_huids=list(self._settings.express_admin_huids),
            )
        return result if result is not None else channel_pair

    async def _send_system_channel(
        self,
        *,
        tg_chat_title: str,
        tg_user_name: str,
        content_type: str,
        reason: SystemChannelReason,
    ) -> None:
        if reason == SystemChannelReason.UNAPPROVED_CHANNEL:
            body = f"[TG: {tg_chat_title}] (не одобрен) {tg_user_name}: {content_type}"
        else:
            body = f"[TG: {tg_chat_title}] {tg_user_name}: {content_type} (не поддерживается)"

        try:
            await send_to_express(
                self._express_bot,
                bot_id=self._settings.express_bot_id,
                chat_id=self._settings.express_system_channel_id,
                body=body,
                wait_callback=self._settings.express_wait_callback,
            )
        except Exception:
            logger.exception("Failed to send system channel message")
