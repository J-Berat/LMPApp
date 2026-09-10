"""Export the image sequence as an animated GIF (via Pillow)."""

from __future__ import annotations

from PIL import Image, ImageOps

from .model import GIFSettings
from .text_overlay import apply_text_overlay


class ExportError(Exception):
    """Raised when the export cannot be performed."""


def _load_and_prepare(path: str, settings: GIFSettings) -> Image.Image:
    img = Image.open(path)
    img = ImageOps.exif_transpose(img)  # respect EXIF orientation
    img = img.convert("RGBA")

    if settings.resize_enabled:
        target_w = max(1, settings.resize_width)
        target_h = max(1, settings.resize_height)
        if settings.keep_aspect_ratio:
            img.thumbnail((target_w, target_h), Image.LANCZOS)
        else:
            img = img.resize((target_w, target_h), Image.LANCZOS)

    if settings.overlay_text.strip():
        img = apply_text_overlay(img, settings)

    return img


def export_gif(
    image_paths: list[str],
    output_path: str,
    settings: GIFSettings,
    frame_delays: list[int] | None = None,
) -> None:
    """Export the images as an animated GIF.

    `frame_delays`, when given, is one delay in milliseconds per frame
    (Pillow accepts a list here just like a single duration), for a
    sequence with per-frame overrides; otherwise every frame uses
    settings.frame_delay_ms.

    Raises ExportError if the image list is empty.
    """
    if not image_paths:
        raise ExportError("Add at least one image before exporting.")

    frames = [_load_and_prepare(p, settings) for p in image_paths]

    colors = max(2, min(256, settings.color_count))
    dither = Image.FLOYDSTEINBERG if settings.dither else Image.NONE
    # A shared palette avoids color flicker between frames.
    converted = [f.convert("P", palette=Image.ADAPTIVE, colors=colors, dither=dither) for f in frames]

    duration = frame_delays if frame_delays is not None else settings.frame_delay_ms
    converted[0].save(
        output_path,
        format="GIF",
        save_all=True,
        append_images=converted[1:],
        duration=duration,
        loop=settings.loop_count,
        disposal=2,
        optimize=False,
    )
