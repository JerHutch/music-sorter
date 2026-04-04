# Music Sorter — Design Specification

## Overview

Music Sorter is a desktop GUI application for organizing, tagging, deduplicating, and restructuring MP3 music collections. It is not a music player. The target user has ~14,000 MP3 files spread across multiple directories, partially tagged, with duplicates and an iTunes library XML as an additional metadata source.

**Tech stack:** Python 3.12+ / PySide6 (Qt6) / SQLite / mutagen / librosa / pyacoustid

**Architecture:** Core library (pure Python, zero Qt dependency) + PySide6 GUI frontend. All business logic lives in the core. The GUI is a thin rendering and dispatch layer. This separation enables TDD on the core without GUI mocking.

---

## 1. Project Structure

```
music-sorter/
├── src/
│   ├── core/                  # Pure Python library — no Qt imports
│   │   ├── __init__.py
│   │   ├── models.py          # Data models (Track, DupeGroup, etc.)
│   │   ├── config.py          # Configuration management
│   │   ├── scanner.py         # File discovery, directory walking
│   │   ├── tagger.py          # Read/write MP3 tags (mutagen)
│   │   ├── fingerprint.py     # AcoustID/Chromaprint integration
│   │   ├── analyzer.py        # BPM detection, key detection
│   │   ├── deduplicator.py    # Duplicate detection & merge logic
│   │   ├── itunes.py          # iTunes XML parser & conflict resolver
│   │   ├── renamer.py         # Pattern engine for file renaming
│   │   ├── organizer.py       # Folder restructuring logic
│   │   ├── normalizer.py      # Tag normalization rules engine
│   │   ├── playlist.py        # Smart playlist generation (M3U/PLS)
│   │   ├── artwork.py         # Album art fetch & embed
│   │   ├── history.py         # Operation log & undo support
│   │   └── database.py        # SQLite cache layer
│   ├── gui/                   # PySide6 frontend
│   │   ├── __init__.py
│   │   ├── app.py             # Application entry point
│   │   ├── main_window.py     # Main window with top nav
│   │   ├── dashboard.py       # Dashboard/overview with stats
│   │   ├── library_browser.py # Track table with configurable columns
│   │   ├── tag_editor.py      # Single & batch tag editing
│   │   ├── dupe_resolver.py   # Duplicate review & merge UI
│   │   ├── itunes_import.py   # iTunes import & conflict resolution UI
│   │   ├── rename_preview.py  # Rename/reorganize dry-run preview
│   │   ├── stats_view.py      # Collection statistics & charts
│   │   ├── playlist_manager.py # Playlist browser with folder tree
│   │   ├── settings_view.py   # Settings/configuration UI
│   │   ├── workers.py         # QThread workers for long operations
│   │   └── widgets/           # Reusable custom widgets
│   └── cli/                   # Future CLI frontend (optional)
├── tests/
│   ├── core/                  # Unit tests for core (TDD, no Qt needed)
│   │   ├── test_scanner.py
│   │   ├── test_tagger.py
│   │   ├── test_fingerprint.py
│   │   ├── test_analyzer.py
│   │   ├── test_deduplicator.py
│   │   ├── test_itunes.py
│   │   ├── test_renamer.py
│   │   ├── test_organizer.py
│   │   ├── test_normalizer.py
│   │   ├── test_playlist.py
│   │   ├── test_artwork.py
│   │   ├── test_history.py
│   │   ├── test_config.py
│   │   └── test_database.py
│   └── gui/                   # GUI integration tests
├── config/                    # Default configuration files
│   └── default_config.yaml
├── docs/
├── pyproject.toml
└── README.md
```

---

## 2. Data Models

### 2.1 Track

The central data model representing one MP3 file and its metadata.

```python
@dataclass
class Track:
    # File info
    file_path: Path
    file_size: int
    bitrate: int
    duration: float

    # Standard ID3 tags
    title: str | None
    artist: str | None
    album_artist: str | None
    album: str | None
    track_number: int | None
    disc_number: int | None
    year: int | None
    genre: str | None

    # DJ-relevant tags
    bpm: float | None
    key: str | None              # Camelot notation (e.g., "8A")

    # Custom tags (stored in ID3 TXXX frames)
    bucket: str | None           # "DJ Mixes", "DJ Music", or "General"

    # Computed/internal
    fingerprint: str | None      # Chromaprint audio fingerprint
    tag_completeness: float      # 0.0–1.0, based on configured required tags
    tag_source: str | None       # "file", "itunes", "musicbrainz", "manual"
    has_artwork: bool
```

### 2.2 Custom Bucket Tag

