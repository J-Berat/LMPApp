"""iCal (.ics) export - one file per session, or the whole schedule.

No server, no sync: a standard calendar file people can double-click (or
you can attach/share) to add the event(s) to their own calendar app.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from .db import Session

_DEFAULT_DURATION = timedelta(hours=1)

# A handful of timezone abbreviations people are likely to type in the
# free-text Time field, mapped to a fixed UTC offset. This is a best
# effort, not DST-aware (CEST vs CET already disambiguates summer/winter
# for Central Europe) - good enough for a personal scheduling file, and
# far better than silently mislabeling the hour.
_TZ_OFFSETS = {
    "UTC": 0, "GMT": 0, "CET": 1, "CEST": 2, "BST": 1, "WET": 0, "WEST": 1,
}

_TIME_RE = re.compile(r"(\d{1,2})[:hH](\d{2})")
_TZ_RE = re.compile(r"\b([A-Z]{2,4})\b")


def _escape(text: str) -> str:
    return (
        text.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
    )


def _fold(line: str) -> str:
    """Fold a line at 75 octets per RFC 5545 (continuation lines start with
    a space). A simple character-based fold - generous enough for the short
    single-line fields we emit, and DESCRIPTION is pre-escaped so it has no
    literal newlines to worry about mid-fold."""
    if len(line.encode("utf-8")) <= 75:
        return line
    out = []
    current = line
    while len(current.encode("utf-8")) > 75:
        out.append(current[:74])
        current = " " + current[74:]
    out.append(current)
    return "\r\n".join(out)


def _parse_start(session: Session) -> tuple[datetime | None, bool]:
    """Return (start, is_all_day). `start` is naive if no recognized
    timezone was found in the Time field (floating local time), or
    timezone-aware (UTC-converted) if one was."""
    date_str = session.date.strip()
    if not date_str:
        return None, False
    try:
        day = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return None, False

    m = _TIME_RE.search(session.time or "")
    if not m:
        return day, True  # no parseable time -> all-day event

    hour, minute = int(m.group(1)), int(m.group(2))
    if not (0 <= hour < 24 and 0 <= minute < 60):
        return day, True

    naive = day.replace(hour=hour, minute=minute)

    tzm = _TZ_RE.search((session.time or "").upper())
    if tzm and tzm.group(1) in _TZ_OFFSETS:
        offset = _TZ_OFFSETS[tzm.group(1)]
        aware = naive.replace(tzinfo=timezone(timedelta(hours=offset)))
        return aware, False

    return naive, False  # floating local time - no recognized zone in the text


def _event_lines(session: Session) -> list[str]:
    start, all_day = _parse_start(session)
    if start is None:
        return []  # no usable date - skip rather than emit a broken event

    lines = ["BEGIN:VEVENT", f"UID:conference-organizer-session-{session.id}@local"]
    lines.append(f"DTSTAMP:{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}")

    if all_day:
        lines.append(f"DTSTART;VALUE=DATE:{start.strftime('%Y%m%d')}")
        lines.append(f"DTEND;VALUE=DATE:{(start + timedelta(days=1)).strftime('%Y%m%d')}")
    elif start.tzinfo is not None:
        start_utc = start.astimezone(timezone.utc)
        end_utc = start_utc + _DEFAULT_DURATION
        lines.append(f"DTSTART:{start_utc.strftime('%Y%m%dT%H%M%SZ')}")
        lines.append(f"DTEND:{end_utc.strftime('%Y%m%dT%H%M%SZ')}")
    else:
        end = start + _DEFAULT_DURATION
        lines.append(f"DTSTART:{start.strftime('%Y%m%dT%H%M%S')}")
        lines.append(f"DTEND:{end.strftime('%Y%m%dT%H%M%S')}")

    lines.append(f"SUMMARY:{_escape(session.title or '(untitled)')}")
    if session.room.strip():
        lines.append(f"LOCATION:{_escape(session.room.strip())}")

    description_parts = []
    if session.speaker_name.strip():
        description_parts.append(f"Speaker: {session.speaker_name.strip()}")
    if session.category.strip():
        description_parts.append(f"Category: {session.category.strip()}")
    if session.abstract.strip():
        description_parts.append(session.abstract.strip())
    if session.recording_url.strip():
        description_parts.append(f"Recording: {session.recording_url.strip()}")
    if session.slides_url.strip():
        description_parts.append(f"Slides: {session.slides_url.strip()}")
    if description_parts:
        lines.append(f"DESCRIPTION:{_escape(chr(10).join(description_parts))}")

    lines.append("END:VEVENT")
    return lines


def _wrap_calendar(event_lines: list[str]) -> str:
    header = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Conference Organizer//EN",
        "CALSCALE:GREGORIAN",
    ]
    footer = ["END:VCALENDAR"]
    all_lines = header + event_lines + footer
    return "\r\n".join(_fold(line) for line in all_lines) + "\r\n"


def export_session_ics(session: Session, path: str) -> None:
    lines = _event_lines(session)
    if not lines:
        raise ValueError("This session has no date to export.")
    with open(path, "w", newline="", encoding="utf-8") as f:
        f.write(_wrap_calendar(lines))


def export_schedule_ics(sessions: list[Session], path: str) -> None:
    all_lines: list[str] = []
    for s in sessions:
        all_lines.extend(_event_lines(s))
    if not all_lines:
        raise ValueError("No sessions with a date to export.")
    with open(path, "w", newline="", encoding="utf-8") as f:
        f.write(_wrap_calendar(all_lines))
