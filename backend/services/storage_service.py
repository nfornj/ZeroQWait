from __future__ import annotations

import logging
from functools import lru_cache
from urllib.parse import quote, urlparse

import boto3
from botocore.client import Config

from shared.secrets import getenv, load_infisical_secrets

load_infisical_secrets()

logger = logging.getLogger(__name__)


def _required_secret(name: str) -> str:
    value = getenv(name, "")
    if not value:
        raise RuntimeError(f"{name} is required for Backblaze B2 storage")
    return value


def _object_key(filename: str) -> str:
    key = filename.strip().replace("\\", "/").lstrip("/")
    if not key or key.endswith("/"):
        raise ValueError("filename must resolve to a non-empty object key")
    return key


def _public_url(endpoint: str, bucket_name: str, key: str) -> str:
    parsed = urlparse(endpoint)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError("B2_ENDPOINT must include scheme and host, for example https://s3.us-east-005.backblazeb2.com")
    encoded_key = quote(key, safe="/")
    return f"{parsed.scheme}://{bucket_name}.{parsed.netloc}/{encoded_key}"


@lru_cache(maxsize=1)
def _client():
    endpoint = _required_secret("B2_ENDPOINT").rstrip("/")
    key_id = _required_secret("B2_KEY_ID")
    app_key = _required_secret("B2_APP_KEY")

    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=key_id,
        aws_secret_access_key=app_key,
        config=Config(signature_version="s3v4", s3={"addressing_style": "virtual"}),
    )


def upload_file(buffer: bytes, filename: str, mime_type: str) -> str:
    key = _object_key(filename)
    endpoint = _required_secret("B2_ENDPOINT").rstrip("/")
    bucket_name = _required_secret("B2_BUCKET_NAME")

    _client().put_object(
        Bucket=bucket_name,
        Key=key,
        Body=buffer,
        ContentType=mime_type,
    )
    return _public_url(endpoint, bucket_name, key)


def delete_file(filename: str) -> None:
    key = _object_key(filename)
    bucket_name = _required_secret("B2_BUCKET_NAME")
    _client().delete_object(Bucket=bucket_name, Key=key)


def get_signed_url(filename: str, expires_in_seconds: int) -> str:
    key = _object_key(filename)
    bucket_name = _required_secret("B2_BUCKET_NAME")
    if expires_in_seconds <= 0:
        raise ValueError("expires_in_seconds must be greater than 0")

    return _client().generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket_name, "Key": key},
        ExpiresIn=expires_in_seconds,
    )


uploadFile = upload_file
deleteFile = delete_file
getSignedUrl = get_signed_url