# Cancel Button for Batch Operations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the existing status-bar cancel button to stop AnalyzeWorker, AutoTagWorker, and ArtworkWorker, in addition to the already-supported ScanWorker.

**Architecture:** Each of the three workers gets a `_cancelled` flag + `cancel()` method following the existing ScanWorker pattern. The cancel button is re-wired to a new `_cancel_current_operation()` that stops all running workers. A `_maybe_hide_cancel()` helper ensures the button stays visible until the last concurrent op finishes.

**Tech Stack:** Python 3.14, PySide6, pytest, uv (run tests with `uv run pytest`)

---

### Task 1: Add cancel support to AnalyzeWorker

**Files:**
- Modify: `src/gui/workers.py` (AnalyzeWorker class, lines ~183-221)
- Test: `tests/gui/test_cancel.py` (create)

- [ ] **Step 1: Write the failing test**

Create `tests/gui/test_cancel.py`:

```python
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.core.models import Track


def _make_track(n: int) -> Track:
    return Track(
        file_path=Path(f"/music/track{n}.mp3"),
        file_size=1_000_000, bitrate=320, duration=240.0,
        title=f"Track {n}", artist="Artist", album=None,
        album_artist=None, track_number=None, year=None,
    )


@patch("src.gui.workers.upsert_track_in_db")
@patch("src.gui.workers.write_tags")
@patch("src.gui.workers.detect_key", return_value="Am")
@patch("src.gui.workers.detect_bpm", return_value=120.0)
def test_analyze_worker_cancel(mock_bpm, mock_key, mock_write, mock_upsert, tmp_path):
    from src.core.database import Database
    from src.gui.workers import AnalyzeWorker

    db = Database(tmp_path / "test.db")
    tracks = [_make_track(i) for i in range(5)]

    updated_out = []
    worker = AnalyzeWorker(tracks, db)
    worker.finished.connect(updated_out.extend)

    # Cancel after first progress signal
    call_count = 0
    def on_progress(completed, total):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            worker.cancel()

    worker.progress.connect(on_progress)
    worker.run()  # run directly (no QThread)

    # Should have processed fewer than all 5 tracks
    assert call_count < 5
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/gui/test_cancel.py::test_analyze_worker_cancel -v
```

Expected: FAIL — `AnalyzeWorker` has no `cancel()` method and processes all tracks regardless.

- [ ] **Step 3: Add `_cancelled` flag and `cancel()` to AnalyzeWorker**

In `src/gui/workers.py`, modify `AnalyzeWorker.__init__` and `run()`:

```python
class AnalyzeWorker(QThread):
    """Detects BPM and key for a list of tracks, writes the results back to disk and DB."""

    progress = Signal(int, int)   # completed, total
    finished = Signal(list)       # list[Track] — updated tracks
    error = Signal(str)

    def __init__(self, tracks: list[Track], db: Database):
        super().__init__()
        self._tracks = tracks
        self._db = db
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self):
        total = len(self._tracks)
        updated: list[Track] = []
        for i, track in enumerate(self._tracks, 1):
            if self._cancelled:
                break
            try:
                bpm = detect_bpm(track.file_path)
                key = detect_key(track.file_path)
                changed: list[str] = []
                if bpm is not None:
                    track.bpm = bpm
                    changed.append("bpm")
                if key is not None:
                    track.key = key
                    changed.append("key")
                if changed:
                    write_tags(track.file_path, track, changed)
                    track.tag_completeness = track.compute_completeness(COMPLETENESS_FIELDS)
                    try:
                        mtime = track.file_path.stat().st_mtime
                    except OSError:
                        mtime = 0.0
                    upsert_track_in_db(self._db, track, file_mtime=mtime)
                    updated.append(track)
            except Exception:
                logger.exception("AnalyzeWorker: failed on %s", track.file_path)
            self.progress.emit(i, total)
        self.finished.emit(updated)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/gui/test_cancel.py::test_analyze_worker_cancel -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/gui/workers.py tests/gui/test_cancel.py
git commit -m "feat: add cancel support to AnalyzeWorker"
```

---

### Task 2: Add cancel support to AutoTagWorker

