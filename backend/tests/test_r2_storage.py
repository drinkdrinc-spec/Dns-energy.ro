import pytest

import r2_storage


class FakeS3:
    def __init__(self):
        self.objects = {}
        self.head_calls = []

    def put_object(self, **kwargs):
        self.objects[(kwargs["Bucket"], kwargs["Key"])] = (
            kwargs["Body"], kwargs["ContentType"]
        )
        return {"ETag": '"test-etag"'}

    def get_object(self, **kwargs):
        body, content_type = self.objects[(kwargs["Bucket"], kwargs["Key"])]
        class Body:
            def read(self):
                return body
        return {"Body": Body(), "ContentType": content_type}

    def head_bucket(self, **kwargs):
        self.head_calls.append(kwargs["Bucket"])


def test_r2_put_and_get_round_trip(monkeypatch):
    fake = FakeS3()
    monkeypatch.setattr(r2_storage, "_client", lambda: fake)
    monkeypatch.setenv("R2_BUCKET_NAME", "dns-energy-files")

    result = r2_storage.put_object("clients/example.pdf", b"pdf-bytes", "application/pdf")
    content, mime = r2_storage.get_object("clients/example.pdf")

    assert result["etag"] == "test-etag"
    assert content == b"pdf-bytes"
    assert mime == "application/pdf"


def test_r2_rejects_path_traversal(monkeypatch):
    fake = FakeS3()
    monkeypatch.setattr(r2_storage, "_client", lambda: fake)
    monkeypatch.setenv("R2_BUCKET_NAME", "dns-energy-files")

    with pytest.raises(ValueError):
        r2_storage.put_object("../secrets.txt", b"x", "text/plain")


def test_r2_requires_bucket_name(monkeypatch):
    monkeypatch.delenv("R2_BUCKET_NAME", raising=False)
    with pytest.raises(RuntimeError, match="R2_BUCKET_NAME"):
        r2_storage._bucket()
