"""Metadata-only CAT pattern import and analysis helpers."""

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import IO

import pandas as pd

METADATA_COLUMNS = [
    "year", "slot", "section", "topic", "subtopic", "question_type",
    "difficulty", "concepts", "estimated_time_seconds", "pattern_tags",
    "source_reference",
]
REQUIRED_COLUMNS = METADATA_COLUMNS
VALID_SECTIONS = {"VARC", "DILR", "QA"}
VALID_DIFFICULTIES = {"Easy", "Medium", "Hard"}
DEFAULT_DATA_PATH = Path(__file__).resolve().parents[2] / "data" / "sample_pyq_metadata.csv"

_TOPIC_ALIASES = {
    "time and work": "Time & Work",
    "time, speed and distance": "Time, Speed & Distance",
    "games and tournaments": "Games/Tournaments",
    "games/tournaments": "Games/Tournaments",
    "linear equations": "Algebra",
}
_SUBTOPIC_ALIASES = {
    "main idea": "Main Idea",
    "time and work": "Time & Work",
    "games and tournaments": "Games/Tournaments",
    "linear equations": "Linear Equations",
}


class DataValidationError(ValueError):
    """Raised when strict metadata validation fails."""


@dataclass
class MetadataImportResult:
    """Clean metadata plus explicit errors for every rejected row."""

    data: pd.DataFrame
    report: dict[str, object]


def _normalize_name(value: object, aliases: dict[str, str]) -> str:
    normalized = " ".join(str(value).strip().split())
    return aliases.get(normalized.casefold(), normalized)


def _normalize_list(value: object) -> str:
    values = str(value).replace("|", ";").replace(",", ";").split(";")
    return "; ".join(dict.fromkeys(item.strip() for item in values if item.strip()))


def _read_csv(source: str | Path | IO[str] | bytes) -> pd.DataFrame:
    if isinstance(source, bytes):
        return pd.read_csv(BytesIO(source))
    if hasattr(source, "read"):
        return pd.read_csv(source)
    path = Path(source)
    if not path.exists():
        raise DataValidationError(f"Metadata CSV was not found: {path}")
    try:
        return pd.read_csv(path)
    except (OSError, pd.errors.ParserError) as error:
        raise DataValidationError(f"Could not read metadata CSV: {error}") from error


