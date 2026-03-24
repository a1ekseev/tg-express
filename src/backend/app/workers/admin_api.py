"""Admin API — FastAPI for channel pair approval, employee management, and file download."""

from __future__ import annotations

import contextlib
import logging
from typing import TYPE_CHECKING
from uuid import UUID

import boto3
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.application.services.approve_service import approve_channel_pair
from app.infrastructure.db.channel_pair_repo import ChannelPairRepo
from app.infrastructure.db.employee_repo import EmployeeRepo
from app.infrastructure.db.session import create_session_factory
from app.infrastructure.express.bot import create_express_bot
from app.infrastructure.http.admin_router import public_router as admin_public_router
from app.infrastructure.http.admin_router import router as admin_router
from app.infrastructure.http.files_router import router as files_router
from app.infrastructure.logging_config import setup_logging
from app.infrastructure.s3.storage import S3Storage
from app.infrastructure.sentry_config import init_sentry
from app.infrastructure.settings import Settings

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

logger = logging.getLogger(__name__)


@contextlib.asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    settings = Settings()  # type: ignore[call-arg]
    init_sentry(settings.sentry_dsn)
    setup_logging(settings.log_level)

    session_factory = create_session_factory(settings.database_url)
    express_bot = create_express_bot(settings)

    s3_client = boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
    )
    s3_storage = S3Storage(s3_client, settings.s3_bucket, settings.file_download_base_url)

    channel_pair_repo = ChannelPairRepo()
    employee_repo = EmployeeRepo()

    async def approve_fn(*, pair_id: object) -> None:
        pid = UUID(str(pair_id))
        async with session_factory() as session, session.begin():
            await approve_channel_pair(
                session=session,
                channel_pair_repo=channel_pair_repo,
                express_bot=express_bot,
                bot_id=settings.express_bot_id,
                pair_id=pid,
                group_prefix=settings.express_group_prefix,
                admin_huids=list(settings.express_admin_huids),
            )

    # --- app.state (used by Depends in routers) ---
    _app.state.session_factory = session_factory
    _app.state.channel_pair_repo = channel_pair_repo
    _app.state.employee_repo = employee_repo
    _app.state.approve_fn = approve_fn
    _app.state.admin_username = settings.admin_username
    _app.state.admin_password = settings.admin_password
    _app.state.jwt_secret_key = settings.jwt_secret_key
    _app.state.s3_storage = s3_storage

    await express_bot.startup()
    try:
        yield
    finally:
        await express_bot.shutdown()


app = FastAPI(title="TG-Express Admin API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,  # type: ignore[arg-type]
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(admin_public_router)
app.include_router(admin_router)
app.include_router(files_router)
