"""Add/edit dialogs for speakers and sessions."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QLineEdit,
    QTextEdit,
    QComboBox,
    QDialogButtonBox,
    QVBoxLayout,
)

from .db import Speaker, Session, SPEAKER_STATUSES, SESSION_STATUSES


class SpeakerDialog(QDialog):
    """Add or edit a single speaker."""

    def __init__(self, speaker: Speaker | None = None, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Edit speaker" if speaker else "Add speaker")
        self.setMinimumWidth(420)

        self.name_edit = QLineEdit(speaker.name if speaker else "")
        self.email_edit = QLineEdit(speaker.email if speaker else "")
        self.affiliation_edit = QLineEdit(speaker.affiliation if speaker else "")

        self.status_combo = QComboBox()
        self.status_combo.addItems(SPEAKER_STATUSES)
        if speaker:
            self.status_combo.setCurrentText(speaker.status)

        self.notes_edit = QTextEdit(speaker.notes if speaker else "")
        self.notes_edit.setFixedHeight(80)

        form = QFormLayout()
        form.addRow("Name:", self.name_edit)
        form.addRow("Email:", self.email_edit)
        form.addRow("Affiliation:", self.affiliation_edit)
        form.addRow("Status:", self.status_combo)
        form.addRow("Notes:", self.notes_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

        self._result: Speaker | None = speaker

    def _on_accept(self) -> None:
        if not self.name_edit.text().strip():
            self.name_edit.setFocus()
            return
        self.accept()

    def result_speaker(self) -> Speaker:
        base = self._result
        return Speaker(
            id=base.id if base else None,
            name=self.name_edit.text().strip(),
            email=self.email_edit.text().strip(),
            affiliation=self.affiliation_edit.text().strip(),
            status=self.status_combo.currentText(),
            notes=self.notes_edit.toPlainText().strip(),
            created_at=base.created_at if base else Speaker(id=None, name="").created_at,
        )


class SessionDialog(QDialog):
    """Add or edit a single session/talk."""

    def __init__(
        self,
        speakers: list[Speaker],
        rooms: list[str] | None = None,
        session: Session | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Edit session" if session else "Add session")
        self.setMinimumWidth(480)
        self._speakers = speakers

        self.speaker_combo = QComboBox()
        self.speaker_combo.addItem("(no speaker assigned)", None)
        for sp in speakers:
            self.speaker_combo.addItem(sp.name, sp.id)
        if session and session.speaker_id is not None:
            idx = self.speaker_combo.findData(session.speaker_id)
            if idx >= 0:
                self.speaker_combo.setCurrentIndex(idx)

        self.date_edit = QLineEdit(session.date if session else "")
        self.date_edit.setPlaceholderText("YYYY-MM-DD")
        self.time_edit = QLineEdit(session.time if session else "")
        self.time_edit.setPlaceholderText("e.g. 14:00 CET")

        self.room_combo = QComboBox()
        self.room_combo.setEditable(True)
        self.room_combo.addItem("")
        for room in rooms or []:
            self.room_combo.addItem(room)
        if session:
            self.room_combo.setCurrentText(session.room)

        self.title_edit = QLineEdit(session.title if session else "")
        self.authors_edit = QLineEdit(session.authors if session else "")
        self.abstract_edit = QTextEdit(session.abstract if session else "")
        self.abstract_edit.setFixedHeight(120)

        self.status_combo = QComboBox()
        self.status_combo.addItems(SESSION_STATUSES)
        if session:
            self.status_combo.setCurrentText(session.status)

        self.recording_edit = QLineEdit(session.recording_url if session else "")
        self.slides_edit = QLineEdit(session.slides_url if session else "")
        self.notes_edit = QTextEdit(session.notes if session else "")
        self.notes_edit.setFixedHeight(60)

        form = QFormLayout()
        form.addRow("Speaker:", self.speaker_combo)
        form.addRow("Date:", self.date_edit)
        form.addRow("Time:", self.time_edit)
        form.addRow("Room:", self.room_combo)
        form.addRow("Talk title:", self.title_edit)
        form.addRow("Author(s):", self.authors_edit)
        form.addRow("Abstract:", self.abstract_edit)
        form.addRow("Status:", self.status_combo)
        form.addRow("Recording URL:", self.recording_edit)
        form.addRow("Slides URL:", self.slides_edit)
        form.addRow("Notes:", self.notes_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

        self._result: Session | None = session

    def result_session(self) -> Session:
        base = self._result
        return Session(
            id=base.id if base else None,
            speaker_id=self.speaker_combo.currentData(),
            date=self.date_edit.text().strip(),
            time=self.time_edit.text().strip(),
            title=self.title_edit.text().strip(),
            authors=self.authors_edit.text().strip(),
            abstract=self.abstract_edit.toPlainText().strip(),
            room=self.room_combo.currentText().strip(),
            status=self.status_combo.currentText(),
            recording_url=self.recording_edit.text().strip(),
            slides_url=self.slides_edit.text().strip(),
            notes=self.notes_edit.toPlainText().strip(),
        )
