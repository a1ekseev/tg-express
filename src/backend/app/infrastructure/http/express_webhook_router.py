from __future__ import annotations

from http import HTTPStatus

from fastapi import APIRouter, Depends, Request  # noqa: TC002 - Request must be runtime for FastAPI DI
from fastapi.responses import JSONResponse
from pybotx import Bot, build_command_accepted_response  # noqa: TC002

from app.infrastructure.http.deps import get_express_bot

router = APIRouter()


@router.post("/command")
async def bot_command(request: Request, bot: Bot = Depends(get_express_bot)) -> JSONResponse:  # noqa: B008
    raw_body = await request.json()
    request_headers = dict(request.headers)
    bot.async_execute_raw_bot_command(raw_body, request_headers=request_headers)
    return JSONResponse(build_command_accepted_response(), status_code=HTTPStatus.ACCEPTED)


@router.get("/status")
async def bot_status(request: Request, bot: Bot = Depends(get_express_bot)) -> JSONResponse:  # noqa: B008
    request_headers = dict(request.headers)
    result = await bot.raw_get_status(
        query_params=dict(request.query_params),
        request_headers=request_headers,
    )
    return JSONResponse(content=result)


@router.post("/notification/callback")
async def bot_notification_callback(request: Request, bot: Bot = Depends(get_express_bot)) -> JSONResponse:  # noqa: B008
    raw_body = await request.json()
    request_headers = dict(request.headers)
    await bot.set_raw_botx_method_result(raw_body, request_headers=request_headers)
    return JSONResponse(build_command_accepted_response(), status_code=HTTPStatus.ACCEPTED)
