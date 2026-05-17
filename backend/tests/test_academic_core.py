import uuid

import pytest


class TestStudentCRUD:
    @pytest.mark.usefixtures("seed_data")
    async def test_create_student(self, client, seed_data):
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "admin@test.com", "password": "Admin123!"},
        )
        token = login_resp.cookies["access_token"]

        response = await client.post(
            "/api/v1/students",
            json={
                "branch_id": "00000000-0000-0000-0000-000000000001",
                "academic_year_id": "00000000-0000-0000-0000-000000000030",
                "first_name": "John",
                "last_name": "Doe",
                "email": "john@test.com",
                "phone": "9876543210",
            },
            cookies={"access_token": token},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["first_name"] == "John"
        assert data["branch_id"] == "00000000-0000-0000-0000-000000000001"

    @pytest.mark.usefixtures("seed_data")
    async def test_list_students(self, client, seed_data):
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "admin@test.com", "password": "Admin123!"},
        )
        token = login_resp.cookies["access_token"]

        await client.post(
            "/api/v1/students",
            json={
                "branch_id": "00000000-0000-0000-0000-000000000001",
                "academic_year_id": "00000000-0000-0000-0000-000000000030",
                "first_name": "Jane",
                "last_name": "Smith",
            },
            cookies={"access_token": token},
        )

        response = await client.get(
            "/api/v1/students?branch_id=00000000-0000-0000-0000-000000000001",
            cookies={"access_token": token},
        )
        assert response.status_code == 200
        assert len(response.json()) >= 1

    @pytest.mark.usefixtures("seed_data")
    async def test_update_student(self, client, seed_data):
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "admin@test.com", "password": "Admin123!"},
        )
        token = login_resp.cookies["access_token"]

        create_resp = await client.post(
            "/api/v1/students",
            json={
                "branch_id": "00000000-0000-0000-0000-000000000001",
                "academic_year_id": "00000000-0000-0000-0000-000000000030",
                "first_name": "Update",
                "last_name": "Me",
            },
            cookies={"access_token": token},
        )
        student_id = create_resp.json()["id"]

        response = await client.patch(
            f"/api/v1/students/{student_id}?branch_id=00000000-0000-0000-0000-000000000001",
            json={"first_name": "Updated"},
            cookies={"access_token": token},
        )
        assert response.status_code == 200
        assert response.json()["first_name"] == "Updated"

    @pytest.mark.usefixtures("seed_data")
    async def test_delete_student_soft(self, client, seed_data):
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "admin@test.com", "password": "Admin123!"},
        )
        token = login_resp.cookies["access_token"]

        create_resp = await client.post(
            "/api/v1/students",
            json={
                "branch_id": "00000000-0000-0000-0000-000000000001",
                "academic_year_id": "00000000-0000-0000-0000-000000000030",
                "first_name": "Delete",
                "last_name": "Me",
            },
            cookies={"access_token": token},
        )
        student_id = create_resp.json()["id"]

        response = await client.delete(
            f"/api/v1/students/{student_id}?branch_id=00000000-0000-0000-0000-000000000001",
            cookies={"access_token": token},
        )
        assert response.status_code == 204

        get_resp = await client.get(
            f"/api/v1/students/{student_id}?branch_id=00000000-0000-0000-0000-000000000001",
            cookies={"access_token": token},
        )
        assert get_resp.status_code == 404

    @pytest.mark.usefixtures("seed_data")
    async def test_student_branch_isolation(self, client, seed_data):
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "admin@test.com", "password": "Admin123!"},
        )
        token = login_resp.cookies["access_token"]

        create_resp = await client.post(
            "/api/v1/students",
            json={
                "branch_id": "00000000-0000-0000-0000-000000000001",
                "academic_year_id": "00000000-0000-0000-0000-000000000030",
                "first_name": "Branch",
                "last_name": "A",
            },
            cookies={"access_token": token},
        )
        student_id = create_resp.json()["id"]

        response = await client.get(
            f"/api/v1/students/{student_id}?branch_id=00000000-0000-0000-0000-000000000002",
            cookies={"access_token": token},
        )
        assert response.status_code == 403


