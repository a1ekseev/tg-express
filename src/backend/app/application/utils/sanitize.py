from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.application.dto import TgEntityDTO

# Unicode emoji pattern — matches most emoji (Emoji_Presentation + Emoji_Modifier_Base + etc.)
_EMOJI_PATTERN = re.compile(
    "["
    "\U0001f600-\U0001f64f"  # emoticons
    "\U0001f300-\U0001f5ff"  # symbols & pictographs
    "\U0001f680-\U0001f6ff"  # transport & map
    "\U0001f1e0-\U0001f1ff"  # flags
    "\U00002702-\U000027b0"  # dingbats
    "\U000024c2-\U0001f251"  # enclosed characters
    "\U0001f900-\U0001f9ff"  # supplemental symbols
    "\U0001fa00-\U0001fa6f"  # chess symbols
    "\U0001fa70-\U0001faff"  # symbols extended-A
    "\U00002600-\U000026ff"  # misc symbols
    "\U0000fe00-\U0000fe0f"  # variation selectors
    "\U0000200d"  # zero-width joiner
    "\U00000023\U000020e3"  # keycap #
    "\U0000002a\U000020e3"  # keycap *
    "\U00000030-\U00000039\U000020e3"  # keycap 0-9
    "\U000000a9"  # copyright
    "\U000000ae"  # registered
    "]+",
    flags=re.UNICODE,
)

_HTML_TAG_PATTERN = re.compile(r"<[^>]+>")


def strip_tg_formatting(text: str, entities: tuple[TgEntityDTO, ...] | None) -> str:
    """Remove Telegram formatting using entities.

    Entities carry offset+length for each formatted span.
    We extract the plain text portion for each entity type,
    removing surrounding markup characters.
    For text_link entities, we keep the visible text and drop the URL.
    """
    if not entities:
        return text

    # Telegram entities are based on UTF-16 offsets in some cases,
    # but aiogram normalizes them to Python string offsets.
    # We just need the plain text without markup — since the `text` field
    # from aiogram already contains the plain text (entities describe *what*
    # is formatted, not the raw markup), we simply return text as-is.
    # The entities don't add markup characters to the text body.
    return text


def strip_express_formatting(text: str) -> str:
    """Remove HTML-like formatting that Express may include."""
    return _HTML_TAG_PATTERN.sub("", text)


def strip_emoji(text: str) -> str:
    """Remove all Unicode emoji from text."""
    return _EMOJI_PATTERN.sub("", text)


def sanitize_to_express(text: str | None, entities: tuple[TgEntityDTO, ...] | None = None) -> str | None:
    """Clean Telegram text before sending to Express.

    1. strip_tg_formatting — remove MarkdownV2/v1/HTML markup
    2. strip_emoji — remove all Unicode emoji
    3. strip — trim whitespace
    4. Return None if result is empty
    """
    if text is None:
        return None
    result = strip_tg_formatting(text, entities)
    result = strip_emoji(result)
    result = result.strip()
    return result or None


def sanitize_to_telegram(text: str | None) -> str | None:
    """Clean Express text before sending to Telegram.

    1. strip_express_formatting — remove HTML tags
    2. strip_emoji — remove all Unicode emoji
    3. strip — trim whitespace
    4. Return None if result is empty
    """
    if text is None:
        return None
    result = strip_express_formatting(text)
    result = strip_emoji(result)
    result = result.strip()
    return result or None
