from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QComboBox, QHeaderView,
)
from PySide6.QtCore import Qt, Signal

from src.core.models import TagConflict

import logging
logger = logging.getLogger(__name__)

_COL_FILE = 0
_COL_FIELD = 1
_COL_CURRENT = 2
_COL_FOUND = 3
_COL_RESOLUTION = 4

_FIELD_LABELS = {
    "title": "Title",
    "artist": "Artist",
    "album": "Album",
    "album_artist": "Album Artist",
    "track_number": "Track #",
    "year": "Year",
}

_OPT_KEEP = "Keep"
_OPT_USE = "Use Found"


class AutoTagReview(QWidget):
    """Conflict review page for Auto-Tag metadata lookup results."""

    apply_requested = Signal(list)  # list[TagConflict] — only conflicts with resolution="incoming"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._conflicts: list[TagConflict] = []
        self._build_ui()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_conflicts(self, conflicts: list[TagConflict]) -> None:
        self._conflicts = conflicts
        self._populate_table(conflicts)
        self._update_status()

    def conflict_count(self) -> int:
        return self._table.rowCount()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(6)

        outer.addWidget(QLabel(
            "Review the metadata found via AcoustID / MusicBrainz. "
            "Choose which values to keep for each track."
        ))

        # Bulk toggle buttons
        bulk_row = QHBoxLayout()
        btn_use_all = QPushButton("Use Found for All")
        btn_keep_all = QPushButton("Keep All")
        btn_use_all.clicked.connect(lambda: self._bulk_set(_OPT_USE))
        btn_keep_all.clicked.connect(lambda: self._bulk_set(_OPT_KEEP))
        bulk_row.addWidget(btn_use_all)
        bulk_row.addWidget(btn_keep_all)
        bulk_row.addStretch()
        outer.addLayout(bulk_row)

        # Conflict table
        self._table = QTableWidget(0, 5)
        self._table.setHorizontalHeaderLabels(["File", "Field", "Current Value", "Found Value", "Resolution"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self._table.verticalHeader().setVisible(False)
        self._table.setAlternatingRowColors(True)
        outer.addWidget(self._table, stretch=1)

        # Status + action buttons
        bottom_row = QHBoxLayout()
        self._status_label = QLabel("")
        self._apply_btn = QPushButton("Apply Changes")
        self._apply_btn.setEnabled(False)
        self._apply_btn.clicked.connect(self._apply)
        btn_skip = QPushButton("Skip All")
        btn_skip.clicked.connect(self._skip)
        bottom_row.addWidget(self._status_label, stretch=1)
        bottom_row.addWidget(btn_skip)
        bottom_row.addWidget(self._apply_btn)
        outer.addLayout(bottom_row)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _populate_table(self, conflicts: list[TagConflict]) -> None:
        self._table.setRowCount(0)
        for conflict in conflicts:
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setItem(row, _COL_FILE, QTableWidgetItem(conflict.file_path.name))
            self._table.setItem(row, _COL_FIELD, QTableWidgetItem(
                _FIELD_LABELS.get(conflict.field, conflict.field)
            ))
            self._table.setItem(row, _COL_CURRENT, QTableWidgetItem(conflict.local_value))
            self._table.setItem(row, _COL_FOUND, QTableWidgetItem(conflict.incoming_value))
            combo = QComboBox()
            combo.addItems([_OPT_KEEP, _OPT_USE])
            # Default: Use Found when current is empty, Keep otherwise
            combo.setCurrentText(_OPT_USE if not conflict.local_value else _OPT_KEEP)
            combo.currentTextChanged.connect(self._update_apply_button)
            self._table.setCellWidget(row, _COL_RESOLUTION, combo)
        self._update_apply_button()

    def _update_status(self) -> None:
        n = len(self._conflicts)
        self._status_label.setText(
            f"{n} conflict{'s' if n != 1 else ''} found." if n else "No conflicts."
        )

    def _bulk_set(self, choice: str) -> None:
        for row in range(self._table.rowCount()):
            combo: QComboBox = self._table.cellWidget(row, _COL_RESOLUTION)
            if combo:
                combo.setCurrentText(choice)

    def _update_apply_button(self, *_args) -> None:
        any_use_found = any(
            (combo := self._table.cellWidget(row, _COL_RESOLUTION)) is not None
            and combo.currentText() == _OPT_USE
            for row in range(self._table.rowCount())
        )
        self._apply_btn.setEnabled(any_use_found)

    def _apply(self) -> None:
        accepted: list[TagConflict] = []
        for row, conflict in enumerate(self._conflicts):
            combo: QComboBox = self._table.cellWidget(row, _COL_RESOLUTION)
            if combo and combo.currentText() == _OPT_USE:
                conflict.resolution = "incoming"
                accepted.append(conflict)
            else:
                conflict.resolution = "local"
        self.apply_requested.emit(accepted)

    def _skip(self) -> None:
        self.apply_requested.emit([])
