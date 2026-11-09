"""Labour register oracles: synthetic identifiers and hand-computed wage arithmetic."""
import json
from dataclasses import FrozenInstanceError, replace
from datetime import date
from decimal import Decimal as D

import pytest

from taxsetu_engine.labour import (
    Employee, WageInput, compile_registers, compute_wage_row, form_a_rows,
    mask, validate_employee, verhoeff_valid,
)


TODAY = date(2026, 11, 9)


def _verhoeff_number(prefix):
    # Independent generator: dihedral multiplication and powers of the base permutation.
    permutation = (1, 5, 7, 6, 2, 8, 3, 0, 9, 4)
    checksum = 0
    for i, digit in enumerate(reversed(prefix), 1):
        value = int(digit)
        for _ in range(i % 8):
            value = permutation[value]
        if checksum < 5:
            checksum = (checksum + value) % 5 + (5 if value >= 5 else 0)
        else:
            checksum = (checksum - value) % 5 + (5 if value < 5 else 0)
    return prefix + str((-checksum) % 5 if checksum < 5 else checksum)


AADHAAR = _verhoeff_number("23456789012")
EMPLOYEE = Employee(
    lin="LIN001", employee_code="E001", full_name="Anita Kumar", surname="Kumar", gender="F",
    father_or_spouse_name="Arun Kumar", date_of_birth=date(1990, 1, 1), nationality="Indian",
    education_level="Graduate", date_of_joining=date(2020, 1, 1), designation="Technician",
    category="Skilled", employment_type="Permanent", mobile="9876543210", uan="123456789012",
    pan="ABCDE1234F", esic_ip="12345678901234567", aadhaar=AADHAAR, bank_account="87654321098765",
    ifsc="ABCD0123456", present_address="Present address", permanent_address="Permanent address",
)
WAGE = WageInput("E001", D("10000"), D("2000"), D("30"), D("30"), basic_earned=D("10000"), da=D("2000"))


@pytest.mark.parametrize("prefix", ["23456789012", "98765432109", "12345678901", "00000000000", "236"])
def test_verhoeff_generated(prefix):
    number = _verhoeff_number(prefix)
    assert verhoeff_valid(number)
    for position, digit in enumerate(number):
        for replacement in "0123456789":
            if replacement != digit:
                assert not verhoeff_valid(number[:position] + replacement + number[position + 1:])


@pytest.mark.parametrize("number", ["", "234567890123", "2364", "12a4", "１２３４", "2363\n", " 2363"])
def test_verhoeff_invalid(number):
    assert not verhoeff_valid(number)


def test_verhoeff_known_vector():
    assert _verhoeff_number("236") == "2363"
    assert verhoeff_valid("2363")


@pytest.mark.parametrize("field,value,message", [
    ("lin", "", "LIN"), ("employee_code", "  ", "Employee code"), ("full_name", "", "Full name"),
    ("gender", "X", "Gender"), ("category", "Other", "Category"),
    ("mobile", "5876543210", "Mobile"), ("mobile", "987654321", "Mobile"),
    ("mobile", "98765432100", "Mobile"), ("mobile", "987654321a", "Mobile"),
    ("uan", "12345678901", "UAN"), ("uan", "1234567890123", "UAN"),
    ("uan", "12345678901a", "UAN"), ("pan", "ABCDE12345", "PAN"),
    ("esic_ip", "1234567890123456", "ESIC IP"), ("esic_ip", "123456789012345678", "ESIC IP"),
    ("aadhaar", "2363", "Aadhaar"), ("aadhaar", AADHAAR[:-1] + str((int(AADHAAR[-1]) + 1) % 10), "Aadhaar"),
    ("aadhaar", "a" * 12, "Aadhaar"), ("ifsc", "ABCD1123456", "IFSC"),
    ("ifsc", "abcd0123456", "IFSC"), ("ifsc", "ABCD012345", "IFSC"),
    ("bank_account", "12345678", "Bank account"), ("bank_account", "1" * 19, "Bank account"),
    ("bank_account", "12345678a", "Bank account"),
    ("date_of_joining", date(1989, 12, 31), "before date of birth"),
    ("date_of_joining", date(2026, 11, 10), "future"),
    ("exit_date", date(2019, 12, 31), "before date of joining"),
])
def test_employee_invalid(field, value, message):
    errors = validate_employee(replace(EMPLOYEE, **{field: value}), TODAY)
    assert len(errors) == 1 and message in errors[0]


