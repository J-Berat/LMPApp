"""SQLite-backed data model for speakers and sessions.

Everything lives in a single local .sqlite3 file - no server, no account,
no sync. The file can be backed up or copied manually like any document.
"""

from __future__ import annotations

import calendar
import os
import shutil
import sqlite3
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timezone

SPEAKER_STATUSES = ["proposed", "contacted", "confirmed", "declined"]
SESSION_STATUSES = ["scheduled", "completed", "cancelled"]

# How many timestamped backups (see ConferenceDB._backup_existing_file) to
# keep before pruning the oldest ones.
BACKUP_RETENTION = 20

SCHEMA = """
CREATE TABLE IF NOT EXISTS speakers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT DEFAULT '',
    affiliation TEXT DEFAULT '',
    status TEXT NOT NULL DEFAULT 'proposed',
    notes TEXT DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    speaker_id INTEGER,
    date TEXT DEFAULT '',
    time TEXT DEFAULT '',
    title TEXT DEFAULT '',
    authors TEXT DEFAULT '',
    abstract TEXT DEFAULT '',
    room TEXT DEFAULT '',
    status TEXT NOT NULL DEFAULT 'scheduled',
    recording_url TEXT DEFAULT '',
    slides_url TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    FOREIGN KEY (speaker_id) REFERENCES speakers(id) ON DELETE SET NULL
);
"""

# Columns added after the initial release: (table, column, definition).
# Applied with ALTER TABLE on existing databases that predate them.
MIGRATIONS = [
    ("sessions", "room", "TEXT DEFAULT ''"),
    ("sessions", "category", "TEXT DEFAULT ''"),
]


def add_one_month(date_str: str) -> str:
    """Return `date_str` (YYYY-MM-DD) shifted forward by one calendar month.

    Clamps to the last valid day of the target month (e.g. Jan 31 -> Feb 28
    or 29). Returns "" if `date_str` doesn't parse - used when duplicating a
    session to suggest "same slot, next month" without guessing wrong.
    """
    try:
        d = datetime.strptime(date_str.strip(), "%Y-%m-%d").date()
    except ValueError:
        return ""
    month = d.month + 1
    year = d.year + (month - 1) // 12
    month = (month - 1) % 12 + 1
    last_day = calendar.monthrange(year, month)[1]
    day = min(d.day, last_day)
    return date(year, month, day).isoformat()


def default_db_path(app_name: str = "Conference Organizer") -> str:
    """Return a sensible per-OS location for the local data file."""
    if os.name == "nt":
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
    elif os.uname().sysname == "Darwin":  # type: ignore[attr-defined]
        base = os.path.expanduser("~/Library/Application Support")
    else:
        base = os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share"))
    folder = os.path.join(base, app_name)
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, "conference_organizer.sqlite3")


@dataclass
class Speaker:
    id: int | None
    name: str
    email: str = ""
    affiliation: str = ""
    status: str = "proposed"
    notes: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class Session:
    id: int | None
    speaker_id: int | None
    date: str = ""
    time: str = ""
    title: str = ""
    authors: str = ""
    abstract: str = ""
    room: str = ""
    category: str = ""
    status: str = "scheduled"
    recording_url: str = ""
    slides_url: str = ""
    notes: str = ""
    speaker_name: str = ""  # populated by joined queries, not persisted directly


@dataclass
class RoomConflict:
    """A group of two or more sessions booked in the same room on the same date."""

    date: str
    room: str
    sessions: list[Session]


