from __future__ import annotations

from typing import TYPE_CHECKING

from app.application.dto import TgEntityDTO, TgIncomingDTO

if TYPE_CHECKING:
    from aiogram.types import Message


def message_to_dto(message: Message) -> TgIncomingDTO:
    entities: tuple[TgEntityDTO, ...] | None = None
    if message.entities:
        entities = tuple(
            TgEntityDTO(
                type=e.type,
                offset=e.offset,
                length=e.length,
                url=e.url,
            )
            for e in message.entities
        )

    # Extract file_id and file metadata
    file_id: str | None = None
    file_name: str | None = None
    file_content_type: str | None = None
    file_size: int | None = None

    if message.photo:
        largest = message.photo[-1]
        file_id = largest.file_id
        file_name = "photo.jpg"
        file_content_type = "image/jpeg"
        file_size = largest.file_size
    elif message.document:
        file_id = message.document.file_id
        file_name = message.document.file_name
        file_content_type = message.document.mime_type
        file_size = message.document.file_size
    elif message.video:
        file_id = message.video.file_id
        file_name = message.video.file_name
        file_content_type = message.video.mime_type
        file_size = message.video.file_size
    elif message.voice:
        file_id = message.voice.file_id
        file_name = "voice.ogg"
        file_content_type = message.voice.mime_type
        file_size = message.voice.file_size
    elif message.audio:
        file_id = message.audio.file_id
        file_name = message.audio.file_name
        file_content_type = message.audio.mime_type
        file_size = message.audio.file_size
    elif message.video_note:
        file_id = message.video_note.file_id
        file_name = "video_note.mp4"
        file_size = message.video_note.file_size

    # Contact fields
    contact_name: str | None = None
    contact_phone: str | None = None
    if message.contact:
        parts = [message.contact.first_name or "", message.contact.last_name or ""]
        contact_name = " ".join(p for p in parts if p).strip() or None
        contact_phone = message.contact.phone_number

    # Body: fallback to contact text representation
    body = message.text or message.caption
    if body is None and contact_name:
        body = f"Contact: {contact_name}"
        if contact_phone:
            body += f" ({contact_phone})"

    # Sender name
    sender_name = ""
    if message.from_user:
        parts = [message.from_user.first_name or "", message.from_user.last_name or ""]
        sender_name = " ".join(p for p in parts if p).strip()

    return TgIncomingDTO(
        tg_message_id=message.message_id,
        tg_chat_id=message.chat.id,
        tg_user_id=message.from_user.id if message.from_user else 0,
        content_type=message.content_type or "unknown",
        body=body,
        entities=entities,
        chat_title=message.chat.title or message.chat.full_name,
        sender_name=sender_name,
        reply_to_message_id=message.reply_to_message.message_id if message.reply_to_message else None,
        media_group_id=message.media_group_id,
        file_id=file_id,
        file_name=file_name,
        file_content_type=file_content_type,
        file_size=file_size,
        contact_name=contact_name,
        contact_phone=contact_phone,
    )
