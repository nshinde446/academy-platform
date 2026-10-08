"""Test Portal — per-subject marks CSV upload (spec Section 2).

One CSV per subject (Name, PRN, Marks): PRNs match across the test's batches →
per-subject marks; batch students missing from a CSV are absent for that subject;
unmatched PRNs go to review; marks over the subject total are errors. The aggregate
StudentMark (sum across subjects) is rebuilt so the rank list stays in sync.
"""

import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.modules.academic.models.academic_models import Subject
from app.modules.student.models.student_models import Student, StudentBatchMapping
from app.modules.tests.models.test_models import (
    StudentMark,
    TestImportReview,
    TestSubjectMark,
)
from app.modules.tests.services import test_service

PHY = uuid.UUID("00000000-0000-0000-0000-000000000050")  # seed subject (Physics)


async def _chem_subject(db_session, seed_data) -> Subject:
    chem = Subject(
        id=uuid.uuid4(), branch_id=seed_data["branch_a"].id,
        academic_year_id=seed_data["academic_year"].id,
        course_id=seed_data["course"].id, name="Chemistry", code="CHEM",
        is_deleted=False,
    )
    db_session.add(chem)
    await db_session.flush()
    return chem


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
    """A PCP test over two batches, two subjects (Physics+Chemistry, 80 each),
    four students (two per batch)."""
    chem = await _chem_subject(db_session, seed_data)
    a, b = seed_data["batch"].id, seed_data["batch_b"].id
    students = {
        "PRNA": await _student(db_session, seed_data, "PRNA", a),
        "PRNB": await _student(db_session, seed_data, "PRNB", a),
        "PRNC": await _student(db_session, seed_data, "PRNC", b),
        "PRND": await _student(db_session, seed_data, "PRND", b),
    }
    test = await test_service.create_test(
        db_session,
        {
            "name": "PCP Test — per subject",
            "batch_ids": [a, b],
            "subjects": [
                {"subject_id": PHY, "total_marks": 80.0},
                {"subject_id": chem.id, "total_marks": 80.0},
            ],
        },
        current_user_id=seed_data["admin_user"].id,
    )
    await db_session.flush()
    return test, chem, students


async def _upload(db_session, seed_data, test, subject_id, csv: str):
    return await test_service.upload_subject_csv(
        db_session, test.id, subject_id, seed_data["branch_a"].id,
        csv.encode("utf-8"), current_user_id=seed_data["admin_user"].id,
    )


async def _agg(db_session, test_id, student_id):
    return (await db_session.execute(
        select(StudentMark).where(
            StudentMark.test_id == test_id,
            StudentMark.student_id == student_id,
            StudentMark.is_deleted == False,
        )
    )).scalar_one()


@pytest.mark.usefixtures("seed_data")
async def test_subject_upload_matches_absent_unmatched_and_aggregates(db_session, seed_data):
    test, chem, st = await _setup(db_session, seed_data)

    phys = (
        "Student Name,PRN Number,Marks Obtained\n"
        "Aarav,PRNA,70\n"
        "Sneha,PRNB,65\n"
        "Ghost,PRNX,50\n"   # unmatched
        # PRNC, PRND not present -> absent for Physics
    )
    out = await _upload(db_session, seed_data, test, PHY, phys)
    assert out["matched"] == 2
    assert out["unmatched"] == 1
    assert out["absent"] == 2
    assert out["errors"] == []
    assert out["all_subjects_uploaded"] is False  # Chemistry still pending

    # per-subject rows
    marks = (await db_session.execute(
        select(TestSubjectMark).where(
            TestSubjectMark.test_id == test.id,
            TestSubjectMark.subject_id == PHY,
            TestSubjectMark.is_deleted == False,
        )
    )).scalars().all()
    by_student = {m.student_id: m for m in marks}
    assert by_student[st["PRNA"]].marks_obtained == 70 and not by_student[st["PRNA"]].absent
    assert by_student[st["PRNC"]].absent is True

    # unmatched tagged with the subject
    review = (await db_session.execute(
        select(TestImportReview).where(
            TestImportReview.test_id == test.id, TestImportReview.is_deleted == False,
        )
    )).scalars().all()
    assert len(review) == 1 and review[0].csv_prn == "PRNX"
    assert review[0].raw_row["__subject_id__"] == str(PHY)

    # aggregate StudentMark reflects Physics only so far
    assert (await _agg(db_session, test.id, st["PRNA"])).marks_obtained == 70
    assert (await _agg(db_session, test.id, st["PRNC"])).is_absent is True  # absent everywhere yet

    # Upload Chemistry for everyone -> all uploaded, totals summed.
    chem_csv = (
        "Student Name,PRN Number,Marks Obtained\n"
        "Aarav,PRNA,60\nSneha,PRNB,55\nChirag,PRNC,50\nDiya,PRND,40\n"
    )
    out2 = await _upload(db_session, seed_data, test, chem.id, chem_csv)
    assert out2["matched"] == 4 and out2["absent"] == 0
    assert out2["all_subjects_uploaded"] is True

    assert (await _agg(db_session, test.id, st["PRNA"])).marks_obtained == 130  # 70+60
    pc = await _agg(db_session, test.id, st["PRNC"])
    assert pc.marks_obtained == 50 and pc.is_absent is False  # present in Chemistry
    assert (await _agg(db_session, test.id, st["PRNA"])).max_marks == 160


