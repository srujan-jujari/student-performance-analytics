import pandas as pd
import pytest

from analytics import (
    average_score,
    calculate_metrics,
    classify_risk,
    subject_summary,
    validate_student_data,
)


@pytest.fixture
def valid_student_data():
    return pd.DataFrame(
        {
            "student_id": ["S001", "S002", "S003"],
            "name": ["Alex", "Blair", "Casey"],
            "subject": ["Math", "Math", "Science"],
            "marks": [40, 39, 80],
            "max_marks": [100, 100, 100],
            "attendance": [80, 70, 90],
        }
    )


def test_validate_student_data_accepts_valid_data(valid_student_data):
    assert validate_student_data(valid_student_data) == []


def test_validate_student_data_reports_missing_columns(valid_student_data):
    data = valid_student_data.drop(columns=["name"])

    errors = validate_student_data(data)

    assert any("Missing required columns: name" in error for error in errors)


def test_validate_student_data_rejects_empty_data(valid_student_data):
    errors = validate_student_data(valid_student_data.iloc[0:0])

    assert "DataFrame must contain at least one student record." in errors


def test_validate_student_data_reports_missing_values(valid_student_data):
    valid_student_data.loc[0, "name"] = None

    errors = validate_student_data(valid_student_data)

    assert "Column 'name' contains missing values." in errors


@pytest.mark.parametrize(
    ("column", "value", "expected_error"),
    [
        ("marks", -1, "marks' must contain values greater than or equal to 0"),
        ("marks", 101, "marks' cannot exceed 'max_marks"),
        ("max_marks", 0, "max_marks' must contain values greater than 0"),
        ("marks", "not-a-number", "marks' must contain numeric values"),
    ],
)
def test_validate_student_data_rejects_invalid_marks(
    valid_student_data, column, value, expected_error
):
    valid_student_data[column] = valid_student_data[column].astype(object)
    valid_student_data.loc[0, column] = value

    errors = validate_student_data(valid_student_data)

    assert any(expected_error in error for error in errors)


@pytest.mark.parametrize("attendance", [-1, 100.1, "not-a-number"])
def test_validate_student_data_rejects_invalid_attendance(
    valid_student_data, attendance
):
    valid_student_data["attendance"] = valid_student_data["attendance"].astype(object)
    valid_student_data.loc[0, "attendance"] = attendance

    errors = validate_student_data(valid_student_data)

    assert any("attendance" in error for error in errors)


def test_calculate_metrics_returns_expected_values(valid_student_data):
    metrics = calculate_metrics(valid_student_data)

    assert metrics["total_records"] == 3
    assert metrics["average_percentage"] == pytest.approx(53.0)
    assert metrics["average_attendance"] == pytest.approx(80.0)
    assert metrics["pass_rate"] == pytest.approx(200 / 3)


def test_calculate_metrics_allows_a_custom_pass_threshold(valid_student_data):
    metrics = calculate_metrics(valid_student_data, pass_threshold=50)

    assert metrics["pass_rate"] == pytest.approx(100 / 3)


def test_calculate_metrics_rejects_invalid_data(valid_student_data):
    valid_student_data.loc[0, "marks"] = 101

    with pytest.raises(ValueError, match="Invalid student data"):
        calculate_metrics(valid_student_data)


def test_classify_risk_assigns_each_risk_category_and_preserves_input():
    data = pd.DataFrame(
        {
            "student_id": ["S001", "S002", "S003", "S004", "S005"],
            "name": ["A", "B", "C", "D", "E"],
            "subject": ["Math"] * 5,
            "marks": [90, 39, 80, 45, 50],
            "max_marks": [100] * 5,
            "attendance": [59, 90, 74, 80, 75],
        }
    )
    original = data.copy(deep=True)

    result = classify_risk(data)

    assert result["risk_level"].tolist() == [
        "High",
        "High",
        "Medium",
        "Medium",
        "Low",
    ]
    assert result["percentage"].tolist() == [90.0, 39.0, 80.0, 45.0, 50.0]
    pd.testing.assert_frame_equal(data, original)
    assert "percentage" not in data.columns
    assert "risk_level" not in data.columns


def test_subject_summary_returns_subject_counts_averages_and_pass_rates(
    valid_student_data,
):
    summary = subject_summary(valid_student_data)

    assert summary["subject"].tolist() == ["Math", "Science"]
    assert summary["student_count"].tolist() == [2, 1]
    assert summary["average_percentage"].tolist() == pytest.approx([39.5, 80.0])
    assert summary["pass_rate"].tolist() == pytest.approx([50.0, 100.0])


def test_average_score_keeps_existing_behavior():
    assert average_score([70, 80, 90]) == 80.0


def test_average_score_requires_at_least_one_score():
    with pytest.raises(ValueError, match="At least one score is required"):
        average_score([])
