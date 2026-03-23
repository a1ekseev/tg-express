from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pybotx import Bot, build_command_accepted_response  # noqa: TC002 - Bot used at runtime for global type

if TYPE_CHECKING:
    from fastapi import Request

router = APIRouter()

_express_bot: Bot | None = None


def set_express_bot(bot: Bot) -> None:
    global _express_bot  # noqa: PLW0603
    _express_bot = bot


@router.post("/express/webhook")
async def express_webhook(request: Request) -> JSONResponse:
    bot = _express_bot
    if bot is None:
        return JSONResponse(status_code=503, content={"detail": "Bot not initialized"})

    raw_body = await request.json()
    await bot.async_execute_raw_bot_command(raw_body)  # type: ignore[unused-awaitable]
    response = build_command_accepted_response()
    return JSONResponse(content=response)
