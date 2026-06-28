"""Branch-local day helpers — the foundation of all day-attendance bucketing.

The critical property: a punch near the day boundary must bucket by *local*
date, not UTC. IST is UTC+5:30, so 2026-06-22 09:29 IST == 04:00 UTC the same
day, but 2026-06-23 02:00 IST == 2026-06-22 20:30 UTC (previous UTC day).
"""

from datetime import date, datetime, timezone

from app.modules.attendance import time_utils

IST = "Asia/Kolkata"


def test_local_date_of_aware_ist_morning():
    # 09:29 IST on the 22nd -> 03:59 UTC, still local date the 22nd.
    instant = datetime(2026, 6, 22, 3, 59, tzinfo=timezone.utc)
    assert time_utils.local_date_of(instant, IST) == date(2026, 6, 22)


def test_local_date_of_naive_treated_as_utc():
    # SQLite strips tzinfo; a naive instant is treated as UTC.
    instant = datetime(2026, 6, 22, 3, 59)
    assert time_utils.local_date_of(instant, IST) == date(2026, 6, 22)


def test_local_date_of_boundary_crosses_back_a_day():
    # 01:00 IST on the 23rd == 19:30 UTC on the 22nd. Local date wins -> 23rd.
    instant = datetime(2026, 6, 22, 19, 30, tzinfo=timezone.utc)
    assert time_utils.local_date_of(instant, IST) == date(2026, 6, 23)


def test_day_bounds_is_half_open_utc():
    start, end = time_utils.day_bounds(date(2026, 6, 22), IST)
    # 00:00 IST 22nd == 18:30 UTC 21st; +24h.
    assert start == datetime(2026, 6, 21, 18, 30, tzinfo=timezone.utc)
    assert end == datetime(2026, 6, 22, 18, 30, tzinfo=timezone.utc)


def test_local_time_on_class_start():
    cutoff = time_utils.class_start_on(date(2026, 6, 22), IST)
    # 10:00 IST == 04:30 UTC.
    assert cutoff == datetime(2026, 6, 22, 4, 30, tzinfo=timezone.utc)


def test_campus_window_on():
    open_, close = time_utils.campus_window_on(date(2026, 6, 22), IST)
    assert open_ == datetime(2026, 6, 22, 1, 30, tzinfo=timezone.utc)   # 07:00 IST
    assert close == datetime(2026, 6, 22, 9, 30, tzinfo=timezone.utc)   # 15:00 IST


def test_unknown_tz_falls_back_to_default():
    # A garbage branch tz must not crash — falls back to the default zone.
    assert time_utils.local_date_of(
        datetime(2026, 6, 22, 3, 59, tzinfo=timezone.utc), "Not/AZone"
    ) == date(2026, 6, 22)
