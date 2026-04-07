# Batch Artwork & Tag-Write Progress Bar Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show a deterministic 0–100% progress bar in the status bar during batch artwork scans and batch tag writes (>1 track); single-track operations are unchanged.

**Architecture:** Add a `progress = Signal(int, int)` to `ArtworkWorker` (mirrors the pattern already in `TagWriteWorker`). In `MainWindow`, connect the existing `_progress_bar` widget to both workers when operating on multiple tracks, and hide it on completion.

**Tech Stack:** PySide6 (`QProgressBar`, `Signal`), pytest-qt

---

## File Map

| File | Change |
|------|--------|
| `src/gui/workers.py` | Add `progress` signal to `ArtworkWorker`; restructure `run()` to remove `continue` so progress emits unconditionally at end of each iteration |
| `src/gui/main_window.py` | Wire progress bar in `_on_artwork_scan` and `_on_tag_save` (batch only); add `_on_artwork_progress` and `_on_tag_write_progress` handlers; hide bar in `_on_tag_write_finished` |
| `tests/gui/test_artwork_worker.py` | Add test for `progress` signal |
| `tests/gui/test_main_window.py` | Add tests: batch artwork shows bar, single artwork does not; batch tag write shows bar, single does not |

---

## Task 1: Add `progress` signal to `ArtworkWorker`

**Files:**
- Modify: `src/gui/workers.py`
- Test: `tests/gui/test_artwork_worker.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/gui/test_artwork_worker.py`:

```python
def test_artwork_worker_emits_progress_for_multiple_tracks(qtbot, tmp_path):
    tracks = [_make_track(tmp_path, f"T{i}") for i in range(3)]
    worker = ArtworkWorker(tracks)
    progress_calls = []
    worker.progress.connect(lambda c, t: progress_calls.append((c, t)))
    with patch("src.gui.workers.find_local_artwork", return_value=_PNG_1X1), \
         patch("src.gui.workers.embed_artwork"):
        with qtbot.waitSignal(worker.done, timeout=5000):
            worker.start()
    assert progress_calls == [(1, 3), (2, 3), (3, 3)]
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/gui/test_artwork_worker.py::test_artwork_worker_emits_progress_for_multiple_tracks -v
```

Expected: `FAILED` — `AttributeError: 'ArtworkWorker' object has no attribute 'progress'`

- [ ] **Step 3: Add `progress` signal and restructure `run()`**

Replace the `ArtworkWorker` class in `src/gui/workers.py` with:

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

    def run(self) -> None:
        total = len(self._tracks)
        for i, track in enumerate(self._tracks):
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
            self.progress.emit(i + 1, total)
        self.done.emit()
```

- [ ] **Step 4: Run all artwork worker tests**

```bash
pytest tests/gui/test_artwork_worker.py -v
```

Expected: all `PASSED`

- [ ] **Step 5: Commit**

```bash
git add src/gui/workers.py tests/gui/test_artwork_worker.py
git commit -m "feat: add progress signal to ArtworkWorker"
```

---

## Task 2: Wire batch artwork progress bar in MainWindow

**Files:**
- Modify: `src/gui/main_window.py`
- Test: `tests/gui/test_main_window.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/gui/test_main_window.py`:

```python
def test_batch_artwork_scan_shows_progress_bar(qtbot):
    from pathlib import Path
    from src.core.models import Track
    mock_config, mock_db = _make_mock_env()
    with patch("src.gui.main_window.Database") as MockDB, \
         patch("src.gui.main_window.Config.load_user_config") as mock_cfg:
        mock_cfg.return_value = mock_config
        MockDB.return_value = mock_db
        from src.gui.main_window import MainWindow
        win = MainWindow()
        qtbot.addWidget(win)

    tracks = [
        Track(file_path=Path(f"/tmp/{i}.mp3"), file_size=1000, bitrate=320, duration=200.0)
        for i in range(2)
    ]
    with patch("src.gui.main_window.ArtworkWorker") as MockWorker:
        mock_instance = MagicMock()
        MockWorker.return_value = mock_instance
        win._on_artwork_scan(tracks)

    assert win._progress_bar.isVisible()
    assert win._progress_bar.maximum() == 2
    assert win._progress_bar.value() == 0


def test_single_artwork_scan_does_not_show_progress_bar(qtbot):
    from pathlib import Path
    from src.core.models import Track
    mock_config, mock_db = _make_mock_env()
    with patch("src.gui.main_window.Database") as MockDB, \
         patch("src.gui.main_window.Config.load_user_config") as mock_cfg:
        mock_cfg.return_value = mock_config
        MockDB.return_value = mock_db
        from src.gui.main_window import MainWindow
        win = MainWindow()
        qtbot.addWidget(win)

    tracks = [
        Track(file_path=Path("/tmp/a.mp3"), file_size=1000, bitrate=320, duration=200.0)
    ]
    with patch("src.gui.main_window.ArtworkWorker") as MockWorker:
        mock_instance = MagicMock()
        MockWorker.return_value = mock_instance
        win._on_artwork_scan(tracks)

    assert not win._progress_bar.isVisible()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/gui/test_main_window.py::test_batch_artwork_scan_shows_progress_bar tests/gui/test_main_window.py::test_single_artwork_scan_does_not_show_progress_bar -v
