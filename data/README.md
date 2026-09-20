# Data

This directory holds CAT previous-year-question (PYQ) metadata and any cleaned data files used for pattern analysis.

`sample_pyq_metadata.csv` is a small synthetic development dataset. It does not contain copyrighted CAT questions.

## PYQ metadata CSV format

Every CSV must include these columns:

```text
year,slot,section,topic,subtopic,difficulty,question_type,question_text,correct_answer,source
```

- `section` must be `VARC`, `DILR`, or `QA`.
- `difficulty` must be `Easy`, `Medium`, or `Hard`.
- Every field is required in the analysis CSV, including `question_text` and `correct_answer`.
