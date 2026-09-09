"""Export de la séquence d'images en GIF animé (via Pillow)."""

from __future__ import annotations

from PIL import Image, ImageOps

from .model import GIFSettings


class ExportError(Exception):
    """Erreur levée lorsque l'export ne peut pas être réalisé."""


def _load_and_prepare(path: str, settings: GIFSettings) -> Image.Image:
    img = Image.open(path)
    img = ImageOps.exif_transpose(img)  # respecte l'orientation EXIF
    img = img.convert("RGBA")

    if settings.resize_enabled:
        target_w = max(1, settings.resize_width)
        target_h = max(1, settings.resize_height)
        if settings.keep_aspect_ratio:
            img.thumbnail((target_w, target_h), Image.LANCZOS)
        else:
            img = img.resize((target_w, target_h), Image.LANCZOS)

    return img


def export_gif(image_paths: list[str], output_path: str, settings: GIFSettings) -> None:
    """Exporte les images en GIF animé.

    Lève ExportError si la liste d'images est vide.
    """
    if not image_paths:
        raise ExportError("Ajoutez au moins une image avant d'exporter.")

    frames = [_load_and_prepare(p, settings) for p in image_paths]

    # Une palette commune évite les scintillements de couleurs entre les frames.
    converted = [f.convert("P", palette=Image.ADAPTIVE, colors=256) for f in frames]

    converted[0].save(
        output_path,
        format="GIF",
        save_all=True,
        append_images=converted[1:],
        duration=settings.frame_delay_ms,
        loop=settings.loop_count,
        disposal=2,
        optimize=False,
    )
