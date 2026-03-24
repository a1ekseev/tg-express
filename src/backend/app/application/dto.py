from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict


class TgEntityDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    type: str
    offset: int
    length: int
    url: str | None = None


class TgIncomingDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    tg_message_id: int
    tg_chat_id: int
    tg_user_id: int
    content_type: str
    body: str | None
    entities: tuple[TgEntityDTO, ...] | None
    chat_title: str | None
    sender_name: str
    reply_to_message_id: int | None
    media_group_id: str | None
    file_id: str | None
    file_name: str | None
    file_content_type: str | None
    file_size: int | None
    contact_name: str | None
    contact_phone: str | None
    file_data: bytes | None = None
    event_type: str = "new_message"


class ExpressIncomingDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    sync_id: UUID
    chat_id: UUID
    user_huid: UUID
    body: str | None
    source_sync_id: UUID | None
    file_type: str | None
    file_name: str | None
    file_content_type: str | None
    has_sticker: bool
    has_location: bool
    has_contact: bool
    contact_name: str | None
    link_url: str | None
    sender_name: str | None = None
    file_data: bytes | None = None
    event_type: str = "new_message"
