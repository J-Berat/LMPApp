"""Burn a text caption or watermark into a single frame.

Shared by the GIF, MP4 and WebP exporters so the same setting produces
the same look regardless of output format.
"""

from __future__ import annotations

from PIL import Image, ImageDraw, ImageFont

from .model import GIFSettings

_MARGIN_RATIO = 0.25  # margin from the edge, as a fraction of the font size


def _load_font(size: int) -> ImageFont.ImageFont:
    size = max(8, size)
    try:
        # Pillow >= 10.1: a real scalable bitmap font (Aileron, bundled
        # with Pillow) instead of the tiny fixed-size default.
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    hex_color = (hex_color or "").strip().lstrip("#")
    if len(hex_color) != 6:
        return (255, 255, 255)
    try:
        return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return (255, 255, 255)


def _anchor_position(
    position: str, canvas_size: tuple[int, int], text_size: tuple[int, int], margin: int
) -> tuple[int, int]:
    cw, ch = canvas_size
    tw, th = text_size
    positions = {
        "top-left": (margin, margin),
        "top-right": (cw - tw - margin, margin),
        "bottom-left": (margin, ch - th - margin),
        "bottom-right": (cw - tw - margin, ch - th - margin),
        "center": ((cw - tw) // 2, (ch - th) // 2),
    }
    return positions.get(position, positions["bottom-right"])


def apply_text_overlay(img: Image.Image, settings: GIFSettings) -> Image.Image:
    """Return a copy of `img` with settings.overlay_text drawn on top, in
    the same mode as the input. A no-op (returns `img` unchanged) if the
    overlay text is blank."""
    text = (settings.overlay_text or "").strip()
    if not text:
        return img

    original_mode = img.mode
    base = img.convert("RGBA")
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)

    font = _load_font(settings.overlay_font_size)
    bbox = draw.textbbox((0, 0), text, font=font)
    text_size = (bbox[2] - bbox[0], bbox[3] - bbox[1])
    margin = max(4, round(settings.overlay_font_size * _MARGIN_RATIO))
    x, y = _anchor_position(settings.overlay_position, base.size, text_size, margin)

    alpha = max(0, min(255, round(settings.overlay_opacity * 255)))
    r, g, b = _hex_to_rgb(settings.overlay_color)

    # A dark outline keeps the text legible over any background color,
    # which matters most for a watermark placed over unpredictable footage.
    outline_alpha = min(255, alpha + 60)
    origin = (x - bbox[0], y - bbox[1])
    for dx, dy in ((-1, -1), (-1, 1), (1, -1), (1, 1), (0, -1), (0, 1), (-1, 0), (1, 0)):
        draw.text((origin[0] + dx, origin[1] + dy), text, font=font, fill=(0, 0, 0, outline_alpha))
    draw.text(origin, text, font=font, fill=(r, g, b, alpha))

    combined = Image.alpha_composite(base, layer)
    return combined if original_mode == "RGBA" else combined.convert(original_mode)
