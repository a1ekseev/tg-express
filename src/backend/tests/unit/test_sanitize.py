from app.application.dto import TgEntityDTO
from app.application.utils.sanitize import (
    sanitize_to_express,
    sanitize_to_telegram,
    strip_emoji,
    strip_express_formatting,
    strip_tg_formatting,
)

# ============================================================
# strip_tg_formatting
# ============================================================


class TestStripTgFormatting:
    def test_no_entities_returns_text(self) -> None:
        assert strip_tg_formatting("hello world", None) == "hello world"

    def test_empty_entities_returns_text(self) -> None:
        assert strip_tg_formatting("hello world", ()) == "hello world"

    def test_with_entities_returns_plain_text(self) -> None:
        entities = (TgEntityDTO(type="bold", offset=0, length=5),)
        assert strip_tg_formatting("hello world", entities) == "hello world"

    def test_text_link_appends_url(self) -> None:
        entities = (TgEntityDTO(type="text_link", offset=6, length=8, url="https://example.com"),)
        result = strip_tg_formatting("Visit our site for more info", entities)
        assert result == "Visit our site (https://example.com) for more info"

    def test_text_link_at_end(self) -> None:
        entities = (TgEntityDTO(type="text_link", offset=10, length=4, url="https://docs.com"),)
        result = strip_tg_formatting("Смотрите тут!", entities)
        assert "https://docs.com" in result

    def test_multiple_text_links(self) -> None:
        text = "Read docs and changelog for details"
        entities = (
            TgEntityDTO(type="text_link", offset=5, length=4, url="https://docs.com"),
            TgEntityDTO(type="text_link", offset=14, length=9, url="https://changelog.com"),
        )
        result = strip_tg_formatting(text, entities)
        assert "https://docs.com" in result
        assert "https://changelog.com" in result
        assert "Read" in result
        assert "details" in result

    def test_text_link_without_url_ignored(self) -> None:
        entities = (TgEntityDTO(type="text_link", offset=0, length=5, url=None),)
        assert strip_tg_formatting("hello world", entities) == "hello world"

    def test_non_text_link_entities_ignored(self) -> None:
        entities = (
            TgEntityDTO(type="bold", offset=0, length=5),
            TgEntityDTO(type="italic", offset=6, length=5),
            TgEntityDTO(type="code", offset=12, length=4),
        )
        assert strip_tg_formatting("hello world test end", entities) == "hello world test end"


# ============================================================
# strip_express_formatting
# ============================================================


class TestStripExpressFormatting:
    # --- Basic tag removal ---
    def test_removes_html_tags(self) -> None:
        assert strip_express_formatting("<b>bold</b> text") == "bold text"

    def test_removes_nested_tags(self) -> None:
        assert strip_express_formatting("<p><b>nested</b></p>") == "nested\n"

    def test_no_tags_unchanged(self) -> None:
        assert strip_express_formatting("plain text") == "plain text"

    def test_removes_anchor_tag(self) -> None:
        assert strip_express_formatting('<a href="https://example.com">link</a>') == "link"

    def test_empty_string(self) -> None:
        assert strip_express_formatting("") == ""

    # --- <br> → newline ---
    def test_br_replaced_with_newline(self) -> None:
        assert strip_express_formatting("line1<br/>line2") == "line1\nline2"

    def test_br_with_space_replaced(self) -> None:
        assert strip_express_formatting("line1<br />line2") == "line1\nline2"

    def test_br_no_slash_replaced(self) -> None:
        assert strip_express_formatting("line1<br>line2") == "line1\nline2"

    # --- HTML entities ---
    def test_decodes_html_entities(self) -> None:
        assert strip_express_formatting("5 &gt; 3 and 1 &lt; 2") == "5 > 3 and 1 < 2"

    def test_decodes_amp_entity(self) -> None:
        assert strip_express_formatting("Tom &amp; Jerry") == "Tom & Jerry"

    def test_decodes_nbsp(self) -> None:
        assert strip_express_formatting("hello&nbsp;world") == "hello\xa0world"

    def test_decodes_mdash(self) -> None:
        assert strip_express_formatting("CRM &mdash; done") == "CRM \u2014 done"

    def test_decodes_euro(self) -> None:
        assert strip_express_formatting("price: 100&euro;") == "price: 100\u20ac"

    # --- No false positives ---
    def test_no_false_positive_on_less_than(self) -> None:
        assert strip_express_formatting("if x < 5 and y > 3") == "if x < 5 and y > 3"

    def test_no_false_positive_on_math_expression(self) -> None:
        assert strip_express_formatting("count < 10") == "count < 10"

    def test_style_attributes_removed(self) -> None:
        assert strip_express_formatting('<span style="color:red">text</span>') == "text"

    def test_markdown_not_stripped(self) -> None:
        assert strip_express_formatting("**bold** text") == "**bold** text"

    # --- Self-closing tags ---
    def test_hr_self_closing_removed(self) -> None:
        result = strip_express_formatting("text<hr/>more")
        assert "<hr" not in result

    def test_hr_space_self_closing_removed(self) -> None:
        result = strip_express_formatting("text<hr />more")
        assert "<hr" not in result

    def test_img_self_closing_removed(self) -> None:
        result = strip_express_formatting('text<img src="photo.jpg"/>more')
        assert "<img" not in result
        assert "text" in result
        assert "more" in result

    # --- Block elements → newline (prevent gluing) ---
    def test_li_elements_not_glued(self) -> None:
        result = strip_express_formatting("<li>Item 1</li><li>Item 2</li>")
        assert "Item 1" in result
        assert "Item 2" in result
        assert "Item 1Item 2" not in result

    def test_p_elements_not_glued(self) -> None:
        result = strip_express_formatting("<p>Para 1</p><p>Para 2</p>")
        assert "Para 1" in result
        assert "Para 2" in result
        assert "Para 1Para 2" not in result

    def test_complex_nested_html(self) -> None:
        html = '<div class="msg"><p>Important</p><ul><li>Item 1</li><li>Item 2</li></ul></div>'
        result = strip_express_formatting(html)
        assert "Important" in result
        assert "Item 1" in result
        assert "Item 2" in result
        assert "ImportantItem" not in result
        assert "Item 1Item 2" not in result


