from __future__ import annotations

from typing import Final

MAX_MESSAGE_LENGTH: Final[int] = 4096


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


def split_to_telegram(header: str | None, body: str | None) -> list[str]:
    """Split message for Telegram. Returns list of parts each <= 4096 chars.

    Part 1: header + newline + beginning of body
    Part N: continuation of body
    """
    full_text = header + "\n" + (body or "") if header else body or ""

    if not full_text:
        return []

    if len(full_text) <= MAX_MESSAGE_LENGTH:
        return [full_text]

    return _split_text(full_text, MAX_MESSAGE_LENGTH)


def _split_text(text: str, max_len: int, reserve_last: int = 0) -> list[str]:
    """Split text into chunks of max_len chars, breaking at newlines or spaces."""
    parts: list[str] = []
    remaining = text

    while remaining:
        effective_max = max_len
        # For all but the last chunk, reserve space for suffix in the last chunk
        if len(remaining) > max_len and reserve_last > 0:
            effective_max = max_len

        if len(remaining) <= effective_max:
            parts.append(remaining)
            break

        # Find best break point
        chunk = remaining[:effective_max]
        break_pos = _find_break_point(chunk)

        parts.append(remaining[:break_pos].rstrip())
        remaining = remaining[break_pos:].lstrip("\n")

    return parts


def _find_break_point(chunk: str) -> int:
    """Find the best position to break a chunk — prefer newline, then space."""
    # Try to break at last newline
    nl_pos = chunk.rfind("\n")
    if nl_pos > 0:
        return nl_pos

    # Try to break at last space
    space_pos = chunk.rfind(" ")
    if space_pos > 0:
        return space_pos

    # No good break point — hard break
    return len(chunk)
