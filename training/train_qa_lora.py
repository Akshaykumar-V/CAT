"""Train a small QA question-writing LoRA adapter on a Colab GPU."""

import argparse
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=Path("training/output"))
    parser.add_argument("--output-dir", type=Path, default=Path("training/adapter"))
    parser.add_argument("--model", default="Qwen/Qwen2.5-0.5B-Instruct")
    args = parser.parse_args()

    import torch
    from datasets import load_dataset
    from peft import LoraConfig, TaskType
    from transformers import AutoTokenizer
    from trl import SFTConfig, SFTTrainer

    if not torch.cuda.is_available():
        raise RuntimeError("A CUDA GPU is required; select a GPU runtime in Colab")
    train_path = args.data_dir / "train.jsonl"
    validation_path = args.data_dir / "validation.jsonl"
    if not train_path.is_file() or not validation_path.is_file():
        raise FileNotFoundError("Run prepare_aqua.py before training")
    data = load_dataset("json", data_files={"train": str(train_path), "validation": str(validation_path)})
    tokenizer = AutoTokenizer.from_pretrained(args.model)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    config = SFTConfig(
        output_dir=str(args.output_dir),
        max_length=1024,
        completion_only_loss=True,
        per_device_train_batch_size=2,
        per_device_eval_batch_size=2,
        gradient_accumulation_steps=8,
        num_train_epochs=1,
        learning_rate=1e-4,
        fp16=True,
        eval_strategy="epoch",
        save_strategy="epoch",
        save_total_limit=1,
        report_to="none",
    )
    trainer = SFTTrainer(
        model=args.model,
        args=config,
        train_dataset=data["train"],
        eval_dataset=data["validation"],
        processing_class=tokenizer,
        peft_config=LoraConfig(r=8, lora_alpha=16, lora_dropout=0.05,
                               target_modules=["q_proj", "v_proj"], task_type=TaskType.CAUSAL_LM),
    )
    trainer.train()
    print("validation:", trainer.evaluate())
    trainer.save_model(str(args.output_dir))
    tokenizer.save_pretrained(str(args.output_dir))


if __name__ == "__main__":
    main()
