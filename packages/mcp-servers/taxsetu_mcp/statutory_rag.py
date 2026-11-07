"""mcp-server-statutory-rag: effective-dated statute lookup. Agents may cite ONLY ids returned from here (anti-hallucination, report s7).
ponytail: keyword-overlap ranking over a tiny in-code corpus; replace with pgvector + BM25 over the signed corpus. Texts are
one-line paraphrases for retrieval, not legal text - a CA must verify before anything is filed."""
import re
from datetime import date

from .core import Server, ToolError

FOREVER = date(9999, 12, 31)
# (id, domain, valid_from, valid_to, title/gist)
CORPUS = [
    ("CBIC-64/38/2018-GST", "gst", date(2018, 9, 14), FOREVER,
     "Circular 64/38/2018-GST: clerical error in Part A or Part B of e-way bill (vehicle number, PIN code) with valid invoice - "
     "penalty Rs 500 CGST plus Rs 500 SGST under section 125, not 200 percent under section 129"),
    ("CGST-s17(5)", "gst", date(2017, 7, 1), FOREVER, "Section 17(5) CGST blocked input tax credit restaurant food motor vehicles"),
    ("CGST-s16(2)(aa)", "gst", date(2022, 1, 1), FOREVER, "Section 16(2)(aa) CGST ITC only if invoice appears in GSTR-2B"),
    ("CGST-r37", "gst", date(2017, 7, 1), FOREVER, "Rule 37 CGST reverse ITC if supplier not paid within 180 days"),
    ("CGST-s47", "gst", date(2017, 7, 1), FOREVER, "Section 47 CGST late fee for delayed GSTR-1 GSTR-3B"),
    ("CGST-s50", "gst", date(2017, 7, 1), FOREVER, "Section 50 CGST interest on delayed payment of tax"),
    ("CGST-s129", "gst", date(2017, 7, 1), FOREVER, "Section 129 CGST detention seizure of goods in transit penalty"),
    ("CGST-s125", "gst", date(2017, 7, 1), FOREVER, "Section 125 CGST general penalty"),
    ("CGST-r138(10)", "gst", date(2018, 4, 1), FOREVER, "Rule 138(10) e-way bill validity one day per 200 km"),
    ("ITA-s44AD", "incometax", date(2016, 4, 1), date(2023, 3, 31),
     "Section 44AD presumptive taxation turnover limit Rs 2 crore eligible business"),
    ("ITA-s44AD", "incometax", date(2023, 4, 1), FOREVER,
     "Section 44AD presumptive taxation turnover limit Rs 3 crore when cash receipts do not exceed 5 percent"),
    ("ITA-s44ADA", "incometax", date(2016, 4, 1), date(2023, 3, 31), "Section 44ADA professionals gross receipts limit Rs 50 lakh"),
    ("ITA-s44ADA", "incometax", date(2023, 4, 1), FOREVER,
     "Section 44ADA professionals gross receipts limit Rs 75 lakh when cash receipts do not exceed 5 percent"),
    ("ITA-s119(2)(b)", "incometax", date(1961, 4, 1), FOREVER, "Section 119(2)(b) condonation of delay refund claim genuine hardship"),
]
RATES: dict = {}    # (hsn_prefix) -> [(valid_from, valid_to, rate_pct)] ; intentionally empty: tax rates must come from the signed corpus


def _toks(s: str) -> set:
    return set(re.findall(r"[a-z0-9]+", s.lower()))


def effective(cid: str, on: date) -> dict:
    for i, dom, a, b, text in CORPUS:
        if i == cid and a <= on <= b:
            return {"id": i, "domain": dom, "valid_from": a, "valid_to": b, "text": text}
    raise ToolError(f"{cid} not in corpus (or not in force on {on}) - do not cite")


def search(query: str, on: date, domain: str | None = None, k: int = 3) -> list:
    q = _toks(query)
    hits = [(len(q & _toks(f"{i} {t}")), i, dom, a, b, t) for i, dom, a, b, t in CORPUS
            if a <= on <= b and (not domain or dom == domain)]
    return [{"id": i, "domain": dom, "valid_from": a, "valid_to": b, "text": t, "score": s}
            for s, i, dom, a, b, t in sorted(hits, key=lambda h: -h[0])[:k] if s > 0]


def build(rates: dict | None = None) -> Server:
    s, table = Server("mcp-server-statutory-rag"), RATES if rates is None else rates

    @s.tool
    def search_effective_dated_statute(query: str, transaction_date: str, domain: str = "") -> list:
        """Top provisions in force on transaction_date (YYYY-MM-DD); domain gst|incometax|''."""
        return search(query, date.fromisoformat(transaction_date), domain or None)

    @s.tool
    def verify_citation(citation_id: str, on_date: str) -> dict:
        """Confirms a citation exists and was in force on the date. Agents must call this before quoting any provision."""
        return effective(citation_id, date.fromisoformat(on_date))

    @s.tool
    def verify_hsn_sac_tax_rate(hsn: str, on_date: str) -> dict:
        """Tax rate for an HSN/SAC prefix on a date. Returns NOT_FOUND (route to CA) rather than guessing."""
        on = date.fromisoformat(on_date)
        for pre in sorted(table, key=len, reverse=True):
            if hsn.startswith(pre):
                for a, b, r in table[pre]:
                    if a <= on <= b:
                        return {"hsn": hsn, "rate_pct": r, "status": "FOUND"}
        return {"hsn": hsn, "status": "NOT_FOUND"}

    @s.resource("law://cgst/section/{sec_no}")
    def cgst(sec_no, date=None):
        return effective(f"CGST-s{sec_no}", _on(date))

    @s.resource("law://incometax/section/{sec_no}")
    def ita(sec_no, ay=None, date=None):
        return effective(f"ITA-s{sec_no}", _on(date))

    @s.resource("law://cbic/circulars/{circular_no}")
    def circ(circular_no, date=None):
        return effective(f"CBIC-{circular_no.replace('%2F', '/')}", _on(date))
    return s


def _on(d):
    return date.fromisoformat(d) if d else date.today()
