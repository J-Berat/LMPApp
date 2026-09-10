"""Dialog for importing frames from a video file: trim, sample rate, speed
and an optional crop, producing a batch of frame images the sequence
editor can add just like any manually-added images."""

from __future__ import annotations

from PIL import Image
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLabel,
    QDoubleSpinBox,
    QSpinBox,
    QPushButton,
    QDialogButtonBox,
    QMessageBox,
)

from .video_importer import probe_video, extract_frame_at, extract_frames, VideoImportError, MAX_EXTRACTED_FRAMES
from .crop_widget import CropDialog, _pil_to_qpixmap

MAX_PREVIEW = 320


def _format_duration(seconds: float) -> str:
    minutes, secs = divmod(max(0.0, seconds), 60)
    return f"{int(minutes)}:{secs:04.1f}"


class VideoImportDialog(QDialog):
    """On accept, `result_frame_paths` holds the extracted frame files and
    `result_frame_delay_ms` the per-frame delay implied by the chosen
    duration/speed - both ready to hand to the model."""

    def __init__(self, video_path: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Import from video")
        self.video_path = video_path
        self._crop_norm: tuple[float, float, float, float] | None = None
        self._preview_frame: Image.Image | None = None
        self._estimated_frame_count = 1
        self._estimated_delay_ms = 200
        self.result_frame_paths: list[str] = []
        self.result_frame_delay_ms: int = 200
        self.info = None

        try:
            self.info = probe_video(video_path)
        except VideoImportError as exc:
            QMessageBox.critical(self, "Cannot open video", str(exc))
            QTimer.singleShot(0, self.reject)
            return

        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setMinimumSize(MAX_PREVIEW, MAX_PREVIEW // 2)
        self.preview_label.setStyleSheet("QLabel { background: #202020; border-radius: 4px; }")

        duration = max(0.0, self.info.duration_seconds)

        self.start_spin = QDoubleSpinBox()
        self.start_spin.setRange(0.0, duration)
        self.start_spin.setDecimals(2)
        self.start_spin.setSuffix(" s")
        self.start_spin.setValue(0.0)

        self.end_spin = QDoubleSpinBox()
        self.end_spin.setRange(0.0, duration)
        self.end_spin.setDecimals(2)
        self.end_spin.setSuffix(" s")
        self.end_spin.setValue(duration)

        self.sample_fps_spin = QSpinBox()
        self.sample_fps_spin.setRange(1, 30)
        self.sample_fps_spin.setValue(10)
        self.sample_fps_spin.setSuffix(" fps")

        self.speed_spin = QDoubleSpinBox()
        self.speed_spin.setRange(0.1, 4.0)
        self.speed_spin.setSingleStep(0.1)
        self.speed_spin.setValue(1.0)
        self.speed_spin.setSuffix("x")

        self.crop_button = QPushButton("Crop…")
        self.crop_status_label = QLabel("No crop selected")

        self.estimate_label = QLabel("")
        self.estimate_label.setWordWrap(True)

        form = QFormLayout()
        form.addRow("Start:", self.start_spin)
        form.addRow("End:", self.end_spin)
        form.addRow("Sample rate:", self.sample_fps_spin)
        form.addRow("Speed:", self.speed_spin)

        crop_row = QHBoxLayout()
        crop_row.addWidget(self.crop_button)
        crop_row.addWidget(self.crop_status_label, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)

        info_text = (
            f"Video: {_format_duration(self.info.duration_seconds)}, "
            f"{self.info.width}×{self.info.height}, ~{self.info.fps:.1f} fps"
        )

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(info_text))
        layout.addWidget(self.preview_label)
        layout.addLayout(form)
        layout.addLayout(crop_row)
        layout.addWidget(self.estimate_label)
        layout.addWidget(buttons)

        self.start_spin.valueChanged.connect(self._on_start_changed)
        self.end_spin.valueChanged.connect(self._on_end_changed)
        self.sample_fps_spin.valueChanged.connect(self._update_estimate)
        self.speed_spin.valueChanged.connect(self._update_estimate)
        self.crop_button.clicked.connect(self._open_crop_dialog)

        self._update_preview()
        self._update_estimate()

    def _update_preview(self) -> None:
        try:
            self._preview_frame = extract_frame_at(self.video_path, self.start_spin.value())
        except VideoImportError:
            self._preview_frame = None
            return
        thumb = self._preview_frame.copy()
        thumb.thumbnail((MAX_PREVIEW, MAX_PREVIEW), Image.LANCZOS)
        self.preview_label.setPixmap(_pil_to_qpixmap(thumb))

    def _on_start_changed(self) -> None:
        if self.start_spin.value() > self.end_spin.value():
            self.end_spin.blockSignals(True)
            self.end_spin.setValue(self.start_spin.value())
            self.end_spin.blockSignals(False)
        # A new start time invalidates any crop drawn on the old preview frame.
        self._crop_norm = None
        self.crop_status_label.setText("No crop selected")
        self._update_preview()
        self._update_estimate()

    def _on_end_changed(self) -> None:
        if self.end_spin.value() < self.start_spin.value():
            self.start_spin.blockSignals(True)
            self.start_spin.setValue(self.end_spin.value())
            self.start_spin.blockSignals(False)
        self._update_estimate()

    def _open_crop_dialog(self) -> None:
        if self._preview_frame is None:
            QMessageBox.warning(self, "No preview", "Could not read a frame to crop from this video.")
            return
        dialog = CropDialog(self._preview_frame, parent=self)
        if dialog.exec():
            rect = dialog.normalized_rect()
            if rect is not None:
                self._crop_norm = rect
                self.crop_status_label.setText("Crop selected")
            else:
                self._crop_norm = None
                self.crop_status_label.setText("No crop selected")

    def _update_estimate(self) -> None:
        start = self.start_spin.value()
        end = self.end_spin.value()
        duration = max(0.0, end - start)
        sample_fps = self.sample_fps_spin.value()
        speed = self.speed_spin.value()
        frame_count = min(max(1, round(duration * sample_fps)), MAX_EXTRACTED_FRAMES)
        output_duration = duration / speed if speed > 0 else duration
        delay_ms = max(20, round((output_duration * 1000) / frame_count)) if frame_count else 200
        self._estimated_frame_count = frame_count
        self._estimated_delay_ms = delay_ms
        capped_note = f" (capped at {MAX_EXTRACTED_FRAMES})" if frame_count == MAX_EXTRACTED_FRAMES else ""
        self.estimate_label.setText(
            f"Will extract {frame_count} frame(s){capped_note}, about {delay_ms} ms each "
            f"(clip length: {duration:.1f}s, output length: {output_duration:.1f}s)."
        )

    def _on_accept(self) -> None:
        start = self.start_spin.value()
        end = self.end_spin.value()
        if end <= start:
            QMessageBox.warning(self, "Invalid range", "The end of the clip must be after the start.")
            return

        crop_box = None
        if self._crop_norm is not None:
            x0, y0, x1, y1 = self._crop_norm
            crop_box = (
                max(0, round(x0 * self.info.width)),
                max(0, round(y0 * self.info.height)),
                min(self.info.width, round(x1 * self.info.width)),
                min(self.info.height, round(y1 * self.info.height)),
            )

        try:
            paths, _ = extract_frames(
                self.video_path, start, end, self.sample_fps_spin.value(), crop_box=crop_box
            )
        except VideoImportError as exc:
            QMessageBox.critical(self, "Import failed", str(exc))
            return

        self.result_frame_paths = paths
        self.result_frame_delay_ms = self._estimated_delay_ms
        self.accept()
