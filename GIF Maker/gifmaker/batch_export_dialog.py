"""Dialog for converting several video files to GIF/MP4/WebP in one go,
all sharing the same trim/sample-rate/speed/crop and the export settings
currently configured in the main window."""

from __future__ import annotations

import dataclasses
import os

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLabel,
    QListWidget,
    QAbstractItemView,
    QPushButton,
    QCheckBox,
    QDoubleSpinBox,
    QSpinBox,
    QLineEdit,
    QFileDialog,
    QMessageBox,
    QDialogButtonBox,
    QProgressDialog,
)

from .model import GIFSettings
from .video_importer import extract_frame_at, VideoImportError
from .crop_widget import CropDialog
from .batch_export import process_videos, BatchItemResult

VIDEO_FILTER = "Videos (*.mp4 *.mov *.m4v *.avi *.mkv *.webm)"


def _is_video_file(path: str) -> bool:
    return path.lower().endswith((".mp4", ".mov", ".m4v", ".avi", ".mkv", ".webm"))


class _VideoListWidget(QListWidget):
    """Plain drop target for a batch of video files."""

    filesDropped = Signal(list)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            paths = [url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()]
            videos = [p for p in paths if _is_video_file(p)]
            if videos:
                self.filesDropped.emit(videos)
            event.acceptProposedAction()
        else:
            super().dropEvent(event)


class _BatchExportThread(QThread):
    progress = Signal(int, int, str)
    finished_all = Signal(list)

    def __init__(
        self, video_paths, output_dir, formats, base_settings,
        trim_start, trim_end, sample_fps, speed, crop_norm, parent=None,
    ) -> None:
        super().__init__(parent)
        self.video_paths = video_paths
        self.output_dir = output_dir
        self.formats = formats
        self.base_settings = base_settings
        self.trim_start = trim_start
        self.trim_end = trim_end
        self.sample_fps = sample_fps
        self.speed = speed
        self.crop_norm = crop_norm

    def run(self) -> None:
        def on_progress(done: int, total: int, result: BatchItemResult) -> None:
            name = os.path.basename(result.video_path)
            message = f"{name} - failed: {result.error}" if result.error else f"{name} - done"
            self.progress.emit(done, total, message)

        results = process_videos(
            self.video_paths, self.output_dir, self.formats, self.base_settings,
            self.trim_start, self.trim_end, self.sample_fps, self.speed, self.crop_norm,
            progress_callback=on_progress,
        )
        self.finished_all.emit(results)