def import_metadata_csv(source: str | Path | IO[str] | bytes) -> MetadataImportResult:
    """Load CSV metadata without silently discarding invalid rows."""
    data = _read_csv(source)
    missing_columns = sorted(set(METADATA_COLUMNS) - set(data.columns))
    if missing_columns:
        return MetadataImportResult(
            pd.DataFrame(columns=METADATA_COLUMNS),
            {"valid": False, "total_rows": len(data), "valid_rows": 0,
             "invalid_rows": len(data), "duplicate_rows": 0,
             "missing_columns": missing_columns,
             "errors": [{"row": None, "errors": [
                 f"Missing required columns: {', '.join(missing_columns)}"
             ]}]},
        )

    errors: list[dict[str, object]] = []
    normalized_rows: dict[int, dict[str, object]] = {}
    for index, row in data[METADATA_COLUMNS].iterrows():
        row_errors: list[str] = []
        normalized = row.to_dict()
        for column in METADATA_COLUMNS:
            if pd.isna(normalized[column]) or str(normalized[column]).strip() == "":
                row_errors.append(f"{column} is required")
        try:
            year = pd.to_numeric(normalized["year"])
            if pd.isna(year) or int(year) != year:
                row_errors.append("year must be a whole number")
            else:
                normalized["year"] = int(year)
        except (TypeError, ValueError):
            row_errors.append("year must be a whole number")
        try:
            estimated = pd.to_numeric(normalized["estimated_time_seconds"])
            if pd.isna(estimated) or int(estimated) != estimated or int(estimated) <= 0:
                row_errors.append("estimated_time_seconds must be a positive whole number")
            else:
                normalized["estimated_time_seconds"] = int(estimated)
        except (TypeError, ValueError):
            row_errors.append("estimated_time_seconds must be a positive whole number")

        normalized["section"] = str(normalized["section"]).strip().upper()
        normalized["difficulty"] = str(normalized["difficulty"]).strip().title()
        normalized["topic"] = _normalize_name(normalized["topic"], _TOPIC_ALIASES)
        normalized["subtopic"] = _normalize_name(normalized["subtopic"], _SUBTOPIC_ALIASES)
        normalized["slot"] = " ".join(str(normalized["slot"]).strip().split())
        normalized["question_type"] = " ".join(str(normalized["question_type"]).strip().split())
        normalized["concepts"] = _normalize_list(normalized["concepts"])
        normalized["pattern_tags"] = _normalize_list(normalized["pattern_tags"])
        normalized["source_reference"] = str(normalized["source_reference"]).strip()
        if normalized["section"] not in VALID_SECTIONS:
            row_errors.append(f"Invalid section values: {normalized['section']}")
        if normalized["difficulty"] not in VALID_DIFFICULTIES:
            row_errors.append(f"Invalid difficulty values: {normalized['difficulty']}")
        if row_errors:
            errors.append({"row": int(index) + 2, "errors": row_errors})
        else:
            normalized_rows[index] = normalized

    normalized_data = pd.DataFrame.from_dict(normalized_rows, orient="index", columns=METADATA_COLUMNS)
    duplicate_indexes = []
    if not normalized_data.empty:
        duplicate_mask = normalized_data.duplicated(
            subset=[column for column in METADATA_COLUMNS if column != "source_reference"],
            keep="first",
        )
        duplicate_indexes = list(normalized_data.index[duplicate_mask])
        for index in duplicate_indexes:
            errors.append({"row": int(index) + 2, "errors": ["Duplicate metadata record"]})
        normalized_data = normalized_data.drop(index=duplicate_indexes)

    clean = normalized_data.reset_index(drop=True)
    report = {
        "valid": not errors,
        "total_rows": int(len(data)),
        "valid_rows": int(len(clean)),
        "invalid_rows": int(len(data) - len(clean)),
        "duplicate_rows": len(duplicate_indexes),
        "missing_columns": [],
        "errors": errors,
    }
    return MetadataImportResult(clean, report)


def validate_metadata_data(data: pd.DataFrame) -> pd.DataFrame:
    """Strictly validate an in-memory metadata frame."""
    result = import_metadata_csv(data.to_csv(index=False).encode("utf-8"))
    if not result.report["valid"] or result.report["valid_rows"] != result.report["total_rows"]:
        raise DataValidationError(str(result.report["errors"]))
    return result.data


def load_pyq_data(csv_path: str | Path = DEFAULT_DATA_PATH) -> pd.DataFrame:
    """Load the metadata-only development dataset strictly."""
    result = import_metadata_csv(csv_path)
    if not result.report["valid"] or result.report["valid_rows"] != result.report["total_rows"]:
        raise DataValidationError(str(result.report))
    return result.data


def validate_pyq_data(data: pd.DataFrame) -> pd.DataFrame:
    """Backward-compatible strict validator for metadata frames."""
    return validate_metadata_data(data)


def _count_by(data: pd.DataFrame, column: str) -> dict[str, int]:
    if data.empty:
        return {}
    return {str(key): int(value) for key, value in data.groupby(column).size().sort_index().items()}


def questions_by_section(data: pd.DataFrame) -> dict[str, int]:
    return _count_by(data, "section")


def questions_by_topic(data: pd.DataFrame) -> dict[str, int]:
    return _count_by(data, "topic")


def subtopic_frequency(data: pd.DataFrame) -> dict[str, int]:
    return _count_by(data, "subtopic")


def topic_frequency_by_year(data: pd.DataFrame) -> list[dict[str, int | str]]:
    if data.empty:
        return []
    grouped = data.groupby(["year", "topic"]).size().reset_index(name="question_count")
    return [{"year": int(row.year), "topic": str(row.topic), "question_count": int(row.question_count)}
            for row in grouped.sort_values(["year", "topic"]).itertuples(index=False)]


