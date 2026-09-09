"""CSV import/export for speakers and sessions.

Plain files on disk - handy for a manual backup, or for bulk-editing the
roster/schedule in a spreadsheet and reloading it. Import always appends
new rows (it never edits or matches existing ones); duplicates are the
user's to clean up afterwards, same as pasting into a spreadsheet twice.
"""

from __future__ import annotations

import csv

from .db import Session, Speaker

SPEAKER_FIELDS = ["name", "email", "affiliation", "status", "notes"]
SESSION_FIELDS = [
    "date", "time", "title", "room", "speaker", "authors", "abstract",
    "status", "recording_url", "slides_url", "notes",
]


def export_speakers_csv(speakers: list[Speaker], path: str) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=SPEAKER_FIELDS)
        writer.writeheader()
        for sp in speakers:
            writer.writerow({field: getattr(sp, field) for field in SPEAKER_FIELDS})


def import_speakers_csv(path: str) -> list[Speaker]:
    """Parse a CSV into new Speaker records (id=None). Rows without a name
    are skipped. Missing columns default the same way the Add speaker
    dialog does."""
    result: list[Speaker] = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = (row.get("name") or "").strip()
            if not name:
                continue
            result.append(
                Speaker(
                    id=None,
                    name=name,
                    email=(row.get("email") or "").strip(),
                    affiliation=(row.get("affiliation") or "").strip(),
                    status=(row.get("status") or "").strip() or "proposed",
                    notes=(row.get("notes") or "").strip(),
                )
            )
    return result


def export_sessions_csv(sessions: list[Session], path: str) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=SESSION_FIELDS)
        writer.writeheader()
        for s in sessions:
            row = {field: getattr(s, field) for field in SESSION_FIELDS if field != "speaker"}
            row["speaker"] = s.speaker_name
            writer.writerow(row)


def import_sessions_csv(path: str, speakers: list[Speaker]) -> list[Session]:
    """Parse a CSV into new Session records (id=None). The "speaker" column
    is matched by exact name (case-insensitive) against existing speakers;
    an unmatched or blank name just leaves the session unassigned rather
    than failing the import."""
    by_name = {sp.name.strip().lower(): sp.id for sp in speakers if sp.name.strip()}
    result: list[Session] = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            date = (row.get("date") or "").strip()
            title = (row.get("title") or "").strip()
            if not date and not title:
                continue
            speaker_name = (row.get("speaker") or "").strip()
            result.append(
                Session(
                    id=None,
                    speaker_id=by_name.get(speaker_name.lower()),
                    date=date,
                    time=(row.get("time") or "").strip(),
                    title=title,
                    authors=(row.get("authors") or "").strip(),
                    abstract=(row.get("abstract") or "").strip(),
                    room=(row.get("room") or "").strip(),
                    status=(row.get("status") or "").strip() or "scheduled",
                    recording_url=(row.get("recording_url") or "").strip(),
                    slides_url=(row.get("slides_url") or "").strip(),
                    notes=(row.get("notes") or "").strip(),
                )
            )
    return result
