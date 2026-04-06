from __future__ import annotations
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFileDialog,
)
from PySide6.QtCore import Qt, Signal, QBuffer, QIODevice
from PySide6.QtGui import QPixmap, QImage

from src.core.artwork import read_artwork
from src.core.models import Track

import logging
logger = logging.getLogger(__name__)

_MAX_DISPLAY_PX = 200
_MAX_DIMENSION_PX = 3000
_MAX_FILE_BYTES = 10 * 1024 * 1024  # 10 MB


class ArtworkPanel(QWidget):
    scan_requested = Signal(list)          # list[Track]
    upload_requested = Signal(list, bytes) # list[Track], validated image bytes

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tracks: list[Track] = []
        self._build_ui()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_track(self, track: Track) -> None:
        self._tracks = [track]
        self._set_batch_mode(False)
        self._status_label.setText("")
        self._warning_label.setVisible(False)
        data = read_artwork(track.file_path)
        if data:
            self.show_artwork(data)
        else:
            self._show_placeholder()

    def load_batch(self, tracks: list[Track]) -> None:
        self._tracks = tracks
        self._set_batch_mode(True)
        self._batch_label.setText(f"{len(tracks)} tracks selected")
        self._status_label.setText("")
        self._warning_label.setVisible(False)

    def clear(self) -> None:
        self._tracks = []
        self._set_batch_mode(False)
        self._show_placeholder()
        self._status_label.setText("")
        self._warning_label.setVisible(False)

    def set_scanning(self, scanning: bool) -> None:
        self._scan_btn.setEnabled(not scanning)
        self._upload_btn.setEnabled(not scanning)
        self._batch_scan_btn.setEnabled(not scanning)
        self._batch_upload_btn.setEnabled(not scanning)
        if scanning:
            self._status_label.setText("Searching…")
        else:
            if self._status_label.text() == "Searching…":
                self._status_label.setText("")

    def show_artwork(self, image_data: bytes) -> None:
        pixmap = QPixmap()
        pixmap.loadFromData(image_data)
        if pixmap.isNull():
            logger.warning("ArtworkPanel: could not render image data")
            self._show_placeholder()
            return
        scaled = pixmap.scaled(
            _MAX_DISPLAY_PX, _MAX_DISPLAY_PX,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._image_label.setPixmap(scaled)
        self._placeholder_label.setVisible(False)
        self._image_label.setVisible(True)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Image display
        self._image_label = QLabel()
        self._image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._image_label.setFixedSize(_MAX_DISPLAY_PX, _MAX_DISPLAY_PX)
        self._image_label.setVisible(False)
        layout.addWidget(self._image_label, alignment=Qt.AlignmentFlag.AlignHCenter)

        # Placeholder
        self._placeholder_label = QLabel("🎵\nNo artwork")
        self._placeholder_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._placeholder_label.setFixedSize(_MAX_DISPLAY_PX, _MAX_DISPLAY_PX)
        self._placeholder_label.setStyleSheet(
            "background: #2a2a4a; color: #888; border-radius: 4px; font-size: 24px;"
        )
        layout.addWidget(self._placeholder_label, alignment=Qt.AlignmentFlag.AlignHCenter)

        # Single-track buttons
        self._single_btns = QWidget()
        single_row = QHBoxLayout(self._single_btns)
        single_row.setContentsMargins(0, 0, 0, 0)
        self._scan_btn = QPushButton("Scan")
        self._upload_btn = QPushButton("Upload")
        single_row.addWidget(self._scan_btn)
        single_row.addWidget(self._upload_btn)
        layout.addWidget(self._single_btns)

        # Batch-mode UI
        self._batch_widget = QWidget()
        batch_layout = QVBoxLayout(self._batch_widget)
        batch_layout.setContentsMargins(0, 0, 0, 0)
        batch_layout.setSpacing(4)
        self._batch_label = QLabel("")
        self._batch_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        batch_row = QHBoxLayout()
        self._batch_scan_btn = QPushButton("Scan all")
        self._batch_upload_btn = QPushButton("Upload to all")
        batch_row.addWidget(self._batch_scan_btn)
        batch_row.addWidget(self._batch_upload_btn)
        batch_layout.addWidget(self._batch_label)
        batch_layout.addLayout(batch_row)
        layout.addWidget(self._batch_widget)
        self._batch_widget.setVisible(False)

        # Status label
        self._status_label = QLabel("")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_label.setStyleSheet("color: #aaa; font-size: 11px;")
        layout.addWidget(self._status_label)

        # Aspect ratio warning
        self._warning_label = QLabel("⚠ Not square — may look cropped in some players")
        self._warning_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._warning_label.setStyleSheet("color: #ffa94d; font-size: 10px;")
        self._warning_label.setWordWrap(True)
        self._warning_label.setVisible(False)
        layout.addWidget(self._warning_label)

        # Wire buttons
        self._scan_btn.clicked.connect(self._on_scan_clicked)
        self._upload_btn.clicked.connect(self._on_upload_clicked)
        self._batch_scan_btn.clicked.connect(self._on_scan_clicked)
        self._batch_upload_btn.clicked.connect(self._on_upload_clicked)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _show_placeholder(self) -> None:
        self._image_label.setVisible(False)
        self._placeholder_label.setVisible(True)

    def _set_batch_mode(self, batch: bool) -> None:
        self._batch_widget.setVisible(batch)
        self._single_btns.setVisible(not batch)
        self._image_label.setVisible(False)
        self._placeholder_label.setVisible(not batch)

    def _on_scan_clicked(self) -> None:
        if self._tracks:
            self.scan_requested.emit(self._tracks)

    def _on_upload_clicked(self) -> None:
        if not self._tracks:
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Select artwork", "", "Images (*.jpg *.jpeg *.png)"
        )
        if not path:
            return
        image_bytes = self._validate_and_process_image(path)
        if image_bytes is not None:
            self.upload_requested.emit(self._tracks, image_bytes)

    def _validate_and_process_image(self, path: str) -> bytes | None:
        # 1. Check file size before loading
        try:
            raw = Path(path).read_bytes()
        except OSError:
            self._status_label.setText("Could not read file")
            return None
        if len(raw) > _MAX_FILE_BYTES:
            self._status_label.setText("File too large (max 10 MB)")
            return None

        # 2. Load with QImage
        img = QImage(path)
        if img.isNull():
            self._status_label.setText("Not a valid image")
            return None

        # 3. Resize if over 3000px in either dimension
        if img.width() > _MAX_DIMENSION_PX or img.height() > _MAX_DIMENSION_PX:
            img = img.scaled(
                _MAX_DIMENSION_PX, _MAX_DIMENSION_PX,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )

        # 4. Warn if not square
        self._warning_label.setVisible(img.width() != img.height())

        # 5. Convert to bytes
        buf = QBuffer()
        buf.open(QIODevice.OpenModeFlag.WriteOnly)
        fmt = "PNG" if path.lower().endswith(".png") else "JPEG"
        img.save(buf, fmt)
        result = bytes(buf.data())
        buf.close()
        return result
