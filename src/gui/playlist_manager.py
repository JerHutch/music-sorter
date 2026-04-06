from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QTreeWidget, QTreeWidgetItem, QPushButton, QLabel,
    QLineEdit, QComboBox, QFormLayout, QGroupBox,
    QMenu, QInputDialog, QFileDialog, QMessageBox,
)
from PySide6.QtCore import Qt, Signal

from src.core.models import PlaylistDefinition, Track
from src.core.playlist import filter_tracks_for_playlist, generate_m3u, generate_pls

import logging
logger = logging.getLogger(__name__)


class PlaylistManager(QWidget):
    """Playlist tree with folder support and an editor panel."""

    show_tracks_requested = Signal(list)  # list[Track]

    def __init__(self, db, all_tracks: list[Track] | None = None, parent=None):
        super().__init__(parent)
        self._db = db
        self._all_tracks: list[Track] = all_tracks or []
        self._playlists: list[PlaylistDefinition] = []
        self._current_playlist: PlaylistDefinition | None = None
        self._build_ui()
        self._load_playlists()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_tracks(self, tracks: list[Track]) -> None:
        self._all_tracks = tracks

    def playlist_count(self) -> int:
        """Count leaf (playlist) items, not folder items."""
        def _count(item: QTreeWidgetItem) -> int:
            if item.data(0, Qt.ItemDataRole.UserRole) is not None:
                return 1
            return sum(_count(item.child(i)) for i in range(item.childCount()))
        root = self._tree.invisibleRootItem()
        return sum(_count(root.child(i)) for i in range(root.childCount()))

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        splitter = QSplitter(Qt.Orientation.Horizontal)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(splitter)

        # Left: tree panel
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(8, 8, 4, 8)

        tree_toolbar = QHBoxLayout()
        btn_new = QPushButton("+ Playlist")
        btn_new.clicked.connect(self._new_playlist)
        btn_folder = QPushButton("+ Folder")
        btn_folder.clicked.connect(self._new_folder)
        btn_regen = QPushButton("Re-generate All")
        btn_regen.clicked.connect(self._regenerate_all)
        tree_toolbar.addWidget(btn_new)
        tree_toolbar.addWidget(btn_folder)
        tree_toolbar.addStretch()
        tree_toolbar.addWidget(btn_regen)
        left_layout.addLayout(tree_toolbar)

        self._tree = QTreeWidget()
        self._tree.setHeaderHidden(True)
        self._tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._tree.customContextMenuRequested.connect(self._on_context_menu)
        self._tree.currentItemChanged.connect(self._on_item_selected)
        self._tree.setDragDropMode(QTreeWidget.DragDropMode.InternalMove)
        left_layout.addWidget(self._tree, stretch=1)
        splitter.addWidget(left)

        # Right: editor panel
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(4, 8, 8, 8)

        self._editor_group = QGroupBox("Playlist Editor")
        form = QFormLayout(self._editor_group)
        self._name_edit = QLineEdit()
        self._folder_edit = QLineEdit()
        self._folder_edit.setPlaceholderText("e.g. DJ/Sets")
        self._format_combo = QComboBox()
        self._format_combo.addItems(["m3u", "pls"])
        self._bucket_combo = QComboBox()
        self._bucket_combo.addItems(["(any)", "DJ Music", "DJ Mixes", "General"])
        self._sort_combo = QComboBox()
        self._sort_combo.addItems(["(none)", "bpm", "artist", "title", "genre"])
        form.addRow("Name:", self._name_edit)
        form.addRow("Folder:", self._folder_edit)
        form.addRow("Format:", self._format_combo)
        form.addRow("Bucket filter:", self._bucket_combo)
        form.addRow("Sort by:", self._sort_combo)
        right_layout.addWidget(self._editor_group)

        btn_row = QHBoxLayout()
        self._save_btn = QPushButton("Save")
        self._save_btn.clicked.connect(self._save_current)
        self._generate_btn = QPushButton("Generate File…")
        self._generate_btn.clicked.connect(self._generate_current)
        btn_row.addWidget(self._save_btn)
        btn_row.addWidget(self._generate_btn)
        btn_row.addStretch()
        right_layout.addLayout(btn_row)

        self._track_count_label = QLabel("")
        right_layout.addWidget(self._track_count_label)
        right_layout.addStretch()
        splitter.addWidget(right)
        splitter.setSizes([300, 400])

        self._editor_group.setEnabled(False)

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def _load_playlists(self) -> None:
        self._playlists = self._db.get_all_playlists()
        self._populate_tree(self._playlists)

    def _populate_tree(self, playlists: list[PlaylistDefinition]) -> None:
        self._tree.clear()
        folders: dict[str, QTreeWidgetItem] = {}
        for pld in playlists:
            folder = pld.folder or ""
            if folder and folder not in folders:
                folder_item = QTreeWidgetItem(self._tree)
                folder_item.setText(0, folder)
                folder_item.setData(0, Qt.ItemDataRole.UserRole, None)
                folder_item.setExpanded(True)
                folders[folder] = folder_item
            parent = folders.get(folder, self._tree.invisibleRootItem())
            item = QTreeWidgetItem(parent if folder else self._tree)
            item.setText(0, pld.name)
            item.setData(0, Qt.ItemDataRole.UserRole, pld)

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_item_selected(self, current: QTreeWidgetItem | None, _prev) -> None:
        if current is None:
            self._editor_group.setEnabled(False)
            return
        pld = current.data(0, Qt.ItemDataRole.UserRole)
        if pld is None:  # folder node
            self._editor_group.setEnabled(False)
            return
        self._current_playlist = pld
        self._name_edit.setText(pld.name)
        self._folder_edit.setText(pld.folder or "")
        self._format_combo.setCurrentText(pld.format)
        bucket = pld.filters.get("bucket", "(any)")
        idx = self._bucket_combo.findText(bucket)
        self._bucket_combo.setCurrentIndex(max(idx, 0))
        sort = pld.sort_by or "(none)"
        idx = self._sort_combo.findText(sort)
        self._sort_combo.setCurrentIndex(max(idx, 0))
        self._editor_group.setEnabled(True)
        matching = filter_tracks_for_playlist(self._all_tracks, pld)
        self._track_count_label.setText(f"{len(matching)} matching tracks")

    def _on_context_menu(self, pos) -> None:
        item = self._tree.itemAt(pos)
        menu = QMenu(self)
        if item:
            pld = item.data(0, Qt.ItemDataRole.UserRole)
            if pld is not None:
                menu.addAction("Rename", lambda: self._rename_playlist(item, pld))
                menu.addAction("Delete", lambda: self._delete_playlist(pld))
        menu.addAction("New Playlist", self._new_playlist)
        menu.addAction("New Folder", self._new_folder)
        menu.exec(self._tree.mapToGlobal(pos))

    # ------------------------------------------------------------------
    # CRUD operations
    # ------------------------------------------------------------------

    def _new_playlist(self) -> None:
        name, ok = QInputDialog.getText(self, "New Playlist", "Playlist name:")
        if ok and name.strip():
            pld = PlaylistDefinition(name=name.strip(), filters={})
            self._db.upsert_playlist(pld)
            self._load_playlists()

    def _new_folder(self) -> None:
        name, ok = QInputDialog.getText(self, "New Folder", "Folder name:")
        if ok and name.strip():
            # Folder is a UI grouping only; it persists when a playlist is saved into it.
            folder_item = QTreeWidgetItem(self._tree)
            folder_item.setText(0, name.strip())
            folder_item.setData(0, Qt.ItemDataRole.UserRole, None)
            folder_item.setExpanded(True)

    def _rename_playlist(self, item: QTreeWidgetItem, pld: PlaylistDefinition) -> None:
        new_name, ok = QInputDialog.getText(self, "Rename", "New name:", text=pld.name)
        if ok and new_name.strip():
            self._db.delete_playlist(pld.name)
            pld.name = new_name.strip()
            self._db.upsert_playlist(pld)
            self._load_playlists()

    def _delete_playlist(self, pld: PlaylistDefinition) -> None:
        result = QMessageBox.question(
            self, "Delete Playlist", f"Delete playlist '{pld.name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if result == QMessageBox.StandardButton.Yes:
            self._db.delete_playlist(pld.name)
            self._load_playlists()

    def _save_current(self) -> None:
        if self._current_playlist is None:
            return
        old_name = self._current_playlist.name
        self._current_playlist.name = self._name_edit.text().strip() or old_name
        self._current_playlist.folder = self._folder_edit.text().strip() or None
        self._current_playlist.format = self._format_combo.currentText()
        bucket = self._bucket_combo.currentText()
        self._current_playlist.filters = {} if bucket == "(any)" else {"bucket": bucket}
        sort = self._sort_combo.currentText()
        self._current_playlist.sort_by = None if sort == "(none)" else sort
        if old_name != self._current_playlist.name:
            self._db.delete_playlist(old_name)
        self._db.upsert_playlist(self._current_playlist)
        self._load_playlists()

    def _generate_current(self) -> None:
        if self._current_playlist is None:
            return
        matching = filter_tracks_for_playlist(self._all_tracks, self._current_playlist)
        if not matching:
            QMessageBox.information(self, "Generate Playlist", "No tracks match the current filters.")
            return
        fmt = self._current_playlist.format
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Playlist", self._current_playlist.name,
            f"Playlist files (*.{fmt})"
        )
        if path:
            output = Path(path)
            generate_m3u(matching, output) if fmt == "m3u" else generate_pls(matching, output)
            QMessageBox.information(self, "Done", f"Saved {len(matching)} tracks to {output.name}")

    def _regenerate_all(self) -> None:
        count = 0
        skipped = 0
        for pld in self._playlists:
            if not pld.folder:
                skipped += 1
                continue
            matching = filter_tracks_for_playlist(self._all_tracks, pld)
            # Resolve relative folder paths against home dir for predictable behavior
            folder_path = Path(pld.folder)
            if not folder_path.is_absolute():
                folder_path = Path.home() / folder_path
            output = folder_path / f"{pld.name}.{pld.format}"
            output.parent.mkdir(parents=True, exist_ok=True)
            generate_m3u(matching, output) if pld.format == "m3u" else generate_pls(matching, output)
            count += 1
        msg = f"Updated {count} playlist(s)."
        if skipped:
            msg += f" {skipped} skipped (no folder set)."
        QMessageBox.information(self, "Re-generate All", msg)
