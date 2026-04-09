# Smart Playlists Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the simple dict-based `PlaylistDefinition` with iTunes-style smart playlists that support a rule tree (one level of nesting), persist in SQLite, and appear in the main sidebar.

**Architecture:** New `SmartPlaylist`, `SimpleRule`, and `RuleGroup` dataclasses replace `PlaylistDefinition`. A field registry and recursive evaluator in `core/playlist.py` filter tracks in-memory. The DB gains a `smart_playlists` table and a `date_added` column on `tracks`. The `PlaylistManager` editor panel is rewritten as a dynamic rule builder; a new Playlists section in the sidebar links to filtered Library views.

**Tech Stack:** Python 3.11+, PySide6, SQLite (via stdlib `sqlite3`), pytest

---

## File Map

| File | Action | What changes |
|---|---|---|
| `src/core/models.py` | Modify | Add `SimpleRule`, `RuleGroup`, `SmartPlaylist`; add `date_added` to `Track`; keep `PlaylistDefinition` until Task 4 |
| `src/core/playlist.py` | Rewrite | Field registry, operator evaluation, `evaluate_rule`, `evaluate_playlist`; keep `generate_m3u`/`generate_pls` |
| `src/core/database.py` | Modify | Add `date_added` column + migration, `smart_playlists` table, new CRUD; remove old playlist CRUD |
| `src/gui/playlist_manager.py` | Rewrite | `RuleRowWidget`, `RuleGroupWidget`, `RuleBuilderWidget`; updated `PlaylistManager` |
| `src/gui/main_window.py` | Modify | Add Playlists sidebar section; wire click → Library filter |
| `tests/core/test_playlist.py` | Modify | Remove old `filter_tracks_for_playlist` tests; add evaluation tests |
| `tests/core/test_database.py` | Modify | Remove old `PlaylistDefinition` playlist tests; add smart playlist + `date_added` tests |

---

## Task 1: Add new model classes to models.py

**Files:**
- Modify: `src/core/models.py`
- Test: `tests/core/test_models.py` (create if missing, or add to existing)

- [ ] **Step 1: Write the failing test**

Create (or append to) `tests/core/test_models.py`:

```python
from src.core.models import SimpleRule, RuleGroup, SmartPlaylist, Track
from pathlib import Path


def test_simple_rule_fields():
    rule = SimpleRule(field="genre", operator="contains", value="Jazz")
    assert rule.field == "genre"
    assert rule.operator == "contains"
    assert rule.value == "Jazz"


def test_rule_group_fields():
    group = RuleGroup(
        conjunction="OR",
        rules=[SimpleRule(field="genre", operator="is", value="Jazz")],
    )
    assert group.conjunction == "OR"
    assert len(group.rules) == 1


def test_smart_playlist_defaults():
    p = SmartPlaylist(name="Test")
    assert p.conjunction == "AND"
    assert p.rules == []
    assert p.limit_count is None
    assert p.limit_order is None
    assert p.sort_by is None
    assert p.folder is None
    assert p.format == "m3u"
    assert p.show_in_sidebar is True


def test_track_has_date_added():
    t = Track(file_path=Path("/a.mp3"), file_size=1000, bitrate=320, duration=180.0)
    assert hasattr(t, "date_added")
    assert t.date_added is None
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/core/test_models.py -v -k "simple_rule or rule_group or smart_playlist or date_added"
```

Expected: FAIL — `ImportError: cannot import name 'SimpleRule'`

- [ ] **Step 3: Add new dataclasses to models.py**

In `src/core/models.py`, add after the existing imports and before `Track`:

```python
@dataclass
class SimpleRule:
    """A single filter condition."""

    field: str
    operator: str
    value: str | float | bool | None = None


@dataclass
class RuleGroup:
    """A group of SimpleRules combined with AND or OR."""

    conjunction: str  # "AND" | "OR"
    rules: list[SimpleRule]
```

Add after `RuleGroup`:

```python
@dataclass
class SmartPlaylist:
    """A named smart playlist with a rule tree."""

    name: str
    conjunction: str = "AND"
    rules: list = field(default_factory=list)  # list[SimpleRule | RuleGroup]
    limit_count: int | None = None
    limit_order: str | None = None
    sort_by: str | None = None
    folder: str | None = None
    format: str = "m3u"
    show_in_sidebar: bool = True
```

Add `date_added` to `Track` after `has_artwork`:

```python
    date_added: float | None = None
```

Do **not** remove `PlaylistDefinition` yet — it is still referenced by `database.py` and `playlist_manager.py`.

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/core/test_models.py -v -k "simple_rule or rule_group or smart_playlist or date_added"
```

Expected: PASS

- [ ] **Step 5: Verify full suite still passes**

```bash
pytest
```

Expected: all existing tests still pass (PlaylistDefinition still exists, nothing broken).

- [ ] **Step 6: Commit**

```bash
git add src/core/models.py tests/core/test_models.py
git commit -m "feat: add SimpleRule, RuleGroup, SmartPlaylist models; add date_added to Track"
```

---

## Task 2: Rewrite playlist.py — field registry and evaluation

**Files:**
- Rewrite: `src/core/playlist.py`
- Modify: `tests/core/test_playlist.py`

- [ ] **Step 1: Write the failing tests**

Replace `tests/core/test_playlist.py` entirely with:

```python
from __future__ import annotations

import time
from pathlib import Path

import pytest

from src.core.models import SimpleRule, RuleGroup, SmartPlaylist, Track
from src.core.playlist import (
    FIELD_REGISTRY,
    OPERATORS_BY_TYPE,
    evaluate_rule,
    evaluate_playlist,
    generate_m3u,
    generate_pls,
)


def _track(path="/music/song.mp3", **kwargs) -> Track:
    defaults = dict(
        file_path=Path(path),
        file_size=5_000_000,
        bitrate=320,
        duration=240.0,
        title="Song",
        artist="Artist",
        has_artwork=False,
        tag_completeness=0.8,
        date_added=time.time() - 3600,
    )
    defaults.update(kwargs)
    return Track(**defaults)


# ---------------------------------------------------------------------------
# generate_m3u / generate_pls (unchanged behaviour)
# ---------------------------------------------------------------------------

def test_generate_m3u(tmp_path):
    tracks = [
        _track("/music/a.mp3", title="Song A", artist="Artist A", duration=180.0),
        _track("/music/b.mp3", title="Song B", artist="Artist B", duration=200.0),
    ]
    output = tmp_path / "playlist.m3u"
    generate_m3u(tracks, output)
    content = output.read_text()
    assert "#EXTM3U" in content
    assert "#EXTINF:180,Artist A - Song A" in content
    assert "/music/a.mp3" in content


def test_generate_pls(tmp_path):
    tracks = [
        _track("/music/a.mp3", title="Song A", duration=180.0),
        _track("/music/b.mp3", title="Song B", duration=200.0),
    ]
    output = tmp_path / "playlist.pls"
    generate_pls(tracks, output)
    content = output.read_text()
    assert "[playlist]" in content
    assert "File1=/music/a.mp3" in content
    assert "NumberOfEntries=2" in content


# ---------------------------------------------------------------------------
# Field registry
# ---------------------------------------------------------------------------

def test_field_registry_contains_expected_fields():
    for field in ("title", "artist", "genre", "bpm", "has_artwork", "date_added"):
        assert field in FIELD_REGISTRY


def test_operators_by_type_keys():
    for t in ("string", "number", "boolean", "date"):
        assert t in OPERATORS_BY_TYPE


# ---------------------------------------------------------------------------
# String operators
# ---------------------------------------------------------------------------

def test_string_contains():
    rule = SimpleRule(field="genre", operator="contains", value="elec")
    assert evaluate_rule(rule, _track(genre="Electronic")) is True
    assert evaluate_rule(rule, _track(genre="Rock")) is False


def test_string_contains_case_insensitive():
    rule = SimpleRule(field="artist", operator="contains", value="beatles")
    assert evaluate_rule(rule, _track(artist="The Beatles")) is True


def test_string_does_not_contain():
    rule = SimpleRule(field="genre", operator="does_not_contain", value="Jazz")
    assert evaluate_rule(rule, _track(genre="Rock")) is True
    assert evaluate_rule(rule, _track(genre="Jazz")) is False


