from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QToolBar,
    QPushButton, QTableView, QLabel, QAbstractItemView, QMenu, QHeaderView,
)
from PySide6.QtCore import Qt, QSortFilterProxyModel, Signal
from PySide6.QtGui import QStandardItemModel, QStandardItem, QColor, QAction

from src.core.models import Track

# Human-readable column headers keyed by Track attribute name
_COLUMN_HEADERS: dict[str, str] = {
    "title": "Title",
    "artist": "Artist",
    "album_artist": "Album Artist",
    "album": "Album",
    "track_number": "#",
    "disc_number": "Disc",
    "year": "Year",
    "genre": "Genre",
    "bpm": "BPM",
    "key": "Key",
    "bitrate": "Bitrate",
    "duration": "Duration",
    "file_path": "Path",
    "file_size": "Size",
    "bucket": "Bucket",
    "tag_completeness": "Tags",
    "tag_source": "Source",
    "has_artwork": "Art",
}

_DEFAULT_VISIBLE = ["title", "artist", "album", "genre", "bpm", "key", "bitrate", "tag_completeness"]


def _completeness_color(score: float) -> QColor:
    if score >= 0.9:
        return QColor("#2ecc71")
    if score >= 0.4:
        return QColor("#e67e22")
    return QColor("#e74c3c")


def _track_cell_value(track: Track, col: str) -> str:
    val = getattr(track, col, None)
    if val is None:
        return ""
    if col == "bpm":
        return f"{val:.1f}"
    if col == "tag_completeness":
        return f"{val * 100:.0f}%"
    if col == "duration":
        mins, secs = divmod(int(val), 60)
        return f"{mins}:{secs:02d}"
    if col == "file_size":
        return f"{val // 1024} KB"
    if col == "has_artwork":
        return "Yes" if val else "No"
    return str(val)


