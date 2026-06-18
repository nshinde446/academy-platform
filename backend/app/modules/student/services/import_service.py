import csv
import io
import re
import uuid
from collections import Counter
from datetime import date
from typing import Any

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.academic.repositories import academic_repository
from app.modules.audit.services import audit_service
from app.modules.batch.models.batch_models import Batch
from app.modules.student.models.student_models import Student, StudentBatchMapping
from app.modules.student.repositories import student_repository

# Reserved key the parsers stash the true source row number under. It is not a
# real column, so _row_to_student_kwargs (which only maps known headers) ignores
# it and it never reaches the Student model.
_ROW_KEY = "__row__"

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

# Subject skeletons per syllabus (design §2/§5). DEFAULTS the coaching can edit
# — §6 leaves Biology-vs-Botany/Zoology and the MHT-CET stream split as open
# decisions, so we only auto-create for the unambiguous tracks and skip the
# rest (no subjects rather than a wrong guess).
SUBJECT_SETS: dict[str, list[str]] = {
    "NEET": ["Physics", "Chemistry", "Botany", "Zoology"],
    "JEE": ["Physics", "Chemistry", "Mathematics"],
    "PCMB": ["Physics", "Chemistry", "Mathematics", "Biology"],
    "MHT-CET-PCM": ["Physics", "Chemistry", "Mathematics"],
    "MHT-CET-PCB": ["Physics", "Chemistry", "Biology"],
    "FOUNDATION": ["Science", "Mathematics", "Mental Ability"],
}

# Target -> default syllabus key when the row has no explicit Syllabus. MHT-CET
# and Other are intentionally absent: their subject set is ambiguous (§6), so
# without an explicit Syllabus we create no subjects.
TARGET_SYLLABUS: dict[str, str] = {
    "NEET": "NEET",
    "JEE-Main": "JEE",
    "JEE-Advanced": "JEE",
    "Both": "PCMB",
    "Foundation": "FOUNDATION",
}

# Free-text Syllabus values normalized to a SUBJECT_SETS key.
_SYLLABUS_ALIASES: dict[str, str] = {
    "neet": "NEET",
    "pcb": "NEET",
    "jee": "JEE",
    "pcm": "JEE",
    "pcmb": "PCMB",
    "both": "PCMB",
    "mht-cet-pcm": "MHT-CET-PCM",
    "mhtcet-pcm": "MHT-CET-PCM",
    "mht-cet-pcb": "MHT-CET-PCB",
    "mhtcet-pcb": "MHT-CET-PCB",
    "foundation": "FOUNDATION",
}

_SUBJECT_CODES: dict[str, str] = {
    "Physics": "PHY",
    "Chemistry": "CHE",
    "Mathematics": "MAT",
    "Biology": "BIO",
    "Botany": "BOT",
    "Zoology": "ZOO",
    "Science": "SCI",
    "Mental Ability": "MA",
}

# Subjects that satisfy a target's exam requirement, for §3 Target×Syllabus
# consistency: NEET needs a biology subject, JEE needs maths.
_BIO_SUBJECTS = {"biology", "botany", "zoology"}
_MATHS_SUBJECTS = {"mathematics", "maths"}


def _syllabus_key(syllabus: str | None, target: str | None) -> str | None:
    """Resolve the subject-set key: explicit Syllabus wins, else the Target
    default. Returns None when the set is ambiguous/unknown (skip subjects)."""
    if syllabus:
        return _SYLLABUS_ALIASES.get(syllabus.strip().lower())
    return TARGET_SYLLABUS.get(target or "")


def _subjects_for(key: str | None) -> list[str]:
    return SUBJECT_SETS.get(key or "", [])


def _subject_code(name: str) -> str:
    return _SUBJECT_CODES.get(name, name[:3].upper())


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


# --- Optional per-row batch override columns (design §5) --------------------
# These let an admin who already knows their structure pin a created batch's
# course name, duration, and intake year instead of everything being a generic
# 1-year course derived from Target. All optional; explicit value wins, else we
# fall back to the Target-derived defaults. They are read straight off the raw
# row (NOT via COLUMN_MAPPING) so they never reach the Student model.
_OVERRIDE_HEADERS = {
    "course_opt": "course_opt",
    "course opt": "course_opt",
    "course": "course_opt",
    "course name": "course_opt",
    "duration": "duration",
    "academic_year": "academic_year",
    "academic year": "academic_year",
    "syllabus": "syllabus",
}


