"""Pandas helpers for analysing CAT PYQ metadata."""

from pathlib import Path

import pandas as pd


REQUIRED_COLUMNS = [
    "year",
    "slot",
    "section",
    "topic",
    "subtopic",
    "difficulty",
    "question_type",
    "question_text",
    "correct_answer",
    "source",
]
VALID_SECTIONS = {"VARC", "DILR", "QA"}
VALID_DIFFICULTIES = {"Easy", "Medium", "Hard"}
DEFAULT_DATA_PATH = Path(__file__).resolve().parents[2] / "data" / "sample_pyq_metadata.csv"


class DataValidationError(ValueError):
    """Raised when a PYQ metadata CSV does not match the expected format."""


def load_pyq_data(csv_path: str | Path = DEFAULT_DATA_PATH) -> pd.DataFrame:
    """Load and validate PYQ metadata from a CSV file."""
    path = Path(csv_path)
    if not path.exists():
        raise DataValidationError(f"PYQ metadata file was not found: {path}")

    try:
        data = pd.read_csv(path)
    except (OSError, pd.errors.ParserError) as error:
        raise DataValidationError(f"Could not read PYQ metadata CSV: {error}") from error

    return validate_pyq_data(data)


def validate_pyq_data(data: pd.DataFrame) -> pd.DataFrame:
    """Validate required fields and return a cleaned copy of the metadata."""
    missing_columns = sorted(set(REQUIRED_COLUMNS) - set(data.columns))
    if missing_columns:
        raise DataValidationError(
            "Missing required columns: " + ", ".join(missing_columns)
        )
    if data.empty:
        raise DataValidationError("PYQ metadata must contain at least one question.")

    cleaned = data[REQUIRED_COLUMNS].copy()
    text_columns = [column for column in REQUIRED_COLUMNS if column != "year"]
    for column in text_columns:
        if cleaned[column].isna().any() or cleaned[column].astype(str).str.strip().eq("").any():
            raise DataValidationError(f"Column '{column}' contains missing values.")
        cleaned[column] = cleaned[column].astype(str).str.strip()

    years = pd.to_numeric(cleaned["year"], errors="coerce")
    if years.isna().any() or (years % 1 != 0).any():
        raise DataValidationError("Column 'year' must contain whole numbers.")
    cleaned["year"] = years.astype(int)

    invalid_sections = sorted(set(cleaned["section"]) - VALID_SECTIONS)
    if invalid_sections:
        raise DataValidationError(
            "Invalid section values: " + ", ".join(invalid_sections)
        )

    invalid_difficulties = sorted(set(cleaned["difficulty"]) - VALID_DIFFICULTIES)
    if invalid_difficulties:
        raise DataValidationError(
            "Invalid difficulty values: " + ", ".join(invalid_difficulties)
        )

    return cleaned


def _count_by(data: pd.DataFrame, column: str) -> dict[str, int]:
    """Return a consistently ordered count for a categorical column."""
    counts = data.groupby(column).size().sort_index()
    return {str(key): int(value) for key, value in counts.items()}


def questions_by_section(data: pd.DataFrame) -> dict[str, int]:
    """Count questions in each CAT section."""
    return _count_by(data, "section")


def questions_by_topic(data: pd.DataFrame) -> dict[str, int]:
    """Count questions for each topic."""
    return _count_by(data, "topic")


def topic_frequency_by_year(data: pd.DataFrame) -> list[dict[str, int | str]]:
    """Count every topic for each year in the dataset."""
    grouped = data.groupby(["year", "topic"]).size().reset_index(name="question_count")
    grouped = grouped.sort_values(["year", "topic"])
    return [
        {
            "year": int(row.year),
            "topic": str(row.topic),
            "question_count": int(row.question_count),
        }
        for row in grouped.itertuples(index=False)
    ]


def difficulty_distribution(data: pd.DataFrame) -> dict[str, int]:
    """Count questions by difficulty."""
    return _count_by(data, "difficulty")


def section_difficulty_distribution(data: pd.DataFrame) -> dict[str, dict[str, int]]:
    """Count difficulty levels within each section."""
    result: dict[str, dict[str, int]] = {}
    for section, section_data in data.groupby("section"):
        result[str(section)] = _count_by(section_data, "difficulty")
    return result


def question_type_distribution(data: pd.DataFrame) -> dict[str, int]:
    """Count questions by their question type."""
    return _count_by(data, "question_type")


def topic_trends(data: pd.DataFrame) -> list[dict[str, int | str]]:
    """Return per-year topic counts, which can be plotted as trends later."""
    return topic_frequency_by_year(data)


def analysis_overview(data: pd.DataFrame) -> dict[str, object]:
    """Return a compact summary of the loaded PYQ metadata."""
    return {
        "total_questions": int(len(data)),
        "years": sorted(int(year) for year in data["year"].unique()),
        "questions_by_section": questions_by_section(data),
        "questions_by_topic": questions_by_topic(data),
        "question_type_distribution": question_type_distribution(data),
    }
