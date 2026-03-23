from __future__ import annotations

from app.domain.models import TgMessageAction

FORWARD_CONTENT_TYPES: frozenset[str] = frozenset(
    {
        "text",
        "photo",
        "document",
        "video",
        "voice",
        "audio",
        "video_note",
        "contact",
    }
)

SKIP_CONTENT_TYPES: frozenset[str] = frozenset(
    {
        "sticker",
        "animation",
        "dice",
        "game",
        "story",
        "new_chat_members",
        "left_chat_member",
        "new_chat_title",
        "new_chat_photo",
        "delete_chat_photo",
        "pinned_message",
        "group_chat_created",
        "supergroup_chat_created",
        "channel_chat_created",
        "migrate_to_chat_id",
        "migrate_from_chat_id",
        "message_auto_delete_timer_changed",
        "video_chat_scheduled",
        "video_chat_started",
        "video_chat_ended",
        "video_chat_participants_invited",
        "forum_topic_created",
        "forum_topic_edited",
        "forum_topic_closed",
        "forum_topic_reopened",
        "general_forum_topic_hidden",
        "general_forum_topic_unhidden",
        "write_access_allowed",
        "boost_added",
        "chat_background_set",
    }
)


def classify_tg_message(content_type: str) -> TgMessageAction:
    if content_type in FORWARD_CONTENT_TYPES:
        return TgMessageAction.FORWARD
    if content_type in SKIP_CONTENT_TYPES:
        return TgMessageAction.SKIP
    return TgMessageAction.SYSTEM


def should_forward_express_message(*, has_sticker: bool, has_location: bool) -> bool:
    return not has_sticker and not has_location