def test_string_is():
    rule = SimpleRule(field="genre", operator="is", value="Jazz")
    assert evaluate_rule(rule, _track(genre="Jazz")) is True
    assert evaluate_rule(rule, _track(genre="Rock")) is False


def test_string_is_not():
    rule = SimpleRule(field="genre", operator="is_not", value="Jazz")
    assert evaluate_rule(rule, _track(genre="Rock")) is True
    assert evaluate_rule(rule, _track(genre="Jazz")) is False


def test_string_starts_with():
    rule = SimpleRule(field="artist", operator="starts_with", value="The")
    assert evaluate_rule(rule, _track(artist="The Beatles")) is True
    assert evaluate_rule(rule, _track(artist="Beatles")) is False


def test_string_ends_with():
    rule = SimpleRule(field="title", operator="ends_with", value="wall")
    assert evaluate_rule(rule, _track(title="Wonderwall")) is True
    assert evaluate_rule(rule, _track(title="Wonder")) is False


# ---------------------------------------------------------------------------
# Number operators
# ---------------------------------------------------------------------------

def test_number_gt():
    rule = SimpleRule(field="bpm", operator="gt", value=120)
    assert evaluate_rule(rule, _track(bpm=140.0)) is True
    assert evaluate_rule(rule, _track(bpm=100.0)) is False


def test_number_lt():
    rule = SimpleRule(field="bpm", operator="lt", value=120)
    assert evaluate_rule(rule, _track(bpm=100.0)) is True
    assert evaluate_rule(rule, _track(bpm=140.0)) is False


def test_number_gte():
    rule = SimpleRule(field="bpm", operator="gte", value=120)
    assert evaluate_rule(rule, _track(bpm=120.0)) is True
    assert evaluate_rule(rule, _track(bpm=119.0)) is False


def test_number_lte():
    rule = SimpleRule(field="bpm", operator="lte", value=120)
    assert evaluate_rule(rule, _track(bpm=120.0)) is True
    assert evaluate_rule(rule, _track(bpm=121.0)) is False


def test_number_is():
    rule = SimpleRule(field="year", operator="is", value=2020)
    assert evaluate_rule(rule, _track(year=2020)) is True
    assert evaluate_rule(rule, _track(year=2021)) is False


def test_number_is_not():
    rule = SimpleRule(field="year", operator="is_not", value=2021)
    assert evaluate_rule(rule, _track(year=2020)) is True
    assert evaluate_rule(rule, _track(year=2021)) is False


def test_number_in_range():
    rule = SimpleRule(field="bpm", operator="in_range", value=(120, 140))
    assert evaluate_rule(rule, _track(bpm=128.0)) is True
    assert evaluate_rule(rule, _track(bpm=100.0)) is False
    assert evaluate_rule(rule, _track(bpm=150.0)) is False


# ---------------------------------------------------------------------------
# Boolean operators
# ---------------------------------------------------------------------------

def test_boolean_is_true():
    rule = SimpleRule(field="has_artwork", operator="is_true", value=None)
    assert evaluate_rule(rule, _track(has_artwork=True)) is True
    assert evaluate_rule(rule, _track(has_artwork=False)) is False


def test_boolean_is_false():
    rule = SimpleRule(field="has_artwork", operator="is_false", value=None)
    assert evaluate_rule(rule, _track(has_artwork=False)) is True
    assert evaluate_rule(rule, _track(has_artwork=True)) is False


# ---------------------------------------------------------------------------
# Date operators
# ---------------------------------------------------------------------------

def test_date_before():
    old = time.time() - 86400 * 30
    recent = time.time() - 3600
    cutoff = time.time() - 86400 * 7
    rule = SimpleRule(field="date_added", operator="before", value=cutoff)
    assert evaluate_rule(rule, _track(date_added=old)) is True
    assert evaluate_rule(rule, _track(date_added=recent)) is False


def test_date_after():
    old = time.time() - 86400 * 30
    recent = time.time() - 3600
    cutoff = time.time() - 86400 * 7
    rule = SimpleRule(field="date_added", operator="after", value=cutoff)
    assert evaluate_rule(rule, _track(date_added=recent)) is True
    assert evaluate_rule(rule, _track(date_added=old)) is False


def test_date_in_last_days():
    recent = time.time() - 3600  # 1 hour ago
    old = time.time() - 86400 * 30  # 30 days ago
    rule = SimpleRule(field="date_added", operator="in_last_days", value=7)
    assert evaluate_rule(rule, _track(date_added=recent)) is True
    assert evaluate_rule(rule, _track(date_added=old)) is False


# ---------------------------------------------------------------------------
# None field value
# ---------------------------------------------------------------------------

def test_none_field_returns_false():
    rule = SimpleRule(field="genre", operator="contains", value="Jazz")
    assert evaluate_rule(rule, _track(genre=None)) is False


def test_none_bpm_returns_false():
    rule = SimpleRule(field="bpm", operator="gt", value=100)
    assert evaluate_rule(rule, _track(bpm=None)) is False


# ---------------------------------------------------------------------------
# RuleGroup
# ---------------------------------------------------------------------------

def test_rule_group_and_all_match():
    group = RuleGroup(conjunction="AND", rules=[
        SimpleRule(field="genre", operator="is", value="Jazz"),
        SimpleRule(field="bpm", operator="gt", value=90),
    ])
    assert evaluate_rule(group, _track(genre="Jazz", bpm=100.0)) is True


def test_rule_group_and_one_fails():
    group = RuleGroup(conjunction="AND", rules=[
        SimpleRule(field="genre", operator="is", value="Jazz"),
        SimpleRule(field="bpm", operator="gt", value=90),
    ])
    assert evaluate_rule(group, _track(genre="Rock", bpm=100.0)) is False


def test_rule_group_or_one_matches():
    group = RuleGroup(conjunction="OR", rules=[
        SimpleRule(field="genre", operator="is", value="Jazz"),
        SimpleRule(field="genre", operator="is", value="Blues"),
    ])
    assert evaluate_rule(group, _track(genre="Jazz")) is True
    assert evaluate_rule(group, _track(genre="Blues")) is True
    assert evaluate_rule(group, _track(genre="Rock")) is False


# ---------------------------------------------------------------------------
# evaluate_playlist
# ---------------------------------------------------------------------------

def test_evaluate_playlist_basic():
    tracks = [
        _track("/a.mp3", genre="Jazz"),
        _track("/b.mp3", genre="Rock"),
    ]
    playlist = SmartPlaylist(name="Jazz", rules=[
        SimpleRule(field="genre", operator="is", value="Jazz"),
    ])
    result = evaluate_playlist(playlist, tracks)
    assert len(result) == 1
    assert result[0].file_path == Path("/a.mp3")


def test_evaluate_playlist_empty_rules_returns_all():
    tracks = [_track(f"/{i}.mp3") for i in range(3)]
    assert len(evaluate_playlist(SmartPlaylist(name="All"), tracks)) == 3


def test_evaluate_playlist_top_level_or():
    tracks = [
        _track("/a.mp3", genre="Jazz"),
        _track("/b.mp3", genre="Blues"),
        _track("/c.mp3", genre="Rock"),
    ]
    playlist = SmartPlaylist(name="Jazz or Blues", conjunction="OR", rules=[
        SimpleRule(field="genre", operator="is", value="Jazz"),
        SimpleRule(field="genre", operator="is", value="Blues"),
    ])
    result = evaluate_playlist(playlist, tracks)
    assert len(result) == 2


def test_evaluate_playlist_sort_by():
    tracks = [
        _track("/a.mp3", bpm=140.0),
        _track("/b.mp3", bpm=90.0),
        _track("/c.mp3", bpm=120.0),
    ]
    playlist = SmartPlaylist(name="Sorted", sort_by="bpm")
    result = evaluate_playlist(playlist, tracks)
    assert [t.bpm for t in result] == [90.0, 120.0, 140.0]


def test_evaluate_playlist_limit():
    tracks = [_track(f"/{i}.mp3") for i in range(10)]
    playlist = SmartPlaylist(name="Limited", limit_count=3)
    result = evaluate_playlist(playlist, tracks)
    assert len(result) == 3


def test_evaluate_playlist_limit_by_field():
    tracks = [_track(f"/{i}.mp3", bpm=float(i * 10)) for i in range(5)]
    playlist = SmartPlaylist(name="Top2", limit_count=2, limit_order="bpm")
    result = evaluate_playlist(playlist, tracks)
    assert len(result) == 2
    assert result[0].bpm == 0.0
    assert result[1].bpm == 10.0


