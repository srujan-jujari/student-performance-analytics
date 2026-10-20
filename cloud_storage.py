"""Authenticated in-memory uploads to Cloudinary."""

import os
from pathlib import Path
from typing import BinaryIO, Literal
from uuid import uuid4

import cloudinary
from cloudinary import uploader
from cloudinary.exceptions import Error as CloudinaryError
from dotenv import load_dotenv

DOTENV_PATH = Path(__file__).resolve().parent / ".env"
REQUIRED_CREDENTIALS = (
    "CLOUDINARY_CLOUD_NAME",
    "CLOUDINARY_API_KEY",
    "CLOUDINARY_API_SECRET",
)


class CloudStorageConfigurationError(ValueError):
    """Raised when required Cloudinary environment settings are unavailable."""


class CloudStorageUploadError(RuntimeError):
    """Raised when Cloudinary rejects or cannot complete an upload."""


def _configure_cloudinary() -> None:
    """Load local environment settings and configure the Cloudinary SDK."""
    load_dotenv(dotenv_path=DOTENV_PATH, override=False)

    credentials = {
        name: os.getenv(name, "").strip()
        for name in REQUIRED_CREDENTIALS
    }
    missing_credentials = [
        name for name, value in credentials.items() if not value
    ]
    if missing_credentials:
        names = ", ".join(missing_credentials)
        raise CloudStorageConfigurationError(
            f"Missing required Cloudinary environment variables: {names}."
        )

    cloudinary.config(
        cloud_name=credentials["CLOUDINARY_CLOUD_NAME"],
        api_key=credentials["CLOUDINARY_API_KEY"],
        api_secret=credentials["CLOUDINARY_API_SECRET"],
        secure=True,
    )


def upload_to_cloudinary(
    file: BinaryIO | bytes | bytearray,
    *,
    asset_category: Literal["source", "report"],
) -> dict[str, str | None]:
    """Upload an in-memory CSV or report as an authenticated raw Cloudinary asset.

    Each upload receives a unique, category-specific public ID. Overwriting is
    disabled so repeated uploads do not replace an earlier asset.
    The returned mapping contains only the public ID, resource type, and format.
    It deliberately excludes delivery URLs and credential data. Authenticated
    Cloudinary assets require signed delivery for access.

    Args:
        file: Bytes or a binary file-like stream. Local file paths are not accepted.
        asset_category: Whether this is an original source CSV or generated report.

    Raises:
        TypeError: If ``file`` is not bytes or a readable file-like object.
        ValueError: If ``asset_category`` is not ``"source"`` or ``"report"``.
        CloudStorageConfigurationError: If Cloudinary credentials are missing.
        CloudStorageUploadError: If upload fails or Cloudinary returns incomplete
            or unexpected metadata.
    """
    if not isinstance(file, (bytes, bytearray)) and not callable(
        getattr(file, "read", None)
    ):
        raise TypeError("file must be bytes or a readable in-memory file object.")
    if asset_category not in {"source", "report"}:
        raise ValueError("asset_category must be 'source' or 'report'.")

    _configure_cloudinary()
    public_id = (
        "student-performance-analytics/"
        f"student_performance_{asset_category}_{uuid4().hex}.csv"
    )

    try:
        result = uploader.upload(
            bytes(file) if isinstance(file, bytearray) else file,
            public_id=public_id,
            resource_type="raw",
            type="authenticated",
            overwrite=False,
        )
    except CloudinaryError as error:
        raise CloudStorageUploadError(
            "Cloudinary upload failed. Check the server configuration and retry."
        ) from error

    if (
        not isinstance(result, dict)
        or not isinstance(result.get("public_id"), str)
        or result.get("resource_type") != "raw"
    ):
        raise CloudStorageUploadError(
            "Cloudinary returned incomplete or unexpected upload metadata."
        )

    asset_format = result.get("format")
    if asset_format is not None and not isinstance(asset_format, str):
        raise CloudStorageUploadError(
            "Cloudinary returned incomplete or unexpected upload metadata."
        )

    return {
        "public_id": result["public_id"],
        "resource_type": "raw",
        "format": asset_format,
    }
