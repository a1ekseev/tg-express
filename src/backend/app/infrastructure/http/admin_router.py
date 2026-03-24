from __future__ import annotations

import hmac
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from uuid import UUID  # noqa: TC003 - needed at runtime for path params and pydantic

import jwt
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer
from pydantic import BaseModel

from app.infrastructure.db.employee_repo import UNSET
from app.infrastructure.http.deps import (
    get_admin_credentials,
    get_approve_fn,
    get_channel_pair_repo,
    get_employee_repo,
    get_jwt_secret_key,
    get_session_factory,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine
    from typing import Any

    from fastapi.security import HTTPAuthorizationCredentials
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from app.infrastructure.db.channel_pair_repo import ChannelPairRepo
    from app.infrastructure.db.employee_repo import EmployeeRepo

_bearer_scheme = HTTPBearer()


async def _verify_jwt(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),  # noqa: B008
    jwt_secret: str = Depends(get_jwt_secret_key),  # noqa: B008
) -> None:
    try:
        jwt.decode(credentials.credentials, jwt_secret, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")  # noqa: B904
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")  # noqa: B904


# Public router (login)
public_router = APIRouter(prefix="/api/admin")

# Protected router (all other admin endpoints)
router = APIRouter(prefix="/api/admin", dependencies=[Depends(_verify_jwt)])


# --- Schemas ---


class LoginRequest(BaseModel):
    username: str
    password: str


class EmployeeUpdateRequest(BaseModel):
    full_name: str | None = None
    position: str | None = None


# --- Auth ---


@public_router.post("/login")
async def login(
    body: LoginRequest,
    credentials: tuple[str, str] = Depends(get_admin_credentials),  # noqa: B008
    jwt_secret: str = Depends(get_jwt_secret_key),  # noqa: B008
) -> dict[str, str]:
    admin_username, admin_password = credentials
    username_ok = hmac.compare_digest(body.username, admin_username)
    password_ok = hmac.compare_digest(body.password, admin_password)
    if not (username_ok and password_ok):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = jwt.encode(
        {"sub": body.username, "exp": datetime.now(UTC) + timedelta(hours=24)},
        jwt_secret,
        algorithm="HS256",
    )
    return {"access_token": token}


# --- Channel Pairs ---


@router.get("/channel-pairs")
async def list_channel_pairs(
    session_factory: async_sessionmaker[AsyncSession] = Depends(get_session_factory),  # noqa: B008
    repo: ChannelPairRepo = Depends(get_channel_pair_repo),  # noqa: B008
) -> list[dict[str, object]]:
    async with session_factory() as session:
        pairs = await repo.list_all(session)
    return [
        {
            "id": str(p.id),
            "tg_chat_id": p.tg_chat_id,
            "express_chat_id": str(p.express_chat_id) if p.express_chat_id else None,
            "is_approved": p.is_approved,
            "name": p.name,
        }
        for p in pairs
    ]


@router.get("/channel-pairs/{pair_id}")
async def get_channel_pair(
    pair_id: UUID,
    session_factory: async_sessionmaker[AsyncSession] = Depends(get_session_factory),  # noqa: B008
    repo: ChannelPairRepo = Depends(get_channel_pair_repo),  # noqa: B008
) -> dict[str, object]:
    async with session_factory() as session:
        pair = await repo.get(session, pair_id)
    return {
        "id": str(pair.id),
        "tg_chat_id": pair.tg_chat_id,
        "express_chat_id": str(pair.express_chat_id) if pair.express_chat_id else None,
        "is_approved": pair.is_approved,
        "name": pair.name,
    }


@router.post("/channel-pairs/{pair_id}/approve")
async def approve_channel_pair(
    pair_id: UUID,
    approve_fn: Callable[..., Coroutine[Any, Any, None]] = Depends(get_approve_fn),  # noqa: B008
) -> dict[str, str]:
    await approve_fn(pair_id=pair_id)
    return {"status": "approved"}


# --- Employees ---


@router.get("/employees")
async def list_employees(
    session_factory: async_sessionmaker[AsyncSession] = Depends(get_session_factory),  # noqa: B008
    repo: EmployeeRepo = Depends(get_employee_repo),  # noqa: B008
) -> list[dict[str, object]]:
    async with session_factory() as session:
        employees = await repo.list_all(session)
    return [
        {
            "id": str(e.id),
            "tg_user_id": e.tg_user_id,
            "express_huid": str(e.express_huid) if e.express_huid else None,
            "full_name": e.full_name,
            "position": e.position,
            "tg_name": e.tg_name,
            "express_name": e.express_name,
        }
        for e in employees
    ]


@router.put("/employees/{employee_id}")
async def update_employee(
    employee_id: UUID,
    body: EmployeeUpdateRequest,
    session_factory: async_sessionmaker[AsyncSession] = Depends(get_session_factory),  # noqa: B008
    repo: EmployeeRepo = Depends(get_employee_repo),  # noqa: B008
) -> dict[str, str]:
    async with session_factory() as session, session.begin():
        await repo.update(
            session,
            employee_id,
            full_name=body.full_name if "full_name" in body.model_fields_set else UNSET,
            position=body.position if "position" in body.model_fields_set else UNSET,
        )
    return {"status": "updated"}


@router.delete("/employees/{employee_id}")
async def delete_employee(
    employee_id: UUID,
    session_factory: async_sessionmaker[AsyncSession] = Depends(get_session_factory),  # noqa: B008
    repo: EmployeeRepo = Depends(get_employee_repo),  # noqa: B008
) -> dict[str, str]:
    async with session_factory() as session, session.begin():
        await repo.delete(session, employee_id)
    return {"status": "deleted"}