```

Expected: `FAILED` for the batch test (bar is not visible); `PASSED` for the single test (it already passes since bar is hidden by default).

- [ ] **Step 3: Update `_on_artwork_scan` and add `_on_artwork_progress`**

Replace `_on_artwork_scan` in `src/gui/main_window.py`:

```python
def _on_artwork_scan(self, tracks: list[Track]) -> None:
    if self._artwork_worker and self._artwork_worker.isRunning():
        self.statusBar().showMessage("Scan already in progress", 2000)
        return
    panel = self._tag_editor.artwork_panel
    panel.set_scanning(True)
    self._artwork_worker = ArtworkWorker(tracks)
    self._artwork_worker.finished.connect(self._on_artwork_scan_track_done)
    self._artwork_worker.done.connect(lambda: panel.set_scanning(False))
    self._artwork_worker.status_message.connect(
        lambda msg: self.statusBar().showMessage(msg, 5000)
    )
    if len(tracks) > 1:
        self._progress_bar.setRange(0, len(tracks))
        self._progress_bar.setValue(0)
        self._progress_bar.setVisible(True)
        self._artwork_worker.progress.connect(self._on_artwork_progress)
        self._artwork_worker.done.connect(lambda: self._progress_bar.setVisible(False))
    self._artwork_worker.start()
```

Add `_on_artwork_progress` directly below `_on_artwork_scan_track_done`:

```python
def _on_artwork_progress(self, completed: int, total: int) -> None:
    self._progress_bar.setRange(0, total)
    self._progress_bar.setValue(completed)
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/gui/test_main_window.py::test_batch_artwork_scan_shows_progress_bar tests/gui/test_main_window.py::test_single_artwork_scan_does_not_show_progress_bar -v
```

Expected: both `PASSED`

- [ ] **Step 5: Commit**

```bash
git add src/gui/main_window.py tests/gui/test_main_window.py
git commit -m "feat: show progress bar during batch artwork scan"
```

---

## Task 3: Wire batch tag-write progress bar in MainWindow

**Files:**
- Modify: `src/gui/main_window.py`
- Test: `tests/gui/test_main_window.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/gui/test_main_window.py`:

```python
def test_batch_tag_write_shows_progress_bar(qtbot):
    from pathlib import Path
    from src.core.models import Track
    mock_config, mock_db = _make_mock_env()
    with patch("src.gui.main_window.Database") as MockDB, \
         patch("src.gui.main_window.Config.load_user_config") as mock_cfg:
        mock_cfg.return_value = mock_config
        MockDB.return_value = mock_db
        from src.gui.main_window import MainWindow
        win = MainWindow()
        qtbot.addWidget(win)

    tracks = [
        Track(file_path=Path(f"/tmp/{i}.mp3"), file_size=1000, bitrate=320, duration=200.0)
        for i in range(2)
    ]
    with patch("src.gui.main_window.TagWriteWorker") as MockWorker:
        mock_instance = MagicMock()
        MockWorker.return_value = mock_instance
        win._on_tag_save(tracks, {"title": "New Title"})

    assert win._progress_bar.isVisible()
    assert win._progress_bar.maximum() == 2
    assert win._progress_bar.value() == 0


def test_single_tag_write_does_not_show_progress_bar(qtbot):
    from pathlib import Path
    from src.core.models import Track
    mock_config, mock_db = _make_mock_env()
    with patch("src.gui.main_window.Database") as MockDB, \
         patch("src.gui.main_window.Config.load_user_config") as mock_cfg:
        mock_cfg.return_value = mock_config
        MockDB.return_value = mock_db
        from src.gui.main_window import MainWindow
        win = MainWindow()
        qtbot.addWidget(win)

    tracks = [
        Track(file_path=Path("/tmp/a.mp3"), file_size=1000, bitrate=320, duration=200.0)
    ]
    with patch("src.gui.main_window.TagWriteWorker") as MockWorker:
        mock_instance = MagicMock()
        MockWorker.return_value = mock_instance
        win._on_tag_save(tracks, {"title": "New Title"})

    assert not win._progress_bar.isVisible()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/gui/test_main_window.py::test_batch_tag_write_shows_progress_bar tests/gui/test_main_window.py::test_single_tag_write_does_not_show_progress_bar -v
```

Expected: `FAILED` for the batch test; `PASSED` for the single test.

- [ ] **Step 3: Update `_on_tag_save`, `_on_tag_write_finished`, and add `_on_tag_write_progress`**

Replace `_on_tag_save` in `src/gui/main_window.py`:

```python
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
    if len(tracks) > 1:
        self._progress_bar.setRange(0, len(tracks))
        self._progress_bar.setValue(0)
        self._progress_bar.setVisible(True)
        self._tag_worker.progress.connect(self._on_tag_write_progress)
    self._tag_worker.start()
    self._status_label.setText(f"Writing tags for {len(tracks)} track(s)…")
```

Replace `_on_tag_write_finished` to hide the progress bar on completion:

```python
def _on_tag_write_finished(self, updated: list) -> None:
    self._progress_bar.setVisible(False)
    self._status_label.setText(f"Saved tags for {len(updated)} track(s)")
    self._refresh_library()
```

Add `_on_tag_write_progress` directly below `_on_tag_write_finished`:

```python
def _on_tag_write_progress(self, completed: int, total: int) -> None:
    self._progress_bar.setRange(0, total)
    self._progress_bar.setValue(completed)
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/gui/test_main_window.py::test_batch_tag_write_shows_progress_bar tests/gui/test_main_window.py::test_single_tag_write_does_not_show_progress_bar -v
```

Expected: both `PASSED`

- [ ] **Step 5: Run the full test suite**

```bash
pytest tests/gui/ -v
```

Expected: all `PASSED`

- [ ] **Step 6: Commit**

```bash
git add src/gui/main_window.py tests/gui/test_main_window.py
git commit -m "feat: show progress bar during batch tag write"
```
