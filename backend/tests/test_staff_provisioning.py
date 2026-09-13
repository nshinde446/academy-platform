"""Staff device-provisioning — dry-run + enqueue mirror the student push, keyed
on Staff.emp_code (9xxxx). Service-level (bypasses the env-gated routes)."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.attendance.models.provisioning_models import (
    CMD_SET_USER_INFO,
    DeviceCommand,
)
from app.modules.attendance.services import provisioning_service as prov
from app.modules.staff.models.staff_models import Department, Staff

BRANCH_A = uuid.UUID("00000000-0000-0000-0000-000000000001")
DEV = "DEV-TEST-1"


async def _dept(db: AsyncSession) -> Department:
    d = Department(
        branch_id=BRANCH_A, name="MSA-Teachers", id_range_start=91000, id_range_end=91999
    )
    db.add(d)
    await db.flush()
    return d


async def _staff(db: AsyncSession, dept: Department, emp_code: str, first="Ratan") -> Staff:
    s = Staff(
        branch_id=BRANCH_A, emp_code=emp_code, first_name=first, last_name="Singh",
        department_id=dept.id,
    )
    db.add(s)
    await db.flush()
    return s


async def test_staff_dry_run_and_enqueue(db_session: AsyncSession, seed_data):
    dept = await _dept(db_session)
    numeric = await _staff(db_session, dept, "91000", first="Numeric")
    legacy = await _staff(db_session, dept, "AB12", first="Legacy")  # non-numeric userId

    # Dry-run: numeric staff → create; non-numeric → skipped (device needs numeric id).
    dry = await prov.render_dry_run_staff(db_session, BRANCH_A, DEV, [numeric.id, legacy.id])
    assert dry.to_create == 1
    assert dry.skipped == 1
    assert dry.dev_id == DEV

    # Push: one command enqueued for the numeric staff, none to the device yet.
    push = await prov.enqueue_staff(db_session, BRANCH_A, DEV, [numeric.id, legacy.id])
    assert push.enqueued == 1
    assert push.skipped == 1

    cmd = (await db_session.execute(
        select(DeviceCommand).where(
            DeviceCommand.dev_id == DEV, DeviceCommand.vendor_user_id == "91000"
        )
    )).scalar_one()
    assert cmd.command == CMD_SET_USER_INFO
    assert cmd.student_id is None            # staff registration, not a student
    assert cmd.payload["users"][0]["userId"] == "91000"
    assert "face" not in cmd.payload["users"][0]  # never carries biometrics

    # Idempotent: re-pushing the same staff enqueues nothing (already in flight).
    again = await prov.enqueue_staff(db_session, BRANCH_A, DEV, [numeric.id])
    assert again.enqueued == 0
    assert again.skipped == 1


async def test_staff_dry_run_marks_update_when_on_device(db_session: AsyncSession, seed_data):
    from app.modules.attendance.models.provisioning_models import DeviceUser

    dept = await _dept(db_session)
    s = await _staff(db_session, dept, "91005")
    # Seed the device mirror as if 91005 is already on the terminal.
    db_session.add(DeviceUser(
        branch_id=BRANCH_A, dev_id=DEV, vendor_user_id="91005", name="Old Name",
    ))
    await db_session.flush()

    dry = await prov.render_dry_run_staff(db_session, BRANCH_A, DEV, [s.id])
    assert dry.to_update == 1
    assert dry.to_create == 0