Stored as an ID3v2 TXXX (user-defined text) frame with description `MUSIC_SORTER_BUCKET`. Values: "DJ Mixes", "DJ Music", "General". This does not interfere with standard players or DJ software.

### 2.3 Supporting Models

- **DupeGroup** — A set of tracks identified as duplicates (by fingerprint similarity). Contains methods to rank by quality and merge tags.
- **TagConflict** — When iTunes XML and file tags disagree on a field. Captures file value, iTunes value, field name, and resolution choice.
- **RenameOperation** — A planned file move: source path, destination path, status (pending/complete/skipped/error).
- **HistoryEntry** — One logged operation: action type, file path, field, old value, new value, timestamp. Used for undo.
- **NormalizationRule** — A tag normalization rule: field, rule type (case, mapping, regex), parameters.
- **PlaylistDefinition** — A saved playlist query: name, folder path, format (M3U/PLS), filter criteria, sort order.

---

## 3. Configuration

All configuration is stored in YAML. The app ships with defaults; user overrides are saved separately and merged.

### 3.1 Required Tags

Defines which tag fields must be populated for a track to be considered "complete." Drives the `tag_completeness` score and the dashboard "missing tags" queue.

```yaml
required_tags:
  global:
    - title
    - artist
    - album
    - genre
    - year
    - bucket
  per_bucket:
    DJ Music:
      - bpm
      - key
```

### 3.2 Rename Patterns

Per-bucket patterns with token substitution and conditionals.

```yaml
rename_patterns:
  default: "{bucket}/{genre}/{artist}/{?album:{album}/}{track:02d} - {title}.mp3"
  DJ Music: "{bucket}/{genre}/{artist} - {title} [{bpm}bpm {key}].mp3"
  DJ Mixes: "{bucket}/{artist}/{title}.mp3"
```

### 3.3 Analysis Settings

Per-bucket toggles for which analyses to run.

```yaml
analysis:
  DJ Music:
    bpm: true
    key: true
    artwork: true
  DJ Mixes:
    bpm: false
    key: false
    artwork: true
  General:
    bpm: false
    key: false
    artwork: true
```

### 3.4 Normalization Rules

```yaml
normalization:
  artist_prefix: "the_first"  # "The Beatles" not "Beatles, The"
  case_mode: "title"          # title case normalization
  genre_map:
    "Hip Hop": "Hip-Hop"
    "HipHop": "Hip-Hop"
    "Drum And Bass": "Drum & Bass"
    "DnB": "Drum & Bass"
  custom_rules:
    - field: artist
      find: "Deadmau5"
      replace: "deadmau5"
```

### 3.5 Source Directories

```yaml
source_directories:
  - /path/to/music/collection1
  - /path/to/music/collection2
itunes_xml_path: /path/to/iTunes Music Library.xml
```

### 3.6 Column Configuration

```yaml
library_columns:
  visible:
    - title
    - artist
    - album
    - genre
    - bpm
    - key
    - bitrate
    - tag_completeness
  order: # same as visible by default, user can reorder
    - title
    - artist
    - album
    - genre
    - bpm
    - key
    - bitrate
    - tag_completeness
  available:  # all possible columns
    - title
    - artist
    - album_artist
    - album
    - track_number
    - disc_number
    - year
    - genre
    - bpm
    - key
    - bitrate
    - duration
    - file_path
    - file_size
    - bucket
    - tag_completeness
    - tag_source
    - has_artwork
```

---

## 4. Core Modules

### 4.1 Scanner (`scanner.py`)

Recursively walks configured source directories and discovers MP3 files.

- Accepts a list of root directories
- Filters by `.mp3` extension (case-insensitive)
- Reports progress via callback: `on_progress(files_found: int, current_dir: str)`
- Returns a list of file paths
- Also identifies empty directories for cleanup reporting

### 4.2 Tagger (`tagger.py`)

Reads and writes MP3 tags using mutagen.

- `read_tags(path) -> Track` — reads all ID3 frames into a Track model
- `write_tags(track, fields, dry_run) -> RenameOperation | None` — writes specified fields back to the file
- Handles ID3v1, ID3v2.3, and ID3v2.4 transparently
- Custom TXXX frame read/write for bucket tag and any future custom tags
- Computes `tag_completeness` based on the configured required tags list

### 4.3 Fingerprinter (`fingerprint.py`)

Audio fingerprinting via Chromaprint (pyacoustid).

- `fingerprint(path) -> str` — generates a Chromaprint fingerprint
- `lookup(fingerprint, duration) -> dict | None` — queries AcoustID API for metadata (title, artist, album, MusicBrainz IDs)
- `similarity(fp1, fp2) -> float` — compares two fingerprints, returns 0.0–1.0 similarity score
- Progress callback for batch operations