def test_evaluate_playlist_with_rule_group():
    tracks = [
        _track("/a.mp3", genre="Jazz", bpm=100.0),
        _track("/b.mp3", genre="Blues", bpm=80.0),
        _track("/c.mp3", genre="Rock", bpm=140.0),
    ]
    playlist = SmartPlaylist(name="Jazz or Blues with low BPM", conjunction="AND", rules=[
        RuleGroup(conjunction="OR", rules=[
            SimpleRule(field="genre", operator="is", value="Jazz"),
            SimpleRule(field="genre", operator="is", value="Blues"),
        ]),
        SimpleRule(field="bpm", operator="lt", value=120),
    ])
    result = evaluate_playlist(playlist, tracks)
    assert len(result) == 2
    paths = {t.file_path for t in result}
    assert Path("/a.mp3") in paths
    assert Path("/b.mp3") in paths
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/core/test_playlist.py -v -k "evaluate_rule or evaluate_playlist or FIELD_REGISTRY"
```

Expected: FAIL — `ImportError: cannot import name 'evaluate_rule'`

- [ ] **Step 3: Rewrite src/core/playlist.py**

Replace the entire file:

```python
from __future__ import annotations

import random as _random
import time
from dataclasses import dataclass
from pathlib import Path

from src.core.models import RuleGroup, SimpleRule, SmartPlaylist, Track


# ---------------------------------------------------------------------------
# Field registry
# ---------------------------------------------------------------------------

@dataclass
class FieldDef:
    label: str
    type: str  # "string" | "number" | "boolean" | "date"


FIELD_REGISTRY: dict[str, FieldDef] = {
    "title":            FieldDef("Title",           "string"),
    "artist":           FieldDef("Artist",          "string"),
    "album":            FieldDef("Album",           "string"),
    "album_artist":     FieldDef("Album Artist",    "string"),
    "genre":            FieldDef("Genre",           "string"),
    "bucket":           FieldDef("Bucket",          "string"),
    "key":              FieldDef("Key",             "string"),
    "bpm":              FieldDef("BPM",             "number"),
    "year":             FieldDef("Year",            "number"),
    "track_number":     FieldDef("Track #",         "number"),
    "bitrate":          FieldDef("Bitrate",         "number"),
    "duration":         FieldDef("Duration (s)",    "number"),
    "tag_completeness": FieldDef("Tag Completeness","number"),
    "has_artwork":      FieldDef("Has Artwork",     "boolean"),
    "date_added":       FieldDef("Date Added",      "date"),
}

OPERATORS_BY_TYPE: dict[str, list[str]] = {
    "string":  ["contains", "does_not_contain", "is", "is_not", "starts_with", "ends_with"],
    "number":  ["is", "is_not", "gt", "lt", "gte", "lte", "in_range"],
    "boolean": ["is_true", "is_false"],
    "date":    ["is", "before", "after", "in_last_days"],
}

OPERATOR_LABELS: dict[str, str] = {
    "contains": "contains",
    "does_not_contain": "does not contain",
    "is": "is",
    "is_not": "is not",
    "starts_with": "starts with",
    "ends_with": "ends with",
    "gt": ">",
    "lt": "<",
    "gte": "≥",
    "lte": "≤",
    "in_range": "in range",
    "is_true": "is true",
    "is_false": "is false",
    "before": "before",
    "after": "after",
    "in_last_days": "in last N days",
}


# ---------------------------------------------------------------------------
# Operator evaluation
# ---------------------------------------------------------------------------

def _apply_operator(field_val, operator: str, value) -> bool:
    if operator == "contains":
        return str(value).lower() in str(field_val).lower()
    if operator == "does_not_contain":
        return str(value).lower() not in str(field_val).lower()
    if operator == "is":
        try:
            return float(field_val) == float(value)
        except (TypeError, ValueError):
            return str(field_val) == str(value)
    if operator == "is_not":
        try:
            return float(field_val) != float(value)
        except (TypeError, ValueError):
            return str(field_val) != str(value)
    if operator == "starts_with":
        return str(field_val).lower().startswith(str(value).lower())
    if operator == "ends_with":
        return str(field_val).lower().endswith(str(value).lower())
    if operator == "gt":
        return float(field_val) > float(value)
    if operator == "lt":
        return float(field_val) < float(value)
    if operator == "gte":
        return float(field_val) >= float(value)
    if operator == "lte":
        return float(field_val) <= float(value)
    if operator == "in_range":
        lo, hi = value
        return float(lo) <= float(field_val) <= float(hi)
    if operator == "is_true":
        return bool(field_val)
    if operator == "is_false":
        return not bool(field_val)
    if operator == "before":
        return float(field_val) < float(value)
    if operator == "after":
        return float(field_val) > float(value)
    if operator == "in_last_days":
        cutoff = time.time() - int(value) * 86400
        return float(field_val) >= cutoff
    return False


# ---------------------------------------------------------------------------
# Rule evaluation
# ---------------------------------------------------------------------------

def evaluate_rule(rule: SimpleRule | RuleGroup, track: Track) -> bool:
    """Evaluate a single rule or rule group against a track."""
    if isinstance(rule, RuleGroup):
        results = [evaluate_rule(r, track) for r in rule.rules]
        return all(results) if rule.conjunction == "AND" else any(results)
    # SimpleRule
    field_val = getattr(track, rule.field, None)
    if field_val is None:
        return False
    return _apply_operator(field_val, rule.operator, rule.value)


def _evaluate_top(playlist: SmartPlaylist, track: Track) -> bool:
    if not playlist.rules:
        return True
    results = [evaluate_rule(r, track) for r in playlist.rules]
    return all(results) if playlist.conjunction == "AND" else any(results)


def _apply_limit(tracks: list[Track], count: int, order: str | None) -> list[Track]:
    if order == "random":
        return _random.sample(tracks, min(count, len(tracks)))
    if order:
        tracks = sorted(
            tracks,
            key=lambda t: (getattr(t, order) is None, getattr(t, order, None) or 0),
        )
    return tracks[:count]


def evaluate_playlist(playlist: SmartPlaylist, tracks: list[Track]) -> list[Track]:
    """Return tracks matching the playlist rules, with sort and limit applied."""
    matching = [t for t in tracks if _evaluate_top(playlist, t)]
    if playlist.sort_by:
        matching.sort(
            key=lambda t: (
                getattr(t, playlist.sort_by) is None,
                getattr(t, playlist.sort_by, None) or 0,
            )
        )
    if playlist.limit_count:
        matching = _apply_limit(matching, playlist.limit_count, playlist.limit_order)
    return matching


# ---------------------------------------------------------------------------
# File generation (unchanged)
# ---------------------------------------------------------------------------

def generate_m3u(tracks: list[Track], output_path: Path) -> None:
    lines = ["#EXTM3U"]
    for track in tracks:
        duration = int(track.duration)
        artist = track.artist or "Unknown"
        title = track.title or track.file_path.stem
        lines.append(f"#EXTINF:{duration},{artist} - {title}")
        lines.append(str(track.file_path))
    output_path.write_text("\n".join(lines) + "\n")


def generate_pls(tracks: list[Track], output_path: Path) -> None:
    lines = ["[playlist]"]
    for i, track in enumerate(tracks, 1):
        lines.append(f"File{i}={track.file_path}")
        lines.append(f"Title{i}={track.title or track.file_path.stem}")
        lines.append(f"Length{i}={int(track.duration)}")
    lines.append(f"NumberOfEntries={len(tracks)}")
    lines.append("Version=2")
    output_path.write_text("\n".join(lines) + "\n")
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/core/test_playlist.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Run full suite**

```bash
pytest
```

Expected: all tests pass. (`PlaylistDefinition` is still in `models.py` so `database.py` and `playlist_manager.py` still import cleanly.)

- [ ] **Step 6: Commit**

```bash
git add src/core/playlist.py tests/core/test_playlist.py
git commit -m "feat: rewrite playlist.py with field registry, evaluate_rule, evaluate_playlist"
```

---

## Task 3: Database — date_added column, smart_playlists table, new CRUD

