"""To Telegram Worker — Express webhook → DB → S3 → Telegram API."""

from __future__ import annotations

import contextlib
import logging
from typing import TYPE_CHECKING

import boto3
from fastapi import FastAPI

from app.application.services.to_telegram_service import ToTelegramService
from app.infrastructure.db.channel_pair_repo import ChannelPairRepo
from app.infrastructure.db.employee_repo import EmployeeRepo
from app.infrastructure.db.mapping_queries import MappingQueries
from app.infrastructure.db.session import create_session_factory
from app.infrastructure.db.to_telegram_repo import ToTelegramRepo
from app.infrastructure.express.bot import create_express_bot
from app.infrastructure.express.handlers import set_system_channel_id, set_webhook_service
from app.infrastructure.http.express_webhook_router import router as webhook_router
from app.infrastructure.http.express_webhook_router import set_express_bot
from app.infrastructure.logging_config import setup_logging
from app.infrastructure.s3.storage import S3Storage
from app.infrastructure.settings import Settings
from app.infrastructure.telegram.bot import create_tg_bot

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

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

    tg_bot = create_tg_bot(settings)

    service = ToTelegramService(
        session_factory=session_factory,
        to_telegram_repo=ToTelegramRepo(),
        channel_pair_repo=ChannelPairRepo(),
        mapping_queries=MappingQueries(),
        employee_repo=EmployeeRepo(),
        s3_storage=s3_storage,
        tg_bot=tg_bot,
        retry_max_attempts=settings.retry_max_attempts,
        retry_base_delay=settings.retry_base_delay,
        retry_max_delay=settings.retry_max_delay,
    )
    set_webhook_service(service)
    set_system_channel_id(settings.express_system_channel_id)

    express_bot = create_express_bot(settings)
    set_express_bot(express_bot)

    await express_bot.startup()
    try:
        yield
    finally:
        await express_bot.shutdown()
        await tg_bot.session.close()


app = FastAPI(lifespan=lifespan)
app.include_router(webhook_router)
