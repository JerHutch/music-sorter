# Cancel Button for Batch Operations

**Date:** 2026-04-14
**Status:** Approved

## Summary

Extend the existing status-bar cancel button (currently scan-only) to stop all running batch operations: artwork lookup, auto-tag (AcoustID fingerprint + MusicBrainz), and analyze (BPM/key detection). A single cancel stops all three if they are running concurrently (as happens during "Process All").

## Workers

`AnalyzeWorker`, `AutoTagWorker`, and `ArtworkWorker` each gain:

```python
self._cancelled = False  # in __init__

def cancel(self) -> None:
    self._cancelled = True
```

Each worker's `run()` loop checks `self._cancelled` at the **top** of each iteration and `break`s early, allowing the current track to finish cleanly before stopping. This matches the existing `ScanWorker` pattern exactly.

## MainWindow UI Wiring

### Re-wire cancel button

In `_build_ui`, change:
```python
self._cancel_btn.clicked.connect(self._cancel_scan)
```
to:
```python
self._cancel_btn.clicked.connect(self._cancel_current_operation)
```

### New `_cancel_current_operation()`

```python
def _cancel_current_operation(self) -> None:
    for worker in (self._scan_worker, self._analyze_worker,
                   self._autotag_worker, self._artwork_worker):
        if worker and worker.isRunning():
            worker.cancel()
    self._cancel_btn.setEnabled(False)
    self._status_label.setText("Cancelling…")
```

### Show cancel button

`_start_analyze`, `_on_auto_tag`, and `_on_artwork_scan` gain the same two lines already present in `_start_scan`:
```python
self._cancel_btn.setVisible(True)
self._cancel_btn.setEnabled(True)
```

### Hide cancel button — shared helper

Replace direct `self._cancel_btn.setVisible(False)` calls in finished handlers with a shared helper:

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

Each `finished` / `done` handler calls `_maybe_hide_cancel()` instead of directly hiding the button. This keeps the button visible until the last concurrent operation finishes.

## Testing

New tests in `tests/gui/` (separate file or appended to relevant worker test files):

| Test | What it verifies |
|------|-----------------|
| `test_analyze_worker_cancel` | Call `.cancel()` after first track; assert `finished` list is shorter than the full track list |
| `test_autotag_worker_cancel` | Same shape; mock `generate_fingerprint` and count calls |
| `test_artwork_worker_cancel` | Same; mock `find_local_artwork` and count calls |

No `MainWindow` wiring tests — the cancel button logic is thin delegation and the worker-level tests cover the meaningful behavior.

## Files Changed

| File | Change |
|------|--------|
| `src/gui/workers.py` | Add `_cancelled` + `cancel()` to `AnalyzeWorker`, `AutoTagWorker`, `ArtworkWorker`; add cancel check in each `run()` loop |
| `src/gui/main_window.py` | Re-wire cancel button; add `_cancel_current_operation()`; add `_maybe_hide_cancel()`; show cancel btn in analyze/autotag/artwork start methods |
| `tests/gui/test_cancel.py` | New cancel tests for the three workers |