**Files:**
- Modify: `src/core/database.py`
- Modify: `tests/core/test_database.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/core/test_database.py` (keep all existing tests, but also replace the old playlist tests at the bottom):

First, remove these three test functions from the file (they reference `PlaylistDefinition`):
- `test_upsert_and_get_playlist`
- `test_delete_playlist`
- `test_upsert_playlist_updates_existing`

Then append new tests:

```python
import time as _time
from src.core.models import SmartPlaylist, SimpleRule, RuleGroup


def test_date_added_set_on_first_upsert(tmp_path):
    db = Database(tmp_path / "lib.db")
    track = _make_track()
    before = _time.time()
    db.upsert_track(track, file_mtime=1000.0)
    after = _time.time()
    row = db._conn.execute(
        "SELECT date_added FROM tracks WHERE file_path = ?",
        (str(track.file_path),),
    ).fetchone()
    assert row is not None
    assert before <= row["date_added"] <= after


def test_date_added_not_overwritten_on_re_upsert(tmp_path):
    db = Database(tmp_path / "lib.db")
    track = _make_track()
    db.upsert_track(track, file_mtime=1000.0)
    row1 = db._conn.execute(
        "SELECT date_added FROM tracks WHERE file_path = ?",
        (str(track.file_path),),
    ).fetchone()
    original = row1["date_added"]
    _time.sleep(0.02)
    db.upsert_track(track, file_mtime=2000.0)
    row2 = db._conn.execute(
        "SELECT date_added FROM tracks WHERE file_path = ?",
        (str(track.file_path),),
    ).fetchone()
    assert row2["date_added"] == original


def test_upsert_and_get_smart_playlist(tmp_path):
    db = Database(tmp_path / "lib.db")
    playlist = SmartPlaylist(
        name="Jazz Night",
        conjunction="AND",
        rules=[
            SimpleRule(field="genre", operator="contains", value="Jazz"),
            RuleGroup(
                conjunction="OR",
                rules=[
                    SimpleRule(field="bpm", operator="gt", value=90),
                    SimpleRule(field="bpm", operator="lt", value=70),
                ],
            ),
        ],
        limit_count=50,
        limit_order="random",
        sort_by="bpm",
        folder="DJ/Sets",
        format="m3u",
        show_in_sidebar=True,
    )
    db.upsert_smart_playlist(playlist)
    playlists = db.get_all_smart_playlists()
    assert len(playlists) == 1
    p = playlists[0]
    assert p.name == "Jazz Night"
    assert p.conjunction == "AND"
    assert len(p.rules) == 2
    assert isinstance(p.rules[0], SimpleRule)
    assert p.rules[0].field == "genre"
    assert isinstance(p.rules[1], RuleGroup)
    assert p.rules[1].conjunction == "OR"
    assert len(p.rules[1].rules) == 2
    assert p.limit_count == 50
    assert p.limit_order == "random"
    assert p.sort_by == "bpm"
    assert p.folder == "DJ/Sets"
    assert p.show_in_sidebar is True


def test_upsert_smart_playlist_updates_existing(tmp_path):
    db = Database(tmp_path / "lib.db")
    db.upsert_smart_playlist(SmartPlaylist(name="Set A", rules=[
        SimpleRule(field="genre", operator="is", value="House"),
    ]))
    db.upsert_smart_playlist(SmartPlaylist(name="Set A", rules=[
        SimpleRule(field="genre", operator="is", value="Techno"),
    ]))
    playlists = db.get_all_smart_playlists()
    assert len(playlists) == 1
    assert isinstance(playlists[0].rules[0], SimpleRule)
    assert playlists[0].rules[0].value == "Techno"


def test_delete_smart_playlist(tmp_path):
    db = Database(tmp_path / "lib.db")
    db.upsert_smart_playlist(SmartPlaylist(name="Gone", rules=[]))
    db.delete_smart_playlist("Gone")
    assert db.get_all_smart_playlists() == []
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/core/test_database.py -v -k "date_added or smart_playlist"
```

Expected: FAIL — `AttributeError: 'Database' object has no attribute 'upsert_smart_playlist'`

- [ ] **Step 3: Update src/core/database.py**

**3a.** Add `import time` at the top of the file (after existing imports).

**3b.** Add `date_added REAL` to `_CREATE_TRACKS`:

```python
_CREATE_TRACKS = """
CREATE TABLE IF NOT EXISTS tracks (
    file_path      TEXT PRIMARY KEY,
    file_size      INTEGER NOT NULL,
    bitrate        INTEGER NOT NULL,
    duration       REAL NOT NULL,
    title          TEXT,
    artist         TEXT,
    album_artist   TEXT,
    album          TEXT,
    track_number   INTEGER,
    disc_number    INTEGER,
    year           INTEGER,
    genre          TEXT,
    bpm            REAL,
    key_           TEXT,
    bucket         TEXT,
    fingerprint    TEXT,
    tag_completeness REAL NOT NULL DEFAULT 0.0,
    tag_source     TEXT,
    has_artwork    INTEGER NOT NULL DEFAULT 0,
    file_mtime     REAL NOT NULL DEFAULT 0.0,
    date_added     REAL
)
"""
```

**3c.** Add the `_CREATE_SMART_PLAYLISTS` constant (replace `_CREATE_PLAYLISTS`):

```python
_CREATE_SMART_PLAYLISTS = """
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
"""
```

**3d.** Update `_row_to_track` to include `date_added`:

```python
def _row_to_track(row: sqlite3.Row) -> Track:
    return Track(
        file_path=Path(row["file_path"]),
        file_size=row["file_size"],
        bitrate=row["bitrate"],
        duration=row["duration"],
        title=row["title"],
        artist=row["artist"],
        album_artist=row["album_artist"],
        album=row["album"],
        track_number=row["track_number"],
        disc_number=row["disc_number"],
        year=row["year"],
        genre=row["genre"],
        bpm=row["bpm"],
        key=row["key_"],
        bucket=row["bucket"],
        fingerprint=row["fingerprint"],
        tag_completeness=row["tag_completeness"],
        tag_source=row["tag_source"],
        has_artwork=bool(row["has_artwork"]),
        date_added=row["date_added"],
    )
```

**3e.** Update `_setup_schema` — replace `cur.execute(_CREATE_PLAYLISTS)` with migrations and new table creation:

```python
    def _setup_schema(self) -> None:
        cur = self._conn
        cur.execute(_CREATE_TRACKS)
        cur.execute(_CREATE_HISTORY)
        cur.execute(_CREATE_SMART_PLAYLISTS)
        # Migrate: add date_added to existing tracks tables
        try:
            cur.execute("ALTER TABLE tracks ADD COLUMN date_added REAL")
        except sqlite3.OperationalError:
            pass  # column already exists
        # Migrate: drop old simple playlists table
        cur.execute("DROP TABLE IF EXISTS playlists")
        self._fts_available = False
        try:
            cur.execute(_CREATE_FTS)
            self._fts_available = True
        except sqlite3.OperationalError:
            pass
        self._conn.commit()
```

**3f.** Update `upsert_track` to include `date_added` in the INSERT but NOT in the ON CONFLICT UPDATE. Add `"date_added"` to the INSERT columns/values and add it to `params`. Do NOT add it to the `DO UPDATE SET` clause:

In the SQL string, add `, date_added` to the INSERT column list and `, :date_added` to the VALUES list. Leave the `ON CONFLICT DO UPDATE SET` block unchanged (no `date_added` entry there).

In the params dict, add:
```python
"date_added": track.date_added if track.date_added is not None else time.time(),
```

The full updated SQL:

```python
    sql = """
    INSERT INTO tracks (
        file_path, file_size, bitrate, duration,
        title, artist, album_artist, album,
        track_number, disc_number, year, genre,
        bpm, key_, bucket, fingerprint,
        tag_completeness, tag_source, has_artwork, file_mtime,
        date_added
    ) VALUES (
        :file_path, :file_size, :bitrate, :duration,
        :title, :artist, :album_artist, :album,
        :track_number, :disc_number, :year, :genre,
        :bpm, :key_, :bucket, :fingerprint,
        :tag_completeness, :tag_source, :has_artwork, :file_mtime,
        :date_added
    )
    ON CONFLICT(file_path) DO UPDATE SET
        file_size        = excluded.file_size,
        bitrate          = excluded.bitrate,
        duration         = excluded.duration,
        title            = excluded.title,
        artist           = excluded.artist,
        album_artist     = excluded.album_artist,
        album            = excluded.album,
        track_number     = excluded.track_number,
        disc_number      = excluded.disc_number,
        year             = excluded.year,
        genre            = excluded.genre,
        bpm              = excluded.bpm,
        key_             = excluded.key_,
        bucket           = excluded.bucket,
        fingerprint      = excluded.fingerprint,
        tag_completeness = excluded.tag_completeness,
        tag_source       = excluded.tag_source,
        has_artwork      = excluded.has_artwork,
        file_mtime       = excluded.file_mtime
    """
    params = {
        "file_path": str(track.file_path),
        "file_size": track.file_size,
        "bitrate": track.bitrate,
        "duration": track.duration,
        "title": track.title,
        "artist": track.artist,
        "album_artist": track.album_artist,
        "album": track.album,
        "track_number": track.track_number,
        "disc_number": track.disc_number,
        "year": track.year,
        "genre": track.genre,
        "bpm": track.bpm,
        "key_": track.key,
        "bucket": track.bucket,
        "fingerprint": track.fingerprint,
        "tag_completeness": track.tag_completeness,
        "tag_source": track.tag_source,
        "has_artwork": int(track.has_artwork),
        "file_mtime": file_mtime,
        "date_added": track.date_added if track.date_added is not None else time.time(),
    }
```

**3g.** Add serialization helpers and new CRUD methods. Add these private functions at module level (after `_row_to_track`):

```python
def _serialize_rule(rule) -> dict:
    if isinstance(rule, SimpleRule):
        return {"type": "simple", "field": rule.field,
                "operator": rule.operator, "value": rule.value}
    if isinstance(rule, RuleGroup):
        return {"type": "group", "conjunction": rule.conjunction,
                "rules": [_serialize_rule(r) for r in rule.rules]}
    raise ValueError(f"Unknown rule type: {type(rule)}")


def _deserialize_rule(d: dict):
    if d["type"] == "simple":
        return SimpleRule(field=d["field"], operator=d["operator"], value=d["value"])
    if d["type"] == "group":
        return RuleGroup(
            conjunction=d["conjunction"],
            rules=[_deserialize_rule(r) for r in d["rules"]],
        )
    raise ValueError(f"Unknown rule type in JSON: {d['type']}")
```

And update the import at the top of `database.py`:

```python
from src.core.models import Track, PlaylistDefinition, SimpleRule, RuleGroup, SmartPlaylist
```

**3h.** Replace the old Playlist CRUD section with new SmartPlaylist CRUD:

```python
    # ------------------------------------------------------------------
    # SmartPlaylist CRUD
    # ------------------------------------------------------------------

    def get_all_smart_playlists(self) -> list[SmartPlaylist]:
        rows = self._conn.execute(
            "SELECT name, folder, format, conjunction, rules, "
            "limit_count, limit_order, sort_by, show_in_sidebar "
            "FROM smart_playlists"
        ).fetchall()
        result = []
        for row in rows:
            raw = json.loads(row["rules"]) if row["rules"] else []
            rules = [_deserialize_rule(r) for r in raw]
            result.append(SmartPlaylist(
                name=row["name"],
                folder=row["folder"],
                format=row["format"] or "m3u",
                conjunction=row["conjunction"] or "AND",
                rules=rules,
                limit_count=row["limit_count"],
                limit_order=row["limit_order"],
                sort_by=row["sort_by"],
                show_in_sidebar=bool(row["show_in_sidebar"]),
            ))
        return result

    def upsert_smart_playlist(self, playlist: SmartPlaylist) -> None:
        rules_json = json.dumps([_serialize_rule(r) for r in playlist.rules])
        with self._lock:
            self._conn.execute(
                """INSERT INTO smart_playlists
                   (name, folder, format, conjunction, rules,
                    limit_count, limit_order, sort_by, show_in_sidebar)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(name) DO UPDATE SET
                       folder          = excluded.folder,
                       format          = excluded.format,
                       conjunction     = excluded.conjunction,
                       rules           = excluded.rules,
                       limit_count     = excluded.limit_count,
                       limit_order     = excluded.limit_order,
                       sort_by         = excluded.sort_by,
                       show_in_sidebar = excluded.show_in_sidebar""",
                (
                    playlist.name, playlist.folder, playlist.format,
                    playlist.conjunction, rules_json,
                    playlist.limit_count, playlist.limit_order,
                    playlist.sort_by, int(playlist.show_in_sidebar),
                ),
            )
            self._conn.commit()

    def delete_smart_playlist(self, name: str) -> None:
        with self._lock:
            self._conn.execute(
                "DELETE FROM smart_playlists WHERE name = ?", (name,)
            )
            self._conn.commit()
```

Keep the old `get_all_playlists`, `upsert_playlist`, `delete_playlist` methods for now — they are still referenced by `playlist_manager.py`. They will be removed in Task 4.

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/core/test_database.py -v
```

Expected: all tests PASS (old `PlaylistDefinition` tests were removed; new smart playlist tests pass).

- [ ] **Step 5: Run full suite**

```bash
pytest
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/core/database.py tests/core/test_database.py
git commit -m "feat: add smart_playlists table, date_added column, SmartPlaylist CRUD"
```

---

## Task 4: Rewrite PlaylistManager GUI

**Files:**
- Rewrite: `src/gui/playlist_manager.py`
- Modify: `src/core/models.py` (remove `PlaylistDefinition`)
- Modify: `src/core/database.py` (remove old CRUD + `PlaylistDefinition` import)

No unit tests for GUI. Manual verification at the end.

- [ ] **Step 1: Remove PlaylistDefinition from models.py**

Delete the `PlaylistDefinition` dataclass entirely from `src/core/models.py`.

- [ ] **Step 2: Clean up database.py**

In `src/core/database.py`:
- Remove `PlaylistDefinition` from the import line: `from src.core.models import Track, SimpleRule, RuleGroup, SmartPlaylist`
- Delete the old `get_all_playlists`, `upsert_playlist`, and `delete_playlist` methods

- [ ] **Step 3: Rewrite src/gui/playlist_manager.py**

Replace the entire file:

```python
from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QTreeWidget, QTreeWidgetItem, QPushButton, QLabel,
    QLineEdit, QComboBox, QFormLayout, QGroupBox,
    QMenu, QInputDialog, QFileDialog, QMessageBox,
    QScrollArea, QSpinBox, QCheckBox,
)
from PySide6.QtCore import Qt, Signal

from src.core.models import SimpleRule, RuleGroup, SmartPlaylist, Track
from src.core.playlist import (
    evaluate_playlist, generate_m3u, generate_pls,
    FIELD_REGISTRY, OPERATORS_BY_TYPE, OPERATOR_LABELS,
)

import logging
logger = logging.getLogger(__name__)

_FIELD_KEYS = list(FIELD_REGISTRY.keys())
_FIELD_LABELS = [fd.label for fd in FIELD_REGISTRY.values()]

_LIMIT_ORDER_OPTIONS = ["(none)", "random", "bpm", "artist", "title", "date_added"]
_SORT_OPTIONS = ["(none)", "bpm", "artist", "title", "genre", "year", "bitrate", "date_added"]


