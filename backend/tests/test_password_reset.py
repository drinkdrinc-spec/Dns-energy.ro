from password_reset import admin_reset_nonce_hash, reset_lookup_hash, reset_rate_key, reset_token_hash, trusted_reset_origin


def test_admin_recovery_nonce_is_stored_as_a_one_time_digest():
    nonce = "fresh-one-time-recovery-nonce"
    digest = admin_reset_nonce_hash(nonce)
    assert digest != nonce
    assert digest == admin_reset_nonce_hash(nonce)
    assert digest != admin_reset_nonce_hash("another-recovery-nonce")


def test_reset_token_digests_are_account_scoped_and_never_the_token():
    token = "secret-reset-token"
    assert reset_token_hash("user-a", token) != token
    assert reset_token_hash("user-a", token) != reset_token_hash("user-b", token)
    assert reset_lookup_hash(token) != token


def test_reset_rate_key_is_stable_case_insensitive_and_not_plain_email():
    email = "Client@Example.com"
    assert reset_rate_key("email", email) == reset_rate_key("email", email.lower())
    assert email.casefold() not in reset_rate_key("email", email)


def test_reset_origin_accepts_only_configured_https_origin():
    allowed = "https://dns-energy-web.onrender.com,https://dns-energy.ro"
    assert trusted_reset_origin("https://dns-energy.ro", allowed, None) == "https://dns-energy.ro"
    assert trusted_reset_origin("https://attacker.example", allowed, "https://dns-energy-web.onrender.com") == "https://dns-energy-web.onrender.com"


def test_reset_origin_rejects_unsafe_fallback():
    assert trusted_reset_origin(None, "https://dns-energy.ro", "http://attacker.example") == "https://dns-energy.ro"
