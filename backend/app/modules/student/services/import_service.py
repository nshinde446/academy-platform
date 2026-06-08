import csv
import io
import uuid
from collections import Counter
from datetime import date
from typing import Any

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.academic.repositories import academic_repository
from app.modules.audit.services import audit_service
from app.modules.batch.models.batch_models import Batch
from app.modules.student.models.student_models import StudentBatchMapping
from app.modules.student.repositories import student_repository

# Excel/CSV column -> Student field
COLUMN_MAPPING = {
    "name": "name",
    "roll no": "enrollment_number",
    "roll_no": "enrollment_number",
    "rollno": "enrollment_number",
    "enrollment no": "enrollment_number",
    "enrollment_number": "enrollment_number",
    "email": "email",
    "phone": "phone",
    "parent mobile": "parent_mobile",
    "parent_mobile": "parent_mobile",
    "gender": "gender",
    "district": "district",
    "caste": "caste",
    "username": "username",
    "rfid": "rfid_number",
    "rfidnumber": "rfid_number",
    "rfid_number": "rfid_number",
    "rfid number": "rfid_number",
    # Per-row enrolment fields. Each row picks its own class / exam /
    # batch — the dialog no longer carries them.
    "class": "standard",
    "standard": "standard",
    "target": "target_exam",
    "target exam": "target_exam",
    "target_exam": "target_exam",
    "batch": "_batch_code",
    "batch code": "_batch_code",
    "batch_code": "_batch_code",
}

# When a referenced batch does not exist yet we can create it on import.
# The Target column drives which course the new batch instantiates and a
# sensible default exam date (month/day, anchored to the academic year's
# end year) so /insights has a pace anchor. Admins can edit both later.
TARGET_COURSE: dict[str, tuple[str, str]] = {
    "NEET": ("NEET", "NEET Preparation"),
    "JEE-Main": ("JEE", "JEE Preparation"),
    "JEE-Advanced": ("JEE", "JEE Preparation"),
    "MHT-CET": ("MHT-CET", "MHT-CET Preparation"),
    "Both": ("NEET-JEE", "NEET + JEE Preparation"),
    "Foundation": ("FND", "Foundation Programme"),
    "Other": ("GEN", "General Programme"),
}
_FALLBACK_COURSE = ("GEN", "General Programme")

TARGET_EXAM_MONTH_DAY: dict[str, tuple[int, int]] = {
    "NEET": (5, 4),
    "JEE-Main": (4, 6),
    "JEE-Advanced": (5, 18),
    "MHT-CET": (4, 24),
    "Both": (5, 4),
}


def _split_name(value: str) -> tuple[str, str]:
    parts = value.strip().split(maxsplit=1)
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], parts[1]


def _normalize(header: str) -> str:
    return header.strip().lower()


def _norm_code(code: str) -> str:
    """Matching key for a batch code: trimmed, whitespace-collapsed,
    case-insensitive. Keeps lookups forgiving of stray spacing / casing
    without rewriting the code's own punctuation (so e.g. ``JEE--11-A``
    and ``JEE-Main-11-A`` stay distinct and surface separately)."""
    return " ".join(code.split()).strip().lower()


def _course_for_target(target: str | None) -> tuple[str, str]:
    return TARGET_COURSE.get(target or "", _FALLBACK_COURSE)


def _suggested_exam_date(target: str | None, end_year: int | None) -> date | None:
    md = TARGET_EXAM_MONTH_DAY.get(target or "")
    if md is None or end_year is None:
        return None
    return date(end_year, md[0], md[1])


def _dominant_target(counter: Counter) -> str | None:
    if not counter:
        return None
    return counter.most_common(1)[0][0]


def _parse_csv(content: bytes) -> list[dict[str, Any]]:
    text = content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    return [dict(row) for row in reader]


def _parse_xlsx(content: bytes) -> list[dict[str, Any]]:
    from openpyxl import load_workbook

    wb = load_workbook(io.BytesIO(content), data_only=True, read_only=True)
    ws = wb.active
    if ws is None:
        return []
    rows = ws.iter_rows(values_only=True)
    try:
        headers = [str(h) if h is not None else "" for h in next(rows)]
    except StopIteration:
        return []
    out: list[dict[str, Any]] = []
    for row in rows:
        record = {
            headers[i]: ("" if row[i] is None else str(row[i]))
            for i in range(min(len(headers), len(row)))
        }
        if any(v for v in record.values()):
            out.append(record)
    return out


def _parse_file(filename: str | None, content: bytes) -> list[dict[str, Any]]:
    name = (filename or "").lower()
    if name.endswith(".csv"):
        return _parse_csv(content)
    if name.endswith((".xlsx", ".xls")):
        return _parse_xlsx(content)
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Unsupported file type. Use .csv or .xlsx",
    )


def _row_to_student_kwargs(
    row: dict[str, Any], branch_id: uuid.UUID, academic_year_id: uuid.UUID
) -> dict[str, Any] | None:
    mapped: dict[str, Any] = {}
    for raw_key, raw_value in row.items():
        if raw_key is None:
            continue
        field = COLUMN_MAPPING.get(_normalize(raw_key))
        if field is None:
            continue
        value = (raw_value or "").strip() if isinstance(raw_value, str) else raw_value
        if value in ("", None):
            continue
        mapped[field] = value

    name_value = mapped.pop("name", None)
    if name_value:
        first, last = _split_name(str(name_value))
        mapped["first_name"] = first
        mapped["last_name"] = last

    if not mapped.get("first_name"):
        return None

    mapped["branch_id"] = branch_id
    mapped["academic_year_id"] = academic_year_id
    mapped.setdefault("last_name", "")
    return mapped


async def _load_batch_index(
    session: AsyncSession, branch_id: uuid.UUID
) -> dict[str, uuid.UUID]:
    """Map normalized batch code -> batch id for the branch's live batches."""
    result = await session.execute(
        select(Batch).where(
            Batch.branch_id == branch_id,
            Batch.is_deleted == False,  # noqa: E712
        )
    )
    return {_norm_code(b.code): b.id for b in result.scalars().all()}


async def _get_or_create_course(
    session: AsyncSession, branch_id: uuid.UUID, code: str, name: str
):
    courses = await academic_repository.list_courses(session, branch_id)
    for c in courses:
        if c.code.strip().lower() == code.lower():
            return c
    return await academic_repository.create_course(
        session,
        branch_id=branch_id,
        name=name,
        code=code,
        duration_years=1,
    )


async def _create_derived_batch(
    session: AsyncSession,
    branch_id: uuid.UUID,
    code: str,
    target: str | None,
    academic_year,
    current_user_id: uuid.UUID,
    ip_address: str | None,
):
    """Create a batch for an unknown code, deriving its course and exam
    date from the dominant Target of the students referencing it."""
    from app.modules.batch.schemas.batch_schemas import BatchCreate
    from app.modules.batch.services import batch_service

    course_code, course_name = _course_for_target(target)
    course = await _get_or_create_course(session, branch_id, course_code, course_name)
    data = BatchCreate(
        branch_id=branch_id,
        start_academic_year_id=academic_year.id,
        course_id=course.id,
        name=code,
        code=code,
        capacity=30,
        target_exam_date=_suggested_exam_date(target, academic_year.end_year),
    )
    return await batch_service.create_batch(
        session, data, current_user_id, ip_address
    )


async def preview_import(
    session: AsyncSession,
    file: UploadFile,
    branch_id: uuid.UUID,
) -> dict[str, Any]:
    """Dry-run a student upload: report row issues and, crucially, which
    batch codes already exist vs. are missing, so the admin can create the
    missing ones (with course/exam-date derived from Target) before any
    rows are written."""
    from app.modules.student.services.student_service import (
        _validate_enrolment_fields,
    )

    content = await file.read()
    rows = _parse_file(file.filename, content)

    years = await academic_repository.list_academic_years(session, branch_id)
    academic_year = years[0] if years else None
    end_year = academic_year.end_year if academic_year else None
    placeholder_year_id = academic_year.id if academic_year else uuid.uuid4()

    batch_index = await _load_batch_index(session, branch_id)

    total_rows = 0
    rows_missing_name = 0
    rows_invalid_enrolment = 0
    unbatched_rows = 0
    importable_rows = 0
    row_issues: list[str] = []

    # Group by normalized code; keep the first-seen display spelling and a
    # tally of Targets so we can derive a course for the missing ones.
    code_display: dict[str, str] = {}
    code_counts: Counter = Counter()
    code_targets: dict[str, Counter] = {}

    for idx, row in enumerate(rows, start=2):  # row 1 is header
        total_rows += 1
        kwargs = _row_to_student_kwargs(row, branch_id, placeholder_year_id)
        if kwargs is None:
            rows_missing_name += 1
            if len(row_issues) < 20:
                row_issues.append(f"Row {idx}: missing required 'Name'")
            continue

        target = kwargs.get("target_exam")
        try:
            _validate_enrolment_fields(kwargs.get("standard"), target)
            enrolment_ok = True
        except HTTPException as exc:
            enrolment_ok = False
            rows_invalid_enrolment += 1
            if len(row_issues) < 20:
                row_issues.append(f"Row {idx}: {exc.detail}")

        code = kwargs.get("_batch_code")
        if code:
            norm = _norm_code(str(code))
            code_display.setdefault(norm, str(code).strip())
            code_counts[norm] += 1
            code_targets.setdefault(norm, Counter())
            if target:
                code_targets[norm][target] += 1
        else:
            unbatched_rows += 1

        if enrolment_ok:
            importable_rows += 1

    batches: list[dict[str, Any]] = []
    existing = 0
    for norm, display in code_display.items():
        exists = norm in batch_index
        if exists:
            existing += 1
        target = _dominant_target(code_targets.get(norm, Counter()))
        course_code, course_name = _course_for_target(target)
        batches.append(
            {
                "code": display,
                "student_count": code_counts[norm],
                "exists": exists,
                "target": target,
                "suggested_course_code": None if exists else course_code,
                "suggested_course_name": None if exists else course_name,
                "suggested_exam_date": (
                    None if exists else _suggested_exam_date(target, end_year)
                ),
            }
        )

    # Missing batches first, then by how many students depend on them.
    batches.sort(key=lambda b: (b["exists"], -b["student_count"]))

    return {
        "total_rows": total_rows,
        "importable_rows": importable_rows,
        "rows_missing_name": rows_missing_name,
        "rows_invalid_enrolment": rows_invalid_enrolment,
        "unbatched_rows": unbatched_rows,
        "existing_batches": existing,
        "missing_batches": len(code_display) - existing,
        "batches": batches,
        "row_issues": row_issues,
    }


