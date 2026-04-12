# Organize Scope Selector Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a scope selector (All Tracks / bucket / playlist) to the Rename/Organize tab that filters the working track set and auto-loads the bucket's configured rename pattern.

**Architecture:** `RenamePreview` gains two new setters (`set_config`, `set_playlists`), a `QComboBox` scope selector, and an internal `_active_tracks` list derived on scope change. `main_window._show_page()` calls the two new setters alongside the existing ones. Filtering and pattern loading happen entirely inside `RenamePreview`.

**Tech Stack:** PySide6, Python 3.11+, `src.core.config.Config`, `src.core.models.SmartPlaylist`, `src.core.playlist.evaluate_playlist`

---

### Task 1: Write failing tests for scope filtering behaviour

**Files:**
- Modify: `tests/gui/test_rename_preview.py`

- [ ] **Step 1: Add imports and helpers at the top of the test file**

Open `tests/gui/test_rename_preview.py`. The existing `_track()` helper returns a track with `bucket="DJ Music"`. Add a second helper and the new imports needed:

```python
from src.core.config import Config
from src.core.models import SmartPlaylist, SimpleRule
```

Add after the existing `_track()` helper:

```python
def _track_bucket(path, bucket):
    return Track(
        file_path=Path(path), file_size=1000, bitrate=320, duration=200.0,
        title="Test Song", artist="DJ X", genre="House", bpm=128.0,
        bucket=bucket, tag_completeness=0.9,
    )


def _make_config(patterns: dict) -> Config:
    return Config({"rename_patterns": patterns})
```

- [ ] **Step 2: Add the four new test functions**

Append to `tests/gui/test_rename_preview.py`:

```python
def test_scope_defaults_to_all_tracks(qtbot):
    """With no scope set, all tracks are used for preview/dry-run."""
    view = RenamePreview()
    qtbot.addWidget(view)
    tracks = [
        _track_bucket("/tmp/a.mp3", "DJ Music"),
        _track_bucket("/tmp/b.mp3", "General"),
    ]
    view.set_tracks(tracks)
    assert view.active_track_count() == 2


def test_scope_bucket_filters_tracks(qtbot):
    """Selecting a bucket scope reduces active tracks to that bucket only."""
    view = RenamePreview()
    qtbot.addWidget(view)
    tracks = [
        _track_bucket("/tmp/a.mp3", "DJ Music"),
        _track_bucket("/tmp/b.mp3", "General"),
        _track_bucket("/tmp/c.mp3", "DJ Music"),
    ]
    config = _make_config({"default": "{title}.mp3", "DJ Music": "{artist} - {title}.mp3"})
    view.set_tracks(tracks)
    view.set_config(config)
    view.select_scope("DJ Music")
    assert view.active_track_count() == 2


def test_scope_bucket_loads_pattern(qtbot):
    """Selecting a bucket auto-loads that bucket's rename pattern."""
    view = RenamePreview()
    qtbot.addWidget(view)
    config = _make_config({"default": "{title}.mp3", "DJ Music": "{artist} - {title}.mp3"})
    view.set_tracks([_track_bucket("/tmp/a.mp3", "DJ Music")])
    view.set_config(config)
    view.select_scope("DJ Music")
    assert view.current_pattern() == "{artist} - {title}.mp3"


def test_scope_all_tracks_loads_default_pattern(qtbot):
    """Switching back to All Tracks loads the default pattern."""
    view = RenamePreview()
    qtbot.addWidget(view)
    config = _make_config({"default": "{title}.mp3", "DJ Music": "{artist} - {title}.mp3"})
    view.set_tracks([_track_bucket("/tmp/a.mp3", "DJ Music")])
    view.set_config(config)
    view.select_scope("DJ Music")
    view.select_scope("All Tracks")
    assert view.active_track_count() == 1
    assert view.current_pattern() == "{title}.mp3"
```

- [ ] **Step 3: Run the tests to confirm they fail**

```bash
cd /mnt/cloud/code/music-sorter && pytest tests/gui/test_rename_preview.py -v -k "scope"
```

