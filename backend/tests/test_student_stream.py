import uuid as _uuid

import pytest
from sqlalchemy import select

BRANCH = "00000000-0000-0000-0000-000000000001"


async def _login(client) -> str:
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.com", "password": "Admin123!"},
    )
    return resp.cookies["access_token"]


def test_default_stream_from_target():
    from app.modules.student.services.student_service import default_stream

    assert default_stream("NEET") == "PCB"
    assert default_stream("JEE-Main") == "PCM"
    assert default_stream("Both") == "PCMB"
    assert default_stream("MHT-CET") == "PCB"  # most are PCB
    assert default_stream("Foundation") is None
    assert default_stream(None) is None


def test_stream_includes_subject_rule():
    from app.modules.student.services.student_service import (
        stream_includes_subject as inc,
    )

    # Physics/Chemistry common to all streams.
    for s in ("PCM", "PCB", "PCMB"):
        assert inc(s, "Physics") and inc(s, "Chemistry")
    # Maths only PCM/PCMB; Biology only PCB/PCMB.
    assert inc("PCM", "Mathematics") and not inc("PCB", "Mathematics")
    assert inc("PCB", "Biology") and not inc("PCM", "Biology")
    assert inc("PCMB", "Mathematics") and inc("PCMB", "Biology")
    # No stream -> nothing filtered.
    assert inc(None, "Mathematics")


def _csv_stream(*lines: str) -> bytes:
    header = "Name,Class,Target,Batch,Roll No,Stream"
    return ("\n".join([header, *lines]) + "\n").encode("utf-8")


class TestStreamImport:
    @pytest.mark.usefixtures("seed_data")
    async def test_import_persists_explicit_and_defaulted_stream(
        self, client, seed_data, db_session
    ):
        from app.modules.student.models.student_models import Student

        token = await _login(client)
        content = _csv_stream(
            "Asha,12,MHT-CET,BATCH-A,ST-1,PCM",  # explicit PCM
            "Bina,12,MHT-CET,BATCH-A,ST-2,",      # blank -> default PCB
        )
        resp = await client.post(
            f"/api/v1/students/import?branch_id={BRANCH}",
            files={"file": ("s.csv", content, "text/csv")},
            cookies={"access_token": token},
        )
        assert resp.json()["imported"] == 2
        rows = (
            await db_session.execute(
                select(Student).where(
                    Student.enrollment_number.in_(["ST-1", "ST-2"])
                )
            )
        ).scalars().all()
        by_enr = {s.enrollment_number: s.stream for s in rows}
        assert by_enr["ST-1"] == "PCM"
        assert by_enr["ST-2"] == "PCB"  # MHT-CET fallback

    @pytest.mark.usefixtures("seed_data")
    async def test_mhtcet_creates_union_subjects_and_syllabus_filters(
        self, client, seed_data, db_session
    ):
        from app.modules.academic.models.academic_models import Course, Subject
        from app.modules.student.models.student_models import Student

        token = await _login(client)
        content = _csv_stream(
            "Cee,12,MHT-CET,MHT-NEW,ST-10,",      # PCB (default)
            "Dee,12,MHT-CET,MHT-NEW,ST-11,PCM",   # PCM
        )
        resp = await client.post(
            f"/api/v1/students/import?branch_id={BRANCH}&create_missing_batches=true",
            files={"file": ("s.csv", content, "text/csv")},
            cookies={"access_token": token},
        )
        data = resp.json()
        assert data["batches_created"] == ["MHT-NEW"]
        # Course carries the union of all four subjects.
        assert data["subjects_created"] == 4

        course = (
            await db_session.execute(
                select(Course).where(
                    Course.code == "MHT-CET", Course.branch_id == _uuid.UUID(BRANCH)
                )
            )
        ).scalar_one()
        names = {
            s.name
            for s in (
                await db_session.execute(
                    select(Subject).where(Subject.course_id == course.id)
                )
            ).scalars().all()
        }
        assert names == {"Physics", "Chemistry", "Mathematics", "Biology"}

        students = (
            await db_session.execute(
                select(Student).where(
                    Student.enrollment_number.in_(["ST-10", "ST-11"])
                )
            )
        ).scalars().all()
        by_enr = {s.enrollment_number: s for s in students}

        # PCB student: Physics/Chemistry/Biology, NO Maths; curriculum loaded.
        pcb_resp = await client.get(
            f"/api/v1/students/{by_enr['ST-10'].id}/syllabus?branch_id={BRANCH}",
            cookies={"access_token": token},
        )
        pcb = pcb_resp.json()
        assert pcb["stream"] == "PCB"
        pcb_subjects = {s["subject_name"] for s in pcb["subjects"]}
        assert pcb_subjects == {"Physics", "Chemistry", "Biology"}
        assert all(s["chapter_count"] > 0 for s in pcb["subjects"])

        # PCM student: Physics/Chemistry/Mathematics, NO Biology.
        pcm_resp = await client.get(
            f"/api/v1/students/{by_enr['ST-11'].id}/syllabus?branch_id={BRANCH}",
            cookies={"access_token": token},
        )
        pcm_subjects = {s["subject_name"] for s in pcm_resp.json()["subjects"]}
        assert pcm_subjects == {"Physics", "Chemistry", "Mathematics"}


class TestStreamOverride:
    @pytest.mark.usefixtures("seed_data")
    async def test_admin_can_override_stream_and_invalid_is_rejected(
        self, client, seed_data, db_session
    ):
        from app.modules.student.models.student_models import Student

        token = await _login(client)
        # Import one MHT-CET student (defaults PCB), then override to PCMB.
        await client.post(
            f"/api/v1/students/import?branch_id={BRANCH}",
            files={
                "file": ("s.csv", _csv_stream("Eve,12,MHT-CET,BATCH-A,ST-20,"), "text/csv")
            },
            cookies={"access_token": token},
        )
        sid = (
            await db_session.execute(
                select(Student.id).where(Student.enrollment_number == "ST-20")
            )
        ).scalar_one()

        ok = await client.patch(
            f"/api/v1/students/{sid}?branch_id={BRANCH}",
            json={"stream": "PCMB"},
            cookies={"access_token": token},
        )
        assert ok.status_code == 200
        assert ok.json()["stream"] == "PCMB"

        bad = await client.patch(
            f"/api/v1/students/{sid}?branch_id={BRANCH}",
            json={"stream": "XYZ"},
            cookies={"access_token": token},
        )
        assert bad.status_code == 422
