# Data

This directory holds CAT previous-year-question (PYQ) metadata and any cleaned data files used for pattern analysis.

`sample_pyq_metadata.csv` is a small synthetic development dataset. It does not contain copyrighted CAT questions.

## PYQ metadata CSV format

Every metadata CSV must include these columns:

```text
year,slot,section,topic,subtopic,question_type,difficulty,concepts,estimated_time_seconds,pattern_tags,source_reference
```

- `section` must be `VARC`, `DILR`, or `QA`.
- `difficulty` must be `Easy`, `Medium`, or `Hard`.
- `concepts` and `pattern_tags` may contain semicolon-separated values.
- Metadata files must not contain question text, answer choices, or solution text unless separately licensed or explicitly supplied by the user.
