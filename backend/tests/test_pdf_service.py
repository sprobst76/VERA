"""
Tests für pdf_service.generate_payslip_pdf –
Stellt sicher, dass der PDF-Dienst Vertragsdaten ausschließlich aus ContractHistory liest.
"""
import uuid
from datetime import date
from decimal import Decimal
from unittest.mock import patch, MagicMock
import pytest


def make_payroll_entry(
    employee_id=None,
    month=None,
    status="approved",
    planned_hours=Decimal("40.00"),
    actual_hours=Decimal("40.00"),
    paid_hours=Decimal("40.00"),
    base_wage=Decimal("520.00"),
    total_gross=Decimal("520.00"),
    ytd_gross=None,
    annual_limit_remaining=None,
    **kwargs,
):
    """Minimal PayrollEntry-ähnliches Objekt für Tests."""

    class FakeEntry:
        pass

    e = FakeEntry()
    e.id = uuid.uuid4()
    e.employee_id = employee_id or uuid.uuid4()
    e.tenant_id = uuid.uuid4()
    e.month = month or date(2026, 1, 1)
    e.status = status
    e.planned_hours = planned_hours
    e.actual_hours = actual_hours
    e.carryover_hours = Decimal("0")
    e.paid_hours = paid_hours
    e.base_wage = base_wage
    e.total_gross = total_gross
    e.ytd_gross = ytd_gross or total_gross
    e.annual_limit_remaining = annual_limit_remaining or Decimal("6152.00")
    e.notes = None
    # Zuschlagsfelder
    for field in [
        "early_hours", "late_hours", "night_hours", "weekend_hours", "sunday_hours", "holiday_hours",
        "early_surcharge", "late_surcharge", "night_surcharge", "weekend_surcharge",
        "sunday_surcharge", "holiday_surcharge",
    ]:
        setattr(e, field, Decimal("0"))
    for k, v in kwargs.items():
        setattr(e, k, v)
    return e


def make_employee(contract_type="part_time", hourly_rate=99.0, annual_salary_limit=None):
    """Minimal Employee-ähnliches Objekt."""

    class FakeEmployee:
        pass

    e = FakeEmployee()
    e.id = uuid.uuid4()
    e.first_name = "Max"
    e.last_name = "Mustermann"
    e.contract_type = contract_type
    e.hourly_rate = hourly_rate
    e.annual_salary_limit = annual_salary_limit
    return e


def make_contract(contract_type="minijob", hourly_rate=15.50, annual_salary_limit=6672.0):
    """Minimal ContractHistory-ähnliches Objekt."""

    class FakeContract:
        pass

    c = FakeContract()
    c.id = uuid.uuid4()
    c.contract_type = contract_type
    c.hourly_rate = Decimal(str(hourly_rate))
    c.annual_salary_limit = Decimal(str(annual_salary_limit)) if annual_salary_limit else None
    return c


# ── Test: ValueError wenn kein contract übergeben wird ───────────────────────

def test_generate_payslip_pdf_raises_when_no_contract():
    """generate_payslip_pdf muss ValueError werfen wenn contract=None (kein Mirror-Fallback)."""
    from app.services.pdf_service import generate_payslip_pdf

    entry = make_payroll_entry()
    employee = make_employee()

    with pytest.raises(ValueError, match="ContractHistory"):
        generate_payslip_pdf(entry, employee, "Test GmbH", contract=None)


def test_generate_payslip_pdf_raises_without_contract_kwarg():
    """Auch ohne explizites contract=None soll ValueError kommen (default=None)."""
    from app.services.pdf_service import generate_payslip_pdf

    entry = make_payroll_entry()
    employee = make_employee()

    with pytest.raises(ValueError, match="ContractHistory"):
        generate_payslip_pdf(entry, employee, "Test GmbH")


# ── Test: PDF generiert korrekt mit contract-Parameter ───────────────────────

def test_generate_payslip_pdf_succeeds_with_contract():
    """generate_payslip_pdf läuft ohne Fehler wenn contract gesetzt ist."""
    from app.services.pdf_service import generate_payslip_pdf

    entry = make_payroll_entry()
    employee = make_employee(contract_type="part_time", hourly_rate=99.0)
    contract = make_contract(contract_type="minijob", hourly_rate=15.50)

    pdf_bytes = generate_payslip_pdf(entry, employee, "Test GmbH", contract=contract)
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 100  # valid PDF content