class TestTeacherCRUD:
    @pytest.mark.usefixtures("seed_data")
    async def test_create_teacher(self, client, seed_data):
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "admin@test.com", "password": "Admin123!"},
        )
        token = login_resp.cookies["access_token"]

        response = await client.post(
            "/api/v1/teachers",
            json={
                "branch_id": "00000000-0000-0000-0000-000000000001",
                "first_name": "Prof",
                "last_name": "Smith",
                "email": "prof@test.com",
                "qualification": "PhD Physics",
            },
            cookies={"access_token": token},
        )
        assert response.status_code == 200
        assert response.json()["first_name"] == "Prof"

    @pytest.mark.usefixtures("seed_data")
    async def test_list_teachers(self, client, seed_data):
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "admin@test.com", "password": "Admin123!"},
        )
        token = login_resp.cookies["access_token"]

        await client.post(
            "/api/v1/teachers",
            json={
                "branch_id": "00000000-0000-0000-0000-000000000001",
                "first_name": "Dr",
                "last_name": "Jones",
            },
            cookies={"access_token": token},
        )

        response = await client.get(
            "/api/v1/teachers?branch_id=00000000-0000-0000-0000-000000000001",
            cookies={"access_token": token},
        )
        assert response.status_code == 200
        assert len(response.json()) >= 1

    @pytest.mark.usefixtures("seed_data")
    async def test_update_teacher(self, client, seed_data):
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "admin@test.com", "password": "Admin123!"},
        )
        token = login_resp.cookies["access_token"]

        create_resp = await client.post(
            "/api/v1/teachers",
            json={
                "branch_id": "00000000-0000-0000-0000-000000000001",
                "first_name": "Old",
                "last_name": "Name",
            },
            cookies={"access_token": token},
        )
        teacher_id = create_resp.json()["id"]

        response = await client.patch(
            f"/api/v1/teachers/{teacher_id}?branch_id=00000000-0000-0000-0000-000000000001",
            json={"first_name": "New"},
            cookies={"access_token": token},
        )
        assert response.status_code == 200
        assert response.json()["first_name"] == "New"

    @pytest.mark.usefixtures("seed_data")
    async def test_delete_teacher(self, client, seed_data):
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "admin@test.com", "password": "Admin123!"},
        )
        token = login_resp.cookies["access_token"]

        create_resp = await client.post(
            "/api/v1/teachers",
            json={
                "branch_id": "00000000-0000-0000-0000-000000000001",
                "first_name": "Gone",
                "last_name": "Teacher",
            },
            cookies={"access_token": token},
        )
        teacher_id = create_resp.json()["id"]

        response = await client.delete(
            f"/api/v1/teachers/{teacher_id}?branch_id=00000000-0000-0000-0000-000000000001",
            cookies={"access_token": token},
        )
        assert response.status_code == 204

    @pytest.mark.usefixtures("seed_data")
    async def test_teacher_branch_isolation(self, client, seed_data):
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "admin@test.com", "password": "Admin123!"},
        )
        token = login_resp.cookies["access_token"]

        create_resp = await client.post(
            "/api/v1/teachers",
            json={
                "branch_id": "00000000-0000-0000-0000-000000000001",
                "first_name": "Isolated",
                "last_name": "Teacher",
            },
            cookies={"access_token": token},
        )
        teacher_id = create_resp.json()["id"]

        response = await client.get(
            f"/api/v1/teachers/{teacher_id}?branch_id=00000000-0000-0000-0000-000000000002",
            cookies={"access_token": token},
        )
        assert response.status_code == 403


