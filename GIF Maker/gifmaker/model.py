"""Data model: the image sequence and export settings."""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass, field

from PySide6.QtCore import QObject, Signal


@dataclass
class ImageItem:
    """A single image in the sequence, with a stable id used for reordering."""

    path: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    # Per-frame delay override, in milliseconds. None means "use the
    # sequence's global frame_delay_ms" - only frames the user explicitly
    # customized (e.g. to hold the last frame longer) carry their own value.
    delay_ms: int | None = None

    @property
    def filename(self) -> str:
        return os.path.basename(self.path)


@dataclass
class GIFSettings:
    """Export settings, shared by the GIF, MP4 and WebP exporters."""

    # Delay between two frames, in milliseconds (replaces the old "fps stepper").
    frame_delay_ms: int = 200
    # Number of loops for the GIF/WebP. 0 means infinite loop.
    loop_count: int = 0
    # Play the sequence forward then backward before looping, for a
    # seamless loop instead of a hard cut back to the first frame.
    ping_pong: bool = False
    # Optional resizing.
    resize_enabled: bool = False
    resize_width: int = 480
    resize_height: int = 480
    keep_aspect_ratio: bool = True
    # GIF color palette. Lower colors / no dithering make smaller files at
    # the cost of quality; WebP/MP4 are not palette-based and ignore this.
    color_count: int = 256
    dither: bool = True
    # Optional text burned into every frame (caption or watermark).
    overlay_text: str = ""
    overlay_position: str = "bottom-right"  # top-left/top-right/bottom-left/bottom-right/center
    overlay_font_size: int = 28
    overlay_color: str = "#FFFFFF"
    overlay_opacity: float = 0.85  # 0.0-1.0

    @property
    def fps(self) -> float:
        if self.frame_delay_ms <= 0:
            return 30.0
        return 1000.0 / self.frame_delay_ms


def build_ping_pong_sequence(items: list) -> list:
    """Forward then backward, without repeating the two end items (which
    would create a visible stutter): [a,b,c,d] -> [a,b,c,d,c,b]. A no-op
    for sequences of fewer than 2 items. Generic over the item type so it
    can apply the same forward/backward pattern to a list of paths or a
    parallel list of per-frame delays."""
    if len(items) < 2:
        return list(items)
    return list(items) + list(reversed(items))[1:-1]


class GIFMakerModel(QObject):
    """Application state: the image sequence being edited and its settings."""

    images_changed = Signal()
    settings_changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.images: list[ImageItem] = []
        self.settings = GIFSettings()

    # -- Managing the image list -------------------------------------------------

    def add_images(self, paths: list[str]) -> None:
        added = False
        existing_paths = {item.path for item in self.images}
        for path in paths:
            if path in existing_paths:
                continue
            if not os.path.isfile(path):
                continue
            self.images.append(ImageItem(path=path))
            existing_paths.add(path)
            added = True
        if added:
            self.images_changed.emit()

    def remove_images(self, ids: list[str]) -> None:
        id_set = set(ids)
        before = len(self.images)
        self.images = [item for item in self.images if item.id not in id_set]
        if len(self.images) != before:
            self.images_changed.emit()

    def clear(self) -> None:
        if self.images:
            self.images = []
            self.images_changed.emit()

    def move_image(self, from_index: int, to_index: int) -> None:
        if not (0 <= from_index < len(self.images)):
            return
        item = self.images.pop(from_index)
        to_index = max(0, min(to_index, len(self.images)))
        self.images.insert(to_index, item)
        self.images_changed.emit()

    def reverse_images(self) -> None:
        if len(self.images) > 1:
            self.images.reverse()
            self.images_changed.emit()

    def set_frame_delay(self, image_id: str, delay_ms: int | None) -> None:
        """Override (or, with None, clear the override on) one frame's
        delay. `delay_ms` of None falls back to settings.frame_delay_ms."""
        for item in self.images:
            if item.id == image_id:
                item.delay_ms = delay_ms
                self.images_changed.emit()
                return

    def image_paths(self) -> list[str]:
        return [item.path for item in self.images]

    def effective_image_paths(self) -> list[str]:
        """The paths actually rendered/exported, i.e. the sequence with
        ping-pong applied when enabled."""
        paths = self.image_paths()
        if self.settings.ping_pong:
            paths = build_ping_pong_sequence(paths)
        return paths

    def effective_frame_delays(self) -> list[int]:
        """One delay in milliseconds per frame of effective_image_paths(),
        in the same order - each frame's own override if it has one,
        otherwise the sequence's global frame_delay_ms. Ping-pong applies
        the same forward/backward duplication as effective_image_paths(),
        so a customized frame keeps its own delay on its mirrored copy too."""
        delays = [
            item.delay_ms if item.delay_ms is not None else self.settings.frame_delay_ms
            for item in self.images
        ]
        if self.settings.ping_pong:
            delays = build_ping_pong_sequence(delays)
        return delays

    # -- Settings -----------------------------------------------------------------------

    def update_settings(self, **kwargs) -> None:
        for key, value in kwargs.items():
            if hasattr(self.settings, key):
                setattr(self.settings, key, value)
        self.settings_changed.emit()

    @property
    def total_duration_seconds(self) -> float:
        return len(self.images) * self.settings.frame_delay_ms / 1000.0
