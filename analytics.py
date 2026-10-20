"""Validation and summary helpers for student performance data."""

import numpy as np
import pandas as pd

REQUIRED_COLUMNS = (
    "student_id",
    "name",
    "subject",
    "marks",
    "max_marks",
    "attendance",
)
NUMERIC_COLUMNS = ("marks", "max_marks", "attendance")


def average_score(scores: list[float]) -> float:
    """Return the average of a non-empty collection of scores."""
    if not scores:
        raise ValueError("At least one score is required.")
    return float(np.mean(scores))


def validate_student_data(df: pd.DataFrame) -> list[str]:
    """Return a list of validation errors, or an empty list when data is valid.

    Numeric values stored as strings (for example, ``"82.5"``) are accepted;
    the analysis functions convert them to numbers on a copy of the data.
    """
    if not isinstance(df, pd.DataFrame):
        return ["Input must be a pandas DataFrame."]

    errors: list[str] = []
    missing_columns = [column for column in REQUIRED_COLUMNS if column not in df.columns]
    if missing_columns:
        errors.append(f"Missing required columns: {', '.join(missing_columns)}.")
    if df.empty:
        errors.append("DataFrame must contain at least one student record.")

    available_columns = [column for column in REQUIRED_COLUMNS if column in df.columns]
    for column in available_columns:
        if df[column].isna().any():
            errors.append(f"Column '{column}' contains missing values.")

    numeric_values: dict[str, pd.Series] = {}
    for column in NUMERIC_COLUMNS:
        if column not in df.columns:
            continue
        values = pd.to_numeric(df[column], errors="coerce")
        numeric_values[column] = values
        invalid_values = df[column].notna() & values.isna()
        if invalid_values.any():
            errors.append(f"Column '{column}' must contain numeric values.")

    if "max_marks" in numeric_values:
        invalid_max_marks = numeric_values["max_marks"].notna() & (
            numeric_values["max_marks"] <= 0
        )
        if invalid_max_marks.any():
            errors.append("Column 'max_marks' must contain values greater than 0.")

    if "marks" in numeric_values and "max_marks" in numeric_values:
        marks = numeric_values["marks"]
        max_marks = numeric_values["max_marks"]
        comparable_scores = marks.notna() & max_marks.notna()
        if (comparable_scores & (marks < 0)).any():
            errors.append("Column 'marks' must contain values greater than or equal to 0.")
        if (comparable_scores & (marks > max_marks)).any():
            errors.append("Column 'marks' cannot exceed 'max_marks'.")

    if "attendance" in numeric_values:
        attendance = numeric_values["attendance"]
        invalid_attendance = attendance.notna() & (
            (attendance < 0) | (attendance > 100)
        )
        if invalid_attendance.any():
            errors.append("Column 'attendance' must be between 0 and 100.")

    return errors


def _validated_numeric_data(df: pd.DataFrame) -> pd.DataFrame:
    """Validate data and return a numeric, independent copy."""
    errors = validate_student_data(df)
    if errors:
        raise ValueError("Invalid student data: " + " ".join(errors))

    data = df.copy()
    for column in NUMERIC_COLUMNS:
        data[column] = pd.to_numeric(data[column])
    return data


def _validate_pass_threshold(pass_threshold: float) -> float:
    """Convert and validate a pass threshold expressed as a percentage."""
    try:
        threshold = float(pass_threshold)
    except (TypeError, ValueError) as error:
        raise ValueError("Pass threshold must be a number between 0 and 100.") from error

    if not np.isfinite(threshold) or not 0 <= threshold <= 100:
        raise ValueError("Pass threshold must be a number between 0 and 100.")
    return threshold


def calculate_metrics(
    df: pd.DataFrame, pass_threshold: float = 40.0
) -> dict[str, int | float]:
    """Calculate overall performance metrics for student records.

    ``pass_threshold`` and ``pass_rate`` are expressed in percentage points.
    The default demonstration threshold is 40%.
    """
    data = _validated_numeric_data(df)
    threshold = _validate_pass_threshold(pass_threshold)
    percentage = data["marks"] / data["max_marks"] * 100

    return {
        "total_records": int(len(data)),
        "average_percentage": float(percentage.mean()),
        "average_attendance": float(data["attendance"].mean()),
        "pass_rate": float((percentage >= threshold).mean() * 100),
    }


def classify_risk(df: pd.DataFrame) -> pd.DataFrame:
    """Return a copy with percentage and a High, Medium, or Low risk label."""
    data = _validated_numeric_data(df)
    data["percentage"] = data["marks"] / data["max_marks"] * 100

    high_risk = (data["attendance"] < 60) | (data["percentage"] < 40)
    medium_risk = (~high_risk) & (
        (data["attendance"] < 75) | (data["percentage"] < 50)
    )
    data["risk_level"] = np.select(
        [high_risk, medium_risk],
        ["High", "Medium"],
        default="Low",
    )
    return data


def subject_summary(
    df: pd.DataFrame, pass_threshold: float = 40.0
) -> pd.DataFrame:
    """Return one row per subject with count, average percentage, and pass rate."""
    data = _validated_numeric_data(df)
    threshold = _validate_pass_threshold(pass_threshold)
    data["percentage"] = data["marks"] / data["max_marks"] * 100
    data["passed"] = data["percentage"] >= threshold

    summary = (
        data.groupby("subject", as_index=False)
        .agg(
            student_count=("student_id", "size"),
            average_percentage=("percentage", "mean"),
            pass_rate=("passed", "mean"),
        )
        .sort_values("subject")
        .reset_index(drop=True)
    )
    summary["pass_rate"] = summary["pass_rate"] * 100
    return summary
