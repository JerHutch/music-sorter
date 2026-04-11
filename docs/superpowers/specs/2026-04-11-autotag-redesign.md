# Auto-Tag Redesign + Full Process

**Date:** 2026-04-11

## Overview

Redesign the two existing library toolbar buttons and add a third:

- **Auto-Tag Selected** — fingerprint each selected track via Chromaprint/AcoustID, look up full metadata from MusicBrainz (title, artist, album, album artist, track number, year), then show a conflict review page before writing anything.
- **Analyze** — detect BPM and key via librosa and overwrite existing values. No review step. Same as today's Analyze behavior.
- **Full Process** — run Analyze and artwork lookup immediately in the background, run Auto-Tag lookup concurrently, then show the conflict review page when the lookup finishes.

## Affected Components

| Component | Change |
|---|---|
| `src/core/fingerprint.py` | Extend `lookup_metadata()` to fetch album, album artist, track number, year from MusicBrainz |
| `src/core/models.py` | Rename `TagConflict` fields to be generic; add `acoustid_no_match: bool = False` to `Track` |
| `src/core/database.py` | Add `acoustid_no_match` column; migrate existing DBs |
| `src/gui/workers.py` | New `AutoTagWorker`; remove `overwrite` flag from `AnalyzeWorker` |
| `src/gui/autotag_review.py` | New conflict review page |
| `src/gui/library_browser.py` | Add `process_all_requested` signal; add No Match column; add Full Process button |
| `src/gui/main_window.py` | Wire new worker, page, signals; handle parallel workers for Full Process |
| `src/gui/itunes_import.py` | Update to use renamed `TagConflict` fields |

## `fingerprint.py` changes

`lookup_metadata()` currently returns `{score, recording_id, title, artist}`.

After the AcoustID match, call `musicbrainzngs.get_recording_by_id(recording_id, includes=["releases", "artists"])` to fetch the first release. Extend the return dict to include:

```python
{
    "score": float,
    "recording_id": str,
    "title": str | None,
    "artist": str | None,
    "album": str | None,
    "album_artist": str | None,
    "track_number": int | None,
    "year": int | None,
}
```

If the MusicBrainz call fails or returns no releases, the four new fields are `None`. The function still returns the AcoustID result rather than `None` in this case.

## `TagConflict` model changes

`TagConflict` currently uses iTunes-specific field names. Rename to be generic so both the iTunes import and the new auto-tag flow share the same model without awkward naming:

| Old field | New field |
|---|---|
| `file_value` | `local_value` |
| `itunes_value` | `incoming_value` |
| resolution `"file"` | resolution `"local"` |
| resolution `"itunes"` | resolution `"incoming"` |

Update `itunes_import.py` and `main_window.py` (`_on_itunes_apply`) to use the new names.

## `AutoTagWorker`

New `QThread` subclass in `workers.py`.

**Inputs:** `tracks: list[Track]`, `db: Database`

**Signals:**
- `progress(completed: int, total: int)`
- `finished(conflicts: list[TagConflict], unmatched_count: int)`
- `error(message: str)`

**Logic per track:**
1. Generate fingerprint via `generate_fingerprint(track.file_path)`
2. Call `lookup_metadata(fingerprint, track.duration)`
3. If no result: increment `unmatched_count`, set `track.acoustid_no_match = True`, upsert to DB, continue
4. If result found: set `track.acoustid_no_match = False`, upsert to DB
5. For each of the six fields (`title`, `artist`, `album`, `album_artist`, `track_number`, `year`): if the looked-up value is not `None` and differs from the track's current value, append a `TagConflict(file_path, field, local_value, incoming_value)`
6. Emit `finished(all_conflicts, unmatched_count)`

**Fields compared:** title, artist, album, album_artist, track_number, year. Genre is excluded.

## `AnalyzeWorker` changes

Remove the `overwrite` parameter — always overwrite. Update `_on_auto_tag` / `_on_analyze` in `main_window.py` to both call the same worker (no flag).

## `AutoTagReview` page

New `src/gui/autotag_review.py`. Structured similarly to `itunes_import.py`.

**Signals:**
- `apply_requested(conflicts: list[TagConflict])` — emits only the accepted (Use Found) conflicts

**`load_conflicts(conflicts, source_tracks)`** — populates the table.