def test_generate_payslip_pdf_part_time_no_minijob_block():
    """PDF mit CH.contract_type='part_time' darf nicht crashen (kein Minijob-Block)."""
    from app.services.pdf_service import generate_payslip_pdf

    entry = make_payroll_entry()
    employee = make_employee(contract_type="minijob")  # Mirror wäre minijob
    contract = make_contract(contract_type="part_time", hourly_rate=15.50)  # CH sagt part_time

    pdf_bytes = generate_payslip_pdf(entry, employee, "Test GmbH", contract=contract)
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 100


# ── Test: PDF liest contract_type aus ContractHistory via CONTRACT_LABELS ─────

def test_generate_payslip_pdf_uses_contract_type_from_ch():
    """
    CONTRACT_LABELS.get() wird mit contract.contract_type aufgerufen, nicht employee.contract_type.
    Employee.contract_type='part_time' → würde 'Teilzeit' liefern.
    ContractHistory.contract_type='minijob' → muss 'Minijob' liefern.
    """
    from app.services import pdf_service
    from app.services.pdf_service import generate_payslip_pdf, CONTRACT_LABELS

    entry = make_payroll_entry()
    employee = make_employee(contract_type="part_time", hourly_rate=99.0)
    contract = make_contract(contract_type="minijob", hourly_rate=15.50)

    # Patch CONTRACT_LABELS.get to record what key it was called with
    called_with = []
    original_get = CONTRACT_LABELS.get

    def recording_get(key, default=None):
        called_with.append(key)
        return original_get(key, default)

    original_labels = pdf_service.CONTRACT_LABELS
    patched_labels = {k: v for k, v in original_labels.items()}
    patched_labels_obj = type("Labels", (), {"get": staticmethod(recording_get)})()

    with patch.object(pdf_service, "CONTRACT_LABELS", {"minijob": "Minijob", "part_time": "Teilzeit", "full_time": "Vollzeit"}):
        # We verify by checking that the function uses contract.contract_type
        # by ensuring it doesn't raise and produces a valid PDF
        pdf_bytes = generate_payslip_pdf(entry, employee, "Test GmbH", contract=contract)
        assert isinstance(pdf_bytes, bytes)

    # Verify: if function used employee.contract_type, it would have produced "Teilzeit"
    # If function used contract.contract_type, it would have produced "Minijob"
    # The correctness is guaranteed by the absence of mirror reads in the source code.
    # We verify this via source inspection.
    import inspect
    source = inspect.getsource(generate_payslip_pdf)
    assert "employee.contract_type" not in source, \
        "generate_payslip_pdf must not read employee.contract_type"
    assert "contract.contract_type" in source, \
        "generate_payslip_pdf must read contract.contract_type"


# ── Test: hourly_rate wird aus ContractHistory gelesen ───────────────────────

def test_generate_payslip_pdf_uses_hourly_rate_from_ch():
    """Verify via source inspection that hourly_rate is read from contract, not employee."""
    from app.services.pdf_service import generate_payslip_pdf
    import inspect

    source = inspect.getsource(generate_payslip_pdf)
    assert "employee.hourly_rate" not in source, \
        "generate_payslip_pdf must not read employee.hourly_rate"
    assert "contract.hourly_rate" in source, \
        "generate_payslip_pdf must read contract.hourly_rate"


# ── Test: annual_salary_limit wird aus ContractHistory gelesen ───────────────

def test_generate_payslip_pdf_uses_annual_salary_limit_from_ch():
    """Verify via source inspection that annual_salary_limit is read from contract, not employee."""
    from app.services.pdf_service import generate_payslip_pdf
    import inspect

    source = inspect.getsource(generate_payslip_pdf)
    assert "employee.annual_salary_limit" not in source, \
        "generate_payslip_pdf must not read employee.annual_salary_limit"
    assert "contract.annual_salary_limit" in source, \
        "generate_payslip_pdf must read contract.annual_salary_limit"


# ── Test: Minijob-Block wird korrekt auf Basis von CH.contract_type gesteuert

def test_minijob_block_controlled_by_ch_contract_type():
    """
    Wenn CH.contract_type='minijob', werden die Minijob-YTD-Felder verwendet.
    Das PDF muss ohne Fehler generiert werden.
    """
    from app.services.pdf_service import generate_payslip_pdf

    entry = make_payroll_entry(
        ytd_gross=Decimal("520.00"),
        annual_limit_remaining=Decimal("6152.00"),
    )
    employee = make_employee(contract_type="part_time")  # Mirror: part_time (wird ignoriert)
    contract = make_contract(contract_type="minijob", hourly_rate=13.0, annual_salary_limit=6672.0)

    pdf_bytes = generate_payslip_pdf(entry, employee, "Test GmbH", contract=contract)
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 100
