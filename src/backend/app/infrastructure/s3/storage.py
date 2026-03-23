from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


class S3Storage:
    def __init__(self, client: Any, bucket: str, base_url: str) -> None:  # noqa: ANN401
        self._client = client
        self._bucket = bucket
        self._base_url = base_url.rstrip("/")

    async def ensure_bucket(self) -> None:
        try:
            await asyncio.to_thread(self._client.head_bucket, Bucket=self._bucket)
        except ClientError:
            logger.info("Creating S3 bucket %s", self._bucket)
            await asyncio.to_thread(self._client.create_bucket, Bucket=self._bucket)

    async def upload(self, key: str, data: bytes, content_type: str) -> None:
        logger.info("S3 upload key=%s content_type=%s", key, content_type)
        await asyncio.to_thread(
            self._client.put_object,
            Bucket=self._bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
        )

    async def download(self, key: str) -> tuple[bytes, str]:
        logger.info("S3 download key=%s", key)
        response: dict[str, Any] = await asyncio.to_thread(
            self._client.get_object,
            Bucket=self._bucket,
            Key=key,
        )
        body: bytes = response["Body"].read()
        content_type: str = response.get("ContentType", "application/octet-stream")
        return body, content_type

    async def get_object_stream(self, key: str) -> AsyncIterator[bytes]:
        response: dict[str, Any] = await asyncio.to_thread(
            self._client.get_object,
            Bucket=self._bucket,
            Key=key,
        )
        body = response["Body"]
        chunk_size = 65536
        while True:
            chunk: bytes = await asyncio.to_thread(body.read, chunk_size)
            if not chunk:
                break
            yield chunk

    def get_download_url(self, s3_key: str) -> str:
        return f"{self._base_url}/api/files/{s3_key}"

    async def configure_lifecycle(self, ttl_days: int) -> None:
        logger.info("S3 configuring lifecycle ttl_days=%d bucket=%s", ttl_days, self._bucket)
        await asyncio.to_thread(
            self._client.put_bucket_lifecycle_configuration,
            Bucket=self._bucket,
            LifecycleConfiguration={
                "Rules": [
                    {
                        "ID": "tg-express-file-ttl",
                        "Status": "Enabled",
                        "Filter": {"Prefix": ""},
                        "Expiration": {"Days": ttl_days},
                    }
                ]
            },
        )

    @staticmethod
    def generate_s3_key(filename: str) -> str:
        return f"{uuid4()}/{filename}"