def _row_overrides(row: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    for raw_key, raw_value in row.items():
        if raw_key is None:
            continue
        key = _OVERRIDE_HEADERS.get(_normalize(raw_key))
        if key is None or key in out:
            continue
        value = str(raw_value).strip() if raw_value not in (None, "") else ""
        if value:
            out[key] = value
    return out


def _merge_overrides(into: dict[str, str], row_overrides: dict[str, str]) -> None:
    """First-seen non-empty value per field wins, so a batch referenced by many
    rows gets one stable set of overrides regardless of row order."""
    for k, v in row_overrides.items():
        into.setdefault(k, v)


def _parse_duration(value: str | None) -> int | None:
    """'2 Years' | '2yr' | '2' | '1 Year' -> int. Bounded to 1..6."""
    if not value:
        return None
    m = re.search(r"\d+", str(value))
    if not m:
        return None
    n = int(m.group())
    return n if 1 <= n <= 6 else None


def _parse_ay_span(value: str | None) -> tuple[int | None, int | None]:
    """'2026-2028' -> (2026, 2028); '2026-27' -> (2026, 2027); '2026' ->
    (2026, None). The end is the calendar end of the span, so span duration =
    end - start (a 2026-2028 span is a 2-year programme)."""
    if not value:
        return None, None
    nums = re.findall(r"\d{2,4}", str(value))
    if not nums:
        return None, None
    start = int(nums[0])
    if len(nums) == 1:
        return start, None
    end = int(nums[1])
    if end < 100:  # '2026-27' -> 2027
        end = (start // 100) * 100 + end
    return start, end


def _effective_duration_and_start(
    overrides: dict[str, str] | None,
) -> tuple[int, int | None]:
    """Resolve (duration_years, start_year) from the override columns. Explicit
    Duration wins; otherwise an Academic_year *span* implies the duration. Start
    year comes from Academic_year when given (else None = use the picked year)."""
    overrides = overrides or {}
    duration = _parse_duration(overrides.get("duration"))
    ay_start, ay_end = _parse_ay_span(overrides.get("academic_year"))
    if duration is None and ay_start is not None and ay_end is not None:
        duration = max(ay_end - ay_start, 1)
    return (duration or 1), ay_start


def _course_code_for(target: str | None, duration: int) -> str:
    """A course's identity includes its duration (design §1: 'NEET 2-Year' and
    'NEET 1-Year' are different courses), so a >1-year course gets a distinct,
    duration-suffixed code. 1-year keeps the bare code (backward compatible)."""
    base, _ = _course_for_target(target)
    return f"{base}-{duration}Y" if duration > 1 else base


def _course_name_for(
    target: str | None, duration: int, course_opt: str | None
) -> str:
    if course_opt:
        return course_opt
    _, base_name = _course_for_target(target)
    return f"{base_name} ({duration}-Year)" if duration > 1 else base_name


def _ay_by_start_year(years: list, start_year: int):
    for y in years:
        if y.start_year == start_year:
            return y
    return None


# --- Cross-field row validation (design §3: catch contradictions, don't ----
# silently coerce). Errors make a row non-importable; warnings are surfaced
# but allowed through.
_ONE_YEAR_CLASSES = {"12", "dropper"}
_EXAM_TARGETS = {"NEET", "JEE-Main", "JEE-Advanced", "Both"}


def _validate_row_consistency(
    standard: str | None,
    target: str | None,
    overrides: dict[str, str] | None,
) -> tuple[list[str], list[str]]:
    """Return (errors, warnings) for one row given its class, target, and
    override columns. Mirrors the §3 matrix, including the Target×Syllabus
    conflicts when an explicit Syllabus is given."""
    errors: list[str] = []
    warnings: list[str] = []
    overrides = overrides or {}
    cls = (standard or "").strip().lower()
    tgt = (target or "").strip()

    duration = _parse_duration(overrides.get("duration"))
    ay_start, ay_end = _parse_ay_span(overrides.get("academic_year"))
    span = (ay_end - ay_start) if (ay_start is not None and ay_end is not None) else None
    # Effective length: explicit Duration wins, else an Academic_year span.
    eff_duration = duration if duration is not None else span

    # E1/E2: 12th and Droppers are single-year programmes (one year before
    # the exam), so a multi-year length is a contradiction.
    if eff_duration is not None and eff_duration > 1 and cls in _ONE_YEAR_CLASSES:
        label = "Droppers" if cls == "dropper" else "Class 12"
        errors.append(
            f"{label} must be a 1-Year programme, not {eff_duration}-Year"
        )

    # E3: an explicit Academic_year span must agree with an explicit Duration.
    if duration is not None and span is not None and span != duration:
        errors.append(
            f"Academic_year span ({span}-Year) doesn't match Duration ({duration}-Year)"
        )

    # W1: an 11th explicitly put in a 1-Year programme finishes mid-program;
    # allowed (deliberate crash course) but worth flagging.
    if duration == 1 and cls == "11":
        warnings.append(
            "Class 11 in a 1-Year programme (crash course?) — confirm this is intended"
        )

    # W2: 9th/10th can't sit NEET/JEE; enrol as-is but flag (the Foundation
    # remap that would set aspiration_target isn't built yet).
    if cls in {"9", "10"} and tgt in _EXAM_TARGETS:
        warnings.append(
            f"Class {standard} targeting {tgt} — Foundation remap not yet "
            f"supported, enrolling as-is"
        )

    return errors, warnings


# --- Batch-code override conflict (design §3 "batch identity collision"): -----
# when many rows share a batch code but disagree on the course/length/year the
# new batch should have, that's an error, not a silent first-seen-wins.
_OVERRIDE_LABELS = {
    "course_opt": "Course_opt",
    "duration": "Duration",
    "academic_year": "Academic_year",
}


def _canon_override(field: str, value: str) -> str | None:
    """Canonical form so cosmetic differences ('2 Years' vs '2') aren't read as
    a conflict; returns None when the value doesn't parse to anything."""
    if field == "duration":
        d = _parse_duration(value)
        return str(d) if d is not None else None
    if field == "academic_year":
        start, end = _parse_ay_span(value)
        return None if start is None else f"{start}-{end}"
    return value.strip().lower()


def _track_override_values(
    store: dict[str, set[str]], row_overrides: dict[str, str]
) -> None:
    for field, value in row_overrides.items():
        canon = _canon_override(field, value)
        if canon:
            store.setdefault(field, set()).add(canon)


def _override_conflict(field_values: dict[str, set[str]]) -> str | None:
    conflicted = [f for f, vals in field_values.items() if len(vals) > 1]
    if not conflicted:
        return None
    return "rows disagree on " + ", ".join(
        _OVERRIDE_LABELS.get(f, f) for f in conflicted
    )


def _pick_academic_year(years: list):
    """Deterministically choose the academic year new students enrol into.

    ``list_academic_years`` has no ORDER BY, so indexing ``years[0]`` picked an
    arbitrary row — with more than one year on a branch that silently pinned
    every imported student (and every derived batch's start year) to the wrong
    year, and could even differ between preview and import. Default to the most
    recent year by ``start_year``."""
    if not years:
        return None
    return max(years, key=lambda y: y.start_year)


def _parse_csv(content: bytes) -> list[dict[str, Any]]:
    text = content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    out: list[dict[str, Any]] = []
    for row in reader:
        record = dict(row)
        # True source line (DictReader skips blank lines, so a running counter
        # would drift); used for accurate "Row N" diagnostics.
        record[_ROW_KEY] = reader.line_num
        out.append(record)
    return out


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
    for excel_row, row in enumerate(rows, start=2):  # header was row 1
        record = {
            headers[i]: ("" if row[i] is None else str(row[i]))
            for i in range(min(len(headers), len(row)))
        }
        if any(v for v in record.values()):
            # Real worksheet row number, so "Row N" matches what the admin
            # sees even when blank rows were skipped.
            record[_ROW_KEY] = excel_row
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
    session: AsyncSession,
    branch_id: uuid.UUID,
    code: str,
    name: str,
    duration_years: int = 1,
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
        duration_years=duration_years,
    )


async def _ensure_subject_skeleton(
    session: AsyncSession,
    branch_id: uuid.UUID,
    course,
    academic_year,
    syllabus_key: str | None,
    import_id: uuid.UUID | None,
) -> int:
    """Create the course's subject skeleton from the resolved syllabus (design
    §4 step 3). The §8 protection: only ever create when the course has *no*
    subjects yet — never overwrite an existing skeleton or a curriculum that a
    syllabus import has since loaded (§7.4). Returns how many were created.

    Matched by ``(course, name)`` ignoring AY, so the later syllabus import
    finds and reuses these subjects when it attaches chapters."""
    names = _subjects_for(syllabus_key)
    if not names:
        return 0
    existing = await academic_repository.list_subjects(session, branch_id, course.id)
    if existing:
        return 0
    for name in names:
        await academic_repository.create_subject(
            session,
            branch_id=branch_id,
            academic_year_id=academic_year.id,
            course_id=course.id,
            name=name,
            code=_subject_code(name),
            import_id=import_id,
        )
    return len(names)


async def _create_derived_batch(
    session: AsyncSession,
    branch_id: uuid.UUID,
    code: str,
    target: str | None,
    academic_year,
    current_user_id: uuid.UUID,
    ip_address: str | None,
    import_id: uuid.UUID | None = None,
    overrides: dict[str, str] | None = None,
    years: list | None = None,
) -> tuple[Any, int]:
    """Create a batch for an unknown code and its course's subject skeleton.
    Course, duration, intake year and exam date come from the optional override
    columns (Course_opt / Duration / Academic_year / Syllabus) when present,
    else are derived from the dominant Target. Batch (and any subjects it
    creates) are tagged with ``import_id`` so an "undo import" can reclaim them.
    Returns ``(batch, subjects_created)``."""
    from app.modules.batch.schemas.batch_schemas import BatchCreate
    from app.modules.batch.services import batch_service

    duration, start_year = _effective_duration_and_start(overrides)

    start_ay = academic_year
    if start_year is not None:
        start_ay = _ay_by_start_year(years or [], start_year)
        if start_ay is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"needs an academic year starting at {start_year} "
                    f"(create it first)"
                ),
            )

    course_code = _course_code_for(target, duration)
    course_name = _course_name_for(
        target, duration, (overrides or {}).get("course_opt")
    )
    course = await _get_or_create_course(
        session, branch_id, course_code, course_name, duration_years=duration
    )
    data = BatchCreate(
        branch_id=branch_id,
        start_academic_year_id=start_ay.id,
        course_id=course.id,
        name=code,
        code=code,
        capacity=30,
        # Exam happens in the calendar year the programme ends.
        target_exam_date=_suggested_exam_date(
            target, start_ay.start_year + duration
        ),
    )
    batch = await batch_service.create_batch(
        session, data, current_user_id, ip_address
    )
    if import_id is not None:
        batch.import_id = import_id
    syllabus_key = _syllabus_key((overrides or {}).get("syllabus"), target)
    subjects_created = await _ensure_subject_skeleton(
        session, branch_id, course, start_ay, syllabus_key, import_id
    )
    await session.flush()
    return batch, subjects_created


