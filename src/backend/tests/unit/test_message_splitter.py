from app.application.utils.message_splitter import (
    CAPTION_LENGTH,
    MAX_MESSAGE_LENGTH,
    split_to_express,
    split_to_telegram,
)


class TestSplitToExpress:
    def test_short_message_single_part(self) -> None:
        parts = split_to_express("[Name]:", "hello", None)
        assert len(parts) == 1
        assert parts[0] == "[Name]:\nhello"

    def test_short_message_with_attachments(self) -> None:
        parts = split_to_express("[Name]:", "hello", "\n\nВложения:\n1. url")
        assert len(parts) == 1
        assert "hello" in parts[0]
        assert "Вложения:" in parts[0]

    def test_no_body(self) -> None:
        parts = split_to_express("[Name]:", None, "\n\nВложения:\n1. url")
        assert len(parts) == 1
        assert "[Name]:" in parts[0]
        assert "Вложения:" in parts[0]

    def test_long_message_splits(self) -> None:
        long_body = "word " * 1000  # ~5000 chars
        parts = split_to_express("[Name]:", long_body, None)
        assert len(parts) > 1
        for part in parts:
            assert len(part) <= MAX_MESSAGE_LENGTH

    def test_long_message_attachments_in_last(self) -> None:
        long_body = "word " * 1000
        attachments = "\n\nВложения:\n1. https://example.com/file.pdf"
        parts = split_to_express("[Name]:", long_body, attachments)
        assert len(parts) > 1
        assert "Вложения:" in parts[-1]

    def test_header_in_first_part(self) -> None:
        long_body = "a " * 2500
        parts = split_to_express("[Архитектор, Иван]:", long_body, None)
        assert parts[0].startswith("[Архитектор, Иван]:")

    def test_exact_limit_no_split(self) -> None:
        header = "[N]:"
        remaining = MAX_MESSAGE_LENGTH - len(header) - 1  # -1 for newline
        body = "x" * remaining
        parts = split_to_express(header, body, None)
        assert len(parts) == 1

    def test_attachments_as_separate_part_when_last_chunk_full(self) -> None:
        body = "x" * (MAX_MESSAGE_LENGTH - len("[N]:") - 1)
        body += " " + "y" * (MAX_MESSAGE_LENGTH - 1)
        attachments = "\n\nВложения:\n1. url"
        parts = split_to_express("[N]:", body, attachments)
        assert len(parts) >= 3
        assert "Вложения:" in parts[-1]
        assert parts[-1].strip().startswith("Вложения:")

    def test_empty_body_string(self) -> None:
        parts = split_to_express("[Name]:", "", None)
        assert len(parts) == 1
        assert parts[0] == "[Name]:\n"

    def test_header_not_isolated_no_newlines_in_body(self) -> None:
        """When body has no newlines, header should NOT be isolated in its own part."""
        header = "[Системный Аналитик, Иван Иванов]:"
        body = "Анализ требований к модулю платежей. " * 120  # ~4440 chars, no \n
        parts = split_to_express(header, body, None)
        # First part should contain header + substantial body content
        assert len(parts[0]) > len(header) + 100
        assert parts[0].startswith(header)
        for part in parts:
            assert len(part) <= MAX_MESSAGE_LENGTH

    def test_header_not_isolated_at_exact_boundary(self) -> None:
        """Header+newline+body = just over 4096. Should not isolate header."""
        header = "[N]:"
        body = "word " * 820  # ~4100 chars with spaces, no newlines
        parts = split_to_express(header, body, None)
        # First part should not be just the header
        assert len(parts[0]) > len(header) + 100
        for part in parts:
            assert len(part) <= MAX_MESSAGE_LENGTH