@pytest.mark.usefixtures("seed_data")
async def test_marks_above_total_are_errored_and_skipped(db_session, seed_data):
    test, chem, st = await _setup(db_session, seed_data)
    csv = (
        "Student Name,PRN Number,Marks Obtained\n"
        "Aarav,PRNA,90\n"   # > 80 -> error, skipped
        "Sneha,PRNB,65\n"
    )
    out = await _upload(db_session, seed_data, test, PHY, csv)
    assert out["matched"] == 1              # only PRNB saved
    assert len(out["errors"]) == 1 and "exceed" in out["errors"][0]
    # PRNA fell through to absent (no valid mark row for them)
    row = (await db_session.execute(
        select(TestSubjectMark).where(
            TestSubjectMark.test_id == test.id,
            TestSubjectMark.subject_id == PHY,
            TestSubjectMark.student_id == st["PRNA"],
            TestSubjectMark.is_deleted == False,
        )
    )).scalar_one()
    assert row.absent is True


@pytest.mark.usefixtures("seed_data")
async def test_reupload_replaces_prior_subject_marks(db_session, seed_data):
    test, chem, st = await _setup(db_session, seed_data)
    await _upload(db_session, seed_data, test, PHY,
                  "Student Name,PRN Number,Marks Obtained\nAarav,PRNA,70\n")
    # Re-upload Physics with a corrected mark.
    await _upload(db_session, seed_data, test, PHY,
                  "Student Name,PRN Number,Marks Obtained\nAarav,PRNA,75\n")
    live = (await db_session.execute(
        select(TestSubjectMark).where(
            TestSubjectMark.test_id == test.id,
            TestSubjectMark.subject_id == PHY,
            TestSubjectMark.student_id == st["PRNA"],
            TestSubjectMark.is_deleted == False,
        )
    )).scalars().all()
    assert len(live) == 1 and live[0].marks_obtained == 75
    assert (await _agg(db_session, test.id, st["PRNA"])).marks_obtained == 75


@pytest.mark.usefixtures("seed_data")
async def test_upload_rejects_subject_not_on_test(db_session, seed_data):
    test, chem, st = await _setup(db_session, seed_data)
    stray = uuid.uuid4()
    with pytest.raises(HTTPException) as ei:
        await _upload(db_session, seed_data, test, stray,
                      "Student Name,PRN Number,Marks Obtained\nAarav,PRNA,70\n")
    assert ei.value.status_code == 422


@pytest.mark.usefixtures("seed_data")
async def test_upload_rejects_bad_csv(db_session, seed_data):
    test, chem, st = await _setup(db_session, seed_data)
    with pytest.raises(HTTPException) as ei:
        await _upload(db_session, seed_data, test, PHY, "Foo,Bar\n1,2\n")
    assert ei.value.status_code == 422
