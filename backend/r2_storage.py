"""Cloudflare R2 adapter using the S3-compatible API."""
import os
from functools import lru_cache
import boto3
from botocore.config import Config


def _required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


@lru_cache(maxsize=1)
def _client():
    account_id = _required("R2_ACCOUNT_ID")
    return boto3.client(
        "s3",
        endpoint_url=os.environ.get("R2_ENDPOINT_URL", f"https://{account_id}.r2.cloudflarestorage.com"),
        aws_access_key_id=_required("R2_ACCESS_KEY_ID"),
        aws_secret_access_key=_required("R2_SECRET_ACCESS_KEY"),
        region_name="auto",
        config=Config(signature_version="s3v4", retries={"max_attempts": 3}),
    )


def _bucket() -> str:
    return _required("R2_BUCKET_NAME")


def put_object(path: str, data: bytes, content_type: str) -> dict:
    key = str(path).lstrip("/")
    if not key or ".." in key.split("/"):
        raise ValueError("Invalid object key")
    response = _client().put_object(Bucket=_bucket(), Key=key, Body=data, ContentType=content_type)
    return {"key": key, "etag": response.get("ETag", "").strip('"'), "bucket": _bucket()}


def get_object(path: str):
    key = str(path).lstrip("/")
    if not key or ".." in key.split("/"):
        raise ValueError("Invalid object key")
    response = _client().get_object(Bucket=_bucket(), Key=key)
    return response["Body"].read(), response.get("ContentType", "application/octet-stream")


def healthcheck() -> bool:
    _client().head_bucket(Bucket=_bucket())
    return True
