from uuid import uuid4

from app.domain.models import (
    ChannelPair,
    Employee,
    EventType,
    MessageDirection,
    MessageStatus,
    SystemChannelReason,
    TgMessageAction,
)


class TestEnums:
    def test_event_type_values(self) -> None:
        assert EventType.NEW_MESSAGE == "new_message"
        assert EventType.EDIT_MESSAGE == "edit_message"
        assert EventType.DELETE_MESSAGE == "delete_message"

    def test_message_status_values(self) -> None:
        assert MessageStatus.PENDING == "pending"
        assert MessageStatus.SENT == "sent"
        assert MessageStatus.FAILED == "failed"

    def test_message_direction_values(self) -> None:
        assert MessageDirection.TG_TO_EXPRESS == "tg_to_express"
        assert MessageDirection.EXPRESS_TO_TG == "express_to_tg"

    def test_tg_message_action_values(self) -> None:
        assert TgMessageAction.FORWARD == "forward"
        assert TgMessageAction.SYSTEM == "system"
        assert TgMessageAction.SKIP == "skip"

    def test_system_channel_reason_values(self) -> None:
        assert SystemChannelReason.UNAPPROVED_CHANNEL == "unapproved_channel"
        assert SystemChannelReason.UNSUPPORTED_TYPE == "unsupported_type"


class TestDataclasses:
    def test_channel_pair_frozen(self) -> None:
        cp = ChannelPair(id=uuid4(), tg_chat_id=123, express_chat_id=None, is_approved=False, name="test")
        assert cp.tg_chat_id == 123

    def test_employee_frozen(self) -> None:
        emp = Employee(
            id=uuid4(),
            tg_user_id=456,
            express_huid=None,
            full_name="Test",
            position="Dev",
            tg_name=None,
            express_name=None,
        )
        assert emp.position == "Dev"

    def test_employee_with_names(self) -> None:
        emp = Employee(
            id=uuid4(),
            tg_user_id=456,
            express_huid=uuid4(),
            full_name="Иван Иванов",
            position="Архитектор",
            tg_name="Ivan Ivanov",
            express_name="Иван",
        )
        assert emp.tg_name == "Ivan Ivanov"
        assert emp.express_name == "Иван"
