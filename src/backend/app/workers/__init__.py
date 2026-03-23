from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import FastAPI

_WORKER_MODULES: dict[str, str] = {
    "to_express": "app.workers.to_express_worker",
    "to_telegram": "app.workers.to_telegram_worker",
    "admin_api": "app.workers.admin_api",
}


def __getattr__(name: str) -> FastAPI:
    if name in _WORKER_MODULES:
        module = importlib.import_module(_WORKER_MODULES[name])
        return module.app
    raise AttributeError(f"module 'app.workers' has no attribute {name!r}")
