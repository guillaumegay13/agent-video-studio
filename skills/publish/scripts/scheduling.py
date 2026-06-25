"""Compute UTC dueAt slots for scheduled posts."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo


class SchedulingError(Exception):
    pass


def _localize_to_utc(d: date, hour: int, tz: ZoneInfo) -> datetime:
    """Build a local datetime and convert to UTC, shifting past DST gaps."""
    naive = datetime(d.year, d.month, d.day, hour, 0)
    local = naive.replace(tzinfo=tz)
    utc = local.astimezone(timezone.utc)
    # Detect a nonexistent local time (spring-forward gap): round-trip mismatch.
    if utc.astimezone(tz).hour != hour:
        local = (naive + timedelta(hours=1)).replace(tzinfo=tz)
        utc = local.astimezone(timezone.utc)
    return utc


def _day_slots(d: date, per_day: int, hour: int, end_hour: int, tz: ZoneInfo) -> list[datetime]:
    if per_day == 1:
        return [_localize_to_utc(d, hour, tz)]
    if end_hour <= hour:
        raise SchedulingError("--end-hour must be greater than --hour when --per-day > 1")
    step = (end_hour - hour) / (per_day - 1)
    return [_localize_to_utc(d, round(hour + i * step), tz) for i in range(per_day)]


def compute_slots(count, per_day, start_date, hour, end_hour, tz, occupied):
    """Return `count` UTC datetimes, `per_day` per calendar day starting at
    `start_date`, skipping any already in `occupied` (a set of UTC datetimes)."""
    zone = ZoneInfo(tz)
    occupied = set(occupied)
    slots: list[datetime] = []
    day = start_date
    guard = 0
    while len(slots) < count and guard < 3650:
        for slot in _day_slots(day, per_day, hour, end_hour, zone):
            if slot in occupied or slot in slots:
                continue
            slots.append(slot)
            if len(slots) == count:
                break
        day += timedelta(days=1)
        guard += 1
    if len(slots) < count:
        raise SchedulingError("Could not allocate enough free slots within 10 years")
    return slots
