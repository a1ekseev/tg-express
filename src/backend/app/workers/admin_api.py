"""Admin API — FastAPI for channel pair approval, employee management, and file download."""

from __future__ import annotations

import contextlib
import logging
from typing import TYPE_CHECKING
from uuid import UUID

import boto3
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pybotx import ChatTypes

from app.infrastructure.db.channel_pair_repo import ChannelPairRepo
from app.infrastructure.db.employee_repo import EmployeeRepo
from app.infrastructure.db.session import create_session_factory
from app.infrastructure.express.bot import create_express_bot
from app.infrastructure.http.admin_router import public_router as admin_public_router
from app.infrastructure.http.admin_router import router as admin_router
from app.infrastructure.http.admin_router import set_admin_deps
from app.infrastructure.http.files_router import router as files_router
from app.infrastructure.http.files_router import set_s3_storage
from app.infrastructure.logging_config import setup_logging
from app.infrastructure.s3.storage import S3Storage
from app.infrastructure.settings import Settings

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

logger = logging.getLogger(__name__)


@contextlib.asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    settings = Settings()  # type: ignore[call-arg]
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
    set_s3_storage(s3_storage)

    channel_pair_repo = ChannelPairRepo()
    employee_repo = EmployeeRepo()

    async def approve_fn(
        *,
        pair_id: object,
        name: str | None,
        member_huids: list[object],
    ) -> None:
        pid = UUID(str(pair_id))
        request_huids = [UUID(str(h)) for h in member_huids]
        all_huids = list({*settings.express_admin_huids, *request_huids})

        express_chat_id = await express_bot.create_chat(
            bot_id=settings.express_bot_id,
            name=name or "TG-Express Bridge",
            chat_type=ChatTypes.GROUP_CHAT,
            huids=all_huids,
        )

        if settings.express_admin_huids:
            await express_bot.promote_to_chat_admins(
                bot_id=settings.express_bot_id,
                chat_id=express_chat_id,
                huids=settings.express_admin_huids,
            )

        async with session_factory() as session, session.begin():
            await channel_pair_repo.approve(session, pid, express_chat_id)

    set_admin_deps(
        session_factory,
        channel_pair_repo,
        employee_repo,
        approve_fn,
        admin_username=settings.admin_username,
        admin_password=settings.admin_password,
        jwt_secret_key=settings.jwt_secret_key,
    )

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