class TestBatchCRUD:
    @pytest.mark.usefixtures("seed_data")
    async def test_create_batch(self, client, seed_data):
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "admin@test.com", "password": "Admin123!"},
        )
        token = login_resp.cookies["access_token"]

        response = await client.post(
            "/api/v1/batches",
            json={
                "branch_id": "00000000-0000-0000-0000-000000000001",
                "academic_year_id": "00000000-0000-0000-0000-000000000030",
                "course_id": "00000000-0000-0000-0000-000000000040",
                "name": "Batch A",
                "code": "BA-01",
                "capacity": 40,
            },
            cookies={"access_token": token},
        )
        assert response.status_code == 200
        assert response.json()["name"] == "Batch A"
        assert response.json()["capacity"] == 40

    @pytest.mark.usefixtures("seed_data")
    async def test_list_batches(self, client, seed_data):
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "admin@test.com", "password": "Admin123!"},
        )
        token = login_resp.cookies["access_token"]

        await client.post(
            "/api/v1/batches",
            json={
                "branch_id": "00000000-0000-0000-0000-000000000001",
                "academic_year_id": "00000000-0000-0000-0000-000000000030",
                "course_id": "00000000-0000-0000-0000-000000000040",
                "name": "Batch B",
                "code": "BB-01",
            },
            cookies={"access_token": token},
        )

        response = await client.get(
            "/api/v1/batches?branch_id=00000000-0000-0000-0000-000000000001",
            cookies={"access_token": token},
        )
        assert response.status_code == 200
        assert len(response.json()) >= 1

    @pytest.mark.usefixtures("seed_data")
    async def test_update_batch(self, client, seed_data):
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "admin@test.com", "password": "Admin123!"},
        )
        token = login_resp.cookies["access_token"]

        create_resp = await client.post(
            "/api/v1/batches",
            json={
                "branch_id": "00000000-0000-0000-0000-000000000001",
                "academic_year_id": "00000000-0000-0000-0000-000000000030",
                "course_id": "00000000-0000-0000-0000-000000000040",
                "name": "Old Batch",
                "code": "OB-01",
            },
            cookies={"access_token": token},
        )
        batch_id = create_resp.json()["id"]

        response = await client.patch(
            f"/api/v1/batches/{batch_id}?branch_id=00000000-0000-0000-0000-000000000001",
            json={"name": "New Batch", "capacity": 50},
            cookies={"access_token": token},
        )
        assert response.status_code == 200
        assert response.json()["name"] == "New Batch"
        assert response.json()["capacity"] == 50

    @pytest.mark.usefixtures("seed_data")
    async def test_delete_batch(self, client, seed_data):
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "admin@test.com", "password": "Admin123!"},
        )
        token = login_resp.cookies["access_token"]

        create_resp = await client.post(
            "/api/v1/batches",
            json={
                "branch_id": "00000000-0000-0000-0000-000000000001",
                "academic_year_id": "00000000-0000-0000-0000-000000000030",
                "course_id": "00000000-0000-0000-0000-000000000040",
                "name": "Delete Batch",
                "code": "DB-01",
            },
            cookies={"access_token": token},
        )
        batch_id = create_resp.json()["id"]

        response = await client.delete(
            f"/api/v1/batches/{batch_id}?branch_id=00000000-0000-0000-0000-000000000001",
            cookies={"access_token": token},
        )
        assert response.status_code == 204

    @pytest.mark.usefixtures("seed_data")
    async def test_batch_branch_isolation(self, client, seed_data):
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "admin@test.com", "password": "Admin123!"},
        )
        token = login_resp.cookies["access_token"]

        create_resp = await client.post(
            "/api/v1/batches",
            json={
                "branch_id": "00000000-0000-0000-0000-000000000001",
                "academic_year_id": "00000000-0000-0000-0000-000000000030",
                "course_id": "00000000-0000-0000-0000-000000000040",
                "name": "Iso Batch",
                "code": "IB-01",
            },
            cookies={"access_token": token},
        )
        batch_id = create_resp.json()["id"]

        response = await client.get(
            f"/api/v1/batches/{batch_id}?branch_id=00000000-0000-0000-0000-000000000002",
            cookies={"access_token": token},
        )
        assert response.status_code == 403


