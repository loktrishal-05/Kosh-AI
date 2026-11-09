"""Deterministic labour registers, Form 16 parsing and incorporation drafts."""
from datetime import date
from decimal import Decimal, InvalidOperation

from taxsetu_engine import form16, labour, spice

from .core import Server, ToolError

_DATES = {"date_of_birth", "date_of_joining", "exit_date"}


def _employee(r: dict) -> labour.Employee:
    return labour.Employee(**{k: ((date.fromisoformat(v) if v else None) if k in _DATES else v) for k, v in r.items()})


def _wage(r: dict) -> labour.WageInput:
    money = {k: Decimal(str(v)) for k, v in r.items() if k not in ("employee_code", "payment_ref", "paid_on", "deductions")}
    return labour.WageInput(employee_code=r["employee_code"], payment_ref=r.get("payment_ref", ""),
                            paid_on=date.fromisoformat(r["paid_on"]) if r.get("paid_on") else None,
                            deductions=tuple((k, Decimal(str(v))) for k, v in r.get("deductions", {}).items()), **money)


def build() -> Server:
    s = Server("mcp-server-mca-labour")

    @s.tool(hitl=True)
    def compile_labour_registers_form_a_and_b(lin: str, month: str, payroll_data: dict, today: str = "") -> dict:
        """payroll_data = {"employees": [Form A fields, dates ISO], "wages": [Form B inputs, deductions as {label: amount}]}.
        Returns masked Form A rows, computed Form B rows, per-employee errors and warnings. Nothing is dropped silently."""
        try:
            emps = [_employee(e) for e in payroll_data.get("employees", [])]
            wages = [_wage(w) for w in payroll_data.get("wages", [])]
        except (TypeError, ValueError, KeyError, InvalidOperation) as e:
            raise ToolError(f"bad payroll_data: {e}") from e
        return labour.compile_registers(lin, month, emps, wages, date.fromisoformat(today) if today else date.today())

    @s.tool(hitl=True)
    def draft_spice_plus_emoa_inc33(inp: dict) -> dict:
        """Draft INC-33 clauses and subscription arithmetic for CA/CS review."""
        return spice.draft_emoa(inp)

    @s.tool(hitl=True)
    def draft_eaoa_inc34_with_entrenchment(inp: dict) -> dict:
        """Draft Table F adoption and an INC-34 entrenchment schedule for CS review."""
        return spice.draft_eaoa(inp)

    @s.tool(hitl=True)
    def parse_form16_certificate(text: str) -> dict:
        """Parse untrusted certificate text and reconcile the stated amounts."""
        parsed = form16.parse_form16(text)
        return {"status": "DRAFT", "disclaimer": form16.DISCLAIMER,
                "parsed": parsed, "validation": form16.validate_form16(parsed)}
    return s
