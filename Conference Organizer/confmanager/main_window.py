"""PySide6 graphical interface for Conference Organizer."""

from __future__ import annotations

import os

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QBrush, QColor, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
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

from .db import ConferenceDB
from .dialogs import SpeakerDialog, SessionDialog
from .pdf_export import export_book_of_abstracts, ExportError
from .calendar_tab import CalendarTab

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
        add_btn.clicked.connect(self.add_speaker)
        edit_btn.clicked.connect(self.edit_selected)
        remove_btn.clicked.connect(self.remove_selected)

        buttons = QHBoxLayout()
        buttons.addWidget(add_btn)
        buttons.addWidget(edit_btn)
        buttons.addWidget(remove_btn)
        buttons.addStretch(1)

        layout = QVBoxLayout(self)
        layout.addLayout(buttons)
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
        remove_btn = QPushButton("Delete session")
        export_btn = QPushButton("Export Book of Abstracts…")
        add_btn.clicked.connect(self.add_session)
        edit_btn.clicked.connect(self.edit_selected)
        remove_btn.clicked.connect(self.remove_selected)
        export_btn.clicked.connect(self.export_book)

        buttons = QHBoxLayout()
        buttons.addWidget(add_btn)
        buttons.addWidget(edit_btn)
        buttons.addWidget(remove_btn)
        buttons.addStretch(1)
        buttons.addWidget(export_btn)

        layout = QVBoxLayout(self)
        layout.addLayout(buttons)
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

    def _show_context_menu(self, pos) -> None:
        if self.table.itemAt(pos) is None:
            return
        menu = QMenu(self)
        menu.addAction("Edit…", self.edit_selected)
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
        session = next((s for s in self.db.list_sessions() if s.id == session_id), None)
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


class MainWindow(QMainWindow):
    def __init__(self, db: ConferenceDB) -> None:
        super().__init__()
        self.db = db
        self.setWindowTitle("Conference Organizer")
        self.resize(1000, 640)

        tabs = QTabWidget()
        self.speakers_tab = SpeakersTab(db)
        self.sessions_tab = SessionsTab(db)
        self.calendar_tab = CalendarTab(db)
        tabs.addTab(self.speakers_tab, "Speakers")
        tabs.addTab(self.sessions_tab, "Sessions")
        tabs.addTab(self.calendar_tab, "Calendar")

        # Any change to speakers or sessions can affect the other two tabs
        # (a renamed speaker shows up in Sessions, a new session can create
        # or resolve a room conflict shown in Sessions/Calendar) - keep
        # everything in sync by refreshing all three together.
        def refresh_all():
            self.speakers_tab_refresh()
            self.sessions_tab_refresh()
            self.calendar_tab.refresh()

        self.speakers_tab_refresh = self.speakers_tab.refresh
        self.sessions_tab_refresh = self.sessions_tab.refresh
        self.speakers_tab.refresh = refresh_all  # type: ignore[method-assign]
        self.sessions_tab.refresh = refresh_all  # type: ignore[method-assign]

        self.setCentralWidget(tabs)
        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage(f"Data file: {db.db_path}")


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
