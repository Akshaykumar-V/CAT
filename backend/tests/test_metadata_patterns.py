"""Tests for metadata-only import and pattern analysis."""

from pathlib import Path

import pandas as pd
from fastapi.testclient import TestClient

from app.analysis import (
    METADATA_COLUMNS,
    analysis_summary,
    difficulty_distribution,
    estimated_time_distribution,
    import_metadata_csv,
    load_pyq_data,
    pattern_tags_frequency,
    questions_by_topic,
    topic_difficulty_relationship,
    topic_frequency_by_slot,
    topic_trends,
)
from app.main import app


client = TestClient(app)
DATA_PATH = Path(__file__).resolve().parents[2] / "data" / "sample_pyq_metadata.csv"


def test_valid_metadata_import_normalizes_names() -> None:
    result = import_metadata_csv(DATA_PATH)

    assert result.report["valid"] is True
    assert result.report["valid_rows"] == 12
    assert "Time & Work" in set(result.data["subtopic"])
    assert "Games/Tournaments" in set(result.data["subtopic"])
    assert "question_text" not in result.data.columns


def test_invalid_section_is_reported_without_silent_discard() -> None:
    data = pd.read_csv(DATA_PATH)
    data.loc[0, "section"] = "Quant"

    result = import_metadata_csv(data.to_csv(index=False).encode())

    assert result.report["valid"] is False
    assert result.report["invalid_rows"] == 1
    assert any("Invalid section values" in error for error in result.report["errors"][0]["errors"])


def test_invalid_difficulty_is_reported() -> None:
    data = pd.read_csv(DATA_PATH)
    data.loc[0, "difficulty"] = "Extreme"

    result = import_metadata_csv(data.to_csv(index=False).encode())

    assert result.report["valid"] is False
    assert any("Invalid difficulty values" in error for error in result.report["errors"][0]["errors"])


def test_missing_columns_are_reported() -> None:
    data = pd.DataFrame({"year": [2024], "section": ["QA"]})

    result = import_metadata_csv(data.to_csv(index=False).encode())

    assert result.report["valid"] is False
    assert "topic" in result.report["missing_columns"]
    assert result.data.columns.tolist() == METADATA_COLUMNS


def test_duplicate_metadata_records_are_reported() -> None:
    data = pd.read_csv(DATA_PATH)
    duplicate = pd.concat([data, data.iloc[[0]]], ignore_index=True)

    result = import_metadata_csv(duplicate.to_csv(index=False).encode())

    assert result.report["duplicate_rows"] == 1
    assert result.report["valid_rows"] == 12
    assert any("Duplicate metadata record" in error for error in result.report["errors"][0]["errors"])


def test_topic_and_slot_analysis() -> None:
    data = load_pyq_data()

    assert questions_by_topic(data)["Arithmetic"] == 2
    assert topic_frequency_by_slot(data)["Slot 2"]["Arithmetic"] == 2
    assert topic_difficulty_relationship(data)["Arithmetic"]["Medium"] == 1


def test_yearly_trends_return_distributions_and_changes() -> None:
    trends = topic_trends(load_pyq_data())
    arithmetic = next(item for item in trends if item["topic"] == "Arithmetic")

    assert arithmetic["yearly_distribution"]["2020"] == 0.25
    assert "year_over_year_change" in arithmetic


def test_difficulty_time_and_pattern_tag_analysis() -> None:
    data = load_pyq_data()

    assert difficulty_distribution(data) == {"Easy": 3, "Hard": 3, "Medium": 6}
    assert estimated_time_distribution(data)["minimum"] == 75
    assert pattern_tags_frequency(data)["comparison"] == 2


def test_blueprint_receives_metadata_signal_without_prediction_claim() -> None:
    response = client.post(
        "/questions/blueprint",
        json={
            "section": "QA",
            "topic": "Arithmetic",
            "subtopic": "Percentages",
            "difficulty": "Medium",
            "question_type": "MCQ",
        },
    )

    assert response.status_code == 200
    signal = response.json()["metadata_signal"]
    assert signal["matching_metadata_records"] == 1
    assert "pattern signal only" in signal["interpretation"]


def test_empty_dataset_analysis_is_structured() -> None:
    empty = pd.DataFrame(columns=METADATA_COLUMNS)

    assert analysis_summary(empty)["total_questions"] == 0
    assert topic_trends(empty) == []
    assert estimated_time_distribution(empty)["buckets"] == {}


def test_metadata_api_endpoints_return_structured_json() -> None:
    for endpoint, key in [
        ("/analysis/patterns", "topic_difficulty"),
        ("/analysis/subtopics", "subtopics"),
        ("/analysis/trends", "topic_trends"),
        ("/analysis/summary", "total_questions"),
    ]:
        response = client.get(endpoint)
        assert response.status_code == 200
        assert key in response.json()


def test_metadata_import_endpoint_returns_report() -> None:
    response = client.post(
        "/analysis/import-metadata",
        content=DATA_PATH.read_bytes(),
        headers={"content-type": "text/csv"},
    )

    assert response.status_code == 200
    assert response.json()["report"]["valid"] is True
    assert len(response.json()["metadata"]) == 12
