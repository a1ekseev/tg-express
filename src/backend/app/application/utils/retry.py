"""Async retry with exponential backoff for transient errors."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

logger = logging.getLogger(__name__)


class PermanentError(Exception):
    """Wraps an exception that should NOT be retried."""

    def __init__(self, cause: Exception) -> None:
        self.cause = cause
        super().__init__(str(cause))


async def with_retry[T](
    fn: Callable[..., Awaitable[T]],
    *args: object,
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    **kwargs: object,
) -> T:
    """Call *fn* with retry on exception. Non-matching exceptions propagate immediately.

    If the exception has a ``retry_after`` attribute (e.g. TelegramRetryAfter),
    that value is used as sleep duration instead of exponential backoff.
    """
    last_exc: Exception | None = None

    for attempt in range(max_attempts):
        try:
            return await fn(*args, **kwargs)
        except PermanentError:
            raise
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if attempt + 1 >= max_attempts:
                break

            retry_after = getattr(exc, "retry_after", None)
            delay = float(retry_after) if retry_after is not None else min(base_delay * (2**attempt), max_delay)

            logger.warning(
                "Retry %d/%d after %.1fs: %s: %s",
                attempt + 1,
                max_attempts,
                delay,
                type(exc).__name__,
                exc,
            )
            await asyncio.sleep(delay)

    raise last_exc  # type: ignore[misc]