@pytest.mark.parametrize("field,value", [
    ("gender", "M"), ("gender", "F"), ("gender", "O"),
    ("category", "Highly Skilled"), ("category", "Skilled"), ("category", "Semi-Skilled"), ("category", "Unskilled"),
    ("mobile", "6000000000"), ("mobile", "7000000000"), ("mobile", "8000000000"),
    ("pan", "abcde1234f"), ("ifsc", "ABCD0ABC123"),
    ("bank_account", "1" * 9), ("bank_account", "1" * 18),
    ("date_of_joining", date(1990, 1, 1)), ("date_of_joining", TODAY),
    ("exit_date", date(2020, 1, 1)), ("exit_date", TODAY),
    ("date_of_birth", None), ("date_of_joining", None),
])
def test_employee_valid(field, value):
    assert validate_employee(replace(EMPLOYEE, **{field: value}), TODAY) == []


@pytest.mark.parametrize("field", ["mobile", "uan", "pan", "esic_ip", "aadhaar", "ifsc", "bank_account"])
def test_optional_identifiers(field):
    assert validate_employee(replace(EMPLOYEE, **{field: ""}), TODAY) == []


@pytest.mark.parametrize("value,keep,expected", [
    ("123456789012", 4, "XXXXXXXX9012"), ("1234", 4, "1234"), ("123", 4, "123"),
    ("1234", 0, "XXXX"), ("", 4, ""), ("1234", 1, "XXX4"), ("12", 9, "12"),
])
def test_mask(value, keep, expected):
    assert mask(value, keep) == expected


def test_mask_negative_keep():
    with pytest.raises(ValueError):
        mask("1234", -1)


def test_form_a_order_columns_dates_and_masking():
    rows = form_a_rows(iter([replace(EMPLOYEE, employee_code="E002"), EMPLOYEE]), "LIN002")
    assert [row["Employee Code"] for row in rows] == ["E001", "E002"]
    assert list(rows[0]) == [
        "LIN", "Employee Code", "Full Name", "Surname", "Gender", "Father's/Spouse's Name", "Date of Birth",
        "Nationality", "Education Level", "Date of Joining", "Designation", "Category", "Type of Employment",
        "Mobile Number", "UAN (EPFO)", "PAN", "ESIC IP Number", "Aadhaar", "Bank Account Number", "IFSC",
        "Present Address", "Permanent Address", "Date of Exit", "Reason of Exit",
    ]
    assert rows[0]["LIN"] == "LIN002"
    assert rows[0]["Date of Birth"] == "1990-01-01" and rows[0]["Date of Exit"] == ""
    assert rows[0]["Aadhaar"] == "XXXXXXXX" + AADHAAR[-4:]
    assert rows[0]["Bank Account Number"] == "XXXXXXXXXX8765"
    encoded = json.dumps(rows)
    assert AADHAAR not in encoded and EMPLOYEE.bank_account not in encoded


@pytest.mark.parametrize("value", ["1", "123", "1234", "12345"])
def test_form_a_masks_even_invalid_short_identifiers(value):
    row = form_a_rows([replace(EMPLOYEE, aadhaar=value, bank_account=value)], "LIN001")[0]
    assert row["Aadhaar"] != value and row["Bank Account Number"] != value


def test_wage_arithmetic():
    row = compute_wage_row(replace(
        WAGE, special_basic=D("1000"), overtime_hours=D("4"), overtime_pay=D("500"),
        hra=D("3000"), other_allowances=D("700"), payment_ref="BANK001", paid_on=TODAY,
        deductions=(("epf", D("1440")), ("esic", D("100")), ("society", D("50")),
                    ("tds", D("200")), ("insurance", D("60")), ("fines", D("25"))),
    ))
    assert row["gross"] == D("17200.00")
    assert row["total_deductions"] == D("1875.00")
    assert row["net"] == D("15325.00")
    assert row["employer_pf"] == D("1440.00")
    assert row["deductions"]["epf"] == D("1440.00")
    assert row["payment_ref"] == "BANK001" and row["paid_on"] == TODAY
    assert not row["below_minimum_wage"]
    for value in row.values():
        if isinstance(value, D):
            assert value.as_tuple().exponent == -2
    assert all(value.as_tuple().exponent == -2 for value in row["deductions"].values())


@pytest.mark.parametrize("basic,da,rate,ceiling,expected", [
    ("14000", "2000", "12", "15000", "1800.00"), ("13000", "2000", "12", "15000", "1800.00"),
    ("10000", "2000", "10", "10000", "1000.00"), ("0", "0", "12", "15000", "0.00"),
])
def test_employer_pf(basic, da, rate, ceiling, expected):
    row = compute_wage_row(replace(WAGE, basic_earned=D(basic), da=D(da)), D(rate), D(ceiling))
    assert row["employer_pf"] == D(expected)


@pytest.mark.parametrize("days,basic,da,below", [
    ("15", "4000", "2000", False), ("15", "3999.99", "2000", True),
    ("15", "4000.01", "2000", False), ("0", "0", "0", False),
    ("1", "399.999", "0", True), ("1", "400", "0", False),
])
def test_minimum_wage_proration(days, basic, da, below):
    row = compute_wage_row(replace(WAGE, days_worked=D(days), basic_earned=D(basic), da=D(da)))
    assert row["below_minimum_wage"] is below