**Files:**
- Modify: `src/gui/workers.py` (AutoTagWorker class, lines ~227-297)
- Test: `tests/gui/test_cancel.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `tests/gui/test_cancel.py`:

```python
@patch("src.gui.workers.lookup_metadata", return_value=None)
@patch("src.gui.workers.generate_fingerprint", return_value=("fake-fp", 240.0))
def test_autotag_worker_cancel(mock_fp, mock_lookup, tmp_path):
    from src.core.database import Database
    from src.gui.workers import AutoTagWorker

    db = Database(tmp_path / "test.db")
    tracks = [_make_track(i) for i in range(5)]
    for track in tracks:
        db.upsert_track(track, file_mtime=1000.0)

    progress_calls = []
    worker = AutoTagWorker(tracks, db, api_key="test-key")

    def on_progress(completed, total):
        progress_calls.append(completed)
        if completed == 1:
            worker.cancel()

    worker.progress.connect(on_progress)
    worker.run()

    assert len(progress_calls) < 5
    assert mock_fp.call_count < 5
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/gui/test_cancel.py::test_autotag_worker_cancel -v
```

Expected: FAIL — `AutoTagWorker` has no `cancel()` and processes all tracks.

- [ ] **Step 3: Add `_cancelled` flag and `cancel()` to AutoTagWorker**

In `src/gui/workers.py`, modify `AutoTagWorker.__init__` and `run()`:

```python
class AutoTagWorker(QThread):
    """Fingerprints tracks, looks up metadata via AcoustID + MusicBrainz, and builds
    a list of TagConflict objects for fields that differ from existing tag values.
    """

    progress = Signal(int, int)   # completed, total
    finished = Signal(list, int)  # list[TagConflict], unmatched_count
    error = Signal(str)

    def __init__(self, tracks: list[Track], db: Database, api_key: str = ""):
        super().__init__()
        self._tracks = tracks
        self._db = db
        self._api_key = api_key
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        total = len(self._tracks)
        conflicts: list[TagConflict] = []
        unmatched = 0
        try:
            for i, track in enumerate(self._tracks, 1):
                if self._cancelled:
                    break
                try:
                    fp_result = generate_fingerprint(track.file_path)
                    if fp_result is None:
                        unmatched += 1
                        track.acoustid_no_match = True
                        self._upsert(track)
                        self.progress.emit(i, total)
                        continue

                    fp, fp_duration = fp_result
                    track.fingerprint = fp
                    meta = lookup_metadata(fp, fp_duration, api_key=self._api_key)
                    if meta is None:
                        unmatched += 1
                        track.acoustid_no_match = True
                        self._upsert(track)
                        self.progress.emit(i, total)
                        continue

                    track.acoustid_no_match = False
                    self._upsert(track)

                    for field in _AUTOTAG_FIELDS:
                        found_val = meta.get(field)
                        if found_val is None:
                            continue
                        current_val = getattr(track, field, None)
                        found_str = str(found_val)
                        current_str = str(current_val) if current_val is not None else ""
                        if found_str != current_str:
                            conflicts.append(TagConflict(
                                file_path=track.file_path,
                                field=field,
                                local_value=current_str,
                                incoming_value=found_str,
                            ))
                except Exception:
                    logger.exception("AutoTagWorker: failed on %s", track.file_path)
                self.progress.emit(i, total)
        except Exception as exc:
            self.error.emit(str(exc))
            return
        self.finished.emit(conflicts, unmatched)

    def _upsert(self, track: Track) -> None:
        try:
            mtime = track.file_path.stat().st_mtime
        except OSError:
            mtime = 0.0
        upsert_track_in_db(self._db, track, file_mtime=mtime)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/gui/test_cancel.py::test_autotag_worker_cancel -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/gui/workers.py tests/gui/test_cancel.py
git commit -m "feat: add cancel support to AutoTagWorker"
```

---

### Task 3: Add cancel support to ArtworkWorker

**Files:**
- Modify: `src/gui/workers.py` (ArtworkWorker class, lines ~300-341)
- Test: `tests/gui/test_cancel.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `tests/gui/test_cancel.py`:

```python
@patch("src.gui.workers.find_local_artwork", return_value=None)
@patch("src.gui.workers._artwork_mod")
def test_artwork_worker_cancel(mock_artwork_mod, mock_find, tmp_path):
    from src.gui.workers import ArtworkWorker

    mock_artwork_mod.musicbrainzngs = None  # skip MusicBrainz path

    tracks = [_make_track(i) for i in range(5)]

    progress_calls = []
    worker = ArtworkWorker(tracks)

    def on_progress(completed, total):
        progress_calls.append(completed)
        if completed == 1:
            worker.cancel()

    worker.progress.connect(on_progress)
    worker.run()

    assert len(progress_calls) < 5
    assert mock_find.call_count < 5
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/gui/test_cancel.py::test_artwork_worker_cancel -v
```

