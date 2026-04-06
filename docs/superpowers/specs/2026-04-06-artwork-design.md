# Artwork Feature Design

**Date:** 2026-04-06

## Overview

When the user selects a track, show its embedded album art in the tag editor. If art is missing, provide a placeholder and controls to scan for art or upload from a file. Support a batch "Scan all" mode when multiple tracks are selected.

---

## Architecture

Three new/modified units:

| Unit | Change |
|---|---|
| `src/core/artwork.py` | Add `find_local_artwork(path: Path) -> bytes \| None` — scans the MP3's parent directory for common cover filenames |
| `src/gui/artwork_panel.py` | New `ArtworkPanel(QWidget)` — image display, placeholder, Scan/Upload buttons; emits signals for actions |
| `src/gui/workers.py` | New `ArtworkWorker(QThread)` — local scan → MusicBrainz fallback → embed; emits `finished` and `status_message` |
| `src/gui/tag_editor.py` | Insert `ArtworkPanel` at top of layout; call `panel.load_track()` / `panel.load_batch()` / `panel.clear()` |
| `src/gui/main_window.py` | Wire `ArtworkPanel` signals → `ArtworkWorker`; route `status_message` → `statusBar().showMessage()` |

---

## Components

### `core/artwork.py` — `find_local_artwork(path)`

Scans the MP3's parent directory for these filenames (case-insensitive, in priority order):
`cover.jpg`, `cover.png`, `folder.jpg`, `folder.png`, `artwork.jpg`, `artwork.png`, `front.jpg`, `front.png`

Returns the raw bytes of the first match, or `None` if none found.

Existing functions (`has_artwork`, `embed_artwork`, `search_cover_art`) are unchanged.

To extract embedded art bytes for display, add `read_artwork(path: Path) -> bytes | None` — reads the first `APIC` frame from the ID3 tags and returns its data.

### `gui/artwork_panel.py` — `ArtworkPanel`

**Layout (single-track mode):**
- Square image widget at top (max 200×200px display, scaled to fit)
- Placeholder shown when no art: grey square with a musical note icon and label "No artwork"
- "Scan" button and "Upload" button below the image
- Inline status label for transient messages ("Searching…", "No artwork found", "Failed to save")
- Non-square aspect ratio warning label (hidden unless triggered)

**Signals:**
```python
scan_requested = Signal(list)    # list[Track] — one track or many (batch)
upload_requested = Signal(list, bytes)   # list[Track] + validated image bytes (1 or many)
```

**Public API:**
```python
def load_track(self, track: Track) -> None   # single-track mode
def load_batch(self, tracks: list[Track]) -> None  # batch mode
def clear(self) -> None
def set_scanning(self, scanning: bool) -> None  # disables buttons during scan
def show_artwork(self, image_data: bytes) -> None  # update displayed image
```

**Batch mode:** Shows "N tracks selected" label with two buttons: "Scan all" and "Upload to all". Scan all only targets tracks missing art. Upload to all opens the same file dialog/validation flow as single-track upload, then embeds the chosen image into every selected track.

### `gui/workers.py` — `ArtworkWorker`

```python
class ArtworkWorker(QThread):
    finished = Signal(Track, bool)   # track, success
    status_message = Signal(str)     # for status bar
```

For each track:
1. Call `find_local_artwork(track.file_path)` — if found, call `embed_artwork` and emit `finished(track, True)`
2. If not found, call `search_cover_art(track.artist, track.album)` — if found, embed and emit `finished(track, True)`
3. If MusicBrainz unavailable (`musicbrainzngs is None`) emit `status_message("MusicBrainz unavailable — artwork not found")` and `finished(track, False)`
4. If MusicBrainz returns no results emit `status_message("No artwork found for <artist> — <album>")` and `finished(track, False)`
5. On any embed failure: log exception, emit `finished(track, False)`, set inline panel label to "Failed to save artwork"

Batch scans run tracks sequentially (not parallel) to respect MusicBrainz rate limits.

