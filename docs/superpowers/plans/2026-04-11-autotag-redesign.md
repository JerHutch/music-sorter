# Auto-Tag Redesign + Full Process Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign Auto-Tag to look up metadata via AcoustID/MusicBrainz with a conflict review page, simplify Analyze to BPM/key only, and add a Full Process button that runs all three workers at once.

**Architecture:** `TagConflict` model fields are renamed to be generic, then reused for both iTunes import and auto-tag conflict flows. A new `AutoTagWorker` fingerprints tracks and builds `TagConflict` lists; a new `AutoTagReview` page (modelled on `ITunesImport`) lets the user resolve them before writing. A `Full Process` button fires auto-tag, analyze, and artwork lookup concurrently.

**Tech Stack:** PySide6, pyacoustid, musicbrainzngs, Chromaprint (fpcalc), SQLite, pytest

---

## File Map

| Action | File | What changes |
|---|---|---|
| Modify | `src/core/models.py` | Rename `TagConflict` fields; add `acoustid_no_match` to `Track` |
| Modify | `src/core/itunes.py` | Use renamed `TagConflict` fields |
| Modify | `src/core/fingerprint.py` | Extend `lookup_metadata` with MusicBrainz detail fetch |
| Modify | `src/core/database.py` | Add `acoustid_no_match` column; update upsert/read |
| Modify | `src/gui/workers.py` | New `AutoTagWorker`; remove `overwrite` from `AnalyzeWorker` |
| Create | `src/gui/autotag_review.py` | New conflict review page |
| Modify | `src/gui/itunes_import.py` | Use renamed `TagConflict` fields and resolution values |
| Modify | `src/gui/library_browser.py` | Add `process_all_requested` signal, Full Process button, No Match column |
| Modify | `src/gui/main_window.py` | Wire new worker, page, signals; Full Process handler |
| Modify | `tests/core/test_itunes.py` | Update field name assertions |
| Modify | `tests/core/test_models.py` | Add `acoustid_no_match` round-trip test |
| Modify | `tests/core/test_fingerprint.py` | Add MusicBrainz lookup tests |
| Modify | `tests/core/test_database.py` | Add `acoustid_no_match` column test |
| Create | `tests/core/test_autotag_worker.py` | Unit tests for conflict generation logic |
| Modify | `docs/guides/library-browser.md` | Document new buttons and No Match column |
| Modify | `docs/guides/tag-editing.md` | Document Auto-Tag conflict review page |

---

### Task 1: Rename TagConflict fields to be generic

`TagConflict.file_value` and `TagConflict.itunes_value` are iTunes-specific names. Rename them to `local_value` and `incoming_value`, and change the resolution string values from `"file"`/`"itunes"` to `"local"`/`"incoming"`. This makes the model reusable for both iTunes import and auto-tag conflict flows.

**Files:**
- Modify: `src/core/models.py:94-101`
- Modify: `src/core/itunes.py:45`
- Modify: `src/gui/itunes_import.py:168-169,184,196`
- Modify: `src/gui/main_window.py:598-601`
- Modify: `tests/core/test_itunes.py:61-62`

- [ ] **Step 1: Write the failing test**

Add to `tests/core/test_itunes.py`, replacing the last assertion block:

```python
def test_resolve_conflicts_flags_difference():
    track = Track(file_path=Path("/test.mp3"), file_size=1000, bitrate=128, duration=100.0, title="Song", genre="Rock")
    itunes_entry = {"title": "Song", "genre": "Electronic"}
    conflicts = resolve_conflicts(track, itunes_entry)
    assert len(conflicts) == 1
    assert conflicts[0].field == "genre"
    assert conflicts[0].local_value == "Rock"       # renamed from file_value
    assert conflicts[0].incoming_value == "Electronic"  # renamed from itunes_value
```

- [ ] **Step 2: Run test to verify it fails**

```
uv run pytest tests/core/test_itunes.py::test_resolve_conflicts_flags_difference -v
```
Expected: `AttributeError: 'TagConflict' object has no attribute 'local_value'`

- [ ] **Step 3: Rename fields in models.py**

In `src/core/models.py`, replace the `TagConflict` dataclass:

```python
@dataclass
class TagConflict:
    """A conflict between local tag value and an incoming value for a single field."""

    file_path: Path
    field: str
    local_value: str
    incoming_value: str
    resolution: str | None = None  # "local", "incoming", or None (unresolved)
```

- [ ] **Step 4: Update itunes.py**

In `src/core/itunes.py` line 45, change:

```python
conflicts.append(TagConflict(file_path=track.file_path, field=field, local_value=str(file_val), incoming_value=str(itunes_val)))
```

- [ ] **Step 5: Update itunes_import.py**

In `src/gui/itunes_import.py`, make these changes:

Line 168-169 in `_populate_table`:
```python
self._table.setItem(row, _COL_FILE_VAL, QTableWidgetItem(conflict.local_value))
self._table.setItem(row, _COL_ITUNES_VAL, QTableWidgetItem(conflict.incoming_value))
```

Line 184 in `_bulk_set_field`:
```python
btn_prefer_itunes.clicked.connect(lambda: self._bulk_set_field("incoming"))
btn_prefer_file.clicked.connect(lambda: self._bulk_set_field("local"))
```

Line 196 in `_apply`:
```python
conflict.resolution = "incoming" if combo.currentText() == "Use iTunes" else "local"
```

- [ ] **Step 6: Update main_window.py**

In `src/gui/main_window.py`, in `_on_itunes_apply` (around line 598-601):

```python
for conflict in conflicts:
    if conflict.resolution != "incoming":
        continue
    track = next((t for t in self._all_tracks if t.file_path == conflict.file_path), None)
    if track is None:
        continue
    setattr(track, conflict.field, conflict.incoming_value)
```

