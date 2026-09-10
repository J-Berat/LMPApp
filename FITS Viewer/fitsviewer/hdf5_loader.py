"""Load HDF5 files and extract what the viewer needs: every dataset in
the file (with its shape/dtype), the array for a chosen one (as a 1D
spectrum, 2D image or full 3D cube), and its attributes - all in plain
h5py/numpy, with no Qt dependency, so this module can be tested on its
own.

A cube is kept whole (never reduced to a single plane) so the viewer can
browse planes and change display settings without re-reading the file.

HDF5 has no single standard for a spectral axis the way FITS has
CRVAL1/CDELT1, so a sibling dataset named "wavelength" (or a close
variant) whose length matches the spectrum's length, or the cube's
number of planes, is used when present, and a plain pixel/plane index
otherwise.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import h5py


class Hdf5LoadError(Exception):
    """Raised when a file or a dataset cannot be read."""


@dataclass
class DatasetInfo:
    path: str  # e.g. "/science/image"
    kind: str  # "image", "spectrum", "cube", "other"
    shape: tuple[int, ...]
    dtype: str


@dataclass
class Hdf5Data:
    path: str  # file path on disk
    datasets: list[DatasetInfo]
    selected_path: str  # dataset path inside the file
    kind: str  # "image", "spectrum" or "cube"
    array: np.ndarray  # 1D for a spectrum, 2D for an image, 3D for a cube
    attributes: dict[str, str]
    axis_values: np.ndarray | None = None  # linear axis (wavelength for a
    # spectrum, or the cube's 1st-axis coordinate); None if not derivable
    axis_unit: str | None = None  # from a "units"/"unit" attr on that axis dataset
    value_unit: str | None = None  # from a "units"/"unit" attr on the dataset itself


_WAVELENGTH_NAMES = {"wavelength", "wavelengths", "wave", "lambda"}


def _classify(shape: tuple[int, ...]) -> str:
    ndim = len(shape)
    if ndim == 2:
        return "image"
    if ndim == 1:
        return "spectrum"
    if ndim > 2:
        return "cube"
    return "other"  # a scalar or an unsupported (e.g. compound) dataset


def _walk_datasets(h5file) -> list[DatasetInfo]:
    infos: list[DatasetInfo] = []

    def visit(name, obj):
        if isinstance(obj, h5py.Dataset):
            infos.append(
                DatasetInfo(path="/" + name, kind=_classify(obj.shape), shape=tuple(obj.shape), dtype=str(obj.dtype))
            )

    h5file.visititems(visit)
    return infos


def list_datasets(path: str) -> list[DatasetInfo]:
    """Open a file just long enough to describe every dataset in it."""
    try:
        with h5py.File(path, "r") as f:
            return _walk_datasets(f)
    except Hdf5LoadError:
        raise
    except Exception as exc:
        raise Hdf5LoadError(f"Could not open this HDF5 file: {exc}") from exc


def first_viewable_path(datasets: list[DatasetInfo]) -> str | None:
    """The first dataset worth showing right after opening a file."""
    for info in datasets:
        if info.kind in ("image", "spectrum", "cube"):
            return info.path
    return datasets[0].path if datasets else None


def _stringify_attr(value) -> str:
    if isinstance(value, bytes):
        try:
            return value.decode("utf-8", errors="replace")
        except Exception:
            return repr(value)
    if isinstance(value, np.ndarray):
        return np.array2string(value, threshold=20)
    return str(value)


def _attr_unit(obj) -> str | None:
    """A "units"/"unit" attribute on a dataset (any capitalization), if
    present and non-empty - HDF5 has no single standard attribute name
    for this the way FITS has BUNIT/CUNITn."""
    for key in ("units", "unit", "Units", "Unit", "UNITS", "UNIT"):
        if key in obj.attrs:
            text = _stringify_attr(obj.attrs[key]).strip()
            if text:
                return text
    return None


def _find_axis_values(group, dataset_name: str, length: int) -> tuple[np.ndarray, str | None] | None:
    """A sibling 1D dataset that looks like a wavelength/spectral axis by
    name and matches the given length (a spectrum's length, or a cube's
    number of planes), along with its unit if it has one."""
    for key in group.keys():
        if key == dataset_name or key.lower() not in _WAVELENGTH_NAMES:
            continue
        try:
            candidate = group[key]
        except Exception:
            continue
        if isinstance(candidate, h5py.Dataset) and candidate.ndim == 1 and candidate.shape[0] == length:
            values = np.asarray(candidate[()], dtype=np.float64)
            return values, _attr_unit(candidate)
    return None


def load_dataset(path: str, dataset_path: str) -> Hdf5Data:
    """Read one dataset's array (in full - a cube is never reduced) and
    its attributes. `dataset_path` is the "/group/name" path inside the
    file."""
    key = dataset_path.lstrip("/")
    try:
        with h5py.File(path, "r") as f:
            if key not in f or not isinstance(f[key], h5py.Dataset):
                raise Hdf5LoadError("This dataset does not exist in the file.")

            datasets = _walk_datasets(f)
            dset = f[key]
            data = dset[()]

            attributes = {k: _stringify_attr(v) for k, v in dset.attrs.items()}
            for k, v in f.attrs.items():
                attributes.setdefault(f"(file) {k}", _stringify_attr(v))

            array = np.asarray(data)
            if array.ndim not in (1, 2, 3):
                raise Hdf5LoadError("This dataset isn't a 1D spectrum, 2D image or 3D cube.")
            array = array.astype(np.float64)

            if array.ndim == 2:
                kind = "image"
            elif array.ndim == 1:
                kind = "spectrum"
            else:
                kind = "cube"

            axis_values = None
            axis_unit = None
            if kind in ("spectrum", "cube"):
                if "/" in key:
                    group_name, dataset_name = key.rsplit("/", 1)
                    group = f[group_name]
                else:
                    group, dataset_name = f, key
                found = _find_axis_values(group, dataset_name, array.shape[0])
                if found is not None:
                    axis_values, axis_unit = found
            value_unit = _attr_unit(dset)

            return Hdf5Data(
                path=path,
                datasets=datasets,
                selected_path="/" + key,
                kind=kind,
                array=array,
                attributes=attributes,
                axis_values=axis_values,
                axis_unit=axis_unit,
                value_unit=value_unit,
            )
    except Hdf5LoadError:
        raise
    except Exception as exc:
        raise Hdf5LoadError(f"Could not read this dataset: {exc}") from exc
