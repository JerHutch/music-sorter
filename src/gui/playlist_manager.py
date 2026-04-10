from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QTreeWidget, QTreeWidgetItem, QPushButton, QLabel,
    QLineEdit, QComboBox, QFormLayout, QGroupBox,
    QMenu, QInputDialog, QFileDialog, QMessageBox,
    QScrollArea, QSpinBox, QCheckBox,
)
from PySide6.QtCore import Qt, Signal

from src.core.models import SimpleRule, RuleGroup, SmartPlaylist, Track
from src.core.playlist import (
    evaluate_playlist, generate_m3u, generate_pls,
    FIELD_REGISTRY, OPERATORS_BY_TYPE, OPERATOR_LABELS,
)

import logging
logger = logging.getLogger(__name__)

_FIELD_KEYS = list(FIELD_REGISTRY.keys())
_FIELD_LABELS = [fd.label for fd in FIELD_REGISTRY.values()]

_LIMIT_ORDER_OPTIONS = ["(none)", "random", "bpm", "artist", "title", "date_added"]
_SORT_OPTIONS = ["(none)", "bpm", "artist", "title", "genre", "year", "bitrate", "date_added"]


class RuleRowWidget(QWidget):
    """A single rule row: field ▾ operator ▾ value [−]."""

    removed = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self._field_combo = QComboBox()
        self._field_combo.addItems(_FIELD_LABELS)
        self._field_combo.setFixedWidth(120)
        self._field_combo.currentIndexChanged.connect(self._on_field_changed)

        self._operator_combo = QComboBox()
        self._operator_combo.setFixedWidth(110)

        self._value_edit = QLineEdit()
        self._value_edit.setPlaceholderText("value")

        btn_remove = QPushButton("−")
        btn_remove.setFixedWidth(28)
        btn_remove.clicked.connect(lambda: self.removed.emit(self))

        layout.addWidget(self._field_combo)
        layout.addWidget(self._operator_combo)
        layout.addWidget(self._value_edit, stretch=1)
        layout.addWidget(btn_remove)

        self._on_field_changed(0)

    def _on_field_changed(self, _idx: int) -> None:
        field_key = _FIELD_KEYS[self._field_combo.currentIndex()]
        field_type = FIELD_REGISTRY[field_key].type
        operators = OPERATORS_BY_TYPE[field_type]
        self._operator_combo.blockSignals(True)
        self._operator_combo.clear()
        self._operator_combo.addItems(
            [OPERATOR_LABELS.get(op, op) for op in operators]
        )
        self._operator_combo.blockSignals(False)

    def _current_operator_key(self) -> str:
        field_key = _FIELD_KEYS[self._field_combo.currentIndex()]
        field_type = FIELD_REGISTRY[field_key].type
        operators = OPERATORS_BY_TYPE[field_type]
        idx = self._operator_combo.currentIndex()
        return operators[idx] if 0 <= idx < len(operators) else operators[0]

    def get_rule(self) -> SimpleRule:
        field_key = _FIELD_KEYS[self._field_combo.currentIndex()]
        operator = self._current_operator_key()
        field_type = FIELD_REGISTRY[field_key].type
        text = self._value_edit.text().strip()
        if field_type == "number":
            try:
                value: str | float | bool | None = float(text)
            except ValueError:
                value = 0.0
        elif field_type == "boolean":
            value = None  # operator encodes the bool (is_true / is_false)
        else:
            value = text
        return SimpleRule(field=field_key, operator=operator, value=value)

    def set_rule(self, rule: SimpleRule) -> None:
        if rule.field in _FIELD_KEYS:
            self._field_combo.setCurrentIndex(_FIELD_KEYS.index(rule.field))
        self._on_field_changed(0)
        field_type = FIELD_REGISTRY[rule.field].type
        operators = OPERATORS_BY_TYPE[field_type]
        if rule.operator in operators:
            self._operator_combo.setCurrentIndex(operators.index(rule.operator))
        if rule.value is not None:
            self._value_edit.setText(str(rule.value))