class TestClassroomCRUD:
    @pytest.mark.usefixtures("seed_data")
    async def test_create_classroom(self, client, seed_data):
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "admin@test.com", "password": "Admin123!"},
        )
        token = login_resp.cookies["access_token"]

        response = await client.post(
            "/api/v1/classrooms",
            json={
                "branch_id": "00000000-0000-0000-0000-000000000001",
                "name": "Room 101",
                "code": "R101",
                "capacity": 60,
                "floor": "1st",
            },
            cookies={"access_token": token},
        )
        assert response.status_code == 200
        assert response.json()["name"] == "Room 101"
        assert response.json()["capacity"] == 60

    @pytest.mark.usefixtures("seed_data")
    async def test_list_classrooms(self, client, seed_data):
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "admin@test.com", "password": "Admin123!"},
        )
        token = login_resp.cookies["access_token"]

        await client.post(
            "/api/v1/classrooms",
            json={
                "branch_id": "00000000-0000-0000-0000-000000000001",
                "name": "Lab A",
                "code": "LA",
                "capacity": 30,
            },
            cookies={"access_token": token},
        )

        response = await client.get(
            "/api/v1/classrooms?branch_id=00000000-0000-0000-0000-000000000001",
            cookies={"access_token": token},
        )
        assert response.status_code == 200
        assert len(response.json()) >= 1

    @pytest.mark.usefixtures("seed_data")
    async def test_update_classroom(self, client, seed_data):
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "admin@test.com", "password": "Admin123!"},
        )
        token = login_resp.cookies["access_token"]

        create_resp = await client.post(
            "/api/v1/classrooms",
            json={
                "branch_id": "00000000-0000-0000-0000-000000000001",
                "name": "Old Room",
                "code": "OR",
                "capacity": 20,
            },
            cookies={"access_token": token},
        )
        classroom_id = create_resp.json()["id"]

        response = await client.patch(
            f"/api/v1/classrooms/{classroom_id}?branch_id=00000000-0000-0000-0000-000000000001",
            json={"name": "New Room", "capacity": 50},
            cookies={"access_token": token},
        )
        assert response.status_code == 200
        assert response.json()["name"] == "New Room"

    @pytest.mark.usefixtures("seed_data")
    async def test_delete_classroom(self, client, seed_data):
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "admin@test.com", "password": "Admin123!"},
        )
        token = login_resp.cookies["access_token"]

        create_resp = await client.post(
            "/api/v1/classrooms",
            json={
                "branch_id": "00000000-0000-0000-0000-000000000001",
                "name": "Gone Room",
                "code": "GR",
                "capacity": 10,
            },
            cookies={"access_token": token},
        )
        classroom_id = create_resp.json()["id"]

        response = await client.delete(
            f"/api/v1/classrooms/{classroom_id}?branch_id=00000000-0000-0000-0000-000000000001",
            cookies={"access_token": token},
        )
        assert response.status_code == 204

    @pytest.mark.usefixtures("seed_data")
    async def test_classroom_branch_isolation(self, client, seed_data):
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "admin@test.com", "password": "Admin123!"},
        )
        token = login_resp.cookies["access_token"]

        create_resp = await client.post(
            "/api/v1/classrooms",
            json={
                "branch_id": "00000000-0000-0000-0000-000000000001",
                "name": "Isolated Room",
                "code": "IR",
                "capacity": 25,
            },
            cookies={"access_token": token},
        )
        classroom_id = create_resp.json()["id"]

        response = await client.get(
            f"/api/v1/classrooms/{classroom_id}?branch_id=00000000-0000-0000-0000-000000000002",
            cookies={"access_token": token},
        )
        assert response.status_code == 403


