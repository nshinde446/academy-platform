import uuid
from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.database.base import Base
from app.core.database.session import get_db
from app.main import app
from app.modules.auth.models.auth_models import (
    Branch,
    Permission,
    Role,
    RolePermission,
    User,
    UserBranchRole,
    UserRole,
)
from app.modules.academic.models.academic_models import (  # noqa: F401
    AcademicYear, Chapter, Course, Institute, Subject, Subtopic, Topic,
)
from app.modules.audit.models.audit_models import AuditLog  # noqa: F401
from app.modules.batch.models.batch_models import Batch, BatchSchedule, BatchSubjectMapping  # noqa: F401
from app.modules.classroom.models.classroom_models import Classroom  # noqa: F401
from app.modules.student.models.student_models import (  # noqa: F401
    Parent, Student, StudentBatchMapping, StudentIdentity,
)
from app.modules.teacher.models.teacher_models import (  # noqa: F401
    Teacher, TeacherBatchMapping, TeacherSubjectMapping,
)
from app.modules.lectures.models.lecture_models import (  # noqa: F401
    Lecture, LectureAttendanceMapping, LectureTopicMapping,
)
from app.modules.attendance.models.attendance_models import (  # noqa: F401
    AttendanceException, AttendanceRecord, RawPunchLog,
)
from app.modules.tests.models.test_models import (  # noqa: F401
    Question, QuestionMetadata, QuestionTopic, StudentMark, Test, TestQuestion,
)
from app.modules.events.models.event_models import (  # noqa: F401
    AcademicEvent, ProcessedEvent,
)
from app.modules.analytics.models.analytics_models import (  # noqa: F401
    AnalyticsBatchSummary, AnalyticsStudentSummary, AnalyticsTeacherSummary,
)
from app.modules.auth.services.auth_service import hash_password

TEST_DATABASE_URL = "sqlite+aiosqlite:///./test.db"

engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False},
)
TestSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture(autouse=True)
async def setup_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def override_get_db():
    async with TestSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture
