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


def _neet_course(db_session, ay_id, subjects):
    from app.modules.academic.models.academic_models import Course, Subject

    course = Course(
        id=_uuid.uuid4(),
        branch_id=_uuid.UUID(BRANCH),
        name="NEET Preparation",
        code="NEET",  # maps to the NEET curriculum sheets
        duration_years=1,
        status="active",
        is_deleted=False,
    )
    db_session.add(course)
    rows = []
    for nm in subjects:
        s = Subject(
            id=_uuid.uuid4(),
            branch_id=_uuid.UUID(BRANCH),
            academic_year_id=ay_id,
            course_id=course.id,
            name=nm,
            code=nm[:3].upper(),
            is_deleted=False,
        )
        db_session.add(s)
        rows.append(s)
    return course, rows


class TestCurriculumBackfill:
    @pytest.mark.usefixtures("seed_data")
    async def test_backfill_fills_empty_neet_subjects(
        self, client, seed_data, db_session
    ):
        from app.modules.academic.models.academic_models import Chapter

        ay_id = seed_data["academic_year"].id
        _, subs = _neet_course(
            db_session, ay_id, ["Physics", "Chemistry", "Botany", "Zoology"]
        )
        await db_session.commit()

        token = await _login(client)
        resp = await client.post(
            f"/api/v1/syllabus/backfill?branch_id={BRANCH}",
            cookies={"access_token": token},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["courses_touched"] == 1
        assert data["subjects_filled"] == 4  # all four map to NEET sheets
        assert data["chapters_added"] > 0
        assert data["topics_added"] > 0

        physics = next(s for s in subs if s.name == "Physics")
        chapters = (
            await db_session.execute(
                select(Chapter).where(
                    Chapter.subject_id == physics.id,
                    Chapter.is_deleted == False,  # noqa: E712
                )
            )
        ).scalars().all()
        assert len(chapters) > 0

    @pytest.mark.usefixtures("seed_data")
    async def test_backfill_idempotent_and_skips_already_filled(
        self, client, seed_data, db_session
    ):
        from app.modules.academic.models.academic_models import Chapter

        ay_id = seed_data["academic_year"].id
        _, subs = _neet_course(db_session, ay_id, ["Physics", "Chemistry"])
        physics = next(s for s in subs if s.name == "Physics")
        await db_session.flush()
        # A syllabus import already loaded a chapter onto Physics — must be left
        # untouched by the backfill.
        db_session.add(
            Chapter(
                id=_uuid.uuid4(),
                branch_id=_uuid.UUID(BRANCH),
                academic_year_id=ay_id,
                subject_id=physics.id,
                name="Hand-loaded Chapter",
                order=0,
                is_deleted=False,
            )
        )
        await db_session.commit()

        token = await _login(client)
        first = (
            await client.post(
                f"/api/v1/syllabus/backfill?branch_id={BRANCH}",
                cookies={"access_token": token},
            )
        ).json()
        # Only Chemistry gets filled; Physics is protected.
        assert first["subjects_filled"] == 1

        phys_chapters = (
            await db_session.execute(
                select(Chapter).where(
                    Chapter.subject_id == physics.id,
                    Chapter.is_deleted == False,  # noqa: E712
                )
            )
        ).scalars().all()
        assert {c.name for c in phys_chapters} == {"Hand-loaded Chapter"}

        # Re-running adds nothing.
        second = (
            await client.post(
                f"/api/v1/syllabus/backfill?branch_id={BRANCH}",
                cookies={"access_token": token},
            )
        ).json()
        assert second["subjects_filled"] == 0
        assert second["chapters_added"] == 0
