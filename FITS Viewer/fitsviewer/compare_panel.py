"""One loaded file in Compare mode: its own open button + extension/dataset
picker, image view, plane slider (for a cube), and a crosshair that the
window can move (from a linked click on another panel) or that can be
locked in place with its own checkbox so it stops reacting to clicks
entirely - independently of every other panel."""

from __future__ import annotations

import os

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QComboBox,
    QCheckBox,
    QSlider,
    QSpinBox,
    QFileDialog,
    QMessageBox,
    QStackedWidget,
)

from .fits_loader import list_hdus, load_hdu, first_viewable_index, FitsLoadError
from .hdf5_loader import list_datasets, load_dataset, first_viewable_path, Hdf5LoadError
from .image_view import ImageView

FITS_EXTENSIONS = (".fits", ".fit", ".fts", ".fits.gz", ".fit.gz")
HDF5_EXTENSIONS = (".h5", ".hdf5", ".he5")


def _file_kind(path: str) -> str | None:
    lower = path.lower()
    if lower.endswith(FITS_EXTENSIONS):
        return "fits"
    if lower.endswith(HDF5_EXTENSIONS):
        return "hdf5"
    return None


class ComparePanel(QWidget):
    #: emitted with (row, col) whenever the user clicks this panel's image
    #: and it isn't locked - the window decides whether/how to propagate it
    pixel_clicked = Signal(int, int)
    #: emitted whenever a new file/extension is loaded, or the selected
    #: pixel changes - the window listens to refresh the shared spectrum plot
    data_changed = Signal()
    remove_requested = Signal(object)

    def __init__(self, label: str, parent=None) -> None:
        super().__init__(parent)
        self.label = label
        self.current_path: str | None = None
        self.file_kind: str | None = None
        self.data = None  # FitsData or Hdf5Data for the currently selected item
        self._selected_pixel: tuple[int, int] | None = None

        self.title_label = QLabel(f"<b>{label}</b> — no file")

        self.open_button = QPushButton("Open…")
        self.open_button.clicked.connect(self._choose_file)

        self.remove_button = QPushButton("✕")
        self.remove_button.setToolTip("Remove this panel from the comparison")
        self.remove_button.setMaximumWidth(28)
        self.remove_button.clicked.connect(lambda: self.remove_requested.emit(self))

        self.item_combo = QComboBox()
        self.item_combo.currentIndexChanged.connect(self._load_selected_item)
        self.item_combo.setEnabled(False)

        self.lock_check = QCheckBox("Lock crosshair")
        self.lock_check.setToolTip(
            "While locked, clicks on this panel (and linked clicks from other panels) are ignored."
        )

        top_row = QHBoxLayout()
        top_row.addWidget(self.open_button)
        top_row.addWidget(self.item_combo, 1)

        second_row = QHBoxLayout()
        second_row.addWidget(self.lock_check)
        second_row.addStretch(1)
        second_row.addWidget(self.remove_button)

        self.plane_slider = QSlider(Qt.Horizontal)
        self.plane_slider.setMinimum(0)
        self.plane_spin = QSpinBox()
        self.plane_spin.setMinimum(0)
        self.plane_slider.valueChanged.connect(self._on_plane_slider)
        self.plane_spin.valueChanged.connect(self._on_plane_spin)
        plane_row = QHBoxLayout()
        plane_row.addWidget(QLabel("Plane:"))
        plane_row.addWidget(self.plane_slider, 1)
        plane_row.addWidget(self.plane_spin)
        self.plane_row_widget = QWidget()
        self.plane_row_widget.setLayout(plane_row)
        self.plane_row_widget.setVisible(False)

        self.image_view = ImageView()
        self.no_image_label = QLabel("1D spectrum — shown in the plot below.")
        self.no_image_label.setAlignment(Qt.AlignCenter)
        self.no_image_label.setStyleSheet("color: #888888;")

        self.stack = QStackedWidget()
        self.stack.addWidget(self.image_view)
        self.stack.addWidget(self.no_image_label)

        crosshair_pen = pg.mkPen("r", width=1)
        self._vline = pg.InfiniteLine(angle=90, pen=crosshair_pen)
        self._hline = pg.InfiniteLine(angle=0, pen=crosshair_pen)
        self._vline.setVisible(False)
        self._hline.setVisible(False)
        view_box = self.image_view.image_view.getView()
        view_box.addItem(self._vline, ignoreBounds=True)
        view_box.addItem(self._hline, ignoreBounds=True)
        view_box.scene().sigMouseClicked.connect(self._on_image_clicked)

        layout = QVBoxLayout(self)
        layout.addWidget(self.title_label)
        layout.addLayout(top_row)
        layout.addLayout(second_row)
        layout.addWidget(self.plane_row_widget)
        layout.addWidget(self.stack, 1)

    # -- file loading (mirrors MainWindow.open_file, scoped to this panel) --

    def _choose_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            f"Open a FITS or HDF5 file for panel {self.label}",
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
                labels_and_keys = [(f"[{info.index}] {info.name} — {info.kind}", info.index) for info in entries]
                start_key = first_viewable_index(entries)
            else:
                entries = list_datasets(path)
                labels_and_keys = [(f"{info.path} — {info.kind}", info.path) for info in entries]
                start_key = first_viewable_path(entries)
        except (FitsLoadError, Hdf5LoadError) as exc:
            QMessageBox.critical(self, "Cannot open file", str(exc))
            return
        if not entries:
            QMessageBox.warning(self, "Empty file", "This file has no datasets/extensions.")
            return

        self.current_path = path
        self.file_kind = kind
        self.item_combo.blockSignals(True)
        self.item_combo.clear()
        for text, key in labels_and_keys:
            self.item_combo.addItem(text, key)
        self.item_combo.setEnabled(len(entries) > 1)
        self.item_combo.blockSignals(False)
        position = self.item_combo.findData(start_key)
        self.item_combo.setCurrentIndex(max(0, position))
        self._load_selected_item()

    def _load_selected_item(self) -> None:
        if self.current_path is None or self.item_combo.count() == 0:
            return
        key = self.item_combo.currentData()
        try:
            if self.file_kind == "fits":
                data = load_hdu(self.current_path, key)
            else:
                data = load_dataset(self.current_path, key)
        except (FitsLoadError, Hdf5LoadError) as exc:
            QMessageBox.critical(self, "Cannot read this item", str(exc))
            return

        self.data = data
        self._selected_pixel = None
        self._vline.setVisible(False)
        self._hline.setVisible(False)

        if data.kind == "cube":
            n_planes = data.array.shape[0]
            self.plane_row_widget.setVisible(True)
            for widget in (self.plane_slider, self.plane_spin):
                widget.blockSignals(True)
                widget.setMaximum(max(n_planes - 1, 0))
                widget.setValue(0)
                widget.blockSignals(False)
            self.image_view.set_array(data.array[0], auto_range=True)
            self.stack.setCurrentWidget(self.image_view)
        elif data.kind == "image":
            self.plane_row_widget.setVisible(False)
            self.image_view.set_array(data.array, auto_range=True)
            self.stack.setCurrentWidget(self.image_view)
        else:  # spectrum: nothing 2D to show - the full curve goes straight to the shared plot
            self.plane_row_widget.setVisible(False)
            self.stack.setCurrentWidget(self.no_image_label)

        self.title_label.setText(f"<b>{self.label}</b> — {os.path.basename(self.current_path)}")
        self.data_changed.emit()

    # -- plane browsing (never re-reads the file - see CubeView for the single-file case) --

    def _on_plane_slider(self, value: int) -> None:
        self.plane_spin.blockSignals(True)
        self.plane_spin.setValue(value)
        self.plane_spin.blockSignals(False)
        self._show_plane(value)

    def _on_plane_spin(self, value: int) -> None:
        self.plane_slider.blockSignals(True)
        self.plane_slider.setValue(value)
        self.plane_slider.blockSignals(False)
        self._show_plane(value)

    def _show_plane(self, index: int) -> None:
        if self.data is None or self.data.kind != "cube":
            return
        self.image_view.set_array(self.data.array[index], auto_range=False)

    # -- pixel selection --

    def image_shape(self) -> tuple[int, int] | None:
        """The (rows, cols) of the currently displayed 2D plane, or None
        if this panel has nothing image-like loaded."""
        if self.data is None:
            return None
        if self.data.kind == "cube":
            return self.data.array.shape[1], self.data.array.shape[2]
        if self.data.kind == "image":
            return self.data.array.shape
        return None

    def _on_image_clicked(self, event) -> None:
        if self.lock_check.isChecked():
            return
        shape = self.image_shape()
        if shape is None:
            return
        view_box = self.image_view.image_view.getView()
        scene_pos = event.scenePos()
        if not view_box.sceneBoundingRect().contains(scene_pos):
            return
        data_pos = view_box.mapSceneToView(scene_pos)
        col = int(np.floor(data_pos.x()))
        row = int(np.floor(data_pos.y()))
        n_rows, n_cols = shape
        if not (0 <= row < n_rows and 0 <= col < n_cols):
            return
        self.set_pixel(row, col)
        self.pixel_clicked.emit(row, col)

    def set_pixel(self, row: int, col: int) -> None:
        """Move this panel's own crosshair to (row, col), clamped to its
        own image bounds. Used for a direct click on this panel, and for a
        linked click coming from another panel - callers don't need to
        check whether this panel is locked first (locking only blocks
        this panel's own mouse clicks; the window itself skips a locked
        panel when propagating a link)."""
        shape = self.image_shape()
        if shape is None:
            return
        n_rows, n_cols = shape
        row = max(0, min(row, n_rows - 1))
        col = max(0, min(col, n_cols - 1))
        self._selected_pixel = (row, col)
        self._vline.setPos(col + 0.5)
        self._hline.setPos(row + 0.5)
        self._vline.setVisible(True)
        self._hline.setVisible(True)
        self.data_changed.emit()

    def spectrum(self) -> tuple[np.ndarray, np.ndarray | None, str | None, str | None] | None:
        """(flux, axis_values, axis_unit, value_unit) for the currently
        selected pixel (a cube) or the whole array (a plain 1D spectrum
        file); None if there's nothing to plot yet (no file, or a cube
        with no pixel selected, or a plain 2D image with no spectral
        axis at all)."""
        if self.data is None:
            return None
        if self.data.kind == "cube" and self._selected_pixel is not None:
            row, col = self._selected_pixel
            return self.data.array[:, row, col], self.data.axis_values, self.data.axis_unit, self.data.value_unit
        if self.data.kind == "spectrum":
            return self.data.array, self.data.axis_values, self.data.axis_unit, self.data.value_unit
        return None
