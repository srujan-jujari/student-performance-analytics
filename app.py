"""Flask entry point for student performance analysis."""

import hmac
import os
import secrets
from io import BytesIO

import pandas as pd
from dotenv import load_dotenv
from flask import Flask, abort, render_template, request, session
from werkzeug.exceptions import RequestEntityTooLarge

from analytics import (
    calculate_metrics,
    classify_risk,
    subject_summary,
    validate_student_data,
)
from cloud_storage import (
    CloudStorageConfigurationError,
    CloudStorageUploadError,
    upload_to_cloudinary,
)

load_dotenv(override=False)

MAX_UPLOAD_SIZE = 5 * 1024 * 1024
MAX_REQUEST_SIZE = 12 * 1024 * 1024
MAX_DASHBOARD_CSV_SIZE = 8 * 1024 * 1024

app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.environ.get("FLASK_SECRET_KEY") or secrets.token_hex(32),
    MAX_CONTENT_LENGTH=MAX_REQUEST_SIZE,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("SESSION_COOKIE_SECURE", "").lower()
    in {"1", "true", "yes"},
)


def _get_csrf_token() -> str:
    """Return a session-bound token for protecting form submissions."""
    token = session.get("_csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["_csrf_token"] = token
    return token


@app.context_processor
def inject_csrf_token():
    """Make a CSRF token generator available to templates."""
    return {"csrf_token": _get_csrf_token}


@app.before_request
def protect_state_changing_requests():
    """Require a session-bound CSRF token on all POST requests."""
    if request.method == "POST":
        expected_token = session.get("_csrf_token")
        submitted_token = request.form.get("csrf_token", "")
        if (
            not expected_token
            or not submitted_token
            or not hmac.compare_digest(expected_token, submitted_token)
        ):
            abort(400)


def _render_upload_error(message: str, status_code: int = 400):
    """Render an upload error without exposing implementation details."""
    return render_template("index.html", error=message), status_code


def _read_valid_student_csv(csv_content: bytes) -> tuple[pd.DataFrame | None, str | None]:
    """Parse and validate CSV bytes, returning either data or a user-facing error."""
    try:
        student_data = pd.read_csv(BytesIO(csv_content))
    except pd.errors.EmptyDataError:
        return None, "The uploaded CSV file is empty."
    except (pd.errors.ParserError, UnicodeDecodeError, ValueError):
        return (
            None,
            "The uploaded file could not be read as a valid CSV. Check its contents and try again.",
        )

    if student_data.empty:
        return None, "The CSV contains no student records. Add at least one data row."

    validation_errors = validate_student_data(student_data)
    if validation_errors:
        return None, "The CSV data is invalid: " + " ".join(validation_errors)
    return student_data, None


def _student_data_from_form() -> tuple[pd.DataFrame | None, bytes | None, str | None]:
    """Read the dashboard's submitted CSV and revalidate it before storage."""
    source_csv = request.form.get("source_csv", "")
    if not source_csv:
        return None, None, "Student data is missing. Upload and analyze the CSV again."

    try:
        csv_content = source_csv.encode("utf-8")
    except UnicodeEncodeError:
        return None, None, "The submitted CSV contains invalid text."

    if len(csv_content) > MAX_DASHBOARD_CSV_SIZE:
        return None, None, "The analyzed CSV is too large to store. Upload a smaller file."
    student_data, error = _read_valid_student_csv(csv_content)
    return student_data, csv_content, error


def _dashboard_context(student_data: pd.DataFrame) -> dict:
    """Build dashboard values using the shared analytics functions."""
    students = classify_risk(student_data)
    risk_counts = {
        level: int((students["risk_level"] == level).sum())
        for level in ("High", "Medium", "Low")
    }
    summary = subject_summary(student_data)
    return {
        "metrics": calculate_metrics(student_data),
        "risk_counts": risk_counts,
        "subject_summary": summary.to_dict(orient="records"),
        "students": students.to_dict(orient="records"),
    }


def _render_dashboard(
    student_data: pd.DataFrame,
    source_csv: str,
    message: str | None = None,
    message_type: str = "success",
    completed_action: str | None = None,
):
    """Render analyzed data and an optional storage result."""
    return render_template(
        "dashboard.html",
        **_dashboard_context(student_data),
        source_csv=source_csv,
        storage_message=message,
        storage_message_type=message_type,
        completed_action=completed_action,
    )


def _render_storage_error(message: str, status_code: int = 400):
    """Render a safe error when submitted dashboard data cannot be validated."""
    return render_template(
        "error.html",
        message=message,
    ), status_code


def _cloudinary_failure_message(error: Exception) -> str:
    """Return a safe storage error that does not reveal credentials or URLs."""
    if isinstance(error, CloudStorageConfigurationError):
        return f"Cloudinary storage is not configured. {error}"
    return "Cloudinary could not store the file. Check the server configuration and try again."


@app.get("/")
def index():
    """Show the CSV upload page."""
    return render_template("index.html")


@app.post("/upload")
def upload():
    """Validate and analyze an uploaded CSV file entirely in memory."""
    uploaded_file = request.files.get("file")
    if uploaded_file is None or not uploaded_file.filename:
        return _render_upload_error("Choose a CSV file to upload.")

    if not uploaded_file.filename.lower().endswith(".csv"):
        return _render_upload_error("The uploaded file must have a .csv extension.")

    csv_content = uploaded_file.read(MAX_UPLOAD_SIZE + 1)
    if len(csv_content) > MAX_UPLOAD_SIZE:
        return _render_upload_error(
            "The file is too large. Upload a CSV file no larger than 5 MB.", 413
        )

    student_data, error = _read_valid_student_csv(csv_content)
    if error:
        return _render_upload_error(error)

    return _render_dashboard(student_data, csv_content.decode("utf-8"))


@app.post("/cloudinary/source")
def store_source_csv():
    """Validate and store the source student CSV as an authenticated Cloudinary asset."""
    student_data, csv_content, error = _student_data_from_form()
    if error:
        return _render_storage_error(error)

    try:
        upload_to_cloudinary(BytesIO(csv_content))
    except (CloudStorageConfigurationError, CloudStorageUploadError) as error:
        return _render_dashboard(
            student_data,
            csv_content.decode("utf-8"),
            message=_cloudinary_failure_message(error),
            message_type="danger",
        )

    return _render_dashboard(
        student_data,
        csv_content.decode("utf-8"),
        message="The validated source CSV was stored as an authenticated Cloudinary asset.",
        completed_action="source",
    )


@app.post("/cloudinary/report")
def store_analyzed_report():
    """Generate and store the analyzed student report in memory."""
    student_data, _, error = _student_data_from_form()
    if error:
        return _render_storage_error(error)
    source_csv = request.form["source_csv"]

    analyzed_students = classify_risk(student_data)
    report_csv = analyzed_students.to_csv(index=False).encode("utf-8")
    try:
        upload_to_cloudinary(BytesIO(report_csv))
    except (CloudStorageConfigurationError, CloudStorageUploadError) as error:
        return _render_dashboard(
            student_data,
            source_csv,
            message=_cloudinary_failure_message(error),
            message_type="danger",
        )

    return _render_dashboard(
        student_data,
        source_csv,
        message="The analyzed CSV report was stored as an authenticated Cloudinary asset.",
        completed_action="report",
    )


@app.get("/dashboard")
def dashboard():
    """Show the dashboard prompt when no upload has been analyzed yet."""
    return render_template("dashboard.html")


@app.errorhandler(400)
def bad_request(_error):
    """Show a generic message for invalid requests, including failed CSRF checks."""
    return (
        render_template(
            "error.html",
            message="The request was invalid or the form expired. Return to the page and try again.",
        ),
        400,
    )


@app.errorhandler(404)
def page_not_found(_error):
    """Render a friendly page for unknown routes."""
    return render_template("error.html", message="The page you requested was not found."), 404


@app.errorhandler(RequestEntityTooLarge)
def upload_too_large(_error):
    """Explain the configured request limit without showing a server error."""
    return _render_upload_error(
        "The request is too large. Upload a CSV file no larger than 5 MB.", 413
    )


@app.errorhandler(500)
def internal_server_error(_error):
    """Show a generic message instead of an exception or stack trace."""
    return (
        render_template(
            "error.html",
            message="Something went wrong while processing your request. Please try again.",
        ),
        500,
    )


if __name__ == "__main__":
    app.run()
