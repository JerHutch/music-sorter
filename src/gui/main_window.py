from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QToolBar, QStackedWidget, QStatusBar, QProgressBar,
    QTreeWidget, QTreeWidgetItem, QLabel, QSplitter, QTabWidget,
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QAction

import logging

from src.core.config import Config, USER_CONFIG_PATH
from src.core.database import Database
from src.core.models import TagConflict, Track
from src.gui.dashboard import Dashboard
from src.gui.dupe_resolver import DupeResolver
from src.gui.itunes_import import ITunesImport
from src.gui.library_browser import LibraryBrowser
from src.gui.playlist_manager import PlaylistManager
from src.gui.rename_preview import RenamePreview
from src.gui.settings_view import SettingsView
from src.gui.tag_editor import TagEditor
from src.gui.workers import ScanWorker, TagWriteWorker

logger = logging.getLogger(__name__)

_PAGE_DASHBOARD = 0
_PAGE_LIBRARY   = 1
_PAGE_ORGANIZE  = 2
_PAGE_IMPORT    = 3
_PAGE_PLAYLISTS = 4
_PAGE_SETTINGS  = 5

_DB_DIR = Path.home() / ".local" / "share" / "music-sorter"


class MainWindow(QMainWindow):
    """Top-level application window."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Music Sorter")
        self.resize(1280, 800)

        self._config_path = USER_CONFIG_PATH
        self._config = Config.load_user_config(self._config_path)
        _DB_DIR.mkdir(parents=True, exist_ok=True)
        self._db = Database(_DB_DIR / "library.db")
        self._all_tracks: list[Track] = []
        self._scan_worker: ScanWorker | None = None
        self._tag_worker: TagWriteWorker | None = None

        self._build_ui()
        self._settings_view.load_config(self._config)
        self._settings_view.settings_changed.connect(self._save_config)
        self._refresh_library()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        toolbar = QToolBar("Navigation")
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(16, 16))
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, toolbar)

        nav_pages = [
            ("Dashboard", _PAGE_DASHBOARD),
            ("Library",   _PAGE_LIBRARY),
            ("Organize",  _PAGE_ORGANIZE),
            ("Import",    _PAGE_IMPORT),
            ("Playlists", _PAGE_PLAYLISTS),
            ("Settings",  _PAGE_SETTINGS),
        ]
        for name, page_idx in nav_pages:
            act = QAction(name, self)
            act.triggered.connect(lambda checked, idx=page_idx: self._show_page(idx))
            toolbar.addAction(act)
        toolbar.addSeparator()
        act_scan = QAction("Scan", self)
        act_scan.triggered.connect(self._start_scan)
        toolbar.addAction(act_scan)

        central = QWidget()
        self.setCentralWidget(central)
        h_layout = QHBoxLayout(central)
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.setSpacing(0)
        h_layout.addWidget(self._build_sidebar())

        self._stack = QStackedWidget()

        # Page 0: Dashboard
        self._dashboard = Dashboard()

        # Page 1: Library + TagEditor split
        library_split = QSplitter(Qt.Orientation.Horizontal)
        visible_cols = self._config.library_columns.get("visible", None)
        self._library = LibraryBrowser(visible_columns=visible_cols)
        self._tag_editor = TagEditor()
        self._tag_editor.setMinimumWidth(280)
        self._tag_editor.setVisible(False)
        library_split.addWidget(self._library)
        library_split.addWidget(self._tag_editor)
        library_split.setSizes([800, 300])
        library_split.setCollapsible(1, True)

        # Page 2: Organize tabs (Dupe Resolver + Rename Preview)
        organize_tabs = QTabWidget()
        self._dupe_resolver = DupeResolver()
        self._rename_preview = RenamePreview()
        organize_tabs.addTab(self._dupe_resolver, "Duplicates")
        organize_tabs.addTab(self._rename_preview, "Rename / Organize")

        # Page 3: iTunes Import
        self._itunes_import = ITunesImport()

        # Page 4: Playlists
        self._playlist_manager = PlaylistManager(db=self._db, all_tracks=self._all_tracks)

        # Page 5: Settings
        self._settings_view = SettingsView()

        self._stack.addWidget(self._dashboard)          # 0
        self._stack.addWidget(library_split)            # 1
        self._stack.addWidget(organize_tabs)            # 2
        self._stack.addWidget(self._itunes_import)      # 3
        self._stack.addWidget(self._playlist_manager)   # 4
        self._stack.addWidget(self._settings_view)      # 5
        h_layout.addWidget(self._stack, stretch=1)

        # Status bar
        status_bar = QStatusBar()
        self.setStatusBar(status_bar)
        self._status_label = QLabel("Ready")
        status_bar.addWidget(self._status_label, 1)
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 0)
        self._progress_bar.setFixedWidth(200)
        self._progress_bar.setVisible(False)
        status_bar.addPermanentWidget(self._progress_bar)

        # Wire library selection → tag editor
        self._library.selection_changed.connect(self._on_library_selection)
        # Wire column changes → config persistence
        self._library.columns_changed.connect(self._on_columns_changed)
        # Wire tag editor save
        self._tag_editor.save_requested.connect(self._on_tag_save)
        # Wire dupe resolver delete
        self._dupe_resolver.delete_requested.connect(self._on_delete_tracks)
        # Wire dupe resolver scan button to use all_tracks
        self._dupe_resolver.scan_requested.connect(self._start_dedup_scan)
        # Wire iTunes import apply
        self._itunes_import.apply_requested.connect(self._on_itunes_apply)
        # Wire rename complete → refresh
        self._rename_preview.rename_complete.connect(lambda _: self._refresh_library())

        self._stack.setCurrentIndex(_PAGE_DASHBOARD)

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

        # Buckets
        buckets_lbl = QLabel("Buckets")
        buckets_lbl.setStyleSheet("color: #aaa; font-weight: bold; font-size: 11px;")
        layout.addWidget(buckets_lbl)
        self._buckets_tree = QTreeWidget()
        self._buckets_tree.setHeaderHidden(True)
        self._buckets_tree.setRootIsDecorated(False)
        self._buckets_tree.setStyleSheet(
            "QTreeWidget { background: transparent; color: #ddd; border: none; }"
            "QTreeWidget::item:selected { background: #444; }"
        )
        self._bucket_items: dict[str, QTreeWidgetItem] = {}
        for bucket in ("All Music", "DJ Music", "DJ Mixes", "General"):
            item = QTreeWidgetItem([bucket])
            self._buckets_tree.addTopLevelItem(item)
            self._bucket_items[bucket] = item
        self._buckets_tree.itemClicked.connect(self._on_bucket_clicked)
        layout.addWidget(self._buckets_tree)

        # Task queue
        queue_lbl = QLabel("Task Queue")
        queue_lbl.setStyleSheet("color: #aaa; font-weight: bold; font-size: 11px;")
        layout.addWidget(queue_lbl)
        self._task_tree = QTreeWidget()
        self._task_tree.setHeaderHidden(True)
        self._task_tree.setRootIsDecorated(False)
        self._task_tree.setStyleSheet(
            "QTreeWidget { background: transparent; color: #ddd; border: none; }"
            "QTreeWidget::item:selected { background: #444; }"
        )
        self._task_items: dict[str, QTreeWidgetItem] = {}
        for task in ("Missing Tags", "No Artwork"):
            item = QTreeWidgetItem([task])
            self._task_tree.addTopLevelItem(item)
            self._task_items[task] = item
        self._task_tree.itemClicked.connect(self._on_task_clicked)
        layout.addWidget(self._task_tree)

        layout.addStretch()
        return sidebar

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def _show_page(self, index: int) -> None:
        self._stack.setCurrentIndex(index)
        if index == _PAGE_ORGANIZE:
            self._rename_preview.set_tracks(self._all_tracks)
            self._rename_preview.set_patterns(self._config.rename_patterns)
        elif index == _PAGE_IMPORT:
            self._itunes_import.set_tracks(self._all_tracks, self._config.source_directories)
        elif index == _PAGE_PLAYLISTS:
            self._playlist_manager.set_tracks(self._all_tracks)

    # ------------------------------------------------------------------
    # Sidebar
    # ------------------------------------------------------------------

    def _on_bucket_clicked(self, item: QTreeWidgetItem, _col: int) -> None:
        self._show_page(_PAGE_LIBRARY)
        self._library.filter_by_bucket(item.text(0).split(" (")[0])

    def _on_task_clicked(self, item: QTreeWidgetItem, _col: int) -> None:
        task = item.text(0).split(" (")[0]
        self._show_page(_PAGE_LIBRARY)
        if task == "Missing Tags":
            self._library.filter_by_fn(lambda t: t.tag_completeness < 0.4)
        elif task == "No Artwork":
            self._library.filter_by_fn(lambda t: not t.has_artwork)

    # ------------------------------------------------------------------
    # Config
    # ------------------------------------------------------------------

    def _save_config(self) -> None:
        self._config.source_directories = self._settings_view.get_source_directories()
        self._config.itunes_xml_path = self._settings_view.get_itunes_path()
        self._config.save(self._config_path)

    def _on_columns_changed(self, columns: list[str]) -> None:
        self._config.set_visible_columns(columns)
        self._config.save(self._config_path)

    # ------------------------------------------------------------------
    # Scanning
    # ------------------------------------------------------------------

    def _start_scan(self) -> None:
        if self._scan_worker and self._scan_worker.isRunning():
            return
        directories = (
            self._settings_view.get_source_directories()
            or self._config.source_directories
        )
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
        self._all_tracks = self._db.get_all_tracks()
        self._library.load_tracks(self._all_tracks)
        self._playlist_manager.set_tracks(self._all_tracks)

        raw_stats = self._db.get_stats()
        fully_tagged    = sum(1 for t in self._all_tracks if t.tag_completeness >= 0.9)
        partially_tagged = sum(1 for t in self._all_tracks if 0.4 <= t.tag_completeness < 0.9)
        missing_tags    = sum(1 for t in self._all_tracks if t.tag_completeness < 0.4)
        no_artwork      = sum(1 for t in self._all_tracks if not t.has_artwork)

        stats = {
            **raw_stats,
            "fully_tagged": fully_tagged,
            "partially_tagged": partially_tagged,
            "missing_tags": missing_tags,
            "duplicates": 0,
            "no_artwork": no_artwork,
        }
        self._dashboard.update_stats(stats)
        self._update_sidebar_counts(missing_tags, no_artwork, raw_stats.get("bucket_counts", {}))

    def _update_sidebar_counts(self, missing_tags: int, no_artwork: int,
                                bucket_counts: dict) -> None:
        total = len(self._all_tracks)
        self._bucket_items["All Music"].setText(0, f"All Music ({total})")
        for bucket in ("DJ Music", "DJ Mixes", "General"):
            count = bucket_counts.get(bucket, 0)
            self._bucket_items[bucket].setText(0, f"{bucket} ({count})")
        self._task_items["Missing Tags"].setText(0, f"Missing Tags ({missing_tags})")
        self._task_items["No Artwork"].setText(0, f"No Artwork ({no_artwork})")

    # ------------------------------------------------------------------
    # Tag editing
    # ------------------------------------------------------------------

    def _on_library_selection(self, tracks: list[Track]) -> None:
        if not tracks:
            self._tag_editor.setVisible(False)
            return
        self._tag_editor.setVisible(True)
        if len(tracks) == 1:
            self._tag_editor.load_track(tracks[0])
        else:
            self._tag_editor.load_tracks(tracks)

    def _on_tag_save(self, tracks: list[Track], changes: dict[str, str]) -> None:
        if self._tag_worker and self._tag_worker.isRunning():
            return
        for track in tracks:
            for field, value in changes.items():
                if field in ("track_number", "disc_number", "year"):
                    setattr(track, field, int(value) if value else None)
                elif field == "bpm":
                    setattr(track, field, float(value) if value else None)
                else:
                    setattr(track, field, value or None)
        pairs = [(track, list(changes.keys())) for track in tracks]
        self._tag_worker = TagWriteWorker(pairs, self._db)
        self._tag_worker.finished.connect(self._on_tag_write_finished)
        self._tag_worker.error.connect(
            lambda msg: self._status_label.setText(f"Tag write error: {msg}")
        )
        self._tag_worker.start()
        self._status_label.setText(f"Writing tags for {len(tracks)} track(s)…")

    def _on_tag_write_finished(self, updated: list) -> None:
        self._status_label.setText(f"Saved tags for {len(updated)} track(s)")
        self._refresh_library()

    # ------------------------------------------------------------------
    # Deduplication
    # ------------------------------------------------------------------

    def _start_dedup_scan(self) -> None:
        dedup_cfg = self._config.deduplication
        self._dupe_resolver.start_scan(
            self._all_tracks,
            duration_tolerance=dedup_cfg.get("duration_tolerance", 2.0),
            similarity_threshold=dedup_cfg.get("similarity_threshold", 0.85),
        )

    def _on_delete_tracks(self, tracks: list[Track]) -> None:
        for track in tracks:
            self._db.delete_track(track.file_path)
        self._refresh_library()
        self._status_label.setText(f"Removed {len(tracks)} duplicate(s) from library.")

    # ------------------------------------------------------------------
    # iTunes import
    # ------------------------------------------------------------------

    def _on_itunes_apply(self, conflicts: list[TagConflict]) -> None:
        if self._tag_worker and self._tag_worker.isRunning():
            return
        itunes_edits: dict[Path, tuple[Track, list[str]]] = {}
        for conflict in conflicts:
            if conflict.resolution != "itunes":
                continue
            track = next((t for t in self._all_tracks if t.file_path == conflict.file_path), None)
            if track is None:
                continue
            setattr(track, conflict.field, conflict.itunes_value)
            if conflict.file_path not in itunes_edits:
                itunes_edits[conflict.file_path] = (track, [])
            itunes_edits[conflict.file_path][1].append(conflict.field)
        if not itunes_edits:
            return
        self._tag_worker = TagWriteWorker(list(itunes_edits.values()), self._db)
        self._tag_worker.finished.connect(self._on_itunes_write_finished)
        self._tag_worker.error.connect(
            lambda msg: self._status_label.setText(f"iTunes tag write error: {msg}")
        )
        self._tag_worker.start()

    def _on_itunes_write_finished(self, updated: list) -> None:
        self._status_label.setText(f"Applied iTunes tags to {len(updated)} track(s)")
        self._refresh_library()

    # ------------------------------------------------------------------
    # Close
    # ------------------------------------------------------------------

    def closeEvent(self, event):
        for worker in (self._scan_worker, self._tag_worker):
            if worker and worker.isRunning():
                if hasattr(worker, "cancel"):
                    worker.cancel()
                worker.wait(3000)
        self._db.close()
        super().closeEvent(event)
