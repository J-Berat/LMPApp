"""Compile all session abstracts into a single "Book of Abstracts" PDF."""

from __future__ import annotations

from fpdf import FPDF
from fpdf.enums import XPos, YPos

from .db import Session


class ExportError(Exception):
    """Raised when the Book of Abstracts cannot be generated."""


class _BookOfAbstracts(FPDF):
    def __init__(self, event_title: str) -> None:
        super().__init__()
        self.event_title = event_title
        self.set_auto_page_break(auto=True, margin=20)

    def header(self) -> None:
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(120, 120, 120)
        self.cell(0, 8, self.event_title, align="R")
        self.ln(12)
        self.set_text_color(0, 0, 0)


def export_book_of_abstracts(sessions: list[Session], output_path: str, event_title: str = "Book of Abstracts") -> None:
    """Write a PDF with a title page and one entry per session with an abstract.

    Sessions are expected pre-sorted (e.g. by date, as returned by
    ConferenceDB.list_sessions()). Sessions with an empty abstract are
    skipped. Raises ExportError if there is nothing to export.
    """
    entries = [s for s in sessions if s.abstract.strip() or s.title.strip()]
    if not entries:
        raise ExportError("No session has a title or an abstract yet.")

    pdf = _BookOfAbstracts(event_title)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 22)
    pdf.ln(30)
    pdf.multi_cell(0, 12, event_title, align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "", 12)
    pdf.ln(4)
    pdf.multi_cell(0, 8, f"{len(entries)} talk(s)", align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    for entry in entries:
        pdf.add_page()

        pdf.set_font("Helvetica", "B", 15)
        pdf.multi_cell(0, 9, entry.title or "(untitled talk)", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(1)

        pdf.set_font("Helvetica", "I", 11)
        speaker_line = entry.authors or entry.speaker_name
        if speaker_line:
            pdf.multi_cell(0, 7, speaker_line, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        date_line = " ".join(part for part in (entry.date, entry.time) if part)
        if date_line:
            pdf.set_font("Helvetica", "", 10)
            pdf.set_text_color(100, 100, 100)
            pdf.multi_cell(0, 6, date_line, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.set_text_color(0, 0, 0)

        pdf.ln(4)
        pdf.set_font("Helvetica", "", 11)
        pdf.multi_cell(0, 6, entry.abstract or "(no abstract submitted)", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.output(output_path)
