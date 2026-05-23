import csv
import io
import uuid
from typing import Any

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.academic.repositories import academic_repository
from app.modules.audit.services import audit_service
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


async def import_students(
    session: AsyncSession,
    file: UploadFile,
    branch_id: uuid.UUID,
    current_user_id: uuid.UUID,
    ip_address: str | None = None,
    *,
    standard: str | None = None,
    target_exam: str | None = None,
) -> dict[str, Any]:
    # Defer to the student service's enrolment-field validator so the
    # error messages match what the create endpoint returns.
    from app.modules.student.services.student_service import (
        _validate_enrolment_fields,
    )
    _validate_enrolment_fields(standard, target_exam)

    content = await file.read()
    filename = (file.filename or "").lower()

    if filename.endswith(".csv"):
        rows = _parse_csv(content)
    elif filename.endswith((".xlsx", ".xls")):
        rows = _parse_xlsx(content)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file type. Use .csv or .xlsx",
        )

    years = await academic_repository.list_academic_years(session, branch_id)
    if not years:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No academic year exists for this branch. Create one first.",
        )
    academic_year_id = years[0].id

    imported = 0
    skipped = 0
    errors: list[str] = []

    for idx, row in enumerate(rows, start=2):  # row 1 is header
        kwargs = _row_to_student_kwargs(row, branch_id, academic_year_id)
        if kwargs is None:
            skipped += 1
            errors.append(f"Row {idx}: missing required 'Name'")
            continue
        # Apply the per-import standard + target_exam to every row.
        if standard is not None:
            kwargs["standard"] = standard
        if target_exam is not None:
            kwargs["target_exam"] = target_exam
        try:
            await student_repository.create(session, **kwargs)
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
        new_values={"imported": imported, "skipped": skipped},
        ip_address=ip_address,
        branch_id=branch_id,
    )

    return {"imported": imported, "skipped": skipped, "errors": errors}
