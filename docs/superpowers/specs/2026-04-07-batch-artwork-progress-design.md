# Batch Artwork & Tag-Write Progress Bar

**Date:** 2026-04-07  
**Feature file:** `docs/todo/features/ready/batch-artworksearch-progress.md`

## Summary

Show a deterministic 0–100% progress bar in the status bar when batch-scanning for artwork or batch-writing tags (i.e. more than one track). Single-track operations are unchanged.

---

## Scope

Two operations gain progress visibility:

1. **Batch artwork scan** — triggered via the "No Artwork" task queue or multi-track selection in the tag editor
2. **Batch tag write** — triggered when saving edits to multiple tracks at once

Single-track scans and single-track tag saves do **not** show the bar (to avoid a distracting flash for instant operations).

---

## Design

### `workers.py` — `ArtworkWorker`

Add a `progress = Signal(int, int)` signal (completed, total).  
Emit it inside `run()` after each track's `finished` emit:

```python
progress = Signal(int, int)   # completed, total

# in run(), after self.finished.emit(...):
self.progress.emit(i + 1, total)   # where i is the 0-based loop index, total = len(self._tracks)
```

This mirrors the existing pattern in `TagWriteWorker`, `AnalyzeWorker`, and `RenameWorker`.

### `main_window.py` — `_on_artwork_scan`

When `len(tracks) > 1`:
- Set `_progress_bar` range to `(0, len(tracks))`, value to `0`, make visible
- Connect `ArtworkWorker.progress` → `_on_artwork_progress`
- On `done` signal: hide `_progress_bar`, restore status label

When `len(tracks) == 1`: no change from current behavior.

Add handler:
```python
def _on_artwork_progress(self, completed: int, total: int) -> None:
    self._progress_bar.setRange(0, total)
    self._progress_bar.setValue(completed)
```

### `main_window.py` — `_on_tag_save`

When `len(tracks) > 1`:
- Set `_progress_bar` range to `(0, len(tracks))`, value to `0`, make visible
- Connect `TagWriteWorker.progress` → `_on_tag_write_progress`
- On `finished`: hide `_progress_bar`

When `len(tracks) == 1`: no change from current behavior.

Add handler:
```python
def _on_tag_write_progress(self, completed: int, total: int) -> None:
    self._progress_bar.setRange(0, total)
    self._progress_bar.setValue(completed)
```

---

## What's not changing

- No new widgets — the existing `_progress_bar` (200px, permanent widget in status bar) is reused
- No changes to `src/core/`
- No new files
- Single-track artwork scan and single-track tag save: unchanged

---

## Testing

- Batch artwork scan on 2+ tracks: progress bar appears, advances per track, hides on completion
- Single-track artwork scan: no progress bar shown
- Batch tag write on 2+ tracks: progress bar appears, advances per track, hides on completion
- Single-track tag save: no progress bar shown