class ConferenceDB:
    """Thin wrapper around a local SQLite file."""

    def __init__(self, db_path: str | None = None) -> None:
        self.db_path = db_path or default_db_path()
        self._backup_existing_file()
        self._conn = sqlite3.connect(self.db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.executescript(SCHEMA)
        self._apply_migrations()
        self._conn.commit()

    def _apply_migrations(self) -> None:
        for table, column, definition in MIGRATIONS:
            existing = {row["name"] for row in self._conn.execute(f"PRAGMA table_info({table})")}
            if column not in existing:
                self._conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    def _backup_existing_file(self) -> None:
        """Copy the data file, if it already exists, into a timestamped
        "backups" folder next to it before this session touches it - a
        cheap safety net against an accidental delete or bad edit. Skips
        silently if a backup was already made in roughly the last hour
        (repeated app restarts shouldn't pile up near-duplicate copies),
        and never blocks startup if anything goes wrong."""
        if not os.path.isfile(self.db_path):
            return  # nothing to protect yet - first launch

        backups_dir = os.path.join(os.path.dirname(self.db_path), "backups")
        try:
            os.makedirs(backups_dir, exist_ok=True)
            existing = sorted(
                f for f in os.listdir(backups_dir)
                if f.startswith("conference_organizer_") and f.endswith(".sqlite3")
            )
        except OSError:
            return

        now = datetime.now()
        if existing:
            last_stamp = existing[-1][len("conference_organizer_"):-len(".sqlite3")]
            try:
                last_time = datetime.strptime(last_stamp, "%Y%m%d_%H%M%S")
                if (now - last_time).total_seconds() < 3600:
                    return
            except ValueError:
                pass

        backup_name = f"conference_organizer_{now.strftime('%Y%m%d_%H%M%S')}.sqlite3"
        backup_path = os.path.join(backups_dir, backup_name)
        try:
            shutil.copy2(self.db_path, backup_path)
        except OSError:
            return

        self._prune_old_backups(backups_dir, existing + [backup_name])

    @staticmethod
    def _prune_old_backups(backups_dir: str, files: list[str]) -> None:
        files = sorted(files)
        excess = len(files) - BACKUP_RETENTION
        for name in files[:max(0, excess)]:
            try:
                os.remove(os.path.join(backups_dir, name))
            except OSError:
                pass

    def close(self) -> None:
        self._conn.close()

    # -- Speakers -----------------------------------------------------------------

    def add_speaker(self, speaker: Speaker) -> int:
        cur = self._conn.execute(
            "INSERT INTO speakers (name, email, affiliation, status, notes, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (speaker.name, speaker.email, speaker.affiliation, speaker.status, speaker.notes, speaker.created_at),
        )
        self._conn.commit()
        return cur.lastrowid

    def update_speaker(self, speaker: Speaker) -> None:
        self._conn.execute(
            "UPDATE speakers SET name=?, email=?, affiliation=?, status=?, notes=? WHERE id=?",
            (speaker.name, speaker.email, speaker.affiliation, speaker.status, speaker.notes, speaker.id),
        )
        self._conn.commit()

    def delete_speaker(self, speaker_id: int) -> None:
        self._conn.execute("DELETE FROM speakers WHERE id=?", (speaker_id,))
        self._conn.commit()

    def list_speakers(self) -> list[Speaker]:
        rows = self._conn.execute("SELECT * FROM speakers ORDER BY name COLLATE NOCASE").fetchall()
        return [Speaker(**{k: row[k] for k in row.keys()}) for row in rows]

    def speaker_status_counts(self) -> dict[str, int]:
        """Number of speakers per status (e.g. {'confirmed': 5, ...}).
        Statuses with zero speakers are simply absent from the result."""
        rows = self._conn.execute("SELECT status, COUNT(*) AS n FROM speakers GROUP BY status").fetchall()
        return {row["status"]: row["n"] for row in rows}

    # -- Sessions -----------------------------------------------------------------

    def add_session(self, session: Session) -> int:
        cur = self._conn.execute(
            "INSERT INTO sessions (speaker_id, date, time, title, authors, abstract, room, "
            "category, status, recording_url, slides_url, notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                session.speaker_id, session.date, session.time, session.title, session.authors,
                session.abstract, session.room, session.category, session.status,
                session.recording_url, session.slides_url, session.notes,
            ),
        )
        self._conn.commit()
        return cur.lastrowid

    def update_session(self, session: Session) -> None:
        self._conn.execute(
            "UPDATE sessions SET speaker_id=?, date=?, time=?, title=?, authors=?, abstract=?, "
            "room=?, category=?, status=?, recording_url=?, slides_url=?, notes=? WHERE id=?",
            (
                session.speaker_id, session.date, session.time, session.title, session.authors,
                session.abstract, session.room, session.category, session.status,
                session.recording_url, session.slides_url, session.notes, session.id,
            ),
        )
        self._conn.commit()

    def delete_session(self, session_id: int) -> None:
        self._conn.execute("DELETE FROM sessions WHERE id=?", (session_id,))
        self._conn.commit()

    def list_sessions(self) -> list[Session]:
        rows = self._conn.execute(
            "SELECT sessions.*, COALESCE(speakers.name, '') AS speaker_name "
            "FROM sessions LEFT JOIN speakers ON speakers.id = sessions.speaker_id "
            "ORDER BY date ASC, time ASC"
        ).fetchall()
        return [Session(**{k: row[k] for k in row.keys()}) for row in rows]

    def list_rooms(self) -> list[str]:
        rows = self._conn.execute(
            "SELECT DISTINCT room FROM sessions WHERE TRIM(room) != '' ORDER BY room COLLATE NOCASE"
        ).fetchall()
        return [row["room"] for row in rows]

    def list_categories(self) -> list[str]:
        rows = self._conn.execute(
            "SELECT DISTINCT category FROM sessions WHERE TRIM(category) != '' ORDER BY category COLLATE NOCASE"
        ).fetchall()
        return [row["category"] for row in rows]

    def upcoming_session_count(self, today: str | None = None) -> int:
        """Number of non-cancelled sessions on or after `today` (defaults to
        the real current date)."""
        today = today or date.today().isoformat()
        return sum(
            1 for s in self.list_sessions()
            if s.date.strip() >= today and s.status != "cancelled"
        )

    # -- Room conflicts -------------------------------------------------------------

    def find_room_conflicts(self, sessions: list[Session] | None = None) -> list[RoomConflict]:
        """Return every (date, room) pair booked by more than one session.

        An empty date or empty room is never considered a conflict (there is
        nothing to compare). Pass `sessions` to check a specific list
        (e.g. including one not yet saved) instead of re-querying the DB.
        """
        if sessions is None:
            sessions = self.list_sessions()

        groups: dict[tuple[str, str], list[Session]] = defaultdict(list)
        for s in sessions:
            if s.date.strip() and s.room.strip():
                groups[(s.date.strip(), s.room.strip())].append(s)

        conflicts = [
            RoomConflict(date=date, room=room, sessions=group)
            for (date, room), group in groups.items()
            if len(group) > 1
        ]
        conflicts.sort(key=lambda c: (c.date, c.room))
        return conflicts

    def conflicts_for(self, date: str, room: str, exclude_session_id: int | None = None) -> list[Session]:
        """Sessions already booked in `room` on `date`, excluding `exclude_session_id`.

        Used to warn before saving a session that would create a new
        conflict, without needing to persist it first.
        """
        if not date.strip() or not room.strip():
            return []
        return [
            s for s in self.list_sessions()
            if s.date.strip() == date.strip() and s.room.strip() == room.strip() and s.id != exclude_session_id
        ]
