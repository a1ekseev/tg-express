from app.application.utils.message_filter import classify_tg_message, should_forward_express_message
from app.domain.models import TgMessageAction


class TestClassifyTgMessage:
    def test_text_is_forward(self) -> None:
        assert classify_tg_message("text") == TgMessageAction.FORWARD

    def test_photo_is_forward(self) -> None:
        assert classify_tg_message("photo") == TgMessageAction.FORWARD

    def test_document_is_forward(self) -> None:
        assert classify_tg_message("document") == TgMessageAction.FORWARD

    def test_video_is_forward(self) -> None:
        assert classify_tg_message("video") == TgMessageAction.FORWARD

    def test_voice_is_forward(self) -> None:
        assert classify_tg_message("voice") == TgMessageAction.FORWARD

    def test_audio_is_forward(self) -> None:
        assert classify_tg_message("audio") == TgMessageAction.FORWARD

    def test_video_note_is_forward(self) -> None:
        assert classify_tg_message("video_note") == TgMessageAction.FORWARD

    def test_contact_is_forward(self) -> None:
        assert classify_tg_message("contact") == TgMessageAction.FORWARD

    def test_sticker_is_skip(self) -> None:
        assert classify_tg_message("sticker") == TgMessageAction.SKIP

    def test_animation_is_skip(self) -> None:
        assert classify_tg_message("animation") == TgMessageAction.SKIP

    def test_dice_is_skip(self) -> None:
        assert classify_tg_message("dice") == TgMessageAction.SKIP

    def test_game_is_skip(self) -> None:
        assert classify_tg_message("game") == TgMessageAction.SKIP

    def test_story_is_skip(self) -> None:
        assert classify_tg_message("story") == TgMessageAction.SKIP

    def test_new_chat_members_is_skip(self) -> None:
        assert classify_tg_message("new_chat_members") == TgMessageAction.SKIP

    def test_pinned_message_is_skip(self) -> None:
        assert classify_tg_message("pinned_message") == TgMessageAction.SKIP

    def test_location_is_system(self) -> None:
        assert classify_tg_message("location") == TgMessageAction.SYSTEM

    def test_venue_is_system(self) -> None:
        assert classify_tg_message("venue") == TgMessageAction.SYSTEM

    def test_poll_is_system(self) -> None:
        assert classify_tg_message("poll") == TgMessageAction.SYSTEM

    def test_unknown_type_is_system(self) -> None:
        assert classify_tg_message("some_future_type") == TgMessageAction.SYSTEM


class TestShouldForwardExpressMessage:
    def test_normal_message_forwarded(self) -> None:
        assert should_forward_express_message(has_sticker=False, has_location=False) is True

    def test_sticker_not_forwarded(self) -> None:
        assert should_forward_express_message(has_sticker=True, has_location=False) is False

    def test_location_not_forwarded(self) -> None:
        assert should_forward_express_message(has_sticker=False, has_location=True) is False

    def test_sticker_and_location_not_forwarded(self) -> None:
        assert should_forward_express_message(has_sticker=True, has_location=True) is False
