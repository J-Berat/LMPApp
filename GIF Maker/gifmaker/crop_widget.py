"""A minimal interactive rectangle-selection tool for cropping - used both
from the video import dialog (crop the extracted frames) and as a general
"Crop…" action on the current image sequence."""

from __future__ import annotations

import os

from PIL import Image
from PySide6.QtCore import Qt, QRect, QPoint
from PySide6.QtGui import QPixmap, QPainter, QColor, QPen, QImage
from PySide6.QtWidgets import (
    QWidget,
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QDialogButtonBox,
)


def _pil_to_qpixmap(img: Image.Image) -> QPixmap:
    rgb = img.convert("RGB")
    data = rgb.tobytes("raw", "RGB")
    qimg = QImage(data, rgb.width, rgb.height, rgb.width * 3, QImage.Format_RGB888)
    return QPixmap.fromImage(qimg.copy())  # copy() detaches from the Python bytes buffer


def _subtract_rect(outer: QRect, inner: QRect) -> list[QRect]:
    """Return up to 4 rectangles covering `outer` minus `inner` - used to
    dim everything outside the current crop selection."""
    inner = inner.intersected(outer)
    if inner.isEmpty():
        return [outer]
    rects = []
    if inner.top() > outer.top():
        rects.append(QRect(outer.left(), outer.top(), outer.width(), inner.top() - outer.top()))
    if inner.bottom() < outer.bottom():
        rects.append(QRect(outer.left(), inner.bottom() + 1, outer.width(), outer.bottom() - inner.bottom()))
    if inner.left() > outer.left():
        rects.append(QRect(outer.left(), inner.top(), inner.left() - outer.left(), inner.height()))
    if inner.right() < outer.right():
        rects.append(QRect(inner.right() + 1, inner.top(), outer.right() - inner.right(), inner.height()))
    return rects


class CropWidget(QWidget):
    """Displays an image at a fixed, fitted size and lets the user drag out
    a rectangle to select the area to keep."""

    MAX_DISPLAY = 640

    def __init__(self, image: Image.Image, parent=None) -> None:
        super().__init__(parent)
        w, h = image.size
        scale = min(1.0, self.MAX_DISPLAY / max(w, h)) if max(w, h) > 0 else 1.0
        self._display_size = (max(1, round(w * scale)), max(1, round(h * scale)))
        display_img = image.resize(self._display_size, Image.LANCZOS)
        self._pixmap = _pil_to_qpixmap(display_img)
        self.setFixedSize(*self._display_size)
        self.setCursor(Qt.CrossCursor)
        self._drag_start: QPoint | None = None
        self._selection: QRect | None = None

    def normalized_rect(self) -> tuple[float, float, float, float] | None:
        """The current selection as (x0, y0, x1, y1) fractions of the
        image, or None if nothing usable has been selected."""
        if self._selection is None or self._selection.width() < 4 or self._selection.height() < 4:
            return None
        w, h = self._display_size
        x0 = max(0.0, self._selection.left() / w)
        y0 = max(0.0, self._selection.top() / h)
        x1 = min(1.0, self._selection.right() / w)
        y1 = min(1.0, self._selection.bottom() / h)
        return (x0, y0, x1, y1)

    def clear_selection(self) -> None:
        self._selection = None
        self.update()

    def mousePressEvent(self, event) -> None:
        self._drag_start = event.position().toPoint()
        self._selection = QRect(self._drag_start, self._drag_start)
        self.update()

    def mouseMoveEvent(self, event) -> None:
        if self._drag_start is None:
            return
        current = event.position().toPoint()
        self._selection = QRect(self._drag_start, current).normalized()
        self.update()

    def mouseReleaseEvent(self, event) -> None:
        self._drag_start = None
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.drawPixmap(0, 0, self._pixmap)
        if self._selection is not None and self._selection.width() > 1 and self._selection.height() > 1:
            w, h = self._display_size
            full = QRect(0, 0, w, h)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(0, 0, 0, 120))
            for rect in _subtract_rect(full, self._selection):
                painter.drawRect(rect)
            painter.setPen(QPen(QColor(255, 255, 255), 2))
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(self._selection)
        painter.end()


class CropDialog(QDialog):
    """Wraps CropWidget with instructions and OK/Cancel/Clear buttons."""

    def __init__(self, image: Image.Image, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Crop")
        self.crop_widget = CropWidget(image)

        hint = QLabel("Click and drag to select the area to keep.")

        clear_btn = QPushButton("Clear selection")
        clear_btn.clicked.connect(self.crop_widget.clear_selection)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        button_row = QHBoxLayout()
        button_row.addWidget(clear_btn)
        button_row.addStretch(1)

        layout = QVBoxLayout(self)
        layout.addWidget(hint)
        layout.addWidget(self.crop_widget)
        layout.addLayout(button_row)
        layout.addWidget(buttons)

    def normalized_rect(self) -> tuple[float, float, float, float] | None:
        return self.crop_widget.normalized_rect()


def apply_crop_to_images(
    image_paths: list[str], norm_rect: tuple[float, float, float, float], out_dir: str
) -> list[str]:
    """Crop every image in `image_paths` to `norm_rect` (x0, y0, x1, y1 as
    fractions of each image's own size) and save the results as new files
    in `out_dir`. Returns the new paths, in the same order as the input."""
    x0, y0, x1, y1 = norm_rect
    new_paths = []
    for i, path in enumerate(image_paths):
        img = Image.open(path)
        w, h = img.size
        box = (
            max(0, round(x0 * w)),
            max(0, round(y0 * h)),
            min(w, round(x1 * w)),
            min(h, round(y1 * h)),
        )
        if box[2] <= box[0] or box[3] <= box[1]:
            box = (0, 0, w, h)  # degenerate selection for this image - keep it whole
        cropped = img.convert("RGBA").crop(box)
        base = os.path.splitext(os.path.basename(path))[0]
        out_path = os.path.join(out_dir, f"{base}_cropped_{i:04d}.png")
        cropped.save(out_path)
        new_paths.append(out_path)
    return new_paths
