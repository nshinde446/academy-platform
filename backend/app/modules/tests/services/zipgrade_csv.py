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
import re
from typing import Any

# Headers are normalized by stripping every non-alphanumeric char (so
# "External ID", "ExternalID" and "external_id" all become "externalid"), then
# matched by exact equality against these aliases in priority order. ZipGrade's
# real export uses ExternalID (the PRN marked on the sheet), EarnedPts,
# PossiblePts, PercentCorrect, FirstName/LastName. The PRN aliases deliberately
# exclude ZipGrade's internal "zipgradeid".
_PRN_ALIASES = ["externalid", "studentid", "prn", "idnumber"]
_NAME_ALIASES = ["studentname", "name", "fullname"]
_FIRST_ALIASES = ["firstname"]
_LAST_ALIASES = ["lastname", "surname"]
_SCORE_ALIASES = [
    "earnedpts", "earnedpoints", "pointsearned", "score", "marks",
    "marksobtained", "totalearned",
]
_TOTAL_ALIASES = [
    "possiblepts", "possiblepoints", "pointspossible", "totalpoints",
    "totalmarks", "maxpoints",
]
_PERCENT_ALIASES = ["percentcorrect", "percent", "percentage", "pct"]

_NON_ALNUM = re.compile(r"[^a-z0-9]+")


class ZipGradeCsvError(ValueError):
    """The uploaded file isn't a readable ZipGrade results CSV."""


def _norm(s: str) -> str:
    return _NON_ALNUM.sub("", (s or "").strip().lstrip("﻿").lower())


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
