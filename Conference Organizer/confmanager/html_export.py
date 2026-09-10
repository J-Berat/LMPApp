"""Static HTML export of the schedule - a single self-contained page you
can host or send by email so people can see the program without opening
the app. Complements the Book of Abstracts PDF: this is a schedule
(time/room/speaker), not the full abstract texts."""

from __future__ import annotations

import html
from collections import defaultdict
from datetime import datetime

from .db import Session


def _format_day_header(date_str: str) -> str:
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d")
        return d.strftime("%A, %B %d, %Y")
    except ValueError:
        return date_str or "Date to be announced"


def _esc(text: str) -> str:
    return html.escape(text or "")


def _session_row(s: Session) -> str:
    title_class = "session-title cancelled" if s.status == "cancelled" else "session-title"

    meta_parts = []
    if s.speaker_name.strip():
        meta_parts.append(_esc(s.speaker_name.strip()))
    if s.room.strip():
        meta_parts.append(_esc(s.room.strip()))
    meta = " · ".join(meta_parts)
    meta_html = f'<div class="session-meta">{meta}</div>' if meta else ""

    badges = ""
    if s.category.strip():
        badges += f'<span class="badge">{_esc(s.category.strip())}</span>'
    if s.status == "cancelled":
        badges += '<span class="badge cancelled">Cancelled</span>'

    return (
        f'<div class="session">'
        f'<span class="session-time">{_esc(s.time or "?")}</span>'
        f'<span class="{title_class}">{_esc(s.title or "(untitled)")}</span>{badges}'
        f'{meta_html}'
        f'</div>'
    )


def export_program_html(sessions: list[Session], path: str, title: str = "Program") -> None:
    """Write a single self-contained HTML file listing every session,
    grouped by day. No external resources - safe to open, host or attach
    to an email as-is."""
    by_date: dict[str, list[Session]] = defaultdict(list)
    undated: list[Session] = []
    for s in sessions:
        if s.date.strip():
            by_date[s.date.strip()].append(s)
        else:
            undated.append(s)

    day_blocks = []
    for date_str in sorted(by_date.keys()):
        day_sessions = sorted(by_date[date_str], key=lambda s: s.time)
        rows = "".join(_session_row(s) for s in day_sessions)
        day_blocks.append(
            f'<section class="day"><h2>{_esc(_format_day_header(date_str))}</h2>'
            f'<div class="sessions">{rows}</div></section>'
        )

    if undated:
        rows = "".join(_session_row(s) for s in undated)
        day_blocks.append(
            '<section class="day"><h2>Date to be announced</h2>'
            f'<div class="sessions">{rows}</div></section>'
        )

    body = "".join(day_blocks) if day_blocks else '<p class="empty">No sessions yet.</p>'

    html_doc = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_esc(title)}</title>
<style>
  body {{ font-family: -apple-system, "Segoe UI", Helvetica, Arial, sans-serif; max-width: 760px;
          margin: 0 auto; padding: 32px 20px 64px; color: #1a1a1a; background: #ffffff; }}
  h1 {{ font-size: 28px; margin-bottom: 4px; }}
  .subtitle {{ color: #666; margin-top: 0; margin-bottom: 32px; font-size: 14px; }}
  .day {{ margin-bottom: 32px; }}
  .day h2 {{ font-size: 18px; border-bottom: 2px solid #1f2d5a; padding-bottom: 6px; color: #1f2d5a; }}
  .session {{ padding: 10px 0; border-bottom: 1px solid #eee; }}
  .session:last-child {{ border-bottom: none; }}
  .session-time {{ font-weight: 600; color: #147a8c; display: inline-block; min-width: 70px; }}
  .session-title {{ font-weight: 600; }}
  .session-title.cancelled {{ text-decoration: line-through; color: #999; }}
  .session-meta {{ color: #555; font-size: 13px; margin-top: 2px; }}
  .badge {{ display: inline-block; background: #dbe9ff; color: #1f2d5a; font-size: 11px;
            padding: 2px 8px; border-radius: 10px; margin-left: 6px; }}
  .badge.cancelled {{ background: #f8c9c9; color: #7a1f1f; }}
  .empty {{ color: #666; }}
</style>
</head>
<body>
<h1>{_esc(title)}</h1>
<p class="subtitle">Generated on {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
{body}
</body>
</html>
"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(html_doc)
