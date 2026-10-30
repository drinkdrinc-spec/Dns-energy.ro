from object_storage import CloudflareR2Storage


class FakeBody:
    def read(self):
        return b"pdf-data"

    def close(self):
        pass


class FakeS3Client:
    def __init__(self):
        self.put_args = None

    def put_object(self, **kwargs):
        self.put_args = kwargs

    def get_object(self, **kwargs):
        return {"Body": FakeBody(), "ContentType": "application/pdf"}


def test_r2_put_and_get_preserve_object_key():
    storage = CloudflareR2Storage(
        account_id="account",
        access_key_id="access",
        secret_access_key="secret",
        bucket_name="dns-energy-files",
    )
    fake = FakeS3Client()
    storage.client = fake

    result = storage.put_object("d-energy/uploads/user/a.pdf", b"pdf-data", "application/pdf")
    data, content_type = storage.get_object("d-energy/uploads/user/a.pdf")

    assert result == {"path": "d-energy/uploads/user/a.pdf", "size": 8}
    assert fake.put_args["Bucket"] == "dns-energy-files"
    assert fake.put_args["Key"] == "d-energy/uploads/user/a.pdf"
    assert data == b"pdf-data"
    assert content_type == "application/pdf"
