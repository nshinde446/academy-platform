"""Test Portal (Phase 1) — ZipGrade CSV upload, PRN matching, rank list.

Builds a batch of four students (three appear in the CSV, one is absent) plus an
unmatched CSV row, then checks the three outcomes, the rank ordering with
absentees last, multi-subject create, idempotent re-upload, and the exporters.
"""

import uuid

from sqlalchemy import select

from app.modules.student.models.student_models import Student, StudentBatchMapping
from app.modules.tests.models.test_models import TestImportReview, TestSubject
from app.modules.tests.services import ranklist_export, test_service

# ZipGrade-standard export headers (tolerant parser resolves these).
CSV = (
    "Student Name,Student ID,Earned Points,Possible Points,Percent Correct\n"
    "Bhavna B,PRNB,180,200,90\n"
    "Aarohi A,PRNA,186,200,93\n"
    "Chirag C,PRNC,150,200,75\n"
    "Ghost G,PRNX,100,200,50\n"  # PRNX not in batch -> needs review
).encode("utf-8")


async def _make_students(db_session, seed_data):
    """Four active students (PRNA..PRND) enrolled in the seed batch."""
    branch = seed_data["branch_a"]
    batch = seed_data["batch"]
    ids = {}
    for i, prn in enumerate(["PRNA", "PRNB", "PRNC", "PRND"]):
        s = Student(
            id=uuid.uuid4(), branch_id=branch.id,
            academic_year_id=seed_data["academic_year"].id,
            first_name=prn, last_name="Student", enrollment_number=prn,
            status="active", is_deleted=False,
        )
        db_session.add(s)
        db_session.add(StudentBatchMapping(
            student_id=s.id, batch_id=batch.id, branch_id=branch.id,
            status="active", is_deleted=False,
        ))
        ids[prn] = s.id
    await db_session.commit()
    return ids


async def _make_test(db_session, seed_data, total_marks=200.0):
    test = await test_service.create_test(
        db_session,
        {
            "name": "11th CET PCM Test",
            "batch_id": seed_data["batch"].id,
            "subject_id": seed_data["subject"].id,
            "total_marks": total_marks,
        },
        current_user_id=seed_data["admin_user"].id,
    )
    await db_session.commit()
    return test


def test_parse_real_zipgrade_header():
    """Real ZipGrade export uses ExternalID as the PRN (NOT ZipGradeID) and
    EarnedPts/PossiblePts/PercentCorrect, with no spaces in headers."""
    from app.modules.tests.services import zipgrade_csv

    raw = (
        "QuizName,QuizClass,FirstName,LastName,ZipGradeID,ExternalID,"
        "EarnedPts,PossiblePts,PercentCorrect\n"
        '"RAVET 11TH JEE","","Janhavi","Deshmukh",9999999,"2807024",'
        "27.0,80.0,33.8\n"
    ).encode("utf-8")
    rows = zipgrade_csv.parse_zipgrade_csv(raw)
    assert len(rows) == 1
    r = rows[0]
    assert r["prn"] == "2807024"          # ExternalID — not ZipGradeID 9999999
    assert r["name"] == "Janhavi Deshmukh"
    assert r["score"] == 27.0
    assert r["total"] == 80.0
    assert r["percent"] == 33.8


async def test_upload_matches_flags_and_marks_absent(db_session, seed_data):
    await _make_students(db_session, seed_data)
    test = await _make_test(db_session, seed_data)

    summary = await test_service.upload_result(
        db_session, test.id, seed_data["branch_a"].id, CSV,
        current_user_id=seed_data["admin_user"].id,
    )
    await db_session.commit()

    assert summary["matched"] == 3          # PRNA/B/C
    assert summary["needs_review"] == 1     # PRNX
    assert summary["absent"] == 1           # PRND
    assert summary["total_rows"] == 4


