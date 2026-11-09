"""Deterministic Form A employee and Form B wage register compilation."""
import re
from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal

from .gst import is_valid_pan
from .money import d, r2


@dataclass(frozen=True)
class Employee:
    lin: str = ""
    employee_code: str = ""
    full_name: str = ""
    surname: str = ""
    gender: str = ""
    father_or_spouse_name: str = ""
    date_of_birth: date | None = None
    nationality: str = ""
    education_level: str = ""
    date_of_joining: date | None = None
    designation: str = ""
    category: str = ""
    employment_type: str = ""
    mobile: str = ""
    uan: str = ""
    pan: str = ""
    esic_ip: str = ""
    aadhaar: str = ""
    bank_account: str = ""
    ifsc: str = ""
    present_address: str = ""
    permanent_address: str = ""
    exit_date: date | None = None
    exit_reason: str = ""


_VERHOEFF_D = (
    (0, 1, 2, 3, 4, 5, 6, 7, 8, 9), (1, 2, 3, 4, 0, 6, 7, 8, 9, 5),
    (2, 3, 4, 0, 1, 7, 8, 9, 5, 6), (3, 4, 0, 1, 2, 8, 9, 5, 6, 7),
    (4, 0, 1, 2, 3, 9, 5, 6, 7, 8), (5, 9, 8, 7, 6, 0, 4, 3, 2, 1),
    (6, 5, 9, 8, 7, 1, 0, 4, 3, 2), (7, 6, 5, 9, 8, 2, 1, 0, 4, 3),
    (8, 7, 6, 5, 9, 3, 2, 1, 0, 4), (9, 8, 7, 6, 5, 4, 3, 2, 1, 0),
)
_VERHOEFF_P = (
    (0, 1, 2, 3, 4, 5, 6, 7, 8, 9), (1, 5, 7, 6, 2, 8, 3, 0, 9, 4),
    (5, 8, 0, 3, 7, 9, 6, 1, 4, 2), (8, 9, 1, 6, 0, 4, 3, 5, 2, 7),
    (9, 4, 5, 3, 1, 2, 6, 8, 7, 0), (4, 2, 8, 6, 5, 7, 3, 9, 0, 1),
    (2, 7, 9, 3, 8, 0, 6, 4, 1, 5), (7, 0, 4, 6, 9, 1, 3, 2, 5, 8),
)
_VERHOEFF_INV = (0, 4, 3, 2, 1, 5, 6, 7, 8, 9)


def verhoeff_valid(number: str) -> bool:
    if not re.fullmatch(r"[0-9]+", number):
        return False
    checksum = 0
    for i, digit in enumerate(reversed(number)):
        checksum = _VERHOEFF_D[checksum][_VERHOEFF_P[i % 8][int(digit)]]
    return _VERHOEFF_INV[checksum] == 0


def validate_employee(e: Employee, today: date) -> list[str]:
    errors = []
    for label, value in (("LIN", e.lin), ("Employee code", e.employee_code), ("Full name", e.full_name)):
        if not value.strip():
            errors.append(f"{label} is required")
    if e.gender not in {"M", "F", "O"}:
        errors.append("Gender must be M, F or O")
    if e.category not in {"Highly Skilled", "Skilled", "Semi-Skilled", "Unskilled"}:
        errors.append("Category must be Highly Skilled, Skilled, Semi-Skilled or Unskilled")
    for label, value, pattern in (
        ("Mobile", e.mobile, r"[6-9][0-9]{9}"), ("UAN", e.uan, r"[0-9]{12}"),
        ("ESIC IP", e.esic_ip, r"[0-9]{17}"), ("IFSC", e.ifsc, r"[A-Z]{4}0[A-Z0-9]{6}"),
        ("Bank account", e.bank_account, r"[0-9]{9,18}"),
    ):
        if value and not re.fullmatch(pattern, value):
            errors.append(f"{label} has an invalid format")
    if e.pan and not is_valid_pan(e.pan):
        errors.append("PAN has an invalid format")
    # ponytail: checksum/format checks do not prove identifier ownership; verify with the issuing authority.
    if e.aadhaar and (not re.fullmatch(r"[0-9]{12}", e.aadhaar) or not verhoeff_valid(e.aadhaar)):
        errors.append("Aadhaar must have 12 digits and a valid Verhoeff checksum")
    if e.date_of_joining:
        if e.date_of_birth and e.date_of_joining < e.date_of_birth:
            errors.append("Date of joining is before date of birth")
        if e.date_of_joining > today:
            errors.append("Date of joining is in the future")
        if e.exit_date and e.exit_date < e.date_of_joining:
            errors.append("Exit date is before date of joining")
    return errors


def mask(value: str, keep: int = 4) -> str:
    if keep < 0:
        raise ValueError("keep must be nonnegative")
    return "X" * max(len(value) - keep, 0) + (value[-keep:] if keep else "")


_FORM_A_COLUMNS = (
    ("LIN", "lin"), ("Employee Code", "employee_code"), ("Full Name", "full_name"),
    ("Surname", "surname"), ("Gender", "gender"), ("Father's/Spouse's Name", "father_or_spouse_name"),
    ("Date of Birth", "date_of_birth"), ("Nationality", "nationality"), ("Education Level", "education_level"),
    ("Date of Joining", "date_of_joining"), ("Designation", "designation"), ("Category", "category"),
    ("Type of Employment", "employment_type"), ("Mobile Number", "mobile"), ("UAN (EPFO)", "uan"),
    ("PAN", "pan"), ("ESIC IP Number", "esic_ip"), ("Aadhaar", "aadhaar"),
    ("Bank Account Number", "bank_account"), ("IFSC", "ifsc"), ("Present Address", "present_address"),
    ("Permanent Address", "permanent_address"), ("Date of Exit", "exit_date"), ("Reason of Exit", "exit_reason"),
)


