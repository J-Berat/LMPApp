"""Image display: pyqtgraph's ImageView (built-in zoom/pan and a
histogram of the *displayed* levels) fed with a pre-stretched array, plus
a small toolbar to choose the stretch, the interval and the colormap -
the quick-look equivalent of DS9's Scale menu."""

from __future__ import annotations

import numpy as np
import pyqtgraph as pg
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox

# A light theme matches the rest of the app's plain Qt widgets instead of
# pyqtgraph's default black plot background; row-major matches plain
# numpy (row, col) indexing, so arrays read from files don't need to be
# transposed before display. Set here (not in fitsviewer/__init__.py) so
# importing this module is what pays for pulling in pyqtgraph/Qt - pure
# logic modules stay importable without a display.
pg.setConfigOptions(imageAxisOrder="row-major", background="w", foreground="k")

from .image_stretch import (
    STRETCHES,
    INTERVALS,
    COLORMAPS,
    COLORMAP_STOPS,
    DEFAULT_STRETCH,
    DEFAULT_INTERVAL,
    DEFAULT_COLORMAP,
    normalize_array,
)


class ImageView(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._array: np.ndarray | None = None

        self.stretch_combo = QComboBox()
        self.stretch_combo.addItems(list(STRETCHES.keys()))
        self.stretch_combo.setCurrentText(DEFAULT_STRETCH)

        self.interval_combo = QComboBox()
        self.interval_combo.addItems(list(INTERVALS.keys()))
        self.interval_combo.setCurrentText(DEFAULT_INTERVAL)

        self.colormap_combo = QComboBox()
        self.colormap_combo.addItems(COLORMAPS)
        self.colormap_combo.setCurrentText(DEFAULT_COLORMAP)

        self.stretch_combo.currentTextChanged.connect(self._refresh)
        self.interval_combo.currentTextChanged.connect(self._refresh)
        self.colormap_combo.currentTextChanged.connect(self._apply_colormap)

        toolbar = QHBoxLayout()
        toolbar.addWidget(QLabel("Stretch:"))
        toolbar.addWidget(self.stretch_combo)
        toolbar.addWidget(QLabel("Limits:"))
        toolbar.addWidget(self.interval_combo)
        toolbar.addWidget(QLabel("Colormap:"))
        toolbar.addWidget(self.colormap_combo)
        toolbar.addStretch(1)

        self.image_view = pg.ImageView()
        self.image_view.ui.roiBtn.hide()
        self.image_view.ui.menuBtn.hide()

        layout = QVBoxLayout(self)
        layout.addLayout(toolbar)
        layout.addWidget(self.image_view)

        self._apply_colormap(self.colormap_combo.currentText())

    def set_array(self, array: np.ndarray, auto_range: bool = True) -> None:
        self._array = array
        self._refresh(auto_range=auto_range)

    def _refresh(self, *_args, auto_range: bool = False) -> None:
        if self._array is None:
            return
        normalized = normalize_array(self._array, self.stretch_combo.currentText(), self.interval_combo.currentText())
        self.image_view.setImage(normalized, autoRange=auto_range, autoLevels=False, levels=(0.0, 1.0))

    def _apply_colormap(self, name: str) -> None:
        stops = COLORMAP_STOPS.get(name, COLORMAP_STOPS[DEFAULT_COLORMAP])
        positions = [pos for pos, _rgb in stops]
        colors = [(r, g, b, 255) for _pos, (r, g, b) in stops]
        self.image_view.setColorMap(pg.ColorMap(positions, colors))
