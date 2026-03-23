from __future__ import annotations

from collections.abc import Callable, Coroutine
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any
from uuid import UUID  # noqa: TC003 - needed at runtime for path params and pydantic

import jwt
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer
from pydantic import BaseModel

if TYPE_CHECKING:
    from fastapi.security import HTTPAuthorizationCredentials
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from app.infrastructure.db.channel_pair_repo import ChannelPairRepo
    from app.infrastructure.db.employee_repo import EmployeeRepo

ApproveFn = Callable[..., Coroutine[Any, Any, None]]

# Injected at startup
_session_factory: async_sessionmaker[AsyncSession] | None = None
_channel_pair_repo: ChannelPairRepo | None = None
_employee_repo: EmployeeRepo | None = None
_approve_fn: ApproveFn | None = None
_admin_username: str = "admin"
_admin_password: str | None = None
_jwt_secret_key: str | None = None

_bearer_scheme = HTTPBearer()


async def _verify_jwt(credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme)) -> None:  # noqa: B008
    if _jwt_secret_key is None:
        raise HTTPException(status_code=503, detail="Auth not configured")
    try:
        jwt.decode(credentials.credentials, _jwt_secret_key, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")  # noqa: B904
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")  # noqa: B904


# Public router (login)
public_router = APIRouter(prefix="/api/admin")

# Protected router (all other admin endpoints)
router = APIRouter(prefix="/api/admin", dependencies=[Depends(_verify_jwt)])


def set_admin_deps(
    session_factory: async_sessionmaker[AsyncSession],
    channel_pair_repo: ChannelPairRepo,
    employee_repo: EmployeeRepo,
    approve_fn: ApproveFn,
    *,
    admin_username: str,
    admin_password: str,
    jwt_secret_key: str,
) -> None:
    global _session_factory, _channel_pair_repo, _employee_repo, _approve_fn  # noqa: PLW0603
    global _admin_username, _admin_password, _jwt_secret_key  # noqa: PLW0603
    _session_factory = session_factory
    _channel_pair_repo = channel_pair_repo
    _employee_repo = employee_repo
    _approve_fn = approve_fn
    _admin_username = admin_username
    _admin_password = admin_password
    _jwt_secret_key = jwt_secret_key


# --- Schemas ---


class LoginRequest(BaseModel):
    username: str
    password: str


class ApproveRequest(BaseModel):
    name: str | None = None
    member_huids: list[UUID] = []  # noqa: RUF012


class EmployeeUpdateRequest(BaseModel):
    full_name: str | None = None
    position: str | None = None


# --- Auth ---


@public_router.post("/login")
async def login(body: LoginRequest) -> dict[str, str]:
    if _admin_password is None or _jwt_secret_key is None:
        raise HTTPException(status_code=503, detail="Auth not configured")
    if body.username != _admin_username or body.password != _admin_password:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = jwt.encode(
        {"sub": body.username, "exp": datetime.now(UTC) + timedelta(hours=24)},
        _jwt_secret_key,
        algorithm="HS256",
    )
    return {"access_token": token}


# --- Channel Pairs ---


@router.get("/channel-pairs")
async def list_channel_pairs() -> list[dict[str, object]]:
    if _session_factory is None or _channel_pair_repo is None:
        raise HTTPException(status_code=503)
    async with _session_factory() as session:
        pairs = await _channel_pair_repo.list_all(session)
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
async def get_channel_pair(pair_id: UUID) -> dict[str, object]:
    if _session_factory is None or _channel_pair_repo is None:
        raise HTTPException(status_code=503)
    async with _session_factory() as session:
        pair = await _channel_pair_repo.get(session, pair_id)
    return {
        "id": str(pair.id),
        "tg_chat_id": pair.tg_chat_id,
        "express_chat_id": str(pair.express_chat_id) if pair.express_chat_id else None,
        "is_approved": pair.is_approved,
        "name": pair.name,
    }


@router.post("/channel-pairs/{pair_id}/approve")
async def approve_channel_pair(pair_id: UUID, body: ApproveRequest) -> dict[str, str]:
    if _session_factory is None or _channel_pair_repo is None or _approve_fn is None:
        raise HTTPException(status_code=503)

    async with _session_factory() as session:
        pair = await _channel_pair_repo.get(session, pair_id)
        if pair.is_approved:
            raise HTTPException(status_code=400, detail="Already approved")

    if _approve_fn is not None:
        await _approve_fn(pair_id=pair_id, name=body.name or pair.name, member_huids=body.member_huids)

    return {"status": "approved"}


# --- Employees ---


@router.get("/employees")
async def list_employees() -> list[dict[str, object]]:
    if _session_factory is None or _employee_repo is None:
        raise HTTPException(status_code=503)
    async with _session_factory() as session:
        employees = await _employee_repo.list_all(session)
    return [
        {
            "id": str(e.id),
            "tg_user_id": e.tg_user_id,
            "express_huid": str(e.express_huid) if e.express_huid else None,
            "full_name": e.full_name,
            "position": e.position,
        }
        for e in employees
    ]


@router.put("/employees/{employee_id}")
async def update_employee(employee_id: UUID, body: EmployeeUpdateRequest) -> dict[str, str]:
    if _session_factory is None or _employee_repo is None:
        raise HTTPException(status_code=503)
    async with _session_factory() as session, session.begin():
        await _employee_repo.update(
            session,
            employee_id,
            full_name=body.full_name,
            position=body.position,
        )
    return {"status": "updated"}


@router.delete("/employees/{employee_id}")
async def delete_employee(employee_id: UUID) -> dict[str, str]:
    if _session_factory is None or _employee_repo is None:
        raise HTTPException(status_code=503)
    async with _session_factory() as session, session.begin():
        await _employee_repo.delete(session, employee_id)
    return {"status": "deleted"}