Expected: 4 failures — `AttributeError: 'RenamePreview' object has no attribute 'active_track_count'` (or similar). If they pass, the implementation already exists and something is wrong.

---

### Task 2: Extend `RenamePreview` with scope state and new setters

**Files:**
- Modify: `src/gui/rename_preview.py`

- [ ] **Step 1: Add new imports at the top of `rename_preview.py`**

The file currently starts with these imports:

```python
from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QProgressBar,
    QTableWidget, QTableWidgetItem, QLineEdit,
    QGroupBox, QHeaderView,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor

from src.core.models import RenameOperation, Track
from src.core.renamer import render_pattern, generate_rename_plan
from src.gui.workers import RenameWorker
```

Replace with:

```python
from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QProgressBar,
    QTableWidget, QTableWidgetItem, QLineEdit,
    QGroupBox, QHeaderView, QComboBox,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor

from src.core.config import Config
from src.core.models import RenameOperation, SmartPlaylist, Track
from src.core.playlist import evaluate_playlist
from src.core.renamer import render_pattern, generate_rename_plan
from src.gui.workers import RenameWorker
```

- [ ] **Step 2: Add new instance variables to `__init__`**

The `__init__` currently reads:

```python
    def __init__(self, parent=None):
        super().__init__(parent)
        self._tracks: list[Track] = []
        self._plan: list[RenameOperation] = []
        self._worker: RenameWorker | None = None
        self._patterns: dict[str, str] = {}
        self._build_ui()
```

Replace with:

```python
    def __init__(self, parent=None):
        super().__init__(parent)
        self._tracks: list[Track] = []
        self._active_tracks: list[Track] = []
        self._plan: list[RenameOperation] = []
        self._worker: RenameWorker | None = None
        self._patterns: dict[str, str] = {}
        self._config: Config | None = None
        self._playlists: list[SmartPlaylist] = []
        self._build_ui()
```

- [ ] **Step 3: Update `set_tracks` to derive `_active_tracks`**

The current `set_tracks`:

```python
    def set_tracks(self, tracks: list[Track]) -> None:
        self._tracks = tracks
        self._update_preview(self._pattern_input.text())
```

Replace with:

```python
    def set_tracks(self, tracks: list[Track]) -> None:
        self._tracks = tracks
        self._on_scope_changed()
```

- [ ] **Step 4: Add `set_config` and `set_playlists` setters**

Add these two methods to the **Public API** section (after `set_patterns`):

```python
    def set_config(self, config: Config) -> None:
        self._config = config
        self._populate_scope_combo()

    def set_playlists(self, playlists: list[SmartPlaylist]) -> None:
        self._playlists = playlists
        self._populate_scope_combo()
```

- [ ] **Step 5: Add `active_track_count`, `select_scope`, and `current_pattern` for testability**

Add these three methods to the **Public API** section:

```python
    def active_track_count(self) -> int:
        return len(self._active_tracks)

    def select_scope(self, name: str) -> None:
        """Programmatically select a scope entry by name (used by tests)."""
        idx = self._scope_combo.findText(name)
        if idx >= 0:
            self._scope_combo.setCurrentIndex(idx)

    def current_pattern(self) -> str:
        return self._pattern_input.text()
```

- [ ] **Step 6: Run the failing tests — expect different failures now**

```bash
cd /mnt/cloud/code/music-sorter && pytest tests/gui/test_rename_preview.py -v -k "scope"
```

Expected: failures mentioning `_scope_combo` not found or `_populate_scope_combo` not defined — the state exists but the combo and handlers are not yet wired.

---

### Task 3: Add scope combo to the UI and wire `_on_scope_changed`

**Files:**
- Modify: `src/gui/rename_preview.py`

- [ ] **Step 1: Add scope row to `_build_ui`**

In `_build_ui`, the method starts with:

```python
    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(6)

        # Pattern editor
        pattern_group = QGroupBox("Rename Pattern")
```

Insert a scope row **before** the pattern group:

```python
    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(6)

        # Scope selector
        scope_row = QHBoxLayout()
        scope_row.addWidget(QLabel("Scope:"))
        self._scope_combo = QComboBox()
        self._scope_combo.addItem("All Tracks")
        self._scope_combo.currentIndexChanged.connect(lambda _: self._on_scope_changed())
        scope_row.addWidget(self._scope_combo, stretch=1)
        outer.addLayout(scope_row)

        # Pattern editor
        pattern_group = QGroupBox("Rename Pattern")
```

- [ ] **Step 2: Add `_populate_scope_combo` helper**

Add this method in the **Internal helpers** section:

```python
    def _populate_scope_combo(self) -> None:
        """Rebuild the scope combo from current config and playlists."""
        current_text = self._scope_combo.currentText()
        self._scope_combo.blockSignals(True)
        self._scope_combo.clear()
        self._scope_combo.addItem("All Tracks")

        if self._config:
            buckets = [k for k in self._config.rename_patterns if k != "default"]
            if buckets:
                self._scope_combo.insertSeparator(self._scope_combo.count())
                for name in buckets:
                    self._scope_combo.addItem(name)

        if self._playlists:
            self._scope_combo.insertSeparator(self._scope_combo.count())
            for pl in self._playlists:
                self._scope_combo.addItem(pl.name)

        # Restore previous selection if still present, else fall back to All Tracks
        idx = self._scope_combo.findText(current_text)
        self._scope_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self._scope_combo.blockSignals(False)
        self._on_scope_changed()
```

- [ ] **Step 3: Add `_on_scope_changed` handler**

Add this method in the **Internal helpers** section:

```python
    def _on_scope_changed(self) -> None:
        """Filter tracks and load pattern based on current scope selection."""
        text = self._scope_combo.currentText()

        if not text or text == "All Tracks":
            self._active_tracks = list(self._tracks)
            if self._config:
                default_pat = self._config.rename_patterns.get("default", "")
                if default_pat:
                    self._pattern_input.setText(default_pat)
        elif self._config and text in self._config.rename_patterns:
            # Bucket selected
            self._active_tracks = [t for t in self._tracks if t.bucket == text]
            pattern = self._config.get_rename_pattern(text)
            if pattern:
                self._pattern_input.setText(pattern)
        else:
            # Playlist selected
            playlist = next((p for p in self._playlists if p.name == text), None)
            if playlist:
                self._active_tracks = evaluate_playlist(playlist, self._tracks)
            else:
                self._active_tracks = list(self._tracks)
            if self._config:
                default_pat = self._config.rename_patterns.get("default", "")
                if default_pat:
                    self._pattern_input.setText(default_pat)

        # Clear stale plan
        self._plan = []
        self._table.setRowCount(0)
        self._execute_btn.setEnabled(False)

        self._update_preview(self._pattern_input.text())
```

- [ ] **Step 4: Update `_update_preview` and `_run_dryrun` to use `_active_tracks`**

In `_update_preview`, replace:

```python
        if not self._tracks or not pattern:
            self._preview_label.setText("Live preview: (select tracks first)")
            self._preview_label.setStyleSheet("color: #888; font-family: monospace;")
            return
        sample = self._tracks[0]
```

with:

```python
        if not self._active_tracks or not pattern:
            self._preview_label.setText("Live preview: (select tracks first)")
            self._preview_label.setStyleSheet("color: #888; font-family: monospace;")
            return
        sample = self._active_tracks[0]
```

In `_run_dryrun`, replace:

```python
        if not self._tracks:
            self._status_label.setText("No tracks loaded.")
            return
        pattern = self._pattern_input.text().strip()
        if not pattern:
            self._status_label.setText("Enter a rename pattern first.")
            return
        try:
            plan = generate_rename_plan(self._tracks, pattern)
```

with:

```python
        if not self._active_tracks:
            self._status_label.setText("No tracks in scope.")
            return
        pattern = self._pattern_input.text().strip()
        if not pattern:
            self._status_label.setText("Enter a rename pattern first.")
            return
        try:
            plan = generate_rename_plan(self._active_tracks, pattern)
```

- [ ] **Step 5: Run the scope tests — expect all 4 to pass**

