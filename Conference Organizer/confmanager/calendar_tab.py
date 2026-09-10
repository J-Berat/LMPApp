"""Calendar view: every session at a glance, with room conflicts highlighted."""

from __future__ import annotations

from collections import defaultdict

from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QTextCharFormat, QColor, QBrush, QFont
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QCalendarWidget,
    QListWidget,
    QListWidgetItem,
    QLabel,
    QCheckBox,
)

from .db import ConferenceDB, Session

DAY_WITH_SESSION_BG = QColor("#dbe9ff")
CONFLICT_BG = QColor("#f8c9c9")
CONFLICT_FG = QColor("#7a1f1f")


def _session_line(s: Session) -> str:
    room_part = f" — {s.room}" if s.room else ""
    speaker_part = f" ({s.speaker_name})" if s.speaker_name else ""
    category_part = f" [{s.category}]" if s.category else ""
    return f"{s.time or '?'}  {s.title or '(untitled)'}{room_part}{speaker_part}{category_part}"


class CalendarTab(QWidget):
    """A month calendar with all sessions, plus a same-day (or full
    multi-day) list and a conflict banner listing every room double-booking."""

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

        self.show_all_checkbox = QCheckBox("Show full program (all days)")
        self.show_all_checkbox.stateChanged.connect(self._update_day_list)

        self.day_list = QListWidget()

        side = QVBoxLayout()
        self.side_label = QLabel("Sessions on selected day:")
        side.addWidget(self.side_label)
        side.addWidget(self.show_all_checkbox)
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
        if self.show_all_checkbox.isChecked():
            self.side_label.setText("Full program (all days):")
            self._populate_full_program()
        else:
            self.side_label.setText("Sessions on selected day:")
            self._populate_selected_day()

    def _populate_selected_day(self) -> None:
        selected = self.calendar.selectedDate()
        date_str = selected.toString("yyyy-MM-dd")
        sessions = [s for s in self.db.list_sessions() if s.date.strip() == date_str]
        if not sessions:
            self.day_list.addItem("(no session on this day)")
            return
        conflicts = self.db.find_room_conflicts(sessions)
        conflict_ids = {s.id for c in conflicts for s in c.sessions}
        for s in sessions:
            self.day_list.addItem(self._session_item(s, conflict_ids))

    def _populate_full_program(self) -> None:
        sessions = self.db.list_sessions()
        if not sessions:
            self.day_list.addItem("(no sessions yet)")
            return
        conflicts = self.db.find_room_conflicts(sessions)
        conflict_ids = {s.id for c in conflicts for s in c.sessions}

        by_date: dict[str, list[Session]] = defaultdict(list)
        undated: list[Session] = []
        for s in sessions:
            if s.date.strip():
                by_date[s.date.strip()].append(s)
            else:
                undated.append(s)

        for date_str in sorted(by_date.keys()):
            header = QListWidgetItem(date_str)
            header_font = header.font()
            header_font.setBold(True)
            header.setFont(header_font)
            header.setFlags(Qt.NoItemFlags)  # a plain section label, not a selectable row
            self.day_list.addItem(header)
            for s in by_date[date_str]:
                self.day_list.addItem(self._session_item(s, conflict_ids))

        if undated:
            header = QListWidgetItem("Date to be announced")
            header_font = header.font()
            header_font.setBold(True)
            header.setFont(header_font)
            header.setFlags(Qt.NoItemFlags)
            self.day_list.addItem(header)
            for s in undated:
                self.day_list.addItem(self._session_item(s, conflict_ids))

    @staticmethod
    def _session_item(s: Session, conflict_ids: set) -> QListWidgetItem:
        item = QListWidgetItem("    " + _session_line(s))
        if s.id in conflict_ids:
            item.setForeground(QBrush(CONFLICT_FG))
            font: QFont = item.font()
            font.setBold(True)
            item.setFont(font)
        return item
