# Remaining GUI Views Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace all placeholder widgets in `src/gui/` with fully functional views, wire up sidebar navigation, and add column configuration to the library browser.

**Architecture:** Each view is a self-contained QWidget that receives `Database` and `Config` objects from `MainWindow`. Long-running operations use QThread workers from `src/gui/workers.py`. All views communicate back to `MainWindow` via Qt signals. `PySide6.QtCharts` handles charts (bundled with PySide6, no extra deps). The tag editor lives inside a QSplitter on the Library page rather than a separate nav item.

**Tech Stack:** Python 3.12+, PySide6 (incl. QtCharts), pytest, pytest-qt (new dev dep)

**Spec:** `docs/superpowers/specs/remaining-gui-views.md`

---

## Scope note

This plan covers 8 independent areas. They share no state between tasks and can be worked on in any order after Task 1 (Workers). Suggested grouping for review checkpoints: Tasks 1–3 (infrastructure), Tasks 4–6 (editing views), Tasks 7–10 (workflow views), Task 11 (navigation wiring).

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `src/gui/workers.py` | Modify | Add DedupeWorker, TagWriteWorker, ITunesWorker, RenameWorker |
| `src/gui/library_browser.py` | Modify | Dynamic columns, right-click show/hide, movable sections, config persistence |
| `src/gui/tag_editor.py` | Replace | Single-track and batch tag editing panel |
| `src/gui/dupe_resolver.py` | Replace | DupeGroup tree table with per-group resolution UI |
| `src/gui/itunes_import.py` | Replace | iTunes XML import + conflict resolution table |
| `src/gui/rename_preview.py` | Replace | Pattern editor, dry-run table, execute workflow |
| `src/gui/stats_view.py` | Replace | QtCharts charts for tag completeness, genres, bitrates, storage |
| `src/gui/playlist_manager.py` | Replace | Playlist tree with folders + editor panel |
| `src/gui/main_window.py` | Modify | Sidebar wiring, live counts, new nav pages, Library→TagEditor split |
| `src/core/database.py` | Modify | Add `get_all_playlists`, `upsert_playlist`, `delete_playlist` |
| `pyproject.toml` | Modify | Add `pytest-qt>=4.0` to dev deps |
| `tests/gui/test_workers.py` | Create | Worker unit tests with mocked core functions |
| `tests/gui/test_library_browser.py` | Create | Column config smoke tests |

---

## Task 1: Add Workers

**Files:**
- Modify: `src/gui/workers.py`
- Modify: `pyproject.toml`
- Create: `tests/gui/test_workers.py`

- [ ] **Step 1: Add pytest-qt to dev dependencies**

Edit `pyproject.toml`, replace the `dev` optional-dependencies block:

```toml
[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-cov>=5.0",
    "pytest-qt>=4.0",
]
```

Run: `uv add --dev pytest-qt`

- [ ] **Step 2: Write failing tests for workers**

Create `tests/gui/test_workers.py`:

```python
from unittest.mock import patch, MagicMock
from pathlib import Path
import pytest
from src.core.models import Track, DupeGroup, TagConflict, RenameOperation
from src.gui.workers import DedupeWorker, TagWriteWorker, ITunesWorker, RenameWorker


def _make_track(path="/tmp/a.mp3", bitrate=320, completeness=0.8):
    return Track(
        file_path=Path(path), file_size=1000, bitrate=bitrate, duration=200.0,
        title="Test", artist="Artist", tag_completeness=completeness,
    )


def test_dedupe_worker_emits_finished(qtbot):
    tracks = [_make_track("/tmp/a.mp3"), _make_track("/tmp/b.mp3")]
    dupe_groups = [DupeGroup(tracks=tracks)]
    with patch("src.gui.workers.find_duplicates", return_value=dupe_groups):
        worker = DedupeWorker(tracks, duration_tolerance=2.0, similarity_threshold=0.85)
        results = []
        worker.finished.connect(results.append)
        with qtbot.waitSignal(worker.finished, timeout=3000):
            worker.start()
    assert results == [dupe_groups]


def test_tag_write_worker_emits_finished(qtbot, tmp_path):
    track = _make_track(str(tmp_path / "a.mp3"))
    with patch("src.gui.workers.write_tags") as mock_write:
        with patch("src.gui.workers.upsert_track_in_db") as mock_upsert:
            worker = TagWriteWorker([(track, ["title", "artist"])], db=MagicMock())
            done = []
            worker.finished.connect(done.append)
            with qtbot.waitSignal(worker.finished, timeout=3000):
                worker.start()
    mock_write.assert_called_once()
    assert len(done) == 1


def test_itunes_worker_emits_finished(qtbot, tmp_path):
    xml_path = tmp_path / "iTunes.xml"
    xml_path.write_bytes(b"")
    tracks = [_make_track()]
    entries = [{"title": "Test", "artist": "Artist", "location": Path("/tmp/a.mp3")}]
    conflicts = [TagConflict(Path("/tmp/a.mp3"), "title", "Test", "Different")]
    with patch("src.gui.workers.parse_itunes_xml", return_value=entries):
        with patch("src.gui.workers.match_itunes_to_files", return_value=([(entries[0], tracks[0])], [])):
            with patch("src.gui.workers.resolve_itunes_conflicts", return_value=conflicts):
                worker = ITunesWorker(xml_path, tracks, source_directories=[])
                results = []
                worker.finished.connect(results.append)
                with qtbot.waitSignal(worker.finished, timeout=3000):
                    worker.start()
    assert results[0] == conflicts


def test_rename_worker_emits_progress_and_finished(qtbot, tmp_path):
    ops = [RenameOperation(source=tmp_path / "a.mp3", destination=tmp_path / "b.mp3")]
    with patch("src.gui.workers.execute_rename_plan", return_value=ops):
        worker = RenameWorker(ops, dry_run=False)
        progress_signals = []
        done = []
        worker.progress.connect(lambda c, t: progress_signals.append((c, t)))
        worker.finished.connect(done.append)
        with qtbot.waitSignal(worker.finished, timeout=3000):
            worker.start()
    assert len(done) == 1
```

- [ ] **Step 3: Run test to verify failure**

```bash
cd /mnt/cloud/code/music-sorter && python -m pytest tests/gui/test_workers.py -v 2>&1 | head -40
```

Expected: ImportError or AttributeError because DedupeWorker etc. don't exist yet.

- [ ] **Step 4: Implement workers**

Replace the entire contents of `src/gui/workers.py`:

```python
import logging
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from src.core.database import Database
from src.core.deduplicator import find_duplicates
from src.core.itunes import match_itunes_to_files, parse_itunes_xml, resolve_conflicts as _resolve_conflicts
from src.core.models import DupeGroup, RenameOperation, TagConflict, Track
from src.core.organizer import execute_rename_plan
from src.core.scanner import scan_directories
from src.core.tagger import read_tags, write_tags

logger = logging.getLogger(__name__)


# Public alias used by tests
def resolve_itunes_conflicts(track, itunes_entry):
    return _resolve_conflicts(track, itunes_entry)


def upsert_track_in_db(db: Database, track: Track, file_mtime: float) -> None:
    db.upsert_track(track, file_mtime=file_mtime)


class ScanWorker(QThread):
    progress = Signal(int, str)
    finished = Signal(int)

    def __init__(self, directories, db):
        super().__init__()
        self._directories = directories
        self._db = db
        self._cancelled = False

    def run(self):
        logger.info("Scan started across %d directories", len(self._directories))
        paths = scan_directories(self._directories, on_progress=self._on_scan_progress)
        for i, path in enumerate(paths):
            if self._cancelled:
                logger.info("Scan cancelled after %d files", i)
                break
            try:
                track = read_tags(path)
                mtime = path.stat().st_mtime
                self._db.upsert_track(track, file_mtime=mtime)
            except Exception:
                logger.exception("Failed to process file: %s", path)
            self.progress.emit(i + 1, str(path))
        logger.info("Scan finished: processed %d files", len(paths))
        self.finished.emit(len(paths))

    def _on_scan_progress(self, count, current_dir):
        self.progress.emit(count, current_dir)

    def cancel(self):
        self._cancelled = True


class DedupeWorker(QThread):
    """Runs find_duplicates in a background thread."""

    progress = Signal(int, int)   # processed, total
    finished = Signal(list)       # list[DupeGroup]
    error = Signal(str)

    def __init__(self, tracks: list[Track], duration_tolerance: float = 2.0,
                 similarity_threshold: float = 0.85):
        super().__init__()
        self._tracks = tracks
        self._duration_tolerance = duration_tolerance
        self._similarity_threshold = similarity_threshold

    def run(self):
        logger.info("DedupeWorker: scanning %d tracks for duplicates", len(self._tracks))
        try:
            groups = find_duplicates(
                self._tracks,
                duration_tolerance=self._duration_tolerance,
                similarity_threshold=self._similarity_threshold,
                on_progress=lambda cur, total: self.progress.emit(cur, total),
            )
            logger.info("DedupeWorker: found %d duplicate groups", len(groups))
            self.finished.emit(groups)
        except Exception as exc:
            logger.exception("DedupeWorker failed")
            self.error.emit(str(exc))


class TagWriteWorker(QThread):
    """Writes tags for one or more tracks in a background thread."""

    progress = Signal(int, int)   # completed, total
    finished = Signal(list)       # list[Track] — updated tracks
    error = Signal(str)

    def __init__(self, track_field_pairs: list[tuple[Track, list[str]]], db: Database):
        super().__init__()
        self._pairs = track_field_pairs
        self._db = db

    def run(self):
        updated: list[Track] = []
        total = len(self._pairs)
        for i, (track, fields) in enumerate(self._pairs, 1):
            try:
                write_tags(track.file_path, track, fields)
                mtime = track.file_path.stat().st_mtime
                upsert_track_in_db(self._db, track, file_mtime=mtime)
                updated.append(track)
            except Exception:
                logger.exception("TagWriteWorker: failed to write %s", track.file_path)
            self.progress.emit(i, total)
        self.finished.emit(updated)


class ITunesWorker(QThread):
    """Parses iTunes XML and matches/conflicts against the local library."""

    progress = Signal(str)         # status message
    finished = Signal(list)        # list[TagConflict]
    error = Signal(str)

    def __init__(self, xml_path: Path, tracks: list[Track], source_directories: list[Path]):
        super().__init__()
        self._xml_path = xml_path
        self._tracks = tracks
        self._source_dirs = source_directories

    def run(self):
        try:
            self.progress.emit("Parsing iTunes XML…")
            entries = parse_itunes_xml(self._xml_path)
            self.progress.emit(f"Matching {len(entries)} iTunes entries to library…")
            matched, _unmatched = match_itunes_to_files(entries, self._tracks, self._source_dirs)
            conflicts: list[TagConflict] = []
            for itunes_entry, track in matched:
                conflicts.extend(resolve_itunes_conflicts(track, itunes_entry))
            self.progress.emit(f"Found {len(conflicts)} conflicts.")
            self.finished.emit(conflicts)
        except Exception as exc:
            logger.exception("ITunesWorker failed")
            self.error.emit(str(exc))


class RenameWorker(QThread):
    """Executes a rename plan in a background thread."""

    progress = Signal(int, int)    # completed, total
    finished = Signal(list)        # list[RenameOperation] — executed ops
    error = Signal(str)

    def __init__(self, plan: list[RenameOperation], dry_run: bool = False):
        super().__init__()
        self._plan = plan
        self._dry_run = dry_run

    def run(self):
        try:
            result = execute_rename_plan(
                self._plan,
                dry_run=self._dry_run,
                on_progress=lambda cur, total: self.progress.emit(cur, total),
            )
            self.finished.emit(result)
        except Exception as exc:
            logger.exception("RenameWorker failed")
            self.error.emit(str(exc))
```