def test_recurring_proration_is_compared_before_rounding():
    row = compute_wage_row(replace(WAGE, minimum_wage_basic=D("100"), minimum_wage_da=D("0"),
                                  working_days_in_month=D("3"), days_worked=D("1"),
                                  basic_earned=D("33.33333333333333333333333333"), da=D("0")))
    assert row["below_minimum_wage"] and row["gross"] == D("33.33")


@pytest.mark.parametrize("deduction,raises", [("12000", False), ("12000.001", True)])
def test_deductions_cannot_exceed_gross(deduction, raises):
    wage = replace(WAGE, deductions=(("epf", D(deduction)),))
    if raises:
        with pytest.raises(ValueError, match="exceed"):
            compute_wage_row(wage)
    else:
        assert compute_wage_row(wage)["net"] == D("0.00")


@pytest.mark.parametrize("label,amount", [("unknown", "1"), ("epf", "-1"), ("esic", "NaN"), ("tds", "Infinity")])
def test_invalid_deductions(label, amount):
    with pytest.raises(ValueError, match="Deductions"):
        compute_wage_row(replace(WAGE, deductions=((label, D(amount)),)))


@pytest.mark.parametrize("field,value", [
    ("working_days_in_month", "0"), ("working_days_in_month", "-1"), ("days_worked", "31"),
    ("days_worked", "-1"), ("overtime_hours", "-1"), ("basic_earned", "-1"),
    ("da", "NaN"), ("hra", "Infinity"), ("minimum_wage_basic", "-1"),
])
def test_invalid_wage_inputs(field, value):
    with pytest.raises(ValueError):
        compute_wage_row(replace(WAGE, **{field: D(value)}))


@pytest.mark.parametrize("rate,ceiling", [("-1", "15000"), ("12", "-1"), ("NaN", "15000")])
def test_invalid_pf_inputs(rate, ceiling):
    with pytest.raises(ValueError):
        compute_wage_row(WAGE, D(rate), D(ceiling))


def test_rounding_and_repeated_deduction_labels():
    row = compute_wage_row(replace(WAGE, basic_earned=D("1.005"), da=D("0"),
                                  deductions=(("epf", D("0.005")), ("epf", D("0.005")))))
    assert row["gross"] == D("1.01") and row["net"] == D("1.00")
    assert row["deductions"]["epf"] == row["total_deductions"] == D("0.01")


def test_compile_registers_valid_and_iterables():
    result = compile_registers("LIN001", "2026-11", iter([EMPLOYEE]), iter([WAGE]), TODAY)
    assert result["month"] == "2026-11" and result["errors"] == {} and result["warnings"] == []
    assert result["form_a"] == form_a_rows([EMPLOYEE], "LIN001")
    assert result["form_b"] == [compute_wage_row(WAGE)]


def test_compile_orphan_and_missing_wage():
    result = compile_registers("LIN001", "2026-11", [EMPLOYEE], [replace(WAGE, employee_code="ORPHAN")], TODAY)
    assert "missing from Form A" in result["errors"]["ORPHAN"][0]
    assert result["form_b"][0]["employee_code"] == "ORPHAN"
    assert result["warnings"] == ["Employee E001 has no wage row"]


def test_compile_collects_employee_and_wage_errors():
    result = compile_registers("LIN001", "2026-11", [replace(EMPLOYEE, gender="X")],
                               [replace(WAGE, deductions=(("fines", D("12001")),))], TODAY)
    assert len(result["errors"]["E001"]) == 2
    assert result["form_b"] == [] and result["warnings"] == []


def test_compile_lin_and_duplicates():
    result = compile_registers("LIN002", "2026-11", [EMPLOYEE, EMPLOYEE], [WAGE, WAGE], TODAY)
    assert any("LIN" in message for message in result["errors"]["E001"])
    assert any("Duplicate employee" in message for message in result["errors"]["E001"])
    assert any("Duplicate wage" in message for message in result["errors"]["E001"])
    result = compile_registers("LIN001", "2026-11", [replace(EMPLOYEE, lin="")], [WAGE], TODAY)
    assert result["errors"] == {}
    result = compile_registers("", "2026-11", [EMPLOYEE], [], TODAY)
    assert "LIN is required" in result["errors"]["E001"]


def test_empty_registers():
    assert compile_registers("LIN001", "2026-11", [], [], TODAY) == {
        "month": "2026-11", "form_a": [], "form_b": [], "errors": {}, "warnings": [],
    }


@pytest.mark.parametrize("record", [EMPLOYEE, WAGE])
def test_dataclasses_are_frozen(record):
    with pytest.raises(FrozenInstanceError):
        record.employee_code = "CHANGED"
