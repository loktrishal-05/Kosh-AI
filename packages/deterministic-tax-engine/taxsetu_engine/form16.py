"""Read and reconcile labelled Form 16 text; never calculate statutory tax."""
import re
from decimal import Decimal, localcontext

DISCLAIMER = "DRAFT: a practising CA/CS must review it before any filing."
_TEXT = {
    "employer_name": r"(?:employer name|name of (?:the )?employer)",
    "employer_tan": r"(?:employer TAN|TAN of (?:the )?employer|TAN)",
    "employee_name": r"(?:employee name|name of (?:the )?employee)",
    "employee_pan": r"(?:employee PAN|PAN of (?:the )?employee|PAN)",
    "assessment_year": r"assessment year", "period_of_employment": r"period of employment",
}
_MONEY = {
    "gross_salary": r"gross salary", "hra": r"(?:HRA|house rent allowance)",
    "lta": r"(?:LTA|leave travel allowance)",
    "exemptions_u_s_10": r"(?:total )?exemptions (?:u/s|under section) 10(?: total)?",
    "standard_deduction": r"standard deduction", "professional_tax": r"professional tax",
    "house_property": r"income from house property", "80c": r"(?:deduction (?:u/s )?)?80C",
    "80ccd_1b": r"(?:deduction (?:u/s )?)?80CCD\(1B\)",
    "80d": r"(?:deduction (?:u/s )?)?80D", "other_vi_a": r"other (?:Chapter )?VI-A(?: deductions)?(?: total)?",
    "total_vi_a": r"(?:total (?:Chapter )?VI-A deductions|Chapter VI-A deductions total)",
    "taxable_income": r"total taxable income", "tax_on_total_income": r"tax on total income",
    "rebate_87a": r"rebate (?:u/s )?87A", "cess": r"health\s*(?:&|and)\s*education cess",
    "net_tax_payable": r"net tax payable", "relief_89": r"relief (?:u/s )?89", "total_tds": r"total TDS",
}


def _amount(value):
    """Bound document numbers to ordinary rupee amounts."""
    if not isinstance(value, (str, int, Decimal)) or isinstance(value, bool):
        return None
    value = re.sub(r"(?:Rs\.?|INR|₹)|[,\s]", "", str(value), flags=re.I)
    if not re.fullmatch(r"-?\d{1,18}(?:\.\d{1,6})?", value, flags=re.ASCII):
        return None
    return Decimal(value)


def parse_form16(text: str) -> dict:
    """Extract labelled lines and Q1-Q4 receipt rows from PDF text."""
    out = {"status": "DRAFT", "disclaimer": DISCLAIMER, "errors": [], "warnings": [], "quarterly_tds": []}
    if not isinstance(text, str):
        out["errors"].append("Form 16 text must be a string")
        text = ""
    # shortcut: labelled lines and one receipt row per quarter; add layout adapters for other PDF extractions.
    for key, label in {**_TEXT, **_MONEY}.items():
        label = label.replace(" ", r"[ \t]+")
        match = re.search(r"^[ \t]*" + label + r"(?:[ \t]*:[ \t]*|[ \t]+(?![ \t]*:))([^\r\n]+?)[ \t]*$", text, re.I | re.M)
        value = (match.group(1).strip() or None) if match else None
        if key in _MONEY and value is not None:
            number = _amount(value)
            if number is None or (number < 0 and key != "house_property"):
                out["errors"].append(f"Invalid amount: {key}")
                value = None
            else:
                value = str(number)
        out[key] = value
        if value is None:
            out["errors"].append(f"Missing or unreadable field: {key}")
    currency = r"(?:Rs\.?|INR|₹)?[ \t]*-?[0-9][0-9,]*(?:\.[0-9]+)?"
    for line in text.splitlines():
        if not re.match(r"\s*Q[0-9]+\b", line, re.I):
            continue
        row = re.fullmatch(r"[ \t]*(Q[1-4])[ \t|]+([^ \t|]+)[ \t|]+(" + currency
                           + r")[ \t|]+(" + currency + r")[ \t]*", line, re.I)
        if not row:
            out["errors"].append(f"Unreadable quarterly TDS row: {line.strip()}")
            continue
        quarter, receipt, deducted, deposited = row.groups()
        amounts = [_amount(deducted), _amount(deposited)]
        if any(a is None or a < 0 for a in amounts):
            out["errors"].append(f"Invalid quarterly TDS amounts: {quarter}")
            continue
        out["quarterly_tds"].append(dict(quarter=quarter.upper(), receipt_number=receipt,
                                        amount_deducted=str(amounts[0]), amount_deposited=str(amounts[1])))
    return out