- [ ] **Step 7: Run tests to verify they pass**

```
uv run pytest tests/core/test_itunes.py -v
```
Expected: all pass

- [ ] **Step 8: Commit**

```bash
git add src/core/models.py src/core/itunes.py src/gui/itunes_import.py src/gui/main_window.py tests/core/test_itunes.py
git commit -m "refactor: rename TagConflict fields to generic local_value/incoming_value"
```

---

### Task 2: Add acoustid_no_match to Track and Database

Add a `acoustid_no_match: bool` field to `Track` so the library can show which tracks had no AcoustID result. Add the column to the DB with a migration, and update upsert/read.

**Files:**
- Modify: `src/core/models.py`
- Modify: `src/core/database.py`
- Modify: `tests/core/test_database.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/core/test_database.py`:

```python
def test_acoustid_no_match_column_roundtrip(db):
    track = _make_track(acoustid_no_match=True)
    db.upsert_track(track, file_mtime=1000.0)
    result = db.get_track(Path("/music/song.mp3"))
    assert result is not None
    assert result.acoustid_no_match is True


def test_acoustid_no_match_defaults_false(db):
    track = _make_track()
    db.upsert_track(track, file_mtime=1000.0)
    result = db.get_track(Path("/music/song.mp3"))
    assert result is not None
    assert result.acoustid_no_match is False


def test_acoustid_no_match_migration(tmp_path):
    """Opening a DB that was created without the column should add it transparently."""
    import sqlite3
    db_path = tmp_path / "old.db"
    # Create a DB without the column
    conn = sqlite3.connect(str(db_path))
    conn.execute("""CREATE TABLE tracks (
        file_path TEXT PRIMARY KEY, file_size INTEGER NOT NULL,
        bitrate INTEGER NOT NULL, duration REAL NOT NULL,
        title TEXT, artist TEXT, album_artist TEXT, album TEXT,
        track_number INTEGER, disc_number INTEGER, year INTEGER, genre TEXT,
        bpm REAL, key_ TEXT, bucket TEXT, fingerprint TEXT,
        tag_completeness REAL NOT NULL DEFAULT 0.0, tag_source TEXT,
        has_artwork INTEGER NOT NULL DEFAULT 0, file_mtime REAL NOT NULL DEFAULT 0.0,
        date_added REAL
    )""")
    conn.commit()
    conn.close()
    # Opening via Database should migrate it
    from src.core.database import Database
    db2 = Database(db_path)
    row = db2._conn.execute("PRAGMA table_info(tracks)").fetchall()
    col_names = [r[1] for r in row]
    assert "acoustid_no_match" in col_names
```

- [ ] **Step 2: Run tests to verify they fail**

```
uv run pytest tests/core/test_database.py::test_acoustid_no_match_column_roundtrip tests/core/test_database.py::test_acoustid_no_match_migration -v
```
Expected: `TypeError` (no `acoustid_no_match` kwarg on Track) and column not found

- [ ] **Step 3: Add field to Track in models.py**

In `src/core/models.py`, add to `Track` after `has_artwork`:

```python
    has_artwork: bool = False
    acoustid_no_match: bool = False
    date_added: float | None = None  # Unix timestamp (time.time()) set on first scan
```

- [ ] **Step 4: Add column to database.py**

In `src/core/database.py`, make three changes:

**a) Add column to `_CREATE_TRACKS`** (after `date_added`):
```python
    date_added     REAL,
    acoustid_no_match INTEGER NOT NULL DEFAULT 0
```

**b) Add migration in `_setup_schema`** (after the `date_added` migration):
```python
        # Migrate: add acoustid_no_match to existing tracks tables
        try:
            cur.execute("ALTER TABLE tracks ADD COLUMN acoustid_no_match INTEGER NOT NULL DEFAULT 0")
        except sqlite3.OperationalError:
            pass  # column already exists
```

**c) Update `_row_to_track`** (after `date_added`):
```python
        date_added=row["date_added"],
        acoustid_no_match=bool(row["acoustid_no_match"]),
```

**d) Update `upsert_track` SQL** — add `acoustid_no_match` to the INSERT columns list, VALUES list, and UPDATE SET list:

In the INSERT column list add `acoustid_no_match` after `date_added`:
```python
        INSERT INTO tracks (
            file_path, file_size, bitrate, duration,
            title, artist, album_artist, album,
            track_number, disc_number, year, genre,
            bpm, key_, bucket, fingerprint,
            tag_completeness, tag_source, has_artwork, file_mtime, date_added,
            acoustid_no_match
        ) VALUES (
            :file_path, :file_size, :bitrate, :duration,
            :title, :artist, :album_artist, :album,
            :track_number, :disc_number, :year, :genre,
            :bpm, :key_, :bucket, :fingerprint,
            :tag_completeness, :tag_source, :has_artwork, :file_mtime, :date_added,
            :acoustid_no_match
        )
        ON CONFLICT(file_path) DO UPDATE SET
            ...
            has_artwork      = excluded.has_artwork,
            acoustid_no_match = excluded.acoustid_no_match,
            file_mtime       = excluded.file_mtime
```

In the params dict, add:
```python
            "acoustid_no_match": int(track.acoustid_no_match),
```

- [ ] **Step 5: Run tests to verify they pass**

```
uv run pytest tests/core/test_database.py -v
```
Expected: all pass

- [ ] **Step 6: Commit**

```bash
git add src/core/models.py src/core/database.py tests/core/test_database.py
git commit -m "feat: add acoustid_no_match field to Track and database"
```

---

### Task 3: Extend fingerprint.lookup_metadata with MusicBrainz

