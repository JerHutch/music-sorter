from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QToolBar,
    QPushButton,
    QTableView,
    QLabel,
    QAbstractItemView,
)
from PySide6.QtCore import (
    Qt,
    QSortFilterProxyModel,
)
from PySide6.QtGui import QStandardItemModel, QStandardItem, QColor

from src.core.models import Track

_COLUMNS = ["Title", "Artist", "Album", "Genre", "BPM", "Key", "Bitrate", "Tags"]
_COL_IDX = {name: i for i, name in enumerate(_COLUMNS)}


def _completeness_color(score: float) -> QColor:
    if score >= 0.9:
        return QColor("#2ecc71")  # green
    if score >= 0.4:
        return QColor("#e67e22")  # orange
    return QColor("#e74c3c")  # red


class LibraryBrowser(QWidget):
    """Track table with search, sortable columns, and multi-select."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # Search bar
        search_layout = QHBoxLayout()
        self._search_box = QLineEdit()
        self._search_box.setPlaceholderText("Search tracks…")
        search_layout.addWidget(self._search_box)
        layout.addLayout(search_layout)

        # Toolbar actions
        toolbar = QToolBar()
        toolbar.setMovable(False)
        btn_autotag = QPushButton("Auto-Tag Selected")
        btn_batch = QPushButton("Batch Edit")
        btn_analyze = QPushButton("Analyze")
        for btn in (btn_autotag, btn_batch, btn_analyze):
            toolbar.addWidget(btn)
        layout.addWidget(toolbar)

        # Model + proxy
        self._model = QStandardItemModel(0, len(_COLUMNS))
        self._model.setHorizontalHeaderLabels(_COLUMNS)

        self._proxy = QSortFilterProxyModel()
        self._proxy.setSourceModel(self._model)
        self._proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._proxy.setFilterKeyColumn(-1)  # search all columns

        # Table view
        self._table = QTableView()
        self._table.setModel(self._proxy)
        self._table.setSortingEnabled(True)
        self._table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self._table.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.verticalHeader().setVisible(False)
        self._table.setAlternatingRowColors(True)
        layout.addWidget(self._table)

        # Status label
        self._status_label = QLabel("0 tracks")
        layout.addWidget(self._status_label)

        # Wire search
        self._search_box.textChanged.connect(self._proxy.setFilterFixedString)

    # ------------------------------------------------------------------
    def load_tracks(self, tracks: list[Track]) -> None:
        """Populate the table with the given list of Track objects."""
        self._model.setRowCount(0)

        for track in tracks:
            bpm_str = f"{track.bpm:.1f}" if track.bpm is not None else ""
            completeness_pct = f"{track.tag_completeness * 100:.0f}%"

            row = [
                QStandardItem(track.title or ""),
                QStandardItem(track.artist or ""),
                QStandardItem(track.album or ""),
                QStandardItem(track.genre or ""),
                QStandardItem(bpm_str),
                QStandardItem(track.key or ""),
                QStandardItem(str(track.bitrate)),
                QStandardItem(completeness_pct),
            ]

            # Color-code the Tags (completeness) cell
            color = _completeness_color(track.tag_completeness)
            row[_COL_IDX["Tags"]].setBackground(color)

            for item in row:
                item.setEditable(False)

            self._model.appendRow(row)

        count = len(tracks)
        self._status_label.setText(f"{count} track{'s' if count != 1 else ''}")