class RuleGroupWidget(QWidget):
    """A sub-group with its own conjunction and rule rows."""

    removed = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows: list[RuleRowWidget] = []
        self._build_ui()
        self._add_rule_row()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(4)
        self.setStyleSheet(
            "RuleGroupWidget { border: 1px solid #2a2a4a; border-radius: 6px; }"
        )

        header = QHBoxLayout()
        lbl = QLabel("Group:")
        lbl.setStyleSheet("color: #7c83ff; font-weight: bold;")
        header.addWidget(lbl)
        header.addWidget(QLabel("Match"))
        self._conjunction_combo = QComboBox()
        self._conjunction_combo.addItems(["ALL", "ANY"])
        self._conjunction_combo.setFixedWidth(65)
        header.addWidget(self._conjunction_combo)
        header.addWidget(QLabel("of:"))
        header.addStretch()
        btn_remove = QPushButton("Remove group")
        btn_remove.clicked.connect(lambda: self.removed.emit(self))
        header.addWidget(btn_remove)
        outer.addLayout(header)

        self._rules_layout = QVBoxLayout()
        self._rules_layout.setSpacing(4)
        outer.addLayout(self._rules_layout)

        btn_add = QPushButton("+ Add rule")
        btn_add.clicked.connect(self._add_rule_row)
        outer.addWidget(btn_add, alignment=Qt.AlignmentFlag.AlignLeft)

    def _add_rule_row(self) -> None:
        row = RuleRowWidget()
        row.removed.connect(self._remove_row)
        self._rows.append(row)
        self._rules_layout.addWidget(row)

    def _remove_row(self, row: RuleRowWidget) -> None:
        if len(self._rows) <= 1:
            return
        self._rows.remove(row)
        self._rules_layout.removeWidget(row)
        row.deleteLater()

    def get_group(self) -> RuleGroup:
        conjunction = "AND" if self._conjunction_combo.currentText() == "ALL" else "OR"
        return RuleGroup(conjunction=conjunction, rules=[r.get_rule() for r in self._rows])

    def set_group(self, group: RuleGroup) -> None:
        for row in list(self._rows):
            self._rules_layout.removeWidget(row)
            row.deleteLater()
        self._rows.clear()
        self._conjunction_combo.setCurrentText("ALL" if group.conjunction == "AND" else "ANY")
        for rule in group.rules:
            row = RuleRowWidget()
            row.removed.connect(self._remove_row)
            row.set_rule(rule)
            self._rows.append(row)
            self._rules_layout.addWidget(row)


class RuleBuilderWidget(QWidget):
    """Top-level rule builder: conjunction selector + list of rules/groups."""

    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._items: list[RuleRowWidget | RuleGroupWidget] = []
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        conj_row = QHBoxLayout()
        conj_row.addWidget(QLabel("Match"))
        self._conjunction_combo = QComboBox()
        self._conjunction_combo.addItems(["ALL", "ANY"])
        self._conjunction_combo.setFixedWidth(65)
        self._conjunction_combo.currentIndexChanged.connect(self.changed)
        conj_row.addWidget(self._conjunction_combo)
        conj_row.addWidget(QLabel("of the following rules:"))
        conj_row.addStretch()
        layout.addLayout(conj_row)

        scroll_content = QWidget()
        self._rules_layout = QVBoxLayout(scroll_content)
        self._rules_layout.setSpacing(4)
        self._rules_layout.setContentsMargins(0, 0, 0, 0)
        self._rules_layout.addStretch()

        scroll = QScrollArea()
        scroll.setWidget(scroll_content)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        layout.addWidget(scroll, stretch=1)

        btn_row = QHBoxLayout()
        btn_add_rule = QPushButton("+ Add Rule")
        btn_add_rule.clicked.connect(self._add_rule_row)
        btn_add_group = QPushButton("+ Add Group")
        btn_add_group.clicked.connect(self._add_group)
        btn_row.addWidget(btn_add_rule)
        btn_row.addWidget(btn_add_group)
        btn_row.addStretch()
        layout.addLayout(btn_row)

    def _add_rule_row(self) -> None:
        row = RuleRowWidget()
        row.removed.connect(self._remove_item)
        self._items.append(row)
        self._rules_layout.insertWidget(self._rules_layout.count() - 1, row)
        self.changed.emit()

    def _add_group(self) -> None:
        group = RuleGroupWidget()
        group.removed.connect(self._remove_item)
        self._items.append(group)
        self._rules_layout.insertWidget(self._rules_layout.count() - 1, group)
        self.changed.emit()

    def _remove_item(self, item) -> None:
        self._items.remove(item)
        self._rules_layout.removeWidget(item)
        item.deleteLater()
        self.changed.emit()

    def get_rules(self) -> tuple[str, list]:
        conjunction = "AND" if self._conjunction_combo.currentText() == "ALL" else "OR"
        rules = []
        for item in self._items:
            if isinstance(item, RuleRowWidget):
                rules.append(item.get_rule())
            else:
                rules.append(item.get_group())
        return conjunction, rules

    def load_rules(self, conjunction: str, rules: list) -> None:
        for item in list(self._items):
            self._rules_layout.removeWidget(item)
            item.deleteLater()
        self._items.clear()
        self._conjunction_combo.setCurrentText("ALL" if conjunction == "AND" else "ANY")
        for rule in rules:
            if isinstance(rule, SimpleRule):
                row = RuleRowWidget()
                row.removed.connect(self._remove_item)
                row.set_rule(rule)
                self._items.append(row)
                self._rules_layout.insertWidget(self._rules_layout.count() - 1, row)
            elif isinstance(rule, RuleGroup):
                group = RuleGroupWidget()
                group.removed.connect(self._remove_item)
                group.set_group(rule)
                self._items.append(group)
                self._rules_layout.insertWidget(self._rules_layout.count() - 1, group)


