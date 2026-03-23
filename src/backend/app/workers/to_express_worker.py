"""To Express Worker — TG polling → DB → S3 → Express API."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import TYPE_CHECKING

import boto3
from aiogram import Router
from fastapi import FastAPI

from app.application.services.to_express_service import ToExpressService
from app.infrastructure.db.channel_pair_repo import ChannelPairRepo
from app.infrastructure.db.employee_repo import EmployeeRepo
from app.infrastructure.db.mapping_queries import MappingQueries
from app.infrastructure.db.session import create_session_factory
from app.infrastructure.db.to_express_repo import ToExpressRepo
from app.infrastructure.express.bot import create_express_bot
from app.infrastructure.logging_config import setup_logging
from app.infrastructure.s3.storage import S3Storage
from app.infrastructure.settings import Settings
from app.infrastructure.telegram.bot import create_dispatcher, create_tg_bot
from app.infrastructure.telegram.converters import message_to_dto

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from aiogram.types import Message

    from app.application.dto import TgIncomingDTO

logger = logging.getLogger(__name__)


@contextlib.asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    settings = Settings()  # type: ignore[call-arg]
    setup_logging(settings.log_level)

    session_factory = create_session_factory(settings.database_url)

    s3_client = boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
    )
    s3_storage = S3Storage(s3_client, settings.s3_bucket, settings.file_download_base_url)

    await s3_storage.ensure_bucket()
    if settings.s3_file_ttl_days is not None:
        await s3_storage.configure_lifecycle(settings.s3_file_ttl_days)

    express_bot = create_express_bot(settings)

    service = ToExpressService(
        session_factory=session_factory,
        to_express_repo=ToExpressRepo(),
        channel_pair_repo=ChannelPairRepo(),
        mapping_queries=MappingQueries(),
        employee_repo=EmployeeRepo(),
        s3_storage=s3_storage,
        settings=settings,
        express_bot=express_bot,
    )

    bot = create_tg_bot(settings)
    dp = create_dispatcher()
    router = Router()

    async def _download_file(dto: TgIncomingDTO) -> TgIncomingDTO:
        if dto.file_id is None:
            return dto
        file_bytes = await bot.download(dto.file_id)
        if file_bytes is None:
            return dto
        return dto.model_copy(update={"file_data": file_bytes.read()})

    @router.message()
    async def on_message(message: Message) -> None:
        dto = await _download_file(message_to_dto(message))
        logger.info(
            "TG message received tg_message_id=%d tg_chat_id=%d content_type=%s",
            dto.tg_message_id,
            dto.tg_chat_id,
            dto.content_type,
        )
        await service.handle_batch([dto])

    @router.edited_message()
    async def on_edited_message(message: Message) -> None:
        dto = await _download_file(message_to_dto(message))
        dto = dto.model_copy(update={"event_type": "edit_message"})
        logger.info("TG edited message tg_message_id=%d tg_chat_id=%d", dto.tg_message_id, dto.tg_chat_id)
        await service.handle_batch([dto])

    dp.include_router(router)

    await express_bot.startup()
    polling_task = asyncio.create_task(dp.start_polling(bot, handle_signals=False, close_bot_session=False))
    try:
        yield
    finally:
        polling_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await polling_task
        await express_bot.shutdown()
        await bot.session.close()


app = FastAPI(lifespan=lifespan)
