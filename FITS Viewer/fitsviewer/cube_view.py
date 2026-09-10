"""Cube display: browse the planes of a 3D array that is kept fully in
memory (so changing plane, line-of-sight axis, stretch, interval or
colormap never re-reads the file), and click a pixel on the image to see
its spectrum - the values along the chosen line-of-sight axis - on the
right, with a crosshair marking the selected pixel."""

from __future__ import annotations

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QSlider,
    QSpinBox,
    QSplitter,
    QComboBox,
)

from .image_view import ImageView
from .spectrum_view import SpectrumView


class CubeView(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._cube: np.ndarray | None = None
        self._working_cube: np.ndarray | None = None  # self._cube with the
        # chosen line-of-sight axis moved to position 0 (a view, no copy)
        self._cube_axis_values: list[np.ndarray | None] | None = None
        self._cube_axis_units: list[str | None] | None = None
        self._cube_axis_labels: list[str | None] | None = None
        self._value_unit: str | None = None
        self._value_label: str | None = None
        self._los_axis: int = 0
        self._selected_pixel: tuple[int, int] | None = None

        self.image_view = ImageView()
        self.spectrum_view = SpectrumView()
        self.spectrum_view.set_title("Click a pixel on the image to show its spectrum")

        self.los_combo = QComboBox()
        self.los_combo.currentIndexChanged.connect(self._on_los_changed)

        self.plane_slider = QSlider(Qt.Horizontal)
        self.plane_slider.setMinimum(0)
        self.plane_spin = QSpinBox()
        self.plane_spin.setMinimum(0)
        self.plane_count_label = QLabel("")

        self.plane_slider.valueChanged.connect(self._on_plane_slider)
        self.plane_spin.valueChanged.connect(self._on_plane_spin)

        los_row = QHBoxLayout()
        los_row.addWidget(QLabel("Line of sight:"))
        los_row.addWidget(self.los_combo, 1)

        plane_row = QHBoxLayout()
        plane_row.addWidget(QLabel("Plane:"))
        plane_row.addWidget(self.plane_slider, 1)
        plane_row.addWidget(self.plane_spin)
        plane_row.addWidget(self.plane_count_label)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addLayout(los_row)
        left_layout.addLayout(plane_row)
        left_layout.addWidget(self.image_view)

        # A crosshair on the last-clicked pixel, hidden until a click happens.
        self._vline = pg.InfiniteLine(angle=90, pen=pg.mkPen("r", width=1))
        self._hline = pg.InfiniteLine(angle=0, pen=pg.mkPen("r", width=1))
        self._vline.setVisible(False)
        self._hline.setVisible(False)
        view_box = self.image_view.image_view.getView()
        view_box.addItem(self._vline, ignoreBounds=True)
        view_box.addItem(self._hline, ignoreBounds=True)
        self.image_view.image_view.getView().scene().sigMouseClicked.connect(self._on_image_clicked)

        splitter = QSplitter()
        splitter.addWidget(left)
        splitter.addWidget(self.spectrum_view)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)

        layout = QVBoxLayout(self)
        layout.addWidget(splitter)

    def set_cube(
        self,
        cube: np.ndarray,
        axis_values: list[np.ndarray | None] | None = None,
        axis_units: list[str | None] | None = None,
        value_unit: str | None = None,
        axis_labels: list[str | None] | None = None,
        value_label: str | None = None,
    ) -> None:
        """Load a new cube. The full array is kept in memory: browsing
        planes, changing the line-of-sight axis, and changing
        stretch/interval/colormap afterwards never re-reads the file.

        `axis_values`/`axis_units`/`axis_labels` each have one entry per
        numpy axis of `cube`, so any axis can be picked as the line of
        sight - the axis along which the spectrum is taken."""
        ndim = cube.ndim
        self._cube = cube
        self._cube_axis_values = list(axis_values) if axis_values is not None else [None] * ndim
        self._cube_axis_units = list(axis_units) if axis_units is not None else [None] * ndim
        self._cube_axis_labels = list(axis_labels) if axis_labels is not None else [None] * ndim
        self._value_unit = value_unit
        self._value_label = value_label

        self.los_combo.blockSignals(True)
        self.los_combo.clear()
        for axis in range(ndim):
            label = self._cube_axis_labels[axis]
            self.los_combo.addItem(f"Axis {axis} ({label})" if label else f"Axis {axis}", axis)
        self.los_combo.setCurrentIndex(0)
        self.los_combo.blockSignals(False)

        self._set_los_axis(0)

    def _on_los_changed(self, combo_index: int) -> None:
        if self._cube is None or combo_index < 0:
            return
        axis = self.los_combo.itemData(combo_index)
        if axis is None:
            return
        self._set_los_axis(axis)

    def _set_los_axis(self, axis: int) -> None:
        """Move the chosen numpy axis of the cube to position 0 (a view,
        no data copy) so the existing plane-browsing and pixel-click
        logic - which always treats axis 0 as the line of sight - works
        unchanged whichever physical axis was picked."""
        self._los_axis = axis
        self._working_cube = np.moveaxis(self._cube, axis, 0)
        self._selected_pixel = None
        self._vline.setVisible(False)
        self._hline.setVisible(False)
        self.spectrum_view.clear()
        self.spectrum_view.set_title("Click a pixel on the image to show its spectrum")

        n_planes = self._working_cube.shape[0]
        for widget in (self.plane_slider, self.plane_spin):
            widget.blockSignals(True)
            widget.setMaximum(max(n_planes - 1, 0))
            widget.setValue(0)
            widget.blockSignals(False)
        self.plane_count_label.setText(f"/ {n_planes - 1}")

        self.image_view.set_array(self._working_cube[0], auto_range=True)

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
        if self._working_cube is None:
            return
        # A plain plane swap - the stretch/interval/colormap combos and
        # the current zoom are all left exactly as they are.
        self.image_view.set_array(self._working_cube[index], auto_range=False)

    def _on_image_clicked(self, event) -> None:
        if self._working_cube is None:
            return
        view_box = self.image_view.image_view.getView()
        scene_pos = event.scenePos()
        if not view_box.sceneBoundingRect().contains(scene_pos):
            return
        data_pos = view_box.mapSceneToView(scene_pos)
        col = int(np.floor(data_pos.x()))
        row = int(np.floor(data_pos.y()))
        _, n_rows, n_cols = self._working_cube.shape
        if not (0 <= row < n_rows and 0 <= col < n_cols):
            return

        self._selected_pixel = (row, col)
        self._vline.setPos(col + 0.5)
        self._hline.setPos(row + 0.5)
        self._vline.setVisible(True)
        self._hline.setVisible(True)

        spectrum = self._working_cube[:, row, col]
        self.spectrum_view.set_spectrum(
            spectrum,
            self._cube_axis_values[self._los_axis],
            x_label=self._cube_axis_labels[self._los_axis] or "Axis value",
            x_unit=self._cube_axis_units[self._los_axis],
            y_label=self._value_label or "Value",
            y_unit=self._value_unit,
            index_label="Plane index",
        )
        self.spectrum_view.set_title(f"Spectrum at pixel (row {row}, col {col})")
