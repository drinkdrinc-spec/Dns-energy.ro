"""Helpers for one-time account recovery links."""

import hashlib
from urllib.parse import urlparse


def reset_token_hash(user_id: str, token: str) -> str:
    """Bind the stored digest to the account so a token cannot be moved between users."""
    return hashlib.sha256(f"{user_id}:{token}".encode("utf-8")).hexdigest()


def reset_lookup_hash(token: str) -> str:
    """Indexable digest used to locate the account-bound digest without storing the token."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def reset_rate_key(kind: str, value: str) -> str:
    """Return a non-reversible database key for a reset rate-limit bucket."""
    return hashlib.sha256(f"{kind}:{value.strip().casefold()}".encode("utf-8")).hexdigest()


def admin_reset_nonce_hash(nonce: str) -> str:
    """Hash the one-time Render-controlled primary-admin recovery nonce."""
    return hashlib.sha256(f"dns-energy-admin-reset:{nonce}".encode("utf-8")).hexdigest()


def _https_origin(value: str | None) -> str | None:
    parsed = urlparse(str(value or "").strip())
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
            or parsed.path not in ("", "/") or parsed.query or parsed.fragment):
        return None
    return f"https://{parsed.netloc}"


def trusted_reset_origin(request_origin: str | None, configured_origins: str, fallback: str | None) -> str:
    allowed = {_https_origin(value) for value in str(configured_origins or "").split(",")}
    allowed.discard(None)
    requested = _https_origin(request_origin)
    if requested and requested in allowed:
        return requested
    safe_fallback = _https_origin(fallback)
    if safe_fallback and (not allowed or safe_fallback in allowed):
        return safe_fallback
    if allowed:
        return sorted(allowed)[0]
    raise ValueError("Nu este configurată o adresă HTTPS de încredere pentru resetarea parolei")
