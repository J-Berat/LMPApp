"""Calendar view: every session at a glance, with room conflicts highlighted."""

from __future__ import annotations

from collections import defaultdict

from PySide6.QtCore import QDate
from PySide6.QtGui import QTextCharFormat, QColor, QBrush
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QCalendarWidget,
    QListWidget,
    QListWidgetItem,
    QLabel,
)

from .db import ConferenceDB, Session

DAY_WITH_SESSION_BG = QColor("#dbe9ff")
CONFLICT_BG = QColor("#f8c9c9")
CONFLICT_FG = QColor("#7a1f1f")


class CalendarTab(QWidget):
    """A month calendar with all sessions, plus a same-day list and a
    conflict banner listing every room double-booking."""

    def __init__(self, db: ConferenceDB, parent=None) -> None:
        super().__init__(parent)
        self.db = db
        self._touched_dates: set[QDate] = set()

        self.banner = QLabel("")
        self.banner.setWordWrap(True)
        self.banner.setStyleSheet("padding: 8px; border-radius: 4px;")

        self.calendar = QCalendarWidget()
        self.calendar.setGridVisible(True)
        self.calendar.selectionChanged.connect(self._update_day_list)

        self.day_list = QListWidget()

        side = QVBoxLayout()
        side.addWidget(QLabel("Sessions on selected day:"))
        side.addWidget(self.day_list)

        content = QHBoxLayout()
        content.addWidget(self.calendar, 2)
        content.addLayout(side, 1)

        layout = QVBoxLayout(self)
        layout.addWidget(self.banner)
        layout.addLayout(content)

        self.refresh()

    def refresh(self) -> None:
        sessions = self.db.list_sessions()
        conflicts = self.db.find_room_conflicts(sessions)
        conflict_dates = {c.date for c in conflicts}

        # Reset any date we previously colored, then re-apply from scratch -
        # QCalendarWidget has no "clear all formats" call.
        default_format = QTextCharFormat()
        for qdate in self._touched_dates:
            self.calendar.setDateTextFormat(qdate, default_format)
        self._touched_dates.clear()

        by_date: dict[str, list[Session]] = defaultdict(list)
        for s in sessions:
            if s.date.strip():
                by_date[s.date.strip()].append(s)

        for date_str in by_date:
            qdate = QDate.fromString(date_str, "yyyy-MM-dd")
            if not qdate.isValid():
                continue
            fmt = QTextCharFormat()
            if date_str in conflict_dates:
                fmt.setBackground(QBrush(CONFLICT_BG))
                fmt.setForeground(QBrush(CONFLICT_FG))
                fmt.setFontWeight(700)
            else:
                fmt.setBackground(QBrush(DAY_WITH_SESSION_BG))
            self.calendar.setDateTextFormat(qdate, fmt)
            self._touched_dates.add(qdate)

        if conflicts:
            lines = [
                f"Room \"{c.room}\" is booked for {len(c.sessions)} sessions on {c.date}: "
                + ", ".join(s.title or "(untitled)" for s in c.sessions)
                for c in conflicts
            ]
            self.banner.setText("⚠ Booking conflict detected!\n" + "\n".join(lines))
            self.banner.setStyleSheet(
                "padding: 8px; border-radius: 4px; background: #f8c9c9; color: #7a1f1f; font-weight: bold;"
            )
        else:
            self.banner.setText("No room conflicts detected.")
            self.banner.setStyleSheet(
                "padding: 8px; border-radius: 4px; background: #dcf5df; color: #1f6b2f;"
            )

        self._update_day_list()

    def _update_day_list(self) -> None:
        self.day_list.clear()
        selected = self.calendar.selectedDate()
        date_str = selected.toString("yyyy-MM-dd")
        sessions = [s for s in self.db.list_sessions() if s.date.strip() == date_str]
        if not sessions:
            self.day_list.addItem("(no session on this day)")
            return
        conflicts = self.db.find_room_conflicts(sessions)
        conflict_session_ids = {s.id for c in conflicts for s in c.sessions}
        for s in sessions:
            room_part = f" — {s.room}" if s.room else ""
            speaker_part = f" ({s.speaker_name})" if s.speaker_name else ""
            text = f"{s.time or '?'}  {s.title or '(untitled)'}{room_part}{speaker_part}"
            item = QListWidgetItem(text)
            if s.id in conflict_session_ids:
                item.setForeground(QBrush(CONFLICT_FG))
                text_font = item.font()
                text_font.setBold(True)
                item.setFont(text_font)
            self.day_list.addItem(item)
