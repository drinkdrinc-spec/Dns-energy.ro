"""S3-compatible object storage adapter for Cloudflare R2.

The application stores object keys in MongoDB. Keep those keys unchanged when
switching providers so existing document references remain valid after a
separately verified data migration.
"""
from __future__ import annotations

import os
from typing import Optional

import boto3
from botocore.config import Config


class R2ConfigurationError(RuntimeError):
    """Raised when R2 is selected but required credentials are missing."""


class CloudflareR2Storage:
    def __init__(
        self,
        *,
        account_id: str,
        access_key_id: str,
        secret_access_key: str,
        bucket_name: str,
        endpoint_url: Optional[str] = None,
        region_name: str = "auto",
    ) -> None:
        missing = [
            name
            for name, value in (
                ("R2_ACCOUNT_ID", account_id),
                ("R2_ACCESS_KEY_ID", access_key_id),
                ("R2_SECRET_ACCESS_KEY", secret_access_key),
                ("R2_BUCKET_NAME", bucket_name),
            )
            if not value
        ]
        if missing:
            raise R2ConfigurationError(
                "Missing Cloudflare R2 settings: " + ", ".join(missing)
            )

        self.bucket_name = bucket_name
        self.endpoint_url = (
            endpoint_url or f"https://{account_id}.r2.cloudflarestorage.com"
        )
        self.client = boto3.client(
            "s3",
            endpoint_url=self.endpoint_url,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            region_name=region_name or "auto",
            config=Config(signature_version="s3v4"),
        )

    @classmethod
    def from_environment(cls) -> "CloudflareR2Storage":
        return cls(
            account_id=os.environ.get("R2_ACCOUNT_ID", "").strip(),
            access_key_id=os.environ.get("R2_ACCESS_KEY_ID", "").strip(),
            secret_access_key=os.environ.get("R2_SECRET_ACCESS_KEY", "").strip(),
            bucket_name=os.environ.get("R2_BUCKET_NAME", "").strip(),
            endpoint_url=os.environ.get("R2_ENDPOINT_URL", "").strip() or None,
            region_name=os.environ.get("R2_REGION", "auto").strip() or "auto",
        )

    def put_object(self, path: str, data: bytes, content_type: str) -> dict:
        self.client.put_object(
            Bucket=self.bucket_name,
            Key=path,
            Body=data,
            ContentType=content_type or "application/octet-stream",
        )
        return {"path": path, "size": len(data)}

    def get_object(self, path: str) -> tuple[bytes, str]:
        response = self.client.get_object(Bucket=self.bucket_name, Key=path)
        body = response["Body"]
        try:
            data = body.read()
        finally:
            body.close()
        return data, response.get("ContentType", "application/octet-stream")