async def test_ranklist_orders_desc_absentees_last(db_session, seed_data):
    await _make_students(db_session, seed_data)
    test = await _make_test(db_session, seed_data)
    await test_service.upload_result(
        db_session, test.id, seed_data["branch_a"].id, CSV,
        current_user_id=seed_data["admin_user"].id,
    )
    await db_session.commit()

    rl = await test_service.get_ranklist(db_session, test.id, seed_data["branch_a"].id)
    # Ranked highest -> lowest: PRNA(186), PRNB(180), PRNC(150).
    assert [r["prn"] for r in rl["ranked"]] == ["PRNA", "PRNB", "PRNC"]
    assert [r["rank"] for r in rl["ranked"]] == [1, 2, 3]
    # PRND absent, at the bottom, excluded from ranking.
    assert [a["prn"] for a in rl["absentees"]] == ["PRND"]
    assert rl["absentees"][0]["absent"] is True
    # One unmatched row awaiting review.
    assert len(rl["needs_review"]) == 1
    assert rl["needs_review"][0]["csv_prn"] == "PRNX"


async def test_reupload_is_idempotent(db_session, seed_data):
    await _make_students(db_session, seed_data)
    test = await _make_test(db_session, seed_data)
    for _ in range(2):
        await test_service.upload_result(
            db_session, test.id, seed_data["branch_a"].id, CSV,
            current_user_id=seed_data["admin_user"].id,
        )
        await db_session.commit()

    rl = await test_service.get_ranklist(db_session, test.id, seed_data["branch_a"].id)
    assert len(rl["ranked"]) == 3
    assert len(rl["absentees"]) == 1
    # Review rows are not duplicated across re-uploads.
    open_rows = (await db_session.execute(
        select(TestImportReview).where(
            TestImportReview.test_id == test.id,
            TestImportReview.is_deleted == False,
        )
    )).scalars().all()
    assert len(open_rows) == 1


async def test_blank_prn_goes_to_review_not_name_matched(db_session, seed_data):
    """Matching is by PRN only — a row scanned without a PRN is flagged for
    review even when its name matches a student in the batch."""
    await _make_students(db_session, seed_data)  # names "PRNA Student" … in batch
    test = await _make_test(db_session, seed_data)
    csv = (
        "Student Name,Student ID,Earned Points,Possible Points\n"
        "PRNA Student,,190,200\n"     # blank PRN, name in batch -> STILL review
    ).encode("utf-8")
    summary = await test_service.upload_result(
        db_session, test.id, seed_data["branch_a"].id, csv,
        current_user_id=seed_data["admin_user"].id,
    )
    await db_session.commit()
    assert summary["matched"] == 0
    assert summary["needs_review"] == 1

    rl = await test_service.get_ranklist(db_session, test.id, seed_data["branch_a"].id)
    assert rl["ranked"] == []            # nobody matched by PRN
    assert len(rl["absentees"]) == 4     # all four had no PRN-matched row
    assert len(rl["needs_review"]) == 1


async def test_multi_subject_create(db_session, seed_data):
    test = await test_service.create_test(
        db_session,
        {
            "name": "PCM multi",
            "batch_id": seed_data["batch"].id,
            "subject_ids": [seed_data["subject"].id],
            "total_marks": 100.0,
        },
        current_user_id=seed_data["admin_user"].id,
    )
    await db_session.commit()
    assert test.subject_id == seed_data["subject"].id
    rows = (await db_session.execute(
        select(TestSubject).where(TestSubject.test_id == test.id)
    )).scalars().all()
    assert len(rows) == 1


async def test_exporters_build_bytes(db_session, seed_data):
    await _make_students(db_session, seed_data)
    test = await _make_test(db_session, seed_data)
    await test_service.upload_result(
        db_session, test.id, seed_data["branch_a"].id, CSV,
        current_user_id=seed_data["admin_user"].id,
    )
    await db_session.commit()
    rl = await test_service.get_ranklist(db_session, test.id, seed_data["branch_a"].id)

    xlsx = ranklist_export.ranklist_xlsx(brand="Matrix Science Academy", ranklist=rl)
    assert xlsx[:2] == b"PK"
    html = ranklist_export.ranklist_html(brand="Matrix Science Academy", ranklist=rl)
    for col in ("Rank", "PRN", "Student Name", "Marks"):
        assert col in html
    assert "PRNA" in html and "ABSENT" in html