### `gui/tag_editor.py` changes

- Import and instantiate `ArtworkPanel` at the top of `_build_ui()`
- Insert it before the scroll area containing the form fields
- Call `self._artwork_panel.load_track(track)` in `_populate_single()`
- Call `self._artwork_panel.load_batch(tracks)` in `_populate_batch()`
- Call `self._artwork_panel.clear()` in `_clear_fields()`
- Expose `artwork_panel` property so `MainWindow` can wire its signals

### `gui/main_window.py` changes

- Connect `self._tag_editor.artwork_panel.scan_requested` → spawn `ArtworkWorker`
- Connect `self._tag_editor.artwork_panel.upload_requested` → call `embed_artwork` on each track in the list, then call `artwork_panel.show_artwork(bytes)` (single-track mode) or refresh count label (batch mode)
- On `ArtworkWorker.finished(track, True)` → call `artwork_panel.show_artwork(read_artwork(track.file_path))`
- On `ArtworkWorker.status_message(msg)` → `self.statusBar().showMessage(msg, 5000)`

---

## Image Upload Validation

Performed in `ArtworkPanel._on_upload_clicked()` before emitting `upload_requested`:

1. File dialog filtered to `*.jpg *.jpeg *.png`
2. Read raw file bytes — if > 10MB, show inline error "File too large (max 10 MB)" and abort
3. Load with `QImage` — if load fails, show inline error "Not a valid image"
4. If either dimension > 3000px: scale down with `QImage.scaled(3000, 3000, Qt.KeepAspectRatio, Qt.SmoothTransformation)`
5. If width ≠ height: show inline warning "⚠ Not square — may look cropped in some players" (non-blocking)
6. Convert scaled `QImage` to bytes via `QBuffer` + `QImage.save()` and emit `upload_requested`

---

## Error Handling

| Situation | Behaviour |
|---|---|
| Corrupt/unreadable art bytes | Show placeholder, log warning |
| MusicBrainz not installed | Status bar: "MusicBrainz unavailable — artwork not found" |
| MusicBrainz no results | Status bar: "No artwork found for \<artist\> — \<album\>" |
| Embed write failure | Inline panel label: "Failed to save artwork"; log exception |
| Upload invalid file | Inline panel label: "Not a valid image" |
| Upload file > 10MB | Inline panel label: "File too large (max 10 MB)" |
| Scan in progress | Scan/Upload buttons disabled; label shows "Searching…" |

---

## Testing

### `tests/core/test_artwork.py`
- `test_find_local_artwork_finds_cover_jpg` — fixture dir with `cover.jpg`, asserts bytes returned
- `test_find_local_artwork_priority_order` — dir with both `folder.jpg` and `cover.jpg`, asserts `cover.jpg` wins
- `test_find_local_artwork_none_when_missing` — empty dir, asserts `None`
- `test_read_artwork_returns_bytes` — fixture MP3 with embedded art, asserts bytes returned
- `test_read_artwork_returns_none_when_absent` — untagged fixture MP3, asserts `None`

### `tests/gui/test_artwork_panel.py`
- `test_load_track_with_artwork_shows_image` — patch `read_artwork` to return bytes, assert placeholder hidden
- `test_load_track_without_artwork_shows_placeholder` — patch returns `None`, assert placeholder visible
- `test_load_batch_shows_batch_ui` — load 3 tracks, assert "3 tracks selected" label and Scan button visible
- `test_scan_requested_signal_fires` — click Scan, assert signal emitted with correct track
- `test_upload_requested_signal_fires` — patch file dialog + QImage load, assert signal emitted
- `test_set_scanning_disables_buttons` — call `set_scanning(True)`, assert buttons disabled
- `test_batch_upload_emits_all_tracks` — load 3 tracks via `load_batch`, patch file dialog, assert `upload_requested` emitted with all 3 tracks and image bytes

MusicBrainz network calls are not tested (consistent with existing `search_cover_art` — no live network in tests).