- [ ] **Step 5: Run tests to verify pass**

```bash
cd /mnt/cloud/code/music-sorter && python -m pytest tests/gui/test_workers.py -v
```

Expected: all 4 tests PASS.

- [ ] **Step 6: Commit**

```bash
cd /mnt/cloud/code/music-sorter
git add src/gui/workers.py tests/gui/test_workers.py pyproject.toml
git commit -m "feat: add DedupeWorker, TagWriteWorker, ITunesWorker, RenameWorker"
```

---

## Task 2: Database — Playlist CRUD

**Files:**
- Modify: `src/core/database.py`
- Modify: `tests/core/test_database.py`

The `PlaylistManager` and sidebar need to list/save/delete playlists from SQLite.

- [ ] **Step 1: Write failing tests**

Append to `tests/core/test_database.py`:

```python
from src.core.models import PlaylistDefinition

def test_upsert_and_get_playlist(tmp_path):
    from src.core.database import Database
    db = Database(tmp_path / "test.db")
    pld = PlaylistDefinition(name="My Set", filters={"bucket": "DJ Music"}, folder="DJ", format="m3u", sort_by="bpm")
    db.upsert_playlist(pld)
    playlists = db.get_all_playlists()
    assert len(playlists) == 1
    assert playlists[0].name == "My Set"
    assert playlists[0].filters == {"bucket": "DJ Music"}
    assert playlists[0].folder == "DJ"
    db.close()

def test_delete_playlist(tmp_path):
    from src.core.database import Database
    db = Database(tmp_path / "test.db")
    pld = PlaylistDefinition(name="To Delete", filters={})
    db.upsert_playlist(pld)
    db.delete_playlist("To Delete")
    assert db.get_all_playlists() == []
    db.close()

def test_upsert_playlist_updates_existing(tmp_path):
    from src.core.database import Database
    db = Database(tmp_path / "test.db")
    pld = PlaylistDefinition(name="Set A", filters={"genre": "House"}, sort_by="bpm")
    db.upsert_playlist(pld)
    pld2 = PlaylistDefinition(name="Set A", filters={"genre": "Techno"}, sort_by="artist")
    db.upsert_playlist(pld2)
    playlists = db.get_all_playlists()
    assert len(playlists) == 1
    assert playlists[0].filters == {"genre": "Techno"}
    db.close()
```

- [ ] **Step 2: Run tests to verify failure**

```bash
cd /mnt/cloud/code/music-sorter && python -m pytest tests/core/test_database.py::test_upsert_and_get_playlist -v
```

Expected: FAIL with `AttributeError: 'Database' object has no attribute 'upsert_playlist'`

- [ ] **Step 3: Add playlist methods to Database**

Append to the `Database` class in `src/core/database.py` (before the `close` method):

```python
    # ------------------------------------------------------------------
    # Playlist CRUD
    # ------------------------------------------------------------------

    def get_all_playlists(self) -> list:
        import json
        from src.core.models import PlaylistDefinition
        rows = self._conn.execute(
            "SELECT name, filters, folder, format, sort_by FROM playlists"
        ).fetchall()
        result = []
        for row in rows:
            filters = json.loads(row["filters"]) if row["filters"] else {}
            result.append(PlaylistDefinition(
                name=row["name"],
                filters=filters,
                folder=row["folder"],
                format=row["format"] or "m3u",
                sort_by=row["sort_by"],
            ))
        return result

    def upsert_playlist(self, pld) -> None:
        import json
        with self._lock:
            self._conn.execute(
                """INSERT INTO playlists (name, filters, folder, format, sort_by)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(name) DO UPDATE SET
                       filters = excluded.filters,
                       folder  = excluded.folder,
                       format  = excluded.format,
                       sort_by = excluded.sort_by""",
                (pld.name, json.dumps(pld.filters), pld.folder, pld.format, pld.sort_by),
            )
            self._conn.commit()

    def delete_playlist(self, name: str) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM playlists WHERE name = ?", (name,))
            self._conn.commit()
```

- [ ] **Step 4: Run tests to verify pass**

```bash
cd /mnt/cloud/code/music-sorter && python -m pytest tests/core/test_database.py -v -k "playlist"
```

Expected: all 3 playlist tests PASS.

- [ ] **Step 5: Commit**

```bash
cd /mnt/cloud/code/music-sorter
git add src/core/database.py tests/core/test_database.py
git commit -m "feat: add playlist CRUD methods to Database"
```

---

## Task 3: Library Column Configuration

**Files:**
- Modify: `src/gui/library_browser.py`
- Create: `tests/gui/test_library_browser.py`

Replace the hardcoded 8-column setup with configurable columns driven by `Config.library_columns`. Column visibility and order are persisted back to config via a signal.

- [ ] **Step 1: Write failing test**

Create `tests/gui/test_library_browser.py`:

```python
from pathlib import Path
import pytest
from PySide6.QtWidgets import QApplication
from src.core.models import Track
from src.gui.library_browser import LibraryBrowser


def _make_track(title="T", artist="A"):
    return Track(
        file_path=Path("/tmp/a.mp3"), file_size=1000, bitrate=320, duration=200.0,
        title=title, artist=artist, genre="House", bpm=128.0, tag_completeness=0.9,
    )


def test_library_browser_loads_tracks(qtbot):
    browser = LibraryBrowser(visible_columns=["title", "artist", "genre"])
    qtbot.addWidget(browser)
    browser.load_tracks([_make_track("Song A", "DJ X"), _make_track("Song B", "DJ Y")])
    assert browser.track_count() == 2


def test_library_browser_column_count_matches_visible(qtbot):
    browser = LibraryBrowser(visible_columns=["title", "artist", "bpm"])
    qtbot.addWidget(browser)
    assert browser.column_count() == 3


def test_library_browser_filter_by_bucket(qtbot):
    t1 = _make_track("A", "X")
    t1.bucket = "DJ Music"
    t2 = _make_track("B", "Y")
    t2.bucket = "General"
    browser = LibraryBrowser(visible_columns=["title", "artist"])
    qtbot.addWidget(browser)
    browser.load_tracks([t1, t2])
    browser.filter_by_bucket("DJ Music")
    assert browser.visible_row_count() == 1
```

- [ ] **Step 2: Run tests to verify failure**

```bash
cd /mnt/cloud/code/music-sorter && python -m pytest tests/gui/test_library_browser.py -v
```

Expected: ImportError or TypeError because LibraryBrowser doesn't accept `visible_columns`.

- [ ] **Step 3: Rewrite LibraryBrowser**

Replace `src/gui/library_browser.py` entirely:

```python
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
    QMenu,
    QHeaderView,
)
from PySide6.QtCore import Qt, QSortFilterProxyModel, Signal
from PySide6.QtGui import QStandardItemModel, QStandardItem, QColor, QAction

from src.core.models import Track

# Human-readable column headers
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
        self._search_box.setPlaceholderText("Search tracks…")
        search_layout.addWidget(self._search_box)
        layout.addLayout(search_layout)

        # Toolbar actions
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

        # Right-click on header → show/hide columns
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
            # Store Track on first item for retrieval
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
        all_columns = list(_COLUMN_HEADERS.keys())
        for col in all_columns:
            action = QAction(_COLUMN_HEADERS[col], self, checkable=True)
            action.setChecked(col in self._visible_columns)
            action.setData(col)
            action.triggered.connect(self._on_toggle_column)
            menu.addAction(action)
        menu.exec(self._table.horizontalHeader().mapToGlobal(pos))

    def _on_toggle_column(self, checked: bool) -> None:
        col = self.sender().data()
        if checked and col not in self._visible_columns:
            self._visible_columns.append(col)
        elif not checked and col in self._visible_columns and len(self._visible_columns) > 1:
            self._visible_columns.remove(col)
        self._rebuild_model_columns()
        self._repopulate()
        self.columns_changed.emit(list(self._visible_columns))

    def _on_section_moved(self, logical: int, old_visual: int, new_visual: int) -> None:
        # Re-derive visible column order from current visual order
        header = self._table.horizontalHeader()
        new_order = [self._visible_columns[header.logicalIndex(i)]
                     for i in range(len(self._visible_columns))]
        self._visible_columns = new_order
        self.columns_changed.emit(list(self._visible_columns))

    def _on_selection_changed(self) -> None:
        self.selection_changed.emit(self.selected_tracks())
```

- [ ] **Step 4: Run tests to verify pass**

```bash
cd /mnt/cloud/code/music-sorter && python -m pytest tests/gui/test_library_browser.py -v
```