def validate_form16(parsed: dict) -> dict:
    """Reconcile stated Part B and quarterly TDS amounts."""
    with localcontext() as context:
        context.prec = 80
        errors, warnings = [], []
        if not isinstance(parsed, dict):
            parsed = {}
            errors.append("Parsed Form 16 must be an object")
        for key in ("errors", "warnings"):
            values = parsed.get(key, [])
            if isinstance(values, list):
                (errors if key == "errors" else warnings).extend(str(v) for v in values)
        for key, pattern in (("employee_pan", r"[A-Z]{5}[0-9]{4}[A-Z]"),
                             ("employer_tan", r"[A-Z]{4}[0-9]{5}[A-Z]")):
            if not isinstance(parsed.get(key), str) or not re.fullmatch(pattern, parsed[key]):
                errors.append(f"Invalid {key} format")
        ay = parsed.get("assessment_year")
        if not isinstance(ay, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}", ay):
            errors.append("Invalid assessment year format")
        elif not (2000 <= int(ay[:4]) <= 2100 and int(ay[5:]) == (int(ay[:4]) + 1) % 100):
            errors.append("Implausible assessment year (expected consecutive years, 2000-2100)")
        for key in _TEXT:
            if not isinstance(parsed.get(key), str) or not parsed[key].strip():
                errors.append(f"Missing {key}")
        amounts = {key: _amount(parsed.get(key)) for key in _MONEY}
        for key, amount in amounts.items():
            if amount is None or (amount < 0 and key != "house_property"):
                errors.append(f"Invalid or missing amount: {key}")
        if all(value is not None for value in amounts.values()):
            a = amounts
            expected = (a["gross_salary"] - a["exemptions_u_s_10"] - a["standard_deduction"]
                        - a["professional_tax"] + a["house_property"] - a["total_vi_a"])
            for label, computed, stated in (
                ("Taxable income", expected, a["taxable_income"]),
                ("Exemptions u/s 10", a["hra"] + a["lta"], a["exemptions_u_s_10"]),
                ("Chapter VI-A", a["80c"] + a["80ccd_1b"] + a["80d"] + a["other_vi_a"], a["total_vi_a"]),
            ):
                if abs(computed - stated) > Decimal("1"):
                    errors.append(f"{label} mismatch: computed {computed}, stated {stated}")
        rows = parsed.get("quarterly_tds")
        total, seen = Decimal("0"), set()
        if not isinstance(rows, list) or not rows:
            errors.append("Missing quarterly TDS table")
            rows = []
        for row in rows:
            if not isinstance(row, dict):
                errors.append("Invalid quarterly TDS row")
                continue
            quarter = row.get("quarter")
            if not isinstance(quarter, str) or quarter not in ("Q1", "Q2", "Q3", "Q4") or quarter in seen:
                errors.append("Invalid or duplicate TDS quarter")
            else:
                seen.add(quarter)
            if not isinstance(row.get("receipt_number"), str) or not row["receipt_number"].strip():
                errors.append("Missing TDS receipt number")
            deducted, deposited = _amount(row.get("amount_deducted")), _amount(row.get("amount_deposited"))
            if deducted is None or deposited is None or deducted < 0 or deposited < 0:
                errors.append("Invalid quarterly TDS amounts")
                continue
            total += deducted
            if deposited < deducted:
                warnings.append(f"{quarter}: deposited {deposited} is below deducted {deducted}")
        if amounts["total_tds"] is not None and total != amounts["total_tds"]:
            errors.append(f"Total TDS mismatch: quarterly deductions {total}, stated {amounts['total_tds']}")
        return dict(status="DRAFT", disclaimer=DISCLAIMER, ok=not errors, errors=errors, warnings=warnings)


def sample_form16(variant="old_regime") -> str:
    """Synthetic certificate; amounts are illustrative, not tax advice."""
    new = variant == "new_regime"
    values = dict(employer_name="Synthetic Demo Widgets Private Limited", employer_tan="DEMO12345A",
                  employee_name="Synthetic Example Employee", employee_pan="ZZZZZ1234Z", assessment_year="2026-27",
                  period_of_employment="01-04-2025 to 31-03-2026", gross_salary="1200000", hra="0" if new else "120000",
                  lta="0" if new else "20000", exemptions_u_s_10="0" if new else "140000",
                  standard_deduction="75000" if new else "50000", professional_tax="0" if new else "2400",
                  house_property="0", **{"80c": "0" if new else "150000", "80ccd_1b": "0" if new else "50000",
                  "80d": "0" if new else "25000"}, other_vi_a="0", total_vi_a="0" if new else "225000",
                  taxable_income="1125000" if new else "782600", tax_on_total_income="52500" if new else "69020",
                  rebate_87a="52500" if new else "0", cess="0" if new else "2760.80", net_tax_payable="0" if new else "71780.80",
                  relief_89="0", total_tds="0" if new else "71780.80")
    if variant == "mismatch":
        values["taxable_income"] = "900000"
    labels = ["Employer name", "Employer TAN", "Employee name", "Employee PAN", "Assessment year", "Period of employment",
              "Gross salary", "HRA", "LTA", "Exemptions u/s 10", "Standard deduction", "Professional tax",
              "Income from house property", "80C", "80CCD(1B)", "80D", "Other VI-A total", "Total VI-A deductions",
              "Total taxable income", "Tax on total income", "Rebate 87A", "Health & education cess", "Net tax payable",
              "Relief 89", "Total TDS"]
    lines = ["FORM 16 - SYNTHETIC DEMO ONLY", "Status: DRAFT", "Part A and Part B", DISCLAIMER]
    lines.extend(f"{label} : {value}" for label, value in zip(labels, values.values()))
    lines.append("Quarter | Receipt number | Amount deducted | Amount deposited")
    amount = "0" if new else "17,945.20"
    lines.extend(f"Q{q} | DEMO2025Q{q} | Rs. {amount} | INR {amount}" for q in range(1, 5))
    return "\n".join(lines) + "\n"
