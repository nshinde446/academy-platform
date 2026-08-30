"""Developer monitoring snapshot — aggregates institute health from the DB:
system size, device connectivity, backup freshness, command queue, and a
computed list of active alerts. All read-only, all DB-derived (no host access),
so it works the same in tests (SQLite) as prod (Postgres)."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.attendance.models.attendance_models import (
    DailyAttendance,
    RawPunchLog,
)
from app.modules.attendance.models.provisioning_models import (
    DeviceCommand,
    DeviceStatus,
)
from app.modules.lectures.models.lecture_models import Lecture
from app.modules.monitoring.models.monitoring_models import BackupRun
from app.modules.student.models.student_models import Student
from app.modules.teacher.models.teacher_models import Teacher

# Thresholds for alerts.
_DEVICE_SILENT_HOURS = 6
_BACKUP_STALE_HOURS = 26  # daily backup + margin


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


async def _count(session: AsyncSession, model, *where) -> int:
    stmt = select(func.count()).select_from(model)
    for w in where:
        stmt = stmt.where(w)
    return int((await session.execute(stmt)).scalar() or 0)


async def dev_snapshot(session: AsyncSession) -> dict:
    now = datetime.now(timezone.utc)
    is_pg = session.bind.dialect.name == "postgresql"
    alerts: list[dict] = []

    # ── System ───────────────────────────────────────────────────────────────
    db_size_bytes = None
    connections = None
    if is_pg:
        db_size_bytes = (
            await session.execute(text("SELECT pg_database_size(current_database())"))
        ).scalar()
        connections = (
            await session.execute(text("SELECT count(*) FROM pg_stat_activity"))
        ).scalar()

    counts = {
        "students": await _count(session, Student, Student.is_deleted == False),  # noqa: E712
        "teachers": await _count(session, Teacher, Teacher.is_deleted == False),  # noqa: E712
        "lectures": await _count(session, Lecture, Lecture.is_deleted == False),  # noqa: E712
        "daily_attendance": await _count(session, DailyAttendance),
        "raw_punches": await _count(session, RawPunchLog),
    }

    # ── Devices ──────────────────────────────────────────────────────────────
    dev_rows = (await session.execute(select(DeviceStatus))).scalars().all()
    devices = []
    for d in dev_rows:
        last_seen = _aware(d.last_seen_at)
        silent_h = (now - last_seen).total_seconds() / 3600 if last_seen else None
        snap = d.snapshot or {}
        devices.append(
            {
                "dev_id": d.dev_id,
                "last_seen_at": last_seen,
                "silent_hours": round(silent_h, 1) if silent_h is not None else None,
                "user_count": snap.get("userCount"),
                "face_count": snap.get("faceCount"),
            }
        )
        if silent_h is not None and silent_h > _DEVICE_SILENT_HOURS:
            alerts.append(
                {
                    "level": "critical",
                    "area": "device",
                    "message": f"Device {d.dev_id} silent for {round(silent_h)}h "
                    f"(> {_DEVICE_SILENT_HOURS}h) — attendance not recording.",
                }
            )

    last_punch = _aware(
        (await session.execute(select(func.max(RawPunchLog.punch_timestamp)))).scalar()
    )
    punches_today = await _count(
        session,
        RawPunchLog,
        RawPunchLog.punch_timestamp
        >= now.replace(hour=0, minute=0, second=0, microsecond=0),
    )
    if last_punch is not None and (now - last_punch) > timedelta(hours=_DEVICE_SILENT_HOURS):
        alerts.append(
            {
                "level": "critical",
                "area": "attendance",
                "message": f"No punches for {round((now - last_punch).total_seconds() / 3600)}h "
                f"(last {last_punch:%Y-%m-%d %H:%M} UTC).",
            }
        )

    # ── Backups ──────────────────────────────────────────────────────────────
    latest_backup = (
        await session.execute(
            select(BackupRun).order_by(BackupRun.created_at.desc()).limit(1)
        )
    ).scalar_one_or_none()
    backup = None
    if latest_backup is not None:
        created = _aware(latest_backup.created_at)
        age_h = (now - created).total_seconds() / 3600
        backup = {
            "created_at": created,
            "age_hours": round(age_h, 1),
            "status": latest_backup.status,
            "size_bytes": latest_backup.size_bytes,
            "offbox": latest_backup.offbox,
        }
        if latest_backup.status != "ok":
            alerts.append({"level": "critical", "area": "backup", "message": "Last backup FAILED."})
        elif age_h > _BACKUP_STALE_HOURS:
            alerts.append(
                {
                    "level": "critical",
                    "area": "backup",
                    "message": f"Last backup is {round(age_h)}h old (> {_BACKUP_STALE_HOURS}h).",
                }
            )
        elif latest_backup.offbox == "failed":
            alerts.append({"level": "warning", "area": "backup", "message": "Off-box backup copy failed."})
        elif latest_backup.offbox == "skipped":
            alerts.append({"level": "warning", "area": "backup", "message": "Off-box copy not configured yet."})
    else:
        alerts.append({"level": "critical", "area": "backup", "message": "No backup has ever run."})

    # ── Command queue ────────────────────────────────────────────────────────
    queue_rows = (
        await session.execute(
            select(DeviceCommand.command_status, func.count())
            .where(DeviceCommand.command_status.in_(("pending", "sent")))
            .group_by(DeviceCommand.command_status)
        )
    ).all()
    queue = {status: int(c) for status, c in queue_rows}

    return {
        "generated_at": now,
        "system": {
            "db_size_bytes": db_size_bytes,
            "connections": connections,
            "counts": counts,
        },
        "devices": devices,
        "attendance": {
            "last_punch_at": last_punch,
            "punches_today": punches_today,
        },
        "backup": backup,
        "queue": {"pending": queue.get("pending", 0), "sent": queue.get("sent", 0)},
        "alerts": alerts,
    }
