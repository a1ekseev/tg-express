from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.infrastructure.http.express_webhook_router import router

_app = FastAPI()
_app.include_router(router)


@pytest.fixture(autouse=True)
def _reset_state() -> None:
    _app.state.express_bot = None  # type: ignore[assignment]


def _set_mock_bot() -> MagicMock:
    bot = MagicMock()
    bot.async_execute_raw_bot_command = AsyncMock()
    bot.raw_get_status = MagicMock(return_value={"status": "ok", "commands": []})
    bot.set_raw_botx_method_result = AsyncMock()
    _app.state.express_bot = bot
    return bot


class TestExpressWebhook:
    @pytest.mark.asyncio
    async def test_returns_503_when_bot_not_initialized(self) -> None:
        async with AsyncClient(transport=ASGITransport(app=_app), base_url="http://test") as client:
            resp = await client.post("/express/webhook", json={"command": "test"})
        assert resp.status_code == 503

    @pytest.mark.asyncio
    async def test_calls_async_execute_raw_bot_command(self) -> None:
        bot = _set_mock_bot()
        async with AsyncClient(transport=ASGITransport(app=_app), base_url="http://test") as client:
            resp = await client.post("/express/webhook", json={"command": "test"})
        assert resp.status_code == 200
        bot.async_execute_raw_bot_command.assert_called_once()


class TestExpressStatus:
    @pytest.mark.asyncio
    async def test_returns_503_when_bot_not_initialized(self) -> None:
        async with AsyncClient(transport=ASGITransport(app=_app), base_url="http://test") as client:
            resp = await client.get("/express/status")
        assert resp.status_code == 503

    @pytest.mark.asyncio
    async def test_calls_raw_get_status(self) -> None:
        bot = _set_mock_bot()
        async with AsyncClient(transport=ASGITransport(app=_app), base_url="http://test") as client:
            resp = await client.get("/express/status?user_huid=abc")
        assert resp.status_code == 200
        bot.raw_get_status.assert_called_once()
        call_kwargs = bot.raw_get_status.call_args
        assert "user_huid" in call_kwargs.kwargs["query_params"]


class TestExpressCallback:
    @pytest.mark.asyncio
    async def test_returns_503_when_bot_not_initialized(self) -> None:
        async with AsyncClient(transport=ASGITransport(app=_app), base_url="http://test") as client:
            resp = await client.post("/express/notification/callback", json={"sync_id": "test"})
        assert resp.status_code == 503

    @pytest.mark.asyncio
    async def test_calls_set_raw_botx_method_result(self) -> None:
        bot = _set_mock_bot()
        async with AsyncClient(transport=ASGITransport(app=_app), base_url="http://test") as client:
            resp = await client.post("/express/notification/callback", json={"sync_id": "test"})
        assert resp.status_code == 200
        bot.set_raw_botx_method_result.assert_called_once()