### 4.4 Analyzer (`analyzer.py`)

BPM and key detection using librosa.

- `detect_bpm(path, duration_limit=60) -> float` — beat tracking on first N seconds of audio
- `detect_key(path) -> str` — chroma feature extraction, returns Camelot notation (1A–12A, 1B–12B)
- Both return `None` on analysis failure (corrupted files, too short, etc.)
- Progress callback for batch operations

### 4.5 Deduplicator (`deduplicator.py`)

Two-pass duplicate detection with merge strategy.

**Pass 1 — Duration pre-filter:**
Group tracks by duration within a configurable tolerance (default: 2 seconds). Only groups with 2+ tracks proceed to pass 2.

**Pass 2 — Fingerprint comparison:**
Within each duration group, compare fingerprints. Tracks with similarity above threshold (default: 0.85, configurable in `deduplication.similarity_threshold`) are grouped as duplicates.

**Merge & resolve per DupeGroup:**

1. Rank copies by bitrate (highest first), then tag completeness
2. Select keeper: highest bitrate copy
3. Merge tags: for each field, prefer non-empty over empty; prefer higher-quality sources (iTunes > MusicBrainz > filename-parsed > existing); flag true conflicts (two different non-empty values) for manual resolution
4. Write merged tags to keeper
5. Log all deletions to history with full tag snapshots
6. Move inferior copies to trash directory (not permanent delete)

**Output:** List of `DupeGroup` objects with auto-recommendations, ready for UI review.

### 4.6 iTunes Importer (`itunes.py`)

One-time import from iTunes Music Library XML.

**Parsing:** Read the plist XML, extract track metadata (title, artist, album artist, album, track number, genre, year, BPM, file location).

**Matching to files on disk:**
1. Path match — convert iTunes `file:///` URI to local path, check if file exists at that location or corresponding location in configured source directories
2. Fingerprint fallback — match by audio fingerprint for moved/renamed files
3. Unmatched entries are reported but ignored

**Conflict resolution rules:**

| Scenario | Default behavior |
|---|---|
| MP3 tag empty, iTunes has value | Auto-fill from iTunes |
| MP3 tag has value, iTunes empty | Keep MP3 tag |
| Both match | No action |
| Both differ | Flag as `TagConflict` |

**Bulk resolution options:** "Always prefer iTunes for [field]" or "Always prefer file for [field]" to resolve remaining conflicts in batch.

### 4.7 Renamer (`renamer.py`)

Pattern engine for file renaming.

**Token substitution:** `{artist}`, `{album_artist}`, `{album}`, `{title}`, `{track}`, `{disc}`, `{year}`, `{genre}`, `{bpm}`, `{key}`, `{bucket}`, `{bitrate}`. Format modifiers via Python format specs: `{track:02d}`, `{title:.50}`.

**Conditional blocks:**
- `{?tag:content}` — include content only if tag has a value
- `{?tag:if_present|if_missing}` — conditional with fallback

**Safety rules:**
- Sanitize all token values for filesystem safety (illegal characters, trailing dots/spaces)
- Detect path collisions before executing — append suffix like `(2)` on collision
- Never overwrite existing files
- Dry-run returns full rename plan as list of `RenameOperation` objects

**Per-bucket patterns:** Different buckets use different patterns from config.

### 4.8 Organizer (`organizer.py`)

Executes the rename plan and restructures directories.

- Takes a list of `RenameOperation` objects from the renamer
- Creates destination directories as needed
- Moves files (not copy — avoids doubling disk usage)
- Logs all moves to history
- Cleans up empty directories left behind after moves
- Dry-run mode: returns the plan without executing

### 4.9 Normalizer (`normalizer.py`)

Tag normalization rules engine.

**Built-in rule types:**
- Artist prefix handling ("The Beatles" vs "Beatles, The")
- Case normalization (title case, as-is, custom per field)
- Genre consolidation via mapping table
- Whitespace/punctuation cleanup (extra spaces, unicode normalization)
- Custom regex find/replace per field

**Workflow:** Scan produces a list of proposed changes (dry-run preview). User reviews and confirms. Changes are applied and logged to history.

### 4.10 Playlist Generator (`playlist.py`)

Query-based playlist generation.

**PlaylistDefinition:**
```yaml
name: "High Energy DJ Set"
folder: "DJ"
format: m3u
filters:
  bucket: "DJ Music"
  bpm: { min: 125, max: 140 }
  genre: ["House", "Techno", "Trance"]
  key: ["8A", "9A", "10A"]
sort_by: bpm
```