# ============================================================
# strip_emoji
# ============================================================


class TestStripEmoji:
    # --- Basic ---
    def test_removes_emoji(self) -> None:
        result = strip_emoji("hello 😀 world")
        assert "😀" not in result
        assert "hello" in result
        assert "world" in result

    def test_no_emoji_unchanged(self) -> None:
        assert strip_emoji("hello world") == "hello world"

    def test_only_emoji_returns_spaces(self) -> None:
        result = strip_emoji("😀🎉🔥")
        assert result.strip() == ""

    # --- Word boundaries (P1 fix) ---
    def test_emoji_between_words_no_glue(self) -> None:
        result = strip_emoji("привет🔥мир")
        assert "привет" in result
        assert "мир" in result
        assert "приветмир" not in result

    def test_urgent_emoji_no_glue(self) -> None:
        result = strip_emoji("Срочно🔥нужна помощь")
        assert "Срочно" in result
        assert "нужна" in result
        assert "Срочнонужна" not in result

    def test_multiple_emoji_between_words(self) -> None:
        result = strip_emoji("Отлично💪поехали🚀")
        assert "Отлично" in result
        assert "поехали" in result
        assert "Отличнопоехали" not in result

    def test_emoji_with_existing_spaces(self) -> None:
        result = strip_emoji("Готово✅ отправил✅ проверь✅")
        assert "Готово" in result
        assert "отправил" in result
        assert "проверь" in result

    def test_trailing_emoji(self) -> None:
        result = strip_emoji("Да👍")
        assert "Да" in result

    # --- Preserves ASCII and text symbols ---
    def test_preserves_digits(self) -> None:
        assert strip_emoji("Заявка 4521 от 15.03.2026") == "Заявка 4521 от 15.03.2026"

    def test_preserves_hash(self) -> None:
        assert strip_emoji("Тикет #12345") == "Тикет #12345"

    def test_preserves_asterisk(self) -> None:
        assert strip_emoji("5* rating") == "5* rating"

    def test_preserves_copyright(self) -> None:
        assert strip_emoji("© 2024 Company") == "© 2024 Company"

    def test_preserves_registered(self) -> None:
        assert strip_emoji("Brand® here") == "Brand® here"

    def test_preserves_phone_number(self) -> None:
        assert strip_emoji("+7 (999) 123-45-67") == "+7 (999) 123-45-67"

    def test_preserves_url(self) -> None:
        url = "https://example.com/page?id=123&sort=asc"
        assert strip_emoji(url) == url

    # --- Space collapsing ---
    def test_collapses_double_spaces(self) -> None:
        result = strip_emoji("word 😀 word")
        assert result == "word word"

    def test_collapses_triple_spaces(self) -> None:
        result = strip_emoji("a 😀 😀 b")
        assert "  " not in result

    # --- Complex emoji sequences ---
    def test_skin_tone_modifier(self) -> None:
        result = strip_emoji("hello 👋🏻 world")
        assert "hello" in result
        assert "world" in result

    def test_family_zwj_sequence(self) -> None:
        result = strip_emoji("test 👨\u200d👩\u200d👧\u200d👦 end")
        assert "test" in result
        assert "end" in result

    def test_flag_emoji(self) -> None:
        result = strip_emoji("hello 🇷🇺 world")
        assert "hello" in result
        assert "world" in result

    # --- Keycap emoji: digit preserved, styling stripped ---
    def test_keycap_digit_preserved(self) -> None:
        result = strip_emoji("Пункт 1\ufe0f\u20e3")
        assert "1" in result
        assert "Пункт" in result

    def test_keycap_hash_preserved(self) -> None:
        result = strip_emoji("Press #\ufe0f\u20e3")
        assert "#" in result


