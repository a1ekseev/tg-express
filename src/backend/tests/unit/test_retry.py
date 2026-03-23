import asyncio

import pytest

from app.application.utils.retry import PermanentError, with_retry


class _TransientError(Exception):
    pass


class _RetryAfterError(Exception):
    def __init__(self, retry_after: float) -> None:
        self.retry_after = retry_after
        super().__init__(f"retry after {retry_after}s")


class TestWithRetry:
    @pytest.mark.asyncio
    async def test_success_on_first_attempt(self) -> None:
        async def fn() -> str:
            return "ok"

        result = await with_retry(fn)
        assert result == "ok"

    @pytest.mark.asyncio
    async def test_retries_on_transient_error(self) -> None:
        calls = 0

        async def fn() -> str:
            nonlocal calls
            calls += 1
            if calls < 3:
                raise _TransientError("transient")
            return "ok"

        result = await with_retry(fn, max_attempts=3, base_delay=0.01)
        assert result == "ok"
        assert calls == 3

    @pytest.mark.asyncio
    async def test_raises_after_max_attempts(self) -> None:
        async def fn() -> str:
            raise _TransientError("always fails")

        with pytest.raises(_TransientError, match="always fails"):
            await with_retry(fn, max_attempts=2, base_delay=0.01)

    @pytest.mark.asyncio
    async def test_permanent_error_not_retried(self) -> None:
        calls = 0

        async def fn() -> str:
            nonlocal calls
            calls += 1
            raise PermanentError(ValueError("bad input"))

        with pytest.raises(PermanentError):
            await with_retry(fn, max_attempts=3, base_delay=0.01)
        assert calls == 1

    @pytest.mark.asyncio
    async def test_retry_after_attribute_used_for_delay(self) -> None:
        calls = 0

        async def fn() -> str:
            nonlocal calls
            calls += 1
            if calls == 1:
                raise _RetryAfterError(retry_after=0.01)
            return "ok"

        result = await with_retry(fn, max_attempts=2, base_delay=100.0)
        assert result == "ok"
        assert calls == 2

    @pytest.mark.asyncio
    async def test_passes_args_and_kwargs(self) -> None:
        async def fn(a: int, b: int, *, c: int) -> int:
            return a + b + c

        result = await with_retry(fn, 1, 2, c=3)
        assert result == 6

    @pytest.mark.asyncio
    async def test_exponential_backoff_delay(self) -> None:
        calls: list[float] = []

        async def fn() -> str:
            calls.append(asyncio.get_event_loop().time())
            if len(calls) < 3:
                raise _TransientError("retry")
            return "ok"

        await with_retry(fn, max_attempts=3, base_delay=0.05, max_delay=1.0)
        assert len(calls) == 3
        # Second delay should be roughly 2x the first
        delay1 = calls[1] - calls[0]
        delay2 = calls[2] - calls[1]
        assert delay1 >= 0.04  # base_delay * 2^0 = 0.05
        assert delay2 >= 0.08  # base_delay * 2^1 = 0.10
