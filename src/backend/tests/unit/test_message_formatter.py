from uuid import uuid4

from app.application.utils.message_formatter import (
    format_attachments_block,
    format_header_to_express,
    format_header_to_telegram,
)
from app.domain.models import Employee


def _employee(
    *,
    position: str | None = None,
    full_name: str | None = None,
) -> Employee:
    return Employee(
        id=uuid4(),
        tg_user_id=123,
        express_huid=None,
        full_name=full_name,
        position=position,
    )


class TestFormatHeaderToExpress:
    def test_position_and_name(self) -> None:
        emp = _employee(position="Архитектор", full_name="Иван Иванов")
        assert format_header_to_express(emp, "tg_name") == "[Архитектор, Иван Иванов]:"

    def test_position_only(self) -> None:
        emp = _employee(position="Аналитик")
        assert format_header_to_express(emp, "tg_name") == "[Аналитик]:"

    def test_name_only(self) -> None:
        emp = _employee(full_name="Иван Иванов")
        assert format_header_to_express(emp, "tg_name") == "[Иван Иванов]:"

    def test_no_employee_data_uses_tg_name(self) -> None:
        emp = _employee()
        assert format_header_to_express(emp, "John Doe") == "[John Doe]:"

    def test_none_employee_uses_tg_name(self) -> None:
        assert format_header_to_express(None, "John Doe") == "[John Doe]:"


class TestFormatHeaderToTelegram:
    def test_with_position(self) -> None:
        emp = _employee(position="Архитектор")
        assert format_header_to_telegram(emp) == "[Архитектор]:"

    def test_no_position_returns_none(self) -> None:
        emp = _employee(full_name="Иван")
        assert format_header_to_telegram(emp) is None

    def test_none_employee_returns_none(self) -> None:
        assert format_header_to_telegram(None) is None


class TestFormatAttachmentsBlock:
    def test_single_file(self) -> None:
        result = format_attachments_block(["https://host/api/files/abc/doc.pdf"])
        assert "Вложения:" in result
        assert "1. https://host/api/files/abc/doc.pdf" in result

    def test_multiple_files(self) -> None:
        urls = [
            "https://host/api/files/abc/doc.pdf",
            "https://host/api/files/def/img.png",
        ]
        result = format_attachments_block(urls)
        assert "1. https://host/api/files/abc/doc.pdf" in result
        assert "2. https://host/api/files/def/img.png" in result

    def test_numbering_starts_at_one(self) -> None:
        result = format_attachments_block(["url1", "url2", "url3"])
        lines = result.strip().split("\n")
        assert lines[1] == "1. url1"
        assert lines[2] == "2. url2"
        assert lines[3] == "3. url3"

    def test_empty_list(self) -> None:
        result = format_attachments_block([])
        assert result == "\nВложения:"
