from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.domain.models import Employee


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


def format_attachments_block(file_urls: list[str]) -> str:
    """Build attachments block for Express messages."""
    lines = ["", "Вложения:"]
    for i, url in enumerate(file_urls, start=1):
        lines.append(f"{i}. {url}")
    return "\n".join(lines)
