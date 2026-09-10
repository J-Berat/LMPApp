"""1D spectrum display via pyqtgraph's PlotWidget: one or several named,
distinctly-colored curves (for Compare mode), axis labels that include
units when the file provides them, and manual x/y limit fields (with an
Auto button) for zooming into a specific range."""

from __future__ import annotations

import numpy as np
import pyqtgraph as pg
from PySide6.QtGui import QDoubleValidator
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QFileDialog,
    QMessageBox,
)

#: Default palette for successive curves added via set_curve() without an
#: explicit color - the first entry matches the single-curve default so
#: set_spectrum()'s look is unchanged.
DEFAULT_CURVE_COLORS = ["#1f6feb", "#d62728", "#2ca02c", "#9467bd", "#ff7f0e", "#17becf", "#8c564b", "#e377c2"]

_MAIN_KEY = "main"


class SpectrumView(QWidget):
    def __init__(self, parent=None, show_legend: bool = False) -> None:
        super().__init__(parent)
        self._x_by_key: dict[str, np.ndarray] = {}
        self._y_by_key: dict[str, np.ndarray] = {}
        self._items_by_key: dict[str, pg.PlotDataItem] = {}
        self._manual_limits = False

        self.plot_widget = pg.PlotWidget()
        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)
        self._legend = self.plot_widget.addLegend() if show_legend else None

        validator = QDoubleValidator()
        validator.setNotation(QDoubleValidator.ScientificNotation)

        self.x_min_edit = QLineEdit()
        self.x_max_edit = QLineEdit()
        self.y_min_edit = QLineEdit()
        self.y_max_edit = QLineEdit()
        for edit in (self.x_min_edit, self.x_max_edit, self.y_min_edit, self.y_max_edit):
            edit.setValidator(validator)
            edit.setMaximumWidth(90)
            edit.editingFinished.connect(self._apply_manual_limits)

        self.auto_button = QPushButton("Auto")
        self.auto_button.setToolTip("Reset both axes to fit the current data")
        self.auto_button.clicked.connect(self._reset_to_auto)

        limits_row = QHBoxLayout()
        limits_row.addWidget(QLabel("X:"))
        limits_row.addWidget(self.x_min_edit)
        limits_row.addWidget(QLabel("–"))
        limits_row.addWidget(self.x_max_edit)
        limits_row.addSpacing(12)
        limits_row.addWidget(QLabel("Y:"))
        limits_row.addWidget(self.y_min_edit)
        limits_row.addWidget(QLabel("–"))
        limits_row.addWidget(self.y_max_edit)
        limits_row.addSpacing(12)
        limits_row.addWidget(self.auto_button)
        limits_row.addStretch(1)

        self.export_csv_button = QPushButton("Export CSV…")
        self.export_csv_button.setToolTip("Save the plotted values (axis + data) to a CSV file")
        self.export_csv_button.clicked.connect(self._export_csv)

        self.export_image_button = QPushButton("Export image…")
        self.export_image_button.setToolTip("Save the plot as a PNG image")
        self.export_image_button.clicked.connect(self._export_image)

        export_row = QHBoxLayout()
        export_row.addWidget(self.export_csv_button)
        export_row.addWidget(self.export_image_button)
        export_row.addStretch(1)

        layout = QVBoxLayout(self)
        layout.addLayout(limits_row)
        layout.addLayout(export_row)
        layout.addWidget(self.plot_widget)

    # -- single-curve convenience API (the plain viewer, one cube's pixel click) --

    def set_spectrum(
        self,
        flux: np.ndarray,
        x_values: np.ndarray | None,
        x_label: str = "Axis value",
        x_unit: str | None = None,
        y_label: str = "Value",
        y_unit: str | None = None,
        index_label: str = "Pixel",
    ) -> None:
        """Show exactly one curve, replacing any others - the common case
        outside Compare mode."""
        for key in [k for k in self._items_by_key if k != _MAIN_KEY]:
            self.remove_curve(key)
        self.set_curve(
            _MAIN_KEY,
            flux,
            x_values,
            label=y_label,
            color=DEFAULT_CURVE_COLORS[0],
            x_label=x_label,
            x_unit=x_unit,
            y_label=y_label,
            y_unit=y_unit,
            index_label=index_label,
        )

    # -- multi-curve API (Compare mode) --

    def set_curve(
        self,
        key: str,
        flux: np.ndarray,
        x_values: np.ndarray | None,
        label: str,
        color: str,
        x_label: str = "Axis value",
        x_unit: str | None = None,
        y_label: str = "Value",
        y_unit: str | None = None,
        index_label: str = "Pixel",
    ) -> None:
        """Add or update one named curve, leaving any other curves in
        place - used to overlay several files' spectra in Compare mode."""
        x = x_values if x_values is not None else np.arange(1, len(flux) + 1)
        self._x_by_key[key] = x
        self._y_by_key[key] = flux

        item = self._items_by_key.get(key)
        if item is None:
            pen = pg.mkPen(color=color, width=2.5)
            item = self.plot_widget.plot([], [], pen=pen, antialias=True, name=label)
            self._items_by_key[key] = item
        item.setData(x, flux)

        x_text = x_label if x_values is not None else index_label
        if x_unit and x_values is not None:
            x_text = f"{x_text} ({x_unit})"
        y_text = f"{y_label} ({y_unit})" if y_unit else y_label
        self.plot_widget.setLabel("bottom", x_text)
        self.plot_widget.setLabel("left", y_text)

        self._update_placeholders()
        if not self._manual_limits:
            self.plot_widget.enableAutoRange()

    def remove_curve(self, key: str) -> None:
        item = self._items_by_key.pop(key, None)
        if item is not None:
            if self._legend is not None:
                self._legend.removeItem(item)
            self.plot_widget.removeItem(item)
        self._x_by_key.pop(key, None)
        self._y_by_key.pop(key, None)
        self._update_placeholders()

    def clear_curves(self) -> None:
        for key in list(self._items_by_key):
            self.remove_curve(key)

    def clear(self) -> None:
        self.clear_curves()

    def set_title(self, text: str) -> None:
        self.plot_widget.setTitle(text)

    def _apply_manual_limits(self) -> None:
        x_min, x_max = self._parse(self.x_min_edit), self._parse(self.x_max_edit)
        y_min, y_max = self._parse(self.y_min_edit), self._parse(self.y_max_edit)

        applied = False
        if x_min is not None and x_max is not None and x_min < x_max:
            self.plot_widget.setXRange(x_min, x_max, padding=0)
            applied = True
        if y_min is not None and y_max is not None and y_min < y_max:
            self.plot_widget.setYRange(y_min, y_max, padding=0)
            applied = True
        if applied:
            self._manual_limits = True

    @staticmethod
    def _parse(edit: QLineEdit) -> float | None:
        text = edit.text().strip()
        if not text:
            return None
        try:
            return float(text)
        except ValueError:
            return None

    def _reset_to_auto(self) -> None:
        self._manual_limits = False
        for edit in (self.x_min_edit, self.x_max_edit, self.y_min_edit, self.y_max_edit):
            edit.blockSignals(True)
            edit.clear()
            edit.blockSignals(False)
        self.plot_widget.enableAutoRange()

    def _export_image(self) -> None:
        if not self._items_by_key:
            QMessageBox.information(self, "Nothing to export", "Nothing is plotted yet.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export plot", "", "PNG image (*.png)")
        if not path:
            return
        if not path.lower().endswith(".png"):
            path += ".png"
        try:
            from pyqtgraph.exporters import ImageExporter

            exporter = ImageExporter(self.plot_widget.plotItem)
            exporter.export(path)
        except Exception as exc:
            QMessageBox.critical(self, "Export failed", f"Could not save the plot: {exc}")

    def _export_csv(self) -> None:
        if not self._items_by_key:
            QMessageBox.information(self, "Nothing to export", "Nothing is plotted yet.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export data", "", "CSV file (*.csv)")
        if not path:
            return
        if not path.lower().endswith(".csv"):
            path += ".csv"

        import csv

        keys = list(self._items_by_key.keys())
        try:
            with open(path, "w", newline="") as f:
                writer = csv.writer(f)
                if len(keys) == 1:
                    key = keys[0]
                    x_label = self.plot_widget.getAxis("bottom").labelText or "x"
                    y_label = self.plot_widget.getAxis("left").labelText or "y"
                    writer.writerow([x_label, y_label])
                    for x, y in zip(self._x_by_key[key], self._y_by_key[key]):
                        writer.writerow([x, y])
                else:
                    # Compare mode: several curves, possibly different
                    # lengths - each gets its own x/y column pair rather
                    # than forcing a single shared x axis.
                    header = []
                    columns = []
                    for key in keys:
                        item = self._items_by_key[key]
                        name = item.name() or key
                        header += [f"{name} - x", f"{name} - y"]
                        columns.append((self._x_by_key[key], self._y_by_key[key]))
                    writer.writerow(header)
                    max_len = max(len(x) for x, _y in columns)
                    for i in range(max_len):
                        row = []
                        for x, y in columns:
                            row.append(x[i] if i < len(x) else "")
                            row.append(y[i] if i < len(y) else "")
                        writer.writerow(row)
        except OSError as exc:
            QMessageBox.critical(self, "Export failed", f"Could not save the data: {exc}")

    def _update_placeholders(self) -> None:
        """Show the combined data's current min/max as placeholder text in
        the limit fields, so the user can see the full range before
        choosing to narrow it."""
        all_x = [v[np.isfinite(v)] for v in self._x_by_key.values() if len(v)]
        all_y = [v[np.isfinite(v)] for v in self._y_by_key.values() if len(v)]

        if all_x:
            combined_x = np.concatenate(all_x)
            if combined_x.size:
                self.x_min_edit.setPlaceholderText(f"{combined_x.min():.4g}")
                self.x_max_edit.setPlaceholderText(f"{combined_x.max():.4g}")
        if all_y:
            combined_y = np.concatenate(all_y)
            if combined_y.size:
                self.y_min_edit.setPlaceholderText(f"{combined_y.min():.4g}")
                self.y_max_edit.setPlaceholderText(f"{combined_y.max():.4g}")
