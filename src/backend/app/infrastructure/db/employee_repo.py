from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import select

from app.domain.models import Employee
from app.infrastructure.db.models import EmployeeModel

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession


class EmployeeRepo:
    @staticmethod
    async def find_by_tg_user_id(session: AsyncSession, tg_user_id: int) -> Employee | None:
        stmt = select(EmployeeModel).where(EmployeeModel.tg_user_id == tg_user_id)
        row = (await session.execute(stmt)).scalar_one_or_none()
        if row is None:
            return None
        return _to_domain(row)

    @staticmethod
    async def find_by_express_huid(session: AsyncSession, express_huid: UUID) -> Employee | None:
        stmt = select(EmployeeModel).where(EmployeeModel.express_huid == express_huid)
        row = (await session.execute(stmt)).scalar_one_or_none()
        if row is None:
            return None
        return _to_domain(row)

    @staticmethod
    async def find_or_create_by_tg_user_id(session: AsyncSession, tg_user_id: int) -> Employee:
        stmt = select(EmployeeModel).where(EmployeeModel.tg_user_id == tg_user_id)
        row = (await session.execute(stmt)).scalar_one_or_none()
        if row is not None:
            return _to_domain(row)
        model = EmployeeModel(id=uuid4(), tg_user_id=tg_user_id)
        session.add(model)
        await session.flush()
        return _to_domain(model)

    @staticmethod
    async def find_or_create_by_express_huid(session: AsyncSession, express_huid: UUID) -> Employee:
        stmt = select(EmployeeModel).where(EmployeeModel.express_huid == express_huid)
        row = (await session.execute(stmt)).scalar_one_or_none()
        if row is not None:
            return _to_domain(row)
        model = EmployeeModel(id=uuid4(), express_huid=express_huid)
        session.add(model)
        await session.flush()
        return _to_domain(model)

    @staticmethod
    async def create(
        session: AsyncSession,
        *,
        tg_user_id: int | None = None,
        express_huid: UUID | None = None,
        full_name: str | None = None,
        position: str | None = None,
    ) -> Employee:
        model = EmployeeModel(
            id=uuid4(),
            tg_user_id=tg_user_id,
            express_huid=express_huid,
            full_name=full_name,
            position=position,
        )
        session.add(model)
        await session.flush()
        return _to_domain(model)

    @staticmethod
    async def update(
        session: AsyncSession,
        employee_id: UUID,
        *,
        full_name: str | None = None,
        position: str | None = None,
    ) -> None:
        stmt = select(EmployeeModel).where(EmployeeModel.id == employee_id)
        row = (await session.execute(stmt)).scalar_one()
        if full_name is not None:
            row.full_name = full_name
        if position is not None:
            row.position = position
        await session.flush()

    @staticmethod
    async def delete(session: AsyncSession, employee_id: UUID) -> None:
        stmt = select(EmployeeModel).where(EmployeeModel.id == employee_id)
        row = (await session.execute(stmt)).scalar_one()
        await session.delete(row)
        await session.flush()

    @staticmethod
    async def list_all(session: AsyncSession) -> list[Employee]:
        stmt = select(EmployeeModel).order_by(EmployeeModel.created_at.desc())
        rows = (await session.execute(stmt)).scalars().all()
        return [_to_domain(r) for r in rows]


def _to_domain(model: EmployeeModel) -> Employee:
    return Employee(
        id=model.id,
        tg_user_id=model.tg_user_id,
        express_huid=model.express_huid,
        full_name=model.full_name,
        position=model.position,
    )
