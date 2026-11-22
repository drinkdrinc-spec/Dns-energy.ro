"""Shared access rule for accounts allowed into the private DNS Energy app."""


def private_mode_account_allowed(user: dict, admin_email: str | None) -> bool:
    """Allow the configured administrator and installer/partner accounts.

    Account activation is checked separately so callers can return the specific
    pending/suspended message instead of masking it as a private-mode denial.
    """
    configured_admin = str(admin_email or "").strip().lower()
    account_email = str((user or {}).get("email") or "").strip().lower()
    is_admin = bool(configured_admin) and account_email == configured_admin and user.get("role") == "admin"
    is_partner = (user or {}).get("account_type") in ("installer", "partner")
    return bool(is_admin or is_partner)
