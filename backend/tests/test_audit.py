import json
import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.repositories import audit_repository
from app.modules.audit.services import audit_service


class TestAuditRepository:
    async def test_create_log(self, db_session: AsyncSession):
        user_id = uuid.uuid4()
        record_id = uuid.uuid4()

        log = await audit_repository.create_log(
            db_session,
            user_id=user_id,
            action="CREATE",
            table_name="users",
            record_id=record_id,
            new_values=json.dumps({"email": "test@example.com"}),
            ip_address="127.0.0.1",
        )
        await db_session.commit()

        assert log.id is not None
        assert log.user_id == user_id
        assert log.action == "CREATE"
        assert log.table_name == "users"
        assert log.record_id == record_id
        assert log.new_values == json.dumps({"email": "test@example.com"})
        assert log.ip_address == "127.0.0.1"

    async def test_create_log_system_event(self, db_session: AsyncSession):
        record_id = uuid.uuid4()

        log = await audit_repository.create_log(
            db_session,
            user_id=None,
            action="IMPORT",
            table_name="students",
            record_id=record_id,
            new_values=json.dumps({"name": "Batch import"}),
        )
        await db_session.commit()

        assert log.user_id is None
        assert log.action == "IMPORT"

    async def test_get_logs_filter_by_table(self, db_session: AsyncSession):
        record_id = uuid.uuid4()

        await audit_repository.create_log(
            db_session,
            user_id=None,
            action="CREATE",
            table_name="users",
            record_id=record_id,
        )
        await audit_repository.create_log(
            db_session,
            user_id=None,
            action="CREATE",
            table_name="roles",
            record_id=uuid.uuid4(),
        )
        await db_session.commit()

        logs, total = await audit_repository.get_logs(
            db_session, table_name="users"
        )
        assert total == 1
        assert logs[0].table_name == "users"

    async def test_get_logs_pagination(self, db_session: AsyncSession):
        for _ in range(5):
            await audit_repository.create_log(
                db_session,
                user_id=None,
                action="UPDATE",
                table_name="users",
                record_id=uuid.uuid4(),
            )
        await db_session.commit()

        logs, total = await audit_repository.get_logs(
            db_session, limit=2, offset=0
        )
        assert total == 5
        assert len(logs) == 2


class TestAuditService:
    async def test_log_action(self, db_session: AsyncSession):
        user_id = uuid.uuid4()
        record_id = uuid.uuid4()

        await audit_service.log_action(
            db_session,
            user_id=user_id,
            action="UPDATE",
            table_name="users",
            record_id=record_id,
            old_values={"status": "active"},
            new_values={"status": "inactive"},
            ip_address="192.168.1.1",
            branch_id=uuid.uuid4(),
        )
        await db_session.commit()

        logs, total = await audit_repository.get_logs(db_session)
        assert total == 1
        assert logs[0].action == "UPDATE"
        assert json.loads(logs[0].old_values) == {"status": "active"}
        assert json.loads(logs[0].new_values) == {"status": "inactive"}


class TestAuditAPI:
    @pytest.mark.usefixtures("seed_data")
    async def test_super_admin_can_view_logs(self, client, seed_data, db_session):
        await audit_repository.create_log(
            db_session,
            user_id=seed_data["admin_user"].id,
            action="CREATE",
            table_name="users",
            record_id=uuid.uuid4(),
            new_values=json.dumps({"email": "new@test.com"}),
        )
        await db_session.commit()

        login_resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "admin@test.com", "password": "Admin123!"},
        )
        access_token = login_resp.cookies["access_token"]

        response = await client.get(
            "/api/v1/audit/logs",
            cookies={"access_token": access_token},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1
        assert data["items"][0]["action"] == "CREATE"

    @pytest.mark.usefixtures("seed_data")
    async def test_non_admin_cannot_view_logs(self, client, seed_data):
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "teacher@test.com", "password": "Teacher123!"},
        )
        access_token = login_resp.cookies["access_token"]

        response = await client.get(
            "/api/v1/audit/logs",
            cookies={"access_token": access_token},
        )
        assert response.status_code == 403

    async def test_unauthenticated_cannot_view_logs(self, client):
        response = await client.get("/api/v1/audit/logs")
        assert response.status_code == 401