```bash
cd /mnt/cloud/code/music-sorter && pytest tests/gui/test_rename_preview.py -v -k "scope"
```

Expected output:
```
PASSED tests/gui/test_rename_preview.py::test_scope_defaults_to_all_tracks
PASSED tests/gui/test_rename_preview.py::test_scope_bucket_filters_tracks
PASSED tests/gui/test_rename_preview.py::test_scope_bucket_loads_pattern
PASSED tests/gui/test_rename_preview.py::test_scope_all_tracks_loads_default_pattern
```

- [ ] **Step 6: Run the full rename_preview test suite to verify no regressions**

```bash
cd /mnt/cloud/code/music-sorter && pytest tests/gui/test_rename_preview.py -v
```

Expected: all tests pass.

- [ ] **Step 7: Commit**

```bash
git add src/gui/rename_preview.py tests/gui/test_rename_preview.py
git commit -m "feat: add scope selector to Rename/Organize view"
```

---

### Task 4: Wire new setters in `main_window._show_page`

**Files:**
- Modify: `src/gui/main_window.py:295-303`

- [ ] **Step 1: Update `_show_page` to call `set_config` and `set_playlists`**

In `main_window.py`, find `_show_page`:

```python
        if index == _PAGE_ORGANIZE:
            self._rename_preview.set_tracks(self._all_tracks)
            self._rename_preview.set_patterns(self._config.rename_patterns)
```

Replace with:

```python
        if index == _PAGE_ORGANIZE:
            self._rename_preview.set_tracks(self._all_tracks)
            self._rename_preview.set_patterns(self._config.rename_patterns)
            self._rename_preview.set_config(self._config)
            self._rename_preview.set_playlists(self._db.get_all_smart_playlists())
```

- [ ] **Step 2: Run the full test suite**

```bash
cd /mnt/cloud/code/music-sorter && pytest --tb=short -q
```

Expected: all tests pass, no regressions.

- [ ] **Step 3: Commit**

```bash
git add src/gui/main_window.py
git commit -m "feat: pass config and playlists to RenamePreview on page switch"
```

---

### Task 5: Update the rename/organize user guide

**Files:**
- Modify: `docs/guides/rename-organize.md`

- [ ] **Step 1: Update the "Using the Rename Preview" section**

Find the section:

```markdown
## Using the Rename Preview

1. Click **Organize** in the top navigation bar, then select the **Rename / Organize** tab.
2. The pattern editor at the top shows the current rename pattern. Edit it and the live preview beneath it updates immediately, showing sample output from a few tracks.
3. Click **Generate Preview** to build the full dry-run table: every old path → new path for all tracks. Scroll through and look for anything unexpected.
4. **Collision warnings** (two tracks mapping to the same destination) are highlighted. Music Sorter automatically appends a suffix like `(2)` to resolve collisions, but you should review them.
5. Click **Execute** to run the moves. Progress is shown in the status bar.
```

Replace with:

```markdown
## Using the Rename Preview

1. Click **Organize** in the top navigation bar, then select the **Rename / Organize** tab.
2. Use the **Scope** dropdown to choose which tracks to act on:
   - **All Tracks** — the entire library (default)
   - A **bucket name** — only tracks tagged with that bucket; the pattern input auto-loads the bucket's configured rename pattern
   - A **playlist name** — only tracks matching that smart playlist's rules; the default pattern is loaded
3. The pattern editor shows the current rename pattern. Edit it and the live preview beneath it updates immediately, showing sample output from the first track in scope.
4. Click **Generate Dry-Run Preview** to build the full table: every old path → new path for tracks in scope. Scroll through and look for anything unexpected.
5. **Collision warnings** (two tracks mapping to the same destination) are highlighted. Music Sorter automatically appends a suffix like `(2)` to resolve collisions, but you should review them.
6. Click **Execute Rename** to run the moves. Progress is shown in the status bar.
```

- [ ] **Step 2: Commit**

```bash
git add docs/guides/rename-organize.md
git commit -m "docs: document scope selector in rename/organize guide"
```
