from __future__ import annotations

import logging

import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.logging import LoggingIntegration


def init_sentry(dsn: str | None) -> None:
    """Initialize Sentry SDK if DSN is provided. Errors only, no tracing."""
    if not dsn:
        return

    sentry_sdk.init(
        dsn=dsn,
        traces_sample_rate=0,
        integrations=[
            FastApiIntegration(),
            LoggingIntegration(event_level=logging.ERROR),
        ],
    )
