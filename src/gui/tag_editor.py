from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit,
    QPushButton, QLabel, QScrollArea, QDialog, QDialogButtonBox,
    QTableWidget, QTableWidgetItem, QFrame,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont

from src.core.models import Track

import logging
logger = logging.getLogger(__name__)

_EDITABLE_FIELDS: list[tuple[str, str]] = [
    ("title",        "Title"),
    ("artist",       "Artist"),
    ("album_artist", "Album Artist"),
    ("album",        "Album"),
    ("track_number", "Track #"),
    ("disc_number",  "Disc #"),
    ("year",         "Year"),
    ("genre",        "Genre"),
    ("bpm",          "BPM"),
    ("key",          "Key"),
    ("bucket",       "Bucket"),
]

_MULTIPLE = "[Multiple]"


class TagEditor(QWidget):
    """Single-track and batch tag editing panel."""

    save_requested = Signal(list, dict)  # (tracks, {field: new_value})

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tracks: list[Track] = []
        self._fields: dict[str, QLineEdit] = {}
        self._build_ui()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_track(self, track: Track) -> None:
        self._tracks = [track]
        self._populate_single(track)

    def load_tracks(self, tracks: list[Track]) -> None:
        self._tracks = tracks
        if not tracks:
            self._clear_fields()
            self._mode_label.setText("")
            self._save_btn.setEnabled(False)
        elif len(tracks) == 1:
            self._populate_single(tracks[0])
        else:
            self._populate_batch(tracks)

    def get_field_value(self, field: str) -> str:
        """Return current text for field, or placeholder text if text is empty but placeholder is set."""
        widget = self._fields.get(field)
        if widget is None:
            return ""
        text = widget.text()
        if not text and widget.placeholderText() == _MULTIPLE:
            return _MULTIPLE
        return text

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(6)

        self._mode_label = QLabel("")
        font = QFont()
        font.setBold(True)
        self._mode_label.setFont(font)
        outer.addWidget(self._mode_label)

        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        outer.addWidget(separator)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        form_widget = QWidget()
        form = QFormLayout(form_widget)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setContentsMargins(4, 4, 4, 4)
        form.setSpacing(6)

        for field, label in _EDITABLE_FIELDS:
            line_edit = QLineEdit()
            self._fields[field] = line_edit
            form.addRow(label + ":", line_edit)

        scroll.setWidget(form_widget)
        outer.addWidget(scroll, stretch=1)

        btn_row = QHBoxLayout()
        self._save_btn = QPushButton("Save")
        self._save_btn.setEnabled(False)
        btn_row.addStretch()
        btn_row.addWidget(self._save_btn)
        outer.addLayout(btn_row)

        self._save_btn.clicked.connect(self._on_save_clicked)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _clear_fields(self) -> None:
        for w in self._fields.values():
            w.setText("")
            w.setPlaceholderText("")

    def _populate_single(self, track: Track) -> None:
        self._mode_label.setText("Tag Editor — single track")
        for field, _ in _EDITABLE_FIELDS:
            val = getattr(track, field, None)
            self._fields[field].setText("" if val is None else str(val))
            self._fields[field].setPlaceholderText("")
        self._save_btn.setEnabled(True)

    def _populate_batch(self, tracks: list[Track]) -> None:
        self._mode_label.setText(f"Batch Edit — {len(tracks)} tracks")
        for field, _ in _EDITABLE_FIELDS:
            values = {str(getattr(t, field, "") or "") for t in tracks}
            if len(values) == 1:
                self._fields[field].setText(values.pop())
                self._fields[field].setPlaceholderText("")
            else:
                self._fields[field].setText("")
                self._fields[field].setPlaceholderText(_MULTIPLE)
        self._save_btn.setEnabled(True)

    def _on_save_clicked(self) -> None:
        if not self._tracks:
            return

        changed: dict[str, str] = {}
        for field, _ in _EDITABLE_FIELDS:
            widget = self._fields[field]
            value = widget.text().strip()
            placeholder = widget.placeholderText()
            if not value and placeholder == _MULTIPLE:
                continue  # user didn't touch this batch field
            if len(self._tracks) == 1:
                original = getattr(self._tracks[0], field, None)
                original_str = "" if original is None else str(original)
                if value != original_str:
                    changed[field] = value
            else:
                if value:  # batch: only include fields user typed into
                    changed[field] = value

        if not changed:
            return

        if len(self._tracks) > 1:
            dlg = _BatchPreviewDialog(self._tracks, changed, parent=self)
            if dlg.exec() != QDialog.DialogCode.Accepted:
                return

        self.save_requested.emit(self._tracks, changed)


class _BatchPreviewDialog(QDialog):
    """Shows what will be changed before applying a batch edit."""

    def __init__(self, tracks: list[Track], changes: dict[str, str], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Confirm Batch Edit")
        self.resize(600, 400)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"Apply the following changes to {len(tracks)} tracks?"))

        table = QTableWidget(len(changes), 2)
        table.setHorizontalHeaderLabels(["Field", "New Value"])
        table.horizontalHeader().setStretchLastSection(True)
        table.verticalHeader().setVisible(False)
        for row, (field, value) in enumerate(changes.items()):
            table.setItem(row, 0, QTableWidgetItem(field))
            table.setItem(row, 1, QTableWidgetItem(value))
        layout.addWidget(table)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
