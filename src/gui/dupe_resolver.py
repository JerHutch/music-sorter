from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QTreeWidget, QTreeWidgetItem, QPushButton, QLabel,
    QProgressBar, QComboBox,
)
from PySide6.QtCore import Qt, Signal

from src.core.models import DupeGroup, Track
from src.gui.workers import DedupeWorker

import logging
logger = logging.getLogger(__name__)

_COL_PATH = 0
_COL_BITRATE = 1
_COL_COMPLETENESS = 2
_COL_ACTION = 3
_DELETE_LABELS = frozenset({"Delete", "Delete (auto)"})


class DupeResolver(QWidget):
    """Review and resolve duplicate track groups."""

    delete_requested = Signal(list)  # list[Track] to delete

    def __init__(self, parent=None):
        super().__init__(parent)
        self._groups: list[DupeGroup] = []
        self._worker: DedupeWorker | None = None
        self._build_ui()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_groups(self, groups: list[DupeGroup]) -> None:
        self._groups = groups
        self._populate_tree(groups)
        self._update_status()

    def start_scan(self, tracks: list[Track], duration_tolerance: float = 2.0,
                   similarity_threshold: float = 0.85) -> None:
        self._progress_bar.setVisible(True)
        self._status_label.setText("Scanning for duplicates…")
        self._scan_btn.setEnabled(False)
        self._worker = DedupeWorker(tracks, duration_tolerance, similarity_threshold)
        self._worker.progress.connect(lambda cur, tot: self._progress_bar.setValue(
            int(cur / tot * 100) if tot else 0))
        self._worker.finished.connect(self._on_scan_finished)
        self._worker.error.connect(self._on_scan_error)
        self._worker.start()

    def group_count(self) -> int:
        return self._tree.topLevelItemCount()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(6)

        toolbar = QHBoxLayout()
        self._scan_btn = QPushButton("Find Duplicates")
        self._auto_resolve_btn = QPushButton("Auto-Resolve All")
        self._auto_resolve_btn.clicked.connect(self._auto_resolve_all)
        self._apply_btn = QPushButton("Apply Deletions…")
        self._apply_btn.clicked.connect(self._apply_deletions)
        toolbar.addWidget(self._scan_btn)
        toolbar.addWidget(self._auto_resolve_btn)
        toolbar.addStretch()
        toolbar.addWidget(self._apply_btn)
        outer.addLayout(toolbar)

        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setVisible(False)
        outer.addWidget(self._progress_bar)

        self._tree = QTreeWidget()
        self._tree.setHeaderLabels(["Path / Group", "Bitrate", "Tags %", "Action"])
        self._tree.setColumnWidth(0, 400)
        self._tree.setColumnWidth(1, 80)
        self._tree.setColumnWidth(2, 80)
        self._tree.setColumnWidth(3, 120)
        self._tree.setAlternatingRowColors(True)
        outer.addWidget(self._tree, stretch=1)

        self._status_label = QLabel("No scan run yet.")
        outer.addWidget(self._status_label)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _populate_tree(self, groups: list[DupeGroup]) -> None:
        self._tree.clear()
        for i, group in enumerate(groups):
            keeper = group.best_track()
            group_item = QTreeWidgetItem(self._tree)
            group_item.setText(0, f"Group {i + 1}  ({len(group.tracks)} copies)")
            group_item.setData(0, Qt.ItemDataRole.UserRole, group)
            group_item.setExpanded(True)

            for track in group.tracks:
                child = QTreeWidgetItem(group_item)
                child.setText(0, str(track.file_path))
                child.setText(1, f"{track.bitrate} kbps")
                child.setText(2, f"{track.tag_completeness * 100:.0f}%")
                child.setData(0, Qt.ItemDataRole.UserRole, track)

                combo = QComboBox()
                combo.addItem("Keep (auto)" if track is keeper else "Delete (auto)")
                combo.addItem("Keep")
                combo.addItem("Delete")
                self._tree.setItemWidget(child, _COL_ACTION, combo)

    def _on_scan_finished(self, groups: list[DupeGroup]) -> None:
        self._progress_bar.setVisible(False)
        self._scan_btn.setEnabled(True)
        self.load_groups(groups)

    def _on_scan_error(self, msg: str) -> None:
        self._progress_bar.setVisible(False)
        self._scan_btn.setEnabled(True)
        self._status_label.setText(f"Error: {msg}")

    def _update_status(self) -> None:
        n = len(self._groups)
        if n == 0:
            self._status_label.setText("No duplicate groups found.")
        else:
            total_dupes = sum(len(g.tracks) - 1 for g in self._groups)
            self._status_label.setText(
                f"{n} duplicate group{'s' if n != 1 else ''} — {total_dupes} redundant file(s)"
            )

    def _auto_resolve_all(self) -> None:
        root = self._tree.invisibleRootItem()
        for i in range(root.childCount()):
            group_item = root.child(i)
            group: DupeGroup = group_item.data(0, Qt.ItemDataRole.UserRole)
            if group is None:
                continue
            keeper = group.best_track()
            for j in range(group_item.childCount()):
                child = group_item.child(j)
                track: Track = child.data(0, Qt.ItemDataRole.UserRole)
                combo: QComboBox = self._tree.itemWidget(child, _COL_ACTION)
                if combo and track is not None:
                    combo.setCurrentText("Keep" if track is keeper else "Delete")

    def _apply_deletions(self) -> None:
        to_delete: list[Track] = []
        root = self._tree.invisibleRootItem()
        for i in range(root.childCount()):
            group_item = root.child(i)
            for j in range(group_item.childCount()):
                child = group_item.child(j)
                combo: QComboBox = self._tree.itemWidget(child, _COL_ACTION)
                if combo and combo.currentText() in _DELETE_LABELS:
                    track: Track = child.data(0, Qt.ItemDataRole.UserRole)
                    if track is not None:
                        to_delete.append(track)
        if to_delete:
            self.delete_requested.emit(to_delete)