def topic_frequency_by_slot(data: pd.DataFrame) -> dict[str, dict[str, int]]:
    if data.empty:
        return {}
    return {str(slot): _count_by(slot_data, "topic") for slot, slot_data in data.groupby("slot")}


def difficulty_distribution(data: pd.DataFrame) -> dict[str, int]:
    return _count_by(data, "difficulty")


def section_difficulty_distribution(data: pd.DataFrame) -> dict[str, dict[str, int]]:
    if data.empty:
        return {}
    return {str(section): _count_by(section_data, "difficulty")
            for section, section_data in data.groupby("section")}


def question_type_distribution(data: pd.DataFrame) -> dict[str, int]:
    return _count_by(data, "question_type")


def topic_difficulty_relationship(data: pd.DataFrame) -> dict[str, dict[str, int]]:
    if data.empty:
        return {}
    return {str(topic): _count_by(topic_data, "difficulty")
            for topic, topic_data in data.groupby("topic")}


def estimated_time_distribution(data: pd.DataFrame) -> dict[str, object]:
    if data.empty:
        return {"buckets": {}, "minimum": None, "maximum": None, "average": None}
    buckets = pd.cut(data["estimated_time_seconds"], [0, 90, 150, float("inf")], labels=["short", "medium", "long"]).value_counts().sort_index()
    return {"buckets": {str(key): int(value) for key, value in buckets.items()},
            "minimum": int(data["estimated_time_seconds"].min()),
            "maximum": int(data["estimated_time_seconds"].max()),
            "average": round(float(data["estimated_time_seconds"].mean()), 2)}


def pattern_tags_frequency(data: pd.DataFrame) -> dict[str, int]:
    if data.empty:
        return {}
    tags = data["pattern_tags"].str.split("; ").explode()
    return {str(key): int(value) for key, value in tags.value_counts().sort_index().items() if key}


def topic_trends(data: pd.DataFrame) -> list[dict[str, object]]:
    if data.empty:
        return []
    yearly = data.groupby(["topic", "year"]).size().unstack(fill_value=0)
    totals = data.groupby("year").size()
    result = []
    for topic, row in yearly.iterrows():
        distribution = {str(year): round(int(row.get(year, 0)) / int(totals[year]), 4) for year in totals.index}
        changes = {str(year): round(distribution[str(year)] - distribution[str(previous)], 4)
                   for previous, year in zip(totals.index, totals.index[1:])}
        result.append({"topic": str(topic), "yearly_distribution": distribution,
                       "year_over_year_change": changes})
    return result


def analysis_summary(data: pd.DataFrame) -> dict[str, object]:
    return {"total_questions": int(len(data)),
            "years": sorted(int(year) for year in data["year"].unique()) if not data.empty else [],
            "sections": questions_by_section(data), "topics": questions_by_topic(data),
            "subtopics": subtopic_frequency(data), "difficulty": difficulty_distribution(data)}


def pattern_signal(data: pd.DataFrame, section: str, topic: str, subtopic: str) -> dict[str, object]:
    """Return descriptive metadata context, never a future-question prediction."""
    scoped = data[(data["section"] == section) & (data["topic"] == topic) & (data["subtopic"] == subtopic)]
    return {
        "matching_metadata_records": int(len(scoped)),
        "difficulty_distribution": difficulty_distribution(scoped),
        "question_type_distribution": question_type_distribution(scoped),
        "common_concepts": sorted({concept for value in scoped["concepts"] for concept in value.split("; ") if concept}),
        "common_pattern_tags": sorted({tag for value in scoped["pattern_tags"] for tag in value.split("; ") if tag}),
        "interpretation": "Historical metadata is a pattern signal only; it does not predict future CAT questions.",
    }


def analysis_overview(data: pd.DataFrame) -> dict[str, object]:
    """Backward-compatible high-level metadata summary."""
    return {"total_questions": int(len(data)),
            "years": sorted(int(year) for year in data["year"].unique()) if not data.empty else [],
            "questions_by_section": questions_by_section(data),
            "questions_by_topic": questions_by_topic(data),
            "question_type_distribution": question_type_distribution(data)}
