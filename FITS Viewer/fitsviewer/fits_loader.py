"""Load FITS files and extract what the viewer needs: the list of HDUs
(extensions), the pixel array for a chosen one (1D spectrum, 2D image or
full 3D cube), its header, and a linear WCS axis when one can be derived
- all in plain astropy/numpy, with no Qt dependency, so this module can
be tested on its own.

A cube is kept whole (never reduced to a single plane) so the viewer can
browse planes and change display settings without re-reading the file.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from astropy.io import fits


class FitsLoadError(Exception):
    """Raised when a file or an extension cannot be read."""


@dataclass
class HduInfo:
    index: int
    name: str
    kind: str  # "image", "spectrum", "cube", "table", "empty"
    shape: tuple[int, ...]


@dataclass
class FitsData:
    path: str
    hdus: list[HduInfo]
    selected_index: int
    kind: str  # "image", "spectrum" or "cube"
    array: np.ndarray  # 1D for a spectrum, 2D for an image, 3D for a cube
    header: fits.Header
    axis_values: np.ndarray | None = None  # linear WCS axis (wavelength for
    # a spectrum, or the cube's 3rd-axis coordinate); None if not derivable
    axis_unit: str | None = None  # from CUNIT1 (spectrum) / CUNIT3 (cube)
    value_unit: str | None = None  # from BUNIT


def _classify(data, header) -> str:
    ndim = getattr(data, "ndim", 0)
    if data is None:
        return "empty"
    if ndim == 2:
        return "image"
    if ndim == 1:
        return "spectrum"
    if ndim > 2:
        return "cube"
    return "table" if str(header.get("XTENSION", "")).upper() == "BINTABLE" else "empty"


def _hdu_infos(hdul) -> list[HduInfo]:
    infos = []
    for i, hdu in enumerate(hdul):
        data = hdu.data
        shape = tuple(data.shape) if data is not None else ()
        infos.append(HduInfo(index=i, name=hdu.name or f"HDU{i}", kind=_classify(data, hdu.header), shape=shape))
    return infos


def list_hdus(path: str) -> list[HduInfo]:
    """Open a FITS file just long enough to describe every extension."""
    try:
        with fits.open(path, memmap=False) as hdul:
            return _hdu_infos(hdul)
    except FitsLoadError:
        raise
    except Exception as exc:
        raise FitsLoadError(f"Could not open this FITS file: {exc}") from exc


def first_viewable_index(hdus: list[HduInfo]) -> int:
    """The first extension worth showing right after opening a file - the
    primary HDU is often empty in real-world multi-extension FITS files."""
    for info in hdus:
        if info.kind in ("image", "spectrum", "cube"):
            return info.index
    return 0


def _header_unit(header, key: str) -> str | None:
    """A header keyword's value as a non-empty stripped string, or None
    if the keyword is absent or blank."""
    if key not in header:
        return None
    text = str(header[key]).strip()
    return text or None


def _linear_axis(header, axis_num: int, length: int) -> np.ndarray | None:
    """A simple linear axis from CRVALn/CDELTn/CRPIXn - the classic FITS
    WCS convention for a single axis (n=1 for a 1D spectrum, n=3 for a
    cube's spectral axis, which is numpy axis 0 of the array). None if
    those keywords are missing, so the caller falls back to pixel index."""
    crval_key, cdelt_key, crpix_key = f"CRVAL{axis_num}", f"CDELT{axis_num}", f"CRPIX{axis_num}"
    if crval_key not in header or cdelt_key not in header:
        return None
    try:
        crval = float(header[crval_key])
        cdelt = float(header[cdelt_key])
        crpix = float(header.get(crpix_key, 1))
    except (TypeError, ValueError):
        return None
    pixels = np.arange(1, length + 1)
    return crval + (pixels - crpix) * cdelt


def load_hdu(path: str, index: int) -> FitsData:
    """Read one extension's data (in full - a cube is never reduced) and
    its header."""
    try:
        with fits.open(path, memmap=False) as hdul:
            if index < 0 or index >= len(hdul):
                raise FitsLoadError("This extension does not exist in the file.")
            hdu = hdul[index]
            data = hdu.data
            if data is None:
                raise FitsLoadError("This extension has no data.")
            header = hdu.header.copy()
            hdus = _hdu_infos(hdul)

            array = np.asarray(data)
            if array.ndim not in (1, 2, 3):
                raise FitsLoadError("This extension's data isn't a 1D spectrum, 2D image or 3D cube.")
            array = array.astype(np.float64)

            if array.ndim == 2:
                kind = "image"
            elif array.ndim == 1:
                kind = "spectrum"
            else:
                kind = "cube"

            axis_values = None
            axis_unit = None
            if kind == "spectrum":
                axis_values = _linear_axis(header, 1, array.shape[0])
                axis_unit = _header_unit(header, "CUNIT1")
            elif kind == "cube":
                axis_values = _linear_axis(header, 3, array.shape[0])
                axis_unit = _header_unit(header, "CUNIT3")
            value_unit = _header_unit(header, "BUNIT")

            return FitsData(
                path=path,
                hdus=hdus,
                selected_index=index,
                kind=kind,
                array=array,
                header=header,
                axis_values=axis_values,
                axis_unit=axis_unit,
                value_unit=value_unit,
            )
    except FitsLoadError:
        raise
    except Exception as exc:
        raise FitsLoadError(f"Could not read this extension: {exc}") from exc
