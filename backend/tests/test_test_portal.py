"""Test Portal (Phase 1) — ZipGrade CSV upload, PRN matching, rank list.

Builds a batch of four students (three appear in the CSV, one is absent) plus an
unmatched CSV row, then checks the three outcomes, the rank ordering with
absentees last, multi-subject create, idempotent re-upload, and the exporters.
"""

import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.core.storage import LocalFilesystemBackend
from app.modules.student.models.student_models import Student, StudentBatchMapping
from app.modules.tests.models.test_models import TestImportReview, TestSubject
from app.modules.tests.services import ranklist_export, test_service


async def _open_review_row(db_session, test_id):
    return (await db_session.execute(
        select(TestImportReview).where(
            TestImportReview.test_id == test_id,
            TestImportReview.resolved == False,
            TestImportReview.is_deleted == False,
        )
    )).scalar_one()

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


# ─── PR-B: needs-review resolution ───────────────────────────────────────────

async def test_resolve_review_assigns_marks_to_new_student(db_session, seed_data):
    """A wrong-batch / typo row resolves onto a chosen student: they get the
    row's marks, appear in the rank list, and the review row clears."""
    await _make_students(db_session, seed_data)
    test = await _make_test(db_session, seed_data)
    await test_service.upload_result(
        db_session, test.id, seed_data["branch_a"].id, CSV,
        current_user_id=seed_data["admin_user"].id,
    )
    await db_session.commit()

    # A branch student who wasn't in the test's batch (so wasn't matched/absent).
    outsider = Student(
        id=uuid.uuid4(), branch_id=seed_data["branch_a"].id,
        academic_year_id=seed_data["academic_year"].id,
        first_name="Ghost", last_name="Gupta", enrollment_number="PRNZ",
        status="active", is_deleted=False,
    )
    db_session.add(outsider)
    await db_session.commit()

    review = await _open_review_row(db_session, test.id)
    result = await test_service.resolve_review(
        db_session, test.id, review.id, outsider.id, seed_data["branch_a"].id,
        current_user_id=seed_data["admin_user"].id,
    )
    await db_session.commit()

    assert result["resolved"] is True
    assert result["marks_obtained"] == 100  # Ghost G row scored 100/200

    rl = await test_service.get_ranklist(db_session, test.id, seed_data["branch_a"].id)
    assert len(rl["needs_review"]) == 0
    # 100 slots below PRNC(150) at the bottom of the ranked list.
    assert rl["ranked"][-1]["student_id"] == outsider.id
    assert rl["ranked"][-1]["marks_obtained"] == 100

    await db_session.refresh(review)
    assert review.resolved is True
    assert review.resolved_student_id == outsider.id
    assert review.resolved_at is not None


async def test_resolve_review_overwrites_an_absent_student(db_session, seed_data):
    """Resolving onto a student previously marked absent flips them to appeared."""
    ids = await _make_students(db_session, seed_data)
    test = await _make_test(db_session, seed_data)
    await test_service.upload_result(
        db_session, test.id, seed_data["branch_a"].id, CSV,
        current_user_id=seed_data["admin_user"].id,
    )
    await db_session.commit()

    review = await _open_review_row(db_session, test.id)
    # PRND was absent; the reviewer realizes the PRNX row is really PRND.
    await test_service.resolve_review(
        db_session, test.id, review.id, ids["PRND"], seed_data["branch_a"].id,
        current_user_id=seed_data["admin_user"].id,
    )
    await db_session.commit()

    rl = await test_service.get_ranklist(db_session, test.id, seed_data["branch_a"].id)
    assert len(rl["absentees"]) == 0
    assert len(rl["needs_review"]) == 0
    prnd = next(r for r in rl["ranked"] if r["student_id"] == ids["PRND"])
    assert prnd["marks_obtained"] == 100
    assert prnd["absent"] is False


async def test_resolve_review_rejects_double_resolve(db_session, seed_data):
    ids = await _make_students(db_session, seed_data)
    test = await _make_test(db_session, seed_data)
    await test_service.upload_result(
        db_session, test.id, seed_data["branch_a"].id, CSV,
        current_user_id=seed_data["admin_user"].id,
    )
    await db_session.commit()

    review = await _open_review_row(db_session, test.id)
    await test_service.resolve_review(
        db_session, test.id, review.id, ids["PRND"], seed_data["branch_a"].id,
        current_user_id=seed_data["admin_user"].id,
    )
    await db_session.commit()

    with pytest.raises(HTTPException) as exc:
        await test_service.resolve_review(
            db_session, test.id, review.id, ids["PRND"], seed_data["branch_a"].id,
            current_user_id=seed_data["admin_user"].id,
        )
    assert exc.value.status_code == 409


# ─── PR-B: answer-key file (reference only) ──────────────────────────────────

async def test_answer_key_upload_and_download_roundtrip(db_session, seed_data, tmp_path):
    test = await _make_test(db_session, seed_data)
    storage = LocalFilesystemBackend(tmp_path)

    info = await test_service.set_answer_key(
        db_session, test.id, seed_data["branch_a"].id,
        "PCM Answer Key.pdf", b"%PDF-1.4 fake key",
        storage, current_user_id=seed_data["admin_user"].id,
    )
    await db_session.commit()
    assert info["filename"] == "PCM Answer Key.pdf"
    assert str(test.id) in info["answer_key_file"]

    filename, data = await test_service.get_answer_key(
        db_session, test.id, seed_data["branch_a"].id, storage,
    )
    assert filename == "PCM Answer Key.pdf"
    assert data == b"%PDF-1.4 fake key"


async def test_get_answer_key_404_when_unset(db_session, seed_data, tmp_path):
    test = await _make_test(db_session, seed_data)
    storage = LocalFilesystemBackend(tmp_path)
    with pytest.raises(HTTPException) as exc:
        await test_service.get_answer_key(
            db_session, test.id, seed_data["branch_a"].id, storage,
        )
    assert exc.value.status_code == 404
