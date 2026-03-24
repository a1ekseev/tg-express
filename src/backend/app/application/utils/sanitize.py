from __future__ import annotations

import html as html_module
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.application.dto import TgEntityDTO

# Emoji pattern — only SMP emoji blocks + dingbats + safe BMP ranges.
# Deliberately excludes ASCII chars (#, *, 0-9), ©, ®, and the massive
# U+24C2..U+1F251 range that contains box-drawing, arrows, math, etc.
_EMOJI_PATTERN = re.compile(
    "["
    "\U0001f600-\U0001f64f"  # emoticons
    "\U0001f300-\U0001f5ff"  # symbols & pictographs
    "\U0001f680-\U0001f6ff"  # transport & map
    "\U0001f1e0-\U0001f1ff"  # flags (regional indicators)
    "\U0001f900-\U0001f9ff"  # supplemental symbols
    "\U0001fa00-\U0001fa6f"  # chess symbols
    "\U0001fa70-\U0001faff"  # symbols extended-A
    "\U00002702-\U000027b0"  # dingbats
    "\U0000fe00-\U0000fe0f"  # variation selectors
    "\U0000200d"  # zero-width joiner
    "\U000020e3"  # combining enclosing keycap
    "]+",
    flags=re.UNICODE,
)

_MULTI_SPACE = re.compile(r" {2,}")

# HTML tag pattern — requires tag name starting with a letter.
# Supports self-closing (e.g. <hr/>, <br/>, <img ... />).
# Avoids false positives like "< 5" or "x < 10 && y > 3".
_HTML_TAG_PATTERN = re.compile(r"</?[a-zA-Z][a-zA-Z0-9]*(?:\s[^>]*)?\s*/?>")

# <br>, <br/>, <br /> — replaced with newline before general tag removal
_BR_PATTERN = re.compile(r"<br\s*/?>", re.IGNORECASE)

# Block-level closing tags — replaced with newline to prevent word gluing
_BLOCK_CLOSE_PATTERN = re.compile(
    r"</(?:p|div|li|h[1-6]|tr|blockquote|section|article|header|footer|ul|ol|table|thead|tbody)>",
    re.IGNORECASE,
)


def strip_tg_formatting(text: str, entities: tuple[TgEntityDTO, ...] | None) -> str:
    """Remove Telegram formatting using entities.

    Since aiogram's `message.text` / `message.caption` already contains the
    plain text (entities describe *what* is formatted via offset+length, they
    don't inject markup characters into the body), we simply return text as-is.

    Exception: `text_link` entities carry a hidden URL that is not in the visible
    text. We append the URL in parentheses after the anchor text.
    """
    if not entities:
        return text

    # Process text_link entities in reverse order to preserve offsets
    result = text
    for entity in sorted(entities, key=lambda e: e.offset, reverse=True):
        if entity.type == "text_link" and entity.url:
            end = entity.offset + entity.length
            result = result[:end] + f" ({entity.url})" + result[end:]

    return result


def strip_express_formatting(text: str) -> str:
    """Remove HTML-like formatting that Express may include.

    1. Replace <br> with newline
    2. Replace block-level closing tags with newline (prevent word gluing)
    3. Strip HTML tags (only real tags starting with a letter)
    4. Decode HTML entities (&amp; → &, &gt; → >, etc.)
    """
    result = _BR_PATTERN.sub("\n", text)
    result = _BLOCK_CLOSE_PATTERN.sub("\n", result)
    result = _HTML_TAG_PATTERN.sub("", result)
    return html_module.unescape(result)


def strip_emoji(text: str) -> str:
    """Remove Unicode emoji from text.

    Replaces emoji with a space (not empty string) to prevent word gluing
    when emoji is between words without spaces, then collapses multiple spaces.
    """
    result = _EMOJI_PATTERN.sub(" ", text)
    return _MULTI_SPACE.sub(" ", result)


def sanitize_to_express(text: str | None, entities: tuple[TgEntityDTO, ...] | None = None) -> str | None:
    """Clean Telegram text before sending to Express.

    1. strip_tg_formatting — extract text_link URLs
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

    1. strip_express_formatting — replace <br>, strip HTML tags, decode entities
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