**Table columns:** File | Field | Current Value | Found Value | Resolution

- Rows with empty current value default to **Use Found**
- Rows with a non-empty current value default to **Keep**
- Clicking the Resolution cell toggles between Keep and Use Found
- Rows are grouped by file (all conflicts for one track are adjacent)
- Above the table: **Use Found for All** and **Keep All** bulk-toggle buttons

**Buttons (bottom):**
- **Apply Changes** — enabled only when at least one row is set to Use Found; fires `apply_requested` with accepted rows
- **Skip All** — navigates back to the library without writing anything

## `acoustid_no_match` column

**`Track` model:** `acoustid_no_match: bool = False`

**Database migration:**
```sql
ALTER TABLE tracks ADD COLUMN IF NOT EXISTS acoustid_no_match INTEGER DEFAULT 0;
```
Run on `Database.__init__` after the existing schema setup, guarded so it's a no-op if the column already exists.

**Library browser:** new sortable **No Match** column. Displays `✓` when `acoustid_no_match` is `True`, blank otherwise. Allows sorting unmatched tracks to top for manual review.

**Behaviour:** set to `True` when `AutoTagWorker` finds no AcoustID match. Reset to `False` if a subsequent run does find a match. Never set by `AnalyzeWorker` or `ArtworkWorker`.

## Data Flow

### Auto-Tag Selected

1. `LibraryBrowser` emits `auto_tag_requested(tracks)`
2. `MainWindow._on_auto_tag()` starts `AutoTagWorker(tracks, db)`, shows progress bar
3. Worker emits `finished(conflicts, unmatched_count)`
4. `MainWindow`:
   - Updates status bar: `"Auto-tag complete — X conflicts found, Y tracks had no match"`
   - If `conflicts` is empty, calls `_refresh_library()` and returns
   - Otherwise loads `AutoTagReview` with conflicts and navigates to it
5. User clicks Apply → `apply_requested(accepted)` fires
6. `MainWindow._on_autotag_apply()` runs `TagWriteWorker(accepted)` → on finish, `_refresh_library()` and navigate to library

### Analyze

Same as today. `LibraryBrowser` emits `analyze_requested(tracks)` → `AnalyzeWorker` → `_refresh_library()`.

### Full Process

1. `LibraryBrowser` emits `process_all_requested(tracks)`
2. `MainWindow._on_full_process()`:
   - Starts `AnalyzeWorker(tracks, db)` immediately
   - Starts `ArtworkWorker(tracks)` immediately
   - Starts `AutoTagWorker(tracks, db)` immediately
3. `AnalyzeWorker` and `ArtworkWorker` finish independently — each calls `_refresh_library()` on finish
4. `AutoTagWorker` finishes → same flow as Auto-Tag Selected from step 4 above

All three workers run concurrently. The conflict review page appears only after `AutoTagWorker` finishes, regardless of whether the other two are done.

## `library_browser.py` changes

- Rename signal: `auto_tag_requested` comment updated to reflect new meaning
- New signal: `process_all_requested = Signal(list)`
- New button in toolbar: **Full Process** — emits `process_all_requested`
- New column in track table: **No Match** — bound to `track.acoustid_no_match`

## `main_window.py` changes

- Add `_autotag_worker: AutoTagWorker | None = None`
- New page in stack: `self._autotag_review = AutoTagReview()` at index `_PAGE_AUTOTAG_REVIEW`
- Wire `_autotag_review.apply_requested` → `_on_autotag_apply()`
- `_on_auto_tag()` — starts `AutoTagWorker`, connects signals
- `_on_full_process()` — starts all three workers, connects signals
- `_on_autotag_finished()` — handles status bar update and navigation
- `_on_autotag_apply()` — runs `TagWriteWorker` on accepted conflicts

## Testing

- `tests/core/test_fingerprint.py` — unit tests for extended `lookup_metadata()` with mocked AcoustID and MusicBrainz responses; test fallback when MusicBrainz returns no releases
- `tests/core/test_autotag_worker.py` (or extend `test_workers.py`) — test conflict generation: fields that match produce no conflict; empty fields default to Use Found; no-match tracks set `acoustid_no_match=True`
- `tests/core/test_database.py` — test that `acoustid_no_match` column is added on init and round-trips correctly
