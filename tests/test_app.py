from io import BytesIO
import re
from unittest.mock import Mock

import pandas as pd
import pytest
from cloud_storage import CloudStorageConfigurationError, CloudStorageUploadError

import app as app_module
from app import app


CSV_CONTENT = (
    "student_id,name,subject,marks,max_marks,attendance\n"
    "S001,Alex,Math,90,100,90\n"
    "S002,Blair,Math,39,100,90\n"
    "S003,Casey,Science,45,100,70\n"
)


@pytest.fixture
def client():
    app.config.update(TESTING=True)
    with app.test_client() as test_client:
        yield test_client


def get_csrf_token(client):
    response = client.get("/")
    match = re.search(rb'name="csrf_token" value="([^"]+)"', response.data)
    assert match is not None
    return match.group(1).decode()


def upload_csv(client, content, filename="students.csv"):
    return client.post(
        "/upload",
        data={
            "csrf_token": get_csrf_token(client),
            "file": (BytesIO(content), filename),
        },
        content_type="multipart/form-data",
    )


def post_storage_action(client, endpoint, csv_content=CSV_CONTENT):
    return client.post(
        endpoint,
        data={
            "csrf_token": get_csrf_token(client),
            "source_csv": csv_content,
        },
        content_type="multipart/form-data",
    )


def test_home_page_contains_csv_upload_form(client):
    response = client.get("/")

    assert response.status_code == 200
    assert b'enctype="multipart/form-data"' in response.data
    assert b'name="file"' in response.data


def test_valid_upload_renders_dashboard_with_analytics(client):
    response = upload_csv(client, CSV_CONTENT.encode())

    assert response.status_code == 200
    assert b"Total records" in response.data
    assert b"3" in response.data
    assert b"Average percentage" in response.data
    assert b"Average attendance" in response.data
    assert b"Pass rate" in response.data
    assert b"High: 1" in response.data
    assert b"Medium: 1" in response.data
    assert b"Low: 1" in response.data
    assert b"Subject summary" in response.data
    assert b"Student performance" in response.data
    assert b"Alex" in response.data
    assert b"90.0%" in response.data
    assert b'id="risk-chart"' in response.data
    assert b'id="subject-chart"' in response.data
    assert b'id="student-search"' in response.data
    assert b'id="subject-filter"' in response.data
    assert b'id="risk-filter"' in response.data
    assert b"Download filtered records CSV" in response.data
    assert b"dashboard.js" in response.data


def test_dashboard_escapes_uploaded_text_in_table_and_json(client):
    csv_content = (
        b"student_id,name,subject,marks,max_marks,attendance\n"
        b"S001,<img src=x onerror=alert(1)>,Math,90,100,90\n"
    )

    response = upload_csv(client, csv_content)

    assert response.status_code == 200
    assert b"&lt;img src=x onerror=alert(1)&gt;" in response.data
    assert b"<img src=x onerror=alert(1)>" not in response.data


def test_dashboard_shows_cloudinary_storage_actions(client):
    response = upload_csv(client, CSV_CONTENT.encode())

    assert response.status_code == 200
    assert b"Store source CSV in Cloudinary" in response.data
    assert b"Store analyzed report in Cloudinary" in response.data
    assert b'name="csrf_token"' in response.data


def test_upload_reports_missing_file(client):
    response = client.post(
        "/upload",
        data={"csrf_token": get_csrf_token(client)},
        content_type="multipart/form-data",
    )

    assert response.status_code == 400
    assert b"Choose a CSV file to upload." in response.data


def test_upload_rejects_non_csv_file(client):
    response = upload_csv(client, b"not a csv", filename="students.txt")

    assert response.status_code == 400
    assert b"must have a .csv extension" in response.data


def test_upload_reports_invalid_csv_contents(client):
    response = upload_csv(client, b"student_id,name\nS001,Alex\n")

    assert response.status_code == 400
    assert b"CSV data is invalid" in response.data
    assert b"Missing required columns" in response.data
    assert b"Traceback" not in response.data


def test_upload_reports_malformed_csv(client):
    response = upload_csv(client, b'"student_id","name\nS001,Alex\n')

    assert response.status_code == 400
    assert b"could not be read as a valid CSV" in response.data
    assert b"Traceback" not in response.data


def test_upload_reports_empty_csv(client):
    response = upload_csv(client, b"")

    assert response.status_code == 400
    assert b"uploaded CSV file is empty" in response.data


