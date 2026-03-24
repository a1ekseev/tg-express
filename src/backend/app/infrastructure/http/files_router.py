from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID  # noqa: TC003 - needed at runtime for path parameter

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.infrastructure.http.deps import get_s3_storage

if TYPE_CHECKING:
    from app.infrastructure.s3.storage import S3Storage

router = APIRouter(prefix="/api/files")


@router.get("/{file_uuid}")
async def download_file(file_uuid: UUID, s3: S3Storage = Depends(get_s3_storage)) -> StreamingResponse:  # noqa: B008
    s3_key = str(file_uuid)
    try:
        meta = await s3.head_object(s3_key)
    except Exception:  # noqa: BLE001
        raise HTTPException(status_code=404, detail="File not found")  # noqa: B904

    filename = meta.get("filename") or s3_key

    return StreamingResponse(
        s3.get_object_stream(s3_key),
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
