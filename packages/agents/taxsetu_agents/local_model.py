"""A small bank-narration classifier that runs on the server's CPU: no API key, no network, no data leaves the deployment.

Trained in Google Colab by ml/taxsetu_narration_finetune.ipynb (a fine-tuned BERT-mini exported to int8 ONNX).
It plugs into the same two hooks as ClaudeLlm: suggest_ledgers (rows a person must check) and extract_entry (the ledger head of a typed sentence).
Like the Claude path it only PROPOSES: a suggestion must be one of the business's real ledgers, is flagged AI_SUGGESTED and still needs a person.
Reading a supplier-bill photo is not something this model does; that stays with ClaudeLlm (needs a key).
Optional dependencies: `pip install onnxruntime tokenizers` (without them, or without the model files, everything falls back to the rules).
"""
import json
import os
from pathlib import Path

DEFAULT_DIR = Path(__file__).parent / "models" / "narration"
THRESHOLD = float(os.environ.get("TAXSETU_LOCAL_THRESHOLD", "0.7"))
ABSTAIN = "Other"


class LocalNarrationModel:
    def __init__(self, directory):
        import numpy as np
        import onnxruntime as ort
        from tokenizers import Tokenizer
        d = Path(directory)
        self.np = np
        self.labels = json.loads((d / "labels.json").read_text(encoding="utf-8"))
        self.tok = Tokenizer.from_file(str(d / "tokenizer.json"))
        self.tok.enable_truncation(64)
        self.tok.enable_padding()
        self.sess = ort.InferenceSession(str(d / "model_int8.onnx"), providers=["CPUExecutionProvider"])
        self.names = {i.name for i in self.sess.get_inputs()}

    def predict(self, texts: list) -> list:
        """[(label, probability)] for each text."""
        np = self.np
        out = []
        for i in range(0, len(texts), 64):
            enc = self.tok.encode_batch([str(t)[:300] for t in texts[i:i + 64]])
            feed = {"input_ids": np.array([e.ids for e in enc], dtype=np.int64), "attention_mask": np.array([e.attention_mask for e in enc], dtype=np.int64),
                    "token_type_ids": np.array([e.type_ids for e in enc], dtype=np.int64)}
            logits = self.sess.run(None, {k: v for k, v in feed.items() if k in self.names})[0]
            p = np.exp(logits - logits.max(-1, keepdims=True))
            p /= p.sum(-1, keepdims=True)
            out += [(self.labels[int(j)], float(p[n, j])) for n, j in enumerate(p.argmax(-1))]
        return out


class LocalLlm:
    """Same shape as ClaudeLlm for the two things it can do. `model` needs only predict(list[str]) -> [(label, probability)]."""
    provider = "local"

    def __init__(self, model, threshold: float = THRESHOLD):
        self.model, self.threshold = model, threshold

    def _confident(self, texts: list) -> list:
        return [(label, p) if label != ABSTAIN and p >= self.threshold else None for label, p in self.model.predict(texts)]

    def suggest_ledgers(self, rows: list, ledgers: list) -> dict:
        """{row index: (ledger, reason)}. A row is skipped unless the model is confident AND its label is one of the allowed ledgers."""
        if not rows or not ledgers:
            return {}
        allowed = set(ledgers)
        texts = [("in | " if r.get("direction") == "money in" else "out | ") + str(r.get("narration", "")) for r in rows]
        out = {}
        for row, got in zip(rows, self._confident(texts)):
            if got and got[0] in allowed:
                out[row["i"]] = (got[0], f"on-server model: looks like {got[0]} ({got[1]:.0%} sure)")
        return out

    def extract_entry(self, text: str) -> dict:
        """Only the ledger head of a typed sentence; amount, date and party stay with the rules."""
        got = self._confident(["out | " + str(text)[:300]])[0]
        return {"head": got[0]} if got else {}

    def extract_bill(self, text: str = "", image: bytes | None = None, media_type: str = "image/jpeg") -> dict:
        raise NotImplementedError("reading a bill photo needs the Claude API key")


def local_llm_from_env():
    """A LocalLlm when the model files and onnxruntime/tokenizers are present, else None. TAXSETU_LOCAL_MODEL=off disables; =<dir> points elsewhere."""
    setting = os.environ.get("TAXSETU_LOCAL_MODEL", "")
    if setting.lower() in ("off", "0", "false", "no"):
        return None
    directory = Path(setting) if setting else DEFAULT_DIR
    if not all((directory / f).exists() for f in ("model_int8.onnx", "tokenizer.json", "labels.json")):
        return None
    try:
        return LocalLlm(LocalNarrationModel(directory))
    except Exception:
        return None