def test_upload_reports_csv_with_no_student_rows(client):
    response = upload_csv(
        client,
        b"student_id,name,subject,marks,max_marks,attendance\n",
    )

    assert response.status_code == 400
    assert b"contains no student records" in response.data


def test_upload_rejects_files_larger_than_configured_limit(client):
    response = upload_csv(
        client,
        b"x" * (app.config["MAX_CONTENT_LENGTH"] + 1),
    )

    assert response.status_code == 413
    assert b"no larger than 5 MB" in response.data


def test_dashboard_get_shows_upload_prompt(client):
    response = client.get("/dashboard")

    assert response.status_code == 200
    assert b"Upload a CSV file to see performance metrics" in response.data


def test_upload_rejects_post_without_csrf_token(client):
    response = client.post(
        "/upload",
        data={"file": (BytesIO(CSV_CONTENT.encode()), "students.csv")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 400
    assert b"form expired" in response.data


def test_store_source_csv_uploads_only_validated_csv(client, monkeypatch):
    mock = Mock(
        return_value={
            "public_id": "private/source.csv",
            "resource_type": "raw",
            "format": "csv",
        }
    )
    monkeypatch.setattr(app_module, "upload_to_cloudinary", mock)

    response = post_storage_action(client, "/cloudinary/source")

    assert response.status_code == 200
    assert b"validated source CSV was stored" in response.data
    assert b"private/source.csv" not in response.data
    mock.assert_called_once()
    uploaded_bytes = mock.call_args.args[0].getvalue()
    assert uploaded_bytes == CSV_CONTENT.encode()
    uploaded_data = pd.read_csv(BytesIO(uploaded_bytes))
    assert uploaded_data["student_id"].tolist() == ["S001", "S002", "S003"]
    assert "percentage" not in uploaded_data.columns
    assert "risk_level" not in uploaded_data.columns


def test_store_report_contains_percentage_and_risk_without_recalculating_in_route(
    client, monkeypatch
):
    mock = Mock(
        return_value={
            "public_id": "private/report.csv",
            "resource_type": "raw",
            "format": "csv",
        }
    )
    monkeypatch.setattr(app_module, "upload_to_cloudinary", mock)

    response = post_storage_action(client, "/cloudinary/report")

    assert response.status_code == 200
    assert b"analyzed CSV report was stored" in response.data
    assert b"private/report.csv" not in response.data
    mock.assert_called_once()
    uploaded_bytes = mock.call_args.args[0].getvalue()
    report = pd.read_csv(BytesIO(uploaded_bytes))
    assert report["percentage"].tolist() == pytest.approx([90.0, 39.0, 45.0])
    assert report["risk_level"].tolist() == ["Low", "High", "Medium"]


@pytest.mark.parametrize("endpoint", ["/cloudinary/source", "/cloudinary/report"])
def test_storage_routes_validate_data_before_calling_cloudinary(
    client, monkeypatch, endpoint
):
    mock = Mock()
    monkeypatch.setattr(app_module, "upload_to_cloudinary", mock)

    response = post_storage_action(
        client,
        endpoint,
        "student_id,name,subject,marks,max_marks,attendance\nS001,Alex,Math,101,100,90\n",
    )

    assert response.status_code == 400
    assert b"cannot exceed" in response.data
    mock.assert_not_called()


@pytest.mark.parametrize(
    "storage_error",
    [
        CloudStorageConfigurationError(
            "Missing required Cloudinary environment variables: CLOUDINARY_API_SECRET."
        ),
        CloudStorageUploadError("Cloudinary upload failed. Check the server configuration and retry."),
    ],
)
@pytest.mark.parametrize("endpoint", ["/cloudinary/source", "/cloudinary/report"])
def test_storage_route_shows_safe_failure_message(
    client, monkeypatch, storage_error, endpoint
):
    mock = Mock(side_effect=storage_error)
    monkeypatch.setattr(app_module, "upload_to_cloudinary", mock)

    response = post_storage_action(client, endpoint)

    assert response.status_code == 200
    assert b"Cloudinary storage is not configured" in response.data or (
        b"Cloudinary could not store the file" in response.data
    )
    assert b"test-api-secret" not in response.data


def test_storage_routes_require_csrf_token(client, monkeypatch):
    mock = Mock()
    monkeypatch.setattr(app_module, "upload_to_cloudinary", mock)

    response = client.post(
        "/cloudinary/source",
        data={"source_csv": CSV_CONTENT},
        content_type="multipart/form-data",
    )

    assert response.status_code == 400
    mock.assert_not_called()
