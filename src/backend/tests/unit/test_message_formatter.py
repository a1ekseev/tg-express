from uuid import uuid4

from app.application.utils.message_formatter import (
    MAX_CHAT_NAME_LENGTH,
    build_express_chat_name,
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
        tg_name=None,
        express_name=None,
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


class TestBuildExpressChatName:
    def test_normal_name(self) -> None:
        assert build_express_chat_name("[TG]", "Чат разработки") == "[TG] Чат разработки"

    def test_prefix_and_name_joined_with_space(self) -> None:
        result = build_express_chat_name("Prefix", "Name")
        assert result == "Prefix Name"

    def test_truncate_long_name(self) -> None:
        long_name = "A" * 200
        result = build_express_chat_name("[TG]", long_name)
        assert len(result) == MAX_CHAT_NAME_LENGTH

    def test_exact_128_not_truncated(self) -> None:
        # prefix(4) + space(1) + name(123) = 128
        name = "x" * 123
        result = build_express_chat_name("[TG]", name)
        assert len(result) == MAX_CHAT_NAME_LENGTH
        assert result.endswith("x")

    def test_long_prefix_truncates(self) -> None:
        prefix = "P" * 120
        name = "N" * 20
        result = build_express_chat_name(prefix, name)
        # 120 + 1 + 20 = 141 > 128
        assert len(result) == MAX_CHAT_NAME_LENGTH
        assert result.startswith("P" * 120)

    def test_cyrillic_truncation(self) -> None:
        name = "Б" * 200
        result = build_express_chat_name("[TG]", name)
        assert len(result) == MAX_CHAT_NAME_LENGTH


class TestFormatAttachmentsBlock:
    def test_single_file_markdown(self) -> None:
        result = format_attachments_block([("https://host/api/files/abc", "doc.pdf")])
        assert "Вложения:" in result
        assert "1. [doc.pdf](https://host/api/files/abc)" in result

    def test_multiple_files_markdown(self) -> None:
        files: list[tuple[str, str | None]] = [
            ("https://host/api/files/abc", "doc.pdf"),
            ("https://host/api/files/def", "img.png"),
        ]
        result = format_attachments_block(files)
        assert "1. [doc.pdf](https://host/api/files/abc)" in result
        assert "2. [img.png](https://host/api/files/def)" in result

    def test_filename_none_fallback(self) -> None:
        result = format_attachments_block([("https://host/api/files/abc", None)])
        assert "[файл](https://host/api/files/abc)" in result

    def test_numbering_starts_at_one(self) -> None:
        files: list[tuple[str, str | None]] = [("url1", "a.txt"), ("url2", "b.txt"), ("url3", "c.txt")]
        lines = format_attachments_block(files).strip().split("\n")
        assert lines[1] == "1. [a.txt](url1)"
        assert lines[2] == "2. [b.txt](url2)"
        assert lines[3] == "3. [c.txt](url3)"

    def test_empty_list(self) -> None:
        result = format_attachments_block([])
        assert result == "\nВложения:"