- Generates M3U or PLS files from filter queries against the track database
- Playlist definitions are saved and can be re-run after collection changes
- Playlists are organized into a folder tree (stored in config)

### 4.11 Artwork Manager (`artwork.py`)

Album art fetch and embed.

- Query MusicBrainz by artist + album to find the release
- Pull cover art from the Cover Art Archive
- Embed as ID3 APIC frame
- Batch mode: queue all tracks missing artwork, fetch in bulk
- All fetched art is staged for preview before writing

### 4.12 History (`history.py`)

Append-only operation log enabling undo.

**Log format (JSONL):**
```json
{"timestamp": "2026-04-04T12:00:00", "action": "tag_write", "file": "/path/to/file.mp3", "field": "artist", "old": "Beetles", "new": "The Beatles"}
{"timestamp": "2026-04-04T12:00:01", "action": "rename", "old_path": "/old/path.mp3", "new_path": "/new/path.mp3"}
{"timestamp": "2026-04-04T12:00:02", "action": "delete", "file": "/path/to/dupe.mp3", "trash_path": "/trash/dupe.mp3", "snapshot": {"title": "...", "artist": "..."}}
```

- **Undo:** Reverses operations in LIFO order
- **Trash:** Deleted files are moved to a trash/staging directory, not permanently removed, until user explicitly empties trash
- **Grouping:** Operations from a single user action (e.g., "deduplicate all") are grouped by a session ID so they can be undone as a unit

### 4.13 Database Cache (`database.py`)

SQLite-based local cache for fast GUI performance. The MP3 file tags remain the **source of truth**; SQLite is a performance cache and query engine.

**Why SQLite:**
- Built into Python (`sqlite3` standard library) — zero deployment overhead
- Single `.db` file, no server process
- 14K rows is trivial; complex queries for playlist filtering and stats aggregation are instant
- FTS5 extension enables fast full-text search across artist/title/album fields

**Schema (core tables):**

```sql
CREATE TABLE tracks (
    id INTEGER PRIMARY KEY,
    file_path TEXT UNIQUE NOT NULL,
    file_size INTEGER,
    file_mtime REAL,            -- modification time for change detection
    bitrate INTEGER,
    duration REAL,
    title TEXT,
    artist TEXT,
    album_artist TEXT,
    album TEXT,
    track_number INTEGER,
    disc_number INTEGER,
    year INTEGER,
    genre TEXT,
    bpm REAL,
    key TEXT,
    bucket TEXT,
    fingerprint TEXT,
    tag_completeness REAL,
    tag_source TEXT,
    has_artwork INTEGER         -- boolean as 0/1
);

CREATE VIRTUAL TABLE tracks_fts USING fts5(
    title, artist, album_artist, album, genre,
    content='tracks', content_rowid='id'
);

CREATE TABLE history (
    id INTEGER PRIMARY KEY,
    session_id TEXT,             -- groups related operations
    timestamp TEXT,
    action TEXT,
    file_path TEXT,
    field TEXT,
    old_value TEXT,
    new_value TEXT,
    metadata TEXT                -- JSON for extra data (snapshots, trash paths)
);

CREATE TABLE playlists (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    folder TEXT,                 -- folder path in tree, e.g. "DJ/Sets"
    format TEXT DEFAULT 'm3u',
    filters TEXT,                -- JSON filter definition
    sort_by TEXT
);
```

**Sync strategy:**

- **First run:** Full scan of all source directories, parse all MP3 tags, populate DB
- **Subsequent launches:** Compare `file_mtime` in DB against actual file mtime. Only re-read files where mtime has changed or file is new. Remove entries for files that no longer exist on disk. This makes startup fast (~1-2 seconds for 14K files)
- **Write-through:** Any tag write operation updates both the MP3 file and the DB row in the same logical operation. The DB update happens after the file write succeeds.
- **Force rescan:** Manual option in Settings to drop and rebuild the entire cache from disk

**Query interface:**

The database module exposes query methods used by the GUI for:
- Filtered/sorted track listing (library browser)
- Full-text search across text fields
- Aggregate stats (tag completeness breakdown, genre distribution, bitrate histogram, storage per bucket)
- Playlist filter evaluation
- Duplicate group retrieval

---

## 5. GUI Design

### 5.1 Main Window Layout

**Top navigation bar:** Dashboard | Library | Import | Settings — plus a summary line (track count, bucket count).

**Left sidebar (persistent across views):**
- **Buckets:** All Music, DJ Music, DJ Mixes, General — with counts. Click to filter.
- **Task Queue:** Missing Tags, Duplicates, No Artwork, Ready to Organize, Empty Dirs — with counts, color-coded by severity. Click to filter the library view to those tracks.
- **Saved Playlists:** Tree view with folder support. Right-click to create folders, drag to organize.

