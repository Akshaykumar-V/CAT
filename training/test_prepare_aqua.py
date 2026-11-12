"""Conversion checks for the source's five-option answer format."""

import json
import unittest

from training.prepare_aqua import convert
from training.evaluate_qa import normalized_words, valid_question


class PrepareAquaTest(unittest.TestCase):
    def test_keeps_correct_answer_when_dropping_a_distractor(self):
        row = {
            "question": "For an integer x, solve for x when twice x plus three equals eleven.",
            "options": ["A)2", "B)3", "C)4", "D)5", "E)6"],
            "rationale": "Twice x plus three equals eleven, so twice x equals eight and x equals four.",
            "correct": "C",
        }
        result = convert(row)
        self.assertIsNotNone(result)
        target = json.loads(result["completion"])
        self.assertEqual(target["correct_answer"], "4")
        self.assertEqual(target["options"], ["2", "3", "4", "5"])

    def test_rejects_unlabelled_problem(self):
        row = {"question": "What is the answer?", "options": [], "rationale": "", "correct": "A"}
        self.assertIsNone(convert(row))

    def test_evaluation_rejects_wrong_answer_key(self):
        target = {
            "question_text": "Solve for x when two x equals eight.",
            "options": ["2", "3", "4", "5"],
            "correct_answer": "9",
            "explanation": "x equals four.",
            "section": "QA", "topic": "Algebra", "subtopic": "Algebra",
            "difficulty": "Medium", "question_type": "MCQ",
        }
        self.assertEqual(valid_question(json.dumps(target)), (False, "answer_missing_from_options"))

    def test_overlap_finds_repeated_six_word_phrase(self):
        self.assertTrue(normalized_words("The value of x is exactly four") &
                        normalized_words("Find why the value of x is exactly four today"))


if __name__ == "__main__":
    unittest.main()
