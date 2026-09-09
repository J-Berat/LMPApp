"""PySide6 graphical interface for GIF Maker."""

from __future__ import annotations

import os

from PySide6.QtCore import Qt, QTimer, QSize, QThread, Signal
from PySide6.QtGui import QPixmap, QIcon, QAction, QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QListWidget,
    QListWidgetItem,
    QAbstractItemView,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSplitter,
    QGroupBox,
    QFormLayout,
    QSpinBox,
    QCheckBox,
    QFileDialog,
    QMessageBox,
    QMenu,
    QStatusBar,
    QProgressDialog,
)

from .model import GIFMakerModel
from .gif_exporter import export_gif, ExportError
from .video_exporter import export_mp4

IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tiff", ".webp")
THUMBNAIL_SIZE = QSize(72, 72)


def _is_image_file(path: str) -> bool:
    return path.lower().endswith(IMAGE_EXTENSIONS)


class ImageListWidget(QListWidget):
    """Reorderable list of the images in the sequence, with drag & drop support."""

    filesDropped = Signal(list)
    orderChanged = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setDragDropMode(QAbstractItemView.InternalMove)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setIconSize(THUMBNAIL_SIZE)
        self.model().rowsMoved.connect(lambda *_: self.orderChanged.emit())

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:
        if event.mimeData().hasUrls():
            paths = [url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()]
            paths = [p for p in paths if _is_image_file(p)]
            if paths:
                self.filesDropped.emit(paths)
            event.acceptProposedAction()
        else:
            super().dropEvent(event)


