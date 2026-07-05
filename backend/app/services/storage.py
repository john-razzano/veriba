import json
from dataclasses import dataclass

from minio import Minio
from minio.error import S3Error

from app.core.config import get_settings


@dataclass
class PresignedUpload:
    upload_url: str
    expires_in: int
    fields: dict


class MinioStorageService:
    def __init__(self):
        settings = get_settings()
        self.bucket = settings.minio_bucket
        self.public_base_url = settings.public_storage_base_url.rstrip("/")
        self.client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )
        if not self.client.bucket_exists(self.bucket):
            self.client.make_bucket(self.bucket)
        self._ensure_public_read_policy()

    def _ensure_public_read_policy(self) -> None:
        policy = json.dumps(
            {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": {"AWS": ["*"]},
                        "Action": ["s3:GetObject"],
                        "Resource": [f"arn:aws:s3:::{self.bucket}/*"],
                    }
                ],
            }
        )
        self.client.set_bucket_policy(self.bucket, policy)

    def save_bytes(self, key: str, data: bytes, content_type: str | None = None) -> str:
        from io import BytesIO

        if content_type is None:
            ext = key.rsplit(".", 1)[-1].lower() if "." in key else ""
            content_type = {
                "jpg": "image/jpeg",
                "jpeg": "image/jpeg",
                "png": "image/png",
                "webp": "image/webp",
                "gif": "image/gif",
                "svg": "image/svg+xml",
            }.get(ext, "application/octet-stream")

        self.client.put_object(
            self.bucket,
            key,
            data=BytesIO(data),
            length=len(data),
            content_type=content_type,
        )
        return self.public_url(key)

    def public_url(self, key: str) -> str:
        return f"{self.public_base_url}/{key}"

    def presign_upload(self, key: str, expires_in: int) -> PresignedUpload:
        url = self.client.presigned_put_object(self.bucket, key, expires=expires_in)
        return PresignedUpload(upload_url=url, expires_in=expires_in, fields={})

    def delete_prefix(self, prefix: str) -> int:
        keys = [item.object_name for item in self.client.list_objects(self.bucket, prefix=prefix, recursive=True)]
        for key in keys:
            self.client.remove_object(self.bucket, key)
        return len(keys)

    def get_bytes(self, key: str) -> bytes:
        response = self.client.get_object(self.bucket, key)
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()

    def healthcheck(self) -> str:
        try:
            self.client.bucket_exists(self.bucket)
            return "connected"
        except S3Error:
            return "disconnected"


_storage_instance = None


def get_storage() -> MinioStorageService:
    global _storage_instance
    if _storage_instance is None:
        _storage_instance = MinioStorageService()
    return _storage_instance
