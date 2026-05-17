import json
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import case, select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.analytics.repositories import analytics_repository
from app.modules.attendance.models.attendance_models import AttendanceRecord
from app.modules.audit.services import audit_service
from app.modules.batch.models.batch_models import Batch
from app.modules.lectures.models.lecture_models import Lecture
from app.modules.student.models.student_models import Student, StudentBatchMapping
from app.modules.teacher.models.teacher_models import Teacher
from app.modules.tests.models.test_models import StudentMark

RISK_ATTENDANCE_WEIGHT = 0.6
RISK_SCORE_WEIGHT = 0.4
RISK_THRESHOLD_DEFAULT = 50.0
WEAK_TOPIC_THRESHOLD = 40.0


async def refresh_all(
    session: AsyncSession,
    branch_id: uuid.UUID,
    academic_year_id: uuid.UUID,
    current_user_id: uuid.UUID | None = None,
    ip_address: str | None = None,
):
    await _refresh_student_summaries(session, branch_id, academic_year_id)
    await _refresh_teacher_summaries(session, branch_id, academic_year_id)
    await _refresh_batch_summaries(session, branch_id, academic_year_id)

    if current_user_id:
        await audit_service.log_action(
            session,
            user_id=current_user_id,
            action="REFRESH",
            table_name="analytics",
            record_id=branch_id,
            new_values={"branch_id": str(branch_id), "academic_year_id": str(academic_year_id)},
            ip_address=ip_address,
            branch_id=branch_id,
        )


async def _refresh_student_summaries(
    session: AsyncSession, branch_id: uuid.UUID, academic_year_id: uuid.UUID
):
    now = datetime.now(timezone.utc)

    result = await session.execute(
        select(Student.id).where(
            Student.branch_id == branch_id,
            Student.academic_year_id == academic_year_id,
            Student.is_deleted == False,
        )
    )
    student_ids = [row[0] for row in result.all()]

    for student_id in student_ids:
        att_result = await session.execute(
            select(
                func.count(AttendanceRecord.id),
                func.sum(
                    case(
                        (AttendanceRecord.attendance_status == "PRESENT", 1),
                        else_=0,
                    )
                ),
                func.sum(
                    case(
                        (AttendanceRecord.attendance_status == "ABSENT", 1),
                        else_=0,
                    )
                ),
                func.sum(
                    case(
                        (AttendanceRecord.attendance_status == "LATE", 1),
                        else_=0,
                    )
                ),
            ).where(
                AttendanceRecord.student_id == student_id,
                AttendanceRecord.branch_id == branch_id,
                AttendanceRecord.is_deleted == False,
            )
        )
        att_row = att_result.first()
        total_att = att_row[0] or 0
        present = att_row[1] or 0
        absent = att_row[2] or 0
        late = att_row[3] or 0
        att_pct = (present / total_att * 100) if total_att > 0 else 0.0

        marks_result = await session.execute(
            select(
                func.count(StudentMark.id),
                func.avg(StudentMark.percentage),
            ).where(
                StudentMark.student_id == student_id,
                StudentMark.branch_id == branch_id,
                StudentMark.is_deleted == False,
                StudentMark.is_absent == False,
            )
        )
        marks_row = marks_result.first()
        total_tests = marks_row[0] or 0
        avg_score = float(marks_row[1] or 0)

        risk_score = _compute_risk_score(att_pct, avg_score)

        weak_result = await session.execute(
            select(StudentMark.test_id, StudentMark.percentage).where(
                StudentMark.student_id == student_id,
                StudentMark.branch_id == branch_id,
                StudentMark.is_deleted == False,
                StudentMark.is_absent == False,
                StudentMark.percentage < WEAK_TOPIC_THRESHOLD,
            )
        )
        weak_test_ids = [str(row[0]) for row in weak_result.all()]
        weak_json = json.dumps(weak_test_ids) if weak_test_ids else None

        await analytics_repository.upsert_student_summary(
            session, student_id, branch_id,
            academic_year_id=academic_year_id,
            total_attendance=total_att,
            present_count=present,
            absent_count=absent,
            late_count=late,
            attendance_percentage=round(att_pct, 2),
            total_tests=total_tests,
            average_score=round(avg_score, 2),
            weak_topics=weak_json,
            risk_score=round(risk_score, 2),
            last_updated=now,
        )


def _compute_risk_score(attendance_pct: float, avg_score: float) -> float:
    att_risk = max(0, 100 - attendance_pct)
    score_risk = max(0, 100 - avg_score)
    return att_risk * RISK_ATTENDANCE_WEIGHT + score_risk * RISK_SCORE_WEIGHT


