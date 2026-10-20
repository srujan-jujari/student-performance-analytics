from io import BytesIO
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from cloudinary.exceptions import Error as CloudinaryError

import cloud_storage


@pytest.fixture
def mock_cloudinary(monkeypatch):
    monkeypatch.setattr(cloud_storage, "load_dotenv", Mock())
    monkeypatch.setenv("CLOUDINARY_CLOUD_NAME", "test-cloud")
    monkeypatch.setenv("CLOUDINARY_API_KEY", "test-api-key")
    monkeypatch.setenv("CLOUDINARY_API_SECRET", "test-api-secret")
    monkeypatch.setattr(
        cloud_storage,
        "uuid4",
        lambda: SimpleNamespace(hex="fixed-unique-id"),
    )

    config = Mock()
    upload = Mock()

    def upload_result(_file, **options):
        return {
            "public_id": options["public_id"],
            "resource_type": "raw",
            "format": "csv",
            "secure_url": "https://example.invalid/should-not-be-returned",
            "api_key": "should-not-be-returned",
        }

    upload.side_effect = upload_result
    monkeypatch.setattr(cloud_storage.cloudinary, "config", config)
    monkeypatch.setattr(cloud_storage.uploader, "upload", upload)
    return config, upload


@pytest.mark.parametrize(
    ("asset_category", "expected_public_id"),
    [
        (
            "source",
            "student-performance-analytics/student_performance_source_fixed-unique-id.csv",
        ),
        (
            "report",
            "student-performance-analytics/student_performance_report_fixed-unique-id.csv",
        ),
    ],
)
def test_uploads_as_named_authenticated_raw_asset(
    mock_cloudinary, asset_category, expected_public_id
):
    config, upload = mock_cloudinary
    csv_stream = BytesIO(b"synthetic,test,data\n")

    metadata = cloud_storage.upload_to_cloudinary(
        csv_stream,
        asset_category=asset_category,
    )

    cloud_storage.load_dotenv.assert_called_once_with(
        dotenv_path=cloud_storage.DOTENV_PATH,
        override=False,
    )
    config.assert_called_once_with(
        cloud_name="test-cloud",
        api_key="test-api-key",
        api_secret="test-api-secret",
        secure=True,
    )
    upload.assert_called_once_with(
        csv_stream,
        public_id=expected_public_id,
        resource_type="raw",
        type="authenticated",
        overwrite=False,
    )
    assert metadata == {
        "public_id": expected_public_id,
        "resource_type": "raw",
        "format": "csv",
    }
    assert "secure_url" not in metadata
    assert "api_key" not in metadata
    assert "api_secret" not in metadata


def test_each_upload_receives_a_unique_public_id(mock_cloudinary, monkeypatch):
    _, upload = mock_cloudinary
    monkeypatch.setattr(
        cloud_storage,
        "uuid4",
        Mock(
            side_effect=[
                SimpleNamespace(hex="first-unique-id"),
                SimpleNamespace(hex="second-unique-id"),
            ]
        ),
    )

    first = cloud_storage.upload_to_cloudinary(b"first", asset_category="source")
    second = cloud_storage.upload_to_cloudinary(b"second", asset_category="source")

    assert first["public_id"] != second["public_id"]
    assert upload.call_args_list[0].kwargs["overwrite"] is False
    assert upload.call_args_list[1].kwargs["overwrite"] is False


def test_uploads_in_memory_bytes(mock_cloudinary):
    _, upload = mock_cloudinary

    cloud_storage.upload_to_cloudinary(
        b"synthetic report",
        asset_category="report",
    )

    upload.assert_called_once_with(
        b"synthetic report",
        public_id=(
            "student-performance-analytics/"
            "student_performance_report_fixed-unique-id.csv"
        ),
        resource_type="raw",
        type="authenticated",
        overwrite=False,
    )


@pytest.mark.parametrize(
    ("missing_variable", "test_value"),
    [
        ("CLOUDINARY_CLOUD_NAME", "test-cloud"),
        ("CLOUDINARY_API_KEY", "test-api-key"),
        ("CLOUDINARY_API_SECRET", "test-api-secret"),
    ],
)
def test_missing_credentials_raise_clear_error_without_upload(
    mock_cloudinary, monkeypatch, missing_variable, test_value
):
    config, upload = mock_cloudinary
    monkeypatch.delenv(missing_variable)

    with pytest.raises(
        cloud_storage.CloudStorageConfigurationError,
        match=missing_variable,
    ) as error:
        cloud_storage.upload_to_cloudinary(
            b"synthetic data",
            asset_category="source",
        )

    assert test_value not in str(error.value)
    config.assert_not_called()
    upload.assert_not_called()


def test_upload_failure_raises_safe_error(mock_cloudinary):
    _, upload = mock_cloudinary
    upload.side_effect = CloudinaryError("mock upload failure")

    with pytest.raises(
        cloud_storage.CloudStorageUploadError,
        match="Cloudinary upload failed",
    ) as error:
        cloud_storage.upload_to_cloudinary(
            b"synthetic data",
            asset_category="source",
        )

    assert isinstance(error.value.__cause__, CloudinaryError)


def test_rejects_unexpected_cloudinary_metadata(mock_cloudinary):
    _, upload = mock_cloudinary
    upload.side_effect = None
    upload.return_value = {"public_id": "unexpected", "resource_type": "image"}

    with pytest.raises(
        cloud_storage.CloudStorageUploadError,
        match="incomplete or unexpected upload metadata",
    ):
        cloud_storage.upload_to_cloudinary(
            b"synthetic data",
            asset_category="source",
        )


def test_rejects_local_file_paths(mock_cloudinary):
    config, upload = mock_cloudinary

    with pytest.raises(TypeError, match="in-memory file object"):
        cloud_storage.upload_to_cloudinary(
            "C:\\private\\student-data.csv",
            asset_category="source",
        )

    config.assert_not_called()
    upload.assert_not_called()


def test_rejects_unknown_asset_category_before_upload(mock_cloudinary):
    config, upload = mock_cloudinary

    with pytest.raises(ValueError, match="asset_category"):
        cloud_storage.upload_to_cloudinary(
            b"synthetic data",
            asset_category="other",
        )

    config.assert_not_called()
    upload.assert_not_called()
