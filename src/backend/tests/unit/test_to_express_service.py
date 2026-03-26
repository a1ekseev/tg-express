"""Tests for ToExpressService with mocked dependencies."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.application.dto import TgIncomingDTO
from app.application.services.to_express_service import ToExpressService
from app.domain.models import ChannelPair, Employee, MessageStatus


def _make_dto(
    *,
    body: str | None = None,
    file_name: str | None = None,
    file_data: bytes | None = None,
    event_type: str = "new_message",
) -> TgIncomingDTO:
    return TgIncomingDTO(
        tg_message_id=100,
        tg_chat_id=-1001,
        tg_user_id=42,
        content_type="text" if not file_name else "photo",
        body=body,
        entities=None,
        chat_title="Test Chat",
        sender_name="Test User",
        reply_to_message_id=None,
        media_group_id=None,
        file_id=None,
        file_name=file_name,
        file_content_type=None,
        file_size=None,
        contact_name=None,
        contact_phone=None,
        file_data=file_data,
        event_type=event_type,
    )


def _make_employee() -> Employee:
    return Employee(
        id=uuid4(),
        tg_user_id=42,
        express_huid=None,
        full_name="Test User",
        position="Dev",
        tg_name="Test User",
        express_name=None,
    )


def _make_service() -> ToExpressService:
    mock_session = MagicMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_session.begin = MagicMock(return_value=mock_session)

    mock_session_factory = MagicMock(return_value=mock_session)

    mock_repo = MagicMock()
    mock_repo.get_status = AsyncMock(return_value=MessageStatus.PENDING)
    mock_repo.mark_sent = AsyncMock()

    mock_employee_repo = MagicMock()
    mock_employee_repo.find_or_create_by_tg_user_id = AsyncMock(return_value=_make_employee())

    mock_mapping = MagicMock()
    mock_mapping.find_express_sync_id = AsyncMock(return_value=uuid4())

    mock_s3 = MagicMock()
    mock_s3.get_download_url = MagicMock(return_value="https://host/api/files/uuid123")

    mock_settings = MagicMock()
    mock_settings.express_bot_id = uuid4()
    mock_settings.express_wait_callback = False
    mock_settings.retry_max_attempts = 1
    mock_settings.retry_base_delay = 0.0
    mock_settings.retry_max_delay = 0.0
    mock_settings.express_system_channel_id = uuid4()

    return ToExpressService(
        session_factory=mock_session_factory,
        to_express_repo=mock_repo,
        channel_pair_repo=MagicMock(),
        mapping_queries=mock_mapping,
        employee_repo=mock_employee_repo,
        s3_storage=mock_s3,
        settings=mock_settings,
        express_bot=MagicMock(),
    )


_SEND_PATH = "app.application.services.to_express_service.send_to_express"
_EDIT_PATH = "app.application.services.to_express_service.edit_in_express"


class TestSendRecordToExpress:
    @pytest.mark.asyncio
    @patch(_SEND_PATH, new_callable=AsyncMock)
    async def test_text_with_file_via_api(self, mock_send: AsyncMock) -> None:
        """Body + file_data → 2 calls: text + file via API (no link)."""
        service = _make_service()
        mock_send.return_value = uuid4()
        dto = _make_dto(body="hello", file_name="photo.jpg", file_data=b"fake-image")

        await service._send_record_to_express(  # noqa: SLF001
            dto,
            uuid4(),
            uuid4(),
            {dto.tg_message_id: "hello"},
            {dto.tg_message_id: "s3-key"},
        )

        assert mock_send.call_count == 2
        # First: text with header
        first_call = mock_send.call_args_list[0]
        assert "[Dev, Test User]:" in first_call.kwargs["body"]
        assert "hello" in first_call.kwargs["body"]
        assert first_call.kwargs.get("file") is None
        # Second: file via API
        second_call = mock_send.call_args_list[1]
        assert second_call.kwargs["file"] is not None
        assert "Вложения:" not in second_call.kwargs["body"]

    @pytest.mark.asyncio
    @patch(_SEND_PATH, new_callable=AsyncMock)
    async def test_file_api_fails_sends_link(self, mock_send: AsyncMock) -> None:
        """File API fails → fallback to Markdown link."""
        service = _make_service()
        call_count = 0

        async def side_effect(*args: object, **kwargs: object) -> object:  # noqa: ARG001
            nonlocal call_count
            call_count += 1
            if kwargs.get("file") is not None:
                raise RuntimeError("Express API error")
            return uuid4()

        mock_send.side_effect = side_effect
        dto = _make_dto(body="hello", file_name="photo.jpg", file_data=b"fake-image")

        await service._send_record_to_express(  # noqa: SLF001
            dto,
            uuid4(),
            uuid4(),
            {dto.tg_message_id: "hello"},
            {dto.tg_message_id: "s3-key"},
        )

        assert call_count == 3  # text + failed file + fallback link
        # Last call should be the Markdown link fallback
        last_call = mock_send.call_args_list[-1]
        assert "Вложения:" in last_call.kwargs["body"]

    @pytest.mark.asyncio
    @patch(_SEND_PATH, new_callable=AsyncMock)
    async def test_file_only_via_api_no_header(self, mock_send: AsyncMock) -> None:
        """File without body → 1 call (file via API), no header-only message."""
        service = _make_service()
        mock_send.return_value = uuid4()
        dto = _make_dto(body=None, file_name="photo.jpg", file_data=b"fake-image")

        await service._send_record_to_express(  # noqa: SLF001
            dto,
            uuid4(),
            uuid4(),
            {dto.tg_message_id: None},
            {dto.tg_message_id: "s3-key"},
        )

        assert mock_send.call_count == 1
        call = mock_send.call_args_list[0]
        assert call.kwargs["file"] is not None

    @pytest.mark.asyncio
    @patch(_SEND_PATH, new_callable=AsyncMock)
    async def test_file_no_data_sends_link(self, mock_send: AsyncMock) -> None:
        """File in s3_keys but no file_data (shouldn't happen, but fallback to link)."""
        service = _make_service()
        mock_send.return_value = uuid4()
        dto = _make_dto(body="hello", file_name="photo.jpg", file_data=None)

        await service._send_record_to_express(  # noqa: SLF001
            dto,
            uuid4(),
            uuid4(),
            {dto.tg_message_id: "hello"},
            {dto.tg_message_id: "s3-key"},
        )

        # text + fallback link (no API attempt since file_data is None)
        assert mock_send.call_count == 2
        last_body = mock_send.call_args_list[-1].kwargs["body"]
        assert "Вложения:" in last_body

    @pytest.mark.asyncio
    @patch(_SEND_PATH, new_callable=AsyncMock)
    async def test_text_only_sends_text(self, mock_send: AsyncMock) -> None:
        """Text without file → 1 call (text only)."""
        service = _make_service()
        mock_send.return_value = uuid4()
        dto = _make_dto(body="hello")

        await service._send_record_to_express(  # noqa: SLF001
            dto,
            uuid4(),
            uuid4(),
            {dto.tg_message_id: "hello"},
            {},
        )

        assert mock_send.call_count == 1
        body = mock_send.call_args_list[0].kwargs["body"]
        assert "[Dev, Test User]:" in body
        assert "hello" in body

    @pytest.mark.asyncio
    @patch(_EDIT_PATH, new_callable=AsyncMock)
    @patch(_SEND_PATH, new_callable=AsyncMock)
    async def test_edit_calls_edit_not_send(self, mock_send: AsyncMock, mock_edit: AsyncMock) -> None:
        """Edit event → calls edit_in_express, not send_to_express."""
        service = _make_service()
        dto = _make_dto(body="edited text", event_type="edit_message")

        await service._send_record_to_express(  # noqa: SLF001
            dto,
            uuid4(),
            uuid4(),
            {dto.tg_message_id: "edited text"},
            {},
        )

        mock_edit.assert_called_once()
        mock_send.assert_not_called()

    @pytest.mark.asyncio
    @patch(_EDIT_PATH, new_callable=AsyncMock)
    @patch(_SEND_PATH, new_callable=AsyncMock)
    async def test_edit_includes_header(self, mock_send: AsyncMock, mock_edit: AsyncMock) -> None:  # noqa: ARG002
        """Edit body should include header [Position, Name]:"""
        service = _make_service()
        dto = _make_dto(body="edited text", event_type="edit_message")

        await service._send_record_to_express(  # noqa: SLF001
            dto,
            uuid4(),
            uuid4(),
            {dto.tg_message_id: "edited text"},
            {},
        )

        edit_body = mock_edit.call_args.kwargs["body"]
        assert "[Dev, Test User]:" in edit_body
        assert "edited text" in edit_body


class TestHandleBatchEmojiFilter:
    @pytest.mark.asyncio
    @patch(_SEND_PATH, new_callable=AsyncMock)
    async def test_emoji_only_message_not_sent(self, mock_send: AsyncMock) -> None:
        """Emoji-only message (body becomes empty after sanitize) should not be forwarded."""
        service = _make_service()
        # Mock channel_pair_repo to return approved pair
        approved_pair = ChannelPair(
            id=uuid4(),
            tg_chat_id=-1001,
            express_chat_id=uuid4(),
            is_approved=True,
            name="Test",
        )
        service._channel_pair_repo.get_or_create_unapproved = AsyncMock(return_value=approved_pair)  # type: ignore[assignment]  # noqa: SLF001
        dto = _make_dto(body="\U0001f525\U0001f525\U0001f525")

        await service.handle_batch([dto])

        mock_send.assert_not_called()
