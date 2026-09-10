"""Cube display: browse the planes of a 3D array that is kept fully in
memory (so changing plane, stretch, interval or colormap never re-reads
the file), and click a pixel on the image to see its spectrum - the
values along the cube's first axis - on the right, with a crosshair
marking the selected pixel."""

from __future__ import annotations

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSlider, QSpinBox, QSplitter

from .image_view import ImageView
from .spectrum_view import SpectrumView


class CubeView(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._cube: np.ndarray | None = None
        self._axis_values: np.ndarray | None = None
        self._axis_unit: str | None = None
        self._value_unit: str | None = None
        self._selected_pixel: tuple[int, int] | None = None

        self.image_view = ImageView()
        self.spectrum_view = SpectrumView()
        self.spectrum_view.set_title("Click a pixel on the image to show its spectrum")

        self.plane_slider = QSlider(Qt.Horizontal)
        self.plane_slider.setMinimum(0)
        self.plane_spin = QSpinBox()
        self.plane_spin.setMinimum(0)
        self.plane_count_label = QLabel("")

        self.plane_slider.valueChanged.connect(self._on_plane_slider)
        self.plane_spin.valueChanged.connect(self._on_plane_spin)

        plane_row = QHBoxLayout()
        plane_row.addWidget(QLabel("Plane:"))
        plane_row.addWidget(self.plane_slider, 1)
        plane_row.addWidget(self.plane_spin)
        plane_row.addWidget(self.plane_count_label)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
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
        axis_values: np.ndarray | None,
        axis_unit: str | None = None,
        value_unit: str | None = None,
    ) -> None:
        """Load a new cube. The full 3D array is kept in memory: browsing
        planes and changing stretch/interval/colormap afterwards never
        re-reads the file."""
        self._cube = cube
        self._axis_values = axis_values
        self._axis_unit = axis_unit
        self._value_unit = value_unit
        self._selected_pixel = None
        self._vline.setVisible(False)
        self._hline.setVisible(False)
        self.spectrum_view.clear()
        self.spectrum_view.set_title("Click a pixel on the image to show its spectrum")

        n_planes = cube.shape[0]
        for widget in (self.plane_slider, self.plane_spin):
            widget.blockSignals(True)
            widget.setMaximum(max(n_planes - 1, 0))
            widget.setValue(0)
            widget.blockSignals(False)
        self.plane_count_label.setText(f"/ {n_planes - 1}")

        self.image_view.set_array(cube[0], auto_range=True)

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
        if self._cube is None:
            return
        # A plain plane swap - the stretch/interval/colormap combos and
        # the current zoom are all left exactly as they are.
        self.image_view.set_array(self._cube[index], auto_range=False)

    def _on_image_clicked(self, event) -> None:
        if self._cube is None:
            return
        view_box = self.image_view.image_view.getView()
        scene_pos = event.scenePos()
        if not view_box.sceneBoundingRect().contains(scene_pos):
            return
        data_pos = view_box.mapSceneToView(scene_pos)
        col = int(np.floor(data_pos.x()))
        row = int(np.floor(data_pos.y()))
        _, n_rows, n_cols = self._cube.shape
        if not (0 <= row < n_rows and 0 <= col < n_cols):
            return

        self._selected_pixel = (row, col)
        self._vline.setPos(col + 0.5)
        self._hline.setPos(row + 0.5)
        self._vline.setVisible(True)
        self._hline.setVisible(True)

        spectrum = self._cube[:, row, col]
        self.spectrum_view.set_spectrum(
            spectrum,
            self._axis_values,
            x_unit=self._axis_unit,
            y_unit=self._value_unit,
            index_label="Plane index",
        )
        self.spectrum_view.set_title(f"Spectrum at pixel (row {row}, col {col})")