class LibraryBrowser(QWidget):
    """Track table with configurable columns, search, and multi-select."""

    selection_changed = Signal(list)   # emits list[Track] when selection changes
    columns_changed = Signal(list)     # emits list[str] when user reorders/toggles

    def __init__(self, visible_columns: list[str] | None = None, parent=None):
        super().__init__(parent)
        self._visible_columns = list(visible_columns or _DEFAULT_VISIBLE)
        self._all_tracks: list[Track] = []
        self._bucket_filter: str | None = None
        self._extra_filter_fn = None  # callable(Track) -> bool

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # Search bar
        search_layout = QHBoxLayout()
        self._search_box = QLineEdit()
        self._search_box.setPlaceholderText("Search tracks\u2026")
        search_layout.addWidget(self._search_box)
        layout.addLayout(search_layout)

        # Toolbar
        toolbar = QToolBar()
        toolbar.setMovable(False)
        self._btn_autotag = QPushButton("Auto-Tag Selected")
        self._btn_batch = QPushButton("Batch Edit")
        self._btn_analyze = QPushButton("Analyze")
        for btn in (self._btn_autotag, self._btn_batch, self._btn_analyze):
            toolbar.addWidget(btn)
        layout.addWidget(toolbar)

        # Model + proxy
        self._model = QStandardItemModel(0, len(self._visible_columns))
        self._model.setHorizontalHeaderLabels(
            [_COLUMN_HEADERS.get(c, c) for c in self._visible_columns]
        )

        self._proxy = QSortFilterProxyModel()
        self._proxy.setSourceModel(self._model)
        self._proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._proxy.setFilterKeyColumn(-1)

        # Table view
        self._table = QTableView()
        self._table.setModel(self._proxy)
        self._table.setSortingEnabled(True)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.horizontalHeader().setSectionsMovable(True)
        self._table.verticalHeader().setVisible(False)
        self._table.setAlternatingRowColors(True)
        layout.addWidget(self._table)

        # Status label
        self._status_label = QLabel("0 tracks")
        layout.addWidget(self._status_label)

        # Right-click header -> show/hide columns
        self._table.horizontalHeader().setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._table.horizontalHeader().customContextMenuRequested.connect(self._on_header_context_menu)
        self._table.horizontalHeader().sectionMoved.connect(self._on_section_moved)

        # Wire search and selection
        self._search_box.textChanged.connect(self._proxy.setFilterFixedString)
        self._table.selectionModel().selectionChanged.connect(self._on_selection_changed)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_tracks(self, tracks: list[Track]) -> None:
        self._all_tracks = tracks
        self._repopulate()

    def filter_by_bucket(self, bucket: str | None) -> None:
        self._bucket_filter = bucket
        self._extra_filter_fn = None
        self._repopulate()

    def filter_by_fn(self, fn) -> None:
        """Filter to tracks matching a predicate: fn(Track) -> bool."""
        self._bucket_filter = None
        self._extra_filter_fn = fn
        self._repopulate()

    def clear_filter(self) -> None:
        self._bucket_filter = None
        self._extra_filter_fn = None
        self._repopulate()

    def selected_tracks(self) -> list[Track]:
        rows = {self._proxy.mapToSource(idx).row()
                for idx in self._table.selectionModel().selectedRows()}
        return [self._model.item(r, 0).data(Qt.ItemDataRole.UserRole) for r in sorted(rows)]

    def track_count(self) -> int:
        return self._model.rowCount()

    def column_count(self) -> int:
        return self._model.columnCount()

    def visible_row_count(self) -> int:
        return self._proxy.rowCount()

    def set_visible_columns(self, columns: list[str]) -> None:
        self._visible_columns = columns
        self._rebuild_model_columns()
        self._repopulate()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _filtered_tracks(self) -> list[Track]:
        if self._bucket_filter is not None:
            if self._bucket_filter == "All Music":
                return list(self._all_tracks)
            return [t for t in self._all_tracks if t.bucket == self._bucket_filter]
        if self._extra_filter_fn is not None:
            return [t for t in self._all_tracks if self._extra_filter_fn(t)]
        return list(self._all_tracks)

    def _repopulate(self) -> None:
        tracks = self._filtered_tracks()
        self._model.setRowCount(0)
        for track in tracks:
            row = []
            for col in self._visible_columns:
                item = QStandardItem(_track_cell_value(track, col))
                item.setEditable(False)
                if col == "tag_completeness":
                    item.setBackground(_completeness_color(track.tag_completeness))
                row.append(item)
            if row:
                row[0].setData(track, Qt.ItemDataRole.UserRole)
            self._model.appendRow(row)
        count = len(tracks)
        self._status_label.setText(f"{count} track{'s' if count != 1 else ''}")

    def _rebuild_model_columns(self) -> None:
        self._model.clear()
        self._model.setColumnCount(len(self._visible_columns))
        self._model.setHorizontalHeaderLabels(
            [_COLUMN_HEADERS.get(c, c) for c in self._visible_columns]
        )

    def _on_header_context_menu(self, pos) -> None:
        menu = QMenu(self)
        for col in list(_COLUMN_HEADERS.keys()):
            action = QAction(_COLUMN_HEADERS[col], self, checkable=True)
            action.setChecked(col in self._visible_columns)
            action.setData(col)
            action.triggered.connect(self._on_toggle_column)
            menu.addAction(action)
        menu.exec(self._table.horizontalHeader().mapToGlobal(pos))

    def _on_toggle_column(self, checked: bool) -> None:
        col = self.sender().data()
        changed = False
        if checked and col not in self._visible_columns:
            self._visible_columns.append(col)
            changed = True
        elif not checked and col in self._visible_columns and len(self._visible_columns) > 1:
            self._visible_columns.remove(col)
            changed = True
        if changed:
            self._rebuild_model_columns()
            self._repopulate()
            self.columns_changed.emit(list(self._visible_columns))

    def _on_section_moved(self, logical: int, old_visual: int, new_visual: int) -> None:
        header = self._table.horizontalHeader()
        # Build a reverse map: display label -> column key
        label_to_col = {v: k for k, v in _COLUMN_HEADERS.items()}
        new_order = []
        for i in range(header.count()):
            label = self._model.horizontalHeaderItem(header.logicalIndex(i))
            if label is not None:
                col_key = label_to_col.get(label.text())
                if col_key:
                    new_order.append(col_key)
        if new_order and len(new_order) == len(self._visible_columns):
            self._visible_columns = new_order
            self.columns_changed.emit(list(self._visible_columns))

    def _on_selection_changed(self) -> None:
        self.selection_changed.emit(self.selected_tracks())
