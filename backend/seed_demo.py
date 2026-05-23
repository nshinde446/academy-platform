"""Seed a realistic demo dataset covering all Lectures + Insights scenarios.

Idempotent: every row created here is tagged with [seed-demo] in its notes
field (where one exists). A second run is a no-op unless you delete the
tagged rows first.

Prerequisite: seed_admin.py must have run (creates the MAIN branch).

Run with:
    cd backend
    python seed_demo.py

After seeding, log in as admin@academy.com / Admin123! and visit:
    /lectures   — should show 10 lectures across all statuses
    /insights   — KPIs should populate; teacher leaderboard & syllabus too

Layout it creates:
    Branch:          MAIN (existing)
    Academic year:   2025-26
    Course:          NEET Preparation (NEET-PREP)
    Subjects:        Physics (PHY), Chemistry (CHEM)
    Chapters:        2 per subject (4 total)
    Topics:          3 per chapter (12 total) — drives syllabus coverage
    Classroom:       Room 101 (cap 60)
    Teachers:        Rahul Sharma, Priya Nair, Asha Kulkarni
    Batches:         NEET 2025-A, NEET 2025-B  (both mapped to Phy+Chem)
    Lectures:        10 covering Scenarios 1-10 from docs/lectures-and-insights.md
    Sessions:        3 (makeup linked, pure ad-hoc, merged)
"""

import asyncio
import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import async_session_factory
from app.modules.auth.models.auth_models import Branch
from app.modules.academic.models.academic_models import (
    AcademicYear,
    Chapter,
    Course,
    Subject,
    Topic,
)
from app.modules.batch.models.batch_models import Batch, BatchSubjectMapping
from app.modules.classroom.models.classroom_models import Classroom
from app.modules.teacher.models.teacher_models import Teacher
from app.modules.lectures.models.lecture_models import (
    Lecture,
    LectureAttendanceMapping,
    LectureSession,
    LectureSessionBatch,
    LectureSessionPlan,
)
from app.modules.student.models.student_models import (
    Student,
    StudentBatchMapping,
)
from app.modules.tests.models.test_models import StudentMark, Test

DEMO_TAG = "[seed-demo]"


async def _find_or_create(
    session: AsyncSession, model, defaults: dict, **lookup
):
    """Find by lookup fields; create with lookup + defaults if missing.

    Tolerates multiple rows (takes the first) since dev DBs accumulate
    duplicates from earlier ad-hoc testing.
    """
    where = [getattr(model, k) == v for k, v in lookup.items()]
    where.append(model.is_deleted == False)
    result = await session.execute(select(model).where(*where).limit(1))
    obj = result.scalars().first()
    if obj is not None:
        return obj, False
    obj = model(**lookup, **defaults)
    session.add(obj)
    await session.flush()
    return obj, True


def _at(base: datetime, days: int, hour: int) -> datetime:
    """Return base + days at hour:00 UTC, seconds zeroed."""
    d = base + timedelta(days=days)
    return d.replace(hour=hour, minute=0, second=0, microsecond=0)


