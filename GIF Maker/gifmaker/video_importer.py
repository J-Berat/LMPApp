"""Read frames out of a video file, so the sequence editor can be seeded
from a video clip instead of only from individually-added images.

Uses the same imageio + bundled ffmpeg dependency already used to write
MP4s, so there is nothing extra to install.
"""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass

import imageio.v2 as imageio
from PIL import Image

# A hard ceiling on how many frames a single import can produce - keeps a
# mis-set sample rate / long clip from generating an enormous GIF or
# freezing the UI for minutes.
MAX_EXTRACTED_FRAMES = 600


class VideoImportError(Exception):
    """Raised when a video file cannot be read or produces no frames."""


@dataclass
class VideoInfo:
    duration_seconds: float
    fps: float
    width: int
    height: int


def probe_video(path: str) -> VideoInfo:
    """Read basic metadata (duration, fps, size) from a video file."""
    try:
        reader = imageio.get_reader(path, "ffmpeg")
    except Exception as exc:
        raise VideoImportError(f"Could not open this video: {exc}") from exc
    try:
        meta = reader.get_meta_data()
        fps = float(meta.get("fps") or 25.0)
        size = meta.get("size") or (0, 0)
        duration = float(meta.get("duration") or 0.0)
        if duration <= 0:
            # Some containers don't report duration in metadata - fall
            # back to counting frames (slower, but a rare case).
            try:
                n = reader.count_frames()
                duration = n / fps if fps > 0 else 0.0
            except Exception:
                duration = 0.0
        return VideoInfo(duration_seconds=duration, fps=fps, width=int(size[0]), height=int(size[1]))
    finally:
        reader.close()


def extract_frame_at(path: str, time_seconds: float) -> Image.Image:
    """Grab a single frame for preview purposes (e.g. the trim start)."""
    try:
        reader = imageio.get_reader(path, "ffmpeg")
    except Exception as exc:
        raise VideoImportError(f"Could not open this video: {exc}") from exc
    try:
        meta = reader.get_meta_data()
        fps = float(meta.get("fps") or 25.0)
        index = max(0, round(time_seconds * fps))
        try:
            frame = reader.get_data(index)
        except IndexError:
            try:
                frame = reader.get_data(max(0, reader.count_frames() - 1))
            except Exception as exc:
                raise VideoImportError(f"Could not read a frame from this video: {exc}") from exc
        return Image.fromarray(frame)
    finally:
        reader.close()


def extract_frames(
    path: str,
    start_seconds: float,
    end_seconds: float,
    sample_fps: float,
    crop_box: tuple[int, int, int, int] | None = None,
) -> tuple[list[str], float]:
    """Extract frames between start_seconds and end_seconds, sampled at
    sample_fps, optionally cropped to `crop_box` (left, top, right, bottom)
    in source pixel coordinates.

    Returns (list of saved PNG file paths, trimmed duration in seconds).
    Frames are written to a fresh temp directory that the OS will clean up
    eventually; the caller doesn't need to.
    """
    if end_seconds <= start_seconds:
        raise VideoImportError("The end of the clip must be after the start.")

    try:
        reader = imageio.get_reader(path, "ffmpeg")
    except Exception as exc:
        raise VideoImportError(f"Could not open this video: {exc}") from exc

    out_dir = tempfile.mkdtemp(prefix="gifmaker_video_")
    try:
        meta = reader.get_meta_data()
        source_fps = float(meta.get("fps") or 25.0)
        duration = end_seconds - start_seconds
        frame_count = min(max(1, round(duration * sample_fps)), MAX_EXTRACTED_FRAMES)
        target_times = [start_seconds + i * (duration / frame_count) for i in range(frame_count)]
        target_indices = [max(0, round(t * source_fps)) for t in target_times]

        results: list[Image.Image | None] = [None] * frame_count
        ti = 0
        last_frame = None
        for i, frame in enumerate(reader):
            last_frame = frame
            while ti < frame_count and target_indices[ti] <= i:
                img = Image.fromarray(frame)
                if crop_box is not None:
                    img = img.crop(crop_box)
                results[ti] = img
                ti += 1
            if ti >= frame_count:
                break

        if ti < frame_count and last_frame is not None:
            # The video ended before we reached every target time (e.g. a
            # slightly-off duration estimate) - repeat the last frame we
            # actually saw rather than leaving gaps.
            img = Image.fromarray(last_frame)
            if crop_box is not None:
                img = img.crop(crop_box)
            for j in range(ti, frame_count):
                results[j] = img

        saved: list[str] = []
        for order, img in enumerate(results):
            if img is None:
                continue
            out_path = os.path.join(out_dir, f"frame_{order:04d}.png")
            img.save(out_path)
            saved.append(out_path)

        if not saved:
            raise VideoImportError("No frames could be extracted from this range.")
        return saved, duration
    finally:
        reader.close()
