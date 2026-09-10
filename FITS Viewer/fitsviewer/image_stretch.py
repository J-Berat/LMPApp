"""Map a raw pixel array to [0, 1] for display: an interval picks the
black/white points, a stretch applies the tone curve - the same two-step
model DS9 and most astro viewers use for "scale". Pure numpy/astropy
(the interval/stretch classes, not astropy's mpl_normalize.ImageNormalize,
which pulls in matplotlib - a dependency this app doesn't otherwise
need), so this module can be tested without a display.
"""

from __future__ import annotations

import numpy as np
from astropy.visualization import (
    MinMaxInterval,
    PercentileInterval,
    ZScaleInterval,
    LinearStretch,
    SqrtStretch,
    LogStretch,
    AsinhStretch,
)

STRETCHES = {
    "Linear": LinearStretch,
    "Sqrt": SqrtStretch,
    "Log": LogStretch,
    "Asinh": AsinhStretch,
}

class SymmetricInterval:
    """A ZScale-derived range, forced symmetric around zero - the
    natural choice when pairing a diverging colormap with signed data
    (Stokes Q/U, a residual, a velocity field), so the neutral (white)
    color always lands exactly on zero regardless of how skewed the
    data's actual min/max happen to be."""

    def get_limits(self, array):
        vmin, vmax = ZScaleInterval().get_limits(array)
        bound = max(abs(vmin), abs(vmax))
        if bound == 0:
            bound = 1.0
        return -bound, bound


INTERVALS = {
    "ZScale": ZScaleInterval,
    "MinMax": MinMaxInterval,
    "99.5%": lambda: PercentileInterval(99.5),
    "99%": lambda: PercentileInterval(99.0),
    "98%": lambda: PercentileInterval(98.0),
    "Symmetric (0-centered)": SymmetricInterval,
}

# Hand-picked anchor colors (0-255 RGB, at positions 0-1) for a small set
# of standard colormaps, defined here instead of fetched from matplotlib
# (which this app does not otherwise depend on, and which pyqtgraph's
# getFromMatplotlib() silently falls back away from when matplotlib
# isn't installed - the actual cause of the colormap picker appearing to
# do nothing). This makes the picker work identically on every machine.
COLORMAP_STOPS: dict[str, list[tuple[float, tuple[int, int, int]]]] = {
    "gray": [(0.0, (0, 0, 0)), (1.0, (255, 255, 255))],
    "viridis": [
        (0.00, (68, 1, 84)),
        (0.25, (59, 82, 139)),
        (0.50, (33, 145, 140)),
        (0.75, (94, 201, 98)),
        (1.00, (253, 231, 37)),
    ],
    "plasma": [
        (0.00, (13, 8, 135)),
        (0.25, (126, 3, 168)),
        (0.50, (204, 71, 120)),
        (0.75, (248, 149, 64)),
        (1.00, (240, 249, 33)),
    ],
    "inferno": [
        (0.00, (0, 0, 4)),
        (0.25, (87, 16, 110)),
        (0.50, (188, 55, 84)),
        (0.75, (249, 142, 9)),
        (1.00, (252, 255, 164)),
    ],
    "magma": [
        (0.00, (0, 0, 4)),
        (0.25, (81, 18, 124)),
        (0.50, (183, 55, 121)),
        (0.75, (252, 137, 97)),
        (1.00, (252, 253, 191)),
    ],
    "cividis": [
        (0.00, (0, 32, 76)),
        (0.25, (63, 73, 108)),
        (0.50, (126, 118, 123)),
        (0.75, (200, 168, 100)),
        (1.00, (255, 234, 70)),
    ],
    "hot": [
        (0.00, (0, 0, 0)),
        (0.365, (255, 0, 0)),
        (0.746, (255, 255, 0)),
        (1.00, (255, 255, 255)),
    ],
    "cool": [
        (0.00, (0, 255, 255)),
        (1.00, (255, 0, 255)),
    ],
    # Diverging colormaps: for data with a meaningful zero-point (Stokes
    # parameters, residuals, velocity fields) - pair these with the
    # "Symmetric (0-centered)" interval above so the neutral color
    # actually lands on the value that means "no signal".
    "RdBu": [
        (0.00, (103, 0, 31)),
        (0.25, (214, 96, 77)),
        (0.50, (247, 247, 247)),
        (0.75, (67, 147, 195)),
        (1.00, (5, 48, 97)),
    ],
    "bwr": [
        (0.00, (0, 0, 255)),
        (0.50, (255, 255, 255)),
        (1.00, (255, 0, 0)),
    ],
    "seismic": [
        (0.00, (0, 0, 77)),
        (0.25, (0, 0, 255)),
        (0.50, (255, 255, 255)),
        (0.75, (255, 0, 0)),
        (1.00, (128, 0, 0)),
    ],
    "coolwarm": [
        (0.00, (59, 76, 192)),
        (0.25, (124, 159, 249)),
        (0.50, (221, 221, 221)),
        (0.75, (239, 138, 98)),
        (1.00, (180, 4, 38)),
    ],
}

COLORMAPS = list(COLORMAP_STOPS.keys())

DEFAULT_STRETCH = "Linear"
DEFAULT_INTERVAL = "ZScale"
DEFAULT_COLORMAP = "gray"


def normalize_array(array: np.ndarray, stretch_name: str, interval_name: str) -> np.ndarray:
    """Return a copy of `array` mapped to [0, 1], safe against NaN/Inf and
    against a fully flat (or empty-of-finite-values) array."""
    finite = array[np.isfinite(array)]
    if finite.size == 0:
        return np.zeros_like(array, dtype=np.float64)

    vmin_all, vmax_all = float(np.min(finite)), float(np.max(finite))
    if vmin_all == vmax_all:
        # A flat image: nothing to stretch - return a flat mid-gray
        # rather than dividing by a zero range.
        return np.full_like(array, 0.5, dtype=np.float64)

    clean = np.where(np.isfinite(array), array, vmin_all)

    interval = INTERVALS.get(interval_name, ZScaleInterval)()
    try:
        vmin, vmax = interval.get_limits(clean)
    except Exception:
        # A pathological interval (e.g. ZScale on an unusual distribution)
        # falls back to plain min/max rather than crashing.
        vmin, vmax = vmin_all, vmax_all
    if vmin == vmax:
        vmin, vmax = vmin_all, vmax_all

    scaled = np.clip((clean - vmin) / (vmax - vmin), 0.0, 1.0)
    stretch = STRETCHES.get(stretch_name, LinearStretch)()
    out = stretch(scaled)
    return np.clip(np.asarray(out, dtype=np.float64), 0.0, 1.0)


def manual_interval_bounds(array: np.ndarray) -> tuple[float, float]:
    """Sensible default (min, max) bounds to seed a manual-limits UI."""
    finite = array[np.isfinite(array)]
    if finite.size == 0:
        return (0.0, 1.0)
    return (float(np.min(finite)), float(np.max(finite)))