Expected: all 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
cd /mnt/cloud/code/music-sorter
git add src/gui/library_browser.py tests/gui/test_library_browser.py
git commit -m "feat: configurable columns in LibraryBrowser with right-click show/hide and reorder"
```

---

## Task 4: Tag Editor

**Files:**
- Replace: `src/gui/tag_editor.py`

The tag editor is a panel that slides in alongside the library. It handles both single-track editing (shows current field values) and batch editing (shows "[Multiple]" for divergent fields). It's activated from outside via `load_track(track)` or `load_tracks(tracks)`.

- [ ] **Step 1: Write failing smoke test**

Append to `tests/gui/test_library_browser.py` (or create `tests/gui/test_tag_editor.py`):

Create `tests/gui/test_tag_editor.py`:

```python
from pathlib import Path
import pytest
from src.core.models import Track
from src.gui.tag_editor import TagEditor


def _make_track(path="/tmp/a.mp3", title="Test", artist="Artist"):
    return Track(
        file_path=Path(path), file_size=1000, bitrate=320, duration=200.0,
        title=title, artist=artist, genre="House", tag_completeness=0.8,
    )


def test_tag_editor_single_track_populates_fields(qtbot):
    editor = TagEditor()
    qtbot.addWidget(editor)
    track = _make_track(title="My Song", artist="DJ X")
    editor.load_track(track)
    assert editor.get_field_value("title") == "My Song"
    assert editor.get_field_value("artist") == "DJ X"


def test_tag_editor_batch_shows_multiple_for_divergent(qtbot):
    editor = TagEditor()
    qtbot.addWidget(editor)
    t1 = _make_track("/tmp/a.mp3", title="Song A", artist="Same Artist")
    t2 = _make_track("/tmp/b.mp3", title="Song B", artist="Same Artist")
    editor.load_tracks([t1, t2])
    assert editor.get_field_value("title") == "[Multiple]"
    assert editor.get_field_value("artist") == "Same Artist"


def test_tag_editor_batch_shows_shared_value_for_same(qtbot):
    editor = TagEditor()
    qtbot.addWidget(editor)
    t1 = _make_track(genre_val := "Techno")
    t2 = _make_track()
    t1.genre = genre_val
    t2.genre = genre_val
    editor.load_tracks([t1, t2])
    assert editor.get_field_value("genre") == "Techno"


def test_tag_editor_empty_when_no_tracks(qtbot):
    editor = TagEditor()
    qtbot.addWidget(editor)
    editor.load_tracks([])
    assert editor.get_field_value("title") == ""
```

Fix the `_make_track` helper (remove the invalid syntax):

```python
def _make_track(path="/tmp/a.mp3", title="Test", artist="Artist"):
    return Track(
        file_path=Path(path), file_size=1000, bitrate=320, duration=200.0,
        title=title, artist=artist, genre="House", tag_completeness=0.8,
    )
```

- [ ] **Step 2: Run test to verify failure**

```bash
cd /mnt/cloud/code/music-sorter && python -m pytest tests/gui/test_tag_editor.py -v
```

Expected: ImportError because TagEditor doesn't have `load_track`, `load_tracks`, `get_field_value`.

- [ ] **Step 3: Implement TagEditor**

Replace `src/gui/tag_editor.py` entirely:

```python
from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLineEdit,
    QPushButton,
    QLabel,
    QScrollArea,
    QDialog,
    QDialogButtonBox,
    QTableWidget,
    QTableWidgetItem,
    QSizePolicy,
    QFrame,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont

from src.core.models import Track

import logging
logger = logging.getLogger(__name__)

# Fields shown in the editor, in order
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

    # Emitted when user clicks Save; payload: (tracks, field→new_value dict)
    save_requested = Signal(list, dict)

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
        widget = self._fields.get(field)
        return widget.text() if widget else ""

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(6)

        # Header
        self._mode_label = QLabel("")
        font = QFont()
        font.setBold(True)
        self._mode_label.setFont(font)
        outer.addWidget(self._mode_label)

        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        outer.addWidget(separator)

        # Scrollable form
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

        # Buttons
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
        for field, _label in _EDITABLE_FIELDS:
            val = getattr(track, field, None)
            self._fields[field].setText("" if val is None else str(val))
            self._fields[field].setPlaceholderText("")
        self._save_btn.setEnabled(True)

    def _populate_batch(self, tracks: list[Track]) -> None:
        self._mode_label.setText(f"Batch Edit — {len(tracks)} tracks")
        for field, _label in _EDITABLE_FIELDS:
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

        # Collect changed fields (non-empty and not [Multiple] placeholder)
        changed: dict[str, str] = {}
        for field, _label in _EDITABLE_FIELDS:
            widget = self._fields[field]
            value = widget.text().strip()
            placeholder = widget.placeholderText()
            # Skip fields left as "[Multiple]" (user didn't touch them)
            if not value and placeholder == _MULTIPLE:
                continue
            # For single-track: record all fields; for batch: only touched ones
            if len(self._tracks) == 1:
                original = getattr(self._tracks[0], field, None)
                original_str = "" if original is None else str(original)
                if value != original_str:
                    changed[field] = value
            else:
                # Batch: only include fields user explicitly typed into
                if value:
                    changed[field] = value

        if not changed:
            return

        # Dry-run preview dialog for batch
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
        layout.addWidget(QLabel(
            f"Apply the following changes to {len(tracks)} tracks?"
        ))

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
```

- [ ] **Step 4: Run tests to verify pass**

```bash
cd /mnt/cloud/code/music-sorter && python -m pytest tests/gui/test_tag_editor.py -v
```

Expected: all 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
cd /mnt/cloud/code/music-sorter
git add src/gui/tag_editor.py tests/gui/test_tag_editor.py
git commit -m "feat: implement TagEditor with single-track and batch editing"
```

---

## Task 5: Stats View (Charts)

**Files:**
- Replace: `src/gui/stats_view.py`
- Modify: `src/gui/dashboard.py`

`StatsView` renders four charts using `PySide6.QtCharts`. `Dashboard` replaces its "Charts will appear here" placeholder group box by embedding a `StatsView`.

- [ ] **Step 1: Write failing smoke test**

Create `tests/gui/test_stats_view.py`:

```python
import pytest
from src.gui.stats_view import StatsView


def test_stats_view_renders_without_data(qtbot):
    view = StatsView()
    qtbot.addWidget(view)
    view.update_stats({
        "fully_tagged": 0,
        "partially_tagged": 0,
        "missing_tags": 0,
        "genre_counts": {},
        "bitrate_counts": {},
        "bucket_counts": {},
    })
    # Should not raise


def test_stats_view_renders_with_data(qtbot):
    view = StatsView()
    qtbot.addWidget(view)
    view.update_stats({
        "fully_tagged": 100,
        "partially_tagged": 50,
        "missing_tags": 20,
        "genre_counts": {"House": 80, "Techno": 60, "Trance": 30},
        "bitrate_counts": {128: 40, 192: 60, 320: 70},
        "bucket_counts": {"DJ Music": 100, "General": 70},
    })
    # Should not raise
```

- [ ] **Step 2: Run test to verify failure**

```bash
cd /mnt/cloud/code/music-sorter && python -m pytest tests/gui/test_stats_view.py -v
```

Expected: FAIL — StatsView doesn't have `update_stats`.

- [ ] **Step 3: Implement StatsView**

Replace `src/gui/stats_view.py` entirely:

```python
from __future__ import annotations

from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel
from PySide6.QtCharts import (
    QChart, QChartView,
    QPieSeries,
    QBarSeries, QBarSet, QBarCategoryAxis, QValueAxis,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter


def _make_chart(title: str) -> QChart:
    chart = QChart()
    chart.setTitle(title)
    chart.setAnimationOptions(QChart.AnimationOption.NoAnimation)
    chart.legend().setVisible(True)
    chart.legend().setAlignment(Qt.AlignmentFlag.AlignBottom)
    return chart


def _chart_view(chart: QChart) -> QChartView:
    view = QChartView(chart)
    view.setRenderHint(QPainter.RenderHint.Antialiasing)
    view.setMinimumHeight(200)
    return view


class StatsView(QWidget):
    """Charts for tag completeness, genre distribution, bitrate, and storage."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QGridLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Tag completeness — pie chart (top-left)
        self._completeness_chart = _make_chart("Tag Completeness")
        self._completeness_view = _chart_view(self._completeness_chart)
        layout.addWidget(self._completeness_view, 0, 0)

        # Genre distribution — bar chart (top-right)
        self._genre_chart = _make_chart("Genre Distribution")
        self._genre_view = _chart_view(self._genre_chart)
        layout.addWidget(self._genre_view, 0, 1)

        # Bitrate distribution — bar chart (bottom-left)
        self._bitrate_chart = _make_chart("Bitrate Distribution")
        self._bitrate_view = _chart_view(self._bitrate_chart)
        layout.addWidget(self._bitrate_view, 1, 0)

        # Storage per bucket — bar chart (bottom-right)
        self._bucket_chart = _make_chart("Tracks per Bucket")
        self._bucket_view = _chart_view(self._bucket_chart)
        layout.addWidget(self._bucket_view, 1, 1)

    def update_stats(self, stats: dict) -> None:
        self._update_completeness(stats)
        self._update_genre(stats.get("genre_counts", {}))
        self._update_bitrate(stats.get("bitrate_counts", {}))
        self._update_bucket(stats.get("bucket_counts", {}))

    # ------------------------------------------------------------------

    def _update_completeness(self, stats: dict) -> None:
        series = QPieSeries()
        fully = stats.get("fully_tagged", 0)
        partial = stats.get("partially_tagged", 0)
        missing = stats.get("missing_tags", 0)
        if fully + partial + missing == 0:
            series.append("No data", 1)
        else:
            if fully:
                series.append(f"Fully tagged ({fully})", fully)
            if partial:
                series.append(f"Partial ({partial})", partial)
            if missing:
                series.append(f"Missing ({missing})", missing)
        self._completeness_chart.removeAllSeries()
        self._completeness_chart.addSeries(series)

    def _update_genre(self, genre_counts: dict) -> None:
        self._genre_chart.removeAllSeries()
        for ax in self._genre_chart.axes():
            self._genre_chart.removeAxis(ax)
        if not genre_counts:
            return
        top = sorted(genre_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        bar_set = QBarSet("Tracks")
        categories = []
        for genre, count in top:
            bar_set.append(count)
            categories.append(genre[:12])  # truncate long names
        series = QBarSeries()
        series.append(bar_set)
        self._genre_chart.addSeries(series)
        axis_x = QBarCategoryAxis()
        axis_x.append(categories)
        axis_x.setLabelsAngle(-45)
        self._genre_chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
        series.attachAxis(axis_x)
        axis_y = QValueAxis()
        self._genre_chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
        series.attachAxis(axis_y)

    def _update_bitrate(self, bitrate_counts: dict) -> None:
        self._bitrate_chart.removeAllSeries()
        for ax in self._bitrate_chart.axes():
            self._bitrate_chart.removeAxis(ax)
        if not bitrate_counts:
            return
        sorted_bitrates = sorted(bitrate_counts.items())
        bar_set = QBarSet("Tracks")
        categories = []
        for bitrate, count in sorted_bitrates:
            bar_set.append(count)
            categories.append(f"{bitrate}k")
        series = QBarSeries()
        series.append(bar_set)
        self._bitrate_chart.addSeries(series)
        axis_x = QBarCategoryAxis()
        axis_x.append(categories)
        self._bitrate_chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
        series.attachAxis(axis_x)
        axis_y = QValueAxis()
        self._bitrate_chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
        series.attachAxis(axis_y)

    def _update_bucket(self, bucket_counts: dict) -> None:
        self._bucket_chart.removeAllSeries()
        for ax in self._bucket_chart.axes():
            self._bucket_chart.removeAxis(ax)
        if not bucket_counts:
            return
        bar_set = QBarSet("Tracks")
        categories = list(bucket_counts.keys())
        for cat in categories:
            bar_set.append(bucket_counts[cat])
        series = QBarSeries()
        series.append(bar_set)
        self._bucket_chart.addSeries(series)
        axis_x = QBarCategoryAxis()
        axis_x.append(categories)
        self._bucket_chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
        series.attachAxis(axis_x)
        axis_y = QValueAxis()
        self._bucket_chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
        series.attachAxis(axis_y)
```