class RuleRowWidget(QWidget):
    """A single rule row: field ▾ operator ▾ value [−]."""

    removed = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self._field_combo = QComboBox()
        self._field_combo.addItems(_FIELD_LABELS)
        self._field_combo.setFixedWidth(120)
        self._field_combo.currentIndexChanged.connect(self._on_field_changed)

        self._operator_combo = QComboBox()
        self._operator_combo.setFixedWidth(110)

        self._value_edit = QLineEdit()
        self._value_edit.setPlaceholderText("value")

        btn_remove = QPushButton("−")
        btn_remove.setFixedWidth(28)
        btn_remove.clicked.connect(lambda: self.removed.emit(self))

        layout.addWidget(self._field_combo)
        layout.addWidget(self._operator_combo)
        layout.addWidget(self._value_edit, stretch=1)
        layout.addWidget(btn_remove)

        self._on_field_changed(0)

    def _on_field_changed(self, _idx: int) -> None:
        field_key = _FIELD_KEYS[self._field_combo.currentIndex()]
        field_type = FIELD_REGISTRY[field_key].type
        operators = OPERATORS_BY_TYPE[field_type]
        self._operator_combo.blockSignals(True)
        self._operator_combo.clear()
        self._operator_combo.addItems(
            [OPERATOR_LABELS.get(op, op) for op in operators]
        )
        self._operator_combo.blockSignals(False)

    def _current_operator_key(self) -> str:
        field_key = _FIELD_KEYS[self._field_combo.currentIndex()]
        field_type = FIELD_REGISTRY[field_key].type
        operators = OPERATORS_BY_TYPE[field_type]
        idx = self._operator_combo.currentIndex()
        return operators[idx] if 0 <= idx < len(operators) else operators[0]

    def get_rule(self) -> SimpleRule:
        field_key = _FIELD_KEYS[self._field_combo.currentIndex()]
        operator = self._current_operator_key()
        field_type = FIELD_REGISTRY[field_key].type
        text = self._value_edit.text().strip()
        if field_type == "number":
            try:
                value: str | float | bool | None = float(text)
            except ValueError:
                value = 0.0
        elif field_type == "boolean":
            value = None  # operator encodes the bool (is_true / is_false)
        else:
            value = text
        return SimpleRule(field=field_key, operator=operator, value=value)

    def set_rule(self, rule: SimpleRule) -> None:
        if rule.field in _FIELD_KEYS:
            self._field_combo.setCurrentIndex(_FIELD_KEYS.index(rule.field))
        self._on_field_changed(0)
        field_type = FIELD_REGISTRY[rule.field].type
        operators = OPERATORS_BY_TYPE[field_type]
        if rule.operator in operators:
            self._operator_combo.setCurrentIndex(operators.index(rule.operator))
        if rule.value is not None:
            self._value_edit.setText(str(rule.value))


class RuleGroupWidget(QWidget):
    """A sub-group with its own conjunction and rule rows."""

    removed = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows: list[RuleRowWidget] = []
        self._build_ui()
        self._add_rule_row()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(4)
        self.setStyleSheet(
            "RuleGroupWidget { border: 1px solid #2a2a4a; border-radius: 6px; }"
        )

        header = QHBoxLayout()
        lbl = QLabel("Group:")
        lbl.setStyleSheet("color: #7c83ff; font-weight: bold;")
        header.addWidget(lbl)
        header.addWidget(QLabel("Match"))
        self._conjunction_combo = QComboBox()
        self._conjunction_combo.addItems(["ALL", "ANY"])
        self._conjunction_combo.setFixedWidth(65)
        header.addWidget(self._conjunction_combo)
        header.addWidget(QLabel("of:"))
        header.addStretch()
        btn_remove = QPushButton("Remove group")
        btn_remove.clicked.connect(lambda: self.removed.emit(self))
        header.addWidget(btn_remove)
        outer.addLayout(header)

        self._rules_layout = QVBoxLayout()
        self._rules_layout.setSpacing(4)
        outer.addLayout(self._rules_layout)

        btn_add = QPushButton("+ Add rule")
        btn_add.clicked.connect(self._add_rule_row)
        outer.addWidget(btn_add, alignment=Qt.AlignmentFlag.AlignLeft)

    def _add_rule_row(self) -> None:
        row = RuleRowWidget()
        row.removed.connect(self._remove_row)
        self._rows.append(row)
        self._rules_layout.addWidget(row)

    def _remove_row(self, row: RuleRowWidget) -> None:
        if len(self._rows) <= 1:
            return
        self._rows.remove(row)
        self._rules_layout.removeWidget(row)
        row.deleteLater()

    def get_group(self) -> RuleGroup:
        conjunction = "AND" if self._conjunction_combo.currentText() == "ALL" else "OR"
        return RuleGroup(conjunction=conjunction, rules=[r.get_rule() for r in self._rows])

    def set_group(self, group: RuleGroup) -> None:
        for row in list(self._rows):
            self._rules_layout.removeWidget(row)
            row.deleteLater()
        self._rows.clear()
        self._conjunction_combo.setCurrentText("ALL" if group.conjunction == "AND" else "ANY")
        for rule in group.rules:
            row = RuleRowWidget()
            row.removed.connect(self._remove_row)
            row.set_rule(rule)
            self._rows.append(row)
            self._rules_layout.addWidget(row)


class RuleBuilderWidget(QWidget):
    """Top-level rule builder: conjunction selector + list of rules/groups."""

    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._items: list[RuleRowWidget | RuleGroupWidget] = []
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        conj_row = QHBoxLayout()
        conj_row.addWidget(QLabel("Match"))
        self._conjunction_combo = QComboBox()
        self._conjunction_combo.addItems(["ALL", "ANY"])
        self._conjunction_combo.setFixedWidth(65)
        self._conjunction_combo.currentIndexChanged.connect(self.changed)
        conj_row.addWidget(self._conjunction_combo)
        conj_row.addWidget(QLabel("of the following rules:"))
        conj_row.addStretch()
        layout.addLayout(conj_row)

        scroll_content = QWidget()
        self._rules_layout = QVBoxLayout(scroll_content)
        self._rules_layout.setSpacing(4)
        self._rules_layout.setContentsMargins(0, 0, 0, 0)
        self._rules_layout.addStretch()

        scroll = QScrollArea()
        scroll.setWidget(scroll_content)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        layout.addWidget(scroll, stretch=1)

        btn_row = QHBoxLayout()
        btn_add_rule = QPushButton("+ Add Rule")
        btn_add_rule.clicked.connect(self._add_rule_row)
        btn_add_group = QPushButton("+ Add Group")
        btn_add_group.clicked.connect(self._add_group)
        btn_row.addWidget(btn_add_rule)
        btn_row.addWidget(btn_add_group)
        btn_row.addStretch()
        layout.addLayout(btn_row)

    def _add_rule_row(self) -> None:
        row = RuleRowWidget()
        row.removed.connect(self._remove_item)
        self._items.append(row)
        # Insert before the stretch at end
        self._rules_layout.insertWidget(self._rules_layout.count() - 1, row)
        self.changed.emit()

    def _add_group(self) -> None:
        group = RuleGroupWidget()
        group.removed.connect(self._remove_item)
        self._items.append(group)
        self._rules_layout.insertWidget(self._rules_layout.count() - 1, group)
        self.changed.emit()

    def _remove_item(self, item) -> None:
        self._items.remove(item)
        self._rules_layout.removeWidget(item)
        item.deleteLater()
        self.changed.emit()

    def get_rules(self) -> tuple[str, list]:
        conjunction = "AND" if self._conjunction_combo.currentText() == "ALL" else "OR"
        rules = []
        for item in self._items:
            if isinstance(item, RuleRowWidget):
                rules.append(item.get_rule())
            else:
                rules.append(item.get_group())
        return conjunction, rules

    def load_rules(self, conjunction: str, rules: list) -> None:
        for item in list(self._items):
            self._rules_layout.removeWidget(item)
            item.deleteLater()
        self._items.clear()
        self._conjunction_combo.setCurrentText("ALL" if conjunction == "AND" else "ANY")
        for rule in rules:
            if isinstance(rule, SimpleRule):
                row = RuleRowWidget()
                row.removed.connect(self._remove_item)
                row.set_rule(rule)
                self._items.append(row)
                self._rules_layout.insertWidget(self._rules_layout.count() - 1, row)
            elif isinstance(rule, RuleGroup):
                group = RuleGroupWidget()
                group.removed.connect(self._remove_item)
                group.set_group(rule)
                self._items.append(group)
                self._rules_layout.insertWidget(self._rules_layout.count() - 1, group)


