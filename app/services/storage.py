"""
Storage backend abstraction: local filesystem (dev) and S3-compatible (production).
"""
from __future__ import annotations

import os
import shutil
import uuid
from abc import ABC, abstractmethod
from pathlib import Path

from app.core.config import settings


class StorageError(Exception):
    pass


class StorageBackend(ABC):
    @abstractmethod
    def save(self, data: bytes, filename: str, content_type: str = "application/octet-stream") -> str:
        """Save bytes and return storage_key."""
        ...

    @abstractmethod
    def delete(self, storage_key: str) -> None:
        ...

    @abstractmethod
    def get_local_path(self, storage_key: str) -> str | None:
        """Return local filesystem path if available (for local backend)."""
        ...


class LocalStorage(StorageBackend):
    def __init__(self, base_path: str):
        self.base = Path(base_path)
        self.base.mkdir(parents=True, exist_ok=True)

    def save(self, data: bytes, filename: str, content_type: str = "application/octet-stream") -> str:
        ext = Path(filename).suffix or ".bin"
        key = f"{uuid.uuid4().hex}{ext}"
        path = self.base / key
        path.write_bytes(data)
        return key

    def delete(self, storage_key: str) -> None:
        path = self.base / storage_key
        if path.exists():
            path.unlink()

    def get_local_path(self, storage_key: str) -> str | None:
        path = self.base / storage_key
        return str(path) if path.exists() else None


class S3Storage(StorageBackend):
    def __init__(self):
        try:
            import boto3
        except ImportError as exc:
            raise StorageError("boto3 is required for S3 storage") from exc

        self.client = boto3.client(
            "s3",
            endpoint_url=settings.storage_endpoint or None,
            aws_access_key_id=settings.storage_access_key,
            aws_secret_access_key=settings.storage_secret_key,
        )
        self.bucket = settings.storage_bucket

    def save(self, data: bytes, filename: str, content_type: str = "application/octet-stream") -> str:
        ext = Path(filename).suffix or ".bin"
        key = f"audio/{uuid.uuid4().hex}{ext}"
        try:
            self.client.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=data,
                ContentType=content_type,
            )
        except Exception as exc:
            raise StorageError(f"Failed to upload to S3: {exc}") from exc
        return key

    def delete(self, storage_key: str) -> None:
        try:
            self.client.delete_object(Bucket=self.bucket, Key=storage_key)
        except Exception as exc:
            raise StorageError(f"Failed to delete from S3: {exc}") from exc

    def get_local_path(self, storage_key: str) -> str | None:
        return None  # S3 objects are not local


def get_storage_backend() -> StorageBackend:
    if settings.storage_backend == "s3":
        return S3Storage()
    return LocalStorage(settings.storage_local_path)
