"""Export the image sequence as an animated WebP (via Pillow).

WebP keeps full RGBA color instead of a 256-color palette like GIF, which
often gives a noticeably smaller file at similar or better visual
quality - a good alternative when the target doesn't specifically need
to be a .gif.
"""

from __future__ import annotations

from .model import GIFSettings
from .gif_exporter import _load_and_prepare, ExportError


def export_webp(
    image_paths: list[str],
    output_path: str,
    settings: GIFSettings,
    frame_delays: list[int] | None = None,
) -> None:
    """Export the images as an animated WebP file.

    `frame_delays`, when given, is one delay in milliseconds per frame,
    for a sequence with per-frame overrides; otherwise every frame uses
    settings.frame_delay_ms.

    Raises ExportError if the image list is empty.
    """
    if not image_paths:
        raise ExportError("Add at least one image before exporting.")

    frames = [_load_and_prepare(p, settings).convert("RGBA") for p in image_paths]

    duration = frame_delays if frame_delays is not None else settings.frame_delay_ms
    frames[0].save(
        output_path,
        format="WEBP",
        save_all=True,
        append_images=frames[1:],
        duration=duration,
        loop=settings.loop_count,
        quality=80,
        method=4,
    )
