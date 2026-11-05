from client_portal import is_client_upload_path, public_client_messages


def test_client_upload_is_scoped_to_owner_and_sign_request():
    path = "dns-energy/uploads/owner-1/sign/sign-1/file.pdf"
    assert is_client_upload_path(path, "dns-energy", "owner-1", "sign-1")
    assert not is_client_upload_path(path, "dns-energy", "owner-1", "sign-2")
    assert not is_client_upload_path(path, "dns-energy", "owner-2", "sign-1")
    assert not is_client_upload_path("dns-energy/uploads/owner-1/sign/sign-1/../secret.pdf", "dns-energy", "owner-1", "sign-1")


def test_client_upload_accepts_legacy_files_only_for_the_same_sign_request():
    path = "dns-energy/uploads/owner-1/client-messages/sign-1/file.pdf"
    assert is_client_upload_path(path, "dns-energy", "owner-1", "sign-1")
    assert not is_client_upload_path(path, "dns-energy", "owner-1", "sign-2")
    assert not is_client_upload_path(path, "dns-energy", "owner-2", "sign-1")


def test_public_message_view_hides_storage_paths_and_internal_messages():
    messages = [
        {"id": "m1", "sender": "team", "audience": "client", "text": "Bună", "created_at": "now",
         "attachments": [{"storage_path": "dns-energy/private-key", "original_filename": "doc.pdf",
                          "content_type": "application/pdf", "size": 42}]},
        {"id": "m2", "sender": "team", "audience": "internal", "text": "Intern"},
    ]

    public = public_client_messages(messages)

    assert len(public) == 1
    assert public[0]["attachments"] == [{"original_filename": "doc.pdf", "content_type": "application/pdf", "size": 42}]
    assert "storage_path" not in public[0]["attachments"][0]
