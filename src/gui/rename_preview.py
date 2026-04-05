from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QProgressBar,
    QTableWidget, QTableWidgetItem, QLineEdit,
    QGroupBox, QHeaderView,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor

from src.core.models import RenameOperation, Track
from src.core.renamer import render_pattern, generate_rename_plan
from src.gui.workers import RenameWorker

import logging
logger = logging.getLogger(__name__)

_STATUS_COLORS = {
    "complete": QColor("#2ecc71"),
    "skipped":  QColor("#e67e22"),
    "error":    QColor("#e74c3c"),
}


class RenamePreview(QWidget):
    """Pattern editor, dry-run table, and execute workflow for rename/organize."""

    rename_complete = Signal(list)  # list[RenameOperation] after execution

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tracks: list[Track] = []
        self._plan: list[RenameOperation] = []
        self._worker: RenameWorker | None = None
        self._patterns: dict[str, str] = {}
        self._build_ui()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_tracks(self, tracks: list[Track]) -> None:
        self._tracks = tracks
        self._update_preview(self._pattern_input.text())

    def set_patterns(self, patterns: dict[str, str]) -> None:
        self._patterns = patterns
        default = patterns.get("default", "")
        if default:
            self._pattern_input.setText(default)

    def load_plan(self, plan: list[RenameOperation]) -> None:
        self._plan = plan
        self._populate_table(plan)
        self._execute_btn.setEnabled(bool(plan))

    def operation_count(self) -> int:
        return self._table.rowCount()

    def is_execute_enabled(self) -> bool:
        return self._execute_btn.isEnabled()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(6)

        # Pattern editor
        pattern_group = QGroupBox("Rename Pattern")
        pattern_layout = QVBoxLayout(pattern_group)
        pattern_row = QHBoxLayout()
        pattern_row.addWidget(QLabel("Pattern:"))
        self._pattern_input = QLineEdit()
        self._pattern_input.setPlaceholderText(
            "{bucket}/{genre}/{artist} - {title} [{bpm}bpm {key}].mp3"
        )
        self._pattern_input.textChanged.connect(self._update_preview)
        pattern_row.addWidget(self._pattern_input, stretch=1)
        pattern_layout.addLayout(pattern_row)
        self._preview_label = QLabel("Live preview: (select tracks first)")
        self._preview_label.setStyleSheet("color: #888; font-family: monospace;")
        pattern_layout.addWidget(self._preview_label)
        outer.addWidget(pattern_group)

        # Toolbar
        toolbar_row = QHBoxLayout()
        self._dryrun_btn = QPushButton("Generate Dry-Run Preview")
        self._dryrun_btn.clicked.connect(self._run_dryrun)
        self._execute_btn = QPushButton("Execute Rename")
        self._execute_btn.setEnabled(False)
        self._execute_btn.clicked.connect(self._execute)
        toolbar_row.addWidget(self._dryrun_btn)
        toolbar_row.addStretch()
        toolbar_row.addWidget(self._execute_btn)
        outer.addLayout(toolbar_row)

        # Progress bar
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setVisible(False)
        outer.addWidget(self._progress_bar)

        # Rename plan table
        self._table = QTableWidget(0, 3)
        self._table.setHorizontalHeaderLabels(["Current Path", "New Path", "Status"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self._table.verticalHeader().setVisible(False)
        self._table.setAlternatingRowColors(True)
        outer.addWidget(self._table, stretch=1)

        # Status
        self._status_label = QLabel("")
        outer.addWidget(self._status_label)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _update_preview(self, pattern: str) -> None:
        if not self._tracks or not pattern:
            self._preview_label.setText("Live preview: (select tracks first)")
            self._preview_label.setStyleSheet("color: #888; font-family: monospace;")
            return
        sample = self._tracks[0]
        try:
            rendered = render_pattern(pattern, sample)
            self._preview_label.setText(f"Preview: {rendered}")
            self._preview_label.setStyleSheet("color: #2ecc71; font-family: monospace;")
        except Exception as exc:
            self._preview_label.setText(f"Pattern error: {exc}")
            self._preview_label.setStyleSheet("color: #e74c3c; font-family: monospace;")

    def _run_dryrun(self) -> None:
        if not self._tracks:
            self._status_label.setText("No tracks loaded.")
            return
        pattern = self._pattern_input.text().strip()
        if not pattern:
            self._status_label.setText("Enter a rename pattern first.")
            return
        try:
            plan = generate_rename_plan(self._tracks, pattern)
            self.load_plan(plan)
            collisions = sum(1 for op in plan if op.status == "skipped")
            self._status_label.setText(
                f"Dry-run: {len(plan)} rename(s)"
                + (f", {collisions} collision(s) highlighted" if collisions else "")
            )
        except Exception as exc:
            self._status_label.setText(f"Error generating plan: {exc}")

    def _populate_table(self, plan: list[RenameOperation]) -> None:
        self._table.setRowCount(0)
        for op in plan:
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setItem(row, 0, QTableWidgetItem(str(op.source)))
            dest_item = QTableWidgetItem(str(op.destination))
            if op.status == "skipped":
                dest_item.setForeground(QColor("#e74c3c"))
            self._table.setItem(row, 1, dest_item)
            status_item = QTableWidgetItem(op.status)
            color = _STATUS_COLORS.get(op.status)
            if color:
                status_item.setBackground(color)
            self._table.setItem(row, 2, status_item)

    def _execute(self) -> None:
        if not self._plan:
            return
        self._execute_btn.setEnabled(False)
        self._progress_bar.setVisible(True)
        self._worker = RenameWorker(self._plan, dry_run=False)
        self._worker.progress.connect(lambda cur, tot: self._progress_bar.setValue(
            int(cur / tot * 100) if tot else 0))
        self._worker.finished.connect(self._on_execute_finished)
        self._worker.error.connect(self._on_execute_error)
        self._worker.start()

    def _on_execute_finished(self, result: list[RenameOperation]) -> None:
        self._progress_bar.setVisible(False)
        self._plan = result
        self._populate_table(result)
        done = sum(1 for op in result if op.status == "complete")
        self._status_label.setText(f"Done: {done}/{len(result)} files renamed.")
        self._execute_btn.setEnabled(False)
        self.rename_complete.emit(result)

    def _on_execute_error(self, msg: str) -> None:
        self._progress_bar.setVisible(False)
        self._execute_btn.setEnabled(True)
        self._status_label.setText(f"Error: {msg}")
