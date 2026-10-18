"""Shift / class time parsing is tolerant of the separator a human types, and
staff shift times are normalized to canonical HH:MM on save — so a start entered
as "08.00" (dot) can never again zero out the Late Fine / Late-IN calculation.
"""

import uuid

import pytest

from app.modules.attendance.time_utils import normalize_hhmm, parse_hhmm
from app.modules.staff.schemas.staff_schemas import StaffCreate, StaffUpdate


@pytest.mark.parametrize("raw,expected", [
    ("08:00", (8, 0)), ("08.00", (8, 0)), ("8-00", (8, 0)),
    ("0800", (8, 0)), ("800", (8, 0)), ("10.30", (10, 30)),
    ("", None), (None, None), ("abc", None), ("25:00", None), ("08:99", None),
])
def test_parse_hhmm_tolerant(raw, expected):
    assert parse_hhmm(raw) == expected


@pytest.mark.parametrize("raw,expected", [
    ("08.00", "08:00"), ("8-00", "08:00"), ("0800", "08:00"),
    ("10.30", "10:30"), ("", None), (None, None),
    ("abc", "abc"),  # unparseable kept as-is (readers stay tolerant)
])
def test_normalize_hhmm(raw, expected):
    assert normalize_hhmm(raw) == expected


def test_staff_create_normalizes_shift_times():
    c = StaffCreate(
        branch_id=uuid.uuid4(), first_name="X", department_id=uuid.uuid4(),
        shift_start="08.00", shift_end="20.30",
    )
    assert c.shift_start == "08:00"
    assert c.shift_end == "20:30"


def test_staff_update_normalizes_shift_start():
    assert StaffUpdate(shift_start="8.0").shift_start == "08:00"
    assert StaffUpdate(shift_start=None).shift_start is None
