"""Modèle de données : liste d'images et réglages d'export."""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass, field

from PySide6.QtCore import QObject, Signal


@dataclass
class ImageItem:
    """Une image de la séquence, avec un identifiant stable pour le réordonnancement."""

    path: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    @property
    def filename(self) -> str:
        return os.path.basename(self.path)


@dataclass
class GIFSettings:
    """Réglages d'export, communs au GIF et au MP4."""

    # Délai entre deux images, en millisecondes (équivalent de l'ancien "Stepper" fps).
    frame_delay_ms: int = 200
    # Nombre de boucles pour le GIF. 0 = boucle infinie.
    loop_count: int = 0
    # Redimensionnement optionnel.
    resize_enabled: bool = False
    resize_width: int = 480
    resize_height: int = 480
    keep_aspect_ratio: bool = True

    @property
    def fps(self) -> float:
        if self.frame_delay_ms <= 0:
            return 30.0
        return 1000.0 / self.frame_delay_ms


class GIFMakerModel(QObject):
    """État de l'application : la séquence d'images en cours d'édition et les réglages."""

    images_changed = Signal()
    settings_changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.images: list[ImageItem] = []
        self.settings = GIFSettings()

    # -- Gestion de la liste d'images -------------------------------------------------

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

    def image_paths(self) -> list[str]:
        return [item.path for item in self.images]

    # -- Réglages -----------------------------------------------------------------------

    def update_settings(self, **kwargs) -> None:
        for key, value in kwargs.items():
            if hasattr(self.settings, key):
                setattr(self.settings, key, value)
        self.settings_changed.emit()

    @property
    def total_duration_seconds(self) -> float:
        return len(self.images) * self.settings.frame_delay_ms / 1000.0