async def _refresh_teacher_summaries(
    session: AsyncSession, branch_id: uuid.UUID, academic_year_id: uuid.UUID
):
    now = datetime.now(timezone.utc)

    result = await session.execute(
        select(Teacher.id).where(
            Teacher.branch_id == branch_id,
            Teacher.is_deleted == False,
        )
    )
    teacher_ids = [row[0] for row in result.all()]

    for teacher_id in teacher_ids:
        lec_result = await session.execute(
            select(
                func.count(Lecture.id),
                func.sum(
                    case(
                        (Lecture.lecture_status == "completed", 1),
                        else_=0,
                    )
                ),
            ).where(
                Lecture.teacher_id == teacher_id,
                Lecture.branch_id == branch_id,
                Lecture.is_deleted == False,
            )
        )
        lec_row = lec_result.first()
        total_lectures = lec_row[0] or 0
        completed = lec_row[1] or 0
        completion_rate = (completed / total_lectures * 100) if total_lectures > 0 else 0.0

        delay_result = await session.execute(
            select(Lecture.scheduled_start, Lecture.actual_start).where(
                Lecture.teacher_id == teacher_id,
                Lecture.branch_id == branch_id,
                Lecture.actual_start.isnot(None),
                Lecture.is_deleted == False,
            )
        )
        delays = []
        for row in delay_result.all():
            if row[1] and row[0]:
                delta = (row[1] - row[0]).total_seconds() / 60
                delays.append(max(0, delta))
        avg_delay = sum(delays) / len(delays) if delays else 0.0

        att_result = await session.execute(
            select(func.avg(AttendanceRecord.id)).where(
                AttendanceRecord.lecture_id.in_(
                    select(Lecture.id).where(
                        Lecture.teacher_id == teacher_id,
                        Lecture.branch_id == branch_id,
                        Lecture.is_deleted == False,
                    )
                ),
                AttendanceRecord.attendance_status == "PRESENT",
                AttendanceRecord.is_deleted == False,
            )
        )
        total_present = await session.execute(
            select(func.count(AttendanceRecord.id)).where(
                AttendanceRecord.lecture_id.in_(
                    select(Lecture.id).where(
                        Lecture.teacher_id == teacher_id,
                        Lecture.branch_id == branch_id,
                        Lecture.is_deleted == False,
                    )
                ),
                AttendanceRecord.attendance_status == "PRESENT",
                AttendanceRecord.is_deleted == False,
            )
        )
        total_records = await session.execute(
            select(func.count(AttendanceRecord.id)).where(
                AttendanceRecord.lecture_id.in_(
                    select(Lecture.id).where(
                        Lecture.teacher_id == teacher_id,
                        Lecture.branch_id == branch_id,
                        Lecture.is_deleted == False,
                    )
                ),
                AttendanceRecord.is_deleted == False,
            )
        )
        present_count = total_present.scalar() or 0
        record_count = total_records.scalar() or 0
        avg_att = (present_count / record_count * 100) if record_count > 0 else 0.0

        await analytics_repository.upsert_teacher_summary(
            session, teacher_id, branch_id,
            academic_year_id=academic_year_id,
            total_lectures=total_lectures,
            completed_lectures=completed,
            completion_rate=round(completion_rate, 2),
            avg_delay_minutes=round(avg_delay, 2),
            avg_student_attendance=round(avg_att, 2),
            last_updated=now,
        )