# ============================================================
# sanitize_to_express (full pipeline)
# ============================================================


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

    def test_business_message_preserved(self) -> None:
        msg = "Заявка #4521 от 15.03.2026. Стоимость: 25000₽"
        assert sanitize_to_express(msg) == msg

    def test_phone_number_preserved(self) -> None:
        msg = "Телефон: +7(495)123-45-67"
        assert sanitize_to_express(msg) == msg

    def test_error_code_preserved(self) -> None:
        msg = "Код ошибки: 502. Попробуйте через 5 минут"
        assert sanitize_to_express(msg) == msg


class TestSanitizeToExpressLargeMessages:
    def test_api_changelog(self) -> None:
        msg = (
            "Коллеги, обновил документацию по API v2.3.1.\n\n"
            "Основные изменения:\n"
            "1. Endpoint /api/users/{id}/settings — добавлен параметр locale (string, ISO 639-1)\n"
            "2. Лимит rate-limiting увеличен с 100 до 500 req/min для Premium-аккаунтов\n"
            "3. Поле created_at теперь возвращает ISO 8601 с timezone (2026-03-23T14:30:00+03:00)\n"
            "4. Удалён deprecated endpoint /api/v1/legacy (был помечен deprecated с 01.01.2025)\n\n"
            "Swagger: https://api.company.com/docs#/v2.3.1\n"
            "Changelog: https://wiki.company.com/changelog?version=2.3.1&format=detailed\n\n"
            "Важно: миграция БД обязательна! Скрипт: ./scripts/migrate_v231.sh --dry-run\n"
            "Оценка даунтайма: ~15 минут (при 50GB+ базе — до 30 мин).\n\n"
            "@team_backend пожалуйста проверьте до 25.03 EOD.\n"
            "Тикет: PROJ-4521"
        )
        result = sanitize_to_express(msg)
        assert result is not None
        assert "v2.3.1" in result
        assert "500" in result
        assert "https://api.company.com/docs#/v2.3.1" in result
        assert "PROJ-4521" in result
        assert "639-1" in result
        assert "+03:00" in result
        assert "@team_backend" in result
        assert "~15" in result
        assert "50GB+" in result
        assert "--dry-run" in result

    def test_production_bug_with_emoji(self) -> None:
        msg = (
            "Баг в продакшене 🔥🔥🔥\n\n"
            "Stack trace:\n"
            '  File "/app/services/payment.py", line 142, in process_payment\n'
            "    amount = Decimal(request.amount) * Decimal('1.05')\n"
            '  File "/app/services/payment.py", line 145, in process_payment\n'
            "    if amount > MAX_PAYMENT:  # MAX_PAYMENT = 999999.99\n"
            "        raise ValueError(f'Amount {amount} exceeds limit')\n\n"
            "Затронуты: ~2500 транзакций за последние 3 часа.\n"
            "Потери: $15,000 (расчёт: 2500 * $6 avg).\n"
            "Hotfix: PR #891 (ветка fix/payment-overflow-check)\n\n"
            "Приоритет: P0 🚨\n"
            "Дежурный: @oncall_team"
        )
        result = sanitize_to_express(msg)
        assert result is not None
        assert "142" in result
        assert "'1.05'" in result
        assert "999999.99" in result
        assert "2500" in result
        assert "$15,000" in result
        assert "PR #891" in result
        assert "🔥" not in result
        assert "🚨" not in result

    def test_message_with_emoji_word_boundaries(self) -> None:
        result = sanitize_to_express("Срочно🔥нужна помощь! Отлично💪поехали🚀")
        assert result is not None
        assert "Срочнонужна" not in result
        assert "Отличнопоехали" not in result
        assert "Срочно" in result
        assert "нужна" in result
        assert "Отлично" in result
        assert "поехали" in result

    def test_text_link_entity_preserves_url(self) -> None:
        text = "Подробности в нашей документации, обращайтесь"
        entities = (TgEntityDTO(type="text_link", offset=21, length=13, url="https://docs.company.com/api"),)
        result = sanitize_to_express(text, entities)
        assert result is not None
        assert "https://docs.company.com/api" in result
        assert "документации" in result
        assert "Подробности" in result