def _missing_batch_blocker(
    target: str | None,
    academic_year,
    courses_by_code: dict[str, Any],
    ay_start_years: set[int],
    overrides: dict[str, str] | None = None,
) -> str | None:
    """Dry-run the academic-year preconditions ``create_batch`` enforces: the
    batch needs both its start year and its end year (``start + duration - 1``)
    to exist. Returns a human reason if creation *would* fail, else ``None`` —
    so the preview warns before the admin commits instead of silently skipping.

    Honors the override columns (Duration / Academic_year) and the rule that an
    existing course with the resolved code pins the duration (design §1)."""
    if academic_year is None:
        return "no academic year exists for this branch"
    duration, start_year_override = _effective_duration_and_start(overrides)
    start_year = (
        start_year_override
        if start_year_override is not None
        else academic_year.start_year
    )
    if start_year not in ay_start_years:
        return f"needs an academic year starting at {start_year} (create it first)"
    course_code = _course_code_for(target, duration)
    existing = courses_by_code.get(course_code.lower())
    eff_duration = (
        max(int(existing.duration_years or 1), 1) if existing else duration
    )
    end_year_start = start_year + eff_duration - 1
    if end_year_start not in ay_start_years:
        return f"needs an academic year starting at {end_year_start} (create it first)"
    return None


