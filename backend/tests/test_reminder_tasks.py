"""
Tests für app.tasks.reminder_tasks – Diensterinnerung respektiert die
Benachrichtigungs-Präferenzen des Mitarbeiters (shift_reminder-Event).
"""
import uuid
from datetime import date, time, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from app.models.employee import Employee
from app.models.shift import Shift
from app.models.notification import NotificationLog
from app.tasks.reminder_tasks import _do_send_reminder


@pytest.mark.asyncio
async def test_reminder_skipped_when_preference_off(monkeypatch, engine, db, tenant):
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    monkeypatch.setattr("app.core.database.AsyncSessionLocal", session_factory)

    emp = Employee(
        tenant_id=tenant.id,
        first_name="Nina",
        last_name="Test",
        email="nina@test.de",
        contract_type="minijob",
        hourly_rate=13.0,
        vacation_days=0,
        is_active=True,
        notification_prefs={"events": {"shift_reminder": False}},
    )
    db.add(emp)
    await db.commit()
    await db.refresh(emp)

    shift = Shift(
        tenant_id=tenant.id,
        employee_id=emp.id,
        date=date.today() + timedelta(days=1),
        start_time=time(9, 0),
        end_time=time(17, 0),
    )
    db.add(shift)
    await db.commit()
    await db.refresh(shift)

    await _do_send_reminder(str(shift.id), hours_before=1.0, shift_type_name=None)

    log_result = await db.execute(select(NotificationLog).where(NotificationLog.event_type == "shift_reminder"))
    assert log_result.scalars().all() == []


@pytest.mark.asyncio
async def test_reminder_dispatches_when_enabled(monkeypatch, engine, db, tenant):
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    monkeypatch.setattr("app.core.database.AsyncSessionLocal", session_factory)

    emp = Employee(
        tenant_id=tenant.id,
        first_name="Nina",
        last_name="Test",
        email="nina@test.de",
        contract_type="minijob",
        hourly_rate=13.0,
        vacation_days=0,
        is_active=True,
        notification_prefs={"events": {"shift_reminder": True}},
    )
    db.add(emp)
    await db.commit()
    await db.refresh(emp)

    shift = Shift(
        tenant_id=tenant.id,
        employee_id=emp.id,
        date=date.today() + timedelta(days=1),
        start_time=time(9, 0),
        end_time=time(17, 0),
    )
    db.add(shift)
    await db.commit()
    await db.refresh(shift)

    await _do_send_reminder(str(shift.id), hours_before=1.0, shift_type_name="Schulbegleitung")

    log_result = await db.execute(select(NotificationLog).where(NotificationLog.event_type == "shift_reminder"))
    logs = log_result.scalars().all()
    assert len(logs) == 1
    assert logs[0].employee_id == emp.id
    assert "Schulbegleitung" in (logs[0].subject or "")


@pytest.mark.asyncio
async def test_reminder_noop_for_shift_without_employee(monkeypatch, engine, db, tenant):
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    monkeypatch.setattr("app.core.database.AsyncSessionLocal", session_factory)

    shift = Shift(
        tenant_id=tenant.id,
        date=date.today() + timedelta(days=1),
        start_time=time(9, 0),
        end_time=time(17, 0),
    )
    db.add(shift)
    await db.commit()
    await db.refresh(shift)

    # Darf nicht crashen, auch ohne zugewiesenen Mitarbeiter
    await _do_send_reminder(str(shift.id), hours_before=1.0, shift_type_name=None)

    log_result = await db.execute(select(NotificationLog))
    assert log_result.scalars().all() == []
