"""MongoDB GridFS storage with lazy read-through migration for legacy files."""
import os
from functools import lru_cache

import requests
from gridfs import GridFSBucket
from pymongo import MongoClient

LEGACY_STORAGE_URL = "https://integrations.emergentagent.com/objstore/api/v1/storage"
LEGACY_STORAGE_KEY = (os.environ.get("EMERGENT_LLM_KEY") or "").strip()
_client = MongoClient(
    os.environ["MONGO_URL"],
    serverSelectionTimeoutMS=10000,
    connectTimeoutMS=10000,
)
_bucket = GridFSBucket(_client[os.environ.get("DB_NAME", "dns_energy")], bucket_name="dns_energy_files")
_legacy_key = None


def init_storage(force: bool = False):
    """Fail startup if MongoDB is unavailable; legacy storage remains read-only and lazy."""
    _client.admin.command("ping")
    return True


def put_object(path: str, data: bytes, content_type: str) -> dict:
    key = str(path).lstrip("/")
    if not key or ".." in key.split("/"):
        raise ValueError("Invalid object key")
    with _bucket.open_upload_stream(key, metadata={"contentType": content_type}) as stream:
        stream.write(data)
        new_id = stream._id
    for old in _bucket.find({"filename": key}):
        if old["_id"] != new_id:
            _bucket.delete(old["_id"])
    return {"path": key, "size": len(data)}


def _legacy_storage_token(force: bool = False) -> str:
    global _legacy_key
    if not LEGACY_STORAGE_KEY:
        raise FileNotFoundError("Fișierul nu există în MongoDB și stocarea istorică nu este configurată")
    if _legacy_key and not force:
        return _legacy_key
    response = requests.post(
        f"{LEGACY_STORAGE_URL}/init",
        json={"emergent_key": LEGACY_STORAGE_KEY},
        timeout=30,
    )
    response.raise_for_status()
    _legacy_key = response.json()["storage_key"]
    return _legacy_key


def get_object(path: str):
    key = str(path).lstrip("/")
    if not key or ".." in key.split("/"):
        raise ValueError("Invalid object key")
    stored = next(iter(_bucket.find({"filename": key}).sort("uploadDate", -1).limit(1)), None)
    if stored:
        with _bucket.open_download_stream(stored["_id"]) as stream:
            return stream.read(), (stored.get("metadata") or {}).get("contentType", "application/octet-stream")

    token = _legacy_storage_token()
    response = requests.get(f"{LEGACY_STORAGE_URL}/objects/{key}", headers={"X-Storage-Key": token}, timeout=60)
    if response.status_code == 404:
        token = _legacy_storage_token(force=True)
        response = requests.get(f"{LEGACY_STORAGE_URL}/objects/{key}", headers={"X-Storage-Key": token}, timeout=60)
    response.raise_for_status()
    data = response.content
    content_type = response.headers.get("Content-Type", "application/octet-stream")
    try:
        put_object(key, data, content_type)
    except Exception:
        # Keep the original readable even if automatic migration fails.
        pass
    return data, content_type