def _row_number(row: dict[str, Any], fallback: int) -> int:
    n = row.get(_ROW_KEY)
    return n if isinstance(n, int) else fallback


def _dup_keys(kwargs: dict[str, Any]) -> tuple[str | None, str | None]:
    """Natural keys used to detect a student already on file: enrolment number
    and email, both case-/space-insensitive. Either may be absent."""
    enr = kwargs.get("enrollment_number")
    em = kwargs.get("email")
    return (
        str(enr).strip().lower() if enr else None,
        str(em).strip().lower() if em else None,
    )


async def _load_student_dedup_keys(
    session: AsyncSession, branch_id: uuid.UUID
) -> tuple[set[str], set[str]]:
    """Existing enrolment numbers and emails for the branch's live students.

    Neither column is unique at the DB level, so without this an admin who
    re-uploads the same file just doubles every student (the real incident that
    produced 2000 rows from a 1000-row file). Seeded into the per-import 'seen'
    sets so re-imports and within-file repeats are skipped, not duplicated."""
    result = await session.execute(
        select(Student.enrollment_number, Student.email).where(
            Student.branch_id == branch_id,
            Student.is_deleted == False,  # noqa: E712
        )
    )
    enrols: set[str] = set()
    emails: set[str] = set()
    for enr, em in result.all():
        if enr:
            enrols.add(enr.strip().lower())
        if em:
            emails.add(em.strip().lower())
    return enrols, emails


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
    academic_year = _pick_academic_year(years)
    placeholder_year_id = academic_year.id if academic_year else uuid.uuid4()

    batch_index = await _load_batch_index(session, branch_id)
    courses = await academic_repository.list_courses(session, branch_id)
    courses_by_code = {c.code.strip().lower(): c for c in courses}
    ay_start_years = {y.start_year for y in years}
    seen_enrols, seen_emails = await _load_student_dedup_keys(session, branch_id)

    total_rows = 0
    rows_missing_name = 0
    rows_invalid_enrolment = 0
    rows_invalid_consistency = 0
    rows_with_warnings = 0
    duplicate_rows = 0
    unbatched_rows = 0
    importable_rows = 0
    row_issues: list[str] = []

    # Group by normalized code; keep the first-seen display spelling and a
    # tally of Targets so we can derive a course for the missing ones.
    code_display: dict[str, str] = {}
    code_counts: Counter = Counter()
    code_targets: dict[str, Counter] = {}
    # First-seen Course_opt / Duration / Academic_year override per batch code,
    # plus the full set of distinct values per field so disagreements surface.
    code_overrides: dict[str, dict[str, str]] = {}
    code_override_values: dict[str, dict[str, set[str]]] = {}
    # Importable rows per code (valid + non-duplicate) so blocked batches can
    # be discounted from importable_rows once blockers are known.
    code_ok_counts: Counter = Counter()

    for idx, row in enumerate(rows, start=2):  # row 1 is header
        rownum = _row_number(row, idx)
        total_rows += 1
        kwargs = _row_to_student_kwargs(row, branch_id, placeholder_year_id)
        if kwargs is None:
            rows_missing_name += 1
            if len(row_issues) < 20:
                row_issues.append(f"Row {rownum}: missing required 'Name'")
            continue

        target = kwargs.get("target_exam")
        try:
            _validate_enrolment_fields(kwargs.get("standard"), target)
            enrolment_ok = True
        except HTTPException as exc:
            enrolment_ok = False
            rows_invalid_enrolment += 1
            if len(row_issues) < 20:
                row_issues.append(f"Row {rownum}: {exc.detail}")

        # §3 cross-field checks: contradictions block the row; warnings pass.
        row_ov = _row_overrides(row)
        c_errors, c_warnings = _validate_row_consistency(
            kwargs.get("standard"), target, row_ov
        )
        consistency_ok = not c_errors
        if c_errors:
            rows_invalid_consistency += 1
            if len(row_issues) < 20:
                row_issues.append(f"Row {rownum}: {'; '.join(c_errors)}")
        if c_warnings:
            rows_with_warnings += 1
            if len(row_issues) < 20:
                row_issues.append(f"Row {rownum}: warning — {'; '.join(c_warnings)}")

        enr_key, em_key = _dup_keys(kwargs)
        is_dup = (enr_key is not None and enr_key in seen_enrols) or (
            em_key is not None and em_key in seen_emails
        )
        if is_dup:
            duplicate_rows += 1
            if len(row_issues) < 20:
                row_issues.append(
                    f"Row {rownum}: duplicate student (already on file) — will be skipped"
                )
        else:
            if enr_key is not None:
                seen_enrols.add(enr_key)
            if em_key is not None:
                seen_emails.add(em_key)

        # A row only counts as importable if it is valid, consistent, AND not
        # a duplicate.
        will_import = enrolment_ok and consistency_ok and not is_dup

        code = kwargs.get("_batch_code")
        if code:
            norm = _norm_code(str(code))
            code_display.setdefault(norm, str(code).strip())
            code_counts[norm] += 1
            code_targets.setdefault(norm, Counter())
            if target:
                code_targets[norm][target] += 1
            _merge_overrides(code_overrides.setdefault(norm, {}), row_ov)
            _track_override_values(
                code_override_values.setdefault(norm, {}), row_ov
            )
            if will_import:
                code_ok_counts[norm] += 1
        else:
            unbatched_rows += 1

        if will_import:
            importable_rows += 1

    batches: list[dict[str, Any]] = []
    existing = 0
    blocked = 0
    for norm, display in code_display.items():
        exists = norm in batch_index
        if exists:
            existing += 1
        target = _dominant_target(code_targets.get(norm, Counter()))
        ov = code_overrides.get(norm, {})
        duration, start_override = _effective_duration_and_start(ov)
        course_code = _course_code_for(target, duration)
        course_name = _course_name_for(target, duration, ov.get("course_opt"))
        # Exam happens in the calendar year the programme ends.
        eff_start = (
            start_override
            if start_override is not None
            else (academic_year.start_year if academic_year else None)
        )
        exam_end_year = eff_start + duration if eff_start is not None else None
        # For a missing batch, check up front whether auto-create would fail,
        # so the admin sees the blocker before committing rather than after.
        # A code whose rows disagree on the overrides is itself a blocker.
        blocker = None
        if not exists:
            blocker = _override_conflict(
                code_override_values.get(norm, {})
            ) or _missing_batch_blocker(
                target, academic_year, courses_by_code, ay_start_years, ov
            )
        if blocker:
            blocked += 1
            # Rows pointing at a batch that cannot be created will be skipped,
            # so they are not actually importable.
            importable_rows -= code_ok_counts.get(norm, 0)
        batches.append(
            {
                "code": display,
                "student_count": code_counts[norm],
                "exists": exists,
                "target": target,
                "suggested_course_code": None if exists else course_code,
                "suggested_course_name": None if exists else course_name,
                "suggested_exam_date": (
                    None if exists else _suggested_exam_date(target, exam_end_year)
                ),
                "creatable": exists or blocker is None,
                "blocker": blocker,
            }
        )

    # Missing-and-blocked first (need attention), then missing, then existing;
    # within each, by how many students depend on the code.
    batches.sort(
        key=lambda b: (b["exists"], b["creatable"], -b["student_count"])
    )

    # A branch with no academic year can't import at all (import 400s), so the
    # preview surfaces it up front instead of cheerfully reporting importable
    # rows the commit would then reject wholesale.
    blocking_error = (
        None
        if academic_year is not None
        else "No academic year exists for this branch. Create one first."
    )

    return {
        "total_rows": total_rows,
        "importable_rows": max(importable_rows, 0),
        "rows_missing_name": rows_missing_name,
        "rows_invalid_enrolment": rows_invalid_enrolment,
        "rows_invalid_consistency": rows_invalid_consistency,
        "rows_with_warnings": rows_with_warnings,
        "duplicate_rows": duplicate_rows,
        "unbatched_rows": unbatched_rows,
        "existing_batches": existing,
        "missing_batches": len(code_display) - existing,
        "blocked_batches": blocked,
        "blocking_error": blocking_error,
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
    academic_year = _pick_academic_year(years)
    if academic_year is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No academic year exists for this branch. Create one first.",
        )
    academic_year_id = academic_year.id

    # One id per import run, stamped on every student (and auto-created batch)
    # so this upload can be audited and undone as a unit (design §9).
    import_id = uuid.uuid4()
    source_file = file.filename

    batch_index = await _load_batch_index(session, branch_id)
    batches_created: list[str] = []
    subjects_created = 0
    # norm code -> human reason a missing batch could NOT be created, so rows
    # pointing at it report *why* instead of a misleading "unknown batch code".
    batch_create_errors: dict[str, str] = {}
    # Seeded with existing students so a re-upload (or within-file repeats) is
    # skipped instead of silently duplicating every row.
    seen_enrols, seen_emails = await _load_student_dedup_keys(session, branch_id)

    # Optionally create any referenced-but-missing batches up front, so the
    # course/exam-date is decided once per code from its dominant Target.
    if create_missing_batches:
        missing: dict[str, tuple[str, Counter]] = {}
        # First-seen override per code, plus the distinct values per field so a
        # code whose rows disagree can be rejected instead of silently guessed.
        code_overrides: dict[str, dict[str, str]] = {}
        code_override_values: dict[str, dict[str, set[str]]] = {}
        for row in rows:
            kwargs = _row_to_student_kwargs(row, branch_id, academic_year_id)
            if kwargs is None:
                continue
            code = kwargs.get("_batch_code")
            if not code:
                continue
            norm = _norm_code(str(code))
            row_ov = _row_overrides(row)
            _merge_overrides(code_overrides.setdefault(norm, {}), row_ov)
            _track_override_values(
                code_override_values.setdefault(norm, {}), row_ov
            )
            if norm in batch_index:
                continue
            display, counter = missing.setdefault(
                norm, (str(code).strip(), Counter())
            )
            target = kwargs.get("target_exam")
            if target:
                counter[target] += 1

        for norm, (display, counter) in missing.items():
            # Rows that disagree on this code's overrides are a hard error —
            # don't guess; rows fall through to "couldn't create batch — …".
            conflict = _override_conflict(code_override_values.get(norm, {}))
            if conflict:
                batch_create_errors[norm] = conflict
                continue
            # Each creation runs in its own savepoint: a failure (e.g. a
            # missing academic year for the derived course's span) rolls back
            # just this batch + any course it created, leaving the outer
            # import transaction usable for the remaining rows.
            try:
                async with session.begin_nested():
                    batch, subj_n = await _create_derived_batch(
                        session,
                        branch_id,
                        display,
                        _dominant_target(counter),
                        academic_year,
                        current_user_id,
                        ip_address,
                        import_id=import_id,
                        overrides=code_overrides.get(norm),
                        years=years,
                    )
                batch_index[norm] = batch.id
                batches_created.append(display)
                subjects_created += subj_n
            except HTTPException as exc:
                batch_create_errors[norm] = str(exc.detail)
            except Exception as exc:  # noqa: BLE001
                batch_create_errors[norm] = str(exc)

    imported = 0
    skipped = 0
    errors: list[str] = []
    warnings: list[str] = []

    for idx, row in enumerate(rows, start=2):  # row 1 is header
        rownum = _row_number(row, idx)
        kwargs = _row_to_student_kwargs(row, branch_id, academic_year_id)
        if kwargs is None:
            skipped += 1
            errors.append(f"Row {rownum}: missing required 'Name'")
            continue

        batch_code = kwargs.pop("_batch_code", None)
        try:
            _validate_enrolment_fields(
                kwargs.get("standard"), kwargs.get("target_exam")
            )
        except HTTPException as exc:
            skipped += 1
            errors.append(f"Row {rownum}: {exc.detail}")
            continue

        # §3 cross-field checks: contradictions skip the row; warnings pass.
        c_errors, c_warnings = _validate_row_consistency(
            kwargs.get("standard"), kwargs.get("target_exam"), _row_overrides(row)
        )
        if c_errors:
            skipped += 1
            errors.append(f"Row {rownum}: {'; '.join(c_errors)}")
            continue
        warnings.extend(f"Row {rownum}: {w}" for w in c_warnings)

        enr_key, em_key = _dup_keys(kwargs)
        if (enr_key is not None and enr_key in seen_enrols) or (
            em_key is not None and em_key in seen_emails
        ):
            skipped += 1
            errors.append(
                f"Row {rownum}: duplicate student (already on file) — skipped"
            )
            continue

        batch_id: uuid.UUID | None = None
        if batch_code:
            norm = _norm_code(str(batch_code))
            batch_id = batch_index.get(norm)
            if batch_id is None:
                skipped += 1
                reason = batch_create_errors.get(norm)
                if reason:
                    errors.append(
                        f"Row {rownum}: couldn't create batch '{batch_code}' — {reason}"
                    )
                else:
                    errors.append(f"Row {rownum}: unknown batch code '{batch_code}'")
                continue

        try:
            # Savepoint per row: a row that fails at flush (e.g. a value longer
            # than its column, or any IntegrityError) rolls back on its own
            # instead of poisoning the session — which previously cascaded
            # PendingRollbackError into every remaining row, the audit log, and
            # the final commit, turning one bad cell into a 500 that saved
            # nothing. Exiting the savepoint flushes the mapping insert too.
            async with session.begin_nested():
                student = await student_repository.create(
                    session,
                    **kwargs,
                    import_id=import_id,
                    import_source_file=source_file,
                )
                if batch_id is not None:
                    session.add(
                        StudentBatchMapping(
                            student_id=student.id,
                            batch_id=batch_id,
                            branch_id=branch_id,
                        )
                    )
            imported += 1
            # Only after a clean insert, so a later duplicate in the same file
            # is caught against a row that actually persisted.
            if enr_key is not None:
                seen_enrols.add(enr_key)
            if em_key is not None:
                seen_emails.add(em_key)
        except Exception as exc:  # noqa: BLE001
            skipped += 1
            errors.append(f"Row {rownum}: {exc}")

    await audit_service.log_action(
        session,
        user_id=current_user_id,
        action="IMPORT",
        table_name="students",
        record_id=import_id,
        new_values={
            "import_id": str(import_id),
            "source_file": source_file,
            "imported": imported,
            "skipped": skipped,
            "batches_created": batches_created,
            "subjects_created": subjects_created,
        },
        ip_address=ip_address,
        branch_id=branch_id,
    )

    return {
        "imported": imported,
        "skipped": skipped,
        "errors": errors,
        "warnings": warnings,
        "batches_created": batches_created,
        "subjects_created": subjects_created,
        # Only hand back an undo handle when rows actually persisted.
        "import_id": import_id if imported > 0 else None,
    }


