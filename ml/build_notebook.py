"""Write ml/taxsetu_narration_finetune.ipynb (the Google Colab notebook) from ml/narration_data.py and the training code below.
    python ml/build_notebook.py
Open it in Colab (File > Upload notebook), choose Runtime > Change runtime type > T4 GPU, then Runtime > Run all.
The last cell downloads taxsetu_narration_model.zip; unzip it into packages/agents/taxsetu_agents/models/narration/."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def code(src):
    return {"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [], "source": src.strip("\n").splitlines(keepends=True)}


def md(src):
    return {"cell_type": "markdown", "metadata": {}, "source": src.strip("\n").splitlines(keepends=True)}


INSTALL = "!pip -q install onnx onnxruntime tokenizers"

TRAIN = '''
import json, time, torch, numpy as np
from transformers import AutoTokenizer, AutoModelForSequenceClassification, get_linear_schedule_with_warmup
from sklearn.metrics import classification_report, f1_score
from narration_data import make, LABELS

SEED, BASE, EPOCHS, BATCH, LR, MAXLEN = 7, "prajjwal1/bert-mini", 3, 64, 3e-4, 64
torch.manual_seed(SEED)
train, test = make(seed=SEED, n_train=40000, n_test=4000)
val, train = train[:2000], train[2000:]            # val: same phrases as training (a sanity check); test: phrases never seen in training
label2id = {l: i for i, l in enumerate(LABELS)}
tok = AutoTokenizer.from_pretrained("bert-base-uncased")      # prajjwal1/bert-mini ships no tokenizer files; it uses the bert-base-uncased vocabulary
dev = "cuda" if torch.cuda.is_available() else "cpu"
print("device:", dev, "| train", len(train), "val", len(val), "test", len(test))
from transformers import BertConfig, BertForSequenceClassification
cfg = BertConfig(vocab_size=30522, hidden_size=256, num_hidden_layers=4, num_attention_heads=4, intermediate_size=1024, num_labels=len(LABELS),
                 id2label=dict(enumerate(LABELS)), label2id=label2id)      # bert-mini's shape; its repo's config.json has no model_type, so the Auto classes cannot read it
try:
    model, PRETRAINED = BertForSequenceClassification.from_pretrained(BASE, config=cfg), True
except Exception as exc:
    print("could not load the pretrained weights; training from random initialisation:", repr(exc)[:300])
    model, PRETRAINED = BertForSequenceClassification(cfg), False
model = model.to(dev)
print("pretrained weights loaded:", PRETRAINED)

def encode(rows):
    e = tok([r["text"] for r in rows], truncation=True, max_length=MAXLEN, padding=True, return_tensors="pt")
    return {k: v.to(dev) for k, v in e.items()}, torch.tensor([label2id[r["label"]] for r in rows]).to(dev)

def predict(rows):
    model.eval(); out = []
    with torch.no_grad():
        for i in range(0, len(rows), 256):
            x, _ = encode(rows[i:i + 256]); out += model(**x).logits.argmax(-1).tolist()
    return out

opt = torch.optim.AdamW(model.parameters(), lr=LR, weight_decay=0.01)
steps = EPOCHS * ((len(train) + BATCH - 1) // BATCH)
sched = get_linear_schedule_with_warmup(opt, int(0.06 * steps), steps)
t0 = time.time()
for epoch in range(EPOCHS):
    model.train(); order = np.random.RandomState(SEED + epoch).permutation(len(train)); total = 0.0
    for i in range(0, len(train), BATCH):
        x, y = encode([train[j] for j in order[i:i + BATCH]])
        loss = torch.nn.functional.cross_entropy(model(**x).logits, y)
        loss.backward(); torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0); opt.step(); sched.step(); opt.zero_grad(); total += loss.item()
        if (i // BATCH) % 100 == 0: print(f"  epoch {epoch + 1} step {i // BATCH}/{len(train) // BATCH}  loss {loss.item():.4f}  ({time.time() - t0:.0f}s)", flush=True)
    acc = np.mean([LABELS[p] == r["label"] for p, r in zip(predict(val), val)])
    print(f"epoch {epoch + 1}/{EPOCHS}  loss {total / (len(train) / BATCH):.4f}  val accuracy {acc:.4f}  ({time.time() - t0:.0f}s)")

pred = [LABELS[p] for p in predict(test)]
gold = [r["label"] for r in test]
fp32_acc = float(np.mean([p == g for p, g in zip(pred, gold)]))
print("\\nHELD-OUT test accuracy (fp32):", round(fp32_acc, 4), "| macro-F1:", round(f1_score(gold, pred, average="macro"), 4))
print(classification_report(gold, pred, digits=3))
'''

EXPORT = '''
import os, zipfile, onnxruntime as ort
from onnxruntime.quantization import quantize_dynamic, QuantType
from tokenizers import Tokenizer

OUT = "taxsetu_narration_model"; os.makedirs(OUT, exist_ok=True)
model.eval().cpu()
class Wrap(torch.nn.Module):
    def __init__(self, m): super().__init__(); self.m = m
    def forward(self, input_ids, attention_mask, token_type_ids): return self.m(input_ids=input_ids, attention_mask=attention_mask, token_type_ids=token_type_ids).logits
e = tok(["out | UPI/DR/1234/BESCOM"], return_tensors="pt")
args = (e["input_ids"], e["attention_mask"], e["token_type_ids"])
kw = dict(input_names=["input_ids", "attention_mask", "token_type_ids"], output_names=["logits"], opset_version=17,
          dynamic_axes={k: {0: "batch", 1: "seq"} for k in ["input_ids", "attention_mask", "token_type_ids"]} | {"logits": {0: "batch"}})
try:
    torch.onnx.export(Wrap(model), args, "model_fp32.onnx", dynamo=False, **kw)
except TypeError:
    torch.onnx.export(Wrap(model), args, "model_fp32.onnx", **kw)
quantize_dynamic("model_fp32.onnx", f"{OUT}/model_int8.onnx", weight_type=QuantType.QInt8)
tok.save_pretrained(OUT)
for f in os.listdir(OUT):
    if f not in ("tokenizer.json", "model_int8.onnx"): os.remove(f"{OUT}/{f}")
json.dump(LABELS, open(f"{OUT}/labels.json", "w"))

# Re-test the EXPORTED int8 model through exactly the code path the API uses (tokenizers + onnxruntime, no torch, no transformers).
tk = Tokenizer.from_file(f"{OUT}/tokenizer.json"); tk.enable_truncation(MAXLEN); tk.enable_padding()
sess = ort.InferenceSession(f"{OUT}/model_int8.onnx", providers=["CPUExecutionProvider"])
def onnx_predict(texts):
    out = []
    for i in range(0, len(texts), 128):
        enc = tk.encode_batch(texts[i:i + 128])
        feed = {"input_ids": np.array([x.ids for x in enc], dtype=np.int64), "attention_mask": np.array([x.attention_mask for x in enc], dtype=np.int64),
                "token_type_ids": np.array([x.type_ids for x in enc], dtype=np.int64)}
        out.append(sess.run(None, feed)[0])
    return np.concatenate(out)
logits = onnx_predict([r["text"] for r in test])
int8_pred = [LABELS[i] for i in logits.argmax(-1)]
int8_acc = float(np.mean([p == g for p, g in zip(int8_pred, gold)]))
agree = float(np.mean([a == b for a, b in zip(int8_pred, pred)]))
p = np.exp(logits - logits.max(-1, keepdims=True)); p /= p.sum(-1, keepdims=True); conf = p.max(-1)
rows = []
for th in (0.5, 0.6, 0.7, 0.8, 0.9):
    keep = conf >= th
    rows.append({"threshold": th, "answered": float(keep.mean()), "accuracy_when_answered": float(np.mean([int8_pred[i] == gold[i] for i in np.where(keep)[0]])) if keep.any() else None})
metrics = {"base_model": BASE, "pretrained_weights_loaded": PRETRAINED, "labels": LABELS, "epochs": EPOCHS, "train_rows": len(train), "test_rows": len(test), "test_is": "synthetic, phrases never seen in training",
           "fp32_test_accuracy": fp32_acc, "int8_test_accuracy": int8_acc, "int8_agrees_with_fp32": agree, "macro_f1_fp32": float(f1_score(gold, pred, average="macro")),
           "confidence_table": rows, "model_bytes": os.path.getsize(f"{OUT}/model_int8.onnx")}
json.dump(metrics, open(f"{OUT}/metrics.json", "w"), indent=1)
print(json.dumps({k: v for k, v in metrics.items() if k != "labels"}, indent=1))
with zipfile.ZipFile("taxsetu_narration_model.zip", "w", zipfile.ZIP_DEFLATED) as z:
    for f in os.listdir(OUT): z.write(f"{OUT}/{f}", f)
print("zip bytes:", os.path.getsize("taxsetu_narration_model.zip"))
'''

DOWNLOAD = '''
from google.colab import files
files.download("taxsetu_narration_model.zip")
'''


def main():
    cells = [
        md("# Kosh AI: bank-narration classifier\nFine-tunes a small BERT (`prajjwal1/bert-mini`, ~11M parameters) to file a bank-statement row under a ledger head, "
           "exports it as an int8 ONNX model, and re-tests the exported file the way the API will run it.\n\n"
           "**Data:** synthetic (`narration_data.py`); no customer data. The test set uses phrases held out of training. Retrain with real, labelled narrations before relying on it.\n\n"
           "Runtime > Change runtime type > T4 GPU, then Runtime > Run all."),
        code(INSTALL),
        code("%%writefile narration_data.py\n" + (HERE / "narration_data.py").read_text(encoding="utf-8")),
        code(TRAIN),
        code(EXPORT),
        code(DOWNLOAD),
    ]
    nb = {"cells": cells, "metadata": {"accelerator": "GPU", "colab": {"provenance": [], "gpuType": "T4"}, "kernelspec": {"name": "python3", "display_name": "Python 3"},
                                       "language_info": {"name": "python"}}, "nbformat": 4, "nbformat_minor": 5}
    path = HERE / "taxsetu_narration_finetune.ipynb"
    path.write_text(json.dumps(nb, indent=1), encoding="utf-8")
    print("wrote", path)


if __name__ == "__main__":
    main()
