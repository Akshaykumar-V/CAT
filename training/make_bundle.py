"""Package the scripts for upload into the Colab notebook."""

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


root = Path(__file__).resolve().parents[1]
with ZipFile(root / "training_bundle.zip", "w", compression=ZIP_DEFLATED) as bundle:
    for filename in ("README.md", "prepare_aqua.py", "train_qa_lora.py", "evaluate_qa.py"):
        file = root / "training" / filename
        bundle.write(file, arcname=f"training/{filename}")
