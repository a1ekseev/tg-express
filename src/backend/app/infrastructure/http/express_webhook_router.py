from __future__ import annotations

from fastapi import APIRouter, Depends, Request  # noqa: TC002 - Request must be runtime for FastAPI DI
from fastapi.responses import JSONResponse
from pybotx import Bot, build_command_accepted_response  # noqa: TC002

from app.infrastructure.http.deps import get_express_bot

router = APIRouter()


@router.post("/express/webhook")
async def express_webhook(request: Request, bot: Bot = Depends(get_express_bot)) -> JSONResponse:  # noqa: B008
    raw_body = await request.json()
    request_headers = dict(request.headers)
    await bot.async_execute_raw_bot_command(raw_body, request_headers=request_headers)  # type: ignore[unused-awaitable]
    response = build_command_accepted_response()
    return JSONResponse(content=response)


@router.get("/express/status")
async def express_status(request: Request, bot: Bot = Depends(get_express_bot)) -> JSONResponse:  # noqa: B008
    request_headers = dict(request.headers)
    result = bot.raw_get_status(
        query_params=dict(request.query_params),
        request_headers=request_headers,
    )
    return JSONResponse(content=result)


@router.post("/express/notification/callback")
async def express_callback(request: Request, bot: Bot = Depends(get_express_bot)) -> JSONResponse:  # noqa: B008
    raw_body = await request.json()
    request_headers = dict(request.headers)
    await bot.set_raw_botx_method_result(raw_body, request_headers=request_headers)
    return JSONResponse(content={"status": "ok"})
