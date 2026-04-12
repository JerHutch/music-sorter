# Organize Scope Selector

**Date:** 2026-04-12
**Status:** Approved

## Problem

The Rename / Organize view currently operates on the entire library. The config supports per-bucket rename patterns (`rename_patterns` keyed by bucket name), but the UI ignores this — there is no way to target a specific bucket or playlist before running a rename.

## Goal

Add a scope selector to the Rename / Organize tab so the user can act on "All Tracks", a specific bucket, or a specific smart playlist, with the pattern input auto-loading the bucket's configured rename pattern when a bucket is selected.

## Approach

Scope selection lives inside `RenamePreview` (Option A). The widget receives the full track list, config, and playlists and handles filtering internally. `main_window` stays thin — it gains two extra setter calls when navigating to the Organize page.

## UI

A `QComboBox` sits at the top of `RenamePreview`, above the "Rename Pattern" group box, labelled "Scope:".

**Combo contents:**
1. "All Tracks"
2. Visual separator (`insertSeparator()`)
3. One entry per bucket — names from `config.rename_patterns` keys, excluding `"default"`
4. Visual separator
5. One entry per smart playlist — names from the `SmartPlaylist` list

**On scope change:**

| Selection | Track filter | Pattern loaded |
|-----------|-------------|----------------|
| All Tracks | full `_tracks` list | `rename_patterns["default"]` |
| Bucket *X* | `[t for t in _tracks if t.bucket == X]` | `config.get_rename_pattern(X)` |
| Playlist *P* | `evaluate_playlist(P, _tracks)` | `rename_patterns["default"]` |

Changing scope clears the plan table and updates the live preview label. It does **not** auto-run a dry-run — the user clicks "Generate Dry-Run Preview" explicitly.

## API Changes to `RenamePreview`

Two new public setters:

```python
def set_config(self, config: Config) -> None: ...
def set_playlists(self, playlists: list[SmartPlaylist]) -> None: ...
```

- `set_config` stores the config; used to populate bucket entries and call `config.get_rename_pattern(bucket)` on scope change.
- `set_playlists` stores the playlist list; used to populate playlist entries and call `evaluate_playlist()` on scope change.
- `set_tracks()` continues to store the **full** track list. `_active_tracks` is derived internally on scope change and used in place of `self._tracks` for preview and dry-run.
- `set_patterns()` is kept unchanged (tests depend on it) but is superseded by `set_config` for combo-driven pattern loading.

## `main_window` Changes

`_show_page()` gains two calls alongside existing ones:

```python
self._rename_preview.set_config(self._config)
self._rename_preview.set_playlists(self._db.get_all_smart_playlists())
```

## Testing

- **Unit**: bucket filtering (tracks filtered by `track.bucket == name`) — new test in existing suite
- **Playlist filtering**: already covered by `evaluate_playlist` tests; no new test needed
- **Pattern auto-load**: already covered by config tests
- **Manual**: launch app → Organize → Rename/Organize → select bucket → confirm pattern updates and dry-run scopes correctly

## Implementation Steps

1. Add `set_config()` and `set_playlists()` setters to `RenamePreview`
2. Add `_active_tracks` internal state, derived from scope selection
3. Add scope `QComboBox` to `_build_ui()` with population logic
4. Wire `_on_scope_changed()` slot: filter tracks, load pattern, clear plan table, refresh preview
5. Replace `self._tracks` references in `_update_preview()` and `_run_dryrun()` with `self._active_tracks`
6. Update `main_window._show_page()` to call the two new setters
7. Write unit test for bucket filtering
8. **Update docs** — revise the Rename/Organize user-facing guide to describe the scope selector

## Out of Scope

- Per-playlist rename patterns (no such concept in config)
- Auto-running dry-run on scope change
- Persisting last-used scope across sessions
