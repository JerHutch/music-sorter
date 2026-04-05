# Remaining GUI Views to Implement

These views exist as placeholders in `src/gui/`. The core library logic backing each one is complete and tested.

## 1. Tag Editor (`src/gui/tag_editor.py`)

**Single track editing:** Click a track in the library browser to open a detail panel showing all tag fields as editable inputs. Save writes via `core.tagger.write_tags` and updates the DB.

**Batch editing:** Select multiple tracks, open the editor showing shared fields. Fields with mixed values display "[Multiple]". Editing a field applies the new value to all selected tracks. Needs dry-run preview before applying.

**Core modules used:** `tagger.write_tags`, `database.upsert_track`, `history.log_tag_write`

## 2. Duplicate Resolver (`src/gui/dupe_resolver.py`)

Table of `DupeGroup` objects, each expandable to show all copies with paths, bitrates, and tag diffs highlighted. Per-group actions: accept auto-recommendation (keep best, merge tags), override which copy to keep, resolve individual tag conflicts via dropdowns, skip. Bulk action button to process all remaining groups with auto-recommendation.

**Core modules used:** `deduplicator.find_duplicates`, `deduplicator.merge_tags`, `history.log_delete`, `history.log_tag_write`

## 3. iTunes Import View (`src/gui/itunes_import.py`)

File picker for the iTunes XML (or pre-filled from settings). Progress bar during parse/match. Conflict resolution table showing: file path, field name, current MP3 value, iTunes value, and a keep-file/use-iTunes toggle per row. Bulk rule buttons: "Always prefer iTunes for [field]" and "Always prefer file for [field]" to resolve remaining conflicts in batch.

**Core modules used:** `itunes.parse_itunes_xml`, `itunes.match_itunes_to_files`, `itunes.resolve_conflicts`, `tagger.write_tags`

## 4. Rename/Organize Preview (`src/gui/rename_preview.py`)

Pattern editor text input with live preview (type a pattern, see sample output for a few tracks). Full dry-run table: old path → new path for all affected tracks, with collision warnings highlighted in red. Execute button only enabled after reviewing the dry-run. Progress bar during execution.

**Core modules used:** `renamer.render_pattern`, `renamer.generate_rename_plan`, `organizer.execute_rename_plan`, `organizer.cleanup_empty_dirs`, `history.log_rename`

## 5. Statistics View (`src/gui/stats_view.py`)

Charts and graphs for the dashboard. Needs actual chart rendering (consider `matplotlib` embedded in Qt via `FigureCanvasQTAgg`, or a lighter option like `pyqtgraph`):
- Tag completeness breakdown (pie/donut chart)
- Genre distribution (bar chart)
- Bitrate distribution (bar chart)
- Storage usage per bucket (bar chart)

All charts should be clickable — clicking a segment navigates to the matching tracks in the library browser.

**Core modules used:** `database.get_stats`

## 6. Playlist Manager (`src/gui/playlist_manager.py`)

Tree view with folder support for organizing saved playlists. Right-click context menu to create folders, rename, delete. Drag-and-drop to reorder playlists within folders. Playlist editor panel: name, folder, format (M3U/PLS), filter criteria builder (bucket, genre, BPM range, key list), sort field. "Generate" button creates the playlist file. "Re-generate All" to update all playlists after collection changes.

**Core modules used:** `playlist.filter_tracks_for_playlist`, `playlist.generate_m3u`, `playlist.generate_pls`, `database.filter_tracks`

## 7. Sidebar Wiring

The sidebar bucket list and task queue are static placeholders. They need to:
- Show live counts from `database.get_stats`
- Clicking a bucket filters the library browser to that bucket
- Clicking a task queue item (Missing Tags, Duplicates, No Artwork, etc.) filters the library to those tracks
- Counts should refresh after scans and operations

## 8. Column Configuration

The library browser table has hardcoded columns. It needs:
- Right-click on column header to show/hide columns
- Drag columns to reorder
- Persist column visibility and order in config via `config.library_columns`
