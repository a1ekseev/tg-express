"""Tests for SystemCommandHandler."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.application.services.system_commands import (
    MAX_FULLNAME_LENGTH,
    MAX_POSITION_LENGTH,
    SystemCommandHandler,
)
from app.domain.models import ChannelPair, Employee

if TYPE_CHECKING:
    from uuid import UUID


def _make_handler(
    *,
    channel_pairs: list[ChannelPair] | None = None,
    employees: list[Employee] | None = None,
) -> SystemCommandHandler:
    mock_session = MagicMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_session.begin = MagicMock(return_value=mock_session)
    mock_session_factory = MagicMock(return_value=mock_session)

    mock_channel_pair_repo = MagicMock()
    mock_channel_pair_repo.find_by_tg_chat_id = AsyncMock(
        return_value=channel_pairs[0] if channel_pairs else None
    )
    mock_channel_pair_repo.get_for_update = AsyncMock(
        return_value=channel_pairs[0] if channel_pairs else None
    )
    mock_channel_pair_repo.approve = AsyncMock()
    mock_channel_pair_repo.list_all = AsyncMock(return_value=channel_pairs or [])

    mock_employee_repo = MagicMock()

    def _find_by_tg(session: object, tg_user_id: int) -> Employee | None:  # noqa: ARG001
        return next((e for e in (employees or []) if e.tg_user_id == tg_user_id), None)

    def _find_by_express(session: object, express_huid: UUID) -> Employee | None:  # noqa: ARG001
        return next((e for e in (employees or []) if e.express_huid == express_huid), None)

    mock_employee_repo.find_by_tg_user_id = AsyncMock(side_effect=_find_by_tg)
    mock_employee_repo.find_by_express_huid = AsyncMock(side_effect=_find_by_express)
    mock_employee_repo.update = AsyncMock()
    mock_employee_repo.list_all = AsyncMock(return_value=employees or [])

    mock_s3 = MagicMock()
    mock_s3.head_object = AsyncMock(return_value={"filename": "test.pdf"})
    mock_s3.download = AsyncMock(return_value=(b"file-content", "application/pdf"))

    mock_bot = MagicMock()
    mock_bot.send_message = AsyncMock(return_value=uuid4())
    mock_bot.create_chat = AsyncMock(return_value=uuid4())
    mock_bot.promote_to_chat_admins = AsyncMock()

    return SystemCommandHandler(
        session_factory=mock_session_factory,
        channel_pair_repo=mock_channel_pair_repo,
        employee_repo=mock_employee_repo,
        s3_storage=mock_s3,
        express_bot=mock_bot,
        bot_id=uuid4(),
        system_channel_id=uuid4(),
        group_prefix="[T<->E]",
        admin_huids=[uuid4()],
        wait_callback=False,
    )


def _make_employee(
    *,
    tg_user_id: int | None = None,
    express_huid: UUID | None = None,
) -> Employee:
    return Employee(
        id=uuid4(),
        tg_user_id=tg_user_id,
        express_huid=express_huid,
        full_name=None,
        position=None,
        tg_name=None,
        express_name=None,
    )


def _make_pair(*, tg_chat_id: int = -1001, is_approved: bool = False) -> ChannelPair:
    return ChannelPair(
        id=uuid4(),
        tg_chat_id=tg_chat_id,
        express_chat_id=uuid4() if is_approved else None,
        is_approved=is_approved,
        name="Test Group",
    )


def _reply_body(handler: SystemCommandHandler) -> str:
    return handler._bot.send_message.call_args.kwargs["body"]  # type: ignore[union-attr]  # noqa: SLF001


def _reply_kwargs(handler: SystemCommandHandler) -> dict[str, object]:
    return handler._bot.send_message.call_args.kwargs  # type: ignore[union-attr]  # noqa: SLF001


class TestUnknownCommand:
    @pytest.mark.asyncio
    async def test_unknown_command_replies(self) -> None:
        handler = _make_handler()
        await handler.handle("/foobar")
        handler._bot.send_message.assert_called_once()  # type: ignore[union-attr]  # noqa: SLF001
        assert "Неизвестная команда" in _reply_body(handler)

    @pytest.mark.asyncio
    async def test_non_command_ignored(self) -> None:
        handler = _make_handler()
        await handler.handle("just text")
        handler._bot.send_message.assert_not_called()  # type: ignore[union-attr]  # noqa: SLF001


class TestApprove:
    @pytest.mark.asyncio
    async def test_approve_not_found(self) -> None:
        handler = _make_handler()
        await handler.handle("/approve -1001")
        assert "не найдена" in _reply_body(handler)

    @pytest.mark.asyncio
    async def test_approve_already_approved(self) -> None:
        pair = _make_pair(is_approved=True)
        handler = _make_handler(channel_pairs=[pair])
        await handler.handle(f"/approve {pair.tg_chat_id}")
        assert "уже одобрена" in _reply_body(handler)

    @pytest.mark.asyncio
    async def test_approve_bad_format(self) -> None:
        handler = _make_handler()
        await handler.handle("/approve")
        assert "Неверный формат" in _reply_body(handler)

    @pytest.mark.asyncio
    async def test_approve_invalid_int(self) -> None:
        handler = _make_handler()
        await handler.handle("/approve abc")
        assert "Неверный формат" in _reply_body(handler)


class TestExpressPosition:
    @pytest.mark.asyncio
    async def test_set_position(self) -> None:
        huid = uuid4()
        emp = _make_employee(express_huid=huid)
        handler = _make_handler(employees=[emp])
        await handler.handle(f"/express_position {huid} Архитектор")
        handler._employee_repo.update.assert_called_once()  # type: ignore[union-attr]  # noqa: SLF001
        assert "установлен" in _reply_body(handler)

    @pytest.mark.asyncio
    async def test_not_found(self) -> None:
        handler = _make_handler()
        await handler.handle(f"/express_position {uuid4()} Dev")
        assert "не найден" in _reply_body(handler)

    @pytest.mark.asyncio
    async def test_too_long(self) -> None:
        huid = uuid4()
        emp = _make_employee(express_huid=huid)
        handler = _make_handler(employees=[emp])
        await handler.handle(f"/express_position {huid} {'A' * (MAX_POSITION_LENGTH + 1)}")
        assert "длиннее" in _reply_body(handler)

    @pytest.mark.asyncio
    async def test_bad_format(self) -> None:
        handler = _make_handler()
        await handler.handle("/express_position")
        assert "Неверный формат" in _reply_body(handler)


class TestExpressFullname:
    @pytest.mark.asyncio
    async def test_set_fullname(self) -> None:
        huid = uuid4()
        emp = _make_employee(express_huid=huid)
        handler = _make_handler(employees=[emp])
        await handler.handle(f"/express_fullname {huid} Иван Иванов")
        handler._employee_repo.update.assert_called_once()  # type: ignore[union-attr]  # noqa: SLF001
        assert "установлен" in _reply_body(handler)

    @pytest.mark.asyncio
    async def test_too_long(self) -> None:
        huid = uuid4()
        emp = _make_employee(express_huid=huid)
        handler = _make_handler(employees=[emp])
        await handler.handle(f"/express_fullname {huid} {'A' * (MAX_FULLNAME_LENGTH + 1)}")
        assert "длиннее" in _reply_body(handler)


class TestTelegramPosition:
    @pytest.mark.asyncio
    async def test_set_position(self) -> None:
        emp = _make_employee(tg_user_id=42)
        handler = _make_handler(employees=[emp])
        await handler.handle("/telegram_position 42 Аналитик")
        handler._employee_repo.update.assert_called_once()  # type: ignore[union-attr]  # noqa: SLF001
        assert "установлен" in _reply_body(handler)

    @pytest.mark.asyncio
    async def test_not_found(self) -> None:
        handler = _make_handler()
        await handler.handle("/telegram_position 999 Dev")
        assert "не найден" in _reply_body(handler)


class TestTelegramFullname:
    @pytest.mark.asyncio
    async def test_set_fullname(self) -> None:
        emp = _make_employee(tg_user_id=42)
        handler = _make_handler(employees=[emp])
        await handler.handle("/telegram_fullname 42 Мария Сидорова")
        handler._employee_repo.update.assert_called_once()  # type: ignore[union-attr]  # noqa: SLF001
        assert "установлен" in _reply_body(handler)


class TestGroupPairList:
    @pytest.mark.asyncio
    async def test_empty_list(self) -> None:
        handler = _make_handler()
        await handler.handle("/group_pair_list")
        assert "пуст" in _reply_body(handler)

    @pytest.mark.asyncio
    async def test_csv_file_sent(self) -> None:
        pair = _make_pair(is_approved=True)
        handler = _make_handler(channel_pairs=[pair])
        await handler.handle("/group_pair_list")
        kw = _reply_kwargs(handler)
        assert "file" in kw
        assert kw["file"].filename == "group_pairs.csv"  # type: ignore[union-attr]
        assert b"tg_chat_id" in kw["file"].content  # type: ignore[union-attr]


class TestUsersList:
    @pytest.mark.asyncio
    async def test_empty_list(self) -> None:
        handler = _make_handler()
        await handler.handle("/users_list")
        assert "пуст" in _reply_body(handler)

    @pytest.mark.asyncio
    async def test_csv_file_sent(self) -> None:
        emp = _make_employee(tg_user_id=42)
        handler = _make_handler(employees=[emp])
        await handler.handle("/users_list")
        kw = _reply_kwargs(handler)
        assert kw["file"].filename == "employees.csv"  # type: ignore[union-attr]
        assert b"tg_user_id" in kw["file"].content  # type: ignore[union-attr]


class TestFileDownload:
    @pytest.mark.asyncio
    async def test_download_file(self) -> None:
        handler = _make_handler()
        await handler.handle(f"/file_download {uuid4()}")
        kw = _reply_kwargs(handler)
        assert kw["file"].filename == "test.pdf"  # type: ignore[union-attr]
        assert kw["file"].content == b"file-content"  # type: ignore[union-attr]

    @pytest.mark.asyncio
    async def test_file_not_found(self) -> None:
        handler = _make_handler()
        handler._s3_storage.head_object = AsyncMock(side_effect=Exception("not found"))  # type: ignore[assignment]  # noqa: SLF001
        await handler.handle(f"/file_download {uuid4()}")
        assert "не найден" in _reply_body(handler)

    @pytest.mark.asyncio
    async def test_bad_format(self) -> None:
        handler = _make_handler()
        await handler.handle("/file_download")
        assert "Неверный формат" in _reply_body(handler)