async def _refresh_batch_summaries(
    session: AsyncSession, branch_id: uuid.UUID, academic_year_id: uuid.UUID
):
    now = datetime.now(timezone.utc)

    result = await session.execute(
        select(Batch.id).where(
            Batch.branch_id == branch_id,
            Batch.academic_year_id == academic_year_id,
            Batch.is_deleted == False,
        )
    )
    batch_ids = [row[0] for row in result.all()]

    for batch_id in batch_ids:
        student_result = await session.execute(
            select(StudentBatchMapping.student_id).where(
                StudentBatchMapping.batch_id == batch_id,
                StudentBatchMapping.is_deleted == False,
            )
        )
        student_ids = [row[0] for row in student_result.all()]
        total_students = len(student_ids)

        if total_students == 0:
            await analytics_repository.upsert_batch_summary(
                session, batch_id, branch_id,
                academic_year_id=academic_year_id,
                total_students=0, avg_attendance=0.0, avg_score=0.0,
                weak_subjects=None, top_performers=None, last_updated=now,
            )
            continue

        att_result = await session.execute(
            select(func.avg(
                case(
                    (AttendanceRecord.attendance_status == "PRESENT", 100.0),
                    else_=0.0,
                )
            )).where(
                AttendanceRecord.student_id.in_(student_ids),
                AttendanceRecord.branch_id == branch_id,
                AttendanceRecord.is_deleted == False,
            )
        )
        avg_att = float(att_result.scalar() or 0)

        score_result = await session.execute(
            select(func.avg(StudentMark.percentage)).where(
                StudentMark.student_id.in_(student_ids),
                StudentMark.branch_id == branch_id,
                StudentMark.is_deleted == False,
                StudentMark.is_absent == False,
            )
        )
        avg_score = float(score_result.scalar() or 0)

        top_result = await session.execute(
            select(StudentMark.student_id, func.avg(StudentMark.percentage).label("avg_pct"))
            .where(
                StudentMark.student_id.in_(student_ids),
                StudentMark.branch_id == branch_id,
                StudentMark.is_deleted == False,
                StudentMark.is_absent == False,
            )
            .group_by(StudentMark.student_id)
            .order_by(func.avg(StudentMark.percentage).desc())
            .limit(5)
        )
        top_performers = [str(row[0]) for row in top_result.all()]
        top_json = json.dumps(top_performers) if top_performers else None

        await analytics_repository.upsert_batch_summary(
            session, batch_id, branch_id,
            academic_year_id=academic_year_id,
            total_students=total_students,
            avg_attendance=round(avg_att, 2),
            avg_score=round(avg_score, 2),
            weak_subjects=None,
            top_performers=top_json,
            last_updated=now,
        )


async def get_student_analytics(
    session: AsyncSession, student_id: uuid.UUID, branch_id: uuid.UUID
):
    summary = await analytics_repository.get_student_summary(session, student_id, branch_id)
    if not summary:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student analytics not found")
    return _format_student(summary)


async def get_teacher_analytics(
    session: AsyncSession, teacher_id: uuid.UUID, branch_id: uuid.UUID
):
    summary = await analytics_repository.get_teacher_summary(session, teacher_id, branch_id)
    if not summary:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Teacher analytics not found")
    return _format_teacher(summary)


async def get_batch_analytics(
    session: AsyncSession, batch_id: uuid.UUID, branch_id: uuid.UUID
):
    summary = await analytics_repository.get_batch_summary(session, batch_id, branch_id)
    if not summary:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch analytics not found")
    return _format_batch(summary)


async def get_risk_students(
    session: AsyncSession, branch_id: uuid.UUID, threshold: float = RISK_THRESHOLD_DEFAULT
):
    students = await analytics_repository.get_risk_students(session, branch_id, threshold)
    return [
        {
            "student_id": s.student_id,
            "risk_score": s.risk_score,
            "attendance_percentage": s.attendance_percentage,
            "average_score": s.average_score,
        }
        for s in students
    ]


def _format_student(s):
    return {
        "student_id": s.student_id,
        "branch_id": s.branch_id,
        "academic_year_id": s.academic_year_id,
        "total_attendance": s.total_attendance,
        "present_count": s.present_count,
        "absent_count": s.absent_count,
        "late_count": s.late_count,
        "attendance_percentage": s.attendance_percentage,
        "total_tests": s.total_tests,
        "average_score": s.average_score,
        "weak_topics": json.loads(s.weak_topics) if s.weak_topics else None,
        "risk_score": s.risk_score,
        "last_updated": s.last_updated,
    }


def _format_teacher(t):
    return {
        "teacher_id": t.teacher_id,
        "branch_id": t.branch_id,
        "academic_year_id": t.academic_year_id,
        "total_lectures": t.total_lectures,
        "completed_lectures": t.completed_lectures,
        "completion_rate": t.completion_rate,
        "avg_delay_minutes": t.avg_delay_minutes,
        "avg_student_attendance": t.avg_student_attendance,
        "last_updated": t.last_updated,
    }


def _format_batch(b):
    return {
        "batch_id": b.batch_id,
        "branch_id": b.branch_id,
        "academic_year_id": b.academic_year_id,
        "total_students": b.total_students,
        "avg_attendance": b.avg_attendance,
        "avg_score": b.avg_score,
        "weak_subjects": json.loads(b.weak_subjects) if b.weak_subjects else None,
        "top_performers": json.loads(b.top_performers) if b.top_performers else None,
        "last_updated": b.last_updated,
    }