Expected: FAIL — `ArtworkWorker` has no `cancel()` and processes all tracks.

- [ ] **Step 3: Add `_cancelled` flag and `cancel()` to ArtworkWorker**

In `src/gui/workers.py`, modify `ArtworkWorker.__init__` and `run()`:

```python
class ArtworkWorker(QThread):
    """Scans for artwork (local folder → MusicBrainz) and embeds it immediately.

    Processes tracks sequentially to respect MusicBrainz rate limits.
    Emits finished(track, success, image_data) once per track and done() when all complete.
    """

    finished = Signal(object, bool, bytes)  # track, success, image_data (b"" on failure)
    done = Signal()                         # fires once when all tracks are processed
    status_message = Signal(str)            # for the main window status bar
    progress = Signal(int, int)             # completed, total

    def __init__(self, tracks: list[Track]):
        super().__init__()
        self._tracks = tracks
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        total = len(self._tracks)
        for i, track in enumerate(self._tracks, 1):
            if self._cancelled:
                break
            try:
                data = find_local_artwork(track.file_path)
                if data:
                    embed_artwork(track.file_path, data)
                    self.finished.emit(track, True, data)
                elif _artwork_mod.musicbrainzngs is None:
                    self.status_message.emit("MusicBrainz unavailable — artwork not found")
                    self.finished.emit(track, False, b"")
                else:
                    data = search_cover_art(track.artist or "", track.album or "")
                    if data:
                        embed_artwork(track.file_path, data)
                        self.finished.emit(track, True, data)
                    else:
                        self.status_message.emit(
                            f"No artwork found for {track.artist} — {track.album}"
                        )
                        self.finished.emit(track, False, b"")
            except Exception:
                logger.exception("ArtworkWorker: failed for %s", track.file_path)
                self.finished.emit(track, False, b"")
            self.progress.emit(i, total)
        self.done.emit()
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/gui/test_cancel.py::test_artwork_worker_cancel -v
```

Expected: PASS

- [ ] **Step 5: Run all cancel tests together**

```bash
uv run pytest tests/gui/test_cancel.py -v
```

Expected: 3 passed

- [ ] **Step 6: Commit**

```bash
git add src/gui/workers.py tests/gui/test_cancel.py
git commit -m "feat: add cancel support to ArtworkWorker"
```

---

### Task 4: Re-wire MainWindow cancel button

**Files:**
- Modify: `src/gui/main_window.py`

- [ ] **Step 1: Replace `_cancel_scan` connection in `_build_ui`**

In `src/gui/main_window.py`, find:

```python
self._cancel_btn.clicked.connect(self._cancel_scan)
```

Replace with:

```python
self._cancel_btn.clicked.connect(self._cancel_current_operation)
```

- [ ] **Step 2: Add `_cancel_current_operation()` method**

Add this method in the Scanning section of `MainWindow` (after `_cancel_scan`):

```python
def _cancel_current_operation(self) -> None:
    for worker in (self._scan_worker, self._analyze_worker,
                   self._autotag_worker, self._artwork_worker):
        if worker and worker.isRunning():
            worker.cancel()
    self._cancel_btn.setEnabled(False)
    self._status_label.setText("Cancelling…")
```

- [ ] **Step 3: Add `_maybe_hide_cancel()` helper**

Add this method alongside `_cancel_current_operation`:

```python
def _maybe_hide_cancel(self) -> None:
    """Hide and re-enable the cancel button when no batch workers are running."""
    running = any(
        w and w.isRunning()
        for w in (self._scan_worker, self._analyze_worker,
                  self._autotag_worker, self._artwork_worker)
    )
    if not running:
        self._cancel_btn.setVisible(False)
        self._cancel_btn.setEnabled(True)
```

- [ ] **Step 4: Update `_on_scan_finished` to use `_maybe_hide_cancel()`**

Find `_on_scan_finished`:

```python
def _on_scan_finished(self, total: int) -> None:
    self._progress_bar.setVisible(False)
    self._cancel_btn.setVisible(False)
    self._cancel_btn.setEnabled(True)
    self._status_label.setText(f"Scan complete — {total} files processed")
    self._refresh_library()
```

