from app.infrastructure.db.employee_repo import UNSET, _Unset


class TestUnsetSentinel:
    def test_unset_is_not_none(self) -> None:
        assert UNSET is not None

    def test_unset_isinstance(self) -> None:
        assert isinstance(UNSET, _Unset)

    def test_none_not_unset(self) -> None:
        assert not isinstance(None, _Unset)

    def test_string_not_unset(self) -> None:
        assert not isinstance("text", _Unset)

    def test_unset_is_singleton(self) -> None:
        assert UNSET is _Unset.UNSET
