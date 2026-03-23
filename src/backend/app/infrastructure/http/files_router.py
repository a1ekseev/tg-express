from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID  # noqa: TC003 - needed at runtime for path parameter

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

if TYPE_CHECKING:
    from app.infrastructure.s3.storage import S3Storage

router = APIRouter(prefix="/api/files")

# Injected at worker startup
_s3_storage: S3Storage | None = None


def set_s3_storage(storage: S3Storage) -> None:
    global _s3_storage  # noqa: PLW0603
    _s3_storage = storage


@router.get("/{file_uuid}/{filename}")
async def download_file(file_uuid: UUID, filename: str) -> StreamingResponse:
    if _s3_storage is None:
        raise HTTPException(status_code=503, detail="Storage not initialized")

    s3_key = f"{file_uuid}/{filename}"
    try:
        stream = _s3_storage.get_object_stream(s3_key)
    except Exception:  # noqa: BLE001
        raise HTTPException(status_code=404, detail="File not found")  # noqa: B904

    return StreamingResponse(
        stream,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
