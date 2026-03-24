from __future__ import annotations

from typing import Final

MAX_MESSAGE_LENGTH: Final[int] = 4096
CAPTION_LENGTH: Final[int] = 1024


def split_to_express(header: str, body: str | None, attachments_block: str | None) -> list[str]:
    """Split message for Express. Returns list of parts each <= 4096 chars.

    Part 1: header + newline + beginning of body
    Part N: continuation of body
    Last part: end of body + attachments_block (or separate part if doesn't fit)
    """
    full_text = header + "\n" + (body or "")
    suffix = attachments_block or ""

    if len(full_text) + len(suffix) <= MAX_MESSAGE_LENGTH:
        return [full_text + suffix]

    # Need to split
    parts = _split_text(full_text, MAX_MESSAGE_LENGTH, reserve_last=len(suffix))

    # Append attachments to last part if fits, otherwise add as separate part
    if parts and len(parts[-1]) + len(suffix) <= MAX_MESSAGE_LENGTH:
        parts[-1] += suffix
    elif suffix:
        parts.append(suffix)

    return parts


def split_to_telegram(
    header: str | None,
    body: str | None,
    *,
    first_part_limit: int | None = None,
) -> list[str]:
    """Split message for Telegram. Returns list of parts each <= 4096 chars.

    Part 1: header + newline + beginning of body
    Part N: continuation of body

    If first_part_limit is set (e.g. 1024 for media captions), the first part
    is limited to that value while subsequent parts use 4096.
    """
    full_text = header + "\n" + (body or "") if header else body or ""

    if not full_text:
        return []

    effective_limit = first_part_limit or MAX_MESSAGE_LENGTH

    if len(full_text) <= effective_limit:
        return [full_text]

    # First part at effective_limit, rest at MAX_MESSAGE_LENGTH
    parts: list[str] = []
    remaining = full_text

    # First chunk
    if len(remaining) > effective_limit:
        chunk = remaining[:effective_limit]
        break_pos = _find_break_point(chunk)
        parts.append(remaining[:break_pos].rstrip())
        remaining = remaining[break_pos:].removeprefix("\n")

    # Remaining chunks at standard limit
    if remaining:
        parts.extend(_split_text(remaining, MAX_MESSAGE_LENGTH))

    return parts


def _split_text(text: str, max_len: int, reserve_last: int = 0) -> list[str]:
    """Split text into chunks of max_len chars, breaking at newlines or spaces."""
    parts: list[str] = []
    remaining = text

    while remaining:
        # If the remainder fits within max_len minus the reserved suffix space, keep it whole
        if len(remaining) <= max_len - reserve_last:
            parts.append(remaining)
            break

        # Otherwise split at max_len (no reserve — reserve only applies to the last chunk)
        if len(remaining) <= max_len:
            # Remaining fits in one chunk but not with suffix — split not needed, just emit
            parts.append(remaining)
            break

        # Find best break point
        chunk = remaining[:max_len]
        break_pos = _find_break_point(chunk)

        parts.append(remaining[:break_pos].rstrip())
        # Strip at most one leading newline to preserve intentional blank lines
        remaining = remaining[break_pos:].removeprefix("\n")

    return parts


def _find_break_point(chunk: str) -> int:
    """Find the best position to break a chunk — prefer newline, then space.

    Avoids breaking in the first 25% of the chunk to prevent
    isolating a short header in its own part.
    """
    min_pos = len(chunk) // 4

    # Try to break at last newline in the last 75%
    nl_pos = chunk.rfind("\n", min_pos)
    if nl_pos > 0:
        return nl_pos

    # Try to break at last space in the last 75%
    space_pos = chunk.rfind(" ", min_pos)
    if space_pos > 0:
        return space_pos

    # Fallback: break at any newline or space
    nl_pos = chunk.rfind("\n")
    if nl_pos > 0:
        return nl_pos

    space_pos = chunk.rfind(" ")
    if space_pos > 0:
        return space_pos

    # No good break point — hard break
    return len(chunk)
