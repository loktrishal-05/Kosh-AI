"""LLM seam. The model only EXTRACTS and DRAFTS; every number it emits is untrusted and is re-derived or checked by the engine.
ponytail: StubLlm is deterministic (key: value parsing + templates) so the whole pipeline is testable offline. A real adapter
(Claude/Gemini vision extractor + drafter, behind this same two-method Protocol) needs an API key and is the next integration."""
import re
from decimal import Decimal, InvalidOperation
from typing import Protocol

_NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")


class Llm(Protocol):
    def extract_invoice(self, text: str) -> dict: ...
    def draft(self, kind: str, facts: dict) -> str: ...


def grounded(text: str, facts: dict) -> bool:
    """Every number in LLM prose must equal a fact we supplied (blocks hallucinated figures in owner-facing summaries)."""
    allowed = set()
    for v in facts.values():
        try:
            allowed.add(Decimal(str(v)))
        except InvalidOperation:
            pass
    return all(Decimal(n.replace(",", "")) in allowed for n in _NUM.findall(text))


_SUMMARY = {   # {out} {itc} {net}
    "en": "Your tax summary: output tax Rs {out}, ITC claimed Rs {itc}, net cash payable Rs {net}.",
    "hi": "आपका कर सारांश: आउटपुट टैक्स ₹{out}, क्लेम किया गया आईटीसी ₹{itc}, नेट नकद देय ₹{net}।",
    "ta": "உங்கள் வரி சுருக்கம்: வெளியீட்டு வரி ₹{out}, ITC ₹{itc}, செலுத்த வேண்டிய நிகர தொகை ₹{net}.",
}


class StubLlm:
    KEYS = ("supplier_gstin", "invoice_no", "invoice_date", "hsn", "description", "taxable", "rate")

    def extract_invoice(self, text: str) -> dict:
        out = {}
        for line in text.splitlines():
            k, _, v = line.partition(":")
            if k.strip().lower() in self.KEYS:
                out[k.strip().lower()] = v.strip()
        return out

    def draft(self, kind: str, facts: dict) -> str:
        if kind == "vernacular_summary":
            return _SUMMARY.get(facts.get("locale"), _SUMMARY["en"]).format(**{k: facts[k] for k in ("out", "itc", "net")})
        raise ValueError(f"unknown draft kind {kind}")


def template_summary(facts: dict) -> str:
    return _SUMMARY.get(facts.get("locale"), _SUMMARY["en"]).format(**{k: facts[k] for k in ("out", "itc", "net")})
