"""Export the image sequence as an animated WebP (via Pillow).

WebP keeps full RGBA color instead of a 256-color palette like GIF, which
often gives a noticeably smaller file at similar or better visual
quality - a good alternative when the target doesn't specifically need
to be a .gif.
"""

from __future__ import annotations

from .model import GIFSettings
from .gif_exporter import _load_and_prepare, ExportError


def export_webp(image_paths: list[str], output_path: str, settings: GIFSettings) -> None:
    """Export the images as an animated WebP file.

    Raises ExportError if the image list is empty.
    """
    if not image_paths:
        raise ExportError("Add at least one image before exporting.")

    frames = [_load_and_prepare(p, settings).convert("RGBA") for p in image_paths]

    frames[0].save(
        output_path,
        format="WEBP",
        save_all=True,
        append_images=frames[1:],
        duration=settings.frame_delay_ms,
        loop=settings.loop_count,
        quality=80,
        method=4,
    )