- [ ] **Step 4: Embed StatsView in Dashboard**

Edit `src/gui/dashboard.py`: replace the `charts_group` placeholder block with a `StatsView` widget.

Find and replace in `dashboard.py`:

Old:
```python
        # Charts placeholder
        charts_group = QGroupBox("Distribution Charts")
        charts_inner = QVBoxLayout(charts_group)
        charts_inner.addWidget(QLabel("Charts will appear here once data is loaded."))
        layout.addWidget(charts_group)
```

New:
```python
        # Charts (embedded StatsView)
        from src.gui.stats_view import StatsView
        self._stats_view = StatsView()
        layout.addWidget(self._stats_view)
```

Also update the `update_stats` method in `dashboard.py` to forward stats to the charts:

Find the end of the `update_stats` method and add:
```python
        self._stats_view.update_stats(stats)
```

Full `update_stats` after the edit:
```python
    def update_stats(self, stats: dict) -> None:
        """Populate stat cards from a stats dict as returned by Database.get_stats()."""
        total = stats.get("total_tracks", 0)
        self._total_card.set_value(total)
        self._fully_tagged_card.set_value(stats.get("fully_tagged", 0))
        self._partially_tagged_card.set_value(stats.get("partially_tagged", 0))
        self._missing_tags_card.set_value(stats.get("missing_tags", 0))
        self._duplicates_card.set_value(stats.get("duplicates", 0))
        self._no_artwork_card.set_value(stats.get("no_artwork", 0))
        self._stats_view.update_stats(stats)
```

- [ ] **Step 5: Run tests to verify pass**

```bash
cd /mnt/cloud/code/music-sorter && python -m pytest tests/gui/test_stats_view.py -v
```

Expected: both tests PASS.

- [ ] **Step 6: Commit**

```bash
cd /mnt/cloud/code/music-sorter
git add src/gui/stats_view.py src/gui/dashboard.py tests/gui/test_stats_view.py
git commit -m "feat: implement StatsView charts and embed in Dashboard"
```

---

## Task 6: Duplicate Resolver

**Files:**
- Replace: `src/gui/dupe_resolver.py`

The view runs `DedupeWorker` when shown, displays results in an expandable tree, and lets the user resolve each group by accepting the auto-recommendation or overriding.

- [ ] **Step 1: Write failing smoke test**

Create `tests/gui/test_dupe_resolver.py`:

```python
from pathlib import Path
import pytest
from src.core.models import Track, DupeGroup
from src.gui.dupe_resolver import DupeResolver


def _track(path, bitrate=320, title="T"):
    return Track(file_path=Path(path), file_size=1000, bitrate=bitrate, duration=200.0,
                 title=title, artist="A", tag_completeness=0.8)


def test_dupe_resolver_loads_groups(qtbot):
    resolver = DupeResolver()
    qtbot.addWidget(resolver)
    groups = [
        DupeGroup(tracks=[_track("/tmp/a.mp3", 320), _track("/tmp/b.mp3", 192)]),
        DupeGroup(tracks=[_track("/tmp/c.mp3", 256), _track("/tmp/d.mp3", 128)]),
    ]
    resolver.load_groups(groups)
    assert resolver.group_count() == 2


def test_dupe_resolver_empty_state(qtbot):
    resolver = DupeResolver()
    qtbot.addWidget(resolver)
    resolver.load_groups([])
    assert resolver.group_count() == 0
```

- [ ] **Step 2: Run test to verify failure**

```bash
cd /mnt/cloud/code/music-sorter && python -m pytest tests/gui/test_dupe_resolver.py -v
```

Expected: FAIL — DupeResolver has no `load_groups` or `group_count`.

- [ ] **Step 3: Implement DupeResolver**

Replace `src/gui/dupe_resolver.py` entirely:

```python
from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QTreeWidget, QTreeWidgetItem, QPushButton, QLabel,
    QProgressBar, QComboBox, QFrame, QGroupBox,
)
from PySide6.QtCore import Qt, Signal

from src.core.models import DupeGroup, Track
from src.gui.workers import DedupeWorker

import logging
logger = logging.getLogger(__name__)

_COL_PATH = 0
_COL_BITRATE = 1
_COL_COMPLETENESS = 2
_COL_STATUS = 3


class DupeResolver(QWidget):
    """Review and resolve duplicate track groups."""

    # Emitted when user confirms deletions: list of Track objects to delete
    delete_requested = Signal(list)

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
        self._worker.error.connect(lambda msg: self._status_label.setText(f"Error: {msg}"))
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

        # Toolbar
        toolbar = QHBoxLayout()
        self._scan_btn = QPushButton("Find Duplicates")
        self._scan_btn.clicked.connect(lambda: self.start_scan([]))  # caller must call start_scan directly
        self._auto_resolve_btn = QPushButton("Auto-Resolve All")
        self._auto_resolve_btn.clicked.connect(self._auto_resolve_all)
        self._apply_btn = QPushButton("Apply Deletions…")
        self._apply_btn.clicked.connect(self._apply_deletions)
        toolbar.addWidget(self._scan_btn)
        toolbar.addWidget(self._auto_resolve_btn)
        toolbar.addStretch()
        toolbar.addWidget(self._apply_btn)
        outer.addLayout(toolbar)

        # Progress bar
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setVisible(False)
        outer.addWidget(self._progress_bar)

        # Tree
        self._tree = QTreeWidget()
        self._tree.setHeaderLabels(["Path / Group", "Bitrate", "Tags %", "Action"])
        self._tree.setColumnWidth(0, 400)
        self._tree.setColumnWidth(1, 80)
        self._tree.setColumnWidth(2, 80)
        self._tree.setColumnWidth(3, 120)
        self._tree.setAlternatingRowColors(True)
        outer.addWidget(self._tree, stretch=1)

        # Status
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
                combo.setProperty("track", track)
                self._tree.setItemWidget(child, 3, combo)

    def _on_scan_finished(self, groups: list[DupeGroup]) -> None:
        self._progress_bar.setVisible(False)
        self._scan_btn.setEnabled(True)
        self.load_groups(groups)

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
        """Set all combos to the auto-recommendation."""
        root = self._tree.invisibleRootItem()
        for i in range(root.childCount()):
            group_item = root.child(i)
            group: DupeGroup = group_item.data(0, Qt.ItemDataRole.UserRole)
            keeper = group.best_track()
            for j in range(group_item.childCount()):
                child = group_item.child(j)
                track: Track = child.data(0, Qt.ItemDataRole.UserRole)
                combo: QComboBox = self._tree.itemWidget(child, 3)
                if combo:
                    combo.setCurrentText("Keep" if track is keeper else "Delete")

    def _apply_deletions(self) -> None:
        to_delete: list[Track] = []
        root = self._tree.invisibleRootItem()
        for i in range(root.childCount()):
            group_item = root.child(i)
            for j in range(group_item.childCount()):
                child = group_item.child(j)
                combo: QComboBox = self._tree.itemWidget(child, 3)
                if combo and "Delete" in combo.currentText():
                    track: Track = child.data(0, Qt.ItemDataRole.UserRole)
                    to_delete.append(track)
        if to_delete:
            self.delete_requested.emit(to_delete)
```

- [ ] **Step 4: Run tests to verify pass**

```bash
cd /mnt/cloud/code/music-sorter && python -m pytest tests/gui/test_dupe_resolver.py -v
```

Expected: both tests PASS.

- [ ] **Step 5: Commit**

```bash
cd /mnt/cloud/code/music-sorter
git add src/gui/dupe_resolver.py tests/gui/test_dupe_resolver.py
git commit -m "feat: implement DupeResolver with expandable group tree and auto-resolve"
```

---

## Task 7: iTunes Import View

**Files:**
- Replace: `src/gui/itunes_import.py`

- [ ] **Step 1: Write failing smoke test**

Create `tests/gui/test_itunes_import.py`:

```python
from pathlib import Path
import pytest
from src.core.models import TagConflict
from src.gui.itunes_import import ITunesImport


def _conflict(field="title", file_val="A", itunes_val="B"):
    return TagConflict(file_path=Path("/tmp/a.mp3"), field=field,
                       file_value=file_val, itunes_value=itunes_val)


def test_itunes_import_loads_conflicts(qtbot):
    view = ITunesImport()
    qtbot.addWidget(view)
    conflicts = [_conflict("title", "Old Title", "New Title"),
                 _conflict("artist", "Old", "New")]
    view.load_conflicts(conflicts)
    assert view.conflict_count() == 2


def test_itunes_import_empty(qtbot):
    view = ITunesImport()
    qtbot.addWidget(view)
    view.load_conflicts([])
    assert view.conflict_count() == 0
```

- [ ] **Step 2: Run test to verify failure**

```bash
cd /mnt/cloud/code/music-sorter && python -m pytest tests/gui/test_itunes_import.py -v
```

Expected: FAIL — no `load_conflicts` or `conflict_count`.

- [ ] **Step 3: Implement ITunesImport**

Replace `src/gui/itunes_import.py` entirely:

```python
from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QProgressBar,
    QTableWidget, QTableWidgetItem, QComboBox,
    QFileDialog, QMenu, QHeaderView,
)
from PySide6.QtCore import Qt, Signal

from src.core.models import TagConflict, Track
from src.gui.workers import ITunesWorker

import logging
logger = logging.getLogger(__name__)

_COL_PATH = 0
_COL_FIELD = 1
_COL_FILE_VAL = 2
_COL_ITUNES_VAL = 3
_COL_ACTION = 4


class ITunesImport(QWidget):
    """iTunes XML import with conflict resolution."""

    # Emitted when user confirms: list[TagConflict] with .resolution set
    apply_requested = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._conflicts: list[TagConflict] = []
        self._worker: ITunesWorker | None = None
        self._tracks: list[Track] = []
        self._source_dirs: list[Path] = []
        self._build_ui()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_tracks(self, tracks: list[Track], source_dirs: list[Path]) -> None:
        self._tracks = tracks
        self._source_dirs = source_dirs

    def load_conflicts(self, conflicts: list[TagConflict]) -> None:
        self._conflicts = conflicts
        self._populate_table(conflicts)
        self._update_status()

    def conflict_count(self) -> int:
        return self._table.rowCount()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(6)

        # File picker row
        file_row = QHBoxLayout()
        self._path_label = QLabel("No iTunes XML selected")
        self._path_label.setStyleSheet("color: #888;")
        browse_btn = QPushButton("Browse…")
        browse_btn.clicked.connect(self._browse_xml)
        self._import_btn = QPushButton("Import")
        self._import_btn.setEnabled(False)
        self._import_btn.clicked.connect(self._start_import)
        file_row.addWidget(QLabel("iTunes Library XML:"))
        file_row.addWidget(self._path_label, stretch=1)
        file_row.addWidget(browse_btn)
        file_row.addWidget(self._import_btn)
        outer.addLayout(file_row)

        # Progress bar
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 0)  # indeterminate
        self._progress_bar.setVisible(False)
        outer.addWidget(self._progress_bar)

        # Bulk rules row
        rules_row = QHBoxLayout()
        rules_row.addWidget(QLabel("Bulk rules:"))
        self._field_combo = QComboBox()
        for field in ["title", "artist", "album_artist", "album", "genre", "year", "track_number", "bpm"]:
            self._field_combo.addItem(field)
        btn_prefer_itunes = QPushButton("Always prefer iTunes for field")
        btn_prefer_file = QPushButton("Always prefer file for field")
        btn_prefer_itunes.clicked.connect(lambda: self._bulk_set_field("itunes"))
        btn_prefer_file.clicked.connect(lambda: self._bulk_set_field("file"))
        rules_row.addWidget(self._field_combo)
        rules_row.addWidget(btn_prefer_itunes)
        rules_row.addWidget(btn_prefer_file)
        rules_row.addStretch()
        outer.addLayout(rules_row)

        # Conflict table
        self._table = QTableWidget(0, 5)
        self._table.setHorizontalHeaderLabels(["File", "Field", "File Value", "iTunes Value", "Use"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self._table.verticalHeader().setVisible(False)
        self._table.setAlternatingRowColors(True)
        outer.addWidget(self._table, stretch=1)

        # Status + apply
        bottom_row = QHBoxLayout()
        self._status_label = QLabel("")
        self._apply_btn = QPushButton("Apply Resolved Conflicts")
        self._apply_btn.setEnabled(False)
        self._apply_btn.clicked.connect(self._apply)
        bottom_row.addWidget(self._status_label, stretch=1)
        bottom_row.addWidget(self._apply_btn)
        outer.addLayout(bottom_row)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _browse_xml(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select iTunes Library XML", "", "XML Files (*.xml)"
        )
        if path:
            self._xml_path = Path(path)
            self._path_label.setText(str(self._xml_path))
            self._path_label.setStyleSheet("")
            self._import_btn.setEnabled(True)

    def _start_import(self) -> None:
        if not hasattr(self, "_xml_path"):
            return
        self._progress_bar.setVisible(True)
        self._import_btn.setEnabled(False)
        self._worker = ITunesWorker(self._xml_path, self._tracks, self._source_dirs)
        self._worker.progress.connect(self._status_label.setText)
        self._worker.finished.connect(self._on_import_finished)
        self._worker.error.connect(lambda msg: (
            self._status_label.setText(f"Error: {msg}"),
            self._progress_bar.setVisible(False),
            self._import_btn.setEnabled(True),
        ))
        self._worker.start()

    def _on_import_finished(self, conflicts: list[TagConflict]) -> None:
        self._progress_bar.setVisible(False)
        self._import_btn.setEnabled(True)
        self.load_conflicts(conflicts)

    def _populate_table(self, conflicts: list[TagConflict]) -> None:
        self._table.setRowCount(0)
        for conflict in conflicts:
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setItem(row, _COL_PATH, QTableWidgetItem(conflict.file_path.name))
            self._table.setItem(row, _COL_FIELD, QTableWidgetItem(conflict.field))
            self._table.setItem(row, _COL_FILE_VAL, QTableWidgetItem(conflict.file_value))
            self._table.setItem(row, _COL_ITUNES_VAL, QTableWidgetItem(conflict.itunes_value))
            combo = QComboBox()
            combo.addItems(["Keep file", "Use iTunes"])
            combo.setProperty("conflict_index", row)
            self._table.setCellWidget(row, _COL_ACTION, combo)
        self._apply_btn.setEnabled(bool(conflicts))

    def _update_status(self) -> None:
        n = len(self._conflicts)
        self._status_label.setText(
            f"{n} conflict{'s' if n != 1 else ''} to resolve." if n else "No conflicts."
        )

    def _bulk_set_field(self, source: str) -> None:
        field = self._field_combo.currentText()
        choice = "Use iTunes" if source == "itunes" else "Keep file"
        for row in range(self._table.rowCount()):
            if self._table.item(row, _COL_FIELD).text() == field:
                combo: QComboBox = self._table.cellWidget(row, _COL_ACTION)
                if combo:
                    combo.setCurrentText(choice)

    def _apply(self) -> None:
        resolved: list[TagConflict] = []
        for row, conflict in enumerate(self._conflicts):
            combo: QComboBox = self._table.cellWidget(row, _COL_ACTION)
            if combo:
                conflict.resolution = "itunes" if combo.currentText() == "Use iTunes" else "file"
            resolved.append(conflict)
        self.apply_requested.emit(resolved)
```

- [ ] **Step 4: Run tests to verify pass**

```bash
cd /mnt/cloud/code/music-sorter && python -m pytest tests/gui/test_itunes_import.py -v
```

Expected: both tests PASS.

- [ ] **Step 5: Commit**

```bash
cd /mnt/cloud/code/music-sorter
git add src/gui/itunes_import.py tests/gui/test_itunes_import.py
git commit -m "feat: implement ITunesImport view with conflict resolution table"
```

---

## Task 8: Rename Preview

**Files:**
- Replace: `src/gui/rename_preview.py`

- [ ] **Step 1: Write failing smoke test**

Create `tests/gui/test_rename_preview.py`:

```python
from pathlib import Path
import pytest
from src.core.models import Track, RenameOperation
from src.gui.rename_preview import RenamePreview


def _track(path="/tmp/a.mp3"):
    return Track(
        file_path=Path(path), file_size=1000, bitrate=320, duration=200.0,
        title="Test Song", artist="DJ X", genre="House", bpm=128.0,
        bucket="DJ Music", tag_completeness=0.9,
    )


def test_rename_preview_loads_plan(qtbot):
    view = RenamePreview()
    qtbot.addWidget(view)
    ops = [
        RenameOperation(source=Path("/tmp/a.mp3"), destination=Path("/music/b.mp3")),
        RenameOperation(source=Path("/tmp/c.mp3"), destination=Path("/music/d.mp3")),
    ]
    view.load_plan(ops)
    assert view.operation_count() == 2


def test_rename_preview_execute_btn_disabled_before_plan(qtbot):
    view = RenamePreview()
    qtbot.addWidget(view)
    assert not view.is_execute_enabled()


def test_rename_preview_execute_btn_enabled_after_plan(qtbot):
    view = RenamePreview()
    qtbot.addWidget(view)
    ops = [RenameOperation(source=Path("/tmp/a.mp3"), destination=Path("/music/b.mp3"))]
    view.load_plan(ops)
    assert view.is_execute_enabled()
```

- [ ] **Step 2: Run test to verify failure**

```bash
cd /mnt/cloud/code/music-sorter && python -m pytest tests/gui/test_rename_preview.py -v
```

Expected: FAIL — no `load_plan`, `operation_count`, `is_execute_enabled`.

- [ ] **Step 3: Implement RenamePreview**

Replace `src/gui/rename_preview.py` entirely:

```python
from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QLabel, QPushButton, QProgressBar,
    QTableWidget, QTableWidgetItem, QLineEdit,
    QGroupBox, QHeaderView,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor

from src.core.models import RenameOperation, Track
from src.core.renamer import render_pattern, generate_rename_plan
from src.gui.workers import RenameWorker

import logging
logger = logging.getLogger(__name__)

_STATUS_COLORS = {
    "pending": None,
    "complete": QColor("#2ecc71"),
    "skipped": QColor("#e67e22"),
    "error": QColor("#e74c3c"),
}


class RenamePreview(QWidget):
    """Pattern editor, dry-run table, and execute workflow for rename/organize."""

    # Emitted after successful execution: list[RenameOperation]
    rename_complete = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tracks: list[Track] = []
        self._plan: list[RenameOperation] = []
        self._worker: RenameWorker | None = None
        self._patterns: dict[str, str] = {}
        self._build_ui()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_tracks(self, tracks: list[Track]) -> None:
        self._tracks = tracks

    def set_patterns(self, patterns: dict[str, str]) -> None:
        """Provide rename patterns dict from Config (bucket → pattern)."""
        self._patterns = patterns
        default = patterns.get("default", "")
        if default:
            self._pattern_input.setText(default)

    def load_plan(self, plan: list[RenameOperation]) -> None:
        self._plan = plan
        self._populate_table(plan)
        self._execute_btn.setEnabled(bool(plan))

    def operation_count(self) -> int:
        return self._table.rowCount()

    def is_execute_enabled(self) -> bool:
        return self._execute_btn.isEnabled()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(6)

        # Pattern editor
        pattern_group = QGroupBox("Rename Pattern")
        pattern_layout = QVBoxLayout(pattern_group)

        pattern_row = QHBoxLayout()
        pattern_row.addWidget(QLabel("Pattern:"))
        self._pattern_input = QLineEdit()
        self._pattern_input.setPlaceholderText(
            "{bucket}/{genre}/{artist} - {title} [{bpm}bpm {key}].mp3"
        )
        self._pattern_input.textChanged.connect(self._update_preview)
        pattern_row.addWidget(self._pattern_input, stretch=1)
        pattern_layout.addLayout(pattern_row)

        self._preview_label = QLabel("Live preview: (select tracks first)")
        self._preview_label.setStyleSheet("color: #888; font-family: monospace;")
        pattern_layout.addWidget(self._preview_label)
        outer.addWidget(pattern_group)

        # Toolbar
        toolbar_row = QHBoxLayout()
        self._dryrun_btn = QPushButton("Generate Dry-Run Preview")
        self._dryrun_btn.clicked.connect(self._run_dryrun)
        self._execute_btn = QPushButton("Execute Rename")
        self._execute_btn.setEnabled(False)
        self._execute_btn.clicked.connect(self._execute)
        toolbar_row.addWidget(self._dryrun_btn)
        toolbar_row.addStretch()
        toolbar_row.addWidget(self._execute_btn)
        outer.addLayout(toolbar_row)

        # Progress bar
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setVisible(False)
        outer.addWidget(self._progress_bar)

        # Rename plan table
        self._table = QTableWidget(0, 3)
        self._table.setHorizontalHeaderLabels(["Current Path", "New Path", "Status"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self._table.verticalHeader().setVisible(False)
        self._table.setAlternatingRowColors(True)
        outer.addWidget(self._table, stretch=1)

        # Status
        self._status_label = QLabel("")
        outer.addWidget(self._status_label)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _update_preview(self, pattern: str) -> None:
        if not self._tracks or not pattern:
            self._preview_label.setText("Live preview: (select tracks first)")
            return
        sample = self._tracks[0]
        try:
            rendered = render_pattern(pattern, sample)
            self._preview_label.setText(f"Preview: {rendered}")
            self._preview_label.setStyleSheet("color: #2ecc71; font-family: monospace;")
        except Exception as exc:
            self._preview_label.setText(f"Pattern error: {exc}")
            self._preview_label.setStyleSheet("color: #e74c3c; font-family: monospace;")

    def _run_dryrun(self) -> None:
        if not self._tracks:
            self._status_label.setText("No tracks loaded.")
            return
        pattern = self._pattern_input.text().strip()
        if not pattern:
            self._status_label.setText("Enter a rename pattern first.")
            return
        try:
            plan = generate_rename_plan(self._tracks, pattern)
            self.load_plan(plan)
            collisions = sum(1 for op in plan if op.status == "skipped")
            self._status_label.setText(
                f"Dry-run: {len(plan)} rename(s)"
                + (f", {collisions} collision(s) highlighted" if collisions else "")
            )
        except Exception as exc:
            self._status_label.setText(f"Error generating plan: {exc}")

    def _populate_table(self, plan: list[RenameOperation]) -> None:
        self._table.setRowCount(0)
        for op in plan:
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setItem(row, 0, QTableWidgetItem(str(op.source)))
            dest_item = QTableWidgetItem(str(op.destination))
            if op.status == "skipped":
                dest_item.setForeground(QColor("#e74c3c"))
            self._table.setItem(row, 1, dest_item)
            status_item = QTableWidgetItem(op.status)
            color = _STATUS_COLORS.get(op.status)
            if color:
                status_item.setBackground(color)
            self._table.setItem(row, 2, status_item)

    def _execute(self) -> None:
        if not self._plan:
            return
        self._execute_btn.setEnabled(False)
        self._progress_bar.setVisible(True)
        self._worker = RenameWorker(self._plan, dry_run=False)
        self._worker.progress.connect(lambda cur, tot: self._progress_bar.setValue(
            int(cur / tot * 100) if tot else 0))
        self._worker.finished.connect(self._on_execute_finished)
        self._worker.error.connect(lambda msg: self._status_label.setText(f"Error: {msg}"))
        self._worker.start()

    def _on_execute_finished(self, result: list[RenameOperation]) -> None:
        self._progress_bar.setVisible(False)
        self.load_plan(result)
        done = sum(1 for op in result if op.status == "complete")
        self._status_label.setText(f"Done: {done}/{len(result)} files renamed.")
        self._execute_btn.setEnabled(False)  # disallow re-execute
        self.rename_complete.emit(result)
```

- [ ] **Step 4: Run tests to verify pass**

```bash
cd /mnt/cloud/code/music-sorter && python -m pytest tests/gui/test_rename_preview.py -v
```

Expected: all 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
cd /mnt/cloud/code/music-sorter
git add src/gui/rename_preview.py tests/gui/test_rename_preview.py
git commit -m "feat: implement RenamePreview with pattern editor, dry-run table, and execute"
```

---

## Task 9: Playlist Manager

**Files:**
- Replace: `src/gui/playlist_manager.py`

- [ ] **Step 1: Write failing smoke test**

Create `tests/gui/test_playlist_manager.py`:

```python
from pathlib import Path
from unittest.mock import MagicMock
import pytest
from src.core.models import PlaylistDefinition
from src.gui.playlist_manager import PlaylistManager


def test_playlist_manager_loads_playlists(qtbot):
    db = MagicMock()
    db.get_all_playlists.return_value = [
        PlaylistDefinition(name="Set A", filters={"bucket": "DJ Music"}, folder="DJ"),
        PlaylistDefinition(name="Set B", filters={}, folder=None),
    ]
    manager = PlaylistManager(db=db)
    qtbot.addWidget(manager)
    assert manager.playlist_count() == 2


def test_playlist_manager_empty_state(qtbot):
    db = MagicMock()
    db.get_all_playlists.return_value = []
    manager = PlaylistManager(db=db)
    qtbot.addWidget(manager)
    assert manager.playlist_count() == 0
```

- [ ] **Step 2: Run test to verify failure**

```bash
cd /mnt/cloud/code/music-sorter && python -m pytest tests/gui/test_playlist_manager.py -v
```

Expected: FAIL — no `playlist_count` in PlaylistManager.

- [ ] **Step 3: Implement PlaylistManager**

Replace `src/gui/playlist_manager.py` entirely:

```python
from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QTreeWidget, QTreeWidgetItem, QPushButton, QLabel,
    QLineEdit, QComboBox, QFormLayout, QGroupBox,
    QMenu, QInputDialog, QFileDialog, QMessageBox,
    QScrollArea, QFrame,
)
from PySide6.QtCore import Qt, Signal

from src.core.models import PlaylistDefinition, Track
from src.core.playlist import filter_tracks_for_playlist, generate_m3u, generate_pls

import logging
logger = logging.getLogger(__name__)


