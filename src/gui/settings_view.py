from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGroupBox,
    QListWidget,
    QPushButton,
    QLineEdit,
    QFileDialog,
    QLabel,
)
from PySide6.QtCore import Signal

from src.core.config import Config


class SettingsView(QWidget):
    """Settings panel for source directories, iTunes path, and rescan actions."""

    settings_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        # --- Source Directories ---
        src_group = QGroupBox("Source Directories")
        src_layout = QVBoxLayout(src_group)

        self._dir_list = QListWidget()
        src_layout.addWidget(self._dir_list)

        dir_btn_layout = QHBoxLayout()
        btn_add = QPushButton("Add…")
        btn_remove = QPushButton("Remove")
        dir_btn_layout.addWidget(btn_add)
        dir_btn_layout.addWidget(btn_remove)
        dir_btn_layout.addStretch()
        src_layout.addLayout(dir_btn_layout)

        btn_add.clicked.connect(self._add_directory)
        btn_remove.clicked.connect(self._remove_directory)

        layout.addWidget(src_group)

        # --- iTunes Library ---
        itunes_group = QGroupBox("iTunes Library")
        itunes_layout = QHBoxLayout(itunes_group)

        self._itunes_path = QLineEdit()
        self._itunes_path.setPlaceholderText("Path to iTunes Library.xml…")
        btn_browse = QPushButton("Browse…")
        itunes_layout.addWidget(QLabel("Library XML:"))
        itunes_layout.addWidget(self._itunes_path)
        itunes_layout.addWidget(btn_browse)

        btn_browse.clicked.connect(self._browse_itunes)

        layout.addWidget(itunes_group)

        # --- Actions ---
        actions_group = QGroupBox("Actions")
        actions_layout = QVBoxLayout(actions_group)

        btn_rescan = QPushButton("Force Full Rescan")
        btn_rescan.clicked.connect(self._force_rescan)
        actions_layout.addWidget(btn_rescan)

        layout.addWidget(actions_group)
        layout.addStretch()

    # ------------------------------------------------------------------
    def load_config(self, config: Config) -> None:
        """Populate controls from a Config object."""
        self._dir_list.clear()
        for d in config.source_directories:
            self._dir_list.addItem(str(d))

        if config.itunes_xml_path:
            self._itunes_path.setText(str(config.itunes_xml_path))

    # ------------------------------------------------------------------
    def _add_directory(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select Music Directory")
        if path:
            self._dir_list.addItem(path)
            self.settings_changed.emit()

    def _remove_directory(self) -> None:
        for item in self._dir_list.selectedItems():
            self._dir_list.takeItem(self._dir_list.row(item))
        self.settings_changed.emit()

    def _browse_itunes(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select iTunes Library XML", "", "XML Files (*.xml)"
        )
        if path:
            self._itunes_path.setText(path)
            self.settings_changed.emit()

    def _force_rescan(self) -> None:
        # Signal propagated via parent (main window handles it)
        pass

    def get_source_directories(self) -> list[Path]:
        """Return the current list of source directories from the UI."""
        return [
            Path(self._dir_list.item(i).text())
            for i in range(self._dir_list.count())
        ]

    def get_itunes_path(self) -> Path | None:
        text = self._itunes_path.text().strip()
        return Path(text) if text else None
