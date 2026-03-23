from app.application.dto import TgEntityDTO
from app.application.utils.sanitize import (
    sanitize_to_express,
    sanitize_to_telegram,
    strip_emoji,
    strip_express_formatting,
    strip_tg_formatting,
)


class TestStripTgFormatting:
    def test_no_entities_returns_text(self) -> None:
        assert strip_tg_formatting("hello world", None) == "hello world"

    def test_empty_entities_returns_text(self) -> None:
        assert strip_tg_formatting("hello world", ()) == "hello world"

    def test_with_entities_returns_plain_text(self) -> None:
        entities = (TgEntityDTO(type="bold", offset=0, length=5),)
        assert strip_tg_formatting("hello world", entities) == "hello world"


class TestStripExpressFormatting:
    def test_removes_html_tags(self) -> None:
        assert strip_express_formatting("<b>bold</b> text") == "bold text"

    def test_removes_nested_tags(self) -> None:
        assert strip_express_formatting("<p><b>nested</b></p>") == "nested"

    def test_no_tags_unchanged(self) -> None:
        assert strip_express_formatting("plain text") == "plain text"

    def test_removes_anchor_tag(self) -> None:
        assert strip_express_formatting('<a href="https://example.com">link</a>') == "link"

    def test_empty_string(self) -> None:
        assert strip_express_formatting("") == ""


class TestStripEmoji:
    def test_removes_emoji(self) -> None:
        result = strip_emoji("hello 😀 world")
        assert "😀" not in result
        assert "hello" in result
        assert "world" in result

    def test_no_emoji_unchanged(self) -> None:
        assert strip_emoji("hello world") == "hello world"

    def test_only_emoji_returns_empty(self) -> None:
        result = strip_emoji("😀🎉🔥")
        assert result.strip() == ""

    def test_emoji_between_words(self) -> None:
        result = strip_emoji("привет🔥мир")
        assert "привет" in result
        assert "мир" in result


class TestSanitizeToExpress:
    def test_none_returns_none(self) -> None:
        assert sanitize_to_express(None) is None

    def test_strips_emoji_and_whitespace(self) -> None:
        result = sanitize_to_express("hello 😀 world")
        assert result is not None
        assert "😀" not in result
        assert "hello" in result

    def test_empty_after_strip_returns_none(self) -> None:
        assert sanitize_to_express("😀🎉") is None

    def test_plain_text_unchanged(self) -> None:
        assert sanitize_to_express("simple text") == "simple text"

    def test_with_entities(self) -> None:
        entities = (TgEntityDTO(type="bold", offset=0, length=6),)
        result = sanitize_to_express("simple text", entities)
        assert result == "simple text"


class TestSanitizeToTelegram:
    def test_none_returns_none(self) -> None:
        assert sanitize_to_telegram(None) is None

    def test_strips_html_and_emoji(self) -> None:
        result = sanitize_to_telegram("<b>bold</b> 😀 text")
        assert result is not None
        assert "<b>" not in result
        assert "😀" not in result
        assert "bold" in result

    def test_empty_after_strip_returns_none(self) -> None:
        assert sanitize_to_telegram("😀") is None

    def test_plain_text_unchanged(self) -> None:
        assert sanitize_to_telegram("simple text") == "simple text"
