from http import HTTPStatus
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.infrastructure.http.express_webhook_router import router

_app = FastAPI()
_app.include_router(router)


@pytest.fixture(autouse=True)
def _reset_state() -> None:
    _app.state.express_bot = None


def _set_mock_bot() -> MagicMock:
    bot = MagicMock()
    bot.async_execute_raw_bot_command = MagicMock()
    bot.raw_get_status = AsyncMock(return_value={"status": "ok", "commands": []})
    bot.set_raw_botx_method_result = AsyncMock()
    _app.state.express_bot = bot
    return bot


class TestBotCommand:
    @pytest.mark.asyncio
    async def test_returns_503_when_bot_not_initialized(self) -> None:
        async with AsyncClient(transport=ASGITransport(app=_app), base_url="http://test") as client:
            resp = await client.post("/command", json={"command": "test"})
        assert resp.status_code == HTTPStatus.SERVICE_UNAVAILABLE

    @pytest.mark.asyncio
    async def test_returns_202_accepted(self) -> None:
        bot = _set_mock_bot()
        async with AsyncClient(transport=ASGITransport(app=_app), base_url="http://test") as client:
            resp = await client.post("/command", json={"command": "test"})
        assert resp.status_code == HTTPStatus.ACCEPTED
        assert resp.json() == {"result": "accepted"}
        bot.async_execute_raw_bot_command.assert_called_once()


class TestBotStatus:
    @pytest.mark.asyncio
    async def test_returns_503_when_bot_not_initialized(self) -> None:
        async with AsyncClient(transport=ASGITransport(app=_app), base_url="http://test") as client:
            resp = await client.get("/status")
        assert resp.status_code == HTTPStatus.SERVICE_UNAVAILABLE

    @pytest.mark.asyncio
    async def test_calls_raw_get_status(self) -> None:
        bot = _set_mock_bot()
        async with AsyncClient(transport=ASGITransport(app=_app), base_url="http://test") as client:
            resp = await client.get("/status?user_huid=abc")
        assert resp.status_code == HTTPStatus.OK
        bot.raw_get_status.assert_called_once()
        call_kwargs = bot.raw_get_status.call_args
        assert "user_huid" in call_kwargs.kwargs["query_params"]


class TestBotNotificationCallback:
    @pytest.mark.asyncio
    async def test_returns_503_when_bot_not_initialized(self) -> None:
        async with AsyncClient(transport=ASGITransport(app=_app), base_url="http://test") as client:
            resp = await client.post("/notification/callback", json={"sync_id": "test"})
        assert resp.status_code == HTTPStatus.SERVICE_UNAVAILABLE

    @pytest.mark.asyncio
    async def test_returns_202_accepted(self) -> None:
        bot = _set_mock_bot()
        async with AsyncClient(transport=ASGITransport(app=_app), base_url="http://test") as client:
            resp = await client.post("/notification/callback", json={"sync_id": "test"})
        assert resp.status_code == HTTPStatus.ACCEPTED
        assert resp.json() == {"result": "accepted"}
        bot.set_raw_botx_method_result.assert_called_once()
