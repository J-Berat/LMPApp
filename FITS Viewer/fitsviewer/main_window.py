"""PySide6 graphical interface for FITS Viewer."""

from __future__ import annotations

import os
import sys

import numpy as np

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QComboBox,
    QFileDialog,
    QMessageBox,
    QStackedWidget,
    QSplitter,
    QStatusBar,
)

from .fits_loader import list_hdus, load_hdu, first_viewable_index, FitsLoadError
from .hdf5_loader import list_datasets, load_dataset, first_viewable_path, Hdf5LoadError
from .image_view import ImageView
from .spectrum_view import SpectrumView
from .cube_view import CubeView
from .header_view import HeaderView
from .compare_window import CompareWindow

FITS_EXTENSIONS = (".fits", ".fit", ".fts", ".fits.gz", ".fit.gz")
HDF5_EXTENSIONS = (".h5", ".hdf5", ".he5")


def _file_kind(path: str) -> str | None:
    lower = path.lower()
    if lower.endswith(FITS_EXTENSIONS):
        return "fits"
    if lower.endswith(HDF5_EXTENSIONS):
        return "hdf5"
    return None


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("FITS Viewer")
        self.resize(1150, 720)
        self.setAcceptDrops(True)

        self.current_path: str | None = None
        self.file_kind: str | None = None  # "fits" or "hdf5"

        self.open_button = QPushButton("Open FITS or HDF5…")
        self.open_button.clicked.connect(self._choose_file)

        self.compare_button = QPushButton("Compare files…")
        self.compare_button.setToolTip("Open several FITS/HDF5 files side by side and overlay their spectra")
        self.compare_button.clicked.connect(self._open_compare_window)
        self._compare_window: CompareWindow | None = None

        self.item_label = QLabel("Extension:")
        self.item_combo = QComboBox()
        self.item_combo.setMinimumWidth(280)
        self.item_combo.currentIndexChanged.connect(self._load_selected_item)
        self.item_combo.setEnabled(False)

        self.info_label = QLabel('Drag & drop a FITS or HDF5 file here, or use "Open FITS or HDF5…".')
        self.info_label.setWordWrap(True)
        self.info_label.setStyleSheet("padding: 4px 2px; color: #444444;")

        top_row = QHBoxLayout()
        top_row.addWidget(self.open_button)
        top_row.addWidget(self.compare_button)
        top_row.addWidget(self.item_label)
        top_row.addWidget(self.item_combo)
        top_row.addStretch(1)

        self.image_view = ImageView()
        self.spectrum_view = SpectrumView()
        self.cube_view = CubeView()
        self.empty_label = QLabel("Nothing to show yet.")
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.empty_label.setStyleSheet("color: #888888; font-size: 14px;")

        self.stack = QStackedWidget()
        self.stack.addWidget(self.empty_label)
        self.stack.addWidget(self.image_view)
        self.stack.addWidget(self.spectrum_view)
        self.stack.addWidget(self.cube_view)

        self.header_view = HeaderView()

        splitter = QSplitter()
        splitter.addWidget(self.stack)
        splitter.addWidget(self.header_view)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.addLayout(top_row)
        layout.addWidget(self.info_label)
        layout.addWidget(splitter, 1)
        self.setCentralWidget(central)

        self.setStatusBar(QStatusBar())

    # -- Drag & drop onto the window --------------------------------------------------

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        paths = [url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()]
        supported = [p for p in paths if _file_kind(p) is not None]
        if supported:
            self.open_file(supported[0])
        elif paths:
            QMessageBox.information(self, "Unsupported file", "Drop a .fits/.fit/.fts or .h5/.hdf5 file.")

    # -- Opening files -------------------------------------------------------------------

    def _open_compare_window(self) -> None:
        if self._compare_window is None:
            self._compare_window = CompareWindow()
        self._compare_window.show()
        self._compare_window.raise_()
        self._compare_window.activateWindow()

    def _choose_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open a FITS or HDF5 file",
            "",
            "FITS or HDF5 files (*.fits *.fit *.fts *.fits.gz *.fit.gz *.h5 *.hdf5 *.he5);;"
            "FITS files (*.fits *.fit *.fts *.fits.gz *.fit.gz);;"
            "HDF5 files (*.h5 *.hdf5 *.he5);;All files (*)",
        )
        if path:
            self.open_file(path)

    def open_file(self, path: str) -> None:
        kind = _file_kind(path)
        if kind is None:
            QMessageBox.warning(self, "Unsupported file", "This isn't a recognized FITS or HDF5 file.")
            return

        try:
            if kind == "fits":
                entries = list_hdus(path)
                labels_and_keys = [
                    (f"[{info.index}] {info.name} — {info.kind} ({self._shape_text(info.shape)})", info.index)
                    for info in entries
                ]
                start_key = first_viewable_index(entries)
            else:
                entries = list_datasets(path)
                labels_and_keys = [
                    (f"{info.path} — {info.kind} ({self._shape_text(info.shape)}, {info.dtype})", info.path)
                    for info in entries
                ]
                start_key = first_viewable_path(entries)
        except (FitsLoadError, Hdf5LoadError) as exc:
            QMessageBox.critical(self, "Cannot open file", str(exc))
            return

        if not entries:
            QMessageBox.warning(self, "Empty file", "This file has no datasets/extensions.")
            return

        self.current_path = path
        self.file_kind = kind
        self.item_label.setText("Extension:" if kind == "fits" else "Dataset:")

        self.item_combo.blockSignals(True)
        self.item_combo.clear()
        for label, key in labels_and_keys:
            self.item_combo.addItem(label, key)
        self.item_combo.setEnabled(len(entries) > 1)
        self.item_combo.blockSignals(False)

        position = self.item_combo.findData(start_key)
        self.item_combo.setCurrentIndex(max(0, position))
        self._load_selected_item()

    @staticmethod
    def _shape_text(shape: tuple[int, ...]) -> str:
        return "×".join(str(d) for d in shape) if shape else "empty"

    def _load_selected_item(self) -> None:
        if self.current_path is None or self.item_combo.count() == 0:
            return
        key = self.item_combo.currentData()
        try:
            if self.file_kind == "fits":
                data = load_hdu(self.current_path, key)
                self.header_view.set_header(data.header)
                selected_label = f"extension [{data.selected_index}]"
            else:
                data = load_dataset(self.current_path, key)
                self.header_view.set_attributes(data.attributes)
                selected_label = f"dataset {data.selected_path}"
        except (FitsLoadError, Hdf5LoadError) as exc:
            QMessageBox.critical(self, "Cannot read this item", str(exc))
            return

        if data.kind == "image":
            self.image_view.set_array(data.array)
            self.stack.setCurrentWidget(self.image_view)
        elif data.kind == "cube":
            self.cube_view.set_cube(data.array, data.axis_values, data.axis_unit, data.value_unit)
            self.stack.setCurrentWidget(self.cube_view)
        else:
            self.spectrum_view.set_spectrum(
                data.array, data.axis_values, x_unit=data.axis_unit, y_unit=data.value_unit
            )
            self.stack.setCurrentWidget(self.spectrum_view)

        self.info_label.setText(
            f"{os.path.basename(self.current_path)} — {selected_label} — "
            f"{data.kind}, shape {tuple(data.array.shape)}"
        )

        finite = data.array[np.isfinite(data.array)]
        if finite.size:
            stats = f"min={finite.min():.4g}   max={finite.max():.4g}   mean={finite.mean():.4g}"
        else:
            stats = "no finite values"
        self.statusBar().showMessage(f"{self.current_path}    —    {stats}")


def run() -> None:
    app = QApplication.instance() or QApplication([])
    app.setApplicationName("FITS Viewer")
    icon_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "AppIcon.png")
    if os.path.isfile(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    window = MainWindow()
    window.show()
    if len(sys.argv) > 1 and os.path.isfile(sys.argv[1]):
        window.open_file(sys.argv[1])
    app.exec()


if __name__ == "__main__":
    run()
