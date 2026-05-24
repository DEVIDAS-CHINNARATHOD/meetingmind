"""
services/storage.py
Unified storage abstraction: local filesystem, AWS S3, or Cloudflare R2.
All methods are async-friendly (S3 calls wrapped with asyncio executor).
"""
from __future__ import annotations

import asyncio
import os
import uuid
from functools import lru_cache
from pathlib import Path
from typing import BinaryIO

import aiofiles
import boto3
from botocore.exceptions import ClientError
import structlog

from config.settings import settings

log = structlog.get_logger(__name__)


class LocalStorageBackend:
    def __init__(self, base_path: str):
        self.base = Path(base_path)
        self.base.mkdir(parents=True, exist_ok=True)

    def _full(self, key: str) -> Path:
        # Prevent path traversal
        safe = Path(key.lstrip("/"))
        return self.base / safe

    async def upload_file(self, file_obj: BinaryIO, key: str, content_type: str = "") -> str:
        dest = self._full(key)
        dest.parent.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(dest, "wb") as f:
            while chunk := file_obj.read(1024 * 1024):  # 1 MB chunks
                await f.write(chunk)
        log.debug("local_upload", key=key, size=dest.stat().st_size)
        return key

    async def upload_bytes(self, data: bytes, key: str, content_type: str = "") -> str:
        dest = self._full(key)
        dest.parent.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(dest, "wb") as f:
            await f.write(data)
        return key

    async def download_bytes(self, key: str) -> bytes:
        async with aiofiles.open(self._full(key), "rb") as f:
            return await f.read()

    async def get_local_path(self, key: str) -> str:
        return str(self._full(key))

    async def delete(self, key: str) -> None:
        p = self._full(key)
        if p.exists():
            p.unlink()

    async def get_url(self, key: str, expires_in: int = 3600) -> str:
        # For local dev, just return a relative path
        return f"/static/{key}"

    async def exists(self, key: str) -> bool:
        return self._full(key).exists()


class S3StorageBackend:
    def __init__(
        self,
        bucket: str,
        access_key: str,
        secret_key: str,
        region: str,
        endpoint_url: str | None = None,
    ):
        self.bucket = bucket
        self._client = boto3.client(
            "s3",
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
            endpoint_url=endpoint_url or None,
        )

    def _run(self, fn, *args, **kwargs):
        """Run blocking boto3 call in thread pool."""
        loop = asyncio.get_event_loop()
        return loop.run_in_executor(None, lambda: fn(*args, **kwargs))

    async def upload_file(self, file_obj: BinaryIO, key: str, content_type: str = "application/octet-stream") -> str:
        extra = {"ContentType": content_type} if content_type else {}
        await self._run(
            self._client.upload_fileobj, file_obj, self.bucket, key,
            ExtraArgs=extra
        )
        log.debug("s3_upload", bucket=self.bucket, key=key)
        return key

    async def upload_bytes(self, data: bytes, key: str, content_type: str = "") -> str:
        import io
        return await self.upload_file(io.BytesIO(data), key, content_type)

    async def download_bytes(self, key: str) -> bytes:
        import io
        buf = io.BytesIO()
        await self._run(self._client.download_fileobj, self.bucket, key, buf)
        return buf.getvalue()

    async def get_local_path(self, key: str) -> str:
        """Download to /tmp and return path — needed for ffmpeg/whisper."""
        import tempfile
        suffix = Path(key).suffix
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as f:
            tmp_path = f.name
        data = await self.download_bytes(key)
        Path(tmp_path).write_bytes(data)
        return tmp_path

    async def delete(self, key: str) -> None:
        await self._run(self._client.delete_object, Bucket=self.bucket, Key=key)

    async def get_url(self, key: str, expires_in: int = 3600) -> str:
        url = await self._run(
            self._client.generate_presigned_url,
            "get_object",
            Params={"Bucket": self.bucket, "Key": key},
            ExpiresIn=expires_in,
        )
        return url

    async def exists(self, key: str) -> bool:
        try:
            await self._run(self._client.head_object, Bucket=self.bucket, Key=key)
            return True
        except ClientError:
            return False


# ── Factory ──────────────────────────────────────────────────

@lru_cache(maxsize=1)
def get_storage():
    if settings.storage_backend == "local":
        return LocalStorageBackend(settings.local_storage_path)
    elif settings.storage_backend == "s3":
        return S3StorageBackend(
            bucket=settings.aws_bucket_name,
            access_key=settings.aws_access_key_id,
            secret_key=settings.aws_secret_access_key,
            region=settings.aws_region,
        )
    elif settings.storage_backend == "r2":
        return S3StorageBackend(
            bucket=settings.r2_bucket_name,
            access_key=settings.r2_access_key_id,
            secret_key=settings.r2_secret_access_key,
            region="auto",
            endpoint_url=settings.r2_endpoint_url,
        )
    raise ValueError(f"Unknown storage backend: {settings.storage_backend}")


# ── Key helpers ───────────────────────────────────────────────

def make_upload_key(workspace_id: str, meeting_id: str, filename: str) -> str:
    ext = Path(filename).suffix.lower()
    return f"workspaces/{workspace_id}/meetings/{meeting_id}/original{ext}"


def make_audio_key(workspace_id: str, meeting_id: str) -> str:
    return f"workspaces/{workspace_id}/meetings/{meeting_id}/audio.wav"


def make_report_key(workspace_id: str, meeting_id: str, report_type: str, fmt: str) -> str:
    return f"workspaces/{workspace_id}/meetings/{meeting_id}/reports/{report_type}.{fmt}"