After AcoustID returns a `recording_id`, call `musicbrainzngs.get_recording_by_id` to fetch album, album artist, track number, and year. Return them as part of the existing result dict.

**Files:**
- Modify: `src/core/fingerprint.py`
- Modify: `tests/core/test_fingerprint.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/core/test_fingerprint.py`:

```python
@patch("src.core.fingerprint.acoustid.match")
@patch("src.core.fingerprint.musicbrainzngs")
def test_lookup_metadata_fetches_musicbrainz_details(mock_mb, mock_match):
    mock_match.return_value = iter([
        (0.95, "recording-id-123", "Blue Monday", "New Order"),
    ])
    mock_mb.get_recording_by_id.return_value = {
        "recording": {
            "artist-credit": [{"artist": {"name": "New Order"}}],
            "release-list": [{
                "title": "Power, Corruption & Lies",
                "date": "1983-05-02",
                "artist-credit": [{"artist": {"name": "New Order"}}],
                "medium-list": [{
                    "track-list": [{"number": "1", "position": "1"}]
                }],
            }],
        }
    }
    result = lookup_metadata("fake-fingerprint", 240.0)
    assert result is not None
    assert result["album"] == "Power, Corruption & Lies"
    assert result["album_artist"] == "New Order"
    assert result["year"] == 1983
    assert result["track_number"] == 1


@patch("src.core.fingerprint.acoustid.match")
@patch("src.core.fingerprint.musicbrainzngs")
def test_lookup_metadata_graceful_when_mb_returns_no_releases(mock_mb, mock_match):
    mock_match.return_value = iter([
        (0.95, "recording-id-123", "Blue Monday", "New Order"),
    ])
    mock_mb.get_recording_by_id.return_value = {
        "recording": {"artist-credit": [], "release-list": []}
    }
    result = lookup_metadata("fake-fingerprint", 240.0)
    assert result is not None
    assert result["title"] == "Blue Monday"
    assert result["album"] is None
    assert result["year"] is None


@patch("src.core.fingerprint.acoustid.match")
@patch("src.core.fingerprint.musicbrainzngs")
def test_lookup_metadata_graceful_when_mb_raises(mock_mb, mock_match):
    mock_match.return_value = iter([
        (0.95, "recording-id-123", "Blue Monday", "New Order"),
    ])
    mock_mb.get_recording_by_id.side_effect = Exception("network error")
    result = lookup_metadata("fake-fingerprint", 240.0)
    assert result is not None
    assert result["title"] == "Blue Monday"
    assert result["album"] is None
```

- [ ] **Step 2: Run tests to verify they fail**

```
uv run pytest tests/core/test_fingerprint.py::test_lookup_metadata_fetches_musicbrainz_details -v
```
Expected: `AssertionError` — `result` has no `album` key

- [ ] **Step 3: Update fingerprint.py**

Replace the contents of `src/core/fingerprint.py` with:

```python
from __future__ import annotations

import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    import acoustid
except ImportError:
    acoustid = None

try:
    import musicbrainzngs
    musicbrainzngs.set_useragent("music-sorter", "0.1", "https://github.com/")
except ImportError:
    musicbrainzngs = None

_API_KEY = "ACOUSTID_API_KEY"


def generate_fingerprint(path: Path) -> str | None:
    """Generate a Chromaprint audio fingerprint. Returns fingerprint string or None."""
    logger.debug("Generating fingerprint: %s", path)
    try:
        result = subprocess.run(
            ["fpcalc", "-raw", str(path)],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            logger.warning("fpcalc returned non-zero exit code for: %s", path)
            return None
        for line in result.stdout.strip().split("\n"):
            if line.startswith("FINGERPRINT="):
                return line.split("=", 1)[1]
        return None
    except subprocess.TimeoutExpired:
        logger.error("fpcalc timed out for: %s", path)
        return None
    except FileNotFoundError:
        logger.error("fpcalc not found — install Chromaprint to enable fingerprinting")
        return None


def _fetch_musicbrainz_details(recording_id: str) -> dict:
    """Fetch album, album_artist, track_number, year from MusicBrainz."""
    if musicbrainzngs is None:
        return {}
    try:
        result = musicbrainzngs.get_recording_by_id(
            recording_id,
            includes=["releases", "artists"],
        )
        recording = result.get("recording", {})
        releases = recording.get("release-list", [])
        if not releases:
            return {}
        release = releases[0]

        album: str | None = release.get("title")

        date_str = release.get("date", "")
        year: int | None = int(date_str[:4]) if len(date_str) >= 4 and date_str[:4].isdigit() else None

        album_artist: str | None = None
        for credit in release.get("artist-credit", []):
            if isinstance(credit, dict) and "artist" in credit:
                album_artist = credit["artist"].get("name")
                break

        track_number: int | None = None
        for medium in release.get("medium-list", []):
            track_list = medium.get("track-list", [])
            if track_list:
                num = track_list[0].get("number") or track_list[0].get("position")
                if num:
                    try:
                        track_number = int(num)
                    except (ValueError, TypeError):
                        pass
                break

        return {
            "album": album,
            "album_artist": album_artist,
            "track_number": track_number,
            "year": year,
        }
    except Exception:
        logger.warning("MusicBrainz lookup failed for recording %s", recording_id)
        return {}


def lookup_metadata(fingerprint: str, duration: float, api_key: str = _API_KEY) -> dict | None:
    """Look up track metadata via AcoustID API, then fetch extended details from MusicBrainz."""
    if acoustid is None:
        return None
    try:
        results = acoustid.match(api_key, None, None, fingerprint=fingerprint, duration=int(duration))
        for score, recording_id, title, artist in results:
            mb_details = _fetch_musicbrainz_details(recording_id)
            return {
                "score": score,
                "recording_id": recording_id,
                "title": title,
                "artist": artist,
                "album": mb_details.get("album"),
                "album_artist": mb_details.get("album_artist"),
                "track_number": mb_details.get("track_number"),
                "year": mb_details.get("year"),
            }
    except Exception:
        return None
    return None


def compute_similarity(fp1: str, fp2: str) -> float:
    """Compute similarity between two fingerprints (0.0 to 1.0)."""
    if fp1 == fp2:
        return 1.0
    try:
        ints1 = [int(x) for x in fp1.split(",")]
        ints2 = [int(x) for x in fp2.split(",")]
    except ValueError:
        common = sum(a == b for a, b in zip(fp1, fp2))
        max_len = max(len(fp1), len(fp2))
        return common / max_len if max_len > 0 else 0.0

    min_len = min(len(ints1), len(ints2))
    max_len = max(len(ints1), len(ints2))
    if max_len == 0:
        return 0.0

    matching_bits = 0
    total_bits = max_len * 32
    for i in range(min_len):
        xor = ints1[i] ^ ints2[i]
        matching_bits += 32 - bin(xor & 0xFFFFFFFF).count("1")

    return matching_bits / total_bits
```

