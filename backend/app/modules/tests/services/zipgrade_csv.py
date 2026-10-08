"""ZipGrade results-CSV parser for the Test Portal.

ZipGrade's exported results CSV has one row per scanned student. Header names
vary a little by app version/export, so this parser resolves columns by a set of
tolerant aliases rather than fixed positions. The fields we need per row:

    prn      the Student ID marked on the OMR sheet (our match key = PRN)
    name     the student's name (display / review only)
    score    marks earned (ZipGrade already scored the sheet)
    total    possible marks (for reference / percent)
    percent  percent correct, if present
    raw      the original row dict, kept verbatim for audit / re-processing

Tune the alias lists below against the client's actual ZipGrade export if a
column isn't picked up.
"""

from __future__ import annotations

import csv
import io
from typing import Any

# Header aliases (compared lowercase, stripped). First match wins. The PRN
# aliases deliberately exclude ZipGrade's own internal "zipgrade id".
_PRN_ALIASES = [
    "student id", "studentid", "prn", "prn number", "prn no", "external id",
    "id number",
]
_NAME_ALIASES = ["student name", "name", "full name"]
_FIRST_ALIASES = ["first name", "firstname"]
_LAST_ALIASES = ["last name", "lastname", "surname"]
_SCORE_ALIASES = [
    "earned points", "points earned", "score", "marks", "marks obtained",
    "total earned",
]
_TOTAL_ALIASES = [
    "possible points", "points possible", "total points", "total marks",
    "possible", "max points",
]
_PERCENT_ALIASES = ["percent correct", "percent", "percentage", "pct", "%"]


class ZipGradeCsvError(ValueError):
    """The uploaded file isn't a readable ZipGrade results CSV."""


def _norm(s: str) -> str:
    return (s or "").strip().lstrip("﻿").lower()


def _pick(header_map: dict[str, str], aliases: list[str]) -> str | None:
    """Return the real header name whose normalized form matches an alias."""
    for alias in aliases:
        if alias in header_map:
            return header_map[alias]
    return None


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    s = str(value).strip().replace("%", "")
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def score_from_raw(raw: dict[str, Any]) -> tuple[float | None, float | None, float | None]:
    """Re-derive (score, total, percent) from a single stored raw ZipGrade row.

    Used when resolving a needs-review row: the original row was kept verbatim on
    ``TestImportReview.raw_row``, and resolving it to a student needs the marks
    back out without re-uploading the whole file. Resolves columns by the same
    aliases as :func:`parse_zipgrade_csv`."""
    header_map = {_norm(h): h for h in raw.keys() if h}
    score_col = _pick(header_map, _SCORE_ALIASES)
    total_col = _pick(header_map, _TOTAL_ALIASES)
    percent_col = _pick(header_map, _PERCENT_ALIASES)
    return (
        _to_float(raw.get(score_col)) if score_col else None,
        _to_float(raw.get(total_col)) if total_col else None,
        _to_float(raw.get(percent_col)) if percent_col else None,
    )


def parse_zipgrade_csv(content: bytes) -> list[dict[str, Any]]:
    """Parse ZipGrade results CSV bytes into normalized rows. Raises
    ``ZipGradeCsvError`` if the file has no header or no PRN column."""
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = content.decode("latin-1")

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise ZipGradeCsvError("CSV has no header row")

    # normalized-header -> original-header
    header_map = {_norm(h): h for h in reader.fieldnames if h}
    prn_col = _pick(header_map, _PRN_ALIASES)
    if not prn_col:
        raise ZipGradeCsvError(
            "Could not find a Student ID / PRN column in the CSV. "
            f"Columns seen: {', '.join(reader.fieldnames)}"
        )
    name_col = _pick(header_map, _NAME_ALIASES)
    first_col = _pick(header_map, _FIRST_ALIASES)
    last_col = _pick(header_map, _LAST_ALIASES)
    score_col = _pick(header_map, _SCORE_ALIASES)
    total_col = _pick(header_map, _TOTAL_ALIASES)
    percent_col = _pick(header_map, _PERCENT_ALIASES)

    rows: list[dict[str, Any]] = []
    for raw in reader:
        prn = (raw.get(prn_col) or "").strip()
        if name_col:
            name = (raw.get(name_col) or "").strip()
        else:
            name = " ".join(
                p for p in [
                    (raw.get(first_col) or "").strip() if first_col else "",
                    (raw.get(last_col) or "").strip() if last_col else "",
                ] if p
            ).strip()
        # Skip fully-blank trailing rows.
        if not prn and not name:
            continue
        rows.append({
            "prn": prn,
            "name": name,
            "score": _to_float(raw.get(score_col)) if score_col else None,
            "total": _to_float(raw.get(total_col)) if total_col else None,
            "percent": _to_float(raw.get(percent_col)) if percent_col else None,
            "raw": dict(raw),
        })
    return rows


# ── Per-subject manual-marks CSV (Test Portal spec, Section 2) ────────────────
# A plain three-column file: Student Name, PRN Number, Marks Obtained. One file
# per subject. Reuses the same tolerant header aliases as the ZipGrade parser.


def parse_subject_marks_csv(content: bytes) -> list[dict[str, Any]]:
    """Parse a per-subject marks CSV (Name, PRN, Marks) into normalized rows:
    ``{prn, name, marks, raw}`` where ``marks`` is a float or None (blank/not a
    number). Raises ``ZipGradeCsvError`` if the header, PRN column, or marks
    column is missing (the spec's "reject a file that doesn't have the 3 columns").
    """
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = content.decode("latin-1")

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise ZipGradeCsvError("CSV has no header row")

    header_map = {_norm(h): h for h in reader.fieldnames if h}
    prn_col = _pick(header_map, _PRN_ALIASES)
    marks_col = _pick(header_map, _SCORE_ALIASES)
    if not prn_col or not marks_col:
        raise ZipGradeCsvError(
            "The marks CSV needs a Student Name, a PRN, and a Marks Obtained "
            f"column. Columns seen: {', '.join(reader.fieldnames)}"
        )
    name_col = _pick(header_map, _NAME_ALIASES)

    rows: list[dict[str, Any]] = []
    for raw in reader:
        prn = (raw.get(prn_col) or "").strip()
        name = (raw.get(name_col) or "").strip() if name_col else ""
        marks_cell = raw.get(marks_col)
        # Skip fully-blank trailing rows.
        if not prn and not name and not (marks_cell or "").strip():
            continue
        rows.append({
            "prn": prn,
            "name": name,
            "marks": _to_float(marks_cell),
            "raw": dict(raw),
        })
    return rows
