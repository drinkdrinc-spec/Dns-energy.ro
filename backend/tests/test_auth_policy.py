from auth_policy import private_mode_account_allowed


def test_private_mode_allows_configured_admin_only_with_admin_role():
    assert private_mode_account_allowed(
        {"email": "ADMIN@DNS-ENERGY.RO", "role": "admin"}, "admin@dns-energy.ro"
    )
    assert not private_mode_account_allowed(
        {"email": "admin@dns-energy.ro", "role": "instalator", "account_type": "team"},
        "admin@dns-energy.ro",
    )


def test_private_mode_allows_installer_and_partner_accounts():
    assert private_mode_account_allowed({"account_type": "installer"}, "admin@dns-energy.ro")
    assert private_mode_account_allowed({"account_type": "partner"}, "admin@dns-energy.ro")


def test_private_mode_rejects_unrelated_accounts():
    assert not private_mode_account_allowed({"role": "admin", "email": "other@example.com"}, "admin@dns-energy.ro")
    assert not private_mode_account_allowed({"account_type": "team"}, "admin@dns-energy.ro")
