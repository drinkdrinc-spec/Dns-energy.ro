"""Small, dependency-free helpers for the public client signing portal."""


def client_upload_prefix(app_name: str, owner: str, sign_request_id: str) -> str:
    app = str(app_name or "dns-energy").strip("/") or "dns-energy"
    return f"{app}/uploads/{owner}/sign/{sign_request_id}/"


def is_client_upload_path(path: str, app_name: str, owner: str, sign_request_id: str) -> bool:
    key = str(path or "").lstrip("/")
    app = str(app_name or "dns-energy").strip("/") or "dns-energy"
    legacy_prefix = f"{app}/uploads/{owner}/client-messages/{sign_request_id}/"
    return bool(key) and ".." not in key.split("/") and key.startswith((
        client_upload_prefix(app, owner, sign_request_id), legacy_prefix
    ))


def public_client_messages(messages) -> list[dict]:
    """Expose conversation metadata without leaking private object-storage keys."""
    public = []
    for item in messages or []:
        if not isinstance(item, dict) or item.get("audience") != "client":
            continue
        message = {key: item.get(key) for key in ("id", "sender", "sender_name", "text", "created_at")}
        message["attachments"] = [
            {key: attachment.get(key) for key in ("original_filename", "content_type", "size")}
            for attachment in (item.get("attachments") or [])
            if isinstance(attachment, dict)
        ]
        public.append(message)
    return public