class PreviewWidget(QWidget):
    """Animated preview of the sequence, with play/pause."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._paths: list[str] = []
        self._delay_ms = 200
        self._index = 0
        self._playing = True

        self.image_label = QLabel("Add images to see the preview")
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setMinimumSize(320, 320)
        self.image_label.setStyleSheet("QLabel { background: #202020; color: #aaaaaa; border-radius: 6px; }")

        self.play_button = QPushButton("⏸ Pause")
        self.play_button.clicked.connect(self.toggle_play)

        self.frame_label = QLabel("")
        self.frame_label.setAlignment(Qt.AlignCenter)

        controls = QHBoxLayout()
        controls.addWidget(self.play_button)
        controls.addStretch(1)
        controls.addWidget(self.frame_label)

        layout = QVBoxLayout(self)
        layout.addWidget(self.image_label, 1)
        layout.addLayout(controls)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._advance_frame)

    def toggle_play(self) -> None:
        self._playing = not self._playing
        self.play_button.setText("⏸ Pause" if self._playing else "▶ Play")
        if self._playing:
            self.timer.start(self._delay_ms)
        else:
            self.timer.stop()

    def set_sequence(self, paths: list[str], delay_ms: int) -> None:
        self._paths = paths
        self._delay_ms = max(20, delay_ms)
        self._index = 0
        self.timer.stop()
        if not paths:
            self.image_label.setText("Add images to see the preview")
            self.image_label.setPixmap(QPixmap())
            self.frame_label.setText("")
            return
        self._show_current_frame()
        if self._playing and len(paths) > 1:
            self.timer.start(self._delay_ms)

    def _advance_frame(self) -> None:
        if not self._paths:
            return
        self._index = (self._index + 1) % len(self._paths)
        self._show_current_frame()

    def _show_current_frame(self) -> None:
        path = self._paths[self._index]
        pixmap = QPixmap(path)
        if not pixmap.isNull():
            scaled = pixmap.scaled(
                self.image_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            self.image_label.setPixmap(scaled)
        self.frame_label.setText(f"Frame {self._index + 1} / {len(self._paths)}")


class SettingsPanel(QWidget):
    """Resizing, timing and looping settings."""

    settingsEdited = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        timing_box = QGroupBox("Timing")
        self.delay_spin = QSpinBox()
        self.delay_spin.setRange(20, 5000)
        self.delay_spin.setSingleStep(10)
        self.delay_spin.setSuffix(" ms")
        self.delay_spin.setValue(200)
        self.delay_spin.valueChanged.connect(self.settingsEdited)

        self.loop_check = QCheckBox("Loop forever")
        self.loop_check.setChecked(True)
        self.loop_check.stateChanged.connect(self.settingsEdited)

        timing_form = QFormLayout(timing_box)
        timing_form.addRow("Delay between frames:", self.delay_spin)
        timing_form.addRow(self.loop_check)

        resize_box = QGroupBox("Resize")
        resize_box.setCheckable(True)
        resize_box.setChecked(False)
        resize_box.toggled.connect(self.settingsEdited)
        self.resize_box = resize_box

        self.width_spin = QSpinBox()
        self.width_spin.setRange(1, 8000)
        self.width_spin.setValue(480)
        self.width_spin.valueChanged.connect(self.settingsEdited)

        self.height_spin = QSpinBox()
        self.height_spin.setRange(1, 8000)
        self.height_spin.setValue(480)
        self.height_spin.valueChanged.connect(self.settingsEdited)

        self.keep_aspect_check = QCheckBox("Keep aspect ratio")
        self.keep_aspect_check.setChecked(True)
        self.keep_aspect_check.stateChanged.connect(self.settingsEdited)

        resize_form = QFormLayout(resize_box)
        resize_form.addRow("Width:", self.width_spin)
        resize_form.addRow("Height:", self.height_spin)
        resize_form.addRow(self.keep_aspect_check)

        layout = QVBoxLayout(self)
        layout.addWidget(timing_box)
        layout.addWidget(resize_box)
        layout.addStretch(1)

    def apply_to(self, model: GIFMakerModel) -> None:
        model.update_settings(
            frame_delay_ms=self.delay_spin.value(),
            loop_count=0 if self.loop_check.isChecked() else 1,
            resize_enabled=self.resize_box.isChecked(),
            resize_width=self.width_spin.value(),
            resize_height=self.height_spin.value(),
            keep_aspect_ratio=self.keep_aspect_check.isChecked(),
        )


class ExportThread(QThread):
    """Runs the export in a background thread so the UI never freezes."""

    finished_ok = Signal(str)
    failed = Signal(str)

    def __init__(self, kind: str, paths: list[str], output_path: str, settings, parent=None) -> None:
        super().__init__(parent)
        self.kind = kind
        self.paths = paths
        self.output_path = output_path
        self.settings = settings

    def run(self) -> None:
        try:
            if self.kind == "gif":
                export_gif(self.paths, self.output_path, self.settings)
            else:
                export_mp4(self.paths, self.output_path, self.settings)
        except ExportError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:  # pragma: no cover - safety net for the UI
            self.failed.emit(f"Export failed: {exc}")
        else:
            self.finished_ok.emit(self.output_path)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("GIF Maker")
        self.resize(980, 620)
        self.setAcceptDrops(True)

        self.model = GIFMakerModel()
        self._export_thread: ExportThread | None = None
        self._progress: QProgressDialog | None = None

        self._build_ui()
        self._connect_signals()
        self.setStatusBar(QStatusBar())

    # -- Building the interface -----------------------------------------------

    def _build_ui(self) -> None:
        # Left panel: image list
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.addWidget(QLabel("Images (drag & drop, or use the Add button)"))

        self.list_widget = ImageListWidget()
        left_layout.addWidget(self.list_widget, 1)

        buttons_row = QHBoxLayout()
        self.add_button = QPushButton("Add…")
        self.remove_button = QPushButton("Remove")
        self.clear_button = QPushButton("Clear all")
        buttons_row.addWidget(self.add_button)
        buttons_row.addWidget(self.remove_button)
        buttons_row.addWidget(self.clear_button)
        left_layout.addLayout(buttons_row)

        # Center: preview
        self.preview = PreviewWidget()

        # Right: settings + export
        right = QWidget()
        right_layout = QVBoxLayout(right)
        self.settings_panel = SettingsPanel()
        right_layout.addWidget(self.settings_panel)

        self.export_gif_button = QPushButton("Export as GIF…")
        self.export_mp4_button = QPushButton("Export as MP4…")
        right_layout.addWidget(self.export_gif_button)
        right_layout.addWidget(self.export_mp4_button)
        right_layout.addStretch(1)

        splitter = QSplitter()
        splitter.addWidget(left)
        splitter.addWidget(self.preview)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)
        splitter.setStretchFactor(2, 2)

        self.setCentralWidget(splitter)

        self.list_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self._show_list_context_menu)

    def _connect_signals(self) -> None:
        self.list_widget.filesDropped.connect(self._add_images)
        self.list_widget.orderChanged.connect(self._sync_order_from_widget)
        self.add_button.clicked.connect(self._choose_files)
        self.remove_button.clicked.connect(self._remove_selected)
        self.clear_button.clicked.connect(self._clear_all)
        self.settings_panel.settingsEdited.connect(self._on_settings_edited)
        self.export_gif_button.clicked.connect(lambda: self._export("gif"))
        self.export_mp4_button.clicked.connect(lambda: self._export("mp4"))
        self.model.images_changed.connect(self._refresh_list)
        self.model.images_changed.connect(self._refresh_preview)
        self.model.settings_changed.connect(self._refresh_preview)

    # -- Drag & drop onto the whole window --------------------------------------

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        if event.mimeData().hasUrls():
            paths = [url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()]
            paths = [p for p in paths if _is_image_file(p)]
            self._add_images(paths)

    # -- List actions ---------------------------------------------------------

    def _choose_files(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Choose images",
            "",
            "Images (*.png *.jpg *.jpeg *.bmp *.gif *.tiff *.webp)",
        )
        if paths:
            self._add_images(paths)

    def _add_images(self, paths: list[str]) -> None:
        if paths:
            self.model.add_images(paths)

    def _remove_selected(self) -> None:
        ids = [item.data(Qt.UserRole) for item in self.list_widget.selectedItems()]
        if ids:
            self.model.remove_images(ids)

    def _clear_all(self) -> None:
        self.model.clear()

    def _show_list_context_menu(self, pos) -> None:
        item = self.list_widget.itemAt(pos)
        if item is None:
            return
        menu = QMenu(self)
        remove_action = QAction("Remove", self)
        remove_action.triggered.connect(lambda: self.model.remove_images([item.data(Qt.UserRole)]))
        menu.addAction(remove_action)
        menu.exec(self.list_widget.mapToGlobal(pos))

    def _sync_order_from_widget(self) -> None:
        ordered_ids = [
            self.list_widget.item(i).data(Qt.UserRole) for i in range(self.list_widget.count())
        ]
        by_id = {item.id: item for item in self.model.images}
        self.model.images = [by_id[i] for i in ordered_ids if i in by_id]
        self.model.images_changed.emit()

    def _refresh_list(self) -> None:
        self.list_widget.blockSignals(True)
        self.list_widget.clear()
        for item in self.model.images:
            list_item = QListWidgetItem(item.filename)
            list_item.setData(Qt.UserRole, item.id)
            pixmap = QPixmap(item.path)
            if not pixmap.isNull():
                thumb = pixmap.scaled(
                    THUMBNAIL_SIZE, Qt.KeepAspectRatio, Qt.SmoothTransformation
                )
                list_item.setIcon(QIcon(thumb))
            self.list_widget.addItem(list_item)
        self.list_widget.blockSignals(False)

    def _on_settings_edited(self) -> None:
        self.settings_panel.apply_to(self.model)

    def _refresh_preview(self) -> None:
        self.preview.set_sequence(self.model.image_paths(), self.model.settings.frame_delay_ms)

    # -- Export -----------------------------------------------------------------------

    def _export(self, kind: str) -> None:
        if not self.model.images:
            QMessageBox.warning(
                self, "Cannot export", "Add at least one image before exporting."
            )
            return

        if kind == "gif":
            path, _ = QFileDialog.getSaveFileName(
                self, "Choose a name and location for the GIF file", "animation.gif", "GIF (*.gif)"
            )
        else:
            path, _ = QFileDialog.getSaveFileName(
                self, "Choose a name and location for the MP4 file", "animation.mp4", "MP4 video (*.mp4)"
            )
        if not path:
            return

        self._progress = QProgressDialog(f"Exporting {kind.upper()}…", None, 0, 0, self)
        self._progress.setWindowModality(Qt.WindowModal)
        self._progress.setCancelButton(None)
        self._progress.show()

        self._export_thread = ExportThread(kind, self.model.image_paths(), path, self.model.settings, self)
        self._export_thread.finished_ok.connect(self._on_export_success)
        self._export_thread.failed.connect(self._on_export_failed)
        self._export_thread.start()

    def _on_export_success(self, path: str) -> None:
        if self._progress:
            self._progress.close()
        self.statusBar().showMessage(f"Exported: {path}", 5000)
        QMessageBox.information(self, "Export complete", f"File created:\n{path}")

    def _on_export_failed(self, message: str) -> None:
        if self._progress:
            self._progress.close()
        QMessageBox.critical(self, "Export failed", message)


def run() -> None:
    app = QApplication.instance() or QApplication([])
    app.setApplicationName("GIF Maker")
    icon_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "AppIcon.png")
    if os.path.isfile(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    window = MainWindow()
    window.show()
    app.exec()


if __name__ == "__main__":
    run()
