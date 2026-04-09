# Smart Playlists Design

**Date:** 2026-04-08  
**Status:** Approved

## Overview

Replace the existing simple `PlaylistDefinition` filter system with iTunes-style smart playlists. Smart playlists are saved queries against the library: the user defines a rule tree, and the playlist is dynamically populated with matching tracks. Playlists persist in the database and can optionally appear in the main sidebar for one-click library filtering.

---

## Decisions

- **Replace, not extend** — `PlaylistDefinition` and `filter_tracks_for_playlist` are removed entirely. No existing playlists to migrate.
- **Sidebar click** — clicking a playlist in the sidebar filters the Library view (same behaviour as clicking a Bucket).
- **One level of nesting** — top-level rule list with optional sub-groups; sub-groups cannot contain further sub-groups.
- **`date_added` field** — added to `Track` and the `tracks` DB table; set on first insert, never overwritten.
- **In-memory evaluation** — rules are evaluated in Python against the in-memory track list, consistent with the existing pattern.

---

## Data Model

### `src/core/models.py`

`PlaylistDefinition` is removed. Three new dataclasses are added:

```python
@dataclass
class SimpleRule:
    """A single rule condition."""
    field: str       # e.g. "artist", "bpm", "date_added"
    operator: str    # e.g. "contains", "gt", "in_last_days"
    value: str | float | bool

@dataclass
class RuleGroup:
    """A group of rules combined with AND or OR."""
    conjunction: str              # "AND" | "OR"
    rules: list[SimpleRule]

@dataclass
class SmartPlaylist:
    """A named smart playlist with a rule tree."""
    name: str
    conjunction: str = "AND"                          # top-level AND/OR
    rules: list[SimpleRule | RuleGroup] = field(default_factory=list)
    limit_count: int | None = None                    # max tracks; None = unlimited
    limit_order: str | None = None                    # "random" | "bpm" | "artist" | "title" | "date_added"
    sort_by: str | None = None                        # output sort field
    folder: str | None = None                         # grouping in PlaylistManager tree
    format: str = "m3u"                               # "m3u" | "pls"
    show_in_sidebar: bool = True
```

`Track` gains one new field:

```python
date_added: float | None = None   # Unix timestamp; set on first DB insert
```

### Serialization

Rules serialize as JSON tagged dicts:

```json
{"type": "simple", "field": "genre", "operator": "contains", "value": "Jazz"}
{"type": "group",  "conjunction": "ANY", "rules": [...]}
```

The `type` discriminator makes deserialization unambiguous.

---

## Field Registry & Operators

Defined in `src/core/playlist.py` as module-level constants. The UI and evaluator both read from this registry — adding a new field is a one-line change.

| Field | Display Name | Type |
|---|---|---|
| title | Title | string |
| artist | Artist | string |
| album | Album | string |
| album_artist | Album Artist | string |
| genre | Genre | string |
| bucket | Bucket | string |
| key | Key | string |
| bpm | BPM | number |
| year | Year | number |
| track_number | Track # | number |
| bitrate | Bitrate | number |
| duration | Duration | number |
| tag_completeness | Tag Completeness | number |
| has_artwork | Has Artwork | boolean |
| date_added | Date Added | date |

**Operators by type:**

| Type | Operators |
|---|---|
| string | contains, does_not_contain, is, is_not, starts_with, ends_with |
| number | is, is_not, gt, lt, gte, lte, in_range |
| boolean | is_true, is_false |
| date | is, before, after, in_last_days |

`in_range` takes a `(min, max)` tuple as its value. `in_last_days` takes an integer N and compares against `time.time() - N * 86400` at evaluation time (relative, not stored as a cutoff).

A `None` field value on a track never matches any operator (no crash, just `False`).

---

## Evaluation

### `src/core/playlist.py`

```python
def evaluate_rule(rule: dict, track: Track) -> bool:
    if rule["type"] == "group":
        results = [evaluate_rule(r, track) for r in rule["rules"]]
        return all(results) if rule["conjunction"] == "AND" else any(results)
    # SimpleRule
    field_val = getattr(track, rule["field"], None)
    if field_val is None:
        return False
    return _apply_operator(field_val, rule["operator"], rule["value"])

def evaluate_playlist(playlist: SmartPlaylist, tracks: list[Track]) -> list[Track]:
    matching = [t for t in tracks if _evaluate_top(playlist, t)]
    if playlist.sort_by:
        matching.sort(key=lambda t: (getattr(t, playlist.sort_by) is None,
                                     getattr(t, playlist.sort_by, None)))
    if playlist.limit_count:
        matching = _apply_limit(matching, playlist.limit_count, playlist.limit_order)
    return matching
```

