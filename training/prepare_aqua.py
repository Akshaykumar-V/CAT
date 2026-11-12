"""Convert licensed AQuA-RAT rows into QA Algebra question-writing examples."""

import argparse
import json
import re
from pathlib import Path

ALGEBRA_CUE = re.compile(r"\b(?:equation|algebra|variable|solve for|value of [a-z]|integers?)\b", re.I)
OPTION = re.compile(r"^([A-E])\s*[).]\s*(.+)$")
INSTRUCTION = (
    "Create one QA Algebra multiple-choice practice question. "
    "Use four distinct options, exactly one correct answer, and a concise worked explanation. "
    "Return only JSON with question_text, options, correct_answer, explanation, "
    "section, topic, subtopic, difficulty, and question_type."
)


def convert(row: dict) -> dict | None:
    question = str(row.get("question", "")).strip()
    rationale = str(row.get("rationale", "")).strip()
    correct = str(row.get("correct", "")).strip().upper()
    if not ALGEBRA_CUE.search(question) or len(question) < 30 or not 40 <= len(rationale) <= 1800:
        return None
    parsed = [OPTION.match(str(option).strip()) for option in row.get("options", [])]
    if len(parsed) != 5 or any(match is None for match in parsed):
        return None
    choices = {match.group(1): match.group(2).strip() for match in parsed}
    if set(choices) != set("ABCDE") or correct not in choices or len(set(choices.values())) != 5:
        return None
    # Drop one wrong choice; AQuA-RAT has five, while this app requires four.
    removed = next(label for label in reversed("ABCDE") if label != correct)
    options = [choices[label] for label in "ABCDE" if label != removed]
    target = {
        "question_text": question,
        "options": options,
        "correct_answer": choices[correct],
        "explanation": rationale,
        "section": "QA",
        "topic": "Algebra",
        "subtopic": "Algebra",
        "difficulty": "Medium",
        "question_type": "MCQ",
    }
    return {"prompt": INSTRUCTION, "completion": json.dumps(target, ensure_ascii=False)}


def prepare(rows, output: Path, limit: int) -> int:
    output.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    seen = set()
    with output.open("w", encoding="utf-8") as file:
        for row in rows:
            example = convert(row)
            if example is None:
                continue
            question = json.loads(example["completion"])["question_text"]
            key = re.sub(r"\W+", " ", question.casefold()).strip()
            if key in seen:
                continue
            seen.add(key)
            file.write(json.dumps(example, ensure_ascii=False) + "\n")
            count += 1
            if count >= limit:
                break
    return count


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path("training/output"))
    parser.add_argument("--max-train", type=int, default=10000)
    args = parser.parse_args()
    from datasets import load_dataset  # Installed in the Colab runtime.

    source = load_dataset("deepmind/aqua_rat", "raw")
    for split, limit in (("train", args.max_train), ("validation", 500)):
        count = prepare(source[split], args.output_dir / f"{split}.jsonl", limit)
        print(f"{split}: {count} QA Algebra examples")
        if count == 0:
            raise RuntimeError(f"No usable {split} examples; inspect the source schema")


if __name__ == "__main__":
    main()