def form_a_rows(employees, lin: str) -> list[dict]:
    rows = []
    for employee in sorted(employees, key=lambda e: e.employee_code):
        row = {}
        for title, field in _FORM_A_COLUMNS:
            value = lin if field == "lin" else getattr(employee, field)
            if field in {"aadhaar", "bank_account"}:
                value = mask(value, min(4, max(len(value) - 1, 0)))
            row[title] = value.isoformat() if isinstance(value, date) else value if value is not None else ""
        rows.append(row)
    return rows


@dataclass(frozen=True)
class WageInput:
    employee_code: str
    minimum_wage_basic: Decimal
    minimum_wage_da: Decimal
    working_days_in_month: Decimal
    days_worked: Decimal
    overtime_hours: Decimal = Decimal("0")
    basic_earned: Decimal = Decimal("0")
    special_basic: Decimal = Decimal("0")
    da: Decimal = Decimal("0")
    overtime_pay: Decimal = Decimal("0")
    hra: Decimal = Decimal("0")
    other_allowances: Decimal = Decimal("0")
    deductions: tuple[tuple[str, Decimal], ...] = ()
    payment_ref: str = ""
    paid_on: date | None = None


_EARNINGS = ("basic_earned", "special_basic", "da", "overtime_pay", "hra", "other_allowances")
_DEDUCTIONS = ("epf", "esic", "society", "tds", "insurance", "fines")


def compute_wage_row(w: WageInput, employer_pf_rate=Decimal("12"), pf_wage_ceiling=Decimal("15000")) -> dict:
    fields = ("minimum_wage_basic", "minimum_wage_da", "working_days_in_month", "days_worked", "overtime_hours") + _EARNINGS
    amounts = {field: d(getattr(w, field)) for field in fields}
    rate, ceiling = d(employer_pf_rate), d(pf_wage_ceiling)
    if any(not amount.is_finite() or amount < 0 for amount in (*amounts.values(), rate, ceiling)):
        raise ValueError("Wage amounts, days, hours and PF inputs must be finite and nonnegative")
    if amounts["working_days_in_month"] == 0 or amounts["days_worked"] > amounts["working_days_in_month"]:
        raise ValueError("Working days must be positive and days worked must not exceed them")
    deductions = dict.fromkeys(_DEDUCTIONS, d(0))
    for label, value in w.deductions:
        amount = d(value)
        if label not in deductions or not amount.is_finite() or amount < 0:
            raise ValueError("Deductions must use epf, esic, society, tds, insurance or fines and nonnegative finite amounts")
        deductions[label] += amount
    gross = sum((amounts[field] for field in _EARNINGS), d(0))
    total_deductions = sum(deductions.values(), d(0))
    if total_deductions > gross:
        raise ValueError("Deductions exceed gross wages")
    pf_wages = amounts["basic_earned"] + amounts["da"]
    # ponytail: PF rate/ceiling and minimum-wage rates are state/scheme-specific inputs a CA must verify.
    # Compare before paisa rounding; cross-multiplication avoids recurring Decimal division.
    below_minimum = pf_wages * amounts["working_days_in_month"] < (
        amounts["minimum_wage_basic"] + amounts["minimum_wage_da"]
    ) * amounts["days_worked"]
    # ponytail: round reported amounts independently; verify sub-paisa source data before ledger reconciliation.
    return {"employee_code": w.employee_code, **{field: r2(value) for field, value in amounts.items()},
            "gross": r2(gross), "deductions": {label: r2(value) for label, value in deductions.items()},
            "total_deductions": r2(total_deductions), "net": r2(gross - total_deductions),
            "employer_pf": r2(rate * min(pf_wages, ceiling) / 100),
            "payment_ref": w.payment_ref, "paid_on": w.paid_on, "below_minimum_wage": below_minimum}


def compile_registers(lin: str, month: str, employees, wages, today: date) -> dict:
    employees, wages = list(employees), list(wages)
    errors, warnings, form_b = {}, [], []
    employee_codes, wage_codes = set(), set()
    # ponytail: caller supplies the register month and population; verify period eligibility before filing.
    for employee in employees:
        messages = validate_employee(replace(employee, lin=lin), today)
        if employee.lin and employee.lin != lin:
            messages.append("Employee LIN does not match register LIN")
        if employee.employee_code in employee_codes:
            messages.append("Duplicate employee code in Form A")
        employee_codes.add(employee.employee_code)
        if messages:
            errors.setdefault(employee.employee_code, []).extend(messages)
    for wage in sorted(wages, key=lambda w: w.employee_code):
        messages = []
        if wage.employee_code not in employee_codes:
            messages.append("Wage employee code is missing from Form A")
        if wage.employee_code in wage_codes:
            messages.append("Duplicate wage row")
        wage_codes.add(wage.employee_code)
        try:
            form_b.append(compute_wage_row(wage))
        except ValueError as exc:
            messages.append(str(exc))
        if messages:
            errors.setdefault(wage.employee_code, []).extend(messages)
    for code in sorted(employee_codes - wage_codes):
        warnings.append(f"Employee {code} has no wage row")
    return {"month": month, "form_a": form_a_rows(employees, lin), "form_b": form_b,
            "errors": errors, "warnings": warnings}
