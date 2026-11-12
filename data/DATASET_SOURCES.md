# Dataset research for CAT Prep AI

The current application does not train a machine-learning model. It uses a synthetic metadata CSV for pattern charts and optionally calls a configured LLM for original question generation. Adding a public dataset must be tied to one of two distinct workflows: metadata analysis or model fine-tuning.

## Candidate sources

| Source | License shown by publisher | Suitable use | Limit |
| --- | --- | --- | --- |
| [ExamBench](https://huggingface.co/datasets/169Pi/exambench) | Apache 2.0 | Fine-tuning or evaluating broad exam reasoning after QA and verbal filtering | Synthetic, broad exam corpus; not verified CAT papers or year/slot metadata |
| [AQuA-RAT](https://huggingface.co/datasets/deepmind/aqua_rat) | Apache 2.0, [original license](https://github.com/google-deepmind/AQuA/blob/master/LICENSE) | First QA Algebra question-generation experiment, with options and rationales | Five-option algebra word problems, not CAT papers; rationale quality needs review |
| [LogiHard-2K](https://huggingface.co/datasets/LogiHard/LogiHard-2K) | CC BY 4.0 | Logical reasoning evaluation and difficulty calibration, with attribution | Mixed languages and exam sources; not full CAT coverage or year/slot metadata |
| [CAT Quant PYQ](https://github.com/r4plh/quant-pyq) | No dataset license found in the repository | Reference for topic and year/slot research | Do not copy its question text into a training set without rights clarification |

## Decision before use

The first selected training source is AQuA-RAT, limited to QA Algebra examples. `training/prepare_aqua.py` converts its five options to the application's four-option format and leaves the original validation split out of training. The converted examples use `Medium` as a placeholder label because the source does not supply CAT difficulty labels. This adapter must not be advertised as trained on real CAT papers or as covering VARC and DILR.

For the planned Render free demo, keep using the existing original template questions until the adapter passes generated-question review and has a separate inference endpoint. Do not present synthetic metadata as real CAT historical data. A metadata-only import needs real year, slot, section, topic, and difficulty labels; none of the licensed candidates above directly provides the application's required CSV schema.
