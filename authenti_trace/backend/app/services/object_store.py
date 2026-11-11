"""Where uploaded media lives between the API and the analysis worker.

LocalStore (default): the key is the file's absolute path; nothing is copied.
S3Store: for an API and workers on different machines. Set OBJECT_STORE=s3 plus S3_BUCKET
(optional S3_PREFIX, S3_ENDPOINT_URL, standard AWS credentials). Configure retention as a bucket
lifecycle rule; purge_expired_media() only cleans the local disk.
"""
import os
import tempfile
from pathlib import Path
from typing import Protocol


class ObjectStore(Protocol):
    remote: bool

    def put(self, local_path: str) -> str: ...
    def fetch(self, key: str) -> str: ...
    def exists(self, key: str) -> bool: ...
    def delete(self, key: str) -> None: ...


class LocalStore:
    remote = False

    def put(self, local_path: str) -> str:
        return local_path

    def fetch(self, key: str) -> str:
        return key

    def exists(self, key: str) -> bool:
        return os.path.exists(key)

    def delete(self, key: str) -> None:
        Path(key).unlink(missing_ok=True)


class S3Store:
    remote = True

    def __init__(self, bucket: str, prefix: str = "", endpoint_url: str | None = None, cache_dir: str | None = None):
        import boto3  # imported here so local installs do not need boto3

        self.bucket = bucket
        self.prefix = prefix.strip("/")
        self.client = boto3.client("s3", endpoint_url=endpoint_url)
        self.cache_dir = cache_dir or os.path.join(tempfile.gettempdir(), "authentitrace-cache")
        os.makedirs(self.cache_dir, exist_ok=True)

    def _key(self, name: str) -> str:
        return f"{self.prefix}/{name}" if self.prefix else name

    def put(self, local_path: str) -> str:
        key = self._key(os.path.basename(local_path))
        self.client.upload_file(local_path, self.bucket, key)
        return key

    def fetch(self, key: str) -> str:
        """Download to a local cache file (signals need a real path) and return it."""
        local = os.path.join(self.cache_dir, os.path.basename(key))
        self.client.download_file(self.bucket, key, local)
        return local

    def exists(self, key: str) -> bool:
        from botocore.exceptions import ClientError

        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
            return True
        except ClientError:
            return False

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=key)


def get_store() -> ObjectStore:
    if os.getenv("OBJECT_STORE", "local").lower() == "s3":
        bucket = os.environ["S3_BUCKET"]  # fail loudly when misconfigured
        return S3Store(bucket, os.getenv("S3_PREFIX", ""), os.getenv("S3_ENDPOINT_URL") or None)
    return LocalStore()


store: ObjectStore = get_store()