`_evaluate_top` applies the top-level conjunction across `playlist.rules`, each of which is either a `SimpleRule` or `RuleGroup` dict (deserialized from JSON).

`_apply_limit` handles `limit_order`:
- `"random"` — `random.sample`
- field name — sort by that field, then slice
- `None` — slice in current order

---

## Database

### Schema changes in `src/core/database.py`

**`tracks` table** — add `date_added REAL` column:
```sql
ALTER TABLE tracks ADD COLUMN date_added REAL
```
Applied via `try/except OperationalError` migration guard (no-op if already present).

`upsert_track` sets `date_added` in the `INSERT` but excludes it from the `ON CONFLICT DO UPDATE` clause, so it is only written once.

**New `smart_playlists` table** — replaces the old `playlists` table:
```sql
CREATE TABLE IF NOT EXISTS smart_playlists (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL UNIQUE,
    folder          TEXT,
    format          TEXT NOT NULL DEFAULT 'm3u',
    conjunction     TEXT NOT NULL DEFAULT 'AND',
    rules           TEXT NOT NULL DEFAULT '[]',
    limit_count     INTEGER,
    limit_order     TEXT,
    sort_by         TEXT,
    show_in_sidebar INTEGER NOT NULL DEFAULT 1
)
```

Old `playlists` table is dropped via migration guard:
```sql
DROP TABLE IF EXISTS playlists
```

**New CRUD methods** on `Database`:
- `get_all_smart_playlists() -> list[SmartPlaylist]`
- `upsert_smart_playlist(playlist: SmartPlaylist) -> None`
- `delete_smart_playlist(name: str) -> None`

Old `get_all_playlists`, `upsert_playlist`, `delete_playlist` methods are removed.

---

## GUI

### `src/gui/playlist_manager.py`

The right-hand editor panel is rebuilt. The current `QComboBox` bucket/sort dropdowns are replaced with a dynamic rule builder widget.

**Editor layout (top to bottom):**
1. Name, Folder, Format fields (kept)
2. Sort By combo + Limit (count input + order combo)
3. Show in sidebar checkbox
4. Horizontal rule
5. Top-level conjunction selector ("Match ALL / ANY of the following rules:")
6. Rule rows — each row: field combo → operator combo → value input → remove button
7. Sub-groups — indented box with own conjunction selector, rule rows, and remove-group button
8. "Add Rule" and "Add Group" buttons
9. Live "N matching tracks" label
10. Save and Generate File… buttons

The operator combo for a rule row updates dynamically when the field changes (string fields show string operators, number fields show number operators, etc.). The value input switches to a checkbox for boolean fields and a spinbox for `in_last_days`.

### `src/gui/main_window.py`

A new "Playlists" section is added to the sidebar below Task Queue, mirroring the Buckets section structure:

```python
self._playlist_items: dict[str, QTreeWidgetItem] = {}
```

`_update_sidebar_playlists(playlists: list[SmartPlaylist])` builds the list from playlists where `show_in_sidebar is True`. The section is hidden if the list is empty.

`_refresh_library()` calls `_update_sidebar_playlists(self._db.get_all_smart_playlists())`.

Clicking a playlist item calls `self._library.filter_by_fn(lambda t: t in evaluate_playlist(pld, self._all_tracks))` and navigates to `_PAGE_LIBRARY`.

`PlaylistManager` is updated to receive and return `SmartPlaylist` objects.

---

## Testing

### `tests/core/test_playlist.py` (new)

- `evaluate_rule` — one test per operator: string (contains, is, starts_with, ends_with, does_not_contain, is_not), number (gt, lt, gte, lte, is, is_not, in_range), boolean (is_true, is_false), date (before, after, in_last_days, is)
- `None` field value returns `False` without raising
- Top-level AND: all rules must match
- Top-level OR: any rule suffices
- `RuleGroup` with AND conjunction
- `RuleGroup` with OR conjunction
- `evaluate_playlist` with `sort_by`
- `evaluate_playlist` with `limit_count` + `limit_order="random"`
- `evaluate_playlist` with `limit_count` + field-based `limit_order`
- Empty rules list returns all tracks

### `tests/core/test_database.py` (additions)

- `date_added` is set on first `upsert_track`
- `date_added` is not overwritten on a second `upsert_track` for the same path
- `upsert_smart_playlist` + `get_all_smart_playlists` round-trips the full rule tree (including a `RuleGroup`)
- `delete_smart_playlist` removes the playlist
- Schema migration: calling `_setup_schema` on a DB that already has the old `playlists` table drops it cleanly