- [ ] **Step 4: Run tests to verify they pass**

```
uv run pytest tests/core/test_fingerprint.py -v
```
Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add src/core/fingerprint.py tests/core/test_fingerprint.py
git commit -m "feat: extend lookup_metadata with MusicBrainz album/year/track details"
```

---

### Task 4: Add AutoTagWorker

New `QThread` subclass in `workers.py`. Fingerprints each track, calls `lookup_metadata`, diffs the result against existing tag values to produce `TagConflict` objects, and tracks unmatched count.

**Files:**
- Modify: `src/gui/workers.py`
- Create: `tests/core/test_autotag_worker.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/core/test_autotag_worker.py`:

```python
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from src.core.models import Track


def _make_track(path="/music/song.mp3", **kwargs) -> Track:
    defaults = dict(
        file_path=Path(path), file_size=1_000_000, bitrate=320, duration=240.0,
        title="Blue Monday", artist="New Order", album=None, album_artist=None,
        track_number=None, year=None,
    )
    defaults.update(kwargs)
    return Track(**defaults)


def _run_worker_sync(tracks, db):
    """Run AutoTagWorker synchronously by calling run() directly (no Qt event loop needed)."""
    from src.gui.workers import AutoTagWorker
    conflicts_out = []
    unmatched_out = []

    worker = AutoTagWorker(tracks, db)
    worker.finished.connect(lambda c, u: (conflicts_out.extend(c), unmatched_out.append(u)))
    worker.run()  # call directly — skips QThread machinery
    return conflicts_out, unmatched_out[0] if unmatched_out else 0


@patch("src.gui.workers.generate_fingerprint", return_value=None)
def test_no_fingerprint_marks_unmatched(mock_fp, tmp_path):
    from src.core.database import Database
    db = Database(tmp_path / "test.db")
    track = _make_track()
    db.upsert_track(track, file_mtime=1000.0)

    conflicts, unmatched = _run_worker_sync([track], db)

    assert unmatched == 1
    assert conflicts == []
    result = db.get_track(Path("/music/song.mp3"))
    assert result.acoustid_no_match is True


@patch("src.gui.workers.lookup_metadata", return_value=None)
@patch("src.gui.workers.generate_fingerprint", return_value="fake-fp")
def test_no_acoustid_match_marks_unmatched(mock_fp, mock_lookup, tmp_path):
    from src.core.database import Database
    db = Database(tmp_path / "test.db")
    track = _make_track()
    db.upsert_track(track, file_mtime=1000.0)

    conflicts, unmatched = _run_worker_sync([track], db)

    assert unmatched == 1
    assert conflicts == []


@patch("src.gui.workers.lookup_metadata")
@patch("src.gui.workers.generate_fingerprint", return_value="fake-fp")
def test_matching_values_produce_no_conflict(mock_fp, mock_lookup, tmp_path):
    from src.core.database import Database
    mock_lookup.return_value = {
        "title": "Blue Monday", "artist": "New Order",
        "album": None, "album_artist": None, "track_number": None, "year": None,
    }
    db = Database(tmp_path / "test.db")
    track = _make_track(title="Blue Monday", artist="New Order")
    db.upsert_track(track, file_mtime=1000.0)

    conflicts, unmatched = _run_worker_sync([track], db)

    assert unmatched == 0
    assert conflicts == []


@patch("src.gui.workers.lookup_metadata")
@patch("src.gui.workers.generate_fingerprint", return_value="fake-fp")
def test_empty_field_produces_use_found_conflict(mock_fp, mock_lookup, tmp_path):
    from src.core.database import Database
    mock_lookup.return_value = {
        "title": "Blue Monday", "artist": "New Order",
        "album": "Power, Corruption & Lies", "album_artist": "New Order",
        "track_number": 1, "year": 1983,
    }
    db = Database(tmp_path / "test.db")
    track = _make_track(title="Blue Monday", artist="New Order",
                        album=None, album_artist=None, track_number=None, year=None)
    db.upsert_track(track, file_mtime=1000.0)

    conflicts, unmatched = _run_worker_sync([track], db)

    assert unmatched == 0
    conflict_fields = {c.field for c in conflicts}
    assert "album" in conflict_fields
    assert "year" in conflict_fields
    album_conflict = next(c for c in conflicts if c.field == "album")
    assert album_conflict.local_value == ""
    assert album_conflict.incoming_value == "Power, Corruption & Lies"