class PlaylistManager(QWidget):
    """Playlist tree with folder support and a smart rule builder editor."""

    show_tracks_requested = Signal(list)

    def __init__(self, db, all_tracks: list[Track] | None = None, parent=None):
        super().__init__(parent)
        self._db = db
        self._all_tracks: list[Track] = all_tracks or []
        self._playlists: list[SmartPlaylist] = []
        self._current: SmartPlaylist | None = None
        self._build_ui()
        self._load_playlists()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_tracks(self, tracks: list[Track]) -> None:
        self._all_tracks = tracks
        self._update_count()

    def playlist_count(self) -> int:
        def _count(item: QTreeWidgetItem) -> int:
            if item.data(0, Qt.ItemDataRole.UserRole) is not None:
                return 1
            return sum(_count(item.child(i)) for i in range(item.childCount()))
        root = self._tree.invisibleRootItem()
        return sum(_count(root.child(i)) for i in range(root.childCount()))

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        splitter = QSplitter(Qt.Orientation.Horizontal)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(splitter)

        # Left: tree
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(8, 8, 4, 8)

        tree_toolbar = QHBoxLayout()
        btn_new = QPushButton("+ Playlist")
        btn_new.clicked.connect(self._new_playlist)
        btn_folder = QPushButton("+ Folder")
        btn_folder.clicked.connect(self._new_folder)
        btn_regen = QPushButton("Re-generate All")
        btn_regen.clicked.connect(self._regenerate_all)
        tree_toolbar.addWidget(btn_new)
        tree_toolbar.addWidget(btn_folder)
        tree_toolbar.addStretch()
        tree_toolbar.addWidget(btn_regen)
        left_layout.addLayout(tree_toolbar)

        self._tree = QTreeWidget()
        self._tree.setHeaderHidden(True)
        self._tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._tree.customContextMenuRequested.connect(self._on_context_menu)
        self._tree.currentItemChanged.connect(self._on_item_selected)
        self._tree.setDragDropMode(QTreeWidget.DragDropMode.InternalMove)
        left_layout.addWidget(self._tree, stretch=1)
        splitter.addWidget(left)

        # Right: editor
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(4, 8, 8, 8)

        self._editor_group = QGroupBox("Playlist Editor")
        editor_layout = QVBoxLayout(self._editor_group)

        form = QFormLayout()
        self._name_edit = QLineEdit()
        self._folder_edit = QLineEdit()
        self._folder_edit.setPlaceholderText("e.g. DJ/Sets")
        self._format_combo = QComboBox()
        self._format_combo.addItems(["m3u", "pls"])
        self._sort_combo = QComboBox()
        self._sort_combo.addItems(_SORT_OPTIONS)
        limit_row = QHBoxLayout()
        self._limit_spin = QSpinBox()
        self._limit_spin.setRange(0, 9999)
        self._limit_spin.setSpecialValueText("unlimited")
        self._limit_spin.setFixedWidth(80)
        self._limit_order_combo = QComboBox()
        self._limit_order_combo.addItems(_LIMIT_ORDER_OPTIONS)
        limit_row.addWidget(self._limit_spin)
        limit_row.addWidget(QLabel("tracks, by"))
        limit_row.addWidget(self._limit_order_combo)
        limit_row.addStretch()
        self._sidebar_check = QCheckBox("Show in sidebar")
        self._sidebar_check.setChecked(True)
        form.addRow("Name:", self._name_edit)
        form.addRow("Folder:", self._folder_edit)
        form.addRow("Format:", self._format_combo)
        form.addRow("Sort by:", self._sort_combo)
        form.addRow("Limit:", limit_row)
        form.addRow("", self._sidebar_check)
        editor_layout.addLayout(form)

        editor_layout.addWidget(QLabel("Rules:"))
        self._rule_builder = RuleBuilderWidget()
        self._rule_builder.changed.connect(self._update_count)
        editor_layout.addWidget(self._rule_builder, stretch=1)

        right_layout.addWidget(self._editor_group, stretch=1)

        btn_row = QHBoxLayout()
        self._save_btn = QPushButton("Save")
        self._save_btn.clicked.connect(self._save_current)
        self._generate_btn = QPushButton("Generate File…")
        self._generate_btn.clicked.connect(self._generate_current)
        btn_row.addWidget(self._save_btn)
        btn_row.addWidget(self._generate_btn)
        btn_row.addStretch()
        right_layout.addLayout(btn_row)

        self._track_count_label = QLabel("")
        right_layout.addWidget(self._track_count_label)
        splitter.addWidget(right)
        splitter.setSizes([300, 500])

        self._editor_group.setEnabled(False)

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def _load_playlists(self) -> None:
        self._playlists = self._db.get_all_smart_playlists()
        self._populate_tree(self._playlists)

    def _populate_tree(self, playlists: list[SmartPlaylist]) -> None:
        self._tree.clear()
        folders: dict[str, QTreeWidgetItem] = {}
        for pld in playlists:
            folder = pld.folder or ""
            if folder and folder not in folders:
                folder_item = QTreeWidgetItem(self._tree)
                folder_item.setText(0, folder)
                folder_item.setData(0, Qt.ItemDataRole.UserRole, None)
                folder_item.setExpanded(True)
                folders[folder] = folder_item
            parent = folders.get(folder, self._tree.invisibleRootItem())
            item = QTreeWidgetItem(parent if folder else self._tree)
            item.setText(0, pld.name)
            item.setData(0, Qt.ItemDataRole.UserRole, pld)

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_item_selected(self, current: QTreeWidgetItem | None, _prev) -> None:
        if current is None:
            self._editor_group.setEnabled(False)
            return
        pld = current.data(0, Qt.ItemDataRole.UserRole)
        if pld is None:
            self._editor_group.setEnabled(False)
            return
        self._current = pld
        self._name_edit.setText(pld.name)
        self._folder_edit.setText(pld.folder or "")
        self._format_combo.setCurrentText(pld.format)
        sort = pld.sort_by or "(none)"
        idx = self._sort_combo.findText(sort)
        self._sort_combo.setCurrentIndex(max(idx, 0))
        self._limit_spin.setValue(pld.limit_count or 0)
        order = pld.limit_order or "(none)"
        idx = self._limit_order_combo.findText(order)
        self._limit_order_combo.setCurrentIndex(max(idx, 0))
        self._sidebar_check.setChecked(pld.show_in_sidebar)
        self._rule_builder.load_rules(pld.conjunction, pld.rules)
        self._editor_group.setEnabled(True)
        self._update_count()

    def _on_context_menu(self, pos) -> None:
        item = self._tree.itemAt(pos)
        menu = QMenu(self)
        if item:
            pld = item.data(0, Qt.ItemDataRole.UserRole)
            if pld is not None:
                menu.addAction("Rename", lambda: self._rename_playlist(item, pld))
                menu.addAction("Delete", lambda: self._delete_playlist(pld))
        menu.addAction("New Playlist", self._new_playlist)
        menu.addAction("New Folder", self._new_folder)
        menu.exec(self._tree.mapToGlobal(pos))

    def _update_count(self) -> None:
        if self._current is None:
            return
        # Build a temporary playlist from current builder state for live count
        conjunction, rules = self._rule_builder.get_rules()
        temp = SmartPlaylist(name="", conjunction=conjunction, rules=rules)
        count = len(evaluate_playlist(temp, self._all_tracks))
        self._track_count_label.setText(f"{count} matching tracks")

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def _new_playlist(self) -> None:
        name, ok = QInputDialog.getText(self, "New Playlist", "Playlist name:")
        if ok and name.strip():
            pld = SmartPlaylist(name=name.strip())
            self._db.upsert_smart_playlist(pld)
            self._load_playlists()

    def _new_folder(self) -> None:
        name, ok = QInputDialog.getText(self, "New Folder", "Folder name:")
        if ok and name.strip():
            folder_item = QTreeWidgetItem(self._tree)
            folder_item.setText(0, name.strip())
            folder_item.setData(0, Qt.ItemDataRole.UserRole, None)
            folder_item.setExpanded(True)

    def _rename_playlist(self, item: QTreeWidgetItem, pld: SmartPlaylist) -> None:
        new_name, ok = QInputDialog.getText(self, "Rename", "New name:", text=pld.name)
        if ok and new_name.strip():
            self._db.delete_smart_playlist(pld.name)
            pld.name = new_name.strip()
            self._db.upsert_smart_playlist(pld)
            self._load_playlists()

    def _delete_playlist(self, pld: SmartPlaylist) -> None:
        result = QMessageBox.question(
            self, "Delete Playlist", f"Delete playlist '{pld.name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if result == QMessageBox.StandardButton.Yes:
            self._db.delete_smart_playlist(pld.name)
            self._load_playlists()

    def _save_current(self) -> None:
        if self._current is None:
            return
        old_name = self._current.name
        self._current.name = self._name_edit.text().strip() or old_name
        self._current.folder = self._folder_edit.text().strip() or None
        self._current.format = self._format_combo.currentText()
        sort = self._sort_combo.currentText()
        self._current.sort_by = None if sort == "(none)" else sort
        limit_val = self._limit_spin.value()
        self._current.limit_count = limit_val if limit_val > 0 else None
        order = self._limit_order_combo.currentText()
        self._current.limit_order = None if order == "(none)" else order
        self._current.show_in_sidebar = self._sidebar_check.isChecked()
        conjunction, rules = self._rule_builder.get_rules()
        self._current.conjunction = conjunction
        self._current.rules = rules
        if old_name != self._current.name:
            self._db.delete_smart_playlist(old_name)
        self._db.upsert_smart_playlist(self._current)
        self._load_playlists()

    def _generate_current(self) -> None:
        if self._current is None:
            return
        matching = evaluate_playlist(self._current, self._all_tracks)
        if not matching:
            QMessageBox.information(self, "Generate", "No tracks match the current rules.")
            return
        fmt = self._current.format
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Playlist", self._current.name,
            f"Playlist files (*.{fmt})"
        )
        if path:
            output = Path(path)
            generate_m3u(matching, output) if fmt == "m3u" else generate_pls(matching, output)
            QMessageBox.information(self, "Done", f"Saved {len(matching)} tracks to {output.name}")

    def _regenerate_all(self) -> None:
        count = 0
        skipped = 0
        for pld in self._playlists:
            if not pld.folder:
                skipped += 1
                continue
            matching = evaluate_playlist(pld, self._all_tracks)
            folder_path = Path(pld.folder)
            if not folder_path.is_absolute():
                folder_path = Path.home() / folder_path
            output = folder_path / f"{pld.name}.{pld.format}"
            output.parent.mkdir(parents=True, exist_ok=True)
            generate_m3u(matching, output) if pld.format == "m3u" else generate_pls(matching, output)
            count += 1
        msg = f"Updated {count} playlist(s)."
        if skipped:
            msg += f" {skipped} skipped (no folder set)."
        QMessageBox.information(self, "Re-generate All", msg)
