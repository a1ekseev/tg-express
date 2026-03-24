from __future__ import annotations

from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from app.domain.models import Employee

MAX_CHAT_NAME_LENGTH: Final[int] = 128


def format_header_to_express(employee: Employee | None, tg_sender_name: str) -> str:
    """Build header line for Express messages: '[Position, Name]:'"""
    if employee is not None:
        parts: list[str] = []
        if employee.position:
            parts.append(employee.position)
        if employee.full_name:
            parts.append(employee.full_name)
        if parts:
            return f"[{', '.join(parts)}]:"
    return f"[{tg_sender_name}]:"


def format_header_to_telegram(employee: Employee | None) -> str | None:
    """Build header line for Telegram messages: '[Position]:' or None."""
    if employee is not None and employee.position:
        return f"[{employee.position}]:"
    return None


def build_express_chat_name(prefix: str, name: str) -> str:
    """Build Express chat name: prefix + space + name, truncated to 128 chars."""
    return (prefix + " " + name)[:MAX_CHAT_NAME_LENGTH]


def format_attachments_block(files: list[tuple[str, str | None]]) -> str:
    """Build attachments block for Express messages in Markdown format."""
    lines = ["", "Вложения:"]
    for i, (url, filename) in enumerate(files, start=1):
        label = filename or "файл"
        lines.append(f"{i}. [{label}]({url})")
    return "\n".join(lines)