@patch("src.gui.workers.lookup_metadata")
@patch("src.gui.workers.generate_fingerprint", return_value="fake-fp")
def test_differing_existing_value_produces_conflict(mock_fp, mock_lookup, tmp_path):
    from src.core.database import Database
    mock_lookup.return_value = {
        "title": "Blue Monday", "artist": "New Order",
        "album": "Power, Corruption & Lies", "album_artist": None,
        "track_number": None, "year": 1983,
    }
    db = Database(tmp_path / "test.db")
    track = _make_track(title="Blue Monday", artist="New Order", album="Wrong Album", year=2000)
    db.upsert_track(track, file_mtime=1000.0)

    conflicts, unmatched = _run_worker_sync([track], db)

    album_conflict = next((c for c in conflicts if c.field == "album"), None)
    assert album_conflict is not None
    assert album_conflict.local_value == "Wrong Album"
    assert album_conflict.incoming_value == "Power, Corruption & Lies"

    year_conflict = next((c for c in conflicts if c.field == "year"), None)
    assert year_conflict is not None
    assert year_conflict.local_value == "2000"
    assert year_conflict.incoming_value == "1983"
```

- [ ] **Step 2: Run tests to verify they fail**

```
uv run pytest tests/core/test_autotag_worker.py -v
```
Expected: `ImportError` — `AutoTagWorker` not defined

- [ ] **Step 3: Add imports to workers.py**

At the top of `src/gui/workers.py`, add these imports alongside the existing ones:

```python
from src.core.fingerprint import generate_fingerprint, lookup_metadata
```

- [ ] **Step 4: Add AutoTagWorker class to workers.py**

Add before the `ArtworkWorker` class:

```python
_AUTOTAG_FIELDS = ["title", "artist", "album", "album_artist", "track_number", "year"]


class AutoTagWorker(QThread):
    """Fingerprints tracks, looks up metadata via AcoustID + MusicBrainz, and builds
    a list of TagConflict objects for fields that differ from existing tag values.
    """

    progress = Signal(int, int)   # completed, total
    finished = Signal(list, int)  # list[TagConflict], unmatched_count
    error = Signal(str)

    def __init__(self, tracks: list[Track], db: Database):
        super().__init__()
        self._tracks = tracks
        self._db = db

    def run(self) -> None:
        from src.core.models import TagConflict
        total = len(self._tracks)
        conflicts: list[TagConflict] = []
        unmatched = 0

        for i, track in enumerate(self._tracks, 1):
            try:
                fp = generate_fingerprint(track.file_path)
                if fp is None:
                    unmatched += 1
                    track.acoustid_no_match = True
                    self._upsert(track)
                    self.progress.emit(i, total)
                    continue

                meta = lookup_metadata(fp, track.duration)
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

        self.finished.emit(conflicts, unmatched)

    def _upsert(self, track: Track) -> None:
        try:
            mtime = track.file_path.stat().st_mtime
        except OSError:
            mtime = 0.0
        upsert_track_in_db(self._db, track, file_mtime=mtime)
```

- [ ] **Step 5: Run tests to verify they pass**

```
uv run pytest tests/core/test_autotag_worker.py -v
```
Expected: all pass

- [ ] **Step 6: Commit**

```bash
git add src/gui/workers.py tests/core/test_autotag_worker.py
git commit -m "feat: add AutoTagWorker for AcoustID/MusicBrainz metadata lookup"
```

---

### Task 5: Simplify AnalyzeWorker

Remove the `overwrite` parameter — it always overwrites now. Auto-tag no longer uses this worker.

**Files:**
- Modify: `src/gui/workers.py`

- [ ] **Step 1: Update AnalyzeWorker in workers.py**

Remove the `overwrite` parameter from `__init__` and update `run` to always process all tracks:

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

    def run(self):
        total = len(self._tracks)
        updated: list[Track] = []
        for i, track in enumerate(self._tracks, 1):
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

- [ ] **Step 2: Update main_window.py callers**

In `src/gui/main_window.py`, find `_on_auto_tag` and `_on_analyze`. They currently both call `AnalyzeWorker` with different `overwrite` flags. Update both:

```python
def _on_auto_tag(self, tracks: list[Track]) -> None:
    """Look up metadata via AcoustID/MusicBrainz for selected tracks."""
    if not tracks:
        return
    if self._autotag_worker and self._autotag_worker.isRunning():
        return
    self._autotag_worker = AutoTagWorker(tracks, self._db)
    self._autotag_worker.progress.connect(self._on_autotag_progress)
    self._autotag_worker.finished.connect(self._on_autotag_finished)
    self._autotag_worker.error.connect(
        lambda msg: self._status_label.setText(f"Auto-tag error: {msg}")
    )
    self._status_label.setText(f"Looking up metadata for {len(tracks)} track(s)…")
    self._progress_bar.setRange(0, len(tracks))
    self._progress_bar.setValue(0)
    self._progress_bar.setVisible(True)
    self._autotag_worker.start()

def _on_analyze(self, tracks: list[Track]) -> None:
    """Run BPM/key detection on selected tracks."""
    self._start_analyze(tracks)

def _start_analyze(self, tracks: list[Track]) -> None:
    if not tracks:
        return
    if self._analyze_worker and self._analyze_worker.isRunning():
        return
    self._analyze_worker = AnalyzeWorker(tracks, self._db)
    self._analyze_worker.progress.connect(self._on_analyze_progress)
    self._analyze_worker.finished.connect(self._on_analyze_finished)
    self._analyze_worker.error.connect(
        lambda msg: self._status_label.setText(f"Analysis error: {msg}")
    )
    self._status_label.setText(f"Analyzing {len(tracks)} track(s)…")
    self._progress_bar.setRange(0, len(tracks))
    self._progress_bar.setValue(0)
    self._progress_bar.setVisible(True)
    self._analyze_worker.start()