```

- [ ] **Step 4: Run full test suite**

```bash
pytest
```

Expected: all tests pass.

- [ ] **Step 5: Manual verification**

```bash
music-sorter
```

Go to Playlists page. Verify:
- "+ Playlist" creates a new playlist and it appears in the tree
- Selecting a playlist shows the rule builder editor with name, folder, format, sort, limit, sidebar checkbox, and rule area
- "Add Rule" adds a row; field dropdown changes operator options dynamically
- "Add Group" adds a nested group with its own conjunction
- The "−" button removes a rule row; "Remove group" removes a group
- "Save" persists the playlist (reload app to verify it loads back)
- "Generate File…" produces a .m3u or .pls file

- [ ] **Step 6: Commit**

```bash
git add src/core/models.py src/core/database.py src/gui/playlist_manager.py
git commit -m "feat: rewrite PlaylistManager with smart rule builder UI"
```

---

## Task 5: Add Playlists section to the sidebar

**Files:**
- Modify: `src/gui/main_window.py`

No unit tests. Manual verification.

- [ ] **Step 1: Add imports to main_window.py**

Add to the existing imports at the top of `src/gui/main_window.py`:

```python
from src.core.playlist import evaluate_playlist
from src.core.models import SmartPlaylist
```

- [ ] **Step 2: Add instance variables in __init__**

In `MainWindow.__init__`, after `self._artwork_worker: ArtworkWorker | None = None`, add:

```python
        self._smart_playlists: list[SmartPlaylist] = []
        self._playlist_sidebar_items: dict[str, QTreeWidgetItem] = {}
```

- [ ] **Step 3: Add the Playlists section to _build_sidebar**

In `_build_sidebar`, after the `layout.addWidget(self._task_tree)` line and before `layout.addStretch()`, add:

```python
        # ---- Playlists section ----
        self._playlists_section_lbl = QLabel("Playlists")
        self._playlists_section_lbl.setStyleSheet("margin-top: 11px; " + _section_style)
        self._playlists_section_lbl.setVisible(False)
        layout.addWidget(self._playlists_section_lbl)

        self._playlists_tree = QTreeWidget()
        self._playlists_tree.setHeaderHidden(True)
        self._playlists_tree.setRootIsDecorated(False)
        self._playlists_tree.setIndentation(0)
        self._playlists_tree.setStyleSheet(_tree_style)
        self._playlists_tree.setVisible(False)
        self._playlists_tree.itemClicked.connect(self._on_sidebar_playlist_clicked)
        layout.addWidget(self._playlists_tree)
```

- [ ] **Step 4: Add _update_sidebar_playlists method**

Add this method to `MainWindow`, after `_update_sidebar_counts`:

```python
    def _update_sidebar_playlists(self, playlists: list[SmartPlaylist]) -> None:
        self._smart_playlists = playlists
        self._playlist_sidebar_items.clear()
        self._playlists_tree.clear()
        sidebar_playlists = [p for p in playlists if p.show_in_sidebar]
        visible = bool(sidebar_playlists)
        self._playlists_section_lbl.setVisible(visible)
        self._playlists_tree.setVisible(visible)
        for pld in sidebar_playlists:
            item = QTreeWidgetItem([f"▶ {pld.name}"])
            item.setData(0, Qt.ItemDataRole.UserRole, pld)
            self._playlists_tree.addTopLevelItem(item)
            self._playlist_sidebar_items[pld.name] = item
```

- [ ] **Step 5: Add _on_sidebar_playlist_clicked method**

```python
    def _on_sidebar_playlist_clicked(self, item: QTreeWidgetItem, _col: int) -> None:
        pld = item.data(0, Qt.ItemDataRole.UserRole)
        if pld is None:
            return
        matching = evaluate_playlist(pld, self._all_tracks)
        matching_paths = {t.file_path for t in matching}
        self._show_page(_PAGE_LIBRARY)
        self._library.filter_by_fn(lambda t: t.file_path in matching_paths)
```

- [ ] **Step 6: Wire _update_sidebar_playlists into _refresh_library**

In `_refresh_library`, after the existing `_update_sidebar_counts(...)` call, add:

```python
        self._update_sidebar_playlists(self._db.get_all_smart_playlists())
```

- [ ] **Step 7: Run full test suite**

```bash
pytest
```

Expected: all tests pass.

- [ ] **Step 8: Manual verification**

```bash
music-sorter
```

1. Create a playlist on the Playlists page, check "Show in sidebar", save it.
2. A "Playlists" section appears in the sidebar with the playlist name.
3. Clicking it navigates to the Library page, filtered to matching tracks.
4. Uncheck "Show in sidebar" on a playlist, save — it disappears from the sidebar.
5. If no playlists have sidebar enabled, the entire Playlists section hides.

- [ ] **Step 9: Commit**

```bash
git add src/gui/main_window.py
git commit -m "feat: add smart playlists section to sidebar with library filter"
```

---

## Self-Review

**Spec coverage:**
- ✅ SmartPlaylist replaces PlaylistDefinition — Task 1, 2, 3, 4
- ✅ Rule tree: SimpleRule, RuleGroup, one level deep — Tasks 1–2
- ✅ Field registry with string/number/boolean/date types — Task 2
- ✅ All operators per type — Task 2
- ✅ None field value returns False — Task 2 test
- ✅ `date_added` on Track and DB — Task 3
- ✅ `date_added` set once, not overwritten — Task 3 test
- ✅ DB: smart_playlists table, old playlists table dropped — Task 3
- ✅ Rule tree JSON serialization round-trip — Task 3 test
- ✅ limit_count + limit_order — Task 2 (evaluate_playlist)
- ✅ sort_by — Task 2
- ✅ PlaylistManager rule builder with dynamic rows and groups — Task 4
- ✅ show_in_sidebar checkbox in editor — Task 4
- ✅ Sidebar Playlists section — Task 5
- ✅ Clicking sidebar playlist filters Library — Task 5
- ✅ Sidebar section hidden when no sidebar playlists — Task 5

**Placeholder scan:** No TBDs or incomplete steps found.

**Type consistency:** `SmartPlaylist`, `SimpleRule`, `RuleGroup` are defined in Task 1 and used consistently throughout. `evaluate_playlist` signature is `(SmartPlaylist, list[Track]) -> list[Track]` and is called that way in Tasks 4 and 5. `get_all_smart_playlists` / `upsert_smart_playlist` / `delete_smart_playlist` defined in Task 3 and used in Task 4.
