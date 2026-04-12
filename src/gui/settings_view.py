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

        # --- Organize ---
        organize_group = QGroupBox("Organize")
        organize_layout = QVBoxLayout(organize_group)

        organize_row = QHBoxLayout()
        organize_row.addWidget(QLabel("Destination:"))
        self._organize_path = QLineEdit()
        self._organize_path.setPlaceholderText("Folder where renamed files are moved…")
        btn_browse_org = QPushButton("Browse…")
        organize_row.addWidget(self._organize_path, stretch=1)
        organize_row.addWidget(btn_browse_org)
        organize_layout.addLayout(organize_row)

        self._overlap_warning = QLabel("⚠ Destination overlaps a source directory.")
        self._overlap_warning.setStyleSheet("color: #e67e22;")
        self._overlap_warning.setVisible(False)
        organize_layout.addWidget(self._overlap_warning)

        btn_browse_org.clicked.connect(self._browse_organize_dir)
        self._organize_path.textChanged.connect(self._check_overlap)
        self._organize_path.textChanged.connect(lambda: self.settings_changed.emit())

        layout.addWidget(organize_group)

        # --- AcoustID ---
        acoustid_group = QGroupBox("AcoustID")
        acoustid_layout = QHBoxLayout(acoustid_group)

        self._acoustid_key = QLineEdit()
        self._acoustid_key.setPlaceholderText("Register at acoustid.org to get a key…")
        self._acoustid_key.setEchoMode(QLineEdit.EchoMode.Password)
        acoustid_layout.addWidget(QLabel("API Key:"))
        acoustid_layout.addWidget(self._acoustid_key)

        self._acoustid_key.textChanged.connect(lambda: self.settings_changed.emit())

        layout.addWidget(acoustid_group)

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

        if config.acoustid_api_key:
            self._acoustid_key.setText(str(config.acoustid_api_key))

        self._organize_path.setText(str(config.organize_directory) if config.organize_directory else "")

    # ------------------------------------------------------------------
    def _add_directory(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select Music Directory")
        if path:
            self._dir_list.addItem(path)
            self._check_overlap()
            self.settings_changed.emit()

    def _remove_directory(self) -> None:
        for item in self._dir_list.selectedItems():
            self._dir_list.takeItem(self._dir_list.row(item))
        self._check_overlap()
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

    def get_acoustid_api_key(self) -> str:
        return self._acoustid_key.text().strip()

    def _browse_organize_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select Organize Destination")
        if path:
            self._organize_path.setText(path)

    def _check_overlap(self) -> None:
        """Show warning if destination overlaps any source directory."""
        dest_text = self._organize_path.text().strip()
        if not dest_text:
            self._overlap_warning.setVisible(False)
            return
        dest = Path(dest_text)
        for src in self.get_source_directories():
            try:
                dest.relative_to(src)   # dest is under src (or equal)
                self._overlap_warning.setVisible(True)
                return
            except ValueError:
                pass
            try:
                src.relative_to(dest)   # src is under dest
                self._overlap_warning.setVisible(True)
                return
            except ValueError:
                pass
        self._overlap_warning.setVisible(False)

    def get_organize_directory(self) -> Path | None:
        text = self._organize_path.text().strip()
        return Path(text) if text else None