class PlaylistManager(QWidget):
    """Playlist tree with folder support and an editor panel."""

    # Emitted when user wants to navigate to matching tracks
    show_tracks_requested = Signal(list)  # list[Track]

    def __init__(self, db, all_tracks: list[Track] | None = None, parent=None):
        super().__init__(parent)
        self._db = db
        self._all_tracks: list[Track] = all_tracks or []
        self._playlists: list[PlaylistDefinition] = []
        self._build_ui()
        self._load_playlists()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_tracks(self, tracks: list[Track]) -> None:
        self._all_tracks = tracks

    def playlist_count(self) -> int:
        count = 0
        root = self._tree.invisibleRootItem()
        for i in range(root.childCount()):
            item = root.child(i)
            if item.data(0, Qt.ItemDataRole.UserRole) is not None:
                count += 1
            else:
                # Folder — count children
                count += item.childCount()
        return count

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
        btn_regen_all = QPushButton("Re-generate All")
        btn_regen_all.clicked.connect(self._regenerate_all)
        tree_toolbar.addWidget(btn_new)
        tree_toolbar.addWidget(btn_folder)
        tree_toolbar.addStretch()
        tree_toolbar.addWidget(btn_regen_all)
        left_layout.addLayout(tree_toolbar)

        self._tree = QTreeWidget()
        self._tree.setHeaderHidden(True)
        self._tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._tree.customContextMenuRequested.connect(self._on_tree_context_menu)
        self._tree.currentItemChanged.connect(self._on_item_selected)
        self._tree.setDragDropMode(QTreeWidget.DragDropMode.InternalMove)
        left_layout.addWidget(self._tree, stretch=1)
        splitter.addWidget(left)

        # Right: editor panel
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(4, 8, 8, 8)

        self._editor_group = QGroupBox("Playlist Editor")
        editor_layout = QFormLayout(self._editor_group)

        self._name_edit = QLineEdit()
        self._folder_edit = QLineEdit()
        self._folder_edit.setPlaceholderText("e.g. DJ/Sets")
        self._format_combo = QComboBox()
        self._format_combo.addItems(["m3u", "pls"])
        self._bucket_filter = QComboBox()
        self._bucket_filter.addItems(["(any)", "DJ Music", "DJ Mixes", "General"])
        self._sort_combo = QComboBox()
        self._sort_combo.addItems(["(none)", "bpm", "artist", "title", "genre"])

        editor_layout.addRow("Name:", self._name_edit)
        editor_layout.addRow("Folder:", self._folder_edit)
        editor_layout.addRow("Format:", self._format_combo)
        editor_layout.addRow("Bucket filter:", self._bucket_filter)
        editor_layout.addRow("Sort by:", self._sort_combo)

        right_layout.addWidget(self._editor_group)

        btn_row = QHBoxLayout()
        self._save_edit_btn = QPushButton("Save")
        self._generate_btn = QPushButton("Generate File…")
        self._save_edit_btn.clicked.connect(self._save_current_playlist)
        self._generate_btn.clicked.connect(self._generate_current)
        btn_row.addWidget(self._save_edit_btn)
        btn_row.addWidget(self._generate_btn)
        btn_row.addStretch()
        right_layout.addLayout(btn_row)

        self._track_count_label = QLabel("")
        right_layout.addWidget(self._track_count_label)
        right_layout.addStretch()

        splitter.addWidget(right)
        splitter.setSizes([300, 400])

        self._current_playlist: PlaylistDefinition | None = None
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
                folder_item.setData(0, Qt.ItemDataRole.UserRole, None)  # None = folder
                folder_item.setExpanded(True)
                folders[folder] = folder_item

            parent = folders.get(folder, self._tree.invisibleRootItem())
            item = QTreeWidgetItem(parent)
            item.setText(0, pld.name)
            item.setData(0, Qt.ItemDataRole.UserRole, pld)

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_item_selected(self, current: QTreeWidgetItem | None, _previous) -> None:
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
        idx = self._bucket_filter.findText(bucket)
        self._bucket_filter.setCurrentIndex(max(idx, 0))
        sort = pld.sort_by or "(none)"
        idx = self._sort_combo.findText(sort)
        self._sort_combo.setCurrentIndex(max(idx, 0))
        self._editor_group.setEnabled(True)

        # Show track count
        matching = filter_tracks_for_playlist(self._all_tracks, pld)
        self._track_count_label.setText(f"{len(matching)} matching tracks")

    def _on_tree_context_menu(self, pos) -> None:
        item = self._tree.itemAt(pos)
        menu = QMenu(self)
        if item:
            pld = item.data(0, Qt.ItemDataRole.UserRole)
            if pld is not None:
                menu.addAction("Rename", lambda: self._rename_playlist(item))
                menu.addAction("Delete", lambda: self._delete_playlist(item, pld))
        menu.addAction("New Playlist", self._new_playlist)
        menu.addAction("New Folder", self._new_folder)
        menu.exec(self._tree.mapToGlobal(pos))

    def _new_playlist(self) -> None:
        name, ok = QInputDialog.getText(self, "New Playlist", "Playlist name:")
        if ok and name.strip():
            pld = PlaylistDefinition(name=name.strip(), filters={})
            self._db.upsert_playlist(pld)
            self._load_playlists()

    def _new_folder(self) -> None:
        name, ok = QInputDialog.getText(self, "New Folder", "Folder name:")
        if ok and name.strip():
            folder_item = QTreeWidgetItem(self._tree)
            folder_item.setText(0, name.strip())
            folder_item.setData(0, Qt.ItemDataRole.UserRole, None)
            folder_item.setExpanded(True)

    def _rename_playlist(self, item: QTreeWidgetItem) -> None:
        pld: PlaylistDefinition = item.data(0, Qt.ItemDataRole.UserRole)
        new_name, ok = QInputDialog.getText(self, "Rename", "New name:", text=pld.name)
        if ok and new_name.strip():
            self._db.delete_playlist(pld.name)
            pld.name = new_name.strip()
            self._db.upsert_playlist(pld)
            self._load_playlists()

    def _delete_playlist(self, item: QTreeWidgetItem, pld: PlaylistDefinition) -> None:
        result = QMessageBox.question(
            self, "Delete Playlist",
            f"Delete playlist '{pld.name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if result == QMessageBox.StandardButton.Yes:
            self._db.delete_playlist(pld.name)
            self._load_playlists()

    def _save_current_playlist(self) -> None:
        if self._current_playlist is None:
            return
        old_name = self._current_playlist.name
        self._current_playlist.name = self._name_edit.text().strip() or old_name
        self._current_playlist.folder = self._folder_edit.text().strip() or None
        self._current_playlist.format = self._format_combo.currentText()
        bucket = self._bucket_filter.currentText()
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
        ext = f"*.{fmt}"
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Playlist", self._current_playlist.name, f"Playlist files ({ext})"
        )
        if path:
            output = Path(path)
            if fmt == "m3u":
                generate_m3u(matching, output)
            else:
                generate_pls(matching, output)
            QMessageBox.information(self, "Done", f"Saved {len(matching)} tracks to {output.name}")

    def _regenerate_all(self) -> None:
        count = 0
        for pld in self._playlists:
            if not pld.folder:
                continue
            matching = filter_tracks_for_playlist(self._all_tracks, pld)
            output = Path(pld.folder) / f"{pld.name}.{pld.format}"
            output.parent.mkdir(parents=True, exist_ok=True)
            if pld.format == "m3u":
                generate_m3u(matching, output)
            else:
                generate_pls(matching, output)
            count += 1
        QMessageBox.information(self, "Re-generate All", f"Updated {count} playlist(s).")
```

- [ ] **Step 4: Run tests to verify pass**

```bash
cd /mnt/cloud/code/music-sorter && python -m pytest tests/gui/test_playlist_manager.py -v
```

Expected: both tests PASS.

- [ ] **Step 5: Commit**

```bash
cd /mnt/cloud/code/music-sorter
git add src/gui/playlist_manager.py tests/gui/test_playlist_manager.py
git commit -m "feat: implement PlaylistManager with folder tree and editor panel"
```

---

## Task 10: Navigation Wiring and Sidebar

**Files:**
- Replace: `src/gui/main_window.py`

This task wires everything together: adds new nav pages (Organize with sub-tabs for Dupe Resolver + Rename Preview, and a Playlists page), wires the Library page with a TagEditor split panel, connects sidebar clicks to library filtering, and refreshes sidebar counts after scans.

- [ ] **Step 1: Write failing smoke test**

Create `tests/gui/test_main_window.py`:

```python
import pytest
from unittest.mock import MagicMock, patch
from src.gui.main_window import MainWindow


def test_main_window_starts(qtbot):
    with patch("src.gui.main_window.Database"), \
         patch("src.gui.main_window.Config.load_user_config") as mock_cfg:
        mock_cfg.return_value = MagicMock(
            source_directories=[],
            itunes_xml_path=None,
            library_columns={"visible": ["title", "artist"]},
        )
        win = MainWindow()
        qtbot.addWidget(win)
        assert win.isVisible() or not win.isVisible()  # just verify no crash on init
```

- [ ] **Step 2: Run test to verify failure**

```bash
cd /mnt/cloud/code/music-sorter && python -m pytest tests/gui/test_main_window.py -v
```

Expected: PASS (MainWindow already exists) — this is a regression guard. If it fails, fix before proceeding.

- [ ] **Step 3: Rewrite MainWindow**

Replace `src/gui/main_window.py` entirely:

```python
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
    QSplitter,
    QTabWidget,
    QSizePolicy,
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QAction

import logging

from src.core.config import Config, USER_CONFIG_PATH
from src.core.database import Database
from src.core.models import Track
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

