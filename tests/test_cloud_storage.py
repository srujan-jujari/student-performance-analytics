from io import BytesIO
from unittest.mock import Mock

import pytest
from botocore.exceptions import ClientError

import cloud_storage


@pytest.fixture
def mock_s3(monkeypatch):
    monkeypatch.setattr(cloud_storage, "load_dotenv", Mock())
    monkeypatch.setenv("AWS_REGION", "ap-southeast-2")
    monkeypatch.setenv("AWS_S3_BUCKET", "student-performance-analytics-cc")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test-access-key")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test-secret-key")
    monkeypatch.setattr(cloud_storage, "uuid4", Mock())
    cloud_storage.uuid4.return_value.hex = "fixed-unique-id"

    client = Mock()
    monkeypatch.setattr(cloud_storage.boto3, "client", Mock(return_value=client))
    monkeypatch.setattr(cloud_storage, "_create_s3_client", Mock(
        return_value=(client, "student-performance-analytics-cc")
    ))
    return client


@pytest.mark.parametrize(
    ("asset_category", "expected_key"),
    [
        ("source", "student-performance-analytics/source/source_fixed-unique-id.csv"),
        ("report", "student-performance-analytics/report/report_fixed-unique-id.csv"),
    ],
)
def test_uploads_csv_to_private_s3_bucket(mock_s3, asset_category, expected_key):
    csv_stream = BytesIO(b"synthetic,test,data\n")

    metadata = cloud_storage.upload_to_s3(csv_stream, asset_category=asset_category)

    mock_s3.upload_fileobj.assert_called_once_with(
        csv_stream,
        "student-performance-analytics-cc",
        expected_key,
        ExtraArgs={
            "ContentType": "text/csv; charset=utf-8",
            "ServerSideEncryption": "AES256",
        },
    )
    assert metadata == {
        "bucket": "student-performance-analytics-cc",
        "key": expected_key,
        "content_type": "text/csv; charset=utf-8",
    }
    assert "url" not in metadata
    assert "secret" not in metadata


def test_each_upload_receives_unique_key(mock_s3, monkeypatch):
    ids = iter(["first-id", "second-id"])
    monkeypatch.setattr(cloud_storage, "uuid4", lambda: type("ID", (), {"hex": next(ids)})())

    first = cloud_storage.upload_to_s3(b"first", asset_category="source")
    second = cloud_storage.upload_to_s3(b"second", asset_category="source")

    assert first["key"] != second["key"]
    assert mock_s3.upload_fileobj.call_count == 2


def test_uploads_bytes(mock_s3):
    content = b"synthetic report"
    cloud_storage.upload_to_s3(content, asset_category="report")
    args, kwargs = mock_s3.upload_fileobj.call_args
    assert isinstance(args[0], BytesIO)
    assert args[0].readable()
    assert args[0].read() == content
    assert args[1] == "student-performance-analytics-cc"
    assert args[2].startswith("student-performance-analytics/report/")
    assert kwargs["ExtraArgs"]["ServerSideEncryption"] == "AES256"


@pytest.mark.parametrize("asset_category", ["unknown", "", None])
def test_rejects_unknown_category_before_s3_client(mock_s3, asset_category):
    with pytest.raises(ValueError, match="asset_category"):
        cloud_storage.upload_to_s3(b"synthetic data", asset_category=asset_category)


def test_rejects_file_path_strings_before_s3_client(mock_s3):
    with pytest.raises(TypeError, match="in-memory file object"):
        cloud_storage.upload_to_s3(r"C:\private\student-data.csv", asset_category="source")


def test_upload_failure_raises_safe_error(mock_s3):
    mock_s3.upload_fileobj.side_effect = ClientError(
        {"Error": {"Code": "AccessDenied", "Message": "mock secret details"}},
        "PutObject",
    )

    with pytest.raises(
        cloud_storage.CloudStorageUploadError,
        match="Amazon S3 could not store the file",
    ) as error:
        cloud_storage.upload_to_s3(b"synthetic data", asset_category="source")

    assert "mock secret details" not in str(error.value)
    assert isinstance(error.value.__cause__, ClientError)


def test_missing_region_fails_before_client_creation(monkeypatch):
    monkeypatch.setattr(cloud_storage, "load_dotenv", Mock())
    monkeypatch.delenv("AWS_REGION", raising=False)
    monkeypatch.setenv("AWS_S3_BUCKET", "student-performance-analytics-cc")
    create_client = Mock()
    monkeypatch.setattr(cloud_storage.boto3, "client", create_client)

    with pytest.raises(cloud_storage.CloudStorageConfigurationError, match="AWS_REGION"):
        cloud_storage._create_s3_client()

    create_client.assert_not_called()


def test_missing_bucket_fails_before_client_creation(monkeypatch):
    monkeypatch.setattr(cloud_storage, "load_dotenv", Mock())
    monkeypatch.setenv("AWS_REGION", "ap-southeast-2")
    monkeypatch.delenv("AWS_S3_BUCKET", raising=False)
    create_client = Mock()
    monkeypatch.setattr(cloud_storage.boto3, "client", create_client)

    with pytest.raises(cloud_storage.CloudStorageConfigurationError, match="AWS_S3_BUCKET"):
        cloud_storage._create_s3_client()

    create_client.assert_not_called()


def test_only_one_aws_credential_is_rejected(monkeypatch):
    monkeypatch.setattr(cloud_storage, "load_dotenv", Mock())
    monkeypatch.setenv("AWS_REGION", "ap-southeast-2")
    monkeypatch.setenv("AWS_S3_BUCKET", "student-performance-analytics-cc")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test-access-key")
    monkeypatch.delenv("AWS_SECRET_ACCESS_KEY", raising=False)

    with pytest.raises(cloud_storage.CloudStorageConfigurationError, match="Set both"):
        cloud_storage._create_s3_client()
