from app.application.utils.message_splitter import MAX_MESSAGE_LENGTH, split_to_express, split_to_telegram


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
        # Body fills last chunk completely, forcing attachments into a new part
        body = "x" * (MAX_MESSAGE_LENGTH - len("[N]:") - 1)  # fills first chunk exactly
        body += " " + "y" * (MAX_MESSAGE_LENGTH - 1)  # fills second chunk nearly full
        attachments = "\n\nВложения:\n1. url"
        parts = split_to_express("[N]:", body, attachments)
        assert len(parts) >= 3
        assert "Вложения:" in parts[-1]
        # Attachments are in a separate last part
        assert parts[-1].strip().startswith("Вложения:")

    def test_empty_body_string(self) -> None:
        parts = split_to_express("[Name]:", "", None)
        assert len(parts) == 1
        assert parts[0] == "[Name]:\n"


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