**Main panel:** Changes based on selected top nav tab.

### 5.2 Library Browser (main view)

- Sortable, multi-select track table
- Configurable columns: right-click header to show/hide. Column visibility and order persisted in config. Available columns: title, artist, album_artist, album, track_number, disc_number, year, genre, bpm, key, bitrate, duration, file_path, file_size, bucket, tag_completeness, tag_source, has_artwork
- Color-coded tag completeness indicator: green (complete), orange (partial), red (missing)
- Search bar with text filter
- Toolbar: Auto-Tag Selected, Batch Edit, Analyze, Organize — actions apply to selected tracks
- Status bar: selection count, tag completeness legend, background task status

### 5.3 Dashboard View

- Tag completeness breakdown (pie/donut chart)
- Genre distribution (bar chart)
- Bitrate distribution (bar chart)
- Storage usage per bucket
- Duplicate count summary
- Missing artwork count
- All stats are clickable — navigate to relevant tracks in library browser

### 5.4 Tag Editor

- **Single track:** Click a track to edit all tag fields in a detail panel
- **Batch edit:** Select multiple tracks, edit shared fields at once (e.g., set genre for 50 tracks, fix misspelled artist). Fields with mixed values show "[Multiple]" and can be overwritten or left as-is.

### 5.5 Duplicate Resolver

- Table of dupe groups, each expandable to show all copies
- Per group: file paths, bitrates, tag diffs highlighted
- Actions per group: accept auto-recommendation, override keeper, resolve tag conflicts via dropdowns, skip
- Bulk action: process all remaining with auto-recommendation

### 5.6 iTunes Import View

- File picker for iTunes XML
- Progress bar for parsing and matching
- Conflict resolution table: file, field, current value, iTunes value, action (keep file / use iTunes)
- Bulk rules: "always prefer iTunes for [field]" / "always prefer file for [field]"

### 5.7 Rename/Organize Preview

- Pattern editor with live preview (type pattern, see sample output)
- Full dry-run table: old path → new path for all affected files
- Collision warnings highlighted
- Execute button (only after dry-run review)

### 5.8 Settings View

- Source directories (add/remove)
- Required tags configuration (global and per-bucket)
- Rename patterns (per-bucket)
- Analysis toggles (per-bucket)
- Normalization rules editor
- Genre mapping table editor
- History/trash management (view log, empty trash)

### 5.9 Background Tasks

- All long-running operations (scanning, fingerprinting, analysis, artwork fetch) run in QThread workers
- Progress bar in status bar area
- Pause/cancel support
- Results are staged for review, not applied automatically

---

## 6. Key Dependencies

| Package | Purpose |
|---|---|
| PySide6 | Qt6 GUI framework |
| sqlite3 (stdlib) | Local cache database — no install needed |
| mutagen | MP3 tag reading/writing (ID3v1, ID3v2.3, ID3v2.4) |
| pyacoustid | AcoustID fingerprint lookup |
| chromaprint (system) | Audio fingerprint generation (native dependency) |
| librosa | BPM and key detection |
| musicbrainzngs | MusicBrainz API for metadata and artwork lookup |
| PyYAML | Configuration file handling |
| pytest | Testing framework |
| pytest-cov | Test coverage reporting |

**System dependency:** chromaprint/fpcalc must be installed (`pacman -S chromaprint` on Arch/CachyOS).

---

## 7. Dry-Run Philosophy

Every destructive or modifying operation supports dry-run mode:

1. The core computes a plan (list of operations: renames, tag writes, deletes)
2. The GUI displays the plan for review
3. User confirms or cancels
4. On confirmation, operations execute and are logged to history
5. Undo is available after execution via history

This applies to: renaming, reorganizing, deduplication (deletes), tag writing, normalization, artwork embedding.

---

## 8. Testing Strategy

**TDD (Red-Green-Refactor) on core:**
- All core modules have corresponding test files
- Tests use fixture MP3 files (small, generated test files with known tags)
- No Qt dependency in core tests — fast execution
- Mock external services (AcoustID API, MusicBrainz API) in tests
- Test the pattern engine extensively (edge cases: missing tags, special characters, collisions)
- Test deduplication with known fingerprint pairs

**GUI tests:**
- Integration tests for critical workflows
- Use Qt test utilities (QTest) for widget interaction testing

---

## 9. Out of Scope

- Music playback
- Streaming integration
- Mobile/web interface
- Non-MP3 format support (could be added later but not in initial scope)
- Multi-user or network access
- Cloud sync
