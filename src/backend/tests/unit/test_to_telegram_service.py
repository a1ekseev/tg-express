"""Tests for ToTelegramService._handle_new_message file-only case."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.application.dto import ExpressIncomingDTO
from app.application.services.to_telegram_service import ToTelegramService
from app.domain.models import Employee


def _make_dto(
    *,
    body: str | None = None,
    file_type: str | None = None,
    file_name: str | None = None,
    file_data: bytes | None = None,
) -> ExpressIncomingDTO:
    return ExpressIncomingDTO(
        sync_id=uuid4(),
        chat_id=uuid4(),
        user_huid=uuid4(),
        body=body,
        source_sync_id=None,
        file_type=file_type,
        file_name=file_name,
        file_content_type=None,
        has_sticker=False,
        has_location=False,
        has_contact=False,
        contact_name=None,
        link_url=None,
        sender_name=None,
        file_data=file_data,
    )


def _make_service() -> ToTelegramService:
    mock_session = MagicMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_session.begin = MagicMock(return_value=mock_session)

    mock_session_factory = MagicMock(return_value=mock_session)

    mock_to_telegram_repo = MagicMock()
    mock_to_telegram_repo.mark_sent = AsyncMock()

    mock_mapping = MagicMock()
    mock_mapping.find_tg_message = AsyncMock(return_value=None)

    mock_employee_repo = MagicMock()
    mock_employee_repo.find_or_create_by_express_huid = AsyncMock(
        return_value=Employee(
            id=uuid4(),
            tg_user_id=None,
            express_huid=uuid4(),
            full_name=None,
            position=None,
            tg_name=None,
            express_name=None,
        )
    )

    mock_tg_bot = MagicMock()
    mock_result = MagicMock()
    mock_result.message_id = 123
    mock_result.chat.id = -1001
    mock_tg_bot.send_document = AsyncMock(return_value=mock_result)
    mock_tg_bot.send_photo = AsyncMock(return_value=mock_result)

    return ToTelegramService(
        session_factory=mock_session_factory,
        to_telegram_repo=mock_to_telegram_repo,
        channel_pair_repo=MagicMock(),
        mapping_queries=mock_mapping,
        employee_repo=mock_employee_repo,
        s3_storage=MagicMock(),
        tg_bot=mock_tg_bot,
        retry_max_attempts=1,
        retry_base_delay=0.0,
        retry_max_delay=0.0,
    )


class TestFileWithoutText:
    @pytest.mark.asyncio
    async def test_file_without_text_sends_document(self) -> None:
        """File without body and without header should still be sent to TG."""
        service = _make_service()
        dto = _make_dto(file_type="document", file_name="report.pdf", file_data=b"pdf-bytes")
        s3_keys = {dto.sync_id: "some-s3-key"}

        await service._handle_new_message(dto, uuid4(), -1001, None, s3_keys)  # noqa: SLF001

        service._tg_bot.send_document.assert_called_once()  # type: ignore[union-attr]  # noqa: SLF001
        call_kwargs = service._tg_bot.send_document.call_args.kwargs  # type: ignore[union-attr]  # noqa: SLF001
        assert call_kwargs["caption"] is None

    @pytest.mark.asyncio
    async def test_file_without_text_sends_photo(self) -> None:
        """Image without body should be sent as photo."""
        service = _make_service()
        dto = _make_dto(file_type="image", file_name="photo.jpg", file_data=b"img-bytes")
        s3_keys = {dto.sync_id: "some-s3-key"}

        await service._handle_new_message(dto, uuid4(), -1001, None, s3_keys)  # noqa: SLF001

        service._tg_bot.send_photo.assert_called_once()  # type: ignore[union-attr]  # noqa: SLF001
        call_kwargs = service._tg_bot.send_photo.call_args.kwargs  # type: ignore[union-attr]  # noqa: SLF001
        assert call_kwargs["caption"] is None
