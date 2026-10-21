"""Private, in-memory CSV uploads to Amazon S3."""

import os
from io import BytesIO
from pathlib import Path
from typing import BinaryIO, Literal
from uuid import uuid4

import boto3
from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError, PartialCredentialsError
from dotenv import load_dotenv

DOTENV_PATH = Path(__file__).resolve().parent / ".env"


class CloudStorageConfigurationError(ValueError):
    """Raised when required S3 configuration or credentials are unavailable."""


class CloudStorageUploadError(RuntimeError):
    """Raised when S3 rejects or cannot complete an upload."""


def _create_s3_client():
    """Create an S3 client using environment credentials locally or an IAM role in AWS."""
    load_dotenv(dotenv_path=DOTENV_PATH, override=False)

    region = os.getenv("AWS_REGION", "").strip()
    bucket = os.getenv("AWS_S3_BUCKET", "").strip()
    if not region or not bucket:
        missing = [name for name, value in (("AWS_REGION", region), ("AWS_S3_BUCKET", bucket)) if not value]
        raise CloudStorageConfigurationError(
            "Missing required AWS environment variables: " + ", ".join(missing) + "."
        )

    access_key = os.getenv("AWS_ACCESS_KEY_ID", "").strip()
    secret_key = os.getenv("AWS_SECRET_ACCESS_KEY", "").strip()
    if bool(access_key) != bool(secret_key):
        raise CloudStorageConfigurationError(
            "Set both AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY, or neither when using an IAM role."
        )

    try:
        if access_key and secret_key:
            client = boto3.client(
                "s3", region_name=region,
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
            )
        else:
            # Uses the standard AWS credential chain, including an attached IAM role.
            client = boto3.client("s3", region_name=region)
    except (NoCredentialsError, PartialCredentialsError) as error:
        raise CloudStorageConfigurationError(
            "AWS credentials are unavailable. Configure local credentials or attach an IAM role."
        ) from error
    return client, bucket


def upload_to_s3(
    file: BinaryIO | bytes | bytearray,
    *,
    asset_category: Literal["source", "report"],
) -> dict[str, str]:
    """Upload an in-memory CSV to a private S3 bucket and return safe object metadata.

    The object key is unique per upload. No public ACL is set; bucket public access
    should remain blocked. The function returns no public URL or credential data.
    """
    if not isinstance(file, (bytes, bytearray)) and not callable(getattr(file, "read", None)):
        raise TypeError("file must be bytes or a readable in-memory file object.")
    if asset_category not in {"source", "report"}:
        raise ValueError("asset_category must be 'source' or 'report'.")

    client, bucket = _create_s3_client()
    object_key = f"student-performance-analytics/{asset_category}/{asset_category}_{uuid4().hex}.csv"
    body = BytesIO(bytes(file)) if isinstance(file, (bytes, bytearray)) else file

    try:
        client.upload_fileobj(
            body,
            bucket,
            object_key,
            ExtraArgs={
                "ContentType": "text/csv; charset=utf-8",
                "ServerSideEncryption": "AES256",
            },
        )
    except (ClientError, BotoCoreError, NoCredentialsError, PartialCredentialsError) as error:
        # Keep details in server logs only; never return AWS response details to users.
        raise CloudStorageUploadError(
            "Amazon S3 could not store the file. Check IAM permissions and server configuration."
        ) from error

    return {"bucket": bucket, "key": object_key, "content_type": "text/csv; charset=utf-8"}
