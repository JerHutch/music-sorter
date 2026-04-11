from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QProgressBar,
    QTableWidget, QTableWidgetItem, QComboBox,
    QFileDialog, QHeaderView,
)
from PySide6.QtCore import Qt, Signal

from src.core.models import TagConflict, Track
from src.gui.workers import ITunesWorker

import logging
logger = logging.getLogger(__name__)

_COL_PATH = 0
_COL_FIELD = 1
_COL_FILE_VAL = 2
_COL_ITUNES_VAL = 3
_COL_ACTION = 4

_CONFLICT_FIELDS = ["title", "artist", "album_artist", "album", "genre", "year", "track_number", "bpm"]


class ITunesImport(QWidget):
    """iTunes XML import with conflict resolution."""

    apply_requested = Signal(list)  # list[TagConflict] with resolution set

    def __init__(self, parent=None):
        super().__init__(parent)
        self._conflicts: list[TagConflict] = []
        self._worker: ITunesWorker | None = None
        self._tracks: list[Track] = []
        self._source_dirs: list[Path] = []
        self._xml_path: Path | None = None
        self._build_ui()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_tracks(self, tracks: list[Track], source_dirs: list[Path]) -> None:
        self._tracks = tracks
        self._source_dirs = source_dirs

    def load_conflicts(self, conflicts: list[TagConflict]) -> None:
        self._conflicts = conflicts
        self._populate_table(conflicts)
        self._update_status()

    def conflict_count(self) -> int:
        return self._table.rowCount()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(6)

        # File picker row
        file_row = QHBoxLayout()
        self._path_label = QLabel("No iTunes XML selected")
        self._path_label.setStyleSheet("color: #888;")
        browse_btn = QPushButton("Browse…")
        browse_btn.clicked.connect(self._browse_xml)
        self._import_btn = QPushButton("Import")
        self._import_btn.setEnabled(False)
        self._import_btn.clicked.connect(self._start_import)
        file_row.addWidget(QLabel("iTunes Library XML:"))
        file_row.addWidget(self._path_label, stretch=1)
        file_row.addWidget(browse_btn)
        file_row.addWidget(self._import_btn)
        outer.addLayout(file_row)

        # Progress bar
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 0)  # indeterminate
        self._progress_bar.setVisible(False)
        outer.addWidget(self._progress_bar)

        # Bulk rules row
        rules_row = QHBoxLayout()
        rules_row.addWidget(QLabel("Bulk rules:"))
        self._field_combo = QComboBox()
        for field in _CONFLICT_FIELDS:
            self._field_combo.addItem(field)
        btn_prefer_itunes = QPushButton("Always prefer iTunes for field")
        btn_prefer_file = QPushButton("Always prefer file for field")
        btn_prefer_itunes.clicked.connect(lambda: self._bulk_set_field("incoming"))
        btn_prefer_file.clicked.connect(lambda: self._bulk_set_field("local"))
        rules_row.addWidget(self._field_combo)
        rules_row.addWidget(btn_prefer_itunes)
        rules_row.addWidget(btn_prefer_file)
        rules_row.addStretch()
        outer.addLayout(rules_row)

        # Conflict table
        self._table = QTableWidget(0, 5)
        self._table.setHorizontalHeaderLabels(["File", "Field", "File Value", "iTunes Value", "Use"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self._table.verticalHeader().setVisible(False)
        self._table.setAlternatingRowColors(True)
        outer.addWidget(self._table, stretch=1)

        # Status + apply
        bottom_row = QHBoxLayout()
        self._status_label = QLabel("")
        self._apply_btn = QPushButton("Apply Resolved Conflicts")
        self._apply_btn.setEnabled(False)
        self._apply_btn.clicked.connect(self._apply)
        bottom_row.addWidget(self._status_label, stretch=1)
        bottom_row.addWidget(self._apply_btn)
        outer.addLayout(bottom_row)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _browse_xml(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select iTunes Library XML", "", "XML Files (*.xml)"
        )
        if path:
            self._xml_path = Path(path)
            self._path_label.setText(str(self._xml_path))
            self._path_label.setStyleSheet("")
            self._import_btn.setEnabled(True)

    def _start_import(self) -> None:
        if self._worker and self._worker.isRunning():
            return
        if self._xml_path is None:
            return
        self._progress_bar.setVisible(True)
        self._import_btn.setEnabled(False)
        self._worker = ITunesWorker(self._xml_path, self._tracks, self._source_dirs)
        self._worker.progress.connect(self._status_label.setText)
        self._worker.finished.connect(self._on_import_finished)
        self._worker.error.connect(self._on_import_error)
        self._worker.start()

    def _on_import_finished(self, conflicts: list[TagConflict]) -> None:
        self._progress_bar.setVisible(False)
        self._import_btn.setEnabled(True)
        self.load_conflicts(conflicts)

    def _on_import_error(self, msg: str) -> None:
        self._progress_bar.setVisible(False)
        self._import_btn.setEnabled(True)
        self._status_label.setText(f"Error: {msg}")

    def _populate_table(self, conflicts: list[TagConflict]) -> None:
        self._table.setRowCount(0)
        for conflict in conflicts:
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setItem(row, _COL_PATH, QTableWidgetItem(conflict.file_path.name))
            self._table.setItem(row, _COL_FIELD, QTableWidgetItem(conflict.field))
            self._table.setItem(row, _COL_FILE_VAL, QTableWidgetItem(conflict.local_value))
            self._table.setItem(row, _COL_ITUNES_VAL, QTableWidgetItem(conflict.incoming_value))
            combo = QComboBox()
            combo.addItems(["Keep file", "Use iTunes"])
            self._table.setCellWidget(row, _COL_ACTION, combo)
        self._apply_btn.setEnabled(bool(conflicts))

    def _update_status(self) -> None:
        n = len(self._conflicts)
        self._status_label.setText(
            f"{n} conflict{'s' if n != 1 else ''} to resolve." if n else "No conflicts."
        )

    def _bulk_set_field(self, source: str) -> None:
        field = self._field_combo.currentText()
        choice = "Use iTunes" if source == "incoming" else "Keep file"
        for row in range(self._table.rowCount()):
            field_item = self._table.item(row, _COL_FIELD)
            if field_item and field_item.text() == field:
                combo: QComboBox = self._table.cellWidget(row, _COL_ACTION)
                if combo:
                    combo.setCurrentText(choice)

    def _apply(self) -> None:
        resolved: list[TagConflict] = []
        for row, conflict in enumerate(self._conflicts):
            combo: QComboBox = self._table.cellWidget(row, _COL_ACTION)
            if combo:
                conflict.resolution = "incoming" if combo.currentText() == "Use iTunes" else "local"
                resolved.append(conflict)
        self.apply_requested.emit(resolved)
