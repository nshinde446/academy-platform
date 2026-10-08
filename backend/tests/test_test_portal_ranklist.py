"""Test Portal — rank list (spec Section 3) + per-subject columns + history.

Two subjects over two batches, crafted so two students tie on total — exercises
the tie-aware ranking (same total → same rank, next rank skips), the per-subject
columns in the rank list and its exports, and the per-subject breakdown that the
student profile's Test History shows.
"""

import uuid

import pytest
from sqlalchemy import select

from app.modules.academic.models.academic_models import Subject
from app.modules.student.models.student_models import Student, StudentBatchMapping
from app.modules.student.repositories import student_repository
from app.modules.tests.services import ranklist_export, test_service

PHY = uuid.UUID("00000000-0000-0000-0000-000000000050")


async def _student(db_session, seed_data, prn, batch_id) -> uuid.UUID:
    s = Student(
        id=uuid.uuid4(), branch_id=seed_data["branch_a"].id,
        academic_year_id=seed_data["academic_year"].id,
        first_name=prn, last_name="S", enrollment_number=prn,
        status="active", is_deleted=False,
    )
    db_session.add(s)
    db_session.add(StudentBatchMapping(
        student_id=s.id, batch_id=batch_id, branch_id=seed_data["branch_a"].id,
        status="active", is_deleted=False,
    ))
    await db_session.flush()
    return s.id


async def _setup(db_session, seed_data):
    chem = Subject(
        id=uuid.uuid4(), branch_id=seed_data["branch_a"].id,
        academic_year_id=seed_data["academic_year"].id,
        course_id=seed_data["course"].id, name="Chemistry", code="CHEM",
        is_deleted=False,
    )
    db_session.add(chem)
    await db_session.flush()
    a, b = seed_data["batch"].id, seed_data["batch_b"].id
    st = {
        "PRNA": await _student(db_session, seed_data, "PRNA", a),
        "PRNB": await _student(db_session, seed_data, "PRNB", a),
        "PRNC": await _student(db_session, seed_data, "PRNC", b),
        "PRND": await _student(db_session, seed_data, "PRND", b),
    }
    test = await test_service.create_test(
        db_session,
        {
            "name": "PCP Test — ranking",
            "batch_ids": [a, b],
            "subjects": [
                {"subject_id": PHY, "total_marks": 80.0},
                {"subject_id": chem.id, "total_marks": 80.0},
            ],
        },
        current_user_id=seed_data["admin_user"].id,
    )
    await db_session.flush()
    # Totals: A 70+60=130, B 65+65=130 (tie), C 50+50=100, D 40+40=80.
    await test_service.upload_subject_csv(
        db_session, test.id, PHY, seed_data["branch_a"].id,
        b"Student Name,PRN Number,Marks Obtained\nA,PRNA,70\nB,PRNB,65\nC,PRNC,50\nD,PRND,40\n",
        current_user_id=seed_data["admin_user"].id,
    )
    await test_service.upload_subject_csv(
        db_session, test.id, chem.id, seed_data["branch_a"].id,
        b"Student Name,PRN Number,Marks Obtained\nA,PRNA,60\nB,PRNB,65\nC,PRNC,50\nD,PRND,40\n",
        current_user_id=seed_data["admin_user"].id,
    )
    await db_session.flush()
    return test, chem, st


@pytest.mark.usefixtures("seed_data")
async def test_ranklist_tie_aware_and_subject_columns(db_session, seed_data):
    test, chem, st = await _setup(db_session, seed_data)
    rl = await test_service.get_ranklist(db_session, test.id, seed_data["branch_a"].id)

    # Tie-aware: two students at 130 both rank 1; next (100) is rank 3, then 4.
    by_prn = {r["prn"]: r for r in rl["ranked"]}
    assert by_prn["PRNA"]["rank"] == 1
    assert by_prn["PRNB"]["rank"] == 1
    assert by_prn["PRNC"]["rank"] == 3   # skips 2
    assert by_prn["PRND"]["rank"] == 4
    assert by_prn["PRNA"]["marks_obtained"] == 130

    # Per-subject columns present and populated.
    assert [s["subject_name"] for s in rl["subjects"]] == ["Physics", "Chemistry"]
    assert by_prn["PRNA"]["subject_marks"] == {"Physics": 70, "Chemistry": 60}
    assert rl["total_marks"] == 160


@pytest.mark.usefixtures("seed_data")
async def test_ranklist_exports_carry_subject_columns(db_session, seed_data):
    test, chem, st = await _setup(db_session, seed_data)
    rl = await test_service.get_ranklist(db_session, test.id, seed_data["branch_a"].id)

    html = ranklist_export.ranklist_html(brand="Matrix Science Academy", ranklist=rl)
    assert "<th class='c'>Physics</th>" in html
    assert "<th class='c'>Chemistry</th>" in html
    assert "<th>Total</th>" in html

    xlsx = ranklist_export.ranklist_xlsx(brand="Matrix Science Academy", ranklist=rl)
    assert xlsx[:2] == b"PK"  # a real .xlsx (zip) came back


@pytest.mark.usefixtures("seed_data")
async def test_student_history_has_subject_breakdown(db_session, seed_data):
    test, chem, st = await _setup(db_session, seed_data)
    await db_session.commit()
    history = await student_repository.get_test_history(
        db_session, st["PRNA"], seed_data["branch_a"].id,
    )
    row = next(h for h in history if h["test_id"] == test.id)
    assert row["subject_marks"] == {"Physics": 70, "Chemistry": 60}
    assert row["marks_obtained"] == 130
    assert row["is_absent"] is False
