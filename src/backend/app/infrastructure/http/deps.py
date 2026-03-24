"""FastAPI dependency providers — extract from app.state set in lifespan."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import HTTPException, Request  # noqa: TC002 - Request must be runtime for FastAPI DI

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine
    from typing import Any

    from pybotx import Bot
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from app.infrastructure.db.channel_pair_repo import ChannelPairRepo
    from app.infrastructure.db.employee_repo import EmployeeRepo
    from app.infrastructure.s3.storage import S3Storage


def get_express_bot(request: Request) -> Bot:
    bot = getattr(request.app.state, "express_bot", None)
    if bot is None:
        raise HTTPException(status_code=503, detail="Bot not initialized")
    return bot


def get_s3_storage(request: Request) -> S3Storage:
    storage = getattr(request.app.state, "s3_storage", None)
    if storage is None:
        raise HTTPException(status_code=503, detail="Storage not initialized")
    return storage


def get_session_factory(request: Request) -> async_sessionmaker[AsyncSession]:
    factory = getattr(request.app.state, "session_factory", None)
    if factory is None:
        raise HTTPException(status_code=503, detail="Database not initialized")
    return factory


def get_channel_pair_repo(request: Request) -> ChannelPairRepo:
    repo = getattr(request.app.state, "channel_pair_repo", None)
    if repo is None:
        raise HTTPException(status_code=503, detail="Not initialized")
    return repo


def get_employee_repo(request: Request) -> EmployeeRepo:
    repo = getattr(request.app.state, "employee_repo", None)
    if repo is None:
        raise HTTPException(status_code=503, detail="Not initialized")
    return repo


def get_approve_fn(request: Request) -> Callable[..., Coroutine[Any, Any, None]]:
    fn = getattr(request.app.state, "approve_fn", None)
    if fn is None:
        raise HTTPException(status_code=503, detail="Not initialized")
    return fn


def get_jwt_secret_key(request: Request) -> str:
    key = getattr(request.app.state, "jwt_secret_key", None)
    if key is None:
        raise HTTPException(status_code=503, detail="Auth not configured")
    return key


def get_admin_credentials(request: Request) -> tuple[str, str]:
    username = getattr(request.app.state, "admin_username", None)
    password = getattr(request.app.state, "admin_password", None)
    if username is None or password is None:
        raise HTTPException(status_code=503, detail="Auth not configured")
    return username, password
