"""Smoke-evaluate a trained adapter's JSON and overlap with training questions."""

import argparse
import json
import re
from pathlib import Path

from training.prepare_aqua import INSTRUCTION


def normalized_words(text: str) -> set[tuple[str, ...]]:
    words = re.findall(r"[a-z0-9]+", text.casefold())
    return set(zip(*(words[index:] for index in range(6)))) if len(words) >= 6 else set()


def valid_question(text: str) -> tuple[bool, str]:
    try:
        item = json.loads(text)
    except json.JSONDecodeError:
        return False, "invalid_json"
    if not isinstance(item, dict):
        return False, "not_object"
    options = item.get("options")
    if not isinstance(options, list) or len(options) != 4 or len(set(map(str, options))) != 4:
        return False, "invalid_options"
    if item.get("correct_answer") not in options:
        return False, "answer_missing_from_options"
    if not str(item.get("question_text", "")).strip() or not str(item.get("explanation", "")).strip():
        return False, "missing_question_or_explanation"
    if (item.get("section"), item.get("topic"), item.get("subtopic"), item.get("difficulty"), item.get("question_type")) != ("QA", "Algebra", "Algebra", "Medium", "MCQ"):
        return False, "invalid_metadata"
    return True, "ok"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--adapter", type=Path, default=Path("training/adapter"))
    parser.add_argument("--train-data", type=Path, default=Path("training/output/train.jsonl"))
    parser.add_argument("--samples", type=int, default=20)
    args = parser.parse_args()
    import torch
    from peft import AutoPeftModelForCausalLM
    from transformers import AutoTokenizer

    model = AutoPeftModelForCausalLM.from_pretrained(str(args.adapter), device_map="auto")
    tokenizer = AutoTokenizer.from_pretrained(str(args.adapter))
    source_ngrams = set()
    with args.train_data.open(encoding="utf-8") as file:
        for line in file:
            source_ngrams.update(normalized_words(json.loads(json.loads(line)["completion"])["question_text"]))
    counts = {}
    for _ in range(args.samples):
        inputs = tokenizer(INSTRUCTION, return_tensors="pt").to(model.device)
        with torch.no_grad():
            output = model.generate(**inputs, max_new_tokens=512, do_sample=True, temperature=0.8)
        text = tokenizer.decode(output[0][inputs["input_ids"].shape[-1]:], skip_special_tokens=True).strip()
        valid, reason = valid_question(text)
        counts[reason] = counts.get(reason, 0) + 1
        if valid:
            question = json.loads(text)["question_text"]
            if normalized_words(question) & source_ngrams:
                counts["overlaps_training_question"] = counts.get("overlaps_training_question", 0) + 1
    print(json.dumps({"samples": args.samples, "counts": counts}, indent=2))


if __name__ == "__main__":
    main()