class TestSplitToTelegram:
    def test_short_message_single_part(self) -> None:
        parts = split_to_telegram("[Архитектор]:", "hello")
        assert len(parts) == 1
        assert parts[0] == "[Архитектор]:\nhello"

    def test_no_header(self) -> None:
        parts = split_to_telegram(None, "hello")
        assert len(parts) == 1
        assert parts[0] == "hello"

    def test_empty_returns_empty(self) -> None:
        parts = split_to_telegram(None, None)
        assert parts == []

    def test_empty_body_with_header(self) -> None:
        parts = split_to_telegram("[Pos]:", None)
        assert len(parts) == 1
        assert parts[0] == "[Pos]:\n"

    def test_long_message_splits(self) -> None:
        long_body = "слово " * 1000
        parts = split_to_telegram("[Pos]:", long_body)
        assert len(parts) > 1
        for part in parts:
            assert len(part) <= MAX_MESSAGE_LENGTH

    def test_splits_on_newlines(self) -> None:
        lines = ["Line " + str(i) for i in range(600)]
        body = "\n".join(lines)
        parts = split_to_telegram(None, body)
        assert len(parts) > 1
        for part in parts:
            assert len(part) <= MAX_MESSAGE_LENGTH

    def test_single_word_longer_than_limit(self) -> None:
        body = "x" * (MAX_MESSAGE_LENGTH + 100)
        parts = split_to_telegram(None, body)
        assert len(parts) == 2
        for part in parts:
            assert len(part) <= MAX_MESSAGE_LENGTH

    # --- first_part_limit (caption support) ---

    def test_first_part_limit_splits_at_caption_length(self) -> None:
        """With first_part_limit=1024, first part must be ≤ 1024."""
        body = "Описание файла с подробной информацией. " * 30  # ~1200 chars
        parts = split_to_telegram("[Архитектор]:", body, first_part_limit=CAPTION_LENGTH)
        assert len(parts) >= 2
        assert len(parts[0]) <= CAPTION_LENGTH
        for part in parts[1:]:
            assert len(part) <= MAX_MESSAGE_LENGTH

    def test_first_part_limit_no_split_when_fits(self) -> None:
        """Short message fits within caption limit — no split needed."""
        parts = split_to_telegram("[P]:", "short body", first_part_limit=CAPTION_LENGTH)
        assert len(parts) == 1
        assert len(parts[0]) <= CAPTION_LENGTH

    def test_first_part_limit_none_uses_4096(self) -> None:
        """Without first_part_limit, 2000-char message fits in single part."""
        body = "word " * 400  # ~2000 chars
        parts = split_to_telegram("[P]:", body, first_part_limit=None)
        assert len(parts) == 1

    def test_first_part_limit_rest_uses_4096(self) -> None:
        """Subsequent parts after the first use the standard 4096 limit."""
        body = "Текст " * 800  # ~4800 chars
        parts = split_to_telegram("[P]:", body, first_part_limit=CAPTION_LENGTH)
        assert len(parts[0]) <= CAPTION_LENGTH
        # Second part can use full 4096
        for part in parts[1:]:
            assert len(part) <= MAX_MESSAGE_LENGTH

    def test_header_not_isolated_with_first_part_limit(self) -> None:
        """Even with caption limit, header should not be alone."""
        header = "[Архитектор]:"  # 13 chars
        body = "x " * 600  # ~1200 chars
        parts = split_to_telegram(header, body, first_part_limit=CAPTION_LENGTH)
        assert len(parts[0]) > len(header) + 10


class TestSplitToExpressLargeMessages:
    def test_api_changelog_with_header_and_attachments(self) -> None:
        header = "[DevOps, Иван Петров]:"
        body = "Обновил документацию по API v2.3.1.\n\nОсновные изменения:\n" + "".join(
            f"{i}. Описание изменения номер {i} с деталями и пояснениями.\n" for i in range(1, 80)
        )
        attachments = "\n\nВложения:\n1. https://files.company.com/docs/api-v2.3.1-changelog.pdf"
        parts = split_to_express(header, body, attachments)
        assert parts[0].startswith(header)
        assert "Вложения:" in parts[-1]
        for part in parts:
            assert len(part) <= MAX_MESSAGE_LENGTH

    def test_single_paragraph_no_newlines(self) -> None:
        """Long paragraph with no newlines should not isolate header."""
        header = "[Системный Аналитик, Александр Иванов]:"
        body = "Анализ бизнес-требований к интеграции с внешним провайдером платежей. " * 80
        parts = split_to_express(header, body, None)
        # Header must not be isolated
        assert len(parts[0]) > len(header) + 100
        for part in parts:
            assert len(part) <= MAX_MESSAGE_LENGTH

    def test_production_bug_report(self) -> None:
        header = "[Backend, Мария Сидорова]:"
        body = (
            "Баг в продакшене.\n\n"
            "Stack trace:\n" + "  File line " * 50 + "\n\n"
            "Затронуты: ~2500 транзакций.\n"
            "Потери: $15,000.\n"
            "Hotfix: PR #891\n\n"
            "Приоритет: P0"
        )
        attachments = "\n\nВложения:\n1. https://files.example.com/logs/crash-2026-03-23.txt"
        parts = split_to_express(header, body, attachments)
        assert parts[0].startswith(header)
        assert "Вложения:" in parts[-1]
        for part in parts:
            assert len(part) <= MAX_MESSAGE_LENGTH


class TestSplitToTelegramLargeMessages:
    def test_long_body_with_file_caption_limit(self) -> None:
        """Full pipeline: header + long body + file → first part ≤ 1024."""
        header = "[Архитектор]:"
        body = "Описание файла с техническими требованиями и спецификациями. " * 20
        parts = split_to_telegram(header, body, first_part_limit=CAPTION_LENGTH)
        assert len(parts) >= 2
        assert len(parts[0]) <= CAPTION_LENGTH
        assert header in parts[0] or parts[0].startswith("[")
        for part in parts:
            assert len(part) <= MAX_MESSAGE_LENGTH

    def test_long_edit_body_fits_in_4096(self) -> None:
        """Edit body > 4096 should be split, first part ≤ 4096."""
        body = "Обновлённый текст требований. " * 200  # ~6000 chars
        parts = split_to_telegram(None, body)
        assert len(parts) >= 2
        for part in parts:
            assert len(part) <= MAX_MESSAGE_LENGTH

    def test_sprint_report_express_to_telegram(self) -> None:
        """Realistic sanitized Sprint report split for Telegram."""
        header = "[Тимлид]:"
        body = (
            "Итоги спринта #47 (10.03 — 21.03.2026)\n\n"
            "Метрики:\n"
            + "".join(f"• Метрика {i}: значение {i * 10}\n" for i in range(1, 100))
            + "\nБлокеры:\n"
            + "".join(f"{i}. Блокер номер {i} с описанием.\n" for i in range(1, 20))
        )
        parts = split_to_telegram(header, body)
        assert parts[0].startswith(header)
        for part in parts:
            assert len(part) <= MAX_MESSAGE_LENGTH