# ============================================================
# sanitize_to_telegram (full pipeline)
# ============================================================


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

    def test_br_becomes_newline(self) -> None:
        result = sanitize_to_telegram("Температура: 25°C<br/>Влажность: 60%")
        assert result == "Температура: 25°C\nВлажность: 60%"

    def test_html_entities_decoded(self) -> None:
        result = sanitize_to_telegram("Tom &amp; Jerry: score 5 &gt; 3")
        assert result == "Tom & Jerry: score 5 > 3"

    def test_less_than_in_text_preserved(self) -> None:
        result = sanitize_to_telegram("if x < 5 and y > 3")
        assert result == "if x < 5 and y > 3"

    def test_full_express_message(self) -> None:
        msg = "<b>Важно!</b> Статус: 200<br/>Детали: x &gt; 5"
        result = sanitize_to_telegram(msg)
        assert result is not None
        assert "Важно!" in result
        assert "200" in result
        assert "x > 5" in result
        assert "\n" in result


class TestSanitizeToTelegramLargeMessages:
    def test_sprint_report(self) -> None:
        msg = (
            "<b>Итоги спринта #47</b> (10.03 — 21.03.2026)<br/><br/>"
            "<b>Метрики:</b><br/>"
            "• Velocity: 85 SP (план: 80 SP, +6.25%)<br/>"
            "• Закрыто тикетов: 34/38 (89.5%)<br/>"
            "• Code review turnaround: &lt;4h (цель: &lt;8h)<br/>"
            "• Bug escape rate: 2.6% (цель: &lt;5%)<br/><br/>"
            "<b>Блокеры:</b><br/>"
            "1. Интеграция с CRM &mdash; ждём API key от партнёра (ETA: 25.03)<br/>"
            "2. CI/CD pipeline &mdash; flaky test в <code>test_payment_flow</code> (PR #892)"
        )
        result = sanitize_to_telegram(msg)
        assert result is not None
        # Tags removed
        assert "<b>" not in result
        assert "<code>" not in result
        assert "<br" not in result
        # Entities decoded
        assert "<4h" in result
        assert "<8h" in result
        assert "<5%" in result
        assert "\u2014" in result  # &mdash; → em dash
        # Digits preserved
        assert "#47" in result
        assert "85" in result
        assert "34/38" in result
        assert "89.5%" in result
        assert "6.25%" in result
        assert "25.03" in result
        assert "#892" in result
        # Newlines present
        assert "\n" in result

    def test_load_test_results(self) -> None:
        msg = (
            "Результат нагрузочного тестирования:<br/><br/>"
            "<pre>Scenario    | RPS  | p50  | p99  | Errors\n"
            "------------|------|------|------|---------\n"
            "Login       | 1500 | 12ms | 85ms | 0.01%\n"
            "Search      | 3000 | 45ms |250ms | 0.05%\n"
            "Checkout    | 800  | 95ms |450ms | 0.12%</pre><br/><br/>"
            "Вывод: p99 для Checkout &gt; 400ms &mdash; нужна оптимизация.<br/>"
            "CPU usage: 78% (лимит: &lt;80%), Memory: 12.5GB/16GB (78%)."
        )
        result = sanitize_to_telegram(msg)
        assert result is not None
        # Table preserved
        assert "|" in result
        assert "1500" in result
        assert "12ms" in result
        assert "0.01%" in result
        assert "3000" in result
        # Entities decoded
        assert "> 400ms" in result or ">400ms" in result
        assert "<80%" in result or "< 80%" in result
        assert "12.5GB" in result

    def test_block_elements_not_glued(self) -> None:
        msg = "<p>Параграф 1</p><p>Параграф 2</p><ul><li>Пункт А</li><li>Пункт Б</li></ul>"
        result = sanitize_to_telegram(msg)
        assert result is not None
        assert "Параграф 1" in result
        assert "Параграф 2" in result
        assert "Пункт А" in result
        assert "Пункт Б" in result
        # Not glued
        assert "Параграф 1Параграф 2" not in result
        assert "Пункт АПункт Б" not in result

    def test_less_than_in_code(self) -> None:
        result = sanitize_to_telegram('if (count < 10) alert("error")')
        assert result is not None
        assert "count" in result
        assert "10" in result
        assert "alert" in result
        # < should NOT be eaten as a tag
        assert "count < 10" in result or "count <10" in result

    def test_html_entities_full(self) -> None:
        result = sanitize_to_telegram("Tom &amp; Jerry: 5 &gt; 3, x &lt; 10, price: 100&euro;")
        assert result is not None
        assert "Tom & Jerry" in result
        assert "5 > 3" in result
        assert "x < 10" in result
        assert "100\u20ac" in result  # €
