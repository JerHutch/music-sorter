from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QToolBar,
    QStackedWidget,
    QStatusBar,
    QProgressBar,
    QTreeWidget,
    QTreeWidgetItem,
    QLabel,
    QPushButton,
    QSizePolicy,
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QAction

from src.core.config import Config
from src.core.database import Database
from src.gui.dashboard import Dashboard
from src.gui.library_browser import LibraryBrowser
from src.gui.settings_view import SettingsView
from src.gui.workers import ScanWorker

# Page indices in the stacked widget
_PAGE_DASHBOARD = 0
_PAGE_LIBRARY = 1
_PAGE_SETTINGS = 2

_DB_DIR = Path.home() / ".local" / "share" / "music-sorter"


class MainWindow(QMainWindow):
    """Top-level application window."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Music Sorter")
        self.resize(1200, 750)

        # Core objects
        self._config = Config.load_defaults()
        _DB_DIR.mkdir(parents=True, exist_ok=True)
        self._db = Database(_DB_DIR / "library.db")
        self._scan_worker: ScanWorker | None = None

        self._build_ui()
        self._settings_view.load_config(self._config)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        # Top toolbar
        toolbar = QToolBar("Navigation")
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(16, 16))
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, toolbar)

        act_dashboard = QAction("Dashboard", self)
        act_library = QAction("Library", self)
        act_settings = QAction("Settings", self)
        act_scan = QAction("Scan", self)

        act_dashboard.triggered.connect(lambda: self._show_page(_PAGE_DASHBOARD))
        act_library.triggered.connect(lambda: self._show_page(_PAGE_LIBRARY))
        act_settings.triggered.connect(lambda: self._show_page(_PAGE_SETTINGS))
        act_scan.triggered.connect(self._start_scan)

        for act in (act_dashboard, act_library, act_settings, act_scan):
            toolbar.addAction(act)

        # Central widget: sidebar + content
        central = QWidget()
        self.setCentralWidget(central)
        h_layout = QHBoxLayout(central)
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.setSpacing(0)

        # Sidebar
        sidebar = self._build_sidebar()
        h_layout.addWidget(sidebar)

        # Content stack
        self._stack = QStackedWidget()
        self._dashboard = Dashboard()
        self._library = LibraryBrowser()
        self._settings_view = SettingsView()

        self._stack.addWidget(self._dashboard)   # index 0
        self._stack.addWidget(self._library)     # index 1
        self._stack.addWidget(self._settings_view)  # index 2

        h_layout.addWidget(self._stack, stretch=1)

        # Status bar
        status_bar = QStatusBar()
        self.setStatusBar(status_bar)

        self._status_label = QLabel("Ready")
        status_bar.addWidget(self._status_label, 1)

        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 0)  # indeterminate by default
        self._progress_bar.setFixedWidth(200)
        self._progress_bar.setVisible(False)
        status_bar.addPermanentWidget(self._progress_bar)

        # Show dashboard initially
        self._stack.setCurrentIndex(_PAGE_DASHBOARD)
        self._refresh_library()

    def _build_sidebar(self) -> QWidget:
        sidebar = QWidget()
        sidebar.setFixedWidth(220)
        sidebar.setObjectName("sidebar")
        sidebar.setStyleSheet(
            "#sidebar { background: #2b2b2b; border-right: 1px solid #444; }"
        )

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Buckets tree
        buckets_label = QLabel("Buckets")
        buckets_label.setStyleSheet("color: #aaa; font-weight: bold; font-size: 11px;")
        layout.addWidget(buckets_label)

        self._buckets_tree = QTreeWidget()
        self._buckets_tree.setHeaderHidden(True)
        self._buckets_tree.setRootIsDecorated(False)
        self._buckets_tree.setStyleSheet(
            "QTreeWidget { background: transparent; color: #ddd; border: none; }"
            "QTreeWidget::item:selected { background: #444; }"
        )
        for bucket in ("All Music", "DJ Music", "DJ Mixes", "General"):
            item = QTreeWidgetItem([bucket])
            self._buckets_tree.addTopLevelItem(item)
        layout.addWidget(self._buckets_tree)

        # Task queue tree
        queue_label = QLabel("Task Queue")
        queue_label.setStyleSheet("color: #aaa; font-weight: bold; font-size: 11px;")
        layout.addWidget(queue_label)

        self._task_tree = QTreeWidget()
        self._task_tree.setHeaderHidden(True)
        self._task_tree.setRootIsDecorated(False)
        self._task_tree.setStyleSheet(
            "QTreeWidget { background: transparent; color: #ddd; border: none; }"
        )
        placeholder = QTreeWidgetItem(["(no tasks)"])
        placeholder.setFlags(placeholder.flags() & ~Qt.ItemFlag.ItemIsSelectable)
        self._task_tree.addTopLevelItem(placeholder)
        layout.addWidget(self._task_tree)

        layout.addStretch()
        return sidebar

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def _show_page(self, index: int) -> None:
        self._stack.setCurrentIndex(index)

    # ------------------------------------------------------------------
    # Scanning
    # ------------------------------------------------------------------

    def _start_scan(self) -> None:
        if self._scan_worker and self._scan_worker.isRunning():
            return  # scan already in progress

        # Pull directories from settings widget (may have been edited by user)
        directories = self._settings_view.get_source_directories()
        if not directories:
            directories = self._config.source_directories

        self._scan_worker = ScanWorker(directories, self._db)
        self._scan_worker.progress.connect(self._on_scan_progress)
        self._scan_worker.finished.connect(self._on_scan_finished)

        self._progress_bar.setRange(0, 0)
        self._progress_bar.setVisible(True)
        self._status_label.setText("Scanning…")
        self._scan_worker.start()

    def _on_scan_progress(self, count: int, current_path: str) -> None:
        self._status_label.setText(f"Scanning… {count} files found — {current_path}")

    def _on_scan_finished(self, total: int) -> None:
        self._progress_bar.setVisible(False)
        self._status_label.setText(f"Scan complete — {total} files processed")
        self._refresh_library()

    # ------------------------------------------------------------------
    # Library refresh
    # ------------------------------------------------------------------

    def _refresh_library(self) -> None:
        tracks = self._db.get_all_tracks()
        self._library.load_tracks(tracks)

        raw_stats = self._db.get_stats()

        # Derive richer stats for the dashboard
        fully_tagged = sum(1 for t in tracks if t.tag_completeness >= 0.9)
        partially_tagged = sum(1 for t in tracks if 0.4 <= t.tag_completeness < 0.9)
        missing_tags = sum(1 for t in tracks if t.tag_completeness < 0.4)
        no_artwork = sum(1 for t in tracks if not t.has_artwork)

        stats = {
            **raw_stats,
            "fully_tagged": fully_tagged,
            "partially_tagged": partially_tagged,
            "missing_tags": missing_tags,
            "duplicates": 0,  # dedup not yet wired into the GUI
            "no_artwork": no_artwork,
        }
        self._dashboard.update_stats(stats)

    def closeEvent(self, event):
        if self._scan_worker and self._scan_worker.isRunning():
            self._scan_worker.cancel()
            self._scan_worker.wait(3000)
        self._db.close()
        super().closeEvent(event)