async def undo_import(
    session: AsyncSession,
    import_id: uuid.UUID,
    branch_id: uuid.UUID,
    current_user_id: uuid.UUID,
    ip_address: str | None = None,
) -> dict[str, Any]:
    """Reverse a bulk import: soft-delete the students it created (and their
    batch mappings), then soft-delete any batches that import auto-created
    which have no other students left, and any subject skeleton it created on
    which no chapters have since been loaded. Scoped to the branch so an import
    id can't reach across branches. Idempotent — re-running finds nothing."""
    from app.modules.academic.models.academic_models import Chapter, Subject
    students = (
        await session.execute(
            select(Student).where(
                Student.import_id == import_id,
                Student.branch_id == branch_id,
                Student.is_deleted == False,  # noqa: E712
            )
        )
    ).scalars().all()
    student_ids = [s.id for s in students]

    mappings = []
    if student_ids:
        mappings = (
            await session.execute(
                select(StudentBatchMapping).where(
                    StudentBatchMapping.student_id.in_(student_ids),
                    StudentBatchMapping.is_deleted == False,  # noqa: E712
                )
            )
        ).scalars().all()

    for m in mappings:
        m.is_deleted = True
    for s in students:
        s.is_deleted = True
    await session.flush()

    # Batches this import spun up. Only reclaim ones with no remaining (live)
    # student — a batch someone has since assigned other students to is kept.
    batches = (
        await session.execute(
            select(Batch).where(
                Batch.import_id == import_id,
                Batch.branch_id == branch_id,
                Batch.is_deleted == False,  # noqa: E712
            )
        )
    ).scalars().all()

    batches_deleted = 0
    for b in batches:
        remaining = (
            await session.execute(
                select(func.count())
                .select_from(StudentBatchMapping)
                .where(
                    StudentBatchMapping.batch_id == b.id,
                    StudentBatchMapping.is_deleted == False,  # noqa: E712
                )
            )
        ).scalar_one()
        if remaining == 0:
            b.is_deleted = True
            batches_deleted += 1
    await session.flush()

    # Subject skeletons this import created. Keep any a syllabus import has
    # since built chapters on — only the bare skeleton is reclaimable (§7.4).
    subjects = (
        await session.execute(
            select(Subject).where(
                Subject.import_id == import_id,
                Subject.branch_id == branch_id,
                Subject.is_deleted == False,  # noqa: E712
            )
        )
    ).scalars().all()

    subjects_deleted = 0
    for s in subjects:
        chapter_count = (
            await session.execute(
                select(func.count())
                .select_from(Chapter)
                .where(
                    Chapter.subject_id == s.id,
                    Chapter.is_deleted == False,  # noqa: E712
                )
            )
        ).scalar_one()
        if chapter_count == 0:
            s.is_deleted = True
            subjects_deleted += 1
    await session.flush()

    await audit_service.log_action(
        session,
        user_id=current_user_id,
        action="IMPORT_UNDO",
        table_name="students",
        record_id=import_id,
        new_values={
            "import_id": str(import_id),
            "students_deleted": len(students),
            "batches_deleted": batches_deleted,
            "subjects_deleted": subjects_deleted,
        },
        ip_address=ip_address,
        branch_id=branch_id,
    )

    return {
        "students_deleted": len(students),
        "batches_deleted": batches_deleted,
        "subjects_deleted": subjects_deleted,
    }