class TestAcademicHierarchy:
    @pytest.mark.usefixtures("seed_data")
    async def test_create_academic_year(self, client, seed_data):
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "admin@test.com", "password": "Admin123!"},
        )
        token = login_resp.cookies["access_token"]

        response = await client.post(
            "/api/v1/academic/academic-years",
            json={
                "branch_id": "00000000-0000-0000-0000-000000000001",
                "name": "2026-2027",
                "start_year": 2026,
                "end_year": 2027,
            },
            cookies={"access_token": token},
        )
        assert response.status_code == 200
        assert response.json()["name"] == "2026-2027"

    @pytest.mark.usefixtures("seed_data")
    async def test_create_course(self, client, seed_data):
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "admin@test.com", "password": "Admin123!"},
        )
        token = login_resp.cookies["access_token"]

        response = await client.post(
            "/api/v1/academic/courses",
            json={
                "branch_id": "00000000-0000-0000-0000-000000000001",
                "academic_year_id": "00000000-0000-0000-0000-000000000030",
                "name": "NEET",
                "code": "NEET-01",
            },
            cookies={"access_token": token},
        )
        assert response.status_code == 200
        assert response.json()["name"] == "NEET"

    @pytest.mark.usefixtures("seed_data")
    async def test_create_subject(self, client, seed_data):
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "admin@test.com", "password": "Admin123!"},
        )
        token = login_resp.cookies["access_token"]

        response = await client.post(
            "/api/v1/academic/subjects",
            json={
                "branch_id": "00000000-0000-0000-0000-000000000001",
                "academic_year_id": "00000000-0000-0000-0000-000000000030",
                "course_id": "00000000-0000-0000-0000-000000000040",
                "name": "Chemistry",
                "code": "CHEM",
            },
            cookies={"access_token": token},
        )
        assert response.status_code == 200
        assert response.json()["name"] == "Chemistry"

    @pytest.mark.usefixtures("seed_data")
    async def test_create_chapter_topic_subtopic(self, client, seed_data):
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "admin@test.com", "password": "Admin123!"},
        )
        token = login_resp.cookies["access_token"]

        ch_resp = await client.post(
            "/api/v1/academic/chapters",
            json={
                "branch_id": "00000000-0000-0000-0000-000000000001",
                "academic_year_id": "00000000-0000-0000-0000-000000000030",
                "subject_id": "00000000-0000-0000-0000-000000000050",
                "name": "Kinematics",
                "order": 1,
            },
            cookies={"access_token": token},
        )
        assert ch_resp.status_code == 200
        chapter_id = ch_resp.json()["id"]

        topic_resp = await client.post(
            "/api/v1/academic/topics",
            json={
                "branch_id": "00000000-0000-0000-0000-000000000001",
                "academic_year_id": "00000000-0000-0000-0000-000000000030",
                "chapter_id": chapter_id,
                "name": "Equations of Motion",
                "order": 1,
            },
            cookies={"access_token": token},
        )
        assert topic_resp.status_code == 200
        topic_id = topic_resp.json()["id"]

        st_resp = await client.post(
            "/api/v1/academic/subtopics",
            json={
                "branch_id": "00000000-0000-0000-0000-000000000001",
                "academic_year_id": "00000000-0000-0000-0000-000000000030",
                "topic_id": topic_id,
                "name": "v = u + at",
                "order": 1,
            },
            cookies={"access_token": token},
        )
        assert st_resp.status_code == 200
        assert st_resp.json()["name"] == "v = u + at"

    @pytest.mark.usefixtures("seed_data")
    async def test_non_admin_cannot_create(self, client, seed_data):
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "teacher@test.com", "password": "Teacher123!"},
        )
        token = login_resp.cookies["access_token"]

        response = await client.post(
            "/api/v1/academic/courses",
            json={
                "branch_id": "00000000-0000-0000-0000-000000000001",
                "academic_year_id": "00000000-0000-0000-0000-000000000030",
                "name": "Unauthorized",
                "code": "UNAUTH",
            },
            cookies={"access_token": token},
        )
        assert response.status_code == 403


class TestAuditOnStudentOperations:
    @pytest.mark.usefixtures("seed_data")
    async def test_student_create_generates_audit(self, client, seed_data):
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "admin@test.com", "password": "Admin123!"},
        )
        token = login_resp.cookies["access_token"]

        await client.post(
            "/api/v1/students",
            json={
                "branch_id": "00000000-0000-0000-0000-000000000001",
                "academic_year_id": "00000000-0000-0000-0000-000000000030",
                "first_name": "Audited",
                "last_name": "Student",
            },
            cookies={"access_token": token},
        )

        audit_resp = await client.get(
            "/api/v1/audit/logs?table_name=students&action=CREATE",
            cookies={"access_token": token},
        )
        assert audit_resp.status_code == 200
        data = audit_resp.json()
        assert data["total"] >= 1
        assert data["items"][0]["table_name"] == "students"
        assert data["items"][0]["action"] == "CREATE"