class PlaylistManager(QWidget):
    """Playlist tree with folder support and a smart rule builder editor."""

    show_tracks_requested = Signal(list)

    def __init__(self, db, all_tracks: list[Track] | None = None, parent=None):
        super().__init__(parent)
        self._db = db
        self._all_tracks: list[Track] = all_tracks or []
        self._playlists: list[SmartPlaylist] = []
        self._current: SmartPlaylist | None = None
        self._build_ui()
        self._load_playlists()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_tracks(self, tracks: list[Track]) -> None:
        self._all_tracks = tracks
        self._update_count()

    def playlist_count(self) -> int:
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

        # Left: tree
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

        # Right: editor
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(4, 8, 8, 8)

        self._editor_group = QGroupBox("Playlist Editor")
        editor_layout = QVBoxLayout(self._editor_group)

        form = QFormLayout()
        self._name_edit = QLineEdit()
        self._folder_edit = QLineEdit()
        self._folder_edit.setPlaceholderText("e.g. DJ/Sets")
        self._format_combo = QComboBox()
        self._format_combo.addItems(["m3u", "pls"])
        self._sort_combo = QComboBox()
        self._sort_combo.addItems(_SORT_OPTIONS)
        limit_row = QHBoxLayout()
        self._limit_spin = QSpinBox()
        self._limit_spin.setRange(0, 9999)
        self._limit_spin.setSpecialValueText("unlimited")
        self._limit_spin.setFixedWidth(80)
        self._limit_order_combo = QComboBox()
        self._limit_order_combo.addItems(_LIMIT_ORDER_OPTIONS)
        limit_row.addWidget(self._limit_spin)
        limit_row.addWidget(QLabel("tracks, by"))
        limit_row.addWidget(self._limit_order_combo)
        limit_row.addStretch()
        self._sidebar_check = QCheckBox("Show in sidebar")
        self._sidebar_check.setChecked(True)
        form.addRow("Name:", self._name_edit)
        form.addRow("Folder:", self._folder_edit)
        form.addRow("Format:", self._format_combo)
        form.addRow("Sort by:", self._sort_combo)
        form.addRow("Limit:", limit_row)
        form.addRow("", self._sidebar_check)
        editor_layout.addLayout(form)

        editor_layout.addWidget(QLabel("Rules:"))
        self._rule_builder = RuleBuilderWidget()
        self._rule_builder.changed.connect(self._update_count)
        editor_layout.addWidget(self._rule_builder, stretch=1)

        right_layout.addWidget(self._editor_group, stretch=1)

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
        splitter.addWidget(right)
        splitter.setSizes([300, 500])

        self._editor_group.setEnabled(False)

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def _load_playlists(self) -> None:
        self._playlists = self._db.get_all_smart_playlists()
        self._populate_tree(self._playlists)

    def _populate_tree(self, playlists: list[SmartPlaylist]) -> None:
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
        if pld is None:
            self._editor_group.setEnabled(False)
            return
        self._current = pld
        self._name_edit.setText(pld.name)
        self._folder_edit.setText(pld.folder or "")
        self._format_combo.setCurrentText(pld.format)
        sort = pld.sort_by or "(none)"
        idx = self._sort_combo.findText(sort)
        self._sort_combo.setCurrentIndex(max(idx, 0))
        self._limit_spin.setValue(pld.limit_count or 0)
        order = pld.limit_order or "(none)"
        idx = self._limit_order_combo.findText(order)
        self._limit_order_combo.setCurrentIndex(max(idx, 0))
        self._sidebar_check.setChecked(pld.show_in_sidebar)
        self._rule_builder.load_rules(pld.conjunction, pld.rules)
        self._editor_group.setEnabled(True)
        self._update_count()

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

    def _update_count(self) -> None:
        if self._current is None:
            return
        conjunction, rules = self._rule_builder.get_rules()
        temp = SmartPlaylist(name="", conjunction=conjunction, rules=rules)
        count = len(evaluate_playlist(temp, self._all_tracks))
        self._track_count_label.setText(f"{count} matching tracks")

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def _new_playlist(self) -> None:
        name, ok = QInputDialog.getText(self, "New Playlist", "Playlist name:")
        if ok and name.strip():
            pld = SmartPlaylist(name=name.strip())
            self._db.upsert_smart_playlist(pld)
            self._load_playlists()

    def _new_folder(self) -> None:
        name, ok = QInputDialog.getText(self, "New Folder", "Folder name:")
        if ok and name.strip():
            folder_item = QTreeWidgetItem(self._tree)
            folder_item.setText(0, name.strip())
            folder_item.setData(0, Qt.ItemDataRole.UserRole, None)
            folder_item.setExpanded(True)

    def _rename_playlist(self, item: QTreeWidgetItem, pld: SmartPlaylist) -> None:
        new_name, ok = QInputDialog.getText(self, "Rename", "New name:", text=pld.name)
        if ok and new_name.strip():
            self._db.delete_smart_playlist(pld.name)
            pld.name = new_name.strip()
            self._db.upsert_smart_playlist(pld)
            self._load_playlists()

    def _delete_playlist(self, pld: SmartPlaylist) -> None:
        result = QMessageBox.question(
            self, "Delete Playlist", f"Delete playlist '{pld.name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if result == QMessageBox.StandardButton.Yes:
            self._db.delete_smart_playlist(pld.name)
            self._load_playlists()

    def _save_current(self) -> None:
        if self._current is None:
            return
        old_name = self._current.name
        self._current.name = self._name_edit.text().strip() or old_name
        self._current.folder = self._folder_edit.text().strip() or None
        self._current.format = self._format_combo.currentText()
        sort = self._sort_combo.currentText()
        self._current.sort_by = None if sort == "(none)" else sort
        limit_val = self._limit_spin.value()
        self._current.limit_count = limit_val if limit_val > 0 else None
        order = self._limit_order_combo.currentText()
        self._current.limit_order = None if order == "(none)" else order
        self._current.show_in_sidebar = self._sidebar_check.isChecked()
        conjunction, rules = self._rule_builder.get_rules()
        self._current.conjunction = conjunction
        self._current.rules = rules
        if old_name != self._current.name:
            self._db.delete_smart_playlist(old_name)
        self._db.upsert_smart_playlist(self._current)
        self._load_playlists()

    def _generate_current(self) -> None:
        if self._current is None:
            return
        matching = evaluate_playlist(self._current, self._all_tracks)
        if not matching:
            QMessageBox.information(self, "Generate", "No tracks match the current rules.")
            return
        fmt = self._current.format
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Playlist", self._current.name,
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
            matching = evaluate_playlist(pld, self._all_tracks)
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
