"""Batch-convert several video files to GIF/MP4/WebP using one shared set
of trim/sample-rate/speed/crop and export settings - the "process many
videos the same way" counterpart of exporting one edited sequence."""

from __future__ import annotations

import dataclasses
import os
import shutil
from dataclasses import dataclass
from typing import Callable

from .model import GIFSettings, build_ping_pong_sequence
from .video_importer import extract_frames, probe_video, VideoImportError
from .gif_exporter import export_gif
from .video_exporter import export_mp4
from .webp_exporter import export_webp

EXPORTERS: dict[str, Callable[[list[str], str, GIFSettings], None]] = {
    "gif": export_gif,
    "mp4": export_mp4,
    "webp": export_webp,
}
EXTENSIONS = {"gif": ".gif", "mp4": ".mp4", "webp": ".webp"}


@dataclass
class BatchItemResult:
    video_path: str
    output_paths: list[str]
    error: str | None = None


def unique_path(path: str) -> str:
    """Avoid silently overwriting a file already in the output folder by
    appending " (2)", " (3)", etc. before the extension."""
    if not os.path.exists(path):
        return path
    base, ext = os.path.splitext(path)
    n = 2
    while os.path.exists(f"{base} ({n}){ext}"):
        n += 1
    return f"{base} ({n}){ext}"


def process_video(
    video_path: str,
    output_dir: str,
    formats: list[str],
    base_settings: GIFSettings,
    trim_start: float | None,
    trim_end: float | None,
    sample_fps: int,
    speed: float,
    crop_norm: tuple[float, float, float, float] | None,
) -> BatchItemResult:
    """Extract frames from one video and export it in every requested
    format, sharing the same trim/speed/crop and GIFSettings. Returns a
    result describing what was written, or the error that stopped this
    file, so one bad file doesn't abort the rest of the batch."""
    frame_dir: str | None = None
    try:
        info = probe_video(video_path)
        duration = max(0.0, info.duration_seconds)
        start = 0.0 if trim_start is None else max(0.0, min(trim_start, duration))
        end = duration if trim_end is None else max(0.0, min(trim_end, duration))
        if end <= start:
            start, end = 0.0, duration

        crop_box = None
        if crop_norm is not None:
            x0, y0, x1, y1 = crop_norm
            crop_box = (
                max(0, round(x0 * info.width)),
                max(0, round(y0 * info.height)),
                min(info.width, round(x1 * info.width)),
                min(info.height, round(y1 * info.height)),
            )

        frame_paths, clip_duration = extract_frames(video_path, start, end, sample_fps, crop_box=crop_box)
        frame_dir = os.path.dirname(frame_paths[0]) if frame_paths else None

        output_duration = clip_duration / speed if speed > 0 else clip_duration
        frame_count = len(frame_paths)
        delay_ms = (
            max(20, round((output_duration * 1000) / frame_count)) if frame_count else base_settings.frame_delay_ms
        )

        settings = dataclasses.replace(base_settings, frame_delay_ms=delay_ms)
        sequence = build_ping_pong_sequence(frame_paths) if settings.ping_pong else frame_paths

        stem = os.path.splitext(os.path.basename(video_path))[0]
        outputs = []
        for fmt in formats:
            out_path = unique_path(os.path.join(output_dir, stem + EXTENSIONS[fmt]))
            EXPORTERS[fmt](sequence, out_path, settings)
            outputs.append(out_path)
        return BatchItemResult(video_path=video_path, output_paths=outputs)
    except VideoImportError as exc:
        return BatchItemResult(video_path=video_path, output_paths=[], error=str(exc))
    except Exception as exc:  # pragma: no cover - safety net, one file must not abort the batch
        return BatchItemResult(video_path=video_path, output_paths=[], error=str(exc))
    finally:
        if frame_dir:
            shutil.rmtree(frame_dir, ignore_errors=True)


def process_videos(
    video_paths: list[str],
    output_dir: str,
    formats: list[str],
    base_settings: GIFSettings,
    trim_start: float | None,
    trim_end: float | None,
    sample_fps: int,
    speed: float,
    crop_norm: tuple[float, float, float, float] | None,
    progress_callback: Callable[[int, int, BatchItemResult], None] | None = None,
) -> list[BatchItemResult]:
    """Process every video in turn, reporting (done, total, result) via
    `progress_callback` as each one finishes."""
    results = []
    total = len(video_paths)
    for i, path in enumerate(video_paths):
        result = process_video(
            path, output_dir, formats, base_settings, trim_start, trim_end, sample_fps, speed, crop_norm,
        )
        results.append(result)
        if progress_callback:
            progress_callback(i + 1, total, result)
    return results
