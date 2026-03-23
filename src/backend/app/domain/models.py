from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class EventType(StrEnum):
    NEW_MESSAGE = "new_message"
    EDIT_MESSAGE = "edit_message"
    DELETE_MESSAGE = "delete_message"


class MessageStatus(StrEnum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"


class MessageDirection(StrEnum):
    TG_TO_EXPRESS = "tg_to_express"
    EXPRESS_TO_TG = "express_to_tg"


class TgMessageAction(StrEnum):
    FORWARD = "forward"
    SYSTEM = "system"
    SKIP = "skip"


class SystemChannelReason(StrEnum):
    UNAPPROVED_CHANNEL = "unapproved_channel"
    UNSUPPORTED_TYPE = "unsupported_type"


class ChannelPair(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    tg_chat_id: int
    express_chat_id: UUID | None
    is_approved: bool
    name: str | None


class Employee(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    tg_user_id: int | None
    express_huid: UUID | None
    full_name: str | None
    position: str | None