async def seed():
    async with async_session_factory() as session:
        # ---- Idempotency guard. Skip if a tagged, non-deleted row exists —
        # soft-deleted rows (from --reset) shouldn't block re-seeding.
        existing = await session.execute(
            select(Lecture).where(
                Lecture.notes.like(f"%{DEMO_TAG}%"),
                Lecture.is_deleted == False,
            )
        )
        if existing.scalars().first() is not None:
            print(
                f"Demo data already seeded (rows tagged '{DEMO_TAG}' found). "
                f"Delete tagged lectures + sessions to re-seed."
            )
            return

        # ---- Branch (must exist from seed_admin)
        result = await session.execute(
            select(Branch).where(Branch.code == "MAIN", Branch.is_deleted == False)
        )
        branch = result.scalar_one_or_none()
        if branch is None:
            print("ERROR: MAIN branch not found. Run `python seed_admin.py` first.")
            return

        # ---- Academic year
        ay, _ = await _find_or_create(
            session,
            AcademicYear,
            defaults={
                "start_year": 2025,
                "end_year": 2026,
                "status": "active",
                "is_deleted": False,
            },
            branch_id=branch.id,
            name="2025-26",
        )

        # ---- Course
        course, _ = await _find_or_create(
            session,
            Course,
            defaults={
                "code": "NEET-PREP",
                "duration_years": 2,
                "description": "Demo NEET preparation course",
                "status": "active",
                "is_deleted": False,
            },
            branch_id=branch.id,
            name="NEET Preparation",
        )

        # ---- Subjects
        physics, _ = await _find_or_create(
            session,
            Subject,
            defaults={
                "code": "PHY",
                "academic_year_id": ay.id,
                "course_id": course.id,
                "status": "active",
                "is_deleted": False,
            },
            branch_id=branch.id,
            name="Physics",
        )
        chemistry, _ = await _find_or_create(
            session,
            Subject,
            defaults={
                "code": "CHEM",
                "academic_year_id": ay.id,
                "course_id": course.id,
                "status": "active",
                "is_deleted": False,
            },
            branch_id=branch.id,
            name="Chemistry",
        )

        # ---- Chapters: 2 per subject
        chapters = {}
        for subj, ch_names in [
            (physics, ["Mechanics", "Optics"]),
            (chemistry, ["Atomic Structure", "Chemical Bonding"]),
        ]:
            for order, name in enumerate(ch_names, start=1):
                ch, _ = await _find_or_create(
                    session,
                    Chapter,
                    defaults={
                        "academic_year_id": ay.id,
                        "subject_id": subj.id,
                        "order": order,
                        "status": "active",
                        "is_deleted": False,
                    },
                    branch_id=branch.id,
                    name=name,
                )
                chapters[name] = ch

        # ---- Topics: 3 per chapter (12 total = denominator for syllabus coverage)
        topics: dict[str, Topic] = {}
        topic_specs = {
            "Mechanics": ["Newton's Laws", "Work and Energy", "Rotational Motion"],
            "Optics": ["Reflection", "Refraction", "Wave Optics"],
            "Atomic Structure": ["Bohr Model", "Quantum Numbers", "Periodic Trends"],
            "Chemical Bonding": ["Ionic Bonds", "Covalent Bonds", "VSEPR Theory"],
        }
        for ch_name, topic_names in topic_specs.items():
            ch = chapters[ch_name]
            for order, name in enumerate(topic_names, start=1):
                tp, _ = await _find_or_create(
                    session,
                    Topic,
                    defaults={
                        "academic_year_id": ay.id,
                        "chapter_id": ch.id,
                        "order": order,
                        "status": "active",
                        "is_deleted": False,
                    },
                    branch_id=branch.id,
                    name=name,
                )
                topics[name] = tp

        # ---- Classroom
        room, _ = await _find_or_create(
            session,
            Classroom,
            defaults={
                "capacity": 60,
                "floor": "1",
                "status": "active",
                "is_deleted": False,
            },
            branch_id=branch.id,
            name="Room 101",
            code="R101",
        )

        # ---- Teachers
        teachers = {}
        for first, last in [
            ("Rahul", "Sharma"),
            ("Priya", "Nair"),
            ("Asha", "Kulkarni"),
        ]:
            t, _ = await _find_or_create(
                session,
                Teacher,
                defaults={
                    "qualification": "M.Sc demo",
                    "status": "active",
                    "is_deleted": False,
                },
                branch_id=branch.id,
                first_name=first,
                last_name=last,
            )
            teachers[first] = t
        rahul = teachers["Rahul"]
        priya = teachers["Priya"]
        asha = teachers["Asha"]

        # ---- Batches.
        # Target exam date is ~6 months out so the pacing badges on
        # /insights and /teachers/[id] show realistic deltas (not 100%
        # expected immediately).
        demo_exam = (date.today() + timedelta(days=180))
        batches = {}
        for name, code in [("NEET 2025-A", "NEET-A"), ("NEET 2025-B", "NEET-B")]:
            b, _ = await _find_or_create(
                session,
                Batch,
                defaults={
                    "start_academic_year_id": ay.id,
                    "end_academic_year_id": ay.id,
                    "course_id": course.id,
                    "capacity": 60,
                    "target_exam_date": demo_exam,
                    "status": "active",
                    "is_deleted": False,
                },
                branch_id=branch.id,
                name=name,
                code=code,
            )
            # If an existing row had a NULL exam date from before this
            # field existed, backfill it so the demo is consistent.
            if b.target_exam_date is None:
                b.target_exam_date = demo_exam
                await session.flush()
            batches[code] = b
        neet_a = batches["NEET-A"]
        neet_b = batches["NEET-B"]

        # ---- BatchSubjectMappings (so syllabus coverage > 0)
        for batch in (neet_a, neet_b):
            for subj in (physics, chemistry):
                await _find_or_create(
                    session,
                    BatchSubjectMapping,
                    defaults={
                        "status": "active",
                        "is_deleted": False,
                    },
                    branch_id=branch.id,
                    batch_id=batch.id,
                    subject_id=subj.id,
                )

        await session.flush()

        # ---- Lectures + sessions covering all 10 scenarios
        now = datetime.now(timezone.utc).replace(second=0, microsecond=0)

        def mk_lecture(
            *,
            teacher: Teacher,
            batch: Batch,
            subject: Subject,
            topic_name: str | None,
            start: datetime,
            duration_hours: int = 1,
            status: str,
            delivery_mode: str = "offline",
            classroom: Classroom | None = None,
            actual_teacher: Teacher | None = None,
            change_reason: str | None = None,
            no_show_reason: str | None = None,
            note_tail: str = "",
            actual_start: datetime | None = None,
            actual_end: datetime | None = None,
        ) -> Lecture:
            return Lecture(
                teacher_id=teacher.id,
                batch_id=batch.id,
                classroom_id=(classroom.id if classroom else None),
                subject_id=subject.id,
                topic_id=(topics[topic_name].id if topic_name else None),
                scheduled_start=start,
                scheduled_end=start + timedelta(hours=duration_hours),
                actual_start=actual_start,
                actual_end=actual_end,
                delivery_mode=delivery_mode,
                lecture_status=status,
                actual_teacher_id=(actual_teacher.id if actual_teacher else None),
                change_reason=change_reason,
                no_show_reason=no_show_reason,
                notes=f"{DEMO_TAG} {note_tail}".strip(),
                branch_id=branch.id,
                academic_year_id=ay.id,
                status="active",
                is_deleted=False,
            )

        # ---- Scenario 1 — Normal completion (5 days ago)
        s1_start = _at(now, -5, 10)
        s1 = mk_lecture(
            teacher=rahul,
            batch=neet_a,
            subject=physics,
            topic_name="Newton's Laws",
            start=s1_start,
            status="completed",
            classroom=room,
            actual_start=s1_start,
            actual_end=s1_start + timedelta(hours=1),
            note_tail="Scenario 1 — happy completion",
        )

        # ---- Scenario 2 — Completed with substitute (Priya covered Rahul)
        s2_start = _at(now, -5, 12)
        s2 = mk_lecture(
            teacher=rahul,
            batch=neet_a,
            subject=physics,
            topic_name="Work and Energy",
            start=s2_start,
            status="completed",
            classroom=room,
            actual_start=s2_start,
            actual_end=s2_start + timedelta(hours=1),
            actual_teacher=priya,
            change_reason="SUBSTITUTE",
            note_tail="Scenario 2 — substitute",
        )

        # ---- Scenario 3 — Teacher no-show
        s3 = mk_lecture(
            teacher=rahul,
            batch=neet_a,
            subject=physics,
            topic_name="Rotational Motion",
            start=_at(now, -4, 10),
            status="no_show",
            classroom=room,
            no_show_reason="TEACHER_NO_SHOW",
            note_tail="Scenario 3 — teacher no-show",
        )

        # ---- Scenario 4 — Student no-show
        s4 = mk_lecture(
            teacher=asha,
            batch=neet_b,
            subject=chemistry,
            topic_name="Bohr Model",
            start=_at(now, -4, 12),
            status="no_show",
            classroom=room,
            no_show_reason="STUDENT_NO_SHOW",
            note_tail="Scenario 4 — student no-show",
        )

        # ---- Scenario 5 — External no-show (power outage etc.)
        s5 = mk_lecture(
            teacher=priya,
            batch=neet_a,
            subject=chemistry,
            topic_name="Quantum Numbers",
            start=_at(now, -4, 14),
            status="no_show",
            classroom=room,
            no_show_reason="EXTERNAL",
            note_tail="Scenario 5 — external no-show",
        )

        # ---- Scenario 6 — Intentional cancellation
        s6 = mk_lecture(
            teacher=rahul,
            batch=neet_a,
            subject=physics,
            topic_name="Reflection",
            start=_at(now, -3, 10),
            status="cancelled",
            classroom=room,
            note_tail="Scenario 6 — intentional cancellation",
        )

        # ---- Scenario 7 — No-show that will be made up
        s7_plan_start = _at(now, -3, 12)
        s7_plan = mk_lecture(
            teacher=asha,
            batch=neet_b,
            subject=physics,
            topic_name="Refraction",
            start=s7_plan_start,
            status="no_show",
            classroom=room,
            no_show_reason="TEACHER_NO_SHOW",
            note_tail="Scenario 7 — missed plan (makeup linked below)",
        )

        # ---- Scenario 9a + 9b — Two scheduled lectures (will appear as
        # mergeable in the UI). We don't auto-merge here — the user can
        # exercise the Merge Lectures dialog against these rows.
        # Use tomorrow's slot to keep them mergeable (status must be scheduled).
        s9_start = _at(now, 1, 9)
        s9a = mk_lecture(
            teacher=rahul,
            batch=neet_a,
            subject=physics,
            topic_name="Wave Optics",
            start=s9_start,
            status="scheduled",
            classroom=room,
            note_tail="Scenario 9a — merge candidate (NEET-A)",
        )
        # Different teacher from 9a so the row pair represents a realistic
        # merge candidate (same time, same subject, different batches/teachers
        # — one teacher ends up taking both batches in one room).
        s9b = mk_lecture(
            teacher=asha,
            batch=neet_b,
            subject=physics,
            topic_name="Wave Optics",
            start=s9_start,
            status="scheduled",
            classroom=room,
            note_tail="Scenario 9b — merge candidate (NEET-B, different teacher)",
        )

        # ---- Scenario 10 — Rescheduled (now writes back as "scheduled"
        # with the new times — see lecture_service.reschedule_lecture).
        # Seed it as scheduled to match the post-fix lifecycle behavior.
        s10 = mk_lecture(
            teacher=priya,
            batch=neet_a,
            subject=chemistry,
            topic_name="Periodic Trends",
            start=_at(now, 1, 14),
            status="scheduled",
            classroom=room,
            note_tail="Scenario 10 — rescheduled (now starts as scheduled)",
        )

        # ---- Scenario 1 future — happy scheduled (so the page has a
        # plain pending row to demo Start/Complete)
        s1f = mk_lecture(
            teacher=asha,
            batch=neet_a,
            subject=chemistry,
            topic_name="Ionic Bonds",
            start=_at(now, 1, 16),
            status="scheduled",
            classroom=room,
            note_tail="Scenario 1-future — happy scheduled",
        )

        session.add_all([s1, s2, s3, s4, s5, s6, s7_plan, s9a, s9b, s10, s1f])
        await session.flush()

        # ---- Sessions covering Scenarios 7, 8, 9
        def mk_session(
            *,
            teacher: Teacher,
            subject: Subject,
            topic_name: str | None,
            start: datetime,
            duration_hours: int = 1,
            origin: str,
            classroom: Classroom | None = None,
            note_tail: str,
        ) -> LectureSession:
            return LectureSession(
                teacher_id=teacher.id,
                classroom_id=(classroom.id if classroom else None),
                subject_id=subject.id,
                topic_id=(topics[topic_name].id if topic_name else None),
                actual_start=start,
                actual_end=start + timedelta(hours=duration_hours),
                delivery_mode="offline",
                session_status="completed",
                origin=origin,
                notes=f"{DEMO_TAG} {note_tail}".strip(),
                branch_id=branch.id,
                academic_year_id=ay.id,
                status="active",
                is_deleted=False,
            )

        # Scenario 7 — Makeup session on yesterday for the no-show plan
        s7_makeup = mk_session(
            teacher=asha,
            subject=physics,
            topic_name="Refraction",
            start=_at(now, -1, 10),
            origin="makeup",
            classroom=room,
            note_tail="Scenario 7 — makeup session",
        )

        # Scenario 8 — Pure ad-hoc revision class yesterday (no plan)
        s8_adhoc = mk_session(
            teacher=priya,
            subject=chemistry,
            topic_name="Covalent Bonds",
            start=_at(now, -1, 14),
            origin="ad_hoc",
            classroom=room,
            note_tail="Scenario 8 — pure ad-hoc",
        )

        session.add_all([s7_makeup, s8_adhoc])
        await session.flush()

        # Session-batch links
        session.add_all(
            [
                LectureSessionBatch(
                    session_id=s7_makeup.id,
                    batch_id=neet_b.id,
                    branch_id=branch.id,
                    status="active",
                    is_deleted=False,
                ),
                LectureSessionBatch(
                    session_id=s8_adhoc.id,
                    batch_id=neet_a.id,
                    branch_id=branch.id,
                    status="active",
                    is_deleted=False,
                ),
            ]
        )

        # Session-plan link (Scenario 7 only — links the makeup session
        # to the no-show plan)
        session.add(
            LectureSessionPlan(
                session_id=s7_makeup.id,
                lecture_id=s7_plan.id,
                branch_id=branch.id,
                status="active",
                is_deleted=False,
            )
        )

        # ---- Students, attendance, tests, marks (Tier 9 outcome data)
        # 4 students per batch. Top 2 attend everything, bottom 2 don't —
        # creates a clean attendance↔score correlation in the demo.
        students_by_batch: dict[uuid.UUID, list] = {}
        for batch_obj in (neet_a, neet_b):
            roster = []
            for i in range(1, 5):
                stu, _ = await _find_or_create(
                    session,
                    Student,
                    defaults={
                        "academic_year_id": ay.id,
                        "course_id": course.id,
                        # NEET 2-year course → Class 11 cohort by convention.
                        "standard": "11",
                        "target_exam": "NEET",
                        "status": "active",
                        "is_deleted": False,
                    },
                    branch_id=branch.id,
                    first_name=f"Student{i}",
                    last_name=batch_obj.code,
                )
                # Backfill on existing demo rows from before this column existed.
                if stu.standard is None:
                    stu.standard = "11"
                if stu.target_exam is None:
                    stu.target_exam = "NEET"
                await session.flush()
                await _find_or_create(
                    session,
                    StudentBatchMapping,
                    defaults={"status": "active", "is_deleted": False},
                    branch_id=branch.id,
                    student_id=stu.id,
                    batch_id=batch_obj.id,
                )
                roster.append(stu)
            students_by_batch[batch_obj.id] = roster

        await session.flush()

        # Attendance on the two completed NEET-A lectures (Scenarios 1, 2).
        for lec in (s1, s2):
            for i, stu in enumerate(students_by_batch.get(lec.batch_id, [])):
                marker = lec.actual_start or lec.scheduled_start
                session.add(
                    LectureAttendanceMapping(
                        lecture_id=lec.id,
                        student_id=stu.id,
                        attendance_status="PRESENT" if i < 2 else "ABSENT",
                        marked_at=marker,
                        branch_id=branch.id,
                        status="active",
                        is_deleted=False,
                    )
                )

        # One published Physics test per batch, recent. Marks correlate
        # with attendance pattern above — top 2 score high, bottom 2 low.
        for batch_obj, score_curve in [
            (neet_a, [88, 75, 52, 38]),
            (neet_b, [82, 70, 48, 35]),
        ]:
            t, created = await _find_or_create(
                session,
                Test,
                defaults={
                    "description": f"{DEMO_TAG} Physics mid-chapter test",
                    "scheduled_at": _at(now, -1, 10),
                    "duration_minutes": 60,
                    "total_marks": 100.0,
                    "test_status": "PUBLISHED",
                    "academic_year_id": ay.id,
                    "status": "active",
                    "is_deleted": False,
                },
                branch_id=branch.id,
                name=f"Physics MCT — {batch_obj.code}",
                batch_id=batch_obj.id,
                subject_id=physics.id,
            )
            if not created:
                continue
            roster = students_by_batch.get(batch_obj.id, [])
            for stu, score in zip(roster, score_curve):
                session.add(
                    StudentMark(
                        student_id=stu.id,
                        test_id=t.id,
                        marks_obtained=float(score),
                        max_marks=100.0,
                        percentage=float(score),
                        is_absent=False,
                        marked_at=t.scheduled_at + timedelta(hours=2),
                        branch_id=branch.id,
                        academic_year_id=ay.id,
                        status="active",
                        is_deleted=False,
                    )
                )

        await session.commit()

        print("Demo dataset seeded successfully.")
        print(f"  branch:       {branch.name} ({branch.code})")
        print(f"  academic yr:  {ay.name}")
        print(f"  course:       {course.name}")
        print(f"  subjects:     Physics, Chemistry  ({2} subjects)")
        print(f"  chapters:     {4}  (2 per subject)")
        print(f"  topics:       {12} (3 per chapter — your syllabus denominator)")
        print(f"  classroom:    {room.name} ({room.code})")
        print(f"  teachers:     Rahul Sharma, Priya Nair, Asha Kulkarni")
        print(f"  batches:      NEET 2025-A, NEET 2025-B")
        print(f"  lectures:     {11} covering Scenarios 1-10")
        print(f"  sessions:     2 (Scenario 7 makeup, Scenario 8 ad-hoc)")
        print()
        print("Scenario 9 is left as TWO scheduled lectures — go to /lectures")
        print("and click 'Merge Lectures' to exercise that flow yourself.")
        print()
        print("Log in:  admin@academy.com  /  Admin123!")


async def reset():
    """Soft-delete every demo-tagged row so seed() can run again.

    Soft-delete (sets is_deleted=True) — does not DROP anything. The rows
    stay queryable for audit but the seed guard treats them as gone.
    """
    async with async_session_factory() as session:
        from sqlalchemy import update

        # Lectures
        result = await session.execute(
            update(Lecture)
            .where(Lecture.notes.like(f"%{DEMO_TAG}%"))
            .values(is_deleted=True)
        )
        lec_count = result.rowcount or 0

        # Sessions
        sess_result = await session.execute(
            update(LectureSession)
            .where(LectureSession.notes.like(f"%{DEMO_TAG}%"))
            .values(is_deleted=True)
        )
        sess_count = sess_result.rowcount or 0

        await session.commit()
        print(f"Reset: soft-deleted {lec_count} lectures, {sess_count} sessions.")
        print("You can now re-run `python seed_demo.py`.")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--reset":
        asyncio.run(reset())
    else:
        asyncio.run(seed())