```

Also add `AutoTagWorker` to the imports at the top of `main_window.py`:
```python
from src.gui.workers import AnalyzeWorker, ArtworkWorker, AutoTagWorker, ScanWorker, TagWriteWorker
```

And add the instance variable in `__init__`:
```python
self._autotag_worker: AutoTagWorker | None = None
```

- [ ] **Step 3: Run all core tests to verify nothing broke**

```
uv run pytest tests/core/ -v
```
Expected: all pass

- [ ] **Step 4: Commit**

```bash
git add src/gui/workers.py src/gui/main_window.py
git commit -m "refactor: AnalyzeWorker always overwrites; _on_auto_tag now uses AutoTagWorker"
```

---

### Task 6: Build AutoTagReview page

New page modelled on `ITunesImport`. Shows conflicts in a table with Keep / Use Found dropdowns, bulk toggle buttons, and Apply/Skip All actions.

**Files:**
- Create: `src/gui/autotag_review.py`

- [ ] **Step 1: Create src/gui/autotag_review.py**

```python
from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QComboBox, QHeaderView,
)
from PySide6.QtCore import Qt, Signal

from src.core.models import TagConflict

import logging
logger = logging.getLogger(__name__)

_COL_FILE = 0
_COL_FIELD = 1
_COL_CURRENT = 2
_COL_FOUND = 3
_COL_RESOLUTION = 4

_FIELD_LABELS = {
    "title": "Title",
    "artist": "Artist",
    "album": "Album",
    "album_artist": "Album Artist",
    "track_number": "Track #",
    "year": "Year",
}

_OPT_KEEP = "Keep"
_OPT_USE = "Use Found"


