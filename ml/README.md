# On-server narration model

A small BERT (`prajjwal1/bert-mini`, about 11M parameters) fine-tuned to file a bank-statement row under a ledger head (Rent Paid, Electricity Charges, Bank Charges, and so on, or "Other").
It runs on the server's CPU as an int8 ONNX file (11 MB) with no API key and no network. It is **opt-in**: set `TAXSETU_LOCAL_MODEL=<directory>` (for example `ml/artifacts/narration_v1`)
and install `onnxruntime tokenizers`. Claude is still used first when `ANTHROPIC_API_KEY` is set. It cannot read bill photos.

## How good is it? (measured, not hoped)
Trained on **synthetic** narrations only (`narration_data.py`; no real customer data exists in this project). The test set uses phrases held out of training.

| | |
|---|---|
| Phrases seen in training | 99.8% right |
| **Phrases never seen** (the number that matters) | **75.9% right** overall |
| At the default confidence threshold of 0.9 | answers 84% of rows, **86% of those right** |
| Strong classes | rent, interest paid/received, sales, professional fees, stationery, fuel and travel (93-100%) |
| Weak classes | telephone/internet (47%), office expenses (50%), insurance (52%), bank charges (54%), salary (64%); **personal spending ("Other") only 4%** |

It learns the vocabulary it was shown and fails on words it was not: "SBI GENERAL" was filed as electricity, "cash handling charges" as repairs, and a grocery payment as rent at 100% confidence.
Its confidence scores are over-confident on unfamiliar wording. So: every suggestion is flagged `AI_SUGGESTED`, capped at 0.6 confidence and still needs a person; do not use it to post anything unchecked.

## Making it good
Train on real, labelled bank narrations from the organisation (a few thousand rows is a start) in place of, or mixed with, `narration_data.py`; keep a test set of narrations from different businesses than the training set.
`python ml/build_notebook.py` writes `taxsetu_narration_finetune.ipynb` (Colab: File > Upload notebook, Runtime > T4 GPU, Run all; the last cell downloads the zip). `python ml/run_notebook_locally.py <folder>` runs the same code on a laptop
(about 15 minutes for 3 epochs on 12 CPU cores). Unzip into a new `ml/artifacts/<name>/`; `tests/agents/test_local_model.py` checks the stored `metrics.json` against a floor.

How the shipped artifact was made: the notebook was uploaded to Colab, which surfaced two real bugs (the bert-mini repo has no tokenizer files and no `model_type`), then the same code was run locally because Colab was slow to allocate a runtime.