Replace with:

```python
def _on_scan_finished(self, total: int) -> None:
    self._progress_bar.setVisible(False)
    self._maybe_hide_cancel()
    self._status_label.setText(f"Scan complete — {total} files processed")
    self._refresh_library()
```

- [ ] **Step 5: Show cancel button in `_start_analyze`**

Find the end of `_start_analyze` where the worker starts:

```python
        self._status_label.setText(f"Analyzing {len(tracks)} track(s)…")
        self._progress_bar.setRange(0, len(tracks))
        self._progress_bar.setValue(0)
        self._progress_bar.setVisible(True)
        self._analyze_worker.start()
```

Replace with:

```python
        self._status_label.setText(f"Analyzing {len(tracks)} track(s)…")
        self._progress_bar.setRange(0, len(tracks))
        self._progress_bar.setValue(0)
        self._progress_bar.setVisible(True)
        self._cancel_btn.setVisible(True)
        self._cancel_btn.setEnabled(True)
        self._analyze_worker.start()
```

- [ ] **Step 6: Update `_on_analyze_finished` to use `_maybe_hide_cancel()`**

Find:

```python
def _on_analyze_finished(self, updated: list) -> None:
    self._progress_bar.setVisible(False)
    self._status_label.setText(f"Analysis complete — {len(updated)} track(s) updated")
    self._refresh_library()
```

Replace with:

```python
def _on_analyze_finished(self, updated: list) -> None:
    self._progress_bar.setVisible(False)
    self._maybe_hide_cancel()
    self._status_label.setText(f"Analysis complete — {len(updated)} track(s) updated")
    self._refresh_library()
```

- [ ] **Step 7: Show cancel button in `_on_auto_tag`**

Find the end of `_on_auto_tag` where the worker starts:

```python
        self._status_label.setText(f"Looking up metadata for {len(tracks)} track(s)…")
        self._progress_bar.setRange(0, len(tracks))
        self._progress_bar.setValue(0)
        self._progress_bar.setVisible(True)
        self._autotag_worker.start()
```

Replace with:

```python
        self._status_label.setText(f"Looking up metadata for {len(tracks)} track(s)…")
        self._progress_bar.setRange(0, len(tracks))
        self._progress_bar.setValue(0)
        self._progress_bar.setVisible(True)
        self._cancel_btn.setVisible(True)
        self._cancel_btn.setEnabled(True)
        self._autotag_worker.start()
```

- [ ] **Step 8: Update `_on_autotag_finished` to use `_maybe_hide_cancel()`**

Find:

```python
def _on_autotag_finished(self, conflicts: list, unmatched: int) -> None:
    self._progress_bar.setVisible(False)
    msg = "Metadata lookup complete"
```

Replace with:

```python
def _on_autotag_finished(self, conflicts: list, unmatched: int) -> None:
    self._progress_bar.setVisible(False)
    self._maybe_hide_cancel()
    msg = "Metadata lookup complete"
```

- [ ] **Step 9: Show cancel button in `_on_artwork_scan` for batch**

In `_on_artwork_scan`, find the block that handles multiple tracks:

```python
        if len(tracks) > 1:
            self._progress_bar.setRange(0, len(tracks))
            self._progress_bar.setValue(0)
            self._progress_bar.setVisible(True)
            self._artwork_worker.progress.connect(self._on_artwork_progress)
            self._artwork_worker.done.connect(lambda: self._progress_bar.setVisible(False))
        self._artwork_worker.start()
```

Replace with:

```python
        if len(tracks) > 1:
            self._progress_bar.setRange(0, len(tracks))
            self._progress_bar.setValue(0)
            self._progress_bar.setVisible(True)
            self._cancel_btn.setVisible(True)
            self._cancel_btn.setEnabled(True)
            self._artwork_worker.progress.connect(self._on_artwork_progress)
            self._artwork_worker.done.connect(lambda: self._progress_bar.setVisible(False))
            self._artwork_worker.done.connect(self._maybe_hide_cancel)
        self._artwork_worker.start()
```

- [ ] **Step 10: Run the full test suite**

```bash
uv run pytest --tb=short -q
```

Expected: all tests pass (263+)

- [ ] **Step 11: Commit**

```bash
git add src/gui/main_window.py
git commit -m "feat: extend cancel button to cover analyze, autotag, and artwork workers"
```
