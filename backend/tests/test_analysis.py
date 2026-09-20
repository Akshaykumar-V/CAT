"""Tests for PYQ metadata validation, analysis helpers, and API routes."""

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.analysis import (
    DataValidationError,
    difficulty_distribution,
    load_pyq_data,
    questions_by_section,
    topic_frequency_by_year,
    validate_pyq_data,
)
from app.main import app


client = TestClient(app)


def test_sample_data_loads_and_section_counts_are_correct() -> None:
    data = load_pyq_data()

    assert len(data) == 12
    assert questions_by_section(data) == {"DILR": 4, "QA": 4, "VARC": 4}


def test_difficulty_distribution_is_correct() -> None:
    data = load_pyq_data()

    assert difficulty_distribution(data) == {"Easy": 3, "Hard": 3, "Medium": 6}


def test_topic_frequency_by_year_returns_expected_record() -> None:
    data = load_pyq_data()
    trends = topic_frequency_by_year(data)

    assert {"year": 2022, "topic": "Arithmetic", "question_count": 1} in trends


def test_validation_rejects_missing_required_column() -> None:
    invalid_data = pd.DataFrame({"year": [2022], "section": ["QA"]})

    with pytest.raises(DataValidationError, match="Missing required columns"):
        validate_pyq_data(invalid_data)


def test_validation_rejects_invalid_section() -> None:
    data = load_pyq_data()
    data.loc[0, "section"] = "Quant"

    with pytest.raises(DataValidationError, match="Invalid section values"):
        validate_pyq_data(data)


@pytest.mark.parametrize(
    ("endpoint", "expected_key"),
    [
        ("/analysis/overview", "total_questions"),
        ("/analysis/sections", "questions_by_section"),
        ("/analysis/topics", "topic_frequency_by_year"),
        ("/analysis/difficulty", "difficulty_distribution"),
        ("/analysis/trends", "topic_trends"),
    ],
)
def test_analysis_endpoints_return_json(endpoint: str, expected_key: str) -> None:
    response = client.get(endpoint)

    assert response.status_code == 200
    assert expected_key in response.json()