class AutoTagReview(QWidget):
    """Conflict review page for Auto-Tag metadata lookup results."""

    apply_requested = Signal(list)  # list[TagConflict] — only conflicts with resolution="incoming"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._conflicts: list[TagConflict] = []
        self._build_ui()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_conflicts(self, conflicts: list[TagConflict]) -> None:
        self._conflicts = conflicts
        self._populate_table(conflicts)
        self._update_status()

    def conflict_count(self) -> int:
        return self._table.rowCount()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(6)

        outer.addWidget(QLabel(
            "Review the metadata found via AcoustID / MusicBrainz. "
            "Choose which values to keep for each track."
        ))

        # Bulk toggle buttons
        bulk_row = QHBoxLayout()
        btn_use_all = QPushButton("Use Found for All")
        btn_keep_all = QPushButton("Keep All")
        btn_use_all.clicked.connect(lambda: self._bulk_set(_OPT_USE))
        btn_keep_all.clicked.connect(lambda: self._bulk_set(_OPT_KEEP))
        bulk_row.addWidget(btn_use_all)
        bulk_row.addWidget(btn_keep_all)
        bulk_row.addStretch()
        outer.addLayout(bulk_row)

        # Conflict table
        self._table = QTableWidget(0, 5)
        self._table.setHorizontalHeaderLabels(["File", "Field", "Current Value", "Found Value", "Resolution"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self._table.verticalHeader().setVisible(False)
        self._table.setAlternatingRowColors(True)
        outer.addWidget(self._table, stretch=1)

        # Status + action buttons
        bottom_row = QHBoxLayout()
        self._status_label = QLabel("")
        self._apply_btn = QPushButton("Apply Changes")
        self._apply_btn.setEnabled(False)
        self._apply_btn.clicked.connect(self._apply)
        btn_skip = QPushButton("Skip All")
        btn_skip.clicked.connect(self._skip)
        bottom_row.addWidget(self._status_label, stretch=1)
        bottom_row.addWidget(btn_skip)
        bottom_row.addWidget(self._apply_btn)
        outer.addLayout(bottom_row)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _populate_table(self, conflicts: list[TagConflict]) -> None:
        self._table.setRowCount(0)
        for conflict in conflicts:
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setItem(row, _COL_FILE, QTableWidgetItem(conflict.file_path.name))
            self._table.setItem(row, _COL_FIELD, QTableWidgetItem(
                _FIELD_LABELS.get(conflict.field, conflict.field)
            ))
            self._table.setItem(row, _COL_CURRENT, QTableWidgetItem(conflict.local_value))
            self._table.setItem(row, _COL_FOUND, QTableWidgetItem(conflict.incoming_value))
            combo = QComboBox()
            combo.addItems([_OPT_KEEP, _OPT_USE])
            # Default: Use Found when current is empty, Keep otherwise
            combo.setCurrentText(_OPT_USE if not conflict.local_value else _OPT_KEEP)
            combo.currentTextChanged.connect(self._update_apply_button)
            self._table.setCellWidget(row, _COL_RESOLUTION, combo)
        self._update_apply_button()

    def _update_status(self) -> None:
        n = len(self._conflicts)
        self._status_label.setText(
            f"{n} conflict{'s' if n != 1 else ''} found." if n else "No conflicts."
        )

    def _bulk_set(self, choice: str) -> None:
        for row in range(self._table.rowCount()):
            combo: QComboBox = self._table.cellWidget(row, _COL_RESOLUTION)
            if combo:
                combo.setCurrentText(choice)

    def _update_apply_button(self, *_args) -> None:
        any_use_found = any(
            (combo := self._table.cellWidget(row, _COL_RESOLUTION)) is not None
            and combo.currentText() == _OPT_USE
            for row in range(self._table.rowCount())
        )
        self._apply_btn.setEnabled(any_use_found)

    def _apply(self) -> None:
        accepted: list[TagConflict] = []
        for row, conflict in enumerate(self._conflicts):
            combo: QComboBox = self._table.cellWidget(row, _COL_RESOLUTION)
            if combo and combo.currentText() == _OPT_USE:
                conflict.resolution = "incoming"
                accepted.append(conflict)
            else:
                conflict.resolution = "local"
        self.apply_requested.emit(accepted)

    def _skip(self) -> None:
        self.apply_requested.emit([])
```

- [ ] **Step 2: Verify it imports cleanly**

```
uv run python -c "from src.gui.autotag_review import AutoTagReview; print('OK')"
```
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add src/gui/autotag_review.py
git commit -m "feat: add AutoTagReview conflict resolution page"
```

---

### Task 7: Update LibraryBrowser

Add the `process_all_requested` signal, **Full Process** button, and `acoustid_no_match` column.

**Files:**
- Modify: `src/gui/library_browser.py`

- [ ] **Step 1: Add acoustid_no_match to column registry**

In `src/gui/library_browser.py`, add to `_COLUMN_HEADERS`:
```python
    "acoustid_no_match": "No Match",
```

Add a rendering case to `_track_cell_value` (after the `has_artwork` case):
```python
    if col == "acoustid_no_match":
        return "✓" if val else ""
```

- [ ] **Step 2: Add signal and button**

In the `LibraryBrowser` class, add the new signal alongside the existing ones:
```python
    process_all_requested = Signal(list)  # emits list[Track] — run auto-tag + analyze + artwork
```

In `__init__`, add the button to the toolbar after `self._btn_analyze`:
```python
        self._btn_full_process = QPushButton("Full Process")
        self._btn_full_process.setEnabled(False)
        toolbar.addWidget(self._btn_full_process)
```

Add the button connection after the existing button connections:
```python
        self._btn_full_process.clicked.connect(
            lambda: self.process_all_requested.emit(self.selected_tracks())
        )
```

Update `_on_selection_changed` to enable the new button:
```python
    def _on_selection_changed(self) -> None:
        tracks = self.selected_tracks()
        has_selection = bool(tracks)
        self._btn_autotag.setEnabled(has_selection)
        self._btn_batch.setEnabled(has_selection)
        self._btn_analyze.setEnabled(has_selection)
        self._btn_full_process.setEnabled(has_selection)
        self.selection_changed.emit(tracks)
```

- [ ] **Step 3: Update the auto_tag_requested signal comment**

Change line 68:
```python
    auto_tag_requested = Signal(list)  # emits list[Track] — AcoustID/MusicBrainz metadata lookup
```

- [ ] **Step 4: Run tests**

```
uv run pytest tests/core/ -v
```
Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add src/gui/library_browser.py
git commit -m "feat: add Full Process button and No Match column to library browser"
```

---

### Task 8: Wire MainWindow

Add the `AutoTagReview` page to the stack, wire all new signals, and add the `_on_full_process` handler.

**Files:**
- Modify: `src/gui/main_window.py`

- [ ] **Step 1: Add page constant and imports**

At the top of `src/gui/main_window.py`, add to the page constants:
```python
_PAGE_AUTOTAG_REVIEW = 6
```

Add to the imports:
```python
from src.gui.autotag_review import AutoTagReview
from src.gui.workers import AnalyzeWorker, ArtworkWorker, AutoTagWorker, ScanWorker, TagWriteWorker
```

- [ ] **Step 2: Add AutoTagReview page to the stack**

In `_build_ui`, after creating `self._settings_view = SettingsView()`:
```python
        # Page 6: Auto-Tag conflict review
        self._autotag_review = AutoTagReview()
```

After `self._stack.addWidget(self._settings_view)  # 5`:
```python
        self._stack.addWidget(self._autotag_review)  # 6
```

- [ ] **Step 3: Wire signals in _build_ui**

After the existing signal connections, add:
```python
        # Wire auto-tag review apply
        self._autotag_review.apply_requested.connect(self._on_autotag_apply)
        # Wire full process button
        self._library.process_all_requested.connect(self._on_full_process)
```

- [ ] **Step 4: Add autotag_worker instance variable in __init__**

In `__init__`, after `self._artwork_worker`:
```python
        self._autotag_worker: AutoTagWorker | None = None
```

- [ ] **Step 5: Add new handler methods**

Add after `_on_analyze_finished`:

```python
    def _on_autotag_progress(self, completed: int, total: int) -> None:
        self._progress_bar.setRange(0, total)
        self._progress_bar.setValue(completed)

    def _on_autotag_finished(self, conflicts: list, unmatched: int) -> None:
        self._progress_bar.setVisible(False)
        msg = "Metadata lookup complete"
        if unmatched:
            msg += f" — {unmatched} track(s) had no match"
        if conflicts:
            msg += f", {len(conflicts)} conflict(s) found"
        self._status_label.setText(msg)
        self._refresh_library()
        if conflicts:
            self._autotag_review.load_conflicts(conflicts)
            self._show_page(_PAGE_AUTOTAG_REVIEW)

    def _on_autotag_apply(self, conflicts: list) -> None:
        if not conflicts:
            self._show_page(_PAGE_LIBRARY)
            return
        pairs: dict = {}
        for conflict in conflicts:
            track = next((t for t in self._all_tracks if t.file_path == conflict.file_path), None)
            if track is None:
                continue
            field = conflict.field
            value = conflict.incoming_value
            if field in ("track_number", "year"):
                try:
                    setattr(track, field, int(value) if value else None)
                except (ValueError, TypeError):
                    setattr(track, field, None)
            else:
                setattr(track, field, value or None)
            if conflict.file_path not in pairs:
                pairs[conflict.file_path] = (track, [])
            pairs[conflict.file_path][1].append(field)
        if not pairs:
            self._show_page(_PAGE_LIBRARY)
            return
        self._tag_worker = TagWriteWorker(list(pairs.values()), self._db)
        self._tag_worker.finished.connect(self._on_autotag_write_finished)
        self._tag_worker.error.connect(
            lambda msg: self._status_label.setText(f"Auto-tag write error: {msg}")
        )
        self._tag_worker.start()

    def _on_autotag_write_finished(self, updated: list) -> None:
        self._status_label.setText(f"Auto-tag applied to {len(updated)} track(s)")
        self._show_page(_PAGE_LIBRARY)
        self._refresh_library()

    def _on_full_process(self, tracks: list) -> None:
        if not tracks:
            return
        # Start BPM/key analysis immediately
        if not (self._analyze_worker and self._analyze_worker.isRunning()):
            self._analyze_worker = AnalyzeWorker(tracks, self._db)
            self._analyze_worker.progress.connect(self._on_analyze_progress)
            self._analyze_worker.finished.connect(self._on_analyze_finished)
            self._analyze_worker.error.connect(
                lambda msg: self._status_label.setText(f"Analysis error: {msg}")
            )
            self._analyze_worker.start()
        # Start artwork lookup immediately
        if not (self._artwork_worker and self._artwork_worker.isRunning()):
            self._artwork_worker = ArtworkWorker(tracks)
            self._artwork_worker.finished.connect(self._on_artwork_scan_track_done)
            self._artwork_worker.done.connect(self._refresh_library)
            self._artwork_worker.status_message.connect(
                lambda msg: self.statusBar().showMessage(msg, 5000)
            )
            self._artwork_worker.start()
        # Start metadata lookup (navigates to review page when done)
        self._on_auto_tag(tracks)
        self._status_label.setText(f"Processing {len(tracks)} track(s)…")
```

- [ ] **Step 6: Update closeEvent to include autotag_worker**

In `closeEvent`, add `self._autotag_worker` to the workers tuple:
```python
        for worker in (
            self._scan_worker,
            self._tag_worker,
            self._analyze_worker,
            self._artwork_worker,
            self._autotag_worker,
            getattr(self._dupe_resolver, "_worker", None),
            getattr(self._rename_preview, "_worker", None),
            getattr(self._itunes_import, "_worker", None),
        ):
```

- [ ] **Step 7: Confirm no duplicate method definitions remain**

Task 5 replaced `_on_auto_tag`, `_on_analyze`, and `_start_analyze` in `main_window.py`. Verify there are no duplicate definitions left:

```bash
grep -n "def _on_auto_tag\|def _on_analyze\|def _start_analyze" src/gui/main_window.py
```

Each should appear exactly once. If any appear twice, remove the old version (the one with an `overwrite` parameter).

- [ ] **Step 8: Run all core tests**

```
uv run pytest tests/core/ -v
```
Expected: all pass

- [ ] **Step 9: Commit**

```bash
git add src/gui/main_window.py
git commit -m "feat: wire AutoTagReview page and Full Process into MainWindow"
```

---

### Task 9: Update documentation

**Files:**
- Modify: `docs/guides/library-browser.md`
- Modify: `docs/guides/tag-editing.md`

- [ ] **Step 1: Read existing library-browser.md**

```
Read docs/guides/library-browser.md
```

- [ ] **Step 2: Update library-browser.md toolbar section**

Find the section describing the toolbar buttons and update it to document the new button meanings and the No Match column:

In the toolbar description, replace any mention of Auto-Tag filling BPM/key with the new behaviour, and document Analyze and Full Process:

```markdown
## Toolbar Buttons

These buttons act on the currently selected tracks.

| Button | What it does |
|---|---|
| **Auto-Tag Selected** | Fingerprints each selected track via Chromaprint, queries AcoustID and MusicBrainz, then opens a conflict review page to apply title, artist, album, album artist, track number, and year. |
| **Analyze** | Detects BPM and key via librosa and overwrites existing values immediately. No review step. |
| **Full Process** | Runs Analyze and artwork lookup immediately in the background, and Auto-Tag concurrently. Shows the conflict review page when the metadata lookup finishes. |
| **Batch Edit** | Opens the tag editor panel pre-loaded with all selected tracks for manual editing. |
```

Also document the No Match column:

```markdown
## No Match Column

The **No Match** column (hidden by default — right-click the header to show it) displays `✓` for tracks where Auto-Tag or Full Process ran but found no AcoustID match. Sort by this column to bring unmatched tracks to the top for manual review.
```

- [ ] **Step 3: Update tag-editing.md**

Add a section for the Auto-Tag conflict review page:

```markdown
## Auto-Tag Conflict Review

After running **Auto-Tag Selected** or **Full Process**, if any looked-up values differ from existing tags, the conflict review page opens automatically.

Each row shows the track filename, the field being compared, the current value in the file, and the value found via MusicBrainz.

**Resolution column defaults:**
- Empty current value → **Use Found** (safe to apply)
- Non-empty current value → **Keep** (preserves existing data)

**Bulk controls:**
- **Use Found for All** — sets every row to Use Found
- **Keep All** — sets every row to Keep

**Apply Changes** writes all rows set to Use Found back to the file and database, then returns to the library. **Skip All** discards the lookup results and returns to the library without writing anything.

Tracks where no AcoustID match was found are silently skipped and marked in the **No Match** column of the library browser.
```

- [ ] **Step 4: Commit**

```bash
git add docs/guides/library-browser.md docs/guides/tag-editing.md
git commit -m "docs: update library browser and tag editing guides for auto-tag redesign"
```

---

## Final verification

- [ ] **Run full test suite**

```
uv run pytest tests/core/ -v
```
Expected: all pass, no regressions

- [ ] **Check imports are clean**

```
uv run python -c "from src.gui.main_window import MainWindow; print('OK')"
```
Expected: `OK`
