# QA Algebra fine-tuning experiment

This workflow fine-tunes a LoRA adapter for [Qwen2.5-0.5B-Instruct](https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct) on the [DeepMind AQuA-RAT](https://huggingface.co/datasets/deepmind/aqua_rat) algebra word-problem dataset. Both declare Apache 2.0 licenses. AQuA-RAT is **not CAT exam data**. This experiment covers QA Algebra only.

In a Google Colab GPU runtime, with this project available in the runtime:

```bash
pip install -U datasets transformers trl peft accelerate
python training/prepare_aqua.py --max-train 10000
python training/train_qa_lora.py
python -m training.evaluate_qa --samples 20
```

`prepare_aqua.py` downloads the public dataset, keeps algebra-cue questions with four distinct converted options, and writes `training/output/train.jsonl` and `validation.jsonl`. The official validation split is not used for training. The training script saves the adapter in `training/adapter/` and reports validation loss. Keep the source license and attribution with any redistributed training data or model.

The dataset has no CAT difficulty labels; converted examples use `Medium` as a placeholder. AQuA-RAT rationales can contain mistakes. `evaluate_qa.py` reports JSON/schema failures and six-word overlap with training questions; it cannot verify mathematical correctness. Before using the adapter in the app, manually review generated questions and answers, check for near-copies of training questions, and verify a separate inference endpoint can serve the adapter. Render's free CPU service is not a GPU training or model-serving environment. The current app continues using its template/provider pipeline until that review is complete.