async def import_students(
    session: AsyncSession,
    file: UploadFile,
    branch_id: uuid.UUID,
    current_user_id: uuid.UUID,
    create_missing_batches: bool = False,
    ip_address: str | None = None,
) -> dict[str, Any]:
    from app.modules.student.services.student_service import (
        _validate_enrolment_fields,
    )

    content = await file.read()
    rows = _parse_file(file.filename, content)

    years = await academic_repository.list_academic_years(session, branch_id)
    if not years:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No academic year exists for this branch. Create one first.",
        )
    academic_year = years[0]
    academic_year_id = academic_year.id

    batch_index = await _load_batch_index(session, branch_id)
    batches_created: list[str] = []

    # Optionally create any referenced-but-missing batches up front, so the
    # course/exam-date is decided once per code from its dominant Target.
    if create_missing_batches:
        missing: dict[str, tuple[str, Counter]] = {}
        for row in rows:
            kwargs = _row_to_student_kwargs(row, branch_id, academic_year_id)
            if kwargs is None:
                continue
            code = kwargs.get("_batch_code")
            if not code:
                continue
            norm = _norm_code(str(code))
            if norm in batch_index:
                continue
            display, counter = missing.setdefault(
                norm, (str(code).strip(), Counter())
            )
            target = kwargs.get("target_exam")
            if target:
                counter[target] += 1

        for norm, (display, counter) in missing.items():
            try:
                batch = await _create_derived_batch(
                    session,
                    branch_id,
                    display,
                    _dominant_target(counter),
                    academic_year,
                    current_user_id,
                    ip_address,
                )
                batch_index[norm] = batch.id
                batches_created.append(display)
            except Exception:  # noqa: BLE001 - rows fall back to "unknown batch"
                continue

    imported = 0
    skipped = 0
    errors: list[str] = []

    for idx, row in enumerate(rows, start=2):  # row 1 is header
        kwargs = _row_to_student_kwargs(row, branch_id, academic_year_id)
        if kwargs is None:
            skipped += 1
            errors.append(f"Row {idx}: missing required 'Name'")
            continue

        batch_code = kwargs.pop("_batch_code", None)
        try:
            _validate_enrolment_fields(
                kwargs.get("standard"), kwargs.get("target_exam")
            )
        except HTTPException as exc:
            skipped += 1
            errors.append(f"Row {idx}: {exc.detail}")
            continue

        batch_id: uuid.UUID | None = None
        if batch_code:
            batch_id = batch_index.get(_norm_code(str(batch_code)))
            if batch_id is None:
                skipped += 1
                errors.append(f"Row {idx}: unknown batch code '{batch_code}'")
                continue

        try:
            student = await student_repository.create(session, **kwargs)
            if batch_id is not None:
                session.add(
                    StudentBatchMapping(
                        student_id=student.id,
                        batch_id=batch_id,
                        branch_id=branch_id,
                    )
                )
                await session.flush()
            imported += 1
        except Exception as exc:  # noqa: BLE001
            skipped += 1
            errors.append(f"Row {idx}: {exc}")

    await audit_service.log_action(
        session,
        user_id=current_user_id,
        action="IMPORT",
        table_name="students",
        record_id=uuid.uuid4(),
        new_values={
            "imported": imported,
            "skipped": skipped,
            "batches_created": batches_created,
        },
        ip_address=ip_address,
        branch_id=branch_id,
    )

    return {
        "imported": imported,
        "skipped": skipped,
        "errors": errors,
        "batches_created": batches_created,
    }