async def db_session():
    async with TestSessionLocal() as session:
        yield session


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def seed_data(db_session: AsyncSession):
    branch_a = Branch(
        id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
        name="Main Branch",
        code="MAIN",
        status="active",
        is_deleted=False,
    )
    branch_b = Branch(
        id=uuid.UUID("00000000-0000-0000-0000-000000000002"),
        name="Secondary Branch",
        code="SEC",
        status="active",
        is_deleted=False,
    )

    admin_role = Role(
        id=uuid.UUID("00000000-0000-0000-0000-000000000010"),
        name="super_admin",
        display_name="Super Admin",
        status="active",
        is_deleted=False,
    )
    teacher_role = Role(
        id=uuid.UUID("00000000-0000-0000-0000-000000000011"),
        name="teacher",
        display_name="Teacher",
        status="active",
        is_deleted=False,
    )

    perm_view = Permission(
        id=uuid.UUID("00000000-0000-0000-0000-000000000020"),
        name="students.view",
        module="students",
        status="active",
        is_deleted=False,
    )
    perm_edit = Permission(
        id=uuid.UUID("00000000-0000-0000-0000-000000000021"),
        name="students.edit",
        module="students",
        status="active",
        is_deleted=False,
    )

    admin_user = User(
        id=uuid.UUID("00000000-0000-0000-0000-000000000100"),
        email="admin@test.com",
        password_hash=hash_password("Admin123!"),
        first_name="Admin",
        last_name="User",
        primary_branch_id=branch_a.id,
        status="active",
        is_deleted=False,
    )
    teacher_user = User(
        id=uuid.UUID("00000000-0000-0000-0000-000000000101"),
        email="teacher@test.com",
        password_hash=hash_password("Teacher123!"),
        first_name="Teacher",
        last_name="User",
        primary_branch_id=branch_a.id,
        status="active",
        is_deleted=False,
    )
    inactive_user = User(
        id=uuid.UUID("00000000-0000-0000-0000-000000000102"),
        email="inactive@test.com",
        password_hash=hash_password("Inactive123!"),
        first_name="Inactive",
        last_name="User",
        status="inactive",
        is_deleted=False,
    )

    db_session.add_all([branch_a, branch_b, admin_role, teacher_role, perm_view, perm_edit])
    await db_session.flush()

    db_session.add_all([admin_user, teacher_user, inactive_user])
    await db_session.flush()

    admin_user_role = UserRole(
        user_id=admin_user.id,
        role_id=admin_role.id,
        status="active",
        is_deleted=False,
    )
    teacher_user_role = UserRole(
        user_id=teacher_user.id,
        role_id=teacher_role.id,
        status="active",
        is_deleted=False,
    )

    role_perm_view = RolePermission(
        role_id=teacher_role.id,
        permission_id=perm_view.id,
        status="active",
        is_deleted=False,
    )
    role_perm_edit = RolePermission(
        role_id=teacher_role.id,
        permission_id=perm_edit.id,
        status="active",
        is_deleted=False,
    )

    teacher_branch_role = UserBranchRole(
        user_id=teacher_user.id,
        branch_id=branch_a.id,
        role_id=teacher_role.id,
        status="active",
        is_deleted=False,
    )

    db_session.add_all([
        admin_user_role,
        teacher_user_role,
        role_perm_view,
        role_perm_edit,
        teacher_branch_role,
    ])
    await db_session.commit()

    academic_year = AcademicYear(
        id=uuid.UUID("00000000-0000-0000-0000-000000000030"),
        branch_id=branch_a.id,
        name="2025-2026",
        start_year=2025,
        end_year=2026,
        status="active",
        is_deleted=False,
    )
    db_session.add(academic_year)
    await db_session.flush()

    course = Course(
        id=uuid.UUID("00000000-0000-0000-0000-000000000040"),
        branch_id=branch_a.id,
        academic_year_id=academic_year.id,
        name="JEE Advanced",
        code="JEE-ADV",
        status="active",
        is_deleted=False,
    )
    db_session.add(course)
    await db_session.flush()

    subject = Subject(
        id=uuid.UUID("00000000-0000-0000-0000-000000000050"),
        branch_id=branch_a.id,
        academic_year_id=academic_year.id,
        course_id=course.id,
        name="Physics",
        code="PHY",
        status="active",
        is_deleted=False,
    )
    db_session.add(subject)
    await db_session.flush()

    teacher = Teacher(
        id=uuid.UUID("00000000-0000-0000-0000-000000000060"),
        user_id=teacher_user.id,
        branch_id=branch_a.id,
        first_name="Teacher",
        last_name="User",
        status="active",
        is_deleted=False,
    )
    db_session.add(teacher)
    await db_session.flush()

    batch = Batch(
        id=uuid.UUID("00000000-0000-0000-0000-000000000070"),
        branch_id=branch_a.id,
        academic_year_id=academic_year.id,
        course_id=course.id,
        name="Batch A",
        code="BATCH-A",
        status="active",
        is_deleted=False,
    )
    batch_b = Batch(
        id=uuid.UUID("00000000-0000-0000-0000-000000000071"),
        branch_id=branch_a.id,
        academic_year_id=academic_year.id,
        course_id=course.id,
        name="Batch B",
        code="BATCH-B",
        status="active",
        is_deleted=False,
    )
    db_session.add_all([batch, batch_b])
    await db_session.flush()

    classroom = Classroom(
        id=uuid.UUID("00000000-0000-0000-0000-000000000080"),
        branch_id=branch_a.id,
        name="Room 101",
        code="R101",
        capacity=40,
        status="active",
        is_deleted=False,
    )
    db_session.add(classroom)
    await db_session.flush()

    student = Student(
        id=uuid.UUID("00000000-0000-0000-0000-000000000090"),
        branch_id=branch_a.id,
        academic_year_id=academic_year.id,
        first_name="Test",
        last_name="Student",
        enrollment_number="STU001",
        status="active",
        is_deleted=False,
    )
    db_session.add(student)
    await db_session.commit()

    return {
        "admin_user": admin_user,
        "teacher_user": teacher_user,
        "inactive_user": inactive_user,
        "branch_a": branch_a,
        "branch_b": branch_b,
        "admin_role": admin_role,
        "teacher_role": teacher_role,
        "academic_year": academic_year,
        "course": course,
        "subject": subject,
        "teacher": teacher,
        "batch": batch,
        "batch_b": batch_b,
        "classroom": classroom,
        "student": student,
    }
