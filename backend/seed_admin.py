import asyncio
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import async_session_factory
from app.core.database.base import Base
from app.modules.auth.models.auth_models import Branch, Permission, Role, RolePermission, User, UserBranchRole, UserRole
from app.modules.academic.models.academic_models import *  # noqa: F401,F403
from app.modules.audit.models.audit_models import *  # noqa: F401,F403
from app.modules.batch.models.batch_models import *  # noqa: F401,F403
from app.modules.classroom.models.classroom_models import *  # noqa: F401,F403
from app.modules.student.models.student_models import *  # noqa: F401,F403
from app.modules.teacher.models.teacher_models import *  # noqa: F401,F403
from app.modules.lectures.models.lecture_models import *  # noqa: F401,F403
from app.modules.attendance.models.attendance_models import *  # noqa: F401,F403
from app.modules.tests.models.test_models import *  # noqa: F401,F403
from app.modules.events.models.event_models import *  # noqa: F401,F403
from app.modules.analytics.models.analytics_models import *  # noqa: F401,F403
from app.modules.notifications.models.notification_models import *  # noqa: F401,F403
from app.modules.reports.models.report_models import *  # noqa: F401,F403
from app.modules.plugins.models.plugin_models import *  # noqa: F401,F403
from app.modules.ai.models.ai_models import *  # noqa: F401,F403
from app.modules.auth.services.auth_service import hash_password


async def seed():
    async with async_session_factory() as session:
        branch = Branch(
            id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
            name="Main Branch",
            code="MAIN",
            status="active",
            is_deleted=False,
        )
        session.add(branch)
        await session.flush()

        admin_role = Role(
            id=uuid.UUID("00000000-0000-0000-0000-000000000010"),
            name="super_admin",
            display_name="Super Admin",
            status="active",
            is_deleted=False,
        )
        session.add(admin_role)
        await session.flush()

        admin_user = User(
            id=uuid.UUID("00000000-0000-0000-0000-000000000100"),
            email="admin@academy.com",
            password_hash=hash_password("Admin123!"),
            first_name="Super",
            last_name="Admin",
            primary_branch_id=branch.id,
            status="active",
            is_deleted=False,
        )
        session.add(admin_user)
        await session.flush()

        user_role = UserRole(
            user_id=admin_user.id,
            role_id=admin_role.id,
            status="active",
            is_deleted=False,
        )
        session.add(user_role)

        branch_role = UserBranchRole(
            user_id=admin_user.id,
            branch_id=branch.id,
            role_id=admin_role.id,
            status="active",
            is_deleted=False,
        )
        session.add(branch_role)

        await session.commit()
        print("Admin user seeded successfully!")
        print("Email:    admin@academy.com")
        print("Password: Admin123!")


if __name__ == "__main__":
    asyncio.run(seed())
