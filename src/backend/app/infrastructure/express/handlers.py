from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.infrastructure.express.bot import collector
from app.infrastructure.express.converters import deleted_event_to_dtos, edit_event_to_dto, incoming_to_dto

if TYPE_CHECKING:
    from uuid import UUID

    from pybotx import Bot, EventDeleted, EventEdit, IncomingMessage

    from app.application.services.to_telegram_service import ToTelegramService

logger = logging.getLogger(__name__)

_webhook_service: ToTelegramService | None = None
_system_channel_id: UUID | None = None


def set_webhook_service(service: ToTelegramService) -> None:
    global _webhook_service  # noqa: PLW0603
    _webhook_service = service


def set_system_channel_id(channel_id: UUID) -> None:
    global _system_channel_id  # noqa: PLW0603
    _system_channel_id = channel_id


@collector.default_message_handler()
async def handle_default_message(message: IncomingMessage, bot: Bot) -> None:  # noqa: ARG001
    if _webhook_service is None:
        return
    if _system_channel_id is not None and message.chat.id == _system_channel_id:
        return
    dto = incoming_to_dto(message)
    logger.info("Express message received sync_id=%s chat_id=%s", message.sync_id, message.chat.id)
    await _webhook_service.handle_batch([dto])


@collector.event_edit
async def handle_edit(event: EventEdit, bot: Bot) -> None:  # noqa: ARG001
    if _webhook_service is None:
        return
    if _system_channel_id is not None and event.chat_id == _system_channel_id:
        return
    dto = edit_event_to_dto(event)
    logger.info("Express edit received sync_id=%s chat_id=%s", event.sync_id, event.chat_id)
    await _webhook_service.handle_batch([dto])


@collector.event_deleted
async def handle_deleted(event: EventDeleted, bot: Bot) -> None:  # noqa: ARG001
    if _webhook_service is None:
        return
    if _system_channel_id is not None and event.group_chat_id == _system_channel_id:
        return
    dtos = deleted_event_to_dtos(event)
    logger.info("Express delete received sync_ids=%s", event.sync_ids)
    if dtos:
        await _webhook_service.handle_batch(dtos)
