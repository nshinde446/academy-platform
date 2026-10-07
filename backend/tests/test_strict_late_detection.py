"""Strict lecture late detection (no buffer): a lecture is late the moment it
starts after its scheduled time; seconds are ignored."""

from datetime import datetime, timezone

from app.modules.lectures.services.lecture_service import _derive_actuals, LATE_THRESHOLD_MIN


def _dt(h, m, s=0):
    return datetime(2026, 11, 2, h, m, s, tzinfo=timezone.utc)


def test_buffer_is_zero():
    assert LATE_THRESHOLD_MIN == 0


def test_started_on_the_minute_is_on_time():
    late, _ = _derive_actuals(_dt(10, 0), _dt(10, 0), _dt(11, 0))
    assert late is False


def test_started_one_minute_late_is_late():
    late, _ = _derive_actuals(_dt(10, 0), _dt(10, 1), _dt(11, 0))
    assert late is True


def test_started_early_is_on_time():
    late, _ = _derive_actuals(_dt(10, 0), _dt(9, 58), _dt(11, 0))
    assert late is False


def test_seconds_are_ignored():
    # 10:00:45 counts as 10:00 -> on time.
    late, _ = _derive_actuals(_dt(10, 0), _dt(10, 0, 45), _dt(11, 0))
    assert late is False
    # 10:01:00 is late; 10:00:59 is still 10:00 -> on time.
    assert _derive_actuals(_dt(10, 0), _dt(10, 0, 59), _dt(11, 0))[0] is False
    assert _derive_actuals(_dt(10, 0), _dt(10, 1, 0), _dt(11, 0))[0] is True


def test_ten_minute_arrival_is_now_late():
    # Previously within the 10-min buffer (on time); now strictly late.
    late, _ = _derive_actuals(_dt(10, 0), _dt(10, 10), _dt(11, 0))
    assert late is True
