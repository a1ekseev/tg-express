from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from app.application.dto import ExpressIncomingDTO

if TYPE_CHECKING:
    from pybotx import EventDeleted, EventEdit, IncomingMessage


def incoming_to_dto(message: IncomingMessage) -> ExpressIncomingDTO:
    file_type: str | None = None
    file_name: str | None = None
    file_content_type: str | None = None

    file_data: bytes | None = None
    if message.file is not None:
        file_type = str(message.file.type.value).lower() if hasattr(message.file, "type") else "document"
        file_name = message.file.filename if hasattr(message.file, "filename") else None
        file_content_type = None
        file_data = message.file.content if hasattr(message.file, "content") else None

    contact_name: str | None = None
    if message.contact is not None:
        contact_name = message.contact.name if hasattr(message.contact, "name") else None

    link_url: str | None = None
    if message.link is not None:
        link_url = message.link.url if hasattr(message.link, "url") else None

    return ExpressIncomingDTO(
        sync_id=message.sync_id,
        chat_id=message.chat.id,
        user_huid=message.sender.huid,
        body=message.body,
        source_sync_id=message.source_sync_id,
        file_type=file_type,
        file_name=file_name,
        file_content_type=file_content_type,
        has_sticker=message.sticker is not None,
        has_location=message.location is not None,
        has_contact=message.contact is not None,
        contact_name=contact_name,
        link_url=link_url,
        file_data=file_data,
    )


def edit_event_to_dto(event: EventEdit) -> ExpressIncomingDTO:
    return ExpressIncomingDTO(
        sync_id=event.sync_id,
        chat_id=event.chat_id,
        user_huid=event.huid,
        body=event.body,
        source_sync_id=None,
        file_type=None,
        file_name=None,
        file_content_type=None,
        has_sticker=False,
        has_location=False,
        has_contact=False,
        contact_name=None,
        link_url=None,
        event_type="edit_message",
    )


def deleted_event_to_dtos(event: EventDeleted) -> list[ExpressIncomingDTO]:
    return [
        ExpressIncomingDTO(
            sync_id=sync_id,
            chat_id=event.group_chat_id,
            user_huid=UUID(int=0),
            body=None,
            source_sync_id=None,
            file_type=None,
            file_name=None,
            file_content_type=None,
            has_sticker=False,
            has_location=False,
            has_contact=False,
            contact_name=None,
            link_url=None,
            event_type="delete_message",
        )
        for sync_id in event.sync_ids
    ]
