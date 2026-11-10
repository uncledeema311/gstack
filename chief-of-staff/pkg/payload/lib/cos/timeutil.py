"""Time zone aware clock and meeting slot finder."""
from __future__ import annotations

import datetime as dt
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

from . import config, store

DAY_NAMES = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def zone(name: str) -> ZoneInfo:
    if not config.timezone_ok(name):
        raise store.CosError("Unknown time zone %r. Use an IANA name such as Australia/Perth." % name, store.EXIT_VALIDATION)
    return ZoneInfo(name)


def today(cfg: Optional[Dict[str, Any]] = None) -> dt.date:
    """Today's date in the configured time zone (falls back to UTC)."""
    name = (cfg or config.load()).get("timezone")
    if not config.timezone_ok(name):
        return store.utcnow().date()
    return store.utcnow().astimezone(ZoneInfo(name)).date()


def _offset(moment: dt.datetime) -> str:
    delta = moment.utcoffset() or dt.timedelta(0)
    minutes = int(delta.total_seconds() // 60)
    sign = "+" if minutes >= 0 else "-"
    return "%s%02d:%02d" % (sign, abs(minutes) // 60, abs(minutes) % 60)


def now_info(tz_name: str) -> Dict[str, Any]:
    local = store.utcnow().astimezone(zone(tz_name))
    return {
        "timezone": tz_name,
        "local": local.replace(microsecond=0).isoformat(),
        "date": local.date().isoformat(),
        "weekday": DAY_NAMES[local.weekday()],
        "utc_offset": _offset(local),
        "abbreviation": local.tzname(),
        "daylight_saving": bool(local.dst()),
        "utc": store.iso(local),
    }


def _hhmm(value: str) -> dt.time:
    hour, minute = value.split(":")
    return dt.time(int(hour), int(minute))


def _local(day: dt.date, clock: dt.time, tz: ZoneInfo) -> Optional[dt.datetime]:
    """Build a local wall-clock time, or None if daylight saving skips it."""
    candidate = dt.datetime.combine(day, clock, tzinfo=tz)
    round_trip = candidate.astimezone(dt.timezone.utc).astimezone(tz)
    if round_trip.replace(tzinfo=None) != candidate.replace(tzinfo=None):
        return None
    return candidate


def parse_busy(entries: List[Dict[str, Any]], tz: ZoneInfo) -> List[Tuple[dt.datetime, dt.datetime]]:
    """Busy blocks. Timestamps need an offset. Date-only values are all-day local."""
    blocks = []
    for entry in entries:
        start_raw, end_raw = str(entry.get("start", "")), str(entry.get("end", ""))
        if not start_raw or not end_raw:
            raise store.CosError("Each busy block needs start and end.", store.EXIT_VALIDATION)
        if len(start_raw) == 10 and len(end_raw) == 10:
            start = dt.datetime.combine(store.parse_date(start_raw), dt.time(0, 0), tzinfo=tz)
            end = dt.datetime.combine(store.parse_date(end_raw), dt.time(0, 0), tzinfo=tz)
        else:
            start, end = store.parse_iso(start_raw), store.parse_iso(end_raw)
        if end <= start:
            raise store.CosError("Busy block ends before it starts: %s to %s" % (start_raw, end_raw), store.EXIT_VALIDATION)
        blocks.append((start, end))
    return blocks


def find_slots(
    cfg: Dict[str, Any],
    start_date: str,
    days: int,
    busy: Optional[List[Dict[str, Any]]],
    calendar_checked_at: Optional[str],
    duration_minutes: Optional[int] = None,
    attendee_timezones: Optional[List[str]] = None,
    limit: int = 6,
    buffer_minutes: Optional[int] = None,
    attendee_hours_only: bool = False,
    attendee_window: Optional[str] = None,
) -> Dict[str, Any]:
    tz = zone(cfg["timezone"])
    sched = cfg["scheduling"]
    hours = cfg["working_hours"]
    duration = dt.timedelta(minutes=duration_minutes or sched["default_duration_minutes"])
    buffer = dt.timedelta(minutes=sched["buffer_minutes"] if buffer_minutes is None else buffer_minutes)
    step = dt.timedelta(minutes=sched["slot_step_minutes"])
    earliest = store.utcnow() + dt.timedelta(hours=sched["min_notice_hours"])
    availability_verified = busy is not None and bool(calendar_checked_at)
    if calendar_checked_at:
        checked = store.parse_iso(calendar_checked_at)
        age_minutes = (store.utcnow() - checked).total_seconds() / 60
        if age_minutes > 60:
            availability_verified = False
    blocks = parse_busy(busy or [], tz)
    attendee_zones = [(name, zone(name)) for name in (attendee_timezones or [])]
    day_start, day_end = _hhmm(sched["attendee_day_start"]), _hhmm(sched["attendee_day_end"])
    if attendee_window:
        # A preference stated by the attendee, in their own local time, for example 13:00-15:00.
        try:
            first_part, last_part = attendee_window.split("-")
            day_start, day_end = _hhmm(first_part), _hhmm(last_part)
        except ValueError:
            raise store.CosError("--attendee-window must look like 13:00-15:00.", store.EXIT_VALIDATION)
        if day_start >= day_end:
            raise store.CosError("--attendee-window must start before it ends.", store.EXIT_VALIDATION)

    slots: List[Dict[str, Any]] = []
    first = store.parse_date(start_date)
    for index in range(max(1, days)):
        day = first + dt.timedelta(days=index)
        if DAY_NAMES[day.weekday()] not in hours["days"]:
            continue
        open_at = _local(day, _hhmm(hours["start"]), tz)
        close_at = _local(day, _hhmm(hours["end"]), tz)
        if open_at is None or close_at is None:
            continue
        # Step in UTC. Adding minutes to a local time does wall-clock arithmetic in Python,
        # which would offer times that daylight saving skips.
        utc = dt.timezone.utc
        cursor_utc, close_utc = open_at.astimezone(utc), close_at.astimezone(utc)
        while cursor_utc + duration <= close_utc and len(slots) < limit:
            end_utc = cursor_utc + duration
            cursor, end = cursor_utc.astimezone(tz), end_utc.astimezone(tz)
            cursor_utc += step
            clear = cursor >= earliest and not any(
                cursor.astimezone(utc) < block_end.astimezone(utc) + buffer
                and end.astimezone(utc) > block_start.astimezone(utc) - buffer
                for block_start, block_end in blocks
            )
            if not clear:
                continue
            attendees = []
            for name, attendee_tz in attendee_zones:
                there = cursor.astimezone(attendee_tz)
                there_end = end.astimezone(attendee_tz)
                attendees.append(
                    {
                        "timezone": name,
                        "start": there.isoformat(),
                        "utc_offset": _offset(there),
                        "outside_business_hours": not (day_start <= there.time() and there_end.time() <= day_end)
                        or there.date() != there_end.date(),
                    }
                )
            if attendee_hours_only and any(item["outside_business_hours"] for item in attendees):
                continue
            slots.append(
                {
                    "start": cursor.isoformat(),
                    "end": end.isoformat(),
                    "weekday": DAY_NAMES[cursor.weekday()],
                    "utc_offset": _offset(cursor),
                    "attendees": attendees,
                }
            )
        if len(slots) >= limit:
            break

    warnings = []
    if not availability_verified:
        warnings.append(
            "Calendar availability is not verified (no busy data, or it was read more than 60 minutes ago). "
            "Read the calendar again before proposing these times."
        )
    return {
        "timezone": cfg["timezone"],
        "duration_minutes": int(duration.total_seconds() // 60),
        "buffer_minutes": int(buffer.total_seconds() // 60),
        "availability_verified": availability_verified,
        "calendar_checked_at": calendar_checked_at,
        "slots": slots,
        "warnings": warnings,
    }