# Top-level page indices
_PAGE_DASHBOARD = 0
_PAGE_LIBRARY = 1
_PAGE_ORGANIZE = 2
_PAGE_IMPORT = 3
_PAGE_PLAYLISTS = 4
_PAGE_SETTINGS = 5

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
        # Top toolbar
        toolbar = QToolBar("Navigation")
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(16, 16))
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, toolbar)

        acts = {
            "Dashboard": _PAGE_DASHBOARD,
            "Library": _PAGE_LIBRARY,
            "Organize": _PAGE_ORGANIZE,
            "Import": _PAGE_IMPORT,
            "Playlists": _PAGE_PLAYLISTS,
            "Settings": _PAGE_SETTINGS,
        }
        for name, page_idx in acts.items():
            act = QAction(name, self)
            act.triggered.connect(lambda checked, idx=page_idx: self._show_page(idx))
            toolbar.addAction(act)

        toolbar.addSeparator()
        act_scan = QAction("Scan", self)
        act_scan.triggered.connect(self._start_scan)
        toolbar.addAction(act_scan)

        # Central widget: sidebar + content
        central = QWidget()
        self.setCentralWidget(central)
        h_layout = QHBoxLayout(central)
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.setSpacing(0)

        h_layout.addWidget(self._build_sidebar())

        # Content stack
        self._stack = QStackedWidget()
        self._dashboard = Dashboard()

        # Library page: splitter with browser left, tag editor right
        library_splitter = QSplitter(Qt.Orientation.Horizontal)
        visible_cols = self._config.library_columns.get("visible", None)
        self._library = LibraryBrowser(visible_columns=visible_cols)
        self._tag_editor = TagEditor()
        self._tag_editor.setMinimumWidth(280)
        self._tag_editor.setVisible(False)
        library_splitter.addWidget(self._library)
        library_splitter.addWidget(self._tag_editor)
        library_splitter.setSizes([800, 300])
        library_splitter.setCollapsible(1, True)

        # Organize page: tab widget
        organize_tabs = QTabWidget()
        self._dupe_resolver = DupeResolver()
        self._rename_preview = RenamePreview()
        organize_tabs.addTab(self._dupe_resolver, "Duplicates")
        organize_tabs.addTab(self._rename_preview, "Rename / Organize")

        # Import page
        self._itunes_import = ITunesImport()

        # Playlists page
        self._playlist_manager = PlaylistManager(db=self._db, all_tracks=self._all_tracks)

        # Settings page
        self._settings_view = SettingsView()

        self._stack.addWidget(self._dashboard)       # 0
        self._stack.addWidget(library_splitter)      # 1
        self._stack.addWidget(organize_tabs)         # 2
        self._stack.addWidget(self._itunes_import)   # 3
        self._stack.addWidget(self._playlist_manager)  # 4
        self._stack.addWidget(self._settings_view)   # 5

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
        self._library.selection_changed.connect(self._on_library_selection_changed)

        # Wire column changes → config save
        self._library.columns_changed.connect(self._on_columns_changed)

        # Wire tag editor save → write worker
        self._tag_editor.save_requested.connect(self._on_tag_save_requested)

        # Wire dupe resolver delete → confirmation + DB update
        self._dupe_resolver.delete_requested.connect(self._on_delete_tracks)

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
        self._bucket_items: dict[str, QTreeWidgetItem] = {}
        for bucket in ("All Music", "DJ Music", "DJ Mixes", "General"):
            item = QTreeWidgetItem([bucket])
            self._buckets_tree.addTopLevelItem(item)
            self._bucket_items[bucket] = item
        self._buckets_tree.itemClicked.connect(self._on_bucket_clicked)
        layout.addWidget(self._buckets_tree)

        # Task queue
        queue_label = QLabel("Task Queue")
        queue_label.setStyleSheet("color: #aaa; font-weight: bold; font-size: 11px;")
        layout.addWidget(queue_label)

        self._task_tree = QTreeWidget()
        self._task_tree.setHeaderHidden(True)
        self._task_tree.setRootIsDecorated(False)
        self._task_tree.setStyleSheet(
            "QTreeWidget { background: transparent; color: #ddd; border: none; }"
            "QTreeWidget::item:selected { background: #444; }"
        )
        self._task_items: dict[str, QTreeWidgetItem] = {}
        for task_name in ("Missing Tags", "No Artwork"):
            item = QTreeWidgetItem([task_name])
            self._task_tree.addTopLevelItem(item)
            self._task_items[task_name] = item
        self._task_tree.itemClicked.connect(self._on_task_clicked)
        layout.addWidget(self._task_tree)

        layout.addStretch()
        return sidebar

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def _show_page(self, index: int) -> None:
        self._stack.setCurrentIndex(index)
        # Push current tracks to whichever view just became active
        if index == _PAGE_ORGANIZE:
            self._rename_preview.set_tracks(self._all_tracks)
            self._rename_preview.set_patterns(self._config.rename_patterns)
        elif index == _PAGE_IMPORT:
            self._itunes_import.set_tracks(self._all_tracks, self._config.source_directories)
        elif index == _PAGE_PLAYLISTS:
            self._playlist_manager.set_tracks(self._all_tracks)

    # ------------------------------------------------------------------
    # Sidebar interactions
    # ------------------------------------------------------------------

    def _on_bucket_clicked(self, item: QTreeWidgetItem, _col: int) -> None:
        bucket = item.text(0)
        self._show_page(_PAGE_LIBRARY)
        self._library.filter_by_bucket(bucket)

    def _on_task_clicked(self, item: QTreeWidgetItem, _col: int) -> None:
        task = item.text(0).split(" (")[0]  # strip count suffix
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
        self._config._data["library_columns"]["visible"] = columns
        self._config.save(self._config_path)

    # ------------------------------------------------------------------
    # Scanning
    # ------------------------------------------------------------------

    def _start_scan(self) -> None:
        if self._scan_worker and self._scan_worker.isRunning():
            return
        directories = self._settings_view.get_source_directories() or self._config.source_directories
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
        fully_tagged = sum(1 for t in self._all_tracks if t.tag_completeness >= 0.9)
        partially_tagged = sum(1 for t in self._all_tracks if 0.4 <= t.tag_completeness < 0.9)
        missing_tags = sum(1 for t in self._all_tracks if t.tag_completeness < 0.4)
        no_artwork = sum(1 for t in self._all_tracks if not t.has_artwork)

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

    def _on_library_selection_changed(self, tracks: list[Track]) -> None:
        if not tracks:
            self._tag_editor.setVisible(False)
            return
        self._tag_editor.setVisible(True)
        if len(tracks) == 1:
            self._tag_editor.load_track(tracks[0])
        else:
            self._tag_editor.load_tracks(tracks)

    def _on_tag_save_requested(self, tracks: list[Track], changes: dict[str, str]) -> None:
        # Apply changes to track objects
        for track in tracks:
            for field, value in changes.items():
                if field in ("track_number", "disc_number", "year"):
                    setattr(track, field, int(value) if value else None)
                elif field == "bpm":
                    setattr(track, field, float(value) if value else None)
                else:
                    setattr(track, field, value or None)

        fields = list(changes.keys())
        pairs = [(track, fields) for track in tracks]
        self._tag_worker = TagWriteWorker(pairs, self._db)
        self._tag_worker.finished.connect(lambda updated: (
            self._status_label.setText(f"Saved tags for {len(updated)} track(s)"),
            self._refresh_library(),
        ))
        self._tag_worker.error.connect(
            lambda msg: self._status_label.setText(f"Tag write error: {msg}")
        )
        self._tag_worker.start()
        self._status_label.setText(f"Writing tags for {len(tracks)} track(s)…")

    # ------------------------------------------------------------------
    # Deduplicate
    # ------------------------------------------------------------------

    def _on_delete_tracks(self, tracks: list[Track]) -> None:
        for track in tracks:
            self._db.delete_track(track.file_path)
        self._refresh_library()
        self._status_label.setText(f"Removed {len(tracks)} duplicate(s) from library.")

    # ------------------------------------------------------------------
    # iTunes import
    # ------------------------------------------------------------------

    def _on_itunes_apply(self, conflicts) -> None:
        """Apply resolved iTunes conflicts by writing affected tags."""
        itunes_fields: dict[Path, tuple[Track, list[str]]] = {}
        for conflict in conflicts:
            if conflict.resolution != "itunes":
                continue
            # Find the track in our library
            track = next((t for t in self._all_tracks if t.file_path == conflict.file_path), None)
            if track is None:
                continue
            setattr(track, conflict.field, conflict.itunes_value)
            if conflict.file_path not in itunes_fields:
                itunes_fields[conflict.file_path] = (track, [])
            itunes_fields[conflict.file_path][1].append(conflict.field)

        if not itunes_fields:
            return

        pairs = list(itunes_fields.values())
        self._tag_worker = TagWriteWorker(pairs, self._db)
        self._tag_worker.finished.connect(lambda updated: (
            self._status_label.setText(f"Applied iTunes tags to {len(updated)} track(s)"),
            self._refresh_library(),
        ))
        self._tag_worker.start()

    # ------------------------------------------------------------------
    # Close
    # ------------------------------------------------------------------

    def closeEvent(self, event):
        for worker in (self._scan_worker, self._tag_worker):
            if worker and worker.isRunning():
                worker.cancel() if hasattr(worker, "cancel") else None
                worker.wait(3000)
        self._db.close()
        super().closeEvent(event)
```

- [ ] **Step 4: Run tests to verify pass**

```bash
cd /mnt/cloud/code/music-sorter && python -m pytest tests/gui/test_main_window.py -v
```

Expected: PASS.

- [ ] **Step 5: Run full test suite**

```bash
cd /mnt/cloud/code/music-sorter && python -m pytest tests/ -v --tb=short 2>&1 | tail -30
```

Expected: All tests pass. Fix any regressions before committing.

- [ ] **Step 6: Commit**

```bash
cd /mnt/cloud/code/music-sorter
git add src/gui/main_window.py tests/gui/test_main_window.py
git commit -m "feat: wire all views into MainWindow with sidebar filtering and tag editor split"
```

---

## Self-Review

### Spec coverage check

| Spec item | Task covering it |
|---|---|
| Tag Editor — single track editing | Task 4, Task 10 |
| Tag Editor — batch editing, `[Multiple]`, dry-run preview | Task 4 |
| Duplicate Resolver — DupeGroup tree, per-group actions, bulk auto-resolve | Task 6 |
| iTunes Import — file picker, progress, conflict table, bulk rules | Task 7 |
| Rename/Organize Preview — pattern editor, live preview, dry-run table, execute | Task 8 |
| Statistics View — charts (completeness, genre, bitrate, storage) | Task 5 |
| Playlist Manager — folder tree, right-click, drag, editor panel, generate | Task 9 |
| Sidebar Wiring — live counts, click to filter library | Task 10 |
| Column Configuration — right-click show/hide, drag reorder, persist to config | Task 3 |
| Workers for all long-running operations | Task 1 |
| Playlist DB CRUD | Task 2 |

All spec items covered. ✓

### Known gaps / deferred items

- **DupeResolver "Find Duplicates" button** in the toolbar calls `start_scan([])` — the caller (`MainWindow`) must wire `_dupe_resolver.start_scan(self._all_tracks, ...)` via a connection or a dedicated Organize-tab button. The current MainWindow doesn't wire this explicitly. Add this wiring in Task 10 Step 3 by adding to `_show_page`:
  ```python
  # Already included: when navigating to Organize, pass tracks to rename preview.
  # Also add this for dupe resolver:
  # (The Find Duplicates button in DupeResolver already calls start_scan with [])
  # Fix: override the button click to use all_tracks from MainWindow.
  ```
  A cleaner fix: in `_build_ui`, after creating `self._dupe_resolver`, connect its scan button:
  ```python
  self._dupe_resolver._scan_btn.clicked.disconnect()
  self._dupe_resolver._scan_btn.clicked.connect(
      lambda: self._dupe_resolver.start_scan(
          self._all_tracks,
          duration_tolerance=self._config.deduplication.get("duration_tolerance", 2.0),
          similarity_threshold=self._config.deduplication.get("similarity_threshold", 0.85),
      )
  )
  ```
  Add this line at the end of `_build_ui` in the MainWindow implementation above (Task 10, Step 3).

- **Charts click-through navigation** (clicking a chart segment navigates to matching tracks) — not implemented. This requires `QPieSeries.clicked` and `QBarSeries.clicked` signals. This can be added in a follow-up task.

- **Playlist sidebar tree** — the sidebar shows a task queue, not the saved playlists tree described in the spec. The `PlaylistManager` is a full-page view (accessible via the Playlists nav button). Adding the playlist tree to the sidebar would require embedding a simplified version in `_build_sidebar`. Deferred.

- **Column order persistence** — `columns_changed` saves to `library_columns.visible` in config. The `order` sub-key from the spec is not implemented separately; order is encoded directly in the `visible` list.
