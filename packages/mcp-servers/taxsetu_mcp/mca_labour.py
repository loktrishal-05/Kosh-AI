"""mcp-server-mca-labour. Labour Form A/B registers are compiled by the deterministic engine; the e-MOA / e-AOA drafters are Phase 5b
and refuse rather than fake legal text."""
from datetime import date
from decimal import Decimal, InvalidOperation

from taxsetu_engine import labour

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

    for name in ("draft_spice_plus_emoa_inc33", "draft_eaoa_inc34_with_entrenchment"):
        def tool(**kw):
            raise ToolError("Phase 5b: not implemented yet")
        tool.__name__ = name
        s.tool(hitl=True)(tool)
    return s
