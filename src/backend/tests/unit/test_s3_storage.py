"""Tests for S3Storage filename encoding in metadata."""

from __future__ import annotations

import urllib.parse
from unittest.mock import MagicMock

import pytest

from app.infrastructure.s3.storage import S3Storage


def _make_storage() -> S3Storage:
    mock_client = MagicMock()
    return S3Storage(mock_client, "test-bucket", "https://example.com")


class TestUploadFilenameEncoding:
    @pytest.mark.asyncio
    async def test_cyrillic_filename_encoded(self) -> None:
        storage = _make_storage()
        await storage.upload("key1", b"data", "text/csv", filename="Отчёт IP.csv")
        call_kwargs = storage._client.put_object.call_args.kwargs  # noqa: SLF001
        metadata = call_kwargs["Metadata"]
        assert metadata["filename"] == urllib.parse.quote("Отчёт IP.csv")
        assert metadata["filename"].isascii()

    @pytest.mark.asyncio
    async def test_ascii_filename_unchanged(self) -> None:
        storage = _make_storage()
        await storage.upload("key2", b"data", "text/csv", filename="report.csv")
        call_kwargs = storage._client.put_object.call_args.kwargs  # noqa: SLF001
        metadata = call_kwargs["Metadata"]
        assert metadata["filename"] == "report.csv"

    @pytest.mark.asyncio
    async def test_no_filename_no_metadata(self) -> None:
        storage = _make_storage()
        await storage.upload("key3", b"data", "text/csv")
        call_kwargs = storage._client.put_object.call_args.kwargs  # noqa: SLF001
        assert call_kwargs["Metadata"] == {}


class TestHeadObjectFilenameDecoding:
    @pytest.mark.asyncio
    async def test_decodes_encoded_filename(self) -> None:
        storage = _make_storage()
        encoded = urllib.parse.quote("Отчёт IP.csv")
        storage._client.head_object.return_value = {"Metadata": {"filename": encoded}}  # noqa: SLF001
        meta = await storage.head_object("key1")
        assert meta["filename"] == "Отчёт IP.csv"

    @pytest.mark.asyncio
    async def test_ascii_filename_passthrough(self) -> None:
        storage = _make_storage()
        storage._client.head_object.return_value = {"Metadata": {"filename": "report.csv"}}  # noqa: SLF001
        meta = await storage.head_object("key1")
        assert meta["filename"] == "report.csv"

    @pytest.mark.asyncio
    async def test_no_filename_in_metadata(self) -> None:
        storage = _make_storage()
        storage._client.head_object.return_value = {"Metadata": {}}  # noqa: SLF001
        meta = await storage.head_object("key1")
        assert "filename" not in meta
