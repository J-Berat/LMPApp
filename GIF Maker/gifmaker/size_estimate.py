"""Estimate an export's output file size without doing the full export:
encode a small sample of the sequence's actual frames at the real
settings, measure that sample's size, then scale up to the full frame
count. This uses the real encoders (Pillow for GIF/WebP, ffmpeg for
MP4) so it reflects real compression, not a guessed bits-per-pixel
formula.

GIF and WebP compress each frame close to independently (palette /
still-image compression), so an evenly spaced sample across the whole
sequence scales linearly with very good accuracy. MP4 (H.264) instead
gets much of its compression from similarity between *consecutive*
frames, so it is sampled as a contiguous run from the start instead -
this tracks the real ratio far better than an evenly spaced sample,
though it can still be off by ten to twenty percent since a longer
looping sequence keeps finding more redundancy than a short prefix
does. Treat all of these as ballpark figures, not exact byte counts.
"""

from __future__ import annotations

import os
import tempfile

from .gif_exporter import export_gif
from .video_exporter import export_mp4
from .webp_exporter import export_webp

_SUFFIX = {"gif": ".gif", "webp": ".webp", "mp4": ".mp4"}
_EXPORTERS = {"gif": export_gif, "webp": export_webp, "mp4": export_mp4}

DEFAULT_SAMPLE_COUNT = 5

# For MP4, sample a contiguous prefix instead (see module docstring).
_VIDEO_SAMPLE_FRACTION = 0.25
_VIDEO_SAMPLE_MIN = 8
_VIDEO_SAMPLE_MAX = 30


def _sample_indices(n: int, sample_count: int) -> list[int]:
    """Up to `sample_count` indices evenly spaced across range(n),
    always including the first and last frame when there are enough."""
    if n <= sample_count:
        return list(range(n))
    if sample_count <= 1:
        return [0]
    step = (n - 1) / (sample_count - 1)
    return sorted({round(i * step) for i in range(sample_count)})


def _video_sample_count(n: int) -> int:
    """Contiguous prefix length to sample for an MP4 estimate."""
    target = round(n * _VIDEO_SAMPLE_FRACTION)
    return min(n, max(_VIDEO_SAMPLE_MIN, target, 1), _VIDEO_SAMPLE_MAX)


def estimate_export_size(
    image_paths: list[str],
    frame_delays: list[int] | None,
    settings,
    kind: str,
    sample_count: int = DEFAULT_SAMPLE_COUNT,
) -> int | None:
    """Estimated output size in bytes for exporting `image_paths` as
    `kind` ("gif", "webp" or "mp4") with `settings`, or None if there is
    nothing to export or the sample export fails for any reason."""
    n = len(image_paths)
    if n == 0:
        return None
    exporter = _EXPORTERS.get(kind)
    suffix = _SUFFIX.get(kind)
    if exporter is None or suffix is None:
        return None

    if kind == "mp4":
        k = _video_sample_count(n)
        indices = list(range(k))
    else:
        indices = _sample_indices(n, sample_count)

    sample_paths = [image_paths[i] for i in indices]
    sample_delays = [frame_delays[i] for i in indices] if frame_delays else None

    fd, tmp_path = tempfile.mkstemp(suffix=suffix)
    os.close(fd)
    try:
        exporter(sample_paths, tmp_path, settings, sample_delays)
        sample_size = os.path.getsize(tmp_path)
    except Exception:
        return None
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass

    scale = n / len(sample_paths)
    return round(sample_size * scale)
