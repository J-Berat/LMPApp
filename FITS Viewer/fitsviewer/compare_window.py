"""Compare mode: open several FITS/HDF5 files side by side, each with its
own image (and, for a cube, its own plane slider), all sharing one
spectrum plot where each panel's spectrum is overlaid in its own color.

Each panel has a "Lock crosshair" checkbox, and the window has a "Link
crosshairs" toggle:
- Linked (default): clicking any unlocked panel moves every other
  unlocked panel's crosshair to the same relative position (scaled
  proportionally, so panels with different image sizes still line up) -
  for comparing the same location across files.
- Unlocked panels with linking off move independently on their own
  clicks - for putting each panel wherever you want and comparing
  whatever two spots you choose.
- A locked panel never moves, whether from its own click or a linked
  one from another panel - so you can freeze one file's spectrum while
  freely exploring another.
"""

from __future__ import annotations

import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QCheckBox, QSplitter

from .compare_panel import ComparePanel
from .spectrum_view import SpectrumView, DEFAULT_CURVE_COLORS

_PANEL_LABELS = "ABCDEFGH"


class CompareWindow(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Compare FITS/HDF5 files")
        self.resize(1300, 820)

        self._panels: list[ComparePanel] = []

        self.add_button = QPushButton("+ Add file to compare")
        self.add_button.clicked.connect(self._add_panel)

        self.link_check = QCheckBox("Link crosshairs (click an unlocked panel to move all unlocked panels together)")
        self.link_check.setChecked(True)

        top_row = QHBoxLayout()
        top_row.addWidget(self.add_button)
        top_row.addWidget(self.link_check)
        top_row.addStretch(1)

        self.panels_splitter = QSplitter()
        self.spectrum_view = SpectrumView(show_legend=True)

        vertical_splitter = QSplitter(Qt.Vertical)
        vertical_splitter.addWidget(self.panels_splitter)
        vertical_splitter.addWidget(self.spectrum_view)
        vertical_splitter.setStretchFactor(0, 3)
        vertical_splitter.setStretchFactor(1, 2)

        layout = QVBoxLayout(self)
        layout.addLayout(top_row)
        layout.addWidget(vertical_splitter, 1)

        self._add_panel()
        self._add_panel()

    def _add_panel(self) -> None:
        if len(self._panels) >= len(_PANEL_LABELS):
            return
        label = _PANEL_LABELS[len(self._panels)]
        panel = ComparePanel(label)
        panel.pixel_clicked.connect(lambda row, col, source=panel: self._on_pixel_clicked(source, row, col))
        panel.data_changed.connect(self._refresh_spectra)
        panel.remove_requested.connect(self._remove_panel)
        self._panels.append(panel)
        self.panels_splitter.addWidget(panel)

    def _remove_panel(self, panel: ComparePanel) -> None:
        if len(self._panels) <= 1:
            return
        self._panels.remove(panel)
        panel.setParent(None)
        panel.deleteLater()
        self.spectrum_view.remove_curve(panel.label)

    def _on_pixel_clicked(self, source: ComparePanel, row: int, col: int) -> None:
        if not self.link_check.isChecked():
            return
        source_shape = source.image_shape()
        if source_shape is None:
            return
        row_frac = (row + 0.5) / source_shape[0]
        col_frac = (col + 0.5) / source_shape[1]
        for panel in self._panels:
            if panel is source or panel.lock_check.isChecked():
                continue
            shape = panel.image_shape()
            if shape is None:
                continue
            target_row = min(int(row_frac * shape[0]), shape[0] - 1)
            target_col = min(int(col_frac * shape[1]), shape[1] - 1)
            panel.set_pixel(target_row, target_col)

    def _refresh_spectra(self) -> None:
        for i, panel in enumerate(self._panels):
            result = panel.spectrum()
            if result is None:
                self.spectrum_view.remove_curve(panel.label)
                continue
            flux, axis_values, axis_unit, value_unit = result
            name = panel.label
            if panel.current_path:
                name = f"{panel.label}: {os.path.basename(panel.current_path)}"
            self.spectrum_view.set_curve(
                panel.label,
                flux,
                axis_values,
                label=name,
                color=DEFAULT_CURVE_COLORS[i % len(DEFAULT_CURVE_COLORS)],
                x_unit=axis_unit,
                y_unit=value_unit,
                index_label="Plane index",
            )