class BatchExportDialog(QDialog):
    """Convert a batch of video files to GIF/MP4/WebP with one shared set
    of trim/sample-rate/speed/crop settings and the export settings the
    user already configured in the main window (resize, loop, ping-pong,
    palette, watermark)."""

    def __init__(self, base_settings: GIFSettings, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Batch export videos")
        self.resize(520, 560)
        self.base_settings = base_settings
        self._crop_norm: tuple[float, float, float, float] | None = None
        self._thread: _BatchExportThread | None = None
        self._progress_dialog: QProgressDialog | None = None

        self.video_list = _VideoListWidget()
        self.video_list.filesDropped.connect(self._add_videos)

        add_btn = QPushButton("Add videos…")
        remove_btn = QPushButton("Remove selected")
        add_btn.clicked.connect(self._choose_videos)
        remove_btn.clicked.connect(self._remove_selected)

        list_buttons = QHBoxLayout()
        list_buttons.addWidget(add_btn)
        list_buttons.addWidget(remove_btn)
        list_buttons.addStretch(1)

        self.trim_check = QCheckBox("Trim to a specific range (unchecked: use each video's full length)")
        self.trim_check.stateChanged.connect(self._on_trim_toggled)

        self.start_spin = QDoubleSpinBox()
        self.start_spin.setRange(0.0, 100000.0)
        self.start_spin.setSuffix(" s")
        self.start_spin.setEnabled(False)

        self.end_spin = QDoubleSpinBox()
        self.end_spin.setRange(0.0, 100000.0)
        self.end_spin.setSuffix(" s")
        self.end_spin.setValue(10.0)
        self.end_spin.setEnabled(False)

        self.sample_fps_spin = QSpinBox()
        self.sample_fps_spin.setRange(1, 30)
        self.sample_fps_spin.setValue(10)
        self.sample_fps_spin.setSuffix(" fps")

        self.speed_spin = QDoubleSpinBox()
        self.speed_spin.setRange(0.1, 4.0)
        self.speed_spin.setSingleStep(0.1)
        self.speed_spin.setValue(1.0)
        self.speed_spin.setSuffix("x")

        self.crop_button = QPushButton("Crop (from the first video)…")
        self.crop_status_label = QLabel("No crop selected")
        self.crop_button.clicked.connect(self._open_crop_dialog)
        crop_row = QHBoxLayout()
        crop_row.addWidget(self.crop_button)
        crop_row.addWidget(self.crop_status_label, 1)

        form = QFormLayout()
        form.addRow(self.trim_check)
        form.addRow("Start:", self.start_spin)
        form.addRow("End:", self.end_spin)
        form.addRow("Sample rate:", self.sample_fps_spin)
        form.addRow("Speed:", self.speed_spin)

        self.gif_check = QCheckBox("GIF")
        self.gif_check.setChecked(True)
        self.mp4_check = QCheckBox("MP4")
        self.webp_check = QCheckBox("WebP")
        formats_row = QHBoxLayout()
        formats_row.addWidget(QLabel("Export as:"))
        formats_row.addWidget(self.gif_check)
        formats_row.addWidget(self.mp4_check)
        formats_row.addWidget(self.webp_check)
        formats_row.addStretch(1)

        self.output_dir_edit = QLineEdit()
        self.output_dir_edit.setReadOnly(True)
        self.output_dir_edit.setPlaceholderText("Choose an output folder…")
        choose_dir_btn = QPushButton("Choose…")
        choose_dir_btn.clicked.connect(self._choose_output_dir)
        output_row = QHBoxLayout()
        output_row.addWidget(QLabel("Output folder:"))
        output_row.addWidget(self.output_dir_edit, 1)
        output_row.addWidget(choose_dir_btn)

        note = QLabel(
            "Every video below is converted with the same trim/speed/crop and the "
            "resize, loop, palette and watermark settings currently set in the main window."
        )
        note.setWordWrap(True)

        buttons = QDialogButtonBox(QDialogButtonBox.Cancel)
        buttons.rejected.connect(self.reject)
        self.start_button = QPushButton("Start batch export")
        self.start_button.clicked.connect(self._start_export)
        buttons.addButton(self.start_button, QDialogButtonBox.AcceptRole)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Videos to convert (drag & drop, or use the button below):"))
        layout.addWidget(self.video_list, 1)
        layout.addLayout(list_buttons)
        layout.addLayout(form)
        layout.addLayout(crop_row)
        layout.addLayout(formats_row)
        layout.addLayout(output_row)
        layout.addWidget(note)
        layout.addWidget(buttons)

    # -- Video list -------------------------------------------------------------------

    def _choose_videos(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(self, "Choose videos", "", VIDEO_FILTER)
        if paths:
            self._add_videos(paths)

    def _add_videos(self, paths: list[str]) -> None:
        existing = {self.video_list.item(i).text() for i in range(self.video_list.count())}
        for path in paths:
            if path not in existing:
                self.video_list.addItem(path)
                existing.add(path)

    def _remove_selected(self) -> None:
        for item in self.video_list.selectedItems():
            self.video_list.takeItem(self.video_list.row(item))

    def _video_paths(self) -> list[str]:
        return [self.video_list.item(i).text() for i in range(self.video_list.count())]

    # -- Trim / crop --------------------------------------------------------------------

    def _on_trim_toggled(self) -> None:
        enabled = self.trim_check.isChecked()
        self.start_spin.setEnabled(enabled)
        self.end_spin.setEnabled(enabled)

    def _open_crop_dialog(self) -> None:
        paths = self._video_paths()
        if not paths:
            QMessageBox.information(self, "No video yet", "Add at least one video first.")
            return
        start = self.start_spin.value() if self.trim_check.isChecked() else 0.0
        try:
            frame = extract_frame_at(paths[0], start)
        except VideoImportError as exc:
            QMessageBox.critical(self, "Cannot read a preview frame", str(exc))
            return
        dialog = CropDialog(frame, parent=self)
        if dialog.exec():
            rect = dialog.normalized_rect()
            self._crop_norm = rect
            self.crop_status_label.setText("Crop selected" if rect is not None else "No crop selected")

    def _choose_output_dir(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "Choose an output folder")
        if directory:
            self.output_dir_edit.setText(directory)

    # -- Running the batch --------------------------------------------------------------

    def _start_export(self) -> None:
        video_paths = self._video_paths()
        if not video_paths:
            QMessageBox.warning(self, "Nothing to export", "Add at least one video first.")
            return
        formats = [
            fmt for fmt, box in (("gif", self.gif_check), ("mp4", self.mp4_check), ("webp", self.webp_check))
            if box.isChecked()
        ]
        if not formats:
            QMessageBox.warning(self, "Nothing to export", "Choose at least one output format.")
            return
        output_dir = self.output_dir_edit.text().strip()
        if not output_dir or not os.path.isdir(output_dir):
            QMessageBox.warning(self, "No output folder", "Choose an output folder first.")
            return

        trim_start = self.start_spin.value() if self.trim_check.isChecked() else None
        trim_end = self.end_spin.value() if self.trim_check.isChecked() else None

        self.start_button.setEnabled(False)
        self._progress_dialog = QProgressDialog("Starting…", None, 0, len(video_paths), self)
        self._progress_dialog.setWindowModality(Qt.WindowModal)
        self._progress_dialog.setCancelButton(None)
        self._progress_dialog.show()

        self._thread = _BatchExportThread(
            video_paths, output_dir, formats, dataclasses.replace(self.base_settings),
            trim_start, trim_end, self.sample_fps_spin.value(), self.speed_spin.value(), self._crop_norm,
            parent=self,
        )
        self._thread.progress.connect(self._on_progress)
        self._thread.finished_all.connect(self._on_finished)
        self._thread.start()

    def _on_progress(self, done: int, total: int, message: str) -> None:
        if self._progress_dialog:
            self._progress_dialog.setMaximum(total)
            self._progress_dialog.setValue(done)
            self._progress_dialog.setLabelText(message)

    def _on_finished(self, results: list) -> None:
        if self._progress_dialog:
            self._progress_dialog.close()
        self.start_button.setEnabled(True)

        succeeded = [r for r in results if not r.error]
        failed = [r for r in results if r.error]
        lines = [f"{len(succeeded)} of {len(results)} video(s) converted successfully."]
        if failed:
            lines.append("")
            lines.append("Failed:")
            for r in failed:
                lines.append(f"  {os.path.basename(r.video_path)}: {r.error}")
        QMessageBox.information(self, "Batch export complete", "\n".join(lines))
        if not failed:
            self.accept()
