from datetime import date, datetime, timezone
import pytest
from scripts.scheduling import compute_slots, SchedulingError


def test_one_per_day_starts_at_hour_utc():
    slots = compute_slots(
        count=3, per_day=1, start_date=date(2026, 7, 1),
        hour=18, end_hour=22, tz="UTC", occupied=set(),
    )
    assert slots == [
        datetime(2026, 7, 1, 18, tzinfo=timezone.utc),
        datetime(2026, 7, 2, 18, tzinfo=timezone.utc),
        datetime(2026, 7, 3, 18, tzinfo=timezone.utc),
    ]


def test_returns_utc_isoformat_compatible():
    slots = compute_slots(count=1, per_day=1, start_date=date(2026, 7, 1),
                          hour=18, end_hour=22, tz="Europe/Paris", occupied=set())
    # Paris is UTC+2 in July -> 18:00 local == 16:00 UTC
    assert slots[0] == datetime(2026, 7, 1, 16, tzinfo=timezone.utc)


def test_skips_occupied_slots():
    occupied = {datetime(2026, 7, 1, 18, tzinfo=timezone.utc)}
    slots = compute_slots(count=1, per_day=1, start_date=date(2026, 7, 1),
                          hour=18, end_hour=22, tz="UTC", occupied=occupied)
    assert slots[0] == datetime(2026, 7, 2, 18, tzinfo=timezone.utc)


def test_per_day_two_spreads_within_window():
    slots = compute_slots(count=2, per_day=2, start_date=date(2026, 7, 1),
                          hour=10, end_hour=22, tz="UTC", occupied=set())
    assert slots[0] == datetime(2026, 7, 1, 10, tzinfo=timezone.utc)
    assert slots[1] == datetime(2026, 7, 1, 22, tzinfo=timezone.utc)


def test_per_day_gt_one_requires_end_hour_after_hour():
    with pytest.raises(SchedulingError):
        compute_slots(count=2, per_day=2, start_date=date(2026, 7, 1),
                      hour=22, end_hour=22, tz="UTC", occupied=set())
