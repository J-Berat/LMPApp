"""Export the image sequence as an MP4 video (via imageio + bundled ffmpeg).

Uses imageio-ffmpeg, which bundles a standalone ffmpeg binary that does not
depend on the system: MP4 rendering works the same way on macOS, Windows
and Linux with no extra installation.
"""

from __future__ import annotations

import numpy as np
import imageio.v2 as imageio
from PIL import Image, ImageOps

from .model import GIFSettings
from .gif_exporter import ExportError
from .text_overlay import apply_text_overlay


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

    if settings.overlay_text.strip():
        img = apply_text_overlay(img, settings)

    return np.asarray(img)


def _even(n: int) -> int:
    # H.264 encoders require even dimensions.
    return n if n % 2 == 0 else n + 1


def export_mp4(
    image_paths: list[str],
    output_path: str,
    settings: GIFSettings,
    frame_delays: list[int] | None = None,
) -> None:
    """Export the images as an MP4 video (H.264).

    A video encodes at one fixed frame rate (settings.fps, from
    settings.frame_delay_ms), unlike a GIF/WebP which can hold each
    frame for its own duration. `frame_delays`, when given, approximates
    per-frame overrides by repeating a frame enough times at that fixed
    rate to match its held duration - e.g. a frame held for 3x as long
    as settings.frame_delay_ms is written 3 times in a row.
    """
    if not image_paths:
        raise ExportError("Add at least one image before exporting.")

    # Determine the target size from the first image when no resizing is
    # requested, so all frames end up with matching dimensions (required
    # for video encoding).
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

    # All frames must share the same size for the video encoder.
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
        for i, arr in enumerate(frames):
            repeat = 1
            if frame_delays is not None and i < len(frame_delays):
                repeat = max(1, round(frame_delays[i] / 1000.0 * fps))
            for _ in range(repeat):
                writer.append_data(arr)
    finally:
        writer.close()
