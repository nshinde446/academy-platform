import pytest

BRANCH = "00000000-0000-0000-0000-000000000001"


async def _login(client) -> str:
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.com", "password": "Admin123!"},
    )
    return resp.cookies["access_token"]


def _csv(*lines: str) -> bytes:
    header = "Name,Class,Target,Batch,Roll No"
    return ("\n".join([header, *lines]) + "\n").encode("utf-8")


class TestStudentImportPreview:
    @pytest.mark.usefixtures("seed_data")
    async def test_preview_splits_existing_and_missing_batches(self, client, seed_data):
        token = await _login(client)
        content = _csv(
            "Aman Sharma,11,NEET,BATCH-A,S-001",       # existing (seed)
            "Priya Singh,12,NEET,NEET-11-A,S-002",      # missing
            "Rohan Patel,11,JEE-Main,NEET-11-A,S-003",  # missing, same code
        )
        resp = await client.post(
            f"/api/v1/students/import/preview?branch_id={BRANCH}",
            files={"file": ("students.csv", content, "text/csv")},
            cookies={"access_token": token},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_rows"] == 3
        assert data["importable_rows"] == 3
        assert data["existing_batches"] == 1
        assert data["missing_batches"] == 1

        by_code = {b["code"]: b for b in data["batches"]}
        assert by_code["BATCH-A"]["exists"] is True
        missing = by_code["NEET-11-A"]
        assert missing["exists"] is False
        assert missing["student_count"] == 2
        # Dominant Target across the two rows is NEET -> NEET course.
        assert missing["target"] == "NEET"
        assert missing["suggested_course_code"] == "NEET"
        assert missing["suggested_exam_date"] is not None

    @pytest.mark.usefixtures("seed_data")
    async def test_preview_flags_row_issues(self, client, seed_data):
        token = await _login(client)
        content = _csv(
            ",11,NEET,BATCH-A,S-001",                 # missing name
            "Bad Target,11,JEE,BATCH-A,S-002",         # invalid target
        )
        resp = await client.post(
            f"/api/v1/students/import/preview?branch_id={BRANCH}",
            files={"file": ("students.csv", content, "text/csv")},
            cookies={"access_token": token},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["rows_missing_name"] == 1
        assert data["rows_invalid_enrolment"] == 1
        assert any("Invalid target_exam" in m for m in data["row_issues"])

    @pytest.mark.usefixtures("seed_data")
    async def test_preview_flags_uncreatable_batch(
        self, client, seed_data, db_session
    ):
        """A missing batch whose course would need an academic year that does
        not exist is flagged not-creatable up front, not silently skipped at
        import time."""
        import uuid as _uuid

        from app.modules.academic.models.academic_models import Course

        # A 2-year NEET course makes any NEET-derived batch need a 2026-start
        # academic year — which the seed branch (only 2025-26) lacks.
        db_session.add(
            Course(
                id=_uuid.UUID("00000000-0000-0000-0000-0000000000a1"),
                branch_id=_uuid.UUID(BRANCH),
                name="NEET 2-Year",
                code="NEET",
                duration_years=2,
                status="active",
                is_deleted=False,
            )
        )
        await db_session.commit()

        token = await _login(client)
        content = _csv("Aarav Rao,11,NEET,NEET-11-X,S-010")
        resp = await client.post(
            f"/api/v1/students/import/preview?branch_id={BRANCH}",
            files={"file": ("students.csv", content, "text/csv")},
            cookies={"access_token": token},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["blocked_batches"] == 1
        flagged = {b["code"]: b for b in data["batches"]}["NEET-11-X"]
        assert flagged["creatable"] is False
        assert "academic year" in (flagged["blocker"] or "")


class TestStudentImportCreateMissing:
    @pytest.mark.usefixtures("seed_data")
    async def test_import_without_flag_skips_unknown_batch(self, client, seed_data):
        token = await _login(client)
        content = _csv("Priya Singh,12,NEET,NEET-11-A,S-002")
        resp = await client.post(
            f"/api/v1/students/import?branch_id={BRANCH}",
            files={"file": ("students.csv", content, "text/csv")},
            cookies={"access_token": token},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["imported"] == 0
        assert data["skipped"] == 1
        assert data["batches_created"] == []
        assert any("unknown batch code 'NEET-11-A'" in e for e in data["errors"])

    @pytest.mark.usefixtures("seed_data")
    async def test_import_with_flag_creates_batch_and_assigns(self, client, seed_data):
        token = await _login(client)
        content = _csv(
            "Priya Singh,12,NEET,NEET-11-A,S-002",
            "Rohan Patel,11,NEET,NEET-11-A,S-003",
        )
        resp = await client.post(
            f"/api/v1/students/import?branch_id={BRANCH}&create_missing_batches=true",
            files={"file": ("students.csv", content, "text/csv")},
            cookies={"access_token": token},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["imported"] == 2
        assert data["skipped"] == 0
        assert data["batches_created"] == ["NEET-11-A"]

        # The new batch is now visible on the batches endpoint.
        batches = await client.get(
            f"/api/v1/batches?branch_id={BRANCH}",
            cookies={"access_token": token},
        )
        codes = {b["code"] for b in batches.json()}
        assert "NEET-11-A" in codes

    @pytest.mark.usefixtures("seed_data")
    async def test_failed_batch_creation_reports_reason(
        self, client, seed_data, monkeypatch
    ):
        """When auto-create is on but a batch can't be created, the row must
        say *why* — not the misleading "unknown batch code"."""
        from fastapi import HTTPException, status

        from app.modules.student.services import import_service

        async def _boom(*args, **kwargs):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot find academic year starting at 2027 for this branch.",
            )

        monkeypatch.setattr(import_service, "_create_derived_batch", _boom)

        token = await _login(client)
        content = _csv("Priya Singh,12,NEET,NEET-11-A,S-002")
        resp = await client.post(
            f"/api/v1/students/import?branch_id={BRANCH}&create_missing_batches=true",
            files={"file": ("students.csv", content, "text/csv")},
            cookies={"access_token": token},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["imported"] == 0
        assert data["skipped"] == 1
        assert data["batches_created"] == []
        assert any(
            "couldn't create batch 'NEET-11-A'" in e
            and "Cannot find academic year" in e
            for e in data["errors"]
        )
        # The misleading generic message must NOT be used in this case.
        assert not any("unknown batch code" in e for e in data["errors"])

    @pytest.mark.usefixtures("seed_data")
    async def test_import_existing_batch_still_matches(self, client, seed_data):
        token = await _login(client)
        content = _csv("Aman Sharma,11,NEET,BATCH-A,S-001")
        resp = await client.post(
            f"/api/v1/students/import?branch_id={BRANCH}",
            files={"file": ("students.csv", content, "text/csv")},
            cookies={"access_token": token},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["imported"] == 1
        assert data["skipped"] == 0


class TestStudentImportDedupAndDiagnostics:
    @pytest.mark.usefixtures("seed_data")
    async def test_duplicate_enrolment_skipped_within_file_and_on_reimport(
        self, client, seed_data
    ):
        """Same Roll No twice in a file imports once; re-uploading skips it
        instead of silently duplicating the student."""
        token = await _login(client)
        content = _csv(
            "Aman Kumar,11,NEET,BATCH-A,S-100",
            "Aman Kumar Again,11,NEET,BATCH-A,S-100",  # same enrolment no.
        )
        resp = await client.post(
            f"/api/v1/students/import?branch_id={BRANCH}",
            files={"file": ("students.csv", content, "text/csv")},
            cookies={"access_token": token},
        )
        data = resp.json()
        assert data["imported"] == 1
        assert data["skipped"] == 1
        assert any("duplicate" in e.lower() for e in data["errors"])

        # Re-uploading the (now-existing) row is skipped, not duplicated.
        again = await client.post(
            f"/api/v1/students/import?branch_id={BRANCH}",
            files={
                "file": (
                    "students.csv",
                    _csv("Aman Kumar,11,NEET,BATCH-A,S-100"),
                    "text/csv",
                )
            },
            cookies={"access_token": token},
        )
        redata = again.json()
        assert redata["imported"] == 0
        assert redata["skipped"] == 1

    @pytest.mark.usefixtures("seed_data")
    async def test_preview_counts_duplicates(self, client, seed_data):
        token = await _login(client)
        # Seed one student, then preview a file that repeats it.
        await client.post(
            f"/api/v1/students/import?branch_id={BRANCH}",
            files={
                "file": (
                    "s.csv",
                    _csv("Ravi Verma,11,NEET,BATCH-A,S-200"),
                    "text/csv",
                )
            },
            cookies={"access_token": token},
        )
        resp = await client.post(
            f"/api/v1/students/import/preview?branch_id={BRANCH}",
            files={
                "file": (
                    "s.csv",
                    _csv("Ravi Verma,11,NEET,BATCH-A,S-200"),
                    "text/csv",
                )
            },
            cookies={"access_token": token},
        )
        data = resp.json()
        assert data["duplicate_rows"] == 1
        assert data["importable_rows"] == 0  # the only row is a duplicate

    @pytest.mark.usefixtures("seed_data")
    async def test_error_row_number_accounts_for_blank_lines(
        self, client, seed_data
    ):
        """A blank line before a bad row must not shift the reported row
        number — 'Row N' should match the line the admin sees."""
        token = await _login(client)
        content = (
            "Name,Class,Target,Batch,Roll No\n"
            "Aman Good,11,NEET,BATCH-A,S-300\n"
            "\n"  # blank line 3
            ",11,NEET,BATCH-A,S-301\n"  # missing name on line 4
        ).encode("utf-8")
        resp = await client.post(
            f"/api/v1/students/import?branch_id={BRANCH}",
            files={"file": ("students.csv", content, "text/csv")},
            cookies={"access_token": token},
        )
        data = resp.json()
        assert data["imported"] == 1
        assert any("Row 4" in e and "Name" in e for e in data["errors"])


class TestStudentImportTraceabilityAndUndo:
    @pytest.mark.usefixtures("seed_data")
    async def test_import_returns_import_id_and_tags_students(
        self, client, seed_data, db_session
    ):
        from sqlalchemy import select

        from app.modules.student.models.student_models import Student

        token = await _login(client)
        content = _csv(
            "Asha Rao,11,NEET,BATCH-A,T-001",
            "Bina Roy,11,NEET,BATCH-A,T-002",
        )
        resp = await client.post(
            f"/api/v1/students/import?branch_id={BRANCH}",
            files={"file": ("roster.csv", content, "text/csv")},
            cookies={"access_token": token},
        )
        data = resp.json()
        assert data["imported"] == 2
        assert data["import_id"] is not None

        # Every imported student carries the same import_id + source filename.
        rows = (
            await db_session.execute(
                select(Student).where(
                    Student.enrollment_number.in_(["T-001", "T-002"])
                )
            )
        ).scalars().all()
        assert {str(s.import_id) for s in rows} == {data["import_id"]}
        assert {s.import_source_file for s in rows} == {"roster.csv"}

    @pytest.mark.usefixtures("seed_data")
    async def test_import_with_no_rows_saved_has_null_import_id(
        self, client, seed_data
    ):
        token = await _login(client)
        # Unknown batch, create-missing off -> nothing persists.
        content = _csv("Cara Sen,11,NEET,NOPE-99,T-010")
        resp = await client.post(
            f"/api/v1/students/import?branch_id={BRANCH}",
            files={"file": ("x.csv", content, "text/csv")},
            cookies={"access_token": token},
        )
        data = resp.json()
        assert data["imported"] == 0
        assert data["import_id"] is None

    @pytest.mark.usefixtures("seed_data")
    async def test_undo_removes_students_and_auto_created_batch(
        self, client, seed_data
    ):
        token = await _login(client)
        content = _csv(
            "Dev Iyer,11,NEET,UNDO-11-A,T-020",
            "Esha Nair,11,NEET,UNDO-11-A,T-021",
        )
        resp = await client.post(
            f"/api/v1/students/import?branch_id={BRANCH}&create_missing_batches=true",
            files={"file": ("x.csv", content, "text/csv")},
            cookies={"access_token": token},
        )
        data = resp.json()
        assert data["imported"] == 2
        assert data["batches_created"] == ["UNDO-11-A"]
        import_id = data["import_id"]

        undo = await client.post(
            f"/api/v1/students/import/{import_id}/undo?branch_id={BRANCH}",
            cookies={"access_token": token},
        )
        assert undo.status_code == 200
        u = undo.json()
        assert u["students_deleted"] == 2
        assert u["batches_deleted"] == 1

        # The auto-created batch is gone again.
        batches = await client.get(
            f"/api/v1/batches?branch_id={BRANCH}",
            cookies={"access_token": token},
        )
        assert "UNDO-11-A" not in {b["code"] for b in batches.json()}

        # Undo is idempotent — a second call finds nothing.
        again = await client.post(
            f"/api/v1/students/import/{import_id}/undo?branch_id={BRANCH}",
            cookies={"access_token": token},
        )
        assert again.json() == {
            "students_deleted": 0,
            "batches_deleted": 0,
            "subjects_deleted": 0,
        }

    @pytest.mark.usefixtures("seed_data")
    async def test_undo_keeps_batch_that_has_other_students(
        self, client, seed_data
    ):
        """A batch this import created but which later gained students from a
        different import must NOT be reclaimed on undo."""
        token = await _login(client)
        # Import A: creates batch SHARED-A with one student.
        a = await client.post(
            f"/api/v1/students/import?branch_id={BRANCH}&create_missing_batches=true",
            files={
                "file": ("a.csv", _csv("Gita Bose,11,NEET,SHARED-A,T-030"), "text/csv")
            },
            cookies={"access_token": token},
        )
        import_a = a.json()["import_id"]

        # Import B: batch already exists, so it just assigns another student.
        b = await client.post(
            f"/api/v1/students/import?branch_id={BRANCH}",
            files={
                "file": ("b.csv", _csv("Hari Das,11,NEET,SHARED-A,T-031"), "text/csv")
            },
            cookies={"access_token": token},
        )
        assert b.json()["batches_created"] == []

        # Undo A: its student goes, but the batch stays (B's student remains).
        undo = await client.post(
            f"/api/v1/students/import/{import_a}/undo?branch_id={BRANCH}",
            cookies={"access_token": token},
        )
        u = undo.json()
        assert u["students_deleted"] == 1
        assert u["batches_deleted"] == 0
        batches = await client.get(
            f"/api/v1/batches?branch_id={BRANCH}",
            cookies={"access_token": token},
        )
        assert "SHARED-A" in {b["code"] for b in batches.json()}


class TestStudentImportOverrides:
    """Optional Course_opt / Duration / Academic_year columns (design §5):
    explicit value wins, else fall back to Target-derived defaults."""

    @staticmethod
    def _add_year(db_session, suffix, start, end):
        import uuid as _uuid

        from app.modules.academic.models.academic_models import AcademicYear

        db_session.add(
            AcademicYear(
                id=_uuid.UUID(f"00000000-0000-0000-0000-0000000000{suffix}"),
                branch_id=_uuid.UUID(BRANCH),
                name=f"{start}-{end}",
                start_year=start,
                end_year=end,
                status="active",
                is_deleted=False,
            )
        )

    @pytest.mark.usefixtures("seed_data")
    async def test_override_duration_and_course_name(
        self, client, seed_data, db_session
    ):
        import uuid as _uuid

        from sqlalchemy import select

        from app.modules.academic.models.academic_models import Course
        from app.modules.batch.models.batch_models import Batch

        # 2026-27 exists so a 2-year batch starting 2025 has its end year.
        self._add_year(db_session, "b1", 2026, 2027)
        await db_session.commit()

        token = await _login(client)
        content = (
            "Name,Class,Target,Batch,Roll No,Course_opt,Academic_year\n"
            "Nia Roy,11,NEET,ELITE-2Y,O-001,NEET 2-Year Elite,2025-2027\n"
        ).encode("utf-8")
        resp = await client.post(
            f"/api/v1/students/import?branch_id={BRANCH}&create_missing_batches=true",
            files={"file": ("o.csv", content, "text/csv")},
            cookies={"access_token": token},
        )
        data = resp.json()
        assert data["imported"] == 1
        assert data["batches_created"] == ["ELITE-2Y"]

        # A 2-year course gets a duration-suffixed code + the custom name.
        course = (
            await db_session.execute(
                select(Course).where(
                    Course.code == "NEET-2Y",
                    Course.branch_id == _uuid.UUID(BRANCH),
                )
            )
        ).scalar_one()
        assert course.duration_years == 2
        assert course.name == "NEET 2-Year Elite"

        batch = (
            await db_session.execute(
                select(Batch).where(Batch.code == "ELITE-2Y")
            )
        ).scalar_one()
        # Spans the 2025 seed year -> the new 2026 year.
        assert batch.start_academic_year_id == _uuid.UUID(
            "00000000-0000-0000-0000-000000000030"
        )
        assert batch.end_academic_year_id == _uuid.UUID(
            "00000000-0000-0000-0000-0000000000b1"
        )

    @pytest.mark.usefixtures("seed_data")
    async def test_override_academic_year_pins_start_against_default(
        self, client, seed_data, db_session
    ):
        """With a later year present (which would be the default intake), an
        Academic_year override still pins the batch to the year it names."""
        import uuid as _uuid

        from sqlalchemy import select

        from app.modules.batch.models.batch_models import Batch

        self._add_year(db_session, "b2", 2026, 2027)  # default pick = 2026
        await db_session.commit()

        token = await _login(client)
        content = (
            "Name,Class,Target,Batch,Roll No,Academic_year\n"
            "Om Shah,12,NEET,AY25-A,P-001,2025-2026\n"  # pin to 2025
        ).encode("utf-8")
        resp = await client.post(
            f"/api/v1/students/import?branch_id={BRANCH}&create_missing_batches=true",
            files={"file": ("p.csv", content, "text/csv")},
            cookies={"access_token": token},
        )
        assert resp.json()["batches_created"] == ["AY25-A"]
        batch = (
            await db_session.execute(
                select(Batch).where(Batch.code == "AY25-A")
            )
        ).scalar_one()
        assert batch.start_academic_year_id == _uuid.UUID(
            "00000000-0000-0000-0000-000000000030"
        )

    @pytest.mark.usefixtures("seed_data")
    async def test_preview_reflects_overrides(self, client, seed_data, db_session):
        self._add_year(db_session, "b3", 2026, 2027)
        await db_session.commit()

        token = await _login(client)
        content = (
            "Name,Class,Target,Batch,Roll No,Course_opt,Academic_year\n"
            "Pia Jain,11,NEET,DLX-2Y,Q-001,NEET Deluxe,2025-2027\n"
        ).encode("utf-8")
        resp = await client.post(
            f"/api/v1/students/import/preview?branch_id={BRANCH}",
            files={"file": ("q.csv", content, "text/csv")},
            cookies={"access_token": token},
        )
        data = resp.json()
        b = {x["code"]: x for x in data["batches"]}["DLX-2Y"]
        assert b["suggested_course_name"] == "NEET Deluxe"
        assert b["suggested_course_code"] == "NEET-2Y"
        assert b["creatable"] is True


class TestStudentImportConsistency:
    """§3 cross-field validation: contradictions are errors, soft mismatches
    are warnings."""

    @pytest.mark.usefixtures("seed_data")
    async def test_class_12_two_year_is_error(self, client, seed_data):
        token = await _login(client)
        content = (
            "Name,Class,Target,Batch,Roll No,Duration\n"
            "Sam P,12,NEET,BATCH-A,V-001,2 Years\n"  # 12th can't be 2-Year
        ).encode("utf-8")
        resp = await client.post(
            f"/api/v1/students/import?branch_id={BRANCH}",
            files={"file": ("v.csv", content, "text/csv")},
            cookies={"access_token": token},
        )
        data = resp.json()
        assert data["imported"] == 0
        assert data["skipped"] == 1
        assert any("Class 12 must be a 1-Year" in e for e in data["errors"])

    @pytest.mark.usefixtures("seed_data")
    async def test_academic_year_span_must_match_duration(self, client, seed_data):
        token = await _login(client)
        content = (
            "Name,Class,Target,Batch,Roll No,Duration,Academic_year\n"
            "Vik T,11,NEET,BATCH-A,V-002,2 Years,2025-2026\n"  # span 1 != dur 2
        ).encode("utf-8")
        resp = await client.post(
            f"/api/v1/students/import?branch_id={BRANCH}",
            files={"file": ("v.csv", content, "text/csv")},
            cookies={"access_token": token},
        )
        data = resp.json()
        assert data["imported"] == 0
        assert any("doesn't match Duration" in e for e in data["errors"])

    @pytest.mark.usefixtures("seed_data")
    async def test_class_9_targeting_neet_imports_with_warning(
        self, client, seed_data
    ):
        token = await _login(client)
        content = (
            "Name,Class,Target,Batch,Roll No\n"
            "Tina Q,9,NEET,BATCH-A,V-003\n"  # 9th can't sit NEET yet
        ).encode("utf-8")
        resp = await client.post(
            f"/api/v1/students/import?branch_id={BRANCH}",
            files={"file": ("v.csv", content, "text/csv")},
            cookies={"access_token": token},
        )
        data = resp.json()
        assert data["imported"] == 1  # imported anyway
        assert any("Class 9 targeting NEET" in w for w in data["warnings"])

    @pytest.mark.usefixtures("seed_data")
    async def test_conflicting_overrides_for_one_code_block_creation(
        self, client, seed_data
    ):
        """Two rows give the same batch code different Durations — the batch is
        not guessed; both rows report the disagreement."""
        token = await _login(client)
        content = (
            "Name,Class,Target,Batch,Roll No,Duration\n"
            "Uma R,11,NEET,MIX-1,V-004,1 Year\n"
            "Ravi S,11,NEET,MIX-1,V-005,2 Years\n"
        ).encode("utf-8")
        resp = await client.post(
            f"/api/v1/students/import?branch_id={BRANCH}&create_missing_batches=true",
            files={"file": ("v.csv", content, "text/csv")},
            cookies={"access_token": token},
        )
        data = resp.json()
        assert data["imported"] == 0
        assert data["batches_created"] == []
        assert any(
            "rows disagree on Duration" in e for e in data["errors"]
        )

    @pytest.mark.usefixtures("seed_data")
    async def test_skipped_row_does_not_poison_batch_overrides(
        self, client, seed_data
    ):
        """Review #1: a row that will be skipped (here a §3 contradiction) must
        not contribute its Duration to a batch's override-conflict detection and
        block the valid rows that share the code. The valid row creates a
        1-Year batch; without the fix the skipped row's '2 Years' fabricated a
        Duration conflict that blocked it."""
        token = await _login(client)
        content = (
            "Name,Class,Target,Batch,Roll No,Duration\n"
            "Valid Vidya,12,NEET,POISON-A,P-1,1 Year\n"   # valid -> 1-year batch
            "Bad Bharat,12,NEET,POISON-A,P-2,2 Years\n"   # §3 error -> skipped
        ).encode("utf-8")
        resp = await client.post(
            f"/api/v1/students/import?branch_id={BRANCH}&create_missing_batches=true",
            files={"file": ("v.csv", content, "text/csv")},
            cookies={"access_token": token},
        )
        data = resp.json()
        # The skipped row's conflicting Duration must NOT block the batch.
        assert data["batches_created"] == ["POISON-A"]
        assert data["imported"] == 1
        # The bad row is reported as a §3 error; the valid row is never blamed
        # for a fabricated "rows disagree" conflict.
        assert any("1-Year" in e for e in data["errors"])
        assert not any("disagree" in e for e in data["errors"])

    @pytest.mark.usefixtures("seed_data")
    async def test_preview_counts_consistency_errors_and_warnings(
        self, client, seed_data
    ):
        token = await _login(client)
        content = (
            "Name,Class,Target,Batch,Roll No,Duration\n"
            "Sam P,12,NEET,BATCH-A,V-010,2 Years\n"  # error
            "Tina Q,9,NEET,BATCH-A,V-011\n"           # warning
        ).encode("utf-8")
        resp = await client.post(
            f"/api/v1/students/import/preview?branch_id={BRANCH}",
            files={"file": ("v.csv", content, "text/csv")},
            cookies={"access_token": token},
        )
        data = resp.json()
        assert data["rows_invalid_consistency"] == 1
        assert data["rows_with_warnings"] == 1
        # The error row is not importable; the warning row still is.
        assert data["importable_rows"] == 1


class TestStudentImportSubjectSkeleton:
    """§8: a new course gets its subject skeleton from the Syllabus/Target, but
    an existing course's subjects are never overwritten."""

    @staticmethod
    async def _course_subjects(db_session, code):
        import uuid as _uuid

        from sqlalchemy import select

        from app.modules.academic.models.academic_models import Course, Subject

        course = (
            await db_session.execute(
                select(Course).where(
                    Course.code == code, Course.branch_id == _uuid.UUID(BRANCH)
                )
            )
        ).scalar_one()
        subs = (
            await db_session.execute(
                select(Subject).where(Subject.course_id == course.id)
            )
        ).scalars().all()
        return {s.name for s in subs}

    @pytest.mark.usefixtures("seed_data")
    async def test_new_neet_batch_creates_subject_skeleton(
        self, client, seed_data, db_session
    ):
        token = await _login(client)
        content = _csv("Asha,11,NEET,SKEL-A,SK-001")
        resp = await client.post(
            f"/api/v1/students/import?branch_id={BRANCH}&create_missing_batches=true",
            files={"file": ("s.csv", content, "text/csv")},
            cookies={"access_token": token},
        )
        data = resp.json()
        assert data["subjects_created"] == 4
        assert await self._course_subjects(db_session, "NEET") == {
            "Physics",
            "Chemistry",
            "Botany",
            "Zoology",
        }

    @pytest.mark.usefixtures("seed_data")
    async def test_skeleton_created_once_per_course(self, client, seed_data):
        token = await _login(client)
        content = _csv(
            "Asha,11,NEET,SK-A,SK-010",
            "Bina,11,NEET,SK-B,SK-011",  # same NEET course, different batch
        )
        resp = await client.post(
            f"/api/v1/students/import?branch_id={BRANCH}&create_missing_batches=true",
            files={"file": ("s.csv", content, "text/csv")},
            cookies={"access_token": token},
        )
        data = resp.json()
        assert sorted(data["batches_created"]) == ["SK-A", "SK-B"]
        # Both batches share the NEET course, so its skeleton is made just once.
        assert data["subjects_created"] == 4

    @pytest.mark.usefixtures("seed_data")
    async def test_explicit_syllabus_overrides_subject_set(
        self, client, seed_data, db_session
    ):
        token = await _login(client)
        content = (
            "Name,Class,Target,Batch,Roll No,Syllabus\n"
            "Cara,11,Other,OTH-A,SK-020,JEE\n"  # Other has no default set
        ).encode("utf-8")
        resp = await client.post(
            f"/api/v1/students/import?branch_id={BRANCH}&create_missing_batches=true",
            files={"file": ("s.csv", content, "text/csv")},
            cookies={"access_token": token},
        )
        data = resp.json()
        assert data["subjects_created"] == 3
        assert await self._course_subjects(db_session, "GEN") == {
            "Physics",
            "Chemistry",
            "Mathematics",
        }

    @pytest.mark.usefixtures("seed_data")
    async def test_mht_cet_creates_union_subjects(self, client, seed_data):
        """MHT-CET now carries the union of subjects on the course (P/C/M/B);
        each student's stream selects their subset at read time."""
        token = await _login(client)
        content = _csv("Dev,11,MHT-CET,MHT-A,SK-030")
        resp = await client.post(
            f"/api/v1/students/import?branch_id={BRANCH}&create_missing_batches=true",
            files={"file": ("s.csv", content, "text/csv")},
            cookies={"access_token": token},
        )
        data = resp.json()
        assert data["batches_created"] == ["MHT-A"]
        assert data["subjects_created"] == 4  # P, C, M, B union

    @pytest.mark.usefixtures("seed_data")
    async def test_neet_with_pcm_syllabus_is_error(self, client, seed_data):
        token = await _login(client)
        content = (
            "Name,Class,Target,Batch,Roll No,Syllabus\n"
            "Eve,11,NEET,BATCH-A,SK-040,PCM\n"  # NEET needs biology
        ).encode("utf-8")
        resp = await client.post(
            f"/api/v1/students/import?branch_id={BRANCH}",
            files={"file": ("s.csv", content, "text/csv")},
            cookies={"access_token": token},
        )
        data = resp.json()
        assert data["imported"] == 0
        assert any("needs a Biology syllabus" in e for e in data["errors"])

    @pytest.mark.usefixtures("seed_data")
    async def test_undo_removes_skeleton_but_keeps_chaptered_subject(
        self, client, seed_data, db_session
    ):
        import uuid as _uuid

        from sqlalchemy import select

        from app.modules.academic.models.academic_models import (
            Chapter,
            Course,
            Subject,
        )

        token = await _login(client)
        content = _csv("Fae,11,NEET,UND-SK,SK-050")
        resp = await client.post(
            f"/api/v1/students/import?branch_id={BRANCH}&create_missing_batches=true",
            files={"file": ("s.csv", content, "text/csv")},
            cookies={"access_token": token},
        )
        data = resp.json()
        import_id = data["import_id"]
        assert data["subjects_created"] == 4

        # A syllabus import later loads a chapter onto one subject.
        course = (
            await db_session.execute(
                select(Course).where(
                    Course.code == "NEET", Course.branch_id == _uuid.UUID(BRANCH)
                )
            )
        ).scalar_one()
        physics = (
            await db_session.execute(
                select(Subject).where(
                    Subject.course_id == course.id, Subject.name == "Physics"
                )
            )
        ).scalar_one()
        db_session.add(
            Chapter(
                id=_uuid.uuid4(),
                branch_id=_uuid.UUID(BRANCH),
                academic_year_id=physics.academic_year_id,
                subject_id=physics.id,
                name="Kinematics",
                order=0,
                is_deleted=False,
            )
        )
        await db_session.commit()

        undo = await client.post(
            f"/api/v1/students/import/{import_id}/undo?branch_id={BRANCH}",
            cookies={"access_token": token},
        )
        u = undo.json()
        # The 3 bare subjects go; Physics (now has a chapter) is protected.
        assert u["subjects_deleted"] == 3
        remaining = (
            await db_session.execute(
                select(Subject).where(
                    Subject.course_id == course.id, Subject.is_deleted == False
                )
            )
        ).scalars().all()
        assert {s.name for s in remaining} == {"Physics"}


class TestStudentImportCurriculum:
    """§3 syllabus auto-population: a new course's subjects get chapters +
    topics from the bundled master curriculum, and undo reclaims them."""

    @staticmethod
    async def _live_chapter_count(db_session, course_code: str) -> int:
        import uuid as _uuid

        from sqlalchemy import func, select

        from app.modules.academic.models.academic_models import (
            Chapter,
            Course,
            Subject,
        )

        course = (
            await db_session.execute(
                select(Course).where(
                    Course.code == course_code,
                    Course.branch_id == _uuid.UUID(BRANCH),
                )
            )
        ).scalar_one()
        return (
            await db_session.execute(
                select(func.count())
                .select_from(Chapter)
                .join(Subject, Chapter.subject_id == Subject.id)
                .where(
                    Subject.course_id == course.id,
                    Chapter.is_deleted == False,
                )
            )
        ).scalar_one()

    @pytest.mark.usefixtures("seed_data")
    async def test_import_populates_chapters_from_master_curriculum(
        self, client, seed_data, db_session
    ):
        token = await _login(client)
        content = _csv("Asha,11,NEET,CUR-A,CU-001")
        resp = await client.post(
            f"/api/v1/students/import?branch_id={BRANCH}&create_missing_batches=true",
            files={"file": ("s.csv", content, "text/csv")},
            cookies={"access_token": token},
        )
        assert resp.json()["batches_created"] == ["CUR-A"]
        # The NEET course's subjects now carry real chapters, not a bare skeleton.
        assert await self._live_chapter_count(db_session, "NEET") > 0

    @pytest.mark.usefixtures("seed_data")
    async def test_undo_reclaims_auto_populated_curriculum(
        self, client, seed_data, db_session
    ):
        token = await _login(client)
        content = _csv("Bina,11,NEET,CUR-B,CU-002")
        resp = await client.post(
            f"/api/v1/students/import?branch_id={BRANCH}&create_missing_batches=true",
            files={"file": ("s.csv", content, "text/csv")},
            cookies={"access_token": token},
        )
        import_id = resp.json()["import_id"]
        assert await self._live_chapter_count(db_session, "NEET") > 0

        undo = await client.post(
            f"/api/v1/students/import/{import_id}/undo?branch_id={BRANCH}",
            cookies={"access_token": token},
        )
        assert undo.json()["subjects_deleted"] == 4
        # No foreign chapters were added, so all auto-created curriculum is gone.
        await db_session.commit()  # refresh snapshot to see undo's commit
        assert await self._live_chapter_count(db_session, "NEET") == 0
