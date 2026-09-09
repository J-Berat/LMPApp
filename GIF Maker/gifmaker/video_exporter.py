"""Export de la séquence d'images en vidéo MP4 (via imageio + ffmpeg embarqué).

Utilise imageio-ffmpeg, qui télécharge/embarque un binaire ffmpeg indépendant
du système : le rendu MP4 fonctionne de la même façon sur macOS, Windows et
Linux sans installation supplémentaire.
"""

from __future__ import annotations

import numpy as np
import imageio.v2 as imageio
from PIL import Image, ImageOps

from .model import GIFSettings
from .gif_exporter import ExportError


def _load_frame_array(path: str, settings: GIFSettings, target_size: tuple[int, int] | None) -> np.ndarray:
    img = Image.open(path)
    img = ImageOps.exif_transpose(img)
    img = img.convert("RGB")

    if settings.resize_enabled:
        target_w = max(1, settings.resize_width)
        target_h = max(1, settings.resize_height)
        if settings.keep_aspect_ratio:
            img.thumbnail((target_w, target_h), Image.LANCZOS)
        else:
            img = img.resize((target_w, target_h), Image.LANCZOS)
    elif target_size is not None:
        img = img.resize(target_size, Image.LANCZOS)

    return np.asarray(img)


def _even(n: int) -> int:
    # Les encodeurs H.264 exigent des dimensions paires.
    return n if n % 2 == 0 else n + 1


def export_mp4(image_paths: list[str], output_path: str, settings: GIFSettings) -> None:
    """Exporte les images en vidéo MP4 (H.264)."""
    if not image_paths:
        raise ExportError("Ajoutez au moins une image avant d'exporter.")

    # Détermine la taille cible à partir de la première image si aucun
    # redimensionnement n'est demandé, pour que toutes les frames soient
    # homogènes (obligatoire pour l'encodage vidéo).
    first = Image.open(image_paths[0])
    first = ImageOps.exif_transpose(first).convert("RGB")
    if settings.resize_enabled:
        base_size = None
    else:
        base_size = (_even(first.width), _even(first.height))

    frames = []
    for path in image_paths:
        arr = _load_frame_array(path, settings, base_size)
        h, w = arr.shape[0], arr.shape[1]
        eh, ew = _even(h), _even(w)
        if (eh, ew) != (h, w):
            padded = np.zeros((eh, ew, 3), dtype=arr.dtype)
            padded[:h, :w] = arr
            arr = padded
        frames.append(arr)

    # Toutes les frames doivent avoir la même taille pour l'encodeur vidéo.
    ref_shape = frames[0].shape
    for i, arr in enumerate(frames):
        if arr.shape != ref_shape:
            img = Image.fromarray(arr).resize((ref_shape[1], ref_shape[0]), Image.LANCZOS)
            frames[i] = np.asarray(img.convert("RGB"))

    fps = settings.fps
    writer = imageio.get_writer(
        output_path,
        format="FFMPEG",
        mode="I",
        fps=fps,
        codec="libx264",
        quality=None,
        pixelformat="yuv420p",
        macro_block_size=None,
        output_params=["-movflags", "+faststart"],
    )
    try:
        for arr in frames:
            writer.append_data(arr)
    finally:
        writer.close()
