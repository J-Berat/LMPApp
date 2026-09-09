"""PySide6 graphical interface for Conference Organizer."""

from __future__ import annotations

import os
from datetime import date

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QBrush, QColor, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QTableWidget,
    QTableWidgetItem,
    QAbstractItemView,
    QPushButton,
    QTabWidget,
    QMessageBox,
    QFileDialog,
    QHeaderView,
    QStatusBar,
    QMenu,
)

from .db import ConferenceDB, Session, add_one_month
from .dialogs import SpeakerDialog, SessionDialog
from .pdf_export import export_book_of_abstracts, ExportError
from .calendar_tab import CalendarTab
from .csv_io import export_speakers_csv, import_speakers_csv, export_sessions_csv, import_sessions_csv
from .ical_export import export_session_ics, export_schedule_ics

CONFLICT_FG = QColor("#7a1f1f")


class SpeakersTab(QWidget):
    def __init__(self, db: ConferenceDB, parent=None) -> None:
        super().__init__(parent)
        self.db = db

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Name", "Email", "Affiliation", "Status"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.doubleClicked.connect(self.edit_selected)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        QShortcut(QKeySequence(Qt.Key_Delete), self.table, activated=self.remove_selected)
        QShortcut(QKeySequence(Qt.Key_Backspace), self.table, activated=self.remove_selected)

        add_btn = QPushButton("Add speaker…")
        edit_btn = QPushButton("Edit…")
        remove_btn = QPushButton("Delete speaker")
        export_csv_btn = QPushButton("Export CSV…")
        import_csv_btn = QPushButton("Import CSV…")
        add_btn.clicked.connect(self.add_speaker)
        edit_btn.clicked.connect(self.edit_selected)
        remove_btn.clicked.connect(self.remove_selected)
        export_csv_btn.clicked.connect(self.export_csv)
        import_csv_btn.clicked.connect(self.import_csv)

        buttons = QHBoxLayout()
        buttons.addWidget(add_btn)
        buttons.addWidget(edit_btn)
        buttons.addWidget(remove_btn)
        buttons.addStretch(1)
        buttons.addWidget(import_csv_btn)
        buttons.addWidget(export_csv_btn)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Filter speakers…")
        self.search_edit.textChanged.connect(self._apply_filter)
        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Filter:"))
        filter_row.addWidget(self.search_edit)

        layout = QVBoxLayout(self)
        layout.addLayout(buttons)
        layout.addLayout(filter_row)
        layout.addWidget(self.table)

        self.refresh()

    def refresh(self) -> None:
        speakers = self.db.list_speakers()
        self.table.setRowCount(len(speakers))
        for row, sp in enumerate(speakers):
            self.table.setItem(row, 0, self._item(sp.name, sp.id))
            self.table.setItem(row, 1, self._item(sp.email))
            self.table.setItem(row, 2, self._item(sp.affiliation))
            self.table.setItem(row, 3, self._item(sp.status))
        self._apply_filter()

    def _apply_filter(self) -> None:
        text = self.search_edit.text().strip().lower()
        for row in range(self.table.rowCount()):
            if not text:
                self.table.setRowHidden(row, False)
                continue
            haystack = " ".join(
                self.table.item(row, col).text().lower()
                for col in range(self.table.columnCount())
                if self.table.item(row, col) is not None
            )
            self.table.setRowHidden(row, text not in haystack)

    @staticmethod
    def _item(text: str, user_data=None) -> QTableWidgetItem:
        item = QTableWidgetItem(text)
        if user_data is not None:
            item.setData(Qt.UserRole, user_data)
        return item

    def _selected_speaker_id(self) -> int | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        return self.table.item(row, 0).data(Qt.UserRole)

    def _show_context_menu(self, pos) -> None:
        if self.table.itemAt(pos) is None:
            return
        menu = QMenu(self)
        menu.addAction("Edit…", self.edit_selected)
        menu.addAction("Delete", self.remove_selected)
        menu.exec(self.table.mapToGlobal(pos))

    def add_speaker(self) -> None:
        dialog = SpeakerDialog(parent=self)
        if dialog.exec():
            self.db.add_speaker(dialog.result_speaker())
            self.refresh()

    def edit_selected(self) -> None:
        speaker_id = self._selected_speaker_id()
        if speaker_id is None:
            return
        speaker = next((s for s in self.db.list_speakers() if s.id == speaker_id), None)
        if speaker is None:
            return
        dialog = SpeakerDialog(speaker=speaker, parent=self)
        if dialog.exec():
            self.db.update_speaker(dialog.result_speaker())
            self.refresh()

    def remove_selected(self) -> None:
        speaker_id = self._selected_speaker_id()
        if speaker_id is None:
            return
        reply = QMessageBox.question(
            self, "Delete speaker",
            "Delete this speaker? Sessions referencing them will keep their date/title but lose the speaker link.",
        )
        if reply == QMessageBox.Yes:
            self.db.delete_speaker(speaker_id)
            self.refresh()

    def export_csv(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Export speakers to CSV", "speakers.csv", "CSV (*.csv)")
        if not path:
            return
        try:
            export_speakers_csv(self.db.list_speakers(), path)
        except Exception as exc:  # pragma: no cover - safety net for the UI
            QMessageBox.critical(self, "Export failed", str(exc))
            return
        QMessageBox.information(self, "Export complete", f"File created:\n{path}")

    def import_csv(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Import speakers from CSV", "", "CSV (*.csv)")
        if not path:
            return
        try:
            new_speakers = import_speakers_csv(path)
        except Exception as exc:
            QMessageBox.critical(self, "Import failed", str(exc))
            return
        for sp in new_speakers:
            self.db.add_speaker(sp)
        self.refresh()
        QMessageBox.information(self, "Import complete", f"Added {len(new_speakers)} speaker(s).")


class SessionsTab(QWidget):
    def __init__(self, db: ConferenceDB, parent=None) -> None:
        super().__init__(parent)
        self.db = db

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Date", "Time", "Title", "Room", "Speaker", "Status"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.doubleClicked.connect(self.edit_selected)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        QShortcut(QKeySequence(Qt.Key_Delete), self.table, activated=self.remove_selected)
        QShortcut(QKeySequence(Qt.Key_Backspace), self.table, activated=self.remove_selected)

        add_btn = QPushButton("Add session…")
        edit_btn = QPushButton("Edit…")
        duplicate_btn = QPushButton("Duplicate…")
        remove_btn = QPushButton("Delete session")
        export_btn = QPushButton("Export Book of Abstracts…")
        export_ics_btn = QPushButton("Export calendar (.ics)…")
        export_csv_btn = QPushButton("Export CSV…")
        import_csv_btn = QPushButton("Import CSV…")
        add_btn.clicked.connect(self.add_session)
        edit_btn.clicked.connect(self.edit_selected)
        duplicate_btn.clicked.connect(self.duplicate_selected)
        remove_btn.clicked.connect(self.remove_selected)
        export_btn.clicked.connect(self.export_book)
        export_ics_btn.clicked.connect(self.export_ics_schedule)
        export_csv_btn.clicked.connect(self.export_csv)
        import_csv_btn.clicked.connect(self.import_csv)

        buttons = QHBoxLayout()
        buttons.addWidget(add_btn)
        buttons.addWidget(edit_btn)
        buttons.addWidget(duplicate_btn)
        buttons.addWidget(remove_btn)
        buttons.addStretch(1)
        buttons.addWidget(import_csv_btn)
        buttons.addWidget(export_csv_btn)
        buttons.addWidget(export_ics_btn)
        buttons.addWidget(export_btn)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Filter sessions…")
        self.search_edit.textChanged.connect(self._apply_filter)
        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Filter:"))
        filter_row.addWidget(self.search_edit)

        layout = QVBoxLayout(self)
        layout.addLayout(buttons)
        layout.addLayout(filter_row)
        layout.addWidget(self.table)

        self.refresh()

    def refresh(self) -> None:
        sessions = self.db.list_sessions()
        conflicts = self.db.find_room_conflicts(sessions)
        conflict_ids = {s.id for c in conflicts for s in c.sessions}

        self.table.setRowCount(len(sessions))
        for row, s in enumerate(sessions):
            values = [s.date, s.time, s.title, s.room, s.speaker_name, s.status]
            for col, value in enumerate(values):
                item = self._item(value, s.id if col == 0 else None)
                if s.id in conflict_ids:
                    item.setForeground(QBrush(CONFLICT_FG))
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)
                    item.setToolTip("Room conflict: another session is booked in the same room on the same date.")
                self.table.setItem(row, col, item)
        self._apply_filter()

    def _apply_filter(self) -> None:
        text = self.search_edit.text().strip().lower()
        for row in range(self.table.rowCount()):
            if not text:
                self.table.setRowHidden(row, False)
                continue
            haystack = " ".join(
                self.table.item(row, col).text().lower()
                for col in range(self.table.columnCount())
                if self.table.item(row, col) is not None
            )
            self.table.setRowHidden(row, text not in haystack)

    @staticmethod
    def _item(text: str, user_data=None) -> QTableWidgetItem:
        item = QTableWidgetItem(text)
        if user_data is not None:
            item.setData(Qt.UserRole, user_data)
        return item

    def _selected_session_id(self) -> int | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        return self.table.item(row, 0).data(Qt.UserRole)

    def _selected_session(self) -> Session | None:
        session_id = self._selected_session_id()
        if session_id is None:
            return None
        return next((s for s in self.db.list_sessions() if s.id == session_id), None)

    def _show_context_menu(self, pos) -> None:
        if self.table.itemAt(pos) is None:
            return
        menu = QMenu(self)
        menu.addAction("Edit…", self.edit_selected)
        menu.addAction("Duplicate…", self.duplicate_selected)
        menu.addAction("Export to calendar (.ics)…", self.export_ics_selected)
        menu.addAction("Delete", self.remove_selected)
        menu.exec(self.table.mapToGlobal(pos))

    def _warn_if_conflict(self, session, exclude_id: int | None) -> bool:
        """Return True if the user wants to proceed despite a new conflict."""
        others = self.db.conflicts_for(session.date, session.room, exclude_session_id=exclude_id)
        if not others:
            return True
        names = ", ".join(o.title or "(untitled)" for o in others)
        reply = QMessageBox.warning(
            self,
            "Room conflict",
            f'Room "{session.room}" is already booked on {session.date} for: {names}.\n\n'
            "Save anyway?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        return reply == QMessageBox.Yes

    def add_session(self) -> None:
        speakers = self.db.list_speakers()
        rooms = self.db.list_rooms()
        dialog = SessionDialog(speakers=speakers, rooms=rooms, parent=self)
        if dialog.exec():
            session = dialog.result_session()
            if self._warn_if_conflict(session, exclude_id=None):
                self.db.add_session(session)
                self.refresh()

    def edit_selected(self) -> None:
        session_id = self._selected_session_id()
        if session_id is None:
            return
        session = self._selected_session()
        if session is None:
            return
        speakers = self.db.list_speakers()
        rooms = self.db.list_rooms()
        dialog = SessionDialog(speakers=speakers, rooms=rooms, session=session, parent=self)
        if dialog.exec():
            updated = dialog.result_session()
            if self._warn_if_conflict(updated, exclude_id=session_id):
                self.db.update_session(updated)
                self.refresh()

    def duplicate_selected(self) -> None:
        """Open the Add session dialog pre-filled from the selected session,
        with the date advanced by one month - a quick way to create next
        month's slot in a recurring series (same time/room/link, blank
        title/speaker/abstract for the new talk)."""
        session = self._selected_session()
        if session is None:
            return
        draft = Session(
            id=None,
            speaker_id=None,
            date=add_one_month(session.date) if session.date.strip() else "",
            time=session.time,
            title="",
            authors="",
            abstract="",
            room=session.room,
            status="scheduled",
            recording_url=session.recording_url,
            slides_url="",
            notes="",
        )
        speakers = self.db.list_speakers()
        rooms = self.db.list_rooms()
        dialog = SessionDialog(speakers=speakers, rooms=rooms, session=draft, parent=self)
        if dialog.exec():
            new_session = dialog.result_session()
            if self._warn_if_conflict(new_session, exclude_id=None):
                self.db.add_session(new_session)
                self.refresh()

    def remove_selected(self) -> None:
        session_id = self._selected_session_id()
        if session_id is None:
            return
        reply = QMessageBox.question(self, "Delete session", "Delete this session?")
        if reply == QMessageBox.Yes:
            self.db.delete_session(session_id)
            self.refresh()

    def export_book(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Choose a name and location for the Book of Abstracts", "book_of_abstracts.pdf", "PDF (*.pdf)"
        )
        if not path:
            return
        try:
            export_book_of_abstracts(self.db.list_sessions(), path)
        except ExportError as exc:
            QMessageBox.warning(self, "Cannot export", str(exc))
            return
        except Exception as exc:  # pragma: no cover - safety net for the UI
            QMessageBox.critical(self, "Export failed", str(exc))
            return
        QMessageBox.information(self, "Export complete", f"File created:\n{path}")

    def export_ics_schedule(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Export full schedule to a calendar file", "schedule.ics", "iCalendar (*.ics)"
        )
        if not path:
            return
        try:
            export_schedule_ics(self.db.list_sessions(), path)
        except ValueError as exc:
            QMessageBox.warning(self, "Cannot export", str(exc))
            return
        except Exception as exc:  # pragma: no cover - safety net for the UI
            QMessageBox.critical(self, "Export failed", str(exc))
            return
        QMessageBox.information(self, "Export complete", f"File created:\n{path}")

    def export_ics_selected(self) -> None:
        session = self._selected_session()
        if session is None:
            return
        default_name = (session.title or "session").strip().replace("/", "-") + ".ics"
        path, _ = QFileDialog.getSaveFileName(self, "Export session to a calendar file", default_name, "iCalendar (*.ics)")
        if not path:
            return
        try:
            export_session_ics(session, path)
        except ValueError as exc:
            QMessageBox.warning(self, "Cannot export", str(exc))
            return
        except Exception as exc:  # pragma: no cover - safety net for the UI
            QMessageBox.critical(self, "Export failed", str(exc))
            return
        QMessageBox.information(self, "Export complete", f"File created:\n{path}")

    def export_csv(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Export sessions to CSV", "sessions.csv", "CSV (*.csv)")
        if not path:
            return
        try:
            export_sessions_csv(self.db.list_sessions(), path)
        except Exception as exc:  # pragma: no cover - safety net for the UI
            QMessageBox.critical(self, "Export failed", str(exc))
            return
        QMessageBox.information(self, "Export complete", f"File created:\n{path}")

    def import_csv(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Import sessions from CSV", "", "CSV (*.csv)")
        if not path:
            return
        try:
            new_sessions = import_sessions_csv(path, self.db.list_speakers())
        except Exception as exc:
            QMessageBox.critical(self, "Import failed", str(exc))
            return
        for s in new_sessions:
            self.db.add_session(s)
        self.refresh()
        QMessageBox.information(self, "Import complete", f"Added {len(new_sessions)} session(s).")


class MainWindow(QMainWindow):
    def __init__(self, db: ConferenceDB) -> None:
        super().__init__()
        self.db = db
        self.setWindowTitle("Conference Organizer")
        self.resize(1000, 640)

        self.next_session_label = QLabel("")
        self.next_session_label.setWordWrap(True)

        tabs = QTabWidget()
        self.speakers_tab = SpeakersTab(db)
        self.sessions_tab = SessionsTab(db)
        self.calendar_tab = CalendarTab(db)
        tabs.addTab(self.speakers_tab, "Speakers")
        tabs.addTab(self.sessions_tab, "Sessions")
        tabs.addTab(self.calendar_tab, "Calendar")

        # Any change to speakers or sessions can affect the other two tabs
        # (a renamed speaker shows up in Sessions, a new session can create
        # or resolve a room conflict shown in Sessions/Calendar, and either
        # can change what "next session" is) - keep everything in sync by
        # refreshing all of it together.
        def refresh_all():
            self.speakers_tab_refresh()
            self.sessions_tab_refresh()
            self.calendar_tab.refresh()
            self._update_next_session_banner()

        self.speakers_tab_refresh = self.speakers_tab.refresh
        self.sessions_tab_refresh = self.sessions_tab.refresh
        self.speakers_tab.refresh = refresh_all  # type: ignore[method-assign]
        self.sessions_tab.refresh = refresh_all  # type: ignore[method-assign]

        central = QWidget()
        central_layout = QVBoxLayout(central)
        central_layout.addWidget(self.next_session_label)
        central_layout.addWidget(tabs)
        self.setCentralWidget(central)

        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage(f"Data file: {db.db_path}")

        self._update_next_session_banner()

    def _update_next_session_banner(self) -> None:
        today = date.today().isoformat()
        upcoming = [
            s for s in self.db.list_sessions()
            if s.date.strip() >= today and s.status != "cancelled"
        ]
        upcoming.sort(key=lambda s: (s.date, s.time))
        if upcoming:
            s = upcoming[0]
            room_part = f" ({s.room})" if s.room else ""
            speaker_part = f" — {s.speaker_name}" if s.speaker_name else ""
            when = f"{s.date} {s.time}".strip()
            self.next_session_label.setText(
                f"Next session: {when}{room_part} — {s.title or '(untitled)'}{speaker_part}"
            )
            self.next_session_label.setStyleSheet(
                "padding: 8px; font-weight: bold; border-radius: 4px; background: #dbe9ff; color: #1f2d5a;"
            )
        else:
            self.next_session_label.setText("No upcoming session scheduled.")
            self.next_session_label.setStyleSheet(
                "padding: 8px; border-radius: 4px; background: #eeeeee; color: #555555;"
            )


def run() -> None:
    app = QApplication.instance() or QApplication([])
    app.setApplicationName("Conference Organizer")
    icon_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "AppIcon.png")
    if os.path.isfile(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    db = ConferenceDB()
    window = MainWindow(db)
    window.show()
    app.exec()
    db.close()


if __name__ == "__main__":
    run()
