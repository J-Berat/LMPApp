"""Compile all session abstracts into a single "Book of Abstracts" PDF."""

from __future__ import annotations

from collections import defaultdict

from fpdf import FPDF
from fpdf.enums import XPos, YPos

from .db import Session, Speaker


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


def _group_by_day(sessions: list[Session]) -> list[tuple[str, list[Session]]]:
    """Group sessions by date, preserving chronological order. Sessions
    with no date are kept together at the end under an empty key."""
    by_date: dict[str, list[Session]] = defaultdict(list)
    for s in sessions:
        by_date[s.date.strip()].append(s)
    dated = sorted((d for d in by_date if d), key=lambda d: d)
    groups = [(d, by_date[d]) for d in dated]
    if by_date.get(""):
        groups.append(("", by_date[""]))
    return groups


def export_book_of_abstracts(sessions: list[Session], output_path: str, event_title: str = "Book of Abstracts") -> None:
    """Write a PDF with a title page and one entry per session with an abstract.

    Sessions are grouped into "Day N" sections by date (in a multi-day
    event this makes the program's structure clear at a glance) and are
    expected pre-sorted within each day (e.g. by time, as returned by
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

    day_groups = _group_by_day(entries)
    multi_day = len([d for d, _ in day_groups if d]) > 1

    for day_index, (day, day_entries) in enumerate(day_groups, start=1):
        if multi_day:
            pdf.add_page()
            pdf.set_font("Helvetica", "B", 18)
            label = f"Day {day_index} - {day}" if day else "Date to be announced"
            pdf.multi_cell(0, 12, label, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        for entry in day_entries:
            pdf.add_page()

            pdf.set_font("Helvetica", "B", 15)
            pdf.multi_cell(0, 9, entry.title or "(untitled talk)", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

            if entry.category.strip():
                pdf.set_font("Helvetica", "I", 10)
                pdf.set_text_color(20, 90, 100)
                pdf.multi_cell(0, 6, entry.category.strip(), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                pdf.set_text_color(0, 0, 0)

            pdf.ln(1)

            pdf.set_font("Helvetica", "I", 11)
            speaker_line = entry.authors or entry.speaker_name
            if speaker_line:
                pdf.multi_cell(0, 7, speaker_line, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

            date_line = " ".join(part for part in (entry.date, entry.time) if part)
            if entry.room.strip():
                date_line = f"{date_line} - {entry.room.strip()}" if date_line else entry.room.strip()
            if date_line:
                pdf.set_font("Helvetica", "", 10)
                pdf.set_text_color(100, 100, 100)
                pdf.multi_cell(0, 6, date_line, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                pdf.set_text_color(0, 0, 0)

            pdf.ln(4)
            pdf.set_font("Helvetica", "", 11)
            pdf.multi_cell(0, 6, entry.abstract or "(no abstract submitted)", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.output(output_path)


def export_name_badges(speakers: list[Speaker], output_path: str, event_title: str = "") -> None:
    """Write a printable A4 sheet of name badges, 8 per page (2 columns x
    4 rows), each showing a speaker's name and affiliation inside a
    light dashed cut line. Speakers with an empty name are skipped.
    Raises ExportError if there is nothing to export.
    """
    entries = [s for s in speakers if s.name.strip()]
    if not entries:
        raise ExportError("No speaker has a name yet.")

    cols, rows = 2, 4
    margin = 10.0
    gap = 6.0
    page_w, page_h = 210.0, 297.0  # A4, in mm
    badge_w = (page_w - 2 * margin - (cols - 1) * gap) / cols
    badge_h = (page_h - 2 * margin - (rows - 1) * gap) / rows
    per_page = cols * rows

    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(auto=False)
    pdf.set_margin(margin)

    for page_start in range(0, len(entries), per_page):
        pdf.add_page()
        for i, sp in enumerate(entries[page_start : page_start + per_page]):
            col = i % cols
            row = i // cols
            x = margin + col * (badge_w + gap)
            y = margin + row * (badge_h + gap)

            pdf.set_dash_pattern(dash=2, gap=2)
            pdf.set_draw_color(160, 160, 160)
            pdf.rect(x, y, badge_w, badge_h)
            pdf.set_dash_pattern()
            pdf.set_draw_color(0, 0, 0)

            if event_title.strip():
                pdf.set_xy(x + 4, y + 6)
                pdf.set_font("Helvetica", "", 9)
                pdf.set_text_color(130, 130, 130)
                pdf.cell(badge_w - 8, 5, event_title.strip(), align="C")
                pdf.set_text_color(0, 0, 0)

            pdf.set_xy(x + 4, y + badge_h / 2 - 10)
            pdf.set_font("Helvetica", "B", 18)
            pdf.multi_cell(badge_w - 8, 8, sp.name.strip(), align="C")

            if sp.affiliation.strip():
                pdf.set_xy(x + 4, y + badge_h / 2 + 6)
                pdf.set_font("Helvetica", "", 11)
                pdf.set_text_color(90, 90, 90)
                pdf.multi_cell(badge_w - 8, 6, sp.affiliation.strip(), align="C")
                pdf.set_text_color(0, 0, 0)

    pdf.output(output_path)
