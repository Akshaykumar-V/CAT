# Analysis

The Pandas analysis module currently lives in `backend/app/analysis.py` so that the API can use it directly.

It imports metadata-only CSV files through `backend/app/analysis.py`. The importer reports missing columns, invalid rows, normalization, and duplicates without silently hiding rejected records.

The API reports section, topic, subtopic, slot, difficulty, question-type, estimated-time, concept, and pattern-tag distributions, plus year-over-year topic shares. Historical metadata is exposed as a pattern signal only; it is not a prediction of future CAT questions.

Metadata files must not contain question text, answer choices, or solution text unless separately licensed or explicitly supplied by the user.
