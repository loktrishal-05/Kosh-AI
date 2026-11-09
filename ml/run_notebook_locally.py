"""Run the Colab notebook's code cells on this machine (same code, same data, same exports) when Colab will not give a runtime.
    python ml/run_notebook_locally.py <scratch folder>
Needs torch, transformers, onnx, onnxruntime, tokenizers, scikit-learn. Writes <scratch folder>/taxsetu_narration_model.zip."""
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
work = Path(sys.argv[1] if len(sys.argv) > 1 else "ml_run").resolve()
work.mkdir(parents=True, exist_ok=True)
os.chdir(work)
sys.path.insert(0, str(HERE))
ns = {"__name__": "__main__"}
for cell in json.loads((HERE / "taxsetu_narration_finetune.ipynb").read_text(encoding="utf-8"))["cells"]:
    src = "".join(cell["source"])
    if cell["cell_type"] != "code" or src.startswith(("!pip", "%%writefile")) or "google.colab" in src:
        continue
    exec(compile(src, "<notebook cell>", "exec"), ns)
