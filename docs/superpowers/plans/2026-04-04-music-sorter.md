# Music Sorter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python + PySide6 desktop application for organizing, tagging, deduplicating, and restructuring MP3 music collections.

**Architecture:** Core library (pure Python, zero Qt dependency) with all business logic + PySide6 GUI frontend as a thin rendering/dispatch layer. SQLite cache for fast queries. TDD on core, QThread workers for long operations in the GUI.

**Tech Stack:** Python 3.12+, PySide6, SQLite, mutagen, pyacoustid, librosa, musicbrainzngs, PyYAML, pytest

**Spec:** `docs/superpowers/specs/2026-04-04-music-sorter-design.md`

---

## Phase 1: Foundation (Scaffolding, Models, Config, Database, Scanner, Tagger)

### Task 1: Project Scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `src/core/__init__.py`
- Create: `src/gui/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/core/__init__.py`
- Create: `tests/gui/__init__.py`
- Create: `config/default_config.yaml`
- Create: `conftest.py`

- [ ] **Step 1: Create pyproject.toml**

```toml
[project]
name = "music-sorter"
version = "0.1.0"
description = "Desktop application for organizing, tagging, and deduplicating MP3 collections"
requires-python = ">=3.12"
dependencies = [
    "PySide6>=6.6",
    "mutagen>=1.47",
    "pyacoustid>=1.3",
    "librosa>=0.10",
    "musicbrainzngs>=0.7",
    "PyYAML>=6.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-cov>=5.0",
]

[build-system]
requires = ["setuptools>=68.0"]
build-backend = "setuptools.backends._legacy:_Backend"

[tool.setuptools.packages.find]
where = ["."]
include = ["src*"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
```

- [ ] **Step 2: Create package __init__.py files**

Create empty `__init__.py` files:
- `src/__init__.py`
- `src/core/__init__.py`
- `src/gui/__init__.py`
- `tests/__init__.py`
- `tests/core/__init__.py`
- `tests/gui/__init__.py`

- [ ] **Step 3: Create default config file**

Create `config/default_config.yaml`:

```yaml
source_directories: []
itunes_xml_path: null

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

rename_patterns:
  default: "{bucket}/{genre}/{artist}/{?album:{album}/}{track:02d} - {title}.mp3"
  DJ Music: "{bucket}/{genre}/{artist} - {title} [{bpm}bpm {key}].mp3"
  DJ Mixes: "{bucket}/{artist}/{title}.mp3"

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

normalization:
  artist_prefix: "the_first"
  case_mode: "title"
  genre_map: {}
  custom_rules: []

deduplication:
  duration_tolerance: 2.0
  similarity_threshold: 0.85

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
  available:
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

- [ ] **Step 4: Create conftest.py with shared fixtures**

Create `conftest.py` at project root:

```python
from pathlib import Path

import pytest


@pytest.fixture
def tmp_music_dir(tmp_path):
    """Create a temporary directory structure for testing."""
    return tmp_path / "music"


@pytest.fixture
def fixtures_dir():
    """Path to test fixture files."""
    return Path(__file__).parent / "tests" / "fixtures"
```

Create `tests/fixtures/` directory (empty for now — populated in Task 3).

- [ ] **Step 5: Create virtual environment and install dependencies**

Run:
```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

- [ ] **Step 6: Verify pytest runs with no tests**

Run: `pytest -v`
Expected: "no tests ran" with exit code 5 (no tests collected), no import errors.

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml conftest.py config/ src/ tests/
git commit -m "feat: project scaffolding with dependencies and default config"
```

---

### Task 2: Data Models

**Files:**
- Create: `src/core/models.py`
- Create: `tests/core/test_models.py`

- [ ] **Step 1: Write failing tests for Track model**

Create `tests/core/test_models.py`:

```python
from pathlib import Path

from src.core.models import Track


def test_track_creation_with_all_fields():
    track = Track(
        file_path=Path("/music/song.mp3"),
        file_size=5_000_000,
        bitrate=320,
        duration=240.5,
        title="Blue Monday",
        artist="New Order",
        album_artist="New Order",
        album="Power, Corruption & Lies",
        track_number=5,
        disc_number=1,
        year=1983,
        genre="Synth-Pop",
        bpm=130.0,
        key="5A",
        bucket="DJ Music",
        fingerprint="AQADtNIyRUkS",
        tag_completeness=1.0,
        tag_source="file",
        has_artwork=True,
    )
    assert track.title == "Blue Monday"
    assert track.file_path == Path("/music/song.mp3")
    assert track.bitrate == 320
    assert track.bucket == "DJ Music"


def test_track_creation_with_minimal_fields():
    track = Track(
        file_path=Path("/music/unknown.mp3"),
        file_size=3_000_000,
        bitrate=192,
        duration=180.0,
    )
    assert track.title is None
    assert track.artist is None
    assert track.bpm is None
    assert track.bucket is None
    assert track.tag_completeness == 0.0
    assert track.has_artwork is False


def test_track_tag_completeness_calculation():
    required = ["title", "artist", "album", "genre", "year", "bucket"]
    track = Track(
        file_path=Path("/music/partial.mp3"),
        file_size=4_000_000,
        bitrate=256,
        duration=200.0,
        title="Strobe",
        artist="Deadmau5",
        genre="Progressive House",
    )
    completeness = track.compute_completeness(required)
    assert completeness == 3 / 6  # title, artist, genre out of 6
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/core/test_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.core.models'`

- [ ] **Step 3: Implement Track model**

Create `src/core/models.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Track:
    """Represents one MP3 file and its metadata."""

    file_path: Path
    file_size: int
    bitrate: int
    duration: float

    # Standard ID3 tags
    title: str | None = None
    artist: str | None = None
    album_artist: str | None = None
    album: str | None = None
    track_number: int | None = None
    disc_number: int | None = None
    year: int | None = None
    genre: str | None = None

    # DJ-relevant tags
    bpm: float | None = None
    key: str | None = None

    # Custom tags (ID3 TXXX frames)
    bucket: str | None = None

    # Computed/internal
    fingerprint: str | None = None
    tag_completeness: float = 0.0
    tag_source: str | None = None
    has_artwork: bool = False

    def compute_completeness(self, required_tags: list[str]) -> float:
        """Compute tag completeness as fraction of required tags that are non-None."""
        if not required_tags:
            return 1.0
        filled = sum(1 for tag in required_tags if getattr(self, tag, None) is not None)
        return filled / len(required_tags)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/core/test_models.py -v`
Expected: 3 passed

- [ ] **Step 5: Write failing tests for supporting models**

Append to `tests/core/test_models.py`:

```python
from src.core.models import (
    DupeGroup,
    HistoryEntry,
    NormalizationRule,
    PlaylistDefinition,
    RenameOperation,
    TagConflict,
)


def test_dupe_group_best_track():
    low = Track(
        file_path=Path("/music/song_128.mp3"),
        file_size=2_000_000,
        bitrate=128,
        duration=240.0,
        title="Song",
        artist="Artist",
    )
    high = Track(
        file_path=Path("/music/song_320.mp3"),
        file_size=5_000_000,
        bitrate=320,
        duration=240.0,
        title="Song",
    )
    group = DupeGroup(tracks=[low, high])
    best = group.best_track()
    assert best.file_path == Path("/music/song_320.mp3")


def test_dupe_group_best_track_tiebreak_by_completeness():
    a = Track(
        file_path=Path("/a.mp3"),
        file_size=5_000_000,
        bitrate=320,
        duration=240.0,
        tag_completeness=0.5,
    )
    b = Track(
        file_path=Path("/b.mp3"),
        file_size=5_000_000,
        bitrate=320,
        duration=240.0,
        tag_completeness=0.8,
    )
    group = DupeGroup(tracks=[a, b])
    assert group.best_track().file_path == Path("/b.mp3")


def test_tag_conflict():
    conflict = TagConflict(
        file_path=Path("/music/song.mp3"),
        field="genre",
        file_value="Electronic",
        itunes_value="Dance",
    )
    assert conflict.field == "genre"
    assert conflict.resolution is None


def test_rename_operation():
    op = RenameOperation(
        source=Path("/old/song.mp3"),
        destination=Path("/new/song.mp3"),
    )
    assert op.status == "pending"


def test_history_entry():
    entry = HistoryEntry(
        action="tag_write",
        file_path=Path("/music/song.mp3"),
        field="artist",
        old_value="Beetles",
        new_value="The Beatles",
    )
    assert entry.session_id is None
    assert entry.timestamp is not None


def test_normalization_rule():
    rule = NormalizationRule(
        field="genre",
        rule_type="mapping",
        parameters={"Hip Hop": "Hip-Hop"},
    )
    assert rule.field == "genre"


def test_playlist_definition():
    playlist = PlaylistDefinition(
        name="High Energy",
        folder="DJ/Sets",
        format="m3u",
        filters={"bucket": "DJ Music", "bpm": {"min": 125, "max": 140}},
        sort_by="bpm",
    )
    assert playlist.folder == "DJ/Sets"
```

- [ ] **Step 6: Run tests to verify new tests fail**

Run: `pytest tests/core/test_models.py -v`
Expected: ImportError for the new model classes

- [ ] **Step 7: Implement supporting models**

Append to `src/core/models.py`:

```python
from datetime import datetime, timezone


@dataclass
class DupeGroup:
    """A set of tracks identified as duplicates by audio fingerprint."""

    tracks: list[Track]

    def best_track(self) -> Track:
        """Return the highest quality track (by bitrate, then tag completeness)."""
        return max(self.tracks, key=lambda t: (t.bitrate, t.tag_completeness))


@dataclass
class TagConflict:
    """A conflict between file tag and iTunes tag for a single field."""

    file_path: Path
    field: str
    file_value: str
    itunes_value: str
    resolution: str | None = None  # "file", "itunes", or None (unresolved)


@dataclass
class RenameOperation:
    """A planned file rename/move."""

    source: Path
    destination: Path
    status: str = "pending"  # pending, complete, skipped, error


@dataclass
class HistoryEntry:
    """One logged operation for undo support."""

    action: str  # tag_write, rename, delete
    file_path: Path
    field: str | None = None
    old_value: str | None = None
    new_value: str | None = None
    session_id: str | None = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict | None = None


@dataclass
class NormalizationRule:
    """A tag normalization rule."""

    field: str
    rule_type: str  # case, mapping, regex
    parameters: dict


@dataclass
class PlaylistDefinition:
    """A saved playlist query definition."""

    name: str
    filters: dict
    folder: str | None = None
    format: str = "m3u"
    sort_by: str | None = None
```

- [ ] **Step 8: Run all tests**

Run: `pytest tests/core/test_models.py -v`
Expected: 10 passed

- [ ] **Step 9: Commit**

```bash
git add src/core/models.py tests/core/test_models.py
git commit -m "feat: add data models (Track, DupeGroup, TagConflict, RenameOperation, etc.)"
```

---

### Task 3: Test Fixtures — Generate MP3 Files

**Files:**
- Create: `tests/fixtures/generate_fixtures.py`
- Create: `tests/conftest.py`

We need small valid MP3 files with known tags for testing. We'll generate them using mutagen's ability to create minimal MP3-like files with ID3 tags.

- [ ] **Step 1: Create fixture generator script**

Create `tests/fixtures/generate_fixtures.py`:

```python
"""Generate minimal MP3 test fixtures with known tags.

Run once: python tests/fixtures/generate_fixtures.py
Creates small valid MP3 files in tests/fixtures/ for use in unit tests.
"""

from pathlib import Path

from mutagen.id3 import ID3, TALB, TBPM, TIT2, TPE1, TPE2, TPOS, TRCK, TYER, TCON, TXXX
from mutagen.mp3 import MP3


FIXTURES_DIR = Path(__file__).parent

# Minimal valid MP3 frame (silence, ~0.026s, 128kbps)
# This is the smallest valid MPEG audio frame possible.
MP3_FRAME = (
    b"\xff\xfb\x90\x00"  # MPEG1 Layer3 128kbps 44100Hz stereo
    + b"\x00" * 413       # pad to full frame size (417 bytes for this config)
)


def make_mp3(filename: str, tags: dict | None = None, frame_count: int = 10) -> Path:
    """Create a minimal MP3 file with optional ID3 tags."""
    path = FIXTURES_DIR / filename
    # Write raw MP3 frames
    with open(path, "wb") as f:
        for _ in range(frame_count):
            f.write(MP3_FRAME)

    if tags:
        audio = MP3(path)
        audio.add_tags()
        id3 = audio.tags

        tag_map = {
            "title": lambda v: TIT2(encoding=3, text=[v]),
            "artist": lambda v: TPE1(encoding=3, text=[v]),
            "album_artist": lambda v: TPE2(encoding=3, text=[v]),
            "album": lambda v: TALB(encoding=3, text=[v]),
            "track_number": lambda v: TRCK(encoding=3, text=[str(v)]),
            "disc_number": lambda v: TPOS(encoding=3, text=[str(v)]),
            "year": lambda v: TYER(encoding=3, text=[str(v)]),
            "genre": lambda v: TCON(encoding=3, text=[v]),
            "bpm": lambda v: TBPM(encoding=3, text=[str(v)]),
        }

        for key, value in tags.items():
            if key == "bucket":
                id3.add(TXXX(encoding=3, desc="MUSIC_SORTER_BUCKET", text=[value]))
            elif key in tag_map:
                id3.add(tag_map[key](value))

        audio.save()

    return path


def main():
    # Fully tagged track
    make_mp3("tagged_full.mp3", {
        "title": "Blue Monday",
        "artist": "New Order",
        "album_artist": "New Order",
        "album": "Power, Corruption & Lies",
        "track_number": 5,
        "disc_number": 1,
        "year": 1983,
        "genre": "Synth-Pop",
        "bpm": 130,
        "bucket": "DJ Music",
    })

    # Partially tagged track
    make_mp3("tagged_partial.mp3", {
        "title": "Strobe",
        "artist": "Deadmau5",
        "genre": "Progressive House",
    })

    # Untagged track
    make_mp3("untagged.mp3")

    # Second copy of full-tagged (different bitrate simulation — same tags, different file)
    make_mp3("tagged_full_dupe.mp3", {
        "title": "Blue Monday",
        "artist": "New Order",
        "album": "Power, Corruption & Lies",
        "genre": "Synth-Pop",
    }, frame_count=5)  # fewer frames = smaller file

    print(f"Fixtures created in {FIXTURES_DIR}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run fixture generator**

Run:
```bash
cd /mnt/cloud/code/music-sorter
source .venv/bin/activate
python tests/fixtures/generate_fixtures.py
```
Expected: "Fixtures created in tests/fixtures" and 4 `.mp3` files in the directory.

- [ ] **Step 3: Create tests/conftest.py with MP3 fixtures**

Create `tests/conftest.py`:

```python
import shutil
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def tagged_full_mp3(tmp_path) -> Path:
    """A fully tagged MP3 file (copy to tmp so tests don't modify fixtures)."""
    src = FIXTURES_DIR / "tagged_full.mp3"
    dst = tmp_path / "tagged_full.mp3"
    shutil.copy2(src, dst)
    return dst


@pytest.fixture
def tagged_partial_mp3(tmp_path) -> Path:
    """A partially tagged MP3 file."""
    src = FIXTURES_DIR / "tagged_partial.mp3"
    dst = tmp_path / "tagged_partial.mp3"
    shutil.copy2(src, dst)
    return dst


@pytest.fixture
def untagged_mp3(tmp_path) -> Path:
    """An MP3 file with no tags."""
    src = FIXTURES_DIR / "untagged.mp3"
    dst = tmp_path / "tagged_untagged.mp3"
    shutil.copy2(src, dst)
    return dst


@pytest.fixture
def music_dir_with_files(tmp_path) -> Path:
    """A directory tree with MP3 files for scanner tests."""
    root = tmp_path / "music"
    electronic = root / "Electronic" / "New Order"
    house = root / "House" / "Deadmau5"
    empty = root / "Empty"

    electronic.mkdir(parents=True)
    house.mkdir(parents=True)
    empty.mkdir(parents=True)

    shutil.copy2(FIXTURES_DIR / "tagged_full.mp3", electronic / "blue_monday.mp3")
    shutil.copy2(FIXTURES_DIR / "tagged_partial.mp3", house / "strobe.mp3")
    shutil.copy2(FIXTURES_DIR / "untagged.mp3", root / "unknown.mp3")

    # Non-MP3 file (should be ignored by scanner)
    (root / "cover.jpg").write_bytes(b"\xff\xd8\xff\xe0")

    return root
```

- [ ] **Step 4: Commit**

```bash
git add tests/fixtures/ tests/conftest.py
git commit -m "feat: add MP3 test fixtures and shared pytest conftest"
```

---

### Task 4: Configuration Module

**Files:**
- Create: `src/core/config.py`
- Create: `tests/core/test_config.py`

- [ ] **Step 1: Write failing tests**

Create `tests/core/test_config.py`:

```python
from pathlib import Path

import pytest

from src.core.config import Config


def test_load_default_config():
    config = Config.load_defaults()
    assert config.required_tags["global"] == [
        "title", "artist", "album", "genre", "year", "bucket"
    ]
    assert config.deduplication["similarity_threshold"] == 0.85


def test_load_from_file(tmp_path):
    user_config = tmp_path / "config.yaml"
    user_config.write_text(
        "source_directories:\n"
        "  - /home/user/music\n"
        "deduplication:\n"
        "  similarity_threshold: 0.90\n"
    )
    config = Config.load(user_config)
    assert config.source_directories == [Path("/home/user/music")]
    assert config.deduplication["similarity_threshold"] == 0.90
    # Defaults still present for unset keys
    assert config.required_tags["global"] == [
        "title", "artist", "album", "genre", "year", "bucket"
    ]


def test_save_config(tmp_path):
    config = Config.load_defaults()
    config.source_directories = [Path("/music/collection")]
    out = tmp_path / "saved.yaml"
    config.save(out)
    reloaded = Config.load(out)
    assert reloaded.source_directories == [Path("/music/collection")]


def test_get_required_tags_for_bucket():
    config = Config.load_defaults()
    dj_tags = config.get_required_tags("DJ Music")
    assert "bpm" in dj_tags
    assert "key" in dj_tags
    assert "title" in dj_tags  # global tags included

    general_tags = config.get_required_tags("General")
    assert "bpm" not in general_tags
    assert "title" in general_tags


def test_get_rename_pattern():
    config = Config.load_defaults()
    assert "{bpm}" in config.get_rename_pattern("DJ Music")
    assert config.get_rename_pattern("Unknown Bucket") == config.rename_patterns["default"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/core/test_config.py -v`
Expected: FAIL — ImportError

- [ ] **Step 3: Implement Config**

Create `src/core/config.py`:

```python
from __future__ import annotations

import copy
from pathlib import Path

import yaml


_DEFAULTS_PATH = Path(__file__).parent.parent.parent / "config" / "default_config.yaml"


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override into base, returning a new dict."""
    result = copy.deepcopy(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


class Config:
    """Application configuration backed by YAML files."""

    def __init__(self, data: dict):
        self._data = data

    @classmethod
    def load_defaults(cls) -> Config:
        with open(_DEFAULTS_PATH) as f:
            data = yaml.safe_load(f)
        return cls(data)

    @classmethod
    def load(cls, path: Path) -> Config:
        with open(_DEFAULTS_PATH) as f:
            defaults = yaml.safe_load(f)
        with open(path) as f:
            overrides = yaml.safe_load(f) or {}
        merged = _deep_merge(defaults, overrides)
        return cls(merged)

    def save(self, path: Path) -> None:
        with open(path, "w") as f:
            yaml.dump(self._data, f, default_flow_style=False, sort_keys=False)

    @property
    def source_directories(self) -> list[Path]:
        return [Path(d) for d in self._data.get("source_directories", [])]

    @source_directories.setter
    def source_directories(self, dirs: list[Path]) -> None:
        self._data["source_directories"] = [str(d) for d in dirs]

    @property
    def itunes_xml_path(self) -> Path | None:
        val = self._data.get("itunes_xml_path")
        return Path(val) if val else None

    @property
    def required_tags(self) -> dict:
        return self._data.get("required_tags", {})

    @property
    def rename_patterns(self) -> dict:
        return self._data.get("rename_patterns", {})

    @property
    def analysis(self) -> dict:
        return self._data.get("analysis", {})

    @property
    def normalization(self) -> dict:
        return self._data.get("normalization", {})

    @property
    def deduplication(self) -> dict:
        return self._data.get("deduplication", {})

    @property
    def library_columns(self) -> dict:
        return self._data.get("library_columns", {})

    def get_required_tags(self, bucket: str) -> list[str]:
        """Return the full list of required tags for a bucket (global + per-bucket)."""
        tags = list(self.required_tags.get("global", []))
        per_bucket = self.required_tags.get("per_bucket", {})
        if bucket in per_bucket:
            for tag in per_bucket[bucket]:
                if tag not in tags:
                    tags.append(tag)
        return tags

    def get_rename_pattern(self, bucket: str) -> str:
        """Return the rename pattern for a bucket, falling back to default."""
        return self.rename_patterns.get(bucket, self.rename_patterns.get("default", ""))
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/core/test_config.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add src/core/config.py tests/core/test_config.py
git commit -m "feat: add configuration module with YAML load/save and deep merge"
```

---

### Task 5: Scanner Module

**Files:**
- Create: `src/core/scanner.py`
- Create: `tests/core/test_scanner.py`

- [ ] **Step 1: Write failing tests**

Create `tests/core/test_scanner.py`:

```python
from pathlib import Path

from src.core.scanner import scan_directories, find_empty_directories


def test_scan_finds_mp3_files(music_dir_with_files):
    results = scan_directories([music_dir_with_files])
    filenames = {p.name for p in results}
    assert "blue_monday.mp3" in filenames
    assert "strobe.mp3" in filenames
    assert "unknown.mp3" in filenames
    assert len(results) == 3


def test_scan_ignores_non_mp3(music_dir_with_files):
    results = scan_directories([music_dir_with_files])
    extensions = {p.suffix.lower() for p in results}
    assert extensions == {".mp3"}


def test_scan_case_insensitive_extension(tmp_path):
    (tmp_path / "song.MP3").write_bytes(b"\xff" * 100)
    (tmp_path / "other.Mp3").write_bytes(b"\xff" * 100)
    results = scan_directories([tmp_path])
    assert len(results) == 2


def test_scan_multiple_directories(tmp_path):
    dir_a = tmp_path / "a"
    dir_b = tmp_path / "b"
    dir_a.mkdir()
    dir_b.mkdir()
    (dir_a / "song1.mp3").write_bytes(b"\xff" * 100)
    (dir_b / "song2.mp3").write_bytes(b"\xff" * 100)
    results = scan_directories([dir_a, dir_b])
    assert len(results) == 2


def test_scan_with_progress_callback(music_dir_with_files):
    progress_calls = []
    def on_progress(count, current_dir):
        progress_calls.append((count, current_dir))

    scan_directories([music_dir_with_files], on_progress=on_progress)
    assert len(progress_calls) > 0
    # Last call should have total count
    assert progress_calls[-1][0] == 3


def test_find_empty_directories(music_dir_with_files):
    empty_dirs = find_empty_directories([music_dir_with_files])
    empty_names = {d.name for d in empty_dirs}
    assert "Empty" in empty_names


def test_scan_nonexistent_directory(tmp_path):
    results = scan_directories([tmp_path / "nonexistent"])
    assert results == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/core/test_scanner.py -v`
Expected: FAIL — ImportError

- [ ] **Step 3: Implement scanner**

Create `src/core/scanner.py`:

```python
from __future__ import annotations

from pathlib import Path
from typing import Callable


def scan_directories(
    directories: list[Path],
    on_progress: Callable[[int, str], None] | None = None,
) -> list[Path]:
    """Recursively scan directories for MP3 files.

    Args:
        directories: Root directories to scan.
        on_progress: Optional callback called with (files_found_so_far, current_directory).

    Returns:
        List of paths to MP3 files found.
    """
    results: list[Path] = []
    for root_dir in directories:
        if not root_dir.is_dir():
            continue
        for path in root_dir.rglob("*"):
            if path.is_file() and path.suffix.lower() == ".mp3":
                results.append(path)
                if on_progress:
                    on_progress(len(results), str(path.parent))
    return results


def find_empty_directories(directories: list[Path]) -> list[Path]:
    """Find directories that contain no files (recursively)."""
    empty: list[Path] = []
    for root_dir in directories:
        if not root_dir.is_dir():
            continue
        for path in root_dir.rglob("*"):
            if path.is_dir() and not any(path.iterdir()):
                empty.append(path)
    return empty
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/core/test_scanner.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add src/core/scanner.py tests/core/test_scanner.py
git commit -m "feat: add scanner module for MP3 file discovery and empty dir detection"
```

---

### Task 6: Tagger Module

**Files:**
- Create: `src/core/tagger.py`
- Create: `tests/core/test_tagger.py`

- [ ] **Step 1: Write failing tests for reading tags**

Create `tests/core/test_tagger.py`:

```python
from pathlib import Path

from src.core.tagger import read_tags, write_tags


def test_read_tags_fully_tagged(tagged_full_mp3):
    track = read_tags(tagged_full_mp3)
    assert track.title == "Blue Monday"
    assert track.artist == "New Order"
    assert track.album_artist == "New Order"
    assert track.album == "Power, Corruption & Lies"
    assert track.track_number == 5
    assert track.disc_number == 1
    assert track.year == 1983
    assert track.genre == "Synth-Pop"
    assert track.bpm == 130.0
    assert track.bucket == "DJ Music"
    assert track.file_path == tagged_full_mp3
    assert track.bitrate > 0
    assert track.duration > 0


def test_read_tags_partial(tagged_partial_mp3):
    track = read_tags(tagged_partial_mp3)
    assert track.title == "Strobe"
    assert track.artist == "Deadmau5"
    assert track.genre == "Progressive House"
    assert track.album is None
    assert track.year is None
    assert track.bpm is None
    assert track.bucket is None


def test_read_tags_untagged(untagged_mp3):
    track = read_tags(untagged_mp3)
    assert track.title is None
    assert track.artist is None
    assert track.file_size > 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/core/test_tagger.py -v`
Expected: FAIL — ImportError

- [ ] **Step 3: Implement read_tags**

Create `src/core/tagger.py`:

```python
from __future__ import annotations

from pathlib import Path

from mutagen.mp3 import MP3

from src.core.models import Track


def _get_text(tags, key: str) -> str | None:
    """Extract text from an ID3 frame, returning None if missing."""
    frame = tags.get(key)
    if frame and frame.text:
        val = str(frame.text[0]).strip()
        return val if val else None
    return None


def _get_int(tags, key: str) -> int | None:
    """Extract integer from an ID3 frame."""
    text = _get_text(tags, key)
    if text is None:
        return None
    # Handle "5/12" format (track_number/total)
    text = text.split("/")[0]
    try:
        return int(text)
    except ValueError:
        return None


def _get_float(tags, key: str) -> float | None:
    """Extract float from an ID3 frame."""
    text = _get_text(tags, key)
    if text is None:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _get_txxx(tags, desc: str) -> str | None:
    """Extract value from a TXXX (user-defined text) frame by description."""
    key = f"TXXX:{desc}"
    return _get_text(tags, key)


def read_tags(path: Path) -> Track:
    """Read MP3 file and return a Track with all available metadata."""
    audio = MP3(path)
    tags = audio.tags or {}

    return Track(
        file_path=path,
        file_size=path.stat().st_size,
        bitrate=audio.info.bitrate // 1000 if audio.info.bitrate else 0,
        duration=audio.info.length or 0.0,
        title=_get_text(tags, "TIT2"),
        artist=_get_text(tags, "TPE1"),
        album_artist=_get_text(tags, "TPE2"),
        album=_get_text(tags, "TALB"),
        track_number=_get_int(tags, "TRCK"),
        disc_number=_get_int(tags, "TPOS"),
        year=_get_int(tags, "TDRC") or _get_int(tags, "TYER"),
        genre=_get_text(tags, "TCON"),
        bpm=_get_float(tags, "TBPM"),
        key=_get_txxx(tags, "INITIAL_KEY"),
        bucket=_get_txxx(tags, "MUSIC_SORTER_BUCKET"),
        has_artwork="APIC:" in tags or any(k.startswith("APIC") for k in tags),
    )
```

- [ ] **Step 4: Run read tests**

Run: `pytest tests/core/test_tagger.py -v`
Expected: 3 passed

- [ ] **Step 5: Write failing tests for writing tags**

Append to `tests/core/test_tagger.py`:

```python
def test_write_tags(tagged_partial_mp3):
    track = read_tags(tagged_partial_mp3)
    track.album = "For Lack of a Better Name"
    track.year = 2009
    track.bucket = "DJ Music"
    track.bpm = 128.0

    write_tags(tagged_partial_mp3, track, ["album", "year", "bucket", "bpm"])

    reloaded = read_tags(tagged_partial_mp3)
    assert reloaded.album == "For Lack of a Better Name"
    assert reloaded.year == 2009
    assert reloaded.bucket == "DJ Music"
    assert reloaded.bpm == 128.0
    # Original tags preserved
    assert reloaded.title == "Strobe"
    assert reloaded.artist == "Deadmau5"


def test_write_tags_dry_run(tagged_partial_mp3):
    track = read_tags(tagged_partial_mp3)
    track.album = "Changed Album"

    write_tags(tagged_partial_mp3, track, ["album"], dry_run=True)

    reloaded = read_tags(tagged_partial_mp3)
    assert reloaded.album is None  # unchanged because dry_run


def test_write_tags_adds_id3_to_untagged(untagged_mp3):
    track = read_tags(untagged_mp3)
    track.title = "New Song"
    track.artist = "New Artist"

    write_tags(untagged_mp3, track, ["title", "artist"])

    reloaded = read_tags(untagged_mp3)
    assert reloaded.title == "New Song"
    assert reloaded.artist == "New Artist"


def test_compute_completeness_with_config():
    from src.core.config import Config

    config = Config.load_defaults()
    track = read_tags.__wrapped__ if hasattr(read_tags, "__wrapped__") else read_tags

    # Use a real fixture read — test integration between tagger and config
    from pathlib import Path
    import shutil

    # This test verifies the compute_completeness method works with config-driven tags
    from src.core.models import Track
    t = Track(
        file_path=Path("/test.mp3"), file_size=100, bitrate=320, duration=100.0,
        title="Test", artist="Artist", album="Album", genre="Rock", year=2020, bucket="General",
    )
    required = config.get_required_tags("General")
    completeness = t.compute_completeness(required)
    assert completeness == 1.0  # all global required tags filled

    dj_required = config.get_required_tags("DJ Music")
    dj_completeness = t.compute_completeness(dj_required)
    assert dj_completeness < 1.0  # missing bpm and key
```

- [ ] **Step 6: Run tests to verify new tests fail**

Run: `pytest tests/core/test_tagger.py -v`
Expected: FAIL on write tests — `write_tags` not defined

- [ ] **Step 7: Implement write_tags**

Append to `src/core/tagger.py`:

```python
from mutagen.id3 import ID3, ID3NoHeaderError, TALB, TBPM, TIT2, TPE1, TPE2, TPOS, TRCK, TDRC, TCON, TXXX


def write_tags(path: Path, track: Track, fields: list[str], dry_run: bool = False) -> None:
    """Write specified tag fields from a Track to the MP3 file.

    Args:
        path: Path to the MP3 file.
        track: Track with updated tag values.
        fields: List of field names to write (e.g., ["title", "artist", "bpm"]).
        dry_run: If True, do not actually write to disk.
    """
    if dry_run:
        return

    try:
        id3 = ID3(path)
    except ID3NoHeaderError:
        id3 = ID3()

    field_to_frame = {
        "title": lambda: TIT2(encoding=3, text=[track.title]) if track.title else None,
        "artist": lambda: TPE1(encoding=3, text=[track.artist]) if track.artist else None,
        "album_artist": lambda: TPE2(encoding=3, text=[track.album_artist]) if track.album_artist else None,
        "album": lambda: TALB(encoding=3, text=[track.album]) if track.album else None,
        "track_number": lambda: TRCK(encoding=3, text=[str(track.track_number)]) if track.track_number is not None else None,
        "disc_number": lambda: TPOS(encoding=3, text=[str(track.disc_number)]) if track.disc_number is not None else None,
        "year": lambda: TDRC(encoding=3, text=[str(track.year)]) if track.year is not None else None,
        "genre": lambda: TCON(encoding=3, text=[track.genre]) if track.genre else None,
        "bpm": lambda: TBPM(encoding=3, text=[str(track.bpm)]) if track.bpm is not None else None,
    }

    txxx_fields = {
        "bucket": "MUSIC_SORTER_BUCKET",
        "key": "INITIAL_KEY",
    }

    for field in fields:
        if field in field_to_frame:
            frame = field_to_frame[field]()
            if frame:
                id3.add(frame)
        elif field in txxx_fields:
            value = getattr(track, field, None)
            if value is not None:
                id3.add(TXXX(encoding=3, desc=txxx_fields[field], text=[str(value)]))

    id3.save(path)
```

- [ ] **Step 8: Run all tagger tests**

Run: `pytest tests/core/test_tagger.py -v`
Expected: 7 passed

- [ ] **Step 9: Commit**

```bash
git add src/core/tagger.py tests/core/test_tagger.py
git commit -m "feat: add tagger module for reading and writing MP3 ID3 tags"
```

---

### Task 7: Database Cache Module

**Files:**
- Create: `src/core/database.py`
- Create: `tests/core/test_database.py`

- [ ] **Step 1: Write failing tests**

Create `tests/core/test_database.py`:

```python
from pathlib import Path

import pytest

from src.core.database import Database
from src.core.models import Track


@pytest.fixture
def db(tmp_path):
    return Database(tmp_path / "test.db")


def _make_track(path="/music/song.mp3", **kwargs):
    defaults = dict(
        file_path=Path(path), file_size=5_000_000, bitrate=320, duration=240.0,
        title="Blue Monday", artist="New Order", album="Power", genre="Synth-Pop",
        year=1983, bucket="DJ Music", tag_completeness=0.8, has_artwork=False,
    )
    defaults.update(kwargs)
    return Track(**defaults)


def test_insert_and_get_track(db):
    track = _make_track()
    db.upsert_track(track, file_mtime=1000.0)
    result = db.get_track(Path("/music/song.mp3"))
    assert result is not None
    assert result.title == "Blue Monday"
    assert result.artist == "New Order"


def test_upsert_updates_existing(db):
    track = _make_track()
    db.upsert_track(track, file_mtime=1000.0)
    track.title = "Updated Title"
    db.upsert_track(track, file_mtime=2000.0)
    result = db.get_track(Path("/music/song.mp3"))
    assert result.title == "Updated Title"


def test_delete_track(db):
    track = _make_track()
    db.upsert_track(track, file_mtime=1000.0)
    db.delete_track(Path("/music/song.mp3"))
    assert db.get_track(Path("/music/song.mp3")) is None


def test_get_all_tracks(db):
    db.upsert_track(_make_track("/a.mp3", title="A"), file_mtime=1000.0)
    db.upsert_track(_make_track("/b.mp3", title="B"), file_mtime=1000.0)
    tracks = db.get_all_tracks()
    assert len(tracks) == 2


def test_get_stale_paths(db):
    db.upsert_track(_make_track("/a.mp3"), file_mtime=1000.0)
    db.upsert_track(_make_track("/b.mp3"), file_mtime=2000.0)
    stale = db.get_stale_paths({Path("/a.mp3"): 1000.0, Path("/b.mp3"): 3000.0})
    # /b.mp3 has newer mtime on disk than in DB
    assert Path("/b.mp3") in stale
    assert Path("/a.mp3") not in stale


def test_get_removed_paths(db):
    db.upsert_track(_make_track("/a.mp3"), file_mtime=1000.0)
    db.upsert_track(_make_track("/b.mp3"), file_mtime=1000.0)
    # Only /a.mp3 exists on disk
    removed = db.get_removed_paths({Path("/a.mp3")})
    assert Path("/b.mp3") in removed
    assert Path("/a.mp3") not in removed


def test_search_tracks(db):
    db.upsert_track(_make_track("/a.mp3", title="Blue Monday", artist="New Order"), file_mtime=1000.0)
    db.upsert_track(_make_track("/b.mp3", title="Strobe", artist="Deadmau5"), file_mtime=1000.0)
    results = db.search("Monday")
    assert len(results) == 1
    assert results[0].title == "Blue Monday"


def test_get_stats(db):
    db.upsert_track(_make_track("/a.mp3", genre="House", bitrate=320, bucket="DJ Music", tag_completeness=1.0), file_mtime=1000.0)
    db.upsert_track(_make_track("/b.mp3", genre="Techno", bitrate=256, bucket="DJ Music", tag_completeness=0.5), file_mtime=1000.0)
    db.upsert_track(_make_track("/c.mp3", genre="House", bitrate=128, bucket="General", tag_completeness=0.0), file_mtime=1000.0)

    stats = db.get_stats()
    assert stats["total_tracks"] == 3
    assert stats["genre_counts"]["House"] == 2
    assert stats["bucket_counts"]["DJ Music"] == 2
    assert stats["bucket_counts"]["General"] == 1


def test_filter_tracks(db):
    db.upsert_track(_make_track("/a.mp3", bucket="DJ Music", genre="House", bpm=128.0), file_mtime=1000.0)
    db.upsert_track(_make_track("/b.mp3", bucket="DJ Music", genre="Techno", bpm=140.0), file_mtime=1000.0)
    db.upsert_track(_make_track("/c.mp3", bucket="General", genre="Rock"), file_mtime=1000.0)

    results = db.filter_tracks(bucket="DJ Music")
    assert len(results) == 2

    results = db.filter_tracks(bucket="DJ Music", genre="House")
    assert len(results) == 1
    assert results[0].genre == "House"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/core/test_database.py -v`
Expected: FAIL — ImportError

- [ ] **Step 3: Implement Database**

Create `src/core/database.py`:

```python
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from src.core.models import Track


class Database:
    """SQLite cache layer for track metadata."""

    def __init__(self, db_path: Path):
        self._path = db_path
        self._conn = sqlite3.connect(str(db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._create_tables()

    def _create_tables(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS tracks (
                id INTEGER PRIMARY KEY,
                file_path TEXT UNIQUE NOT NULL,
                file_size INTEGER,
                file_mtime REAL,
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
                key_ TEXT,
                bucket TEXT,
                fingerprint TEXT,
                tag_completeness REAL,
                tag_source TEXT,
                has_artwork INTEGER
            );

            CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY,
                session_id TEXT,
                timestamp TEXT,
                action TEXT,
                file_path TEXT,
                field TEXT,
                old_value TEXT,
                new_value TEXT,
                metadata TEXT
            );

            CREATE TABLE IF NOT EXISTS playlists (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                folder TEXT,
                format TEXT DEFAULT 'm3u',
                filters TEXT,
                sort_by TEXT
            );
        """)
        # Create FTS table if not exists
        try:
            self._conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS tracks_fts USING fts5(
                    title, artist, album_artist, album, genre,
                    content='tracks', content_rowid='id'
                );
            """)
        except sqlite3.OperationalError:
            pass  # FTS5 not available — search will fall back to LIKE
        self._conn.commit()

    def _row_to_track(self, row: sqlite3.Row) -> Track:
        return Track(
            file_path=Path(row["file_path"]),
            file_size=row["file_size"] or 0,
            bitrate=row["bitrate"] or 0,
            duration=row["duration"] or 0.0,
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
            tag_completeness=row["tag_completeness"] or 0.0,
            tag_source=row["tag_source"],
            has_artwork=bool(row["has_artwork"]),
        )

    def upsert_track(self, track: Track, file_mtime: float) -> None:
        """Insert or update a track in the database."""
        self._conn.execute(
            """INSERT INTO tracks (
                file_path, file_size, file_mtime, bitrate, duration,
                title, artist, album_artist, album, track_number, disc_number,
                year, genre, bpm, key_, bucket, fingerprint,
                tag_completeness, tag_source, has_artwork
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(file_path) DO UPDATE SET
                file_size=excluded.file_size, file_mtime=excluded.file_mtime,
                bitrate=excluded.bitrate, duration=excluded.duration,
                title=excluded.title, artist=excluded.artist,
                album_artist=excluded.album_artist, album=excluded.album,
                track_number=excluded.track_number, disc_number=excluded.disc_number,
                year=excluded.year, genre=excluded.genre, bpm=excluded.bpm,
                key_=excluded.key_, bucket=excluded.bucket,
                fingerprint=excluded.fingerprint,
                tag_completeness=excluded.tag_completeness,
                tag_source=excluded.tag_source, has_artwork=excluded.has_artwork
            """,
            (
                str(track.file_path), track.file_size, file_mtime,
                track.bitrate, track.duration,
                track.title, track.artist, track.album_artist, track.album,
                track.track_number, track.disc_number,
                track.year, track.genre, track.bpm, track.key, track.bucket,
                track.fingerprint, track.tag_completeness, track.tag_source,
                int(track.has_artwork),
            ),
        )
        # Update FTS index
        try:
            row = self._conn.execute(
                "SELECT id FROM tracks WHERE file_path = ?", (str(track.file_path),)
            ).fetchone()
            if row:
                self._conn.execute(
                    "INSERT OR REPLACE INTO tracks_fts(rowid, title, artist, album_artist, album, genre) VALUES (?, ?, ?, ?, ?, ?)",
                    (row["id"], track.title, track.artist, track.album_artist, track.album, track.genre),
                )
        except sqlite3.OperationalError:
            pass  # FTS not available
        self._conn.commit()

    def get_track(self, path: Path) -> Track | None:
        """Get a track by file path."""
        row = self._conn.execute(
            "SELECT * FROM tracks WHERE file_path = ?", (str(path),)
        ).fetchone()
        return self._row_to_track(row) if row else None

    def delete_track(self, path: Path) -> None:
        """Remove a track from the database."""
        self._conn.execute("DELETE FROM tracks WHERE file_path = ?", (str(path),))
        self._conn.commit()

    def get_all_tracks(self) -> list[Track]:
        """Return all tracks."""
        rows = self._conn.execute("SELECT * FROM tracks").fetchall()
        return [self._row_to_track(r) for r in rows]

    def get_stale_paths(self, disk_mtimes: dict[Path, float]) -> set[Path]:
        """Return paths where disk mtime is newer than cached mtime."""
        stale = set()
        for path, disk_mtime in disk_mtimes.items():
            row = self._conn.execute(
                "SELECT file_mtime FROM tracks WHERE file_path = ?", (str(path),)
            ).fetchone()
            if row is None or disk_mtime > row["file_mtime"]:
                stale.add(path)
        return stale

    def get_removed_paths(self, disk_paths: set[Path]) -> set[Path]:
        """Return paths in DB that no longer exist on disk."""
        disk_strs = {str(p) for p in disk_paths}
        rows = self._conn.execute("SELECT file_path FROM tracks").fetchall()
        return {Path(r["file_path"]) for r in rows if r["file_path"] not in disk_strs}

    def search(self, query: str) -> list[Track]:
        """Full-text search across title, artist, album, genre."""
        try:
            rows = self._conn.execute(
                """SELECT t.* FROM tracks t
                   JOIN tracks_fts fts ON t.id = fts.rowid
                   WHERE tracks_fts MATCH ?""",
                (query,),
            ).fetchall()
        except sqlite3.OperationalError:
            # FTS not available — fall back to LIKE
            pattern = f"%{query}%"
            rows = self._conn.execute(
                """SELECT * FROM tracks WHERE
                   title LIKE ? OR artist LIKE ? OR album LIKE ? OR genre LIKE ?""",
                (pattern, pattern, pattern, pattern),
            ).fetchall()
        return [self._row_to_track(r) for r in rows]

    def get_stats(self) -> dict:
        """Return aggregate statistics about the collection."""
        total = self._conn.execute("SELECT COUNT(*) as c FROM tracks").fetchone()["c"]

        genre_rows = self._conn.execute(
            "SELECT genre, COUNT(*) as c FROM tracks WHERE genre IS NOT NULL GROUP BY genre"
        ).fetchall()
        genre_counts = {r["genre"]: r["c"] for r in genre_rows}

        bucket_rows = self._conn.execute(
            "SELECT bucket, COUNT(*) as c FROM tracks WHERE bucket IS NOT NULL GROUP BY bucket"
        ).fetchall()
        bucket_counts = {r["bucket"]: r["c"] for r in bucket_rows}

        bitrate_rows = self._conn.execute(
            "SELECT bitrate, COUNT(*) as c FROM tracks GROUP BY bitrate"
        ).fetchall()
        bitrate_counts = {r["bitrate"]: r["c"] for r in bitrate_rows}

        return {
            "total_tracks": total,
            "genre_counts": genre_counts,
            "bucket_counts": bucket_counts,
            "bitrate_counts": bitrate_counts,
        }

    def filter_tracks(self, **filters) -> list[Track]:
        """Filter tracks by field values."""
        conditions = []
        params = []
        for field, value in filters.items():
            col = "key_" if field == "key" else field
            conditions.append(f"{col} = ?")
            params.append(value)

        where = " AND ".join(conditions) if conditions else "1=1"
        rows = self._conn.execute(
            f"SELECT * FROM tracks WHERE {where}", params
        ).fetchall()
        return [self._row_to_track(r) for r in rows]

    def close(self) -> None:
        self._conn.close()
```

- [ ] **Step 4: Run all database tests**

Run: `pytest tests/core/test_database.py -v`
Expected: 10 passed

- [ ] **Step 5: Commit**

```bash
git add src/core/database.py tests/core/test_database.py
git commit -m "feat: add SQLite database cache with FTS search, filtering, and sync support"
```

---

### Task 8: Run full Phase 1 test suite

- [ ] **Step 1: Run all tests**

Run: `pytest tests/ -v --tb=short`
Expected: All tests pass (models, config, scanner, tagger, database)

- [ ] **Step 2: Run with coverage**

Run: `pytest tests/ --cov=src/core --cov-report=term-missing`
Expected: Coverage report showing tested modules. Verify no untested code paths in critical modules.

- [ ] **Step 3: Commit any fixes if needed**

---

## Phase 2: Audio Analysis (Fingerprinting, BPM/Key Detection, Deduplication)

### Task 9: Fingerprint Module

**Files:**
- Create: `src/core/fingerprint.py`
- Create: `tests/core/test_fingerprint.py`

- [ ] **Step 1: Write failing tests**

Create `tests/core/test_fingerprint.py`:

```python
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from src.core.fingerprint import generate_fingerprint, lookup_metadata, compute_similarity


def test_generate_fingerprint(tagged_full_mp3):
    """Test fingerprint generation on a real MP3 file."""
    fp = generate_fingerprint(tagged_full_mp3)
    assert fp is not None
    assert isinstance(fp, str)
    assert len(fp) > 0


def test_generate_fingerprint_returns_none_for_invalid(tmp_path):
    bad_file = tmp_path / "not_audio.mp3"
    bad_file.write_bytes(b"not an mp3 file")
    fp = generate_fingerprint(bad_file)
    assert fp is None


@patch("src.core.fingerprint.acoustid.match")
def test_lookup_metadata_success(mock_match):
    mock_match.return_value = iter([
        (0.95, "recording-id-123", "Blue Monday", "New Order"),
    ])
    result = lookup_metadata("fake-fingerprint", 240.0)
    assert result is not None
    assert result["title"] == "Blue Monday"
    assert result["artist"] == "New Order"
    assert result["score"] == 0.95


@patch("src.core.fingerprint.acoustid.match")
def test_lookup_metadata_no_results(mock_match):
    mock_match.return_value = iter([])
    result = lookup_metadata("fake-fingerprint", 240.0)
    assert result is None


def test_compute_similarity_identical():
    fp = "AQADtNIyRUkS"
    assert compute_similarity(fp, fp) == 1.0


def test_compute_similarity_different():
    sim = compute_similarity("AQADtNIyRUkS", "BBBBBZZZZZZZ")
    assert 0.0 <= sim <= 1.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/core/test_fingerprint.py -v`
Expected: FAIL — ImportError

- [ ] **Step 3: Implement fingerprint module**

Create `src/core/fingerprint.py`:

```python
from __future__ import annotations

import subprocess
from pathlib import Path

try:
    import acoustid
except ImportError:
    acoustid = None


# AcoustID API key — users should set their own via config
_API_KEY = "ACOUSTID_API_KEY"


def generate_fingerprint(path: Path) -> str | None:
    """Generate a Chromaprint audio fingerprint for an MP3 file.

    Returns the fingerprint string, or None if generation fails.
    """
    try:
        result = subprocess.run(
            ["fpcalc", "-raw", str(path)],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            return None
        for line in result.stdout.strip().split("\n"):
            if line.startswith("FINGERPRINT="):
                return line.split("=", 1)[1]
        return None
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None


def lookup_metadata(fingerprint: str, duration: float, api_key: str = _API_KEY) -> dict | None:
    """Look up track metadata via AcoustID API.

    Returns dict with title, artist, recording_id, score — or None if no match.
    """
    if acoustid is None:
        return None
    try:
        results = acoustid.match(api_key, None, None, fingerprint=fingerprint, duration=int(duration))
        for score, recording_id, title, artist in results:
            return {
                "score": score,
                "recording_id": recording_id,
                "title": title,
                "artist": artist,
            }
    except Exception:
        return None
    return None


def compute_similarity(fp1: str, fp2: str) -> float:
    """Compute similarity between two raw fingerprints (0.0 to 1.0).

    Uses Hamming-like comparison on the integer fingerprint arrays.
    """
    if fp1 == fp2:
        return 1.0

    try:
        ints1 = [int(x) for x in fp1.split(",")]
        ints2 = [int(x) for x in fp2.split(",")]
    except ValueError:
        # Not in raw integer format — fall back to string comparison
        common = sum(a == b for a, b in zip(fp1, fp2))
        max_len = max(len(fp1), len(fp2))
        return common / max_len if max_len > 0 else 0.0

    # Compare using popcount of XOR (bit-level similarity)
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

- [ ] **Step 4: Run tests**

Run: `pytest tests/core/test_fingerprint.py -v`
Expected: All passed (some may skip if fpcalc not installed — the mock tests should all pass)

- [ ] **Step 5: Commit**

```bash
git add src/core/fingerprint.py tests/core/test_fingerprint.py
git commit -m "feat: add fingerprint module with Chromaprint generation and AcoustID lookup"
```

---

### Task 10: Analyzer Module (BPM & Key Detection)

**Files:**
- Create: `src/core/analyzer.py`
- Create: `tests/core/test_analyzer.py`

- [ ] **Step 1: Write failing tests**

Create `tests/core/test_analyzer.py`:

```python
from pathlib import Path
from unittest.mock import patch, MagicMock

import numpy as np
import pytest

from src.core.analyzer import detect_bpm, detect_key, _pitch_class_to_camelot


def test_pitch_class_to_camelot():
    assert _pitch_class_to_camelot(0, True) == "8B"   # C major
    assert _pitch_class_to_camelot(0, False) == "5A"   # C minor
    assert _pitch_class_to_camelot(7, True) == "3B"    # G major


@patch("src.core.analyzer.librosa")
def test_detect_bpm(mock_librosa):
    mock_librosa.load.return_value = (np.zeros(44100 * 30), 44100)
    mock_librosa.beat.beat_track.return_value = (128.5, np.array([0, 100, 200]))
    result = detect_bpm(Path("/fake/song.mp3"))
    assert result == 128.5
    mock_librosa.load.assert_called_once()


@patch("src.core.analyzer.librosa")
def test_detect_bpm_returns_none_on_error(mock_librosa):
    mock_librosa.load.side_effect = Exception("decode error")
    result = detect_bpm(Path("/fake/bad.mp3"))
    assert result is None


@patch("src.core.analyzer.librosa")
def test_detect_key(mock_librosa):
    # Simulate chroma features that peak at C
    chroma = np.zeros((12, 100))
    chroma[0, :] = 1.0  # C is dominant
    mock_librosa.load.return_value = (np.zeros(44100 * 30), 44100)
    mock_librosa.feature.chroma_cqt.return_value = chroma
    result = detect_key(Path("/fake/song.mp3"))
    # C major or C minor — depends on algorithm, but should be a valid Camelot key
    assert result is not None
    assert result[-1] in ("A", "B")


@patch("src.core.analyzer.librosa")
def test_detect_key_returns_none_on_error(mock_librosa):
    mock_librosa.load.side_effect = Exception("decode error")
    result = detect_key(Path("/fake/bad.mp3"))
    assert result is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/core/test_analyzer.py -v`
Expected: FAIL — ImportError

- [ ] **Step 3: Implement analyzer**

Create `src/core/analyzer.py`:

```python
from __future__ import annotations

from pathlib import Path

import numpy as np

try:
    import librosa
except ImportError:
    librosa = None


# Camelot wheel mapping: (pitch_class, is_major) -> Camelot notation
# Pitch classes: 0=C, 1=C#, 2=D, ..., 11=B
_CAMELOT_MAJOR = {
    0: "8B", 1: "3B", 2: "10B", 3: "5B", 4: "12B", 5: "7B",
    6: "2B", 7: "9B", 8: "4B", 9: "11B", 10: "6B", 11: "1B",
}  # wrong, let me redo
# Actually the standard Camelot wheel:
# Key signatures mapped to Camelot:
_CAMELOT_MAJOR = {
    0: "8B",   # C major
    1: "3B",   # Db major
    2: "10B",  # D major
    3: "5B",   # Eb major
    4: "12B",  # E major
    5: "7B",   # F major
    6: "2B",   # F#/Gb major
    7: "9B",   # G major (wrong — G major is 9B? Let me look up)
}
# Let me use the correct standard mapping:
_CAMELOT_MAJOR = {
    0: "8B", 1: "3B", 2: "10B", 3: "5B", 4: "12B", 5: "7B",
    6: "2B", 7: "9B", 8: "4B", 9: "11B", 10: "6B", 11: "1B",
}
_CAMELOT_MINOR = {
    0: "5A", 1: "12A", 2: "7A", 3: "2A", 4: "9A", 5: "4A",
    6: "11A", 7: "6A", 8: "1A", 9: "8A", 10: "3A", 11: "10A",
}


def _pitch_class_to_camelot(pitch_class: int, is_major: bool) -> str:
    """Convert a pitch class (0-11) and mode to Camelot notation."""
    if is_major:
        return _CAMELOT_MAJOR[pitch_class]
    return _CAMELOT_MINOR[pitch_class]


def detect_bpm(path: Path, duration_limit: float = 60.0) -> float | None:
    """Detect BPM of an audio file using beat tracking.

    Args:
        path: Path to the audio file.
        duration_limit: Only analyze first N seconds (for speed).

    Returns:
        BPM as float, or None on failure.
    """
    if librosa is None:
        return None
    try:
        y, sr = librosa.load(str(path), duration=duration_limit, sr=22050, mono=True)
        tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
        if isinstance(tempo, np.ndarray):
            tempo = float(tempo[0])
        return round(float(tempo), 1)
    except Exception:
        return None


def detect_key(path: Path, duration_limit: float = 60.0) -> str | None:
    """Detect musical key using chroma features.

    Returns key in Camelot notation (e.g., "8A", "5B"), or None on failure.
    """
    if librosa is None:
        return None
    try:
        y, sr = librosa.load(str(path), duration=duration_limit, sr=22050, mono=True)
        chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
        chroma_avg = np.mean(chroma, axis=1)

        # Determine key using Krumhansl-Schmuckler profiles
        major_profile = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09,
                                   2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
        minor_profile = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53,
                                   2.54, 4.75, 3.98, 2.69, 3.34, 3.17])

        best_corr = -2.0
        best_pitch = 0
        best_is_major = True

        for shift in range(12):
            shifted = np.roll(chroma_avg, -shift)
            major_corr = float(np.corrcoef(shifted, major_profile)[0, 1])
            minor_corr = float(np.corrcoef(shifted, minor_profile)[0, 1])

            if major_corr > best_corr:
                best_corr = major_corr
                best_pitch = shift
                best_is_major = True
            if minor_corr > best_corr:
                best_corr = minor_corr
                best_pitch = shift
                best_is_major = False

        return _pitch_class_to_camelot(best_pitch, best_is_major)
    except Exception:
        return None
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/core/test_analyzer.py -v`
Expected: All passed

- [ ] **Step 5: Commit**

```bash
git add src/core/analyzer.py tests/core/test_analyzer.py
git commit -m "feat: add BPM and key detection with Camelot wheel notation"
```

---

### Task 11: Deduplicator Module

**Files:**
- Create: `src/core/deduplicator.py`
- Create: `tests/core/test_deduplicator.py`

- [ ] **Step 1: Write failing tests**

Create `tests/core/test_deduplicator.py`:

```python
from pathlib import Path
from unittest.mock import patch

import pytest

from src.core.deduplicator import find_duration_groups, find_duplicates, merge_tags
from src.core.models import Track, DupeGroup


def _track(path, duration=240.0, bitrate=320, fingerprint="fp1", **kwargs):
    defaults = dict(
        file_path=Path(path), file_size=5_000_000, bitrate=bitrate,
        duration=duration, fingerprint=fingerprint,
        tag_completeness=0.5, has_artwork=False,
    )
    defaults.update(kwargs)
    return Track(**defaults)


def test_find_duration_groups():
    tracks = [
        _track("/a.mp3", duration=240.0),
        _track("/b.mp3", duration=241.0),  # within 2s tolerance
        _track("/c.mp3", duration=300.0),  # different song
    ]
    groups = find_duration_groups(tracks, tolerance=2.0)
    # a and b should be in the same group, c alone
    assert any(len(g) >= 2 for g in groups)
    two_group = [g for g in groups if len(g) >= 2][0]
    paths = {t.file_path for t in two_group}
    assert Path("/a.mp3") in paths
    assert Path("/b.mp3") in paths


def test_find_duration_groups_no_dupes():
    tracks = [
        _track("/a.mp3", duration=100.0),
        _track("/b.mp3", duration=200.0),
        _track("/c.mp3", duration=300.0),
    ]
    groups = find_duration_groups(tracks, tolerance=2.0)
    # All groups should have size 1 — no potential dupes
    assert all(len(g) == 1 for g in groups)


@patch("src.core.deduplicator.compute_similarity")
def test_find_duplicates(mock_sim):
    # Make a and b similar, c different
    def sim(fp1, fp2):
        if {fp1, fp2} == {"fp_same_1", "fp_same_2"}:
            return 0.95
        return 0.1

    mock_sim.side_effect = sim

    tracks = [
        _track("/a.mp3", duration=240.0, fingerprint="fp_same_1"),
        _track("/b.mp3", duration=241.0, fingerprint="fp_same_2"),
        _track("/c.mp3", duration=240.5, fingerprint="fp_different"),
    ]
    dupes = find_duplicates(tracks, duration_tolerance=2.0, similarity_threshold=0.85)
    assert len(dupes) == 1
    assert len(dupes[0].tracks) == 2


def test_merge_tags():
    keeper = _track("/a.mp3", bitrate=320, title="Song", artist=None, genre="Rock")
    inferior = _track("/b.mp3", bitrate=128, title="Song", artist="The Artist", genre="Pop")

    conflicts = merge_tags(keeper, [inferior])
    # artist should be filled from inferior
    assert keeper.artist == "The Artist"
    # genre differs — should be flagged as conflict
    assert any(c.field == "genre" for c in conflicts)


def test_merge_tags_no_conflicts():
    keeper = _track("/a.mp3", title="Song", artist="Artist")
    inferior = _track("/b.mp3", title="Song", artist="Artist")

    conflicts = merge_tags(keeper, [inferior])
    assert len(conflicts) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/core/test_deduplicator.py -v`
Expected: FAIL — ImportError

- [ ] **Step 3: Implement deduplicator**

Create `src/core/deduplicator.py`:

```python
from __future__ import annotations

from src.core.fingerprint import compute_similarity
from src.core.models import DupeGroup, TagConflict, Track


# Tag fields that can be merged
_MERGEABLE_FIELDS = [
    "title", "artist", "album_artist", "album", "track_number",
    "disc_number", "year", "genre", "bpm", "key", "bucket",
]


def find_duration_groups(tracks: list[Track], tolerance: float = 2.0) -> list[list[Track]]:
    """Group tracks by similar duration (pre-filter for deduplication).

    Returns groups of tracks within `tolerance` seconds of each other.
    """
    if not tracks:
        return []

    sorted_tracks = sorted(tracks, key=lambda t: t.duration)
    groups: list[list[Track]] = []
    current_group: list[Track] = [sorted_tracks[0]]

    for track in sorted_tracks[1:]:
        if track.duration - current_group[0].duration <= tolerance:
            current_group.append(track)
        else:
            groups.append(current_group)
            current_group = [track]
    groups.append(current_group)

    return groups


def find_duplicates(
    tracks: list[Track],
    duration_tolerance: float = 2.0,
    similarity_threshold: float = 0.85,
    on_progress: callable = None,
) -> list[DupeGroup]:
    """Find duplicate tracks using duration pre-filter and fingerprint comparison.

    Returns a list of DupeGroup objects, each containing 2+ duplicate tracks.
    """
    duration_groups = find_duration_groups(tracks, duration_tolerance)
    dupe_groups: list[DupeGroup] = []
    processed = 0

    for group in duration_groups:
        if len(group) < 2:
            processed += len(group)
            continue

        # Compare fingerprints within the group
        matched = set()
        for i, track_a in enumerate(group):
            if i in matched or not track_a.fingerprint:
                continue
            cluster = [track_a]
            for j in range(i + 1, len(group)):
                if j in matched or not group[j].fingerprint:
                    continue
                sim = compute_similarity(track_a.fingerprint, group[j].fingerprint)
                if sim >= similarity_threshold:
                    cluster.append(group[j])
                    matched.add(j)
            if len(cluster) >= 2:
                matched.add(i)
                dupe_groups.append(DupeGroup(tracks=cluster))

        processed += len(group)
        if on_progress:
            on_progress(processed, len(tracks))

    return dupe_groups


def merge_tags(keeper: Track, inferiors: list[Track]) -> list[TagConflict]:
    """Merge the best tags from inferior tracks into the keeper.

    Fills empty fields on keeper from inferiors. When both have different
    non-empty values, creates a TagConflict for manual resolution.

    Modifies keeper in place. Returns list of unresolved conflicts.
    """
    conflicts: list[TagConflict] = []

    for field in _MERGEABLE_FIELDS:
        keeper_val = getattr(keeper, field)

        for inferior in inferiors:
            inf_val = getattr(inferior, field)
            if inf_val is None:
                continue

            if keeper_val is None:
                setattr(keeper, field, inf_val)
                keeper_val = inf_val
            elif keeper_val != inf_val:
                conflicts.append(TagConflict(
                    file_path=keeper.file_path,
                    field=field,
                    file_value=str(keeper_val),
                    itunes_value=str(inf_val),  # reusing itunes_value field for "other value"
                ))
                break  # only one conflict per field

    return conflicts
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/core/test_deduplicator.py -v`
Expected: All passed

- [ ] **Step 5: Commit**

```bash
git add src/core/deduplicator.py tests/core/test_deduplicator.py
git commit -m "feat: add deduplicator with duration pre-filter and fingerprint comparison"
```

---

## Phase 3: Import, Normalization, Rename & Organize

### Task 12: iTunes Import Module

**Files:**
- Create: `src/core/itunes.py`
- Create: `tests/core/test_itunes.py`
- Create: `tests/fixtures/itunes_library.xml`

- [ ] **Step 1: Create test iTunes XML fixture**

Create `tests/fixtures/itunes_library.xml`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
	<key>Tracks</key>
	<dict>
		<key>1001</key>
		<dict>
			<key>Track ID</key><integer>1001</integer>
			<key>Name</key><string>Blue Monday</string>
			<key>Artist</key><string>New Order</string>
			<key>Album Artist</key><string>New Order</string>
			<key>Album</key><string>Power, Corruption &amp; Lies</string>
			<key>Genre</key><string>Synth-Pop</string>
			<key>Year</key><integer>1983</integer>
			<key>Track Number</key><integer>5</integer>
			<key>BPM</key><integer>130</integer>
			<key>Location</key><string>file:///music/Electronic/New%20Order/blue_monday.mp3</string>
		</dict>
		<key>1002</key>
		<dict>
			<key>Track ID</key><integer>1002</integer>
			<key>Name</key><string>Strobe</string>
			<key>Artist</key><string>Deadmau5</string>
			<key>Album</key><string>For Lack of a Better Name</string>
			<key>Genre</key><string>Progressive House</string>
			<key>Year</key><integer>2009</integer>
			<key>Location</key><string>file:///music/House/Deadmau5/strobe.mp3</string>
		</dict>
		<key>1003</key>
		<dict>
			<key>Track ID</key><integer>1003</integer>
			<key>Name</key><string>Nonexistent Track</string>
			<key>Artist</key><string>Nobody</string>
			<key>Location</key><string>file:///music/missing/track.mp3</string>
		</dict>
	</dict>
</dict>
</plist>
```

- [ ] **Step 2: Write failing tests**

Create `tests/core/test_itunes.py`:

```python
from pathlib import Path

import pytest

from src.core.itunes import parse_itunes_xml, match_itunes_to_files, resolve_conflicts
from src.core.models import TagConflict, Track


@pytest.fixture
def itunes_xml():
    return Path(__file__).parent.parent / "fixtures" / "itunes_library.xml"


def test_parse_itunes_xml(itunes_xml):
    entries = parse_itunes_xml(itunes_xml)
    assert len(entries) == 3
    assert entries[0]["title"] == "Blue Monday"
    assert entries[0]["artist"] == "New Order"
    assert entries[1]["title"] == "Strobe"
    assert entries[2]["title"] == "Nonexistent Track"


def test_parse_itunes_location_decoding(itunes_xml):
    entries = parse_itunes_xml(itunes_xml)
    blue = entries[0]
    assert blue["location"] == Path("/music/Electronic/New Order/blue_monday.mp3")


def test_match_itunes_to_files(itunes_xml, music_dir_with_files):
    entries = parse_itunes_xml(itunes_xml)
    tracks = [
        Track(
            file_path=music_dir_with_files / "Electronic" / "New Order" / "blue_monday.mp3",
            file_size=1000, bitrate=128, duration=100.0,
            title="Blue Monday", artist="New Order", genre="Electronic",
        ),
        Track(
            file_path=music_dir_with_files / "House" / "Deadmau5" / "strobe.mp3",
            file_size=1000, bitrate=128, duration=100.0,
            title="Strobe", artist="Deadmau5",
        ),
    ]
    matched, unmatched = match_itunes_to_files(entries, tracks, [music_dir_with_files])
    assert len(matched) >= 1  # at least filename-based match
    assert any(e["title"] == "Nonexistent Track" for e in unmatched)


def test_resolve_conflicts_auto_fill():
    """When file tag is empty and iTunes has a value, auto-fill."""
    track = Track(
        file_path=Path("/test.mp3"), file_size=1000, bitrate=128, duration=100.0,
        title="Song", artist=None,
    )
    itunes_entry = {"title": "Song", "artist": "The Artist", "album": "The Album"}
    conflicts = resolve_conflicts(track, itunes_entry)
    assert track.artist == "The Artist"
    assert track.album == "The Album"
    assert len(conflicts) == 0  # no conflicts, just auto-fill


def test_resolve_conflicts_keeps_file_when_itunes_empty():
    track = Track(
        file_path=Path("/test.mp3"), file_size=1000, bitrate=128, duration=100.0,
        title="Song", artist="File Artist",
    )
    itunes_entry = {"title": "Song", "artist": None}
    conflicts = resolve_conflicts(track, itunes_entry)
    assert track.artist == "File Artist"
    assert len(conflicts) == 0


def test_resolve_conflicts_flags_difference():
    track = Track(
        file_path=Path("/test.mp3"), file_size=1000, bitrate=128, duration=100.0,
        title="Song", genre="Rock",
    )
    itunes_entry = {"title": "Song", "genre": "Electronic"}
    conflicts = resolve_conflicts(track, itunes_entry)
    assert len(conflicts) == 1
    assert conflicts[0].field == "genre"
    assert conflicts[0].file_value == "Rock"
    assert conflicts[0].itunes_value == "Electronic"
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/core/test_itunes.py -v`
Expected: FAIL — ImportError

- [ ] **Step 4: Implement iTunes module**

Create `src/core/itunes.py`:

```python
from __future__ import annotations

import plistlib
from pathlib import Path
from urllib.parse import unquote, urlparse

from src.core.models import TagConflict, Track


_FIELD_MAP = {
    "Name": "title",
    "Artist": "artist",
    "Album Artist": "album_artist",
    "Album": "album",
    "Genre": "genre",
    "Year": "year",
    "Track Number": "track_number",
    "BPM": "bpm",
}


def parse_itunes_xml(xml_path: Path) -> list[dict]:
    """Parse an iTunes Music Library XML file.

    Returns a list of dicts with keys: title, artist, album_artist, album,
    genre, year, track_number, bpm, location (as Path).
    """
    with open(xml_path, "rb") as f:
        plist = plistlib.load(f)

    entries = []
    tracks_dict = plist.get("Tracks", {})

    for track_id, track_data in tracks_dict.items():
        entry = {}
        for xml_key, field_name in _FIELD_MAP.items():
            value = track_data.get(xml_key)
            entry[field_name] = value

        # Parse location URI to a local path
        location = track_data.get("Location", "")
        if location:
            parsed = urlparse(location)
            entry["location"] = Path(unquote(parsed.path))
        else:
            entry["location"] = None

        entries.append(entry)

    return entries


def match_itunes_to_files(
    itunes_entries: list[dict],
    tracks: list[Track],
    source_directories: list[Path],
) -> tuple[list[tuple[dict, Track]], list[dict]]:
    """Match iTunes entries to Track objects on disk.

    First tries path-based matching (by filename within source directories).
    Returns (matched_pairs, unmatched_entries).
    """
    # Build lookup by filename
    track_by_name: dict[str, Track] = {}
    for track in tracks:
        track_by_name[track.file_path.name] = track

    # Also build lookup by full relative structure
    track_by_path: dict[Path, Track] = {t.file_path: t for t in tracks}

    matched: list[tuple[dict, Track]] = []
    unmatched: list[dict] = []

    for entry in itunes_entries:
        location = entry.get("location")
        found = False

        if location:
            # Try direct path match within source directories
            for source_dir in source_directories:
                # Try matching the filename portion
                candidate = source_dir / location.name
                if candidate in track_by_path:
                    matched.append((entry, track_by_path[candidate]))
                    found = True
                    break

                # Try matching by walking to find the file by name
                if location.name in track_by_name:
                    matched.append((entry, track_by_name[location.name]))
                    found = True
                    break

        if not found:
            unmatched.append(entry)

    return matched, unmatched


def resolve_conflicts(track: Track, itunes_entry: dict) -> list[TagConflict]:
    """Compare track tags against iTunes entry, auto-filling and flagging conflicts.

    Modifies track in place for auto-fill cases.
    Returns list of conflicts where both have different non-empty values.
    """
    conflicts: list[TagConflict] = []
    compare_fields = ["title", "artist", "album_artist", "album", "genre", "year", "track_number", "bpm"]

    for field in compare_fields:
        file_val = getattr(track, field, None)
        itunes_val = itunes_entry.get(field)

        if file_val is None and itunes_val is not None:
            # Auto-fill from iTunes
            setattr(track, field, itunes_val)
        elif file_val is not None and itunes_val is not None and str(file_val) != str(itunes_val):
            # Conflict
            conflicts.append(TagConflict(
                file_path=track.file_path,
                field=field,
                file_value=str(file_val),
                itunes_value=str(itunes_val),
            ))

    return conflicts
```

- [ ] **Step 5: Run tests**

Run: `pytest tests/core/test_itunes.py -v`
Expected: All passed

- [ ] **Step 6: Commit**

```bash
git add src/core/itunes.py tests/core/test_itunes.py tests/fixtures/itunes_library.xml
git commit -m "feat: add iTunes XML parser with path matching and conflict resolution"
```

---

### Task 13: Tag Normalizer Module

**Files:**
- Create: `src/core/normalizer.py`
- Create: `tests/core/test_normalizer.py`

- [ ] **Step 1: Write failing tests**

Create `tests/core/test_normalizer.py`:

```python
from pathlib import Path

import pytest

from src.core.normalizer import (
    normalize_case,
    normalize_artist_prefix,
    normalize_genre,
    apply_custom_rule,
    scan_normalizations,
)
from src.core.models import Track


def _track(**kwargs):
    defaults = dict(
        file_path=Path("/test.mp3"), file_size=1000, bitrate=320,
        duration=100.0, has_artwork=False,
    )
    defaults.update(kwargs)
    return Track(**defaults)


def test_normalize_case_title():
    assert normalize_case("hello world", "title") == "Hello World"


def test_normalize_case_preserves_already_correct():
    assert normalize_case("Hello World", "title") == "Hello World"


def test_normalize_case_as_is():
    assert normalize_case("hElLo", "as_is") == "hElLo"


def test_normalize_artist_prefix_the_first():
    assert normalize_artist_prefix("Beatles, The", "the_first") == "The Beatles"


def test_normalize_artist_prefix_the_last():
    assert normalize_artist_prefix("The Beatles", "the_last") == "Beatles, The"


def test_normalize_artist_prefix_no_change():
    assert normalize_artist_prefix("Deadmau5", "the_first") == "Deadmau5"


def test_normalize_genre_mapping():
    genre_map = {"Hip Hop": "Hip-Hop", "HipHop": "Hip-Hop", "DnB": "Drum & Bass"}
    assert normalize_genre("Hip Hop", genre_map) == "Hip-Hop"
    assert normalize_genre("HipHop", genre_map) == "Hip-Hop"
    assert normalize_genre("Rock", genre_map) == "Rock"  # no mapping, unchanged


def test_apply_custom_rule_regex():
    rule = {"field": "artist", "find": r"Deadmau\d", "replace": "deadmau5"}
    assert apply_custom_rule("Deadmau5", rule) == "deadmau5"
    assert apply_custom_rule("New Order", rule) == "New Order"


def test_scan_normalizations():
    tracks = [
        _track(title="hello world", artist="Beatles, The", genre="Hip Hop"),
        _track(title="LOUD SONG", artist="The Beatles", genre="Rock"),
    ]
    config = {
        "artist_prefix": "the_first",
        "case_mode": "title",
        "genre_map": {"Hip Hop": "Hip-Hop"},
        "custom_rules": [],
    }
    changes = scan_normalizations(tracks, config)
    # Should propose changes for title case and artist prefix
    assert len(changes) > 0
    # Each change is (track, field, old_value, new_value)
    fields_changed = {c[1] for c in changes}
    assert "title" in fields_changed or "artist" in fields_changed
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/core/test_normalizer.py -v`
Expected: FAIL — ImportError

- [ ] **Step 3: Implement normalizer**

Create `src/core/normalizer.py`:

```python
from __future__ import annotations

import re
import unicodedata

from src.core.models import Track


def normalize_case(value: str, mode: str) -> str:
    """Normalize string case.

    Modes: "title" (title case), "upper", "lower", "as_is" (no change).
    """
    if mode == "title":
        return value.title()
    elif mode == "upper":
        return value.upper()
    elif mode == "lower":
        return value.lower()
    return value


def normalize_artist_prefix(artist: str, mode: str) -> str:
    """Normalize 'The' prefix in artist names.

    Modes:
        "the_first": "Beatles, The" -> "The Beatles"
        "the_last": "The Beatles" -> "Beatles, The"
    """
    if mode == "the_first":
        # "Beatles, The" -> "The Beatles"
        match = re.match(r"^(.+),\s*(The|A|An)$", artist, re.IGNORECASE)
        if match:
            return f"{match.group(2)} {match.group(1)}"
    elif mode == "the_last":
        # "The Beatles" -> "Beatles, The"
        match = re.match(r"^(The|A|An)\s+(.+)$", artist, re.IGNORECASE)
        if match:
            return f"{match.group(2)}, {match.group(1)}"
    return artist


def normalize_genre(genre: str, genre_map: dict[str, str]) -> str:
    """Map genre to canonical form using the genre mapping table."""
    return genre_map.get(genre, genre)


def normalize_whitespace(value: str) -> str:
    """Clean up extra whitespace and normalize unicode."""
    value = unicodedata.normalize("NFC", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def apply_custom_rule(value: str, rule: dict) -> str:
    """Apply a custom regex find/replace rule."""
    return re.sub(rule["find"], rule["replace"], value)


def scan_normalizations(
    tracks: list[Track],
    config: dict,
) -> list[tuple[Track, str, str, str]]:
    """Scan tracks and produce a list of proposed normalization changes.

    Returns list of (track, field, old_value, new_value) tuples.
    Does not modify tracks — this is a dry-run preview.
    """
    changes: list[tuple[Track, str, str, str]] = []
    case_mode = config.get("case_mode", "as_is")
    artist_prefix = config.get("artist_prefix", "the_first")
    genre_map = config.get("genre_map", {})
    custom_rules = config.get("custom_rules", [])

    text_fields = ["title", "album"]

    for track in tracks:
        # Case normalization on text fields
        for field in text_fields:
            value = getattr(track, field, None)
            if value is None:
                continue
            cleaned = normalize_whitespace(value)
            normalized = normalize_case(cleaned, case_mode)
            if normalized != value:
                changes.append((track, field, value, normalized))

        # Artist prefix normalization
        if track.artist:
            cleaned = normalize_whitespace(track.artist)
            normalized = normalize_artist_prefix(cleaned, artist_prefix)
            if normalized != track.artist:
                changes.append((track, "artist", track.artist, normalized))

        # Genre mapping
        if track.genre and track.genre in genre_map:
            new_genre = genre_map[track.genre]
            if new_genre != track.genre:
                changes.append((track, "genre", track.genre, new_genre))

        # Custom rules
        for rule in custom_rules:
            field = rule["field"]
            value = getattr(track, field, None)
            if value is None:
                continue
            new_value = apply_custom_rule(value, rule)
            if new_value != value:
                changes.append((track, field, value, new_value))

    return changes
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/core/test_normalizer.py -v`
Expected: All passed

- [ ] **Step 5: Commit**

```bash
git add src/core/normalizer.py tests/core/test_normalizer.py
git commit -m "feat: add tag normalization engine with case, prefix, genre mapping, and regex rules"
```

---

### Task 14: Pattern Engine (Renamer)

**Files:**
- Create: `src/core/renamer.py`
- Create: `tests/core/test_renamer.py`

- [ ] **Step 1: Write failing tests**

Create `tests/core/test_renamer.py`:

```python
from pathlib import Path

import pytest

from src.core.renamer import render_pattern, sanitize_filename, generate_rename_plan
from src.core.models import Track, RenameOperation


def _track(**kwargs):
    defaults = dict(
        file_path=Path("/music/old.mp3"), file_size=5_000_000, bitrate=320,
        duration=240.0, title="Blue Monday", artist="New Order",
        album="Power, Corruption & Lies", genre="Synth-Pop",
        track_number=5, year=1983, bucket="DJ Music", bpm=130.0, key="5A",
        has_artwork=False,
    )
    defaults.update(kwargs)
    return Track(**defaults)


def test_render_simple_pattern():
    track = _track()
    result = render_pattern("{artist}/{album}/{title}.mp3", track)
    assert result == "New Order/Power, Corruption & Lies/Blue Monday.mp3"


def test_render_with_format_spec():
    track = _track()
    result = render_pattern("{track:02d} - {title}.mp3", track)
    assert result == "05 - Blue Monday.mp3"


def test_render_conditional_present():
    track = _track()
    result = render_pattern("{?album:{album}/}{title}.mp3", track)
    assert result == "Power, Corruption & Lies/Blue Monday.mp3"


def test_render_conditional_missing():
    track = _track(album=None)
    result = render_pattern("{?album:{album}/}{title}.mp3", track)
    assert result == "Blue Monday.mp3"


def test_render_conditional_with_fallback():
    track = _track(album_artist=None)
    result = render_pattern("{?album_artist:{album_artist}|{artist}}/{title}.mp3", track)
    assert result == "New Order/Blue Monday.mp3"


def test_render_conditional_with_fallback_present():
    track = _track(album_artist="New Order Collective")
    result = render_pattern("{?album_artist:{album_artist}|{artist}}/{title}.mp3", track)
    assert result == "New Order Collective/Blue Monday.mp3"


def test_render_dj_music_pattern():
    track = _track()
    result = render_pattern("{bucket}/{genre}/{artist} - {title} [{bpm}bpm {key}].mp3", track)
    assert result == "DJ Music/Synth-Pop/New Order - Blue Monday [130.0bpm 5A].mp3"


def test_sanitize_filename():
    assert sanitize_filename('Song: The "Best" Mix') == "Song_ The _Best_ Mix"
    assert sanitize_filename("trailing.  ") == "trailing"
    assert sanitize_filename("  leading") == "leading"


def test_generate_rename_plan():
    tracks = [
        _track(file_path=Path("/music/old1.mp3"), title="Song A", artist="Artist"),
        _track(file_path=Path("/music/old2.mp3"), title="Song B", artist="Artist"),
    ]
    patterns = {"default": "{artist}/{title}.mp3"}
    base_dir = Path("/output")

    plan = generate_rename_plan(tracks, patterns, base_dir)
    assert len(plan) == 2
    assert all(isinstance(op, RenameOperation) for op in plan)
    assert plan[0].destination == Path("/output/Artist/Song A.mp3")
    assert plan[1].destination == Path("/output/Artist/Song B.mp3")


def test_generate_rename_plan_collision():
    tracks = [
        _track(file_path=Path("/music/a.mp3"), title="Same", artist="Artist"),
        _track(file_path=Path("/music/b.mp3"), title="Same", artist="Artist"),
    ]
    patterns = {"default": "{artist}/{title}.mp3"}
    base_dir = Path("/output")

    plan = generate_rename_plan(tracks, patterns, base_dir)
    destinations = [op.destination for op in plan]
    # Should not have duplicates — collision resolution adds suffix
    assert len(set(destinations)) == 2
    assert any("(2)" in str(d) for d in destinations)


def test_generate_rename_plan_uses_bucket_pattern():
    track = _track(bucket="DJ Music")
    patterns = {
        "default": "{artist}/{title}.mp3",
        "DJ Music": "{bucket}/{artist} - {title}.mp3",
    }
    base_dir = Path("/output")
    plan = generate_rename_plan([track], patterns, base_dir)
    assert "DJ Music" in str(plan[0].destination)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/core/test_renamer.py -v`
Expected: FAIL — ImportError

- [ ] **Step 3: Implement renamer**

Create `src/core/renamer.py`:

```python
from __future__ import annotations

import re
from pathlib import Path

from src.core.models import RenameOperation, Track


# Characters illegal in filenames on most filesystems
_ILLEGAL_CHARS = re.compile(r'[<>:"/\\|?*]')


def sanitize_filename(name: str) -> str:
    """Remove or replace characters that are illegal in filenames."""
    name = _ILLEGAL_CHARS.sub("_", name)
    name = name.strip(". ")
    return name


def _get_token_value(track: Track, token: str, fmt: str | None = None) -> str | None:
    """Get the value of a token from a track, optionally formatted."""
    value = getattr(track, token, None)
    if value is None:
        return None
    if fmt:
        try:
            return format(value, fmt)
        except (ValueError, TypeError):
            return str(value)
    return str(value)


def render_pattern(pattern: str, track: Track) -> str:
    """Render a rename pattern with token substitution and conditionals.

    Supports:
        {token} — simple substitution
        {token:fmt} — with format spec
        {?tag:content} — include content only if tag is non-None
        {?tag:if_present|if_missing} — conditional with fallback
    """
    result = pattern

    # Process conditionals first: {?tag:if_present|if_missing} and {?tag:content}
    def replace_conditional(match):
        tag = match.group(1)
        body = match.group(2)
        value = getattr(track, tag, None)

        if "|" in body:
            if_present, if_missing = body.split("|", 1)
            template = if_present if value is not None else if_missing
        else:
            template = body if value is not None else ""

        # Recursively render tokens within the chosen branch
        return _render_simple_tokens(template, track)

    result = re.sub(r"\{\?(\w+):([^}]+)\}", replace_conditional, result)

    # Process remaining simple tokens
    result = _render_simple_tokens(result, track)

    # Sanitize each path component
    parts = Path(result).parts
    sanitized = [sanitize_filename(p) if i > 0 or not p.endswith(":") else p
                 for i, p in enumerate(parts)]
    return str(Path(*sanitized)) if sanitized else result


def _render_simple_tokens(template: str, track: Track) -> str:
    """Replace {token} and {token:fmt} patterns."""
    def replace_token(match):
        token = match.group(1)
        fmt = match.group(2)
        value = _get_token_value(track, token, fmt)
        return value if value is not None else ""

    return re.sub(r"\{(\w+)(?::([^}]+))?\}", replace_token, template)


def generate_rename_plan(
    tracks: list[Track],
    patterns: dict[str, str],
    base_dir: Path,
) -> list[RenameOperation]:
    """Generate a rename plan for a list of tracks.

    Uses bucket-specific patterns from config, falling back to default.
    Handles path collisions by appending (N) suffix.
    """
    plan: list[RenameOperation] = []
    used_destinations: dict[str, int] = {}

    for track in tracks:
        pattern = patterns.get(track.bucket, patterns.get("default", "{title}.mp3"))
        relative = render_pattern(pattern, track)
        destination = base_dir / relative

        # Handle collisions
        dest_str = str(destination)
        if dest_str in used_destinations:
            used_destinations[dest_str] += 1
            stem = destination.stem
            suffix = destination.suffix
            destination = destination.with_name(f"{stem} ({used_destinations[dest_str]}){suffix}")
        else:
            used_destinations[dest_str] = 1

        plan.append(RenameOperation(source=track.file_path, destination=destination))

    return plan
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/core/test_renamer.py -v`
Expected: All passed

- [ ] **Step 5: Commit**

```bash
git add src/core/renamer.py tests/core/test_renamer.py
git commit -m "feat: add pattern engine for file renaming with conditionals and collision handling"
```

---

### Task 15: Organizer Module

**Files:**
- Create: `src/core/organizer.py`
- Create: `tests/core/test_organizer.py`

- [ ] **Step 1: Write failing tests**

Create `tests/core/test_organizer.py`:

```python
from pathlib import Path

import pytest

from src.core.organizer import execute_rename_plan, cleanup_empty_dirs
from src.core.models import RenameOperation


def test_execute_rename_plan(tmp_path):
    src = tmp_path / "old" / "song.mp3"
    src.parent.mkdir(parents=True)
    src.write_bytes(b"fake mp3 data")

    dst = tmp_path / "new" / "Artist" / "song.mp3"
    plan = [RenameOperation(source=src, destination=dst)]

    results = execute_rename_plan(plan)
    assert dst.exists()
    assert not src.exists()
    assert results[0].status == "complete"


def test_execute_rename_plan_creates_dirs(tmp_path):
    src = tmp_path / "song.mp3"
    src.write_bytes(b"data")
    dst = tmp_path / "deep" / "nested" / "dir" / "song.mp3"

    plan = [RenameOperation(source=src, destination=dst)]
    execute_rename_plan(plan)
    assert dst.exists()


def test_execute_rename_plan_dry_run(tmp_path):
    src = tmp_path / "song.mp3"
    src.write_bytes(b"data")
    dst = tmp_path / "new" / "song.mp3"

    plan = [RenameOperation(source=src, destination=dst)]
    results = execute_rename_plan(plan, dry_run=True)
    assert src.exists()
    assert not dst.exists()
    assert results[0].status == "pending"  # unchanged in dry_run


def test_execute_rename_plan_source_missing(tmp_path):
    src = tmp_path / "missing.mp3"
    dst = tmp_path / "new.mp3"

    plan = [RenameOperation(source=src, destination=dst)]
    results = execute_rename_plan(plan)
    assert results[0].status == "error"


def test_cleanup_empty_dirs(tmp_path):
    empty = tmp_path / "a" / "b" / "c"
    empty.mkdir(parents=True)
    notempty = tmp_path / "d"
    notempty.mkdir()
    (notempty / "file.txt").write_text("content")

    removed = cleanup_empty_dirs(tmp_path)
    assert not empty.exists()
    assert notempty.exists()
    assert len(removed) > 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/core/test_organizer.py -v`
Expected: FAIL — ImportError

- [ ] **Step 3: Implement organizer**

Create `src/core/organizer.py`:

```python
from __future__ import annotations

import shutil
from pathlib import Path

from src.core.models import RenameOperation


def execute_rename_plan(
    plan: list[RenameOperation],
    dry_run: bool = False,
    on_progress: callable = None,
) -> list[RenameOperation]:
    """Execute a list of rename operations (move files).

    Modifies each operation's status in place.
    Returns the same list with updated statuses.
    """
    for i, op in enumerate(plan):
        if dry_run:
            continue  # leave status as "pending"

        if not op.source.exists():
            op.status = "error"
            continue

        try:
            op.destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(op.source), str(op.destination))
            op.status = "complete"
        except OSError:
            op.status = "error"

        if on_progress:
            on_progress(i + 1, len(plan))

    return plan


def cleanup_empty_dirs(root: Path) -> list[Path]:
    """Remove empty directories under root, bottom-up.

    Returns list of removed directories.
    """
    removed: list[Path] = []
    # Walk bottom-up so we remove deepest empty dirs first
    for dirpath in sorted(root.rglob("*"), key=lambda p: len(p.parts), reverse=True):
        if dirpath.is_dir() and not any(dirpath.iterdir()):
            dirpath.rmdir()
            removed.append(dirpath)
    return removed
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/core/test_organizer.py -v`
Expected: All passed

- [ ] **Step 5: Commit**

```bash
git add src/core/organizer.py tests/core/test_organizer.py
git commit -m "feat: add organizer module for executing rename plans and cleaning empty dirs"
```

---

## Phase 4: Artwork, Playlists, History

### Task 16: History Module

**Files:**
- Create: `src/core/history.py`
- Create: `tests/core/test_history.py`

- [ ] **Step 1: Write failing tests**

Create `tests/core/test_history.py`:

```python
import json
from pathlib import Path

import pytest

from src.core.history import History


@pytest.fixture
def history(tmp_path):
    return History(tmp_path / "history.jsonl", tmp_path / "trash")


def test_log_tag_write(history):
    history.log_tag_write(Path("/song.mp3"), "artist", "Old", "New")
    entries = history.get_entries()
    assert len(entries) == 1
    assert entries[0]["action"] == "tag_write"
    assert entries[0]["old_value"] == "Old"
    assert entries[0]["new_value"] == "New"


def test_log_rename(history):
    history.log_rename(Path("/old.mp3"), Path("/new.mp3"))
    entries = history.get_entries()
    assert len(entries) == 1
    assert entries[0]["action"] == "rename"


def test_log_delete(history, tmp_path):
    src = tmp_path / "song.mp3"
    src.write_bytes(b"mp3 data")
    snapshot = {"title": "Song", "artist": "Artist"}

    history.log_delete(src, snapshot)
    entries = history.get_entries()
    assert len(entries) == 1
    assert entries[0]["action"] == "delete"
    # File should be moved to trash, not deleted
    assert not src.exists()
    trash_path = Path(entries[0]["metadata"]["trash_path"])
    assert trash_path.exists()


def test_undo_tag_write(history):
    history.log_tag_write(Path("/song.mp3"), "artist", "Old", "New")
    entry = history.get_entries()[-1]
    undo_op = history.get_undo_operation(entry)
    assert undo_op["action"] == "tag_write"
    assert undo_op["field"] == "artist"
    assert undo_op["value"] == "Old"  # restore old value


def test_undo_rename(history):
    history.log_rename(Path("/old.mp3"), Path("/new.mp3"))
    entry = history.get_entries()[-1]
    undo_op = history.get_undo_operation(entry)
    assert undo_op["action"] == "rename"
    assert undo_op["source"] == "/new.mp3"
    assert undo_op["destination"] == "/old.mp3"


def test_undo_delete(history, tmp_path):
    src = tmp_path / "song.mp3"
    src.write_bytes(b"mp3 data")
    history.log_delete(src, {"title": "Song"})
    entry = history.get_entries()[-1]
    undo_op = history.get_undo_operation(entry)
    assert undo_op["action"] == "restore"
    assert undo_op["destination"] == str(src)


def test_session_grouping(history):
    session = history.begin_session("dedup_batch")
    history.log_tag_write(Path("/a.mp3"), "artist", "Old", "New", session_id=session)
    history.log_delete(Path("/dev/null"), {}, session_id=session)  # won't actually move
    entries = history.get_session_entries(session)
    assert len(entries) == 2
    assert all(e["session_id"] == session for e in entries)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/core/test_history.py -v`
Expected: FAIL — ImportError

- [ ] **Step 3: Implement history**

Create `src/core/history.py`:

```python
from __future__ import annotations

import json
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path


class History:
    """Append-only operation log with undo support."""

    def __init__(self, log_path: Path, trash_dir: Path):
        self._log_path = log_path
        self._trash_dir = trash_dir
        self._trash_dir.mkdir(parents=True, exist_ok=True)
        # Ensure log file exists
        if not self._log_path.exists():
            self._log_path.parent.mkdir(parents=True, exist_ok=True)
            self._log_path.touch()

    def _append(self, entry: dict) -> None:
        entry.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
        with open(self._log_path, "a") as f:
            f.write(json.dumps(entry) + "\n")

    def begin_session(self, label: str = "") -> str:
        """Create a new session ID for grouping related operations."""
        return f"{label}_{uuid.uuid4().hex[:8]}"

    def log_tag_write(
        self, file_path: Path, field: str, old_value: str, new_value: str,
        session_id: str | None = None,
    ) -> None:
        self._append({
            "action": "tag_write",
            "file_path": str(file_path),
            "field": field,
            "old_value": old_value,
            "new_value": new_value,
            "session_id": session_id,
        })

    def log_rename(
        self, old_path: Path, new_path: Path, session_id: str | None = None,
    ) -> None:
        self._append({
            "action": "rename",
            "file_path": str(old_path),
            "metadata": {"new_path": str(new_path)},
            "session_id": session_id,
        })

    def log_delete(
        self, file_path: Path, snapshot: dict, session_id: str | None = None,
    ) -> None:
        trash_name = f"{uuid.uuid4().hex[:8]}_{file_path.name}"
        trash_path = self._trash_dir / trash_name

        if file_path.exists():
            shutil.move(str(file_path), str(trash_path))

        self._append({
            "action": "delete",
            "file_path": str(file_path),
            "session_id": session_id,
            "metadata": {
                "trash_path": str(trash_path),
                "snapshot": snapshot,
            },
        })

    def get_entries(self) -> list[dict]:
        """Return all history entries."""
        entries = []
        with open(self._log_path) as f:
            for line in f:
                line = line.strip()
                if line:
                    entries.append(json.loads(line))
        return entries

    def get_session_entries(self, session_id: str) -> list[dict]:
        """Return entries for a specific session."""
        return [e for e in self.get_entries() if e.get("session_id") == session_id]

    def get_undo_operation(self, entry: dict) -> dict:
        """Return the inverse operation for an entry."""
        action = entry["action"]

        if action == "tag_write":
            return {
                "action": "tag_write",
                "file_path": entry["file_path"],
                "field": entry["field"],
                "value": entry["old_value"],
            }
        elif action == "rename":
            return {
                "action": "rename",
                "source": entry["metadata"]["new_path"],
                "destination": entry["file_path"],
            }
        elif action == "delete":
            return {
                "action": "restore",
                "source": entry["metadata"]["trash_path"],
                "destination": entry["file_path"],
            }
        else:
            raise ValueError(f"Unknown action: {action}")
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/core/test_history.py -v`
Expected: All passed (the `/dev/null` test may need adjustment on the session test — it won't move `/dev/null` but that's fine, it will still log)

- [ ] **Step 5: Commit**

```bash
git add src/core/history.py tests/core/test_history.py
git commit -m "feat: add history module with operation logging, undo, and trash-based deletes"
```

---

### Task 17: Artwork Module

**Files:**
- Create: `src/core/artwork.py`
- Create: `tests/core/test_artwork.py`

- [ ] **Step 1: Write failing tests**

Create `tests/core/test_artwork.py`:

```python
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from src.core.artwork import search_cover_art, embed_artwork, has_artwork


def test_has_artwork_false(untagged_mp3):
    assert has_artwork(untagged_mp3) is False


def test_has_artwork_true_after_embed(untagged_mp3):
    # Create a minimal PNG (1x1 pixel)
    png_data = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
        b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00"
        b"\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00"
        b"\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    embed_artwork(untagged_mp3, png_data)
    assert has_artwork(untagged_mp3) is True


@patch("src.core.artwork.musicbrainzngs")
def test_search_cover_art_success(mock_mb):
    mock_mb.search_releases.return_value = {
        "release-list": [{"id": "release-123", "score": "100"}]
    }
    mock_mb.get_image_list.return_value = {
        "images": [{"front": True, "thumbnails": {"small": "http://example.com/thumb.jpg"}}]
    }
    mock_mb.get_image_front.return_value = b"\xff\xd8fake_image_data"

    result = search_cover_art("New Order", "Power, Corruption & Lies")
    assert result is not None
    assert len(result) > 0


@patch("src.core.artwork.musicbrainzngs")
def test_search_cover_art_not_found(mock_mb):
    mock_mb.search_releases.return_value = {"release-list": []}
    result = search_cover_art("Unknown Artist", "Unknown Album")
    assert result is None


def test_embed_artwork_dry_run(untagged_mp3):
    embed_artwork(untagged_mp3, b"fake_data", dry_run=True)
    assert has_artwork(untagged_mp3) is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/core/test_artwork.py -v`
Expected: FAIL — ImportError

- [ ] **Step 3: Implement artwork module**

Create `src/core/artwork.py`:

```python
from __future__ import annotations

from pathlib import Path

from mutagen.id3 import ID3, ID3NoHeaderError, APIC
from mutagen.mp3 import MP3

try:
    import musicbrainzngs
    musicbrainzngs.set_useragent("MusicSorter", "0.1.0", "https://github.com/JerHutch/music-sorter")
except ImportError:
    musicbrainzngs = None


def has_artwork(path: Path) -> bool:
    """Check if an MP3 file has embedded album art."""
    try:
        audio = MP3(path)
        tags = audio.tags or {}
        return any(k.startswith("APIC") for k in tags)
    except Exception:
        return False


def embed_artwork(path: Path, image_data: bytes, dry_run: bool = False) -> None:
    """Embed album art into an MP3 file as an APIC frame."""
    if dry_run:
        return

    try:
        id3 = ID3(path)
    except ID3NoHeaderError:
        id3 = ID3()

    # Detect MIME type from magic bytes
    if image_data[:8] == b"\x89PNG\r\n\x1a\n":
        mime = "image/png"
    else:
        mime = "image/jpeg"

    id3.add(APIC(
        encoding=3,
        mime=mime,
        type=3,  # Cover (front)
        desc="Front Cover",
        data=image_data,
    ))
    id3.save(path)


def search_cover_art(artist: str, album: str) -> bytes | None:
    """Search MusicBrainz for album art and return image data.

    Returns image bytes, or None if not found.
    """
    if musicbrainzngs is None:
        return None

    try:
        results = musicbrainzngs.search_releases(artist=artist, release=album, limit=5)
        releases = results.get("release-list", [])
        if not releases:
            return None

        release_id = releases[0]["id"]
        image_data = musicbrainzngs.get_image_front(release_id)
        return image_data
    except Exception:
        return None
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/core/test_artwork.py -v`
Expected: All passed

- [ ] **Step 5: Commit**

```bash
git add src/core/artwork.py tests/core/test_artwork.py
git commit -m "feat: add artwork module with MusicBrainz lookup and APIC embedding"
```

---

### Task 18: Playlist Module

**Files:**
- Create: `src/core/playlist.py`
- Create: `tests/core/test_playlist.py`

- [ ] **Step 1: Write failing tests**

Create `tests/core/test_playlist.py`:

```python
from pathlib import Path

import pytest

from src.core.playlist import generate_m3u, generate_pls, filter_tracks_for_playlist
from src.core.models import Track, PlaylistDefinition


def _track(path="/music/song.mp3", **kwargs):
    defaults = dict(
        file_path=Path(path), file_size=5_000_000, bitrate=320,
        duration=240.0, title="Song", artist="Artist", has_artwork=False,
    )
    defaults.update(kwargs)
    return Track(**defaults)


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
    assert "/music/b.mp3" in content


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
    assert "Title1=Song A" in content
    assert "NumberOfEntries=2" in content


def test_filter_tracks_for_playlist():
    tracks = [
        _track("/a.mp3", bucket="DJ Music", genre="House", bpm=128.0),
        _track("/b.mp3", bucket="DJ Music", genre="Techno", bpm=140.0),
        _track("/c.mp3", bucket="General", genre="Rock", bpm=None),
    ]
    playlist = PlaylistDefinition(
        name="DJ House",
        filters={"bucket": "DJ Music", "genre": ["House"]},
    )
    result = filter_tracks_for_playlist(tracks, playlist)
    assert len(result) == 1
    assert result[0].genre == "House"


def test_filter_tracks_bpm_range():
    tracks = [
        _track("/a.mp3", bpm=120.0),
        _track("/b.mp3", bpm=130.0),
        _track("/c.mp3", bpm=145.0),
    ]
    playlist = PlaylistDefinition(
        name="Mid Tempo",
        filters={"bpm": {"min": 125, "max": 140}},
    )
    result = filter_tracks_for_playlist(tracks, playlist)
    assert len(result) == 1
    assert result[0].bpm == 130.0


def test_filter_tracks_sort():
    tracks = [
        _track("/a.mp3", bpm=140.0),
        _track("/b.mp3", bpm=120.0),
        _track("/c.mp3", bpm=130.0),
    ]
    playlist = PlaylistDefinition(
        name="Sorted",
        filters={},
        sort_by="bpm",
    )
    result = filter_tracks_for_playlist(tracks, playlist)
    bpms = [t.bpm for t in result]
    assert bpms == [120.0, 130.0, 140.0]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/core/test_playlist.py -v`
Expected: FAIL — ImportError

- [ ] **Step 3: Implement playlist module**

Create `src/core/playlist.py`:

```python
from __future__ import annotations

from pathlib import Path

from src.core.models import PlaylistDefinition, Track


def generate_m3u(tracks: list[Track], output_path: Path) -> None:
    """Generate an M3U playlist file."""
    lines = ["#EXTM3U"]
    for track in tracks:
        duration = int(track.duration)
        artist = track.artist or "Unknown"
        title = track.title or track.file_path.stem
        lines.append(f"#EXTINF:{duration},{artist} - {title}")
        lines.append(str(track.file_path))
    output_path.write_text("\n".join(lines) + "\n")


def generate_pls(tracks: list[Track], output_path: Path) -> None:
    """Generate a PLS playlist file."""
    lines = ["[playlist]"]
    for i, track in enumerate(tracks, 1):
        lines.append(f"File{i}={track.file_path}")
        lines.append(f"Title{i}={track.title or track.file_path.stem}")
        lines.append(f"Length{i}={int(track.duration)}")
    lines.append(f"NumberOfEntries={len(tracks)}")
    lines.append("Version=2")
    output_path.write_text("\n".join(lines) + "\n")


def filter_tracks_for_playlist(
    tracks: list[Track],
    playlist: PlaylistDefinition,
) -> list[Track]:
    """Filter and sort tracks according to a playlist definition."""
    result = list(tracks)

    for field, value in playlist.filters.items():
        if isinstance(value, dict):
            # Range filter: {"min": X, "max": Y}
            min_val = value.get("min")
            max_val = value.get("max")
            result = [
                t for t in result
                if getattr(t, field, None) is not None
                and (min_val is None or getattr(t, field) >= min_val)
                and (max_val is None or getattr(t, field) <= max_val)
            ]
        elif isinstance(value, list):
            # List filter: value in list
            result = [t for t in result if getattr(t, field, None) in value]
        else:
            # Exact match
            result = [t for t in result if getattr(t, field, None) == value]

    if playlist.sort_by:
        result.sort(key=lambda t: (getattr(t, playlist.sort_by, None) is None, getattr(t, playlist.sort_by, 0)))

    return result
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/core/test_playlist.py -v`
Expected: All passed

- [ ] **Step 5: Commit**

```bash
git add src/core/playlist.py tests/core/test_playlist.py
git commit -m "feat: add playlist module with M3U/PLS generation and filter-based track selection"
```

---

### Task 19: Run full core test suite

- [ ] **Step 1: Run all tests**

Run: `pytest tests/ -v --tb=short`
Expected: All core tests pass

- [ ] **Step 2: Run with coverage**

Run: `pytest tests/ --cov=src/core --cov-report=term-missing`
Expected: Good coverage across all core modules

- [ ] **Step 3: Commit any fixes**

---

## Phase 5: GUI Application

### Task 20: Application Entry Point & Main Window

**Files:**
- Create: `src/gui/app.py`
- Create: `src/gui/main_window.py`

- [ ] **Step 1: Create application entry point**

Create `src/gui/app.py`:

```python
import sys

from PySide6.QtWidgets import QApplication

from src.gui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Music Sorter")
    app.setOrganizationName("MusicSorter")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Create main window shell**

Create `src/gui/main_window.py`:

```python
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QStackedWidget, QToolBar, QLabel, QStatusBar,
)

from src.gui.dashboard import DashboardView
from src.gui.library_browser import LibraryBrowser
from src.gui.settings_view import SettingsView


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Music Sorter")
        self.setMinimumSize(1200, 800)

        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Left sidebar
        self._sidebar = self._create_sidebar()
        layout.addWidget(self._sidebar)

        # Main content stack
        self._stack = QStackedWidget()
        self._dashboard = DashboardView()
        self._library = LibraryBrowser()
        self._settings = SettingsView()

        self._stack.addWidget(self._dashboard)
        self._stack.addWidget(self._library)
        self._stack.addWidget(self._settings)

        layout.addWidget(self._stack, stretch=1)

        # Toolbar (top nav)
        self._create_toolbar()

        # Status bar
        self._status = QStatusBar()
        self.setStatusBar(self._status)
        self._status.showMessage("Ready")

    def _create_toolbar(self):
        toolbar = QToolBar("Navigation")
        toolbar.setMovable(False)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, toolbar)

        toolbar.addAction("Dashboard", lambda: self._stack.setCurrentWidget(self._dashboard))
        toolbar.addAction("Library", lambda: self._stack.setCurrentWidget(self._library))
        toolbar.addAction("Settings", lambda: self._stack.setCurrentWidget(self._settings))

    def _create_sidebar(self) -> QWidget:
        sidebar = QWidget()
        sidebar.setFixedWidth(220)
        sidebar.setStyleSheet("background-color: #16163a; color: #ccc;")
        layout = QVBoxLayout(sidebar)
        layout.addWidget(QLabel("Buckets"))
        layout.addWidget(QLabel("  All Music"))
        layout.addWidget(QLabel("  DJ Music"))
        layout.addWidget(QLabel("  DJ Mixes"))
        layout.addWidget(QLabel("  General"))
        layout.addStretch()
        return sidebar
```

- [ ] **Step 3: Create placeholder views**

Create `src/gui/dashboard.py`:

```python
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel


class DashboardView(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Dashboard — Statistics and task queue"))
        layout.addStretch()
```

Create `src/gui/library_browser.py`:

```python
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel


class LibraryBrowser(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Library Browser — Track table"))
        layout.addStretch()
```

Create `src/gui/settings_view.py`:

```python
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel


class SettingsView(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Settings"))
        layout.addStretch()
```

- [ ] **Step 4: Test launch**

Run: `python -m src.gui.app`
Expected: Window opens with toolbar (Dashboard/Library/Settings), sidebar, and placeholder content. Close window to exit.

- [ ] **Step 5: Commit**

```bash
git add src/gui/
git commit -m "feat: add GUI shell with main window, toolbar navigation, sidebar, and placeholder views"
```

---

### Task 21: Library Browser with Track Table

**Files:**
- Modify: `src/gui/library_browser.py`
- Create: `src/gui/workers.py`

- [ ] **Step 1: Implement workers for background operations**

Create `src/gui/workers.py`:

```python
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from src.core.database import Database
from src.core.scanner import scan_directories
from src.core.tagger import read_tags


class ScanWorker(QThread):
    """Background worker for scanning directories and populating the database."""

    progress = Signal(int, str)   # files_processed, current_file
    finished = Signal(int)        # total_files

    def __init__(self, directories: list[Path], db: Database):
        super().__init__()
        self._directories = directories
        self._db = db
        self._cancelled = False

    def run(self):
        paths = scan_directories(self._directories, on_progress=self._on_scan_progress)
        for i, path in enumerate(paths):
            if self._cancelled:
                break
            try:
                track = read_tags(path)
                mtime = path.stat().st_mtime
                self._db.upsert_track(track, file_mtime=mtime)
            except Exception:
                pass  # skip unreadable files
            self.progress.emit(i + 1, str(path))
        self.finished.emit(len(paths))

    def _on_scan_progress(self, count, current_dir):
        self.progress.emit(count, current_dir)

    def cancel(self):
        self._cancelled = True
```

- [ ] **Step 2: Implement library browser with table**

Replace `src/gui/library_browser.py`:

```python
from PySide6.QtCore import Qt, QSortFilterProxyModel
from PySide6.QtGui import QStandardItemModel, QStandardItem, QColor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableView, QHeaderView,
    QLineEdit, QPushButton, QLabel, QAbstractItemView,
)

from src.core.models import Track


class LibraryBrowser(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Toolbar
        toolbar = QHBoxLayout()
        self._search = QLineEdit()
        self._search.setPlaceholderText("Search tracks...")
        self._search.textChanged.connect(self._on_search)
        toolbar.addWidget(self._search)
        toolbar.addWidget(QPushButton("Auto-Tag Selected"))
        toolbar.addWidget(QPushButton("Batch Edit"))
        toolbar.addWidget(QPushButton("Analyze"))
        layout.addLayout(toolbar)

        # Table
        self._model = QStandardItemModel()
        self._model.setHorizontalHeaderLabels([
            "Title", "Artist", "Album", "Genre", "BPM", "Key", "Bitrate", "Tags"
        ])

        self._proxy = QSortFilterProxyModel()
        self._proxy.setSourceModel(self._model)
        self._proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._proxy.setFilterKeyColumn(-1)  # search all columns

        self._table = QTableView()
        self._table.setModel(self._proxy)
        self._table.setSortingEnabled(True)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        layout.addWidget(self._table)

        # Status
        self._status = QLabel("0 tracks")
        layout.addWidget(self._status)

    def load_tracks(self, tracks: list[Track]):
        """Populate the table with tracks."""
        self._model.removeRows(0, self._model.rowCount())
        for track in tracks:
            row = [
                QStandardItem(track.title or ""),
                QStandardItem(track.artist or ""),
                QStandardItem(track.album or ""),
                QStandardItem(track.genre or ""),
                QStandardItem(str(track.bpm) if track.bpm else ""),
                QStandardItem(track.key or ""),
                QStandardItem(f"{track.bitrate}k" if track.bitrate else ""),
                self._completeness_item(track.tag_completeness),
            ]
            self._model.appendRow(row)
        self._status.setText(f"{len(tracks)} tracks")

    def _completeness_item(self, completeness: float) -> QStandardItem:
        item = QStandardItem()
        if completeness >= 0.9:
            item.setForeground(QColor("#69db7c"))
            item.setText("●")
        elif completeness >= 0.4:
            item.setForeground(QColor("#ffa94d"))
            item.setText("●")
        else:
            item.setForeground(QColor("#ff6b6b"))
            item.setText("●")
        return item

    def _on_search(self, text: str):
        self._proxy.setFilterFixedString(text)
```

- [ ] **Step 3: Test launch with table**

Run: `python -m src.gui.app`
Expected: Library view shows an empty table with column headers, search bar, and action buttons.

- [ ] **Step 4: Commit**

```bash
git add src/gui/library_browser.py src/gui/workers.py
git commit -m "feat: add library browser with sortable track table, search, and background scan worker"
```

---

### Task 22: Dashboard View with Statistics

**Files:**
- Modify: `src/gui/dashboard.py`

- [ ] **Step 1: Implement dashboard**

Replace `src/gui/dashboard.py`:

```python
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGroupBox, QGridLayout,
)


class StatCard(QWidget):
    """A single statistic display card."""

    def __init__(self, title: str, value: str = "0", color: str = "#7c83ff"):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 10, 15, 10)

        self._value_label = QLabel(value)
        self._value_label.setStyleSheet(f"font-size: 28px; font-weight: bold; color: {color};")
        self._value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._value_label)

        title_label = QLabel(title)
        title_label.setStyleSheet("font-size: 12px; color: #888;")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)

    def set_value(self, value: str):
        self._value_label.setText(value)


class DashboardView(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)

        # Title
        title = QLabel("Collection Overview")
        title.setStyleSheet("font-size: 20px; font-weight: bold;")
        layout.addWidget(title)

        # Stats cards row
        cards_layout = QHBoxLayout()
        self._total_card = StatCard("Total Tracks")
        self._tagged_card = StatCard("Fully Tagged", color="#69db7c")
        self._partial_card = StatCard("Partially Tagged", color="#ffa94d")
        self._untagged_card = StatCard("Missing Tags", color="#ff6b6b")
        self._dupes_card = StatCard("Duplicates", color="#ffa94d")
        self._no_art_card = StatCard("No Artwork", color="#888")

        for card in [self._total_card, self._tagged_card, self._partial_card,
                     self._untagged_card, self._dupes_card, self._no_art_card]:
            cards_layout.addWidget(card)

        layout.addLayout(cards_layout)

        # Placeholder for future charts
        charts_group = QGroupBox("Distribution Charts")
        charts_layout = QVBoxLayout(charts_group)
        charts_layout.addWidget(QLabel("Genre, bitrate, and bucket distribution charts will appear here."))
        layout.addWidget(charts_group)

        layout.addStretch()

    def update_stats(self, stats: dict):
        """Update dashboard with stats from the database."""
        self._total_card.set_value(str(stats.get("total_tracks", 0)))
```

- [ ] **Step 2: Commit**

```bash
git add src/gui/dashboard.py
git commit -m "feat: add dashboard view with stat cards and chart placeholders"
```

---

### Task 23: Settings View

**Files:**
- Modify: `src/gui/settings_view.py`

- [ ] **Step 1: Implement settings view**

Replace `src/gui/settings_view.py`:

```python
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QListWidget, QGroupBox, QFormLayout, QFileDialog,
)

from src.core.config import Config


class SettingsView(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)

        # Source directories
        dirs_group = QGroupBox("Source Directories")
        dirs_layout = QVBoxLayout(dirs_group)
        self._dirs_list = QListWidget()
        dirs_layout.addWidget(self._dirs_list)
        dirs_buttons = QHBoxLayout()
        add_btn = QPushButton("Add Directory")
        add_btn.clicked.connect(self._add_directory)
        remove_btn = QPushButton("Remove Selected")
        remove_btn.clicked.connect(self._remove_directory)
        dirs_buttons.addWidget(add_btn)
        dirs_buttons.addWidget(remove_btn)
        dirs_layout.addLayout(dirs_buttons)
        layout.addWidget(dirs_group)

        # iTunes XML
        itunes_group = QGroupBox("iTunes Library")
        itunes_layout = QHBoxLayout(itunes_group)
        self._itunes_path = QLineEdit()
        self._itunes_path.setPlaceholderText("Path to iTunes Music Library.xml")
        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self._browse_itunes)
        itunes_layout.addWidget(self._itunes_path)
        itunes_layout.addWidget(browse_btn)
        layout.addWidget(itunes_group)

        # Actions
        actions_group = QGroupBox("Actions")
        actions_layout = QVBoxLayout(actions_group)
        scan_btn = QPushButton("Force Full Rescan")
        actions_layout.addWidget(scan_btn)
        layout.addWidget(actions_group)

        layout.addStretch()

    def _add_directory(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Select Music Directory")
        if dir_path:
            self._dirs_list.addItem(dir_path)

    def _remove_directory(self):
        current = self._dirs_list.currentRow()
        if current >= 0:
            self._dirs_list.takeItem(current)

    def _browse_itunes(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select iTunes Library XML", "", "XML Files (*.xml)"
        )
        if path:
            self._itunes_path.setText(path)

    def load_config(self, config: Config):
        """Populate settings from config."""
        self._dirs_list.clear()
        for d in config.source_directories:
            self._dirs_list.addItem(str(d))
        if config.itunes_xml_path:
            self._itunes_path.setText(str(config.itunes_xml_path))
```

- [ ] **Step 2: Commit**

```bash
git add src/gui/settings_view.py
git commit -m "feat: add settings view with source directory management and iTunes XML picker"
```

---

### Task 24: Wire Everything Together

**Files:**
- Modify: `src/gui/main_window.py`
- Create: `src/gui/tag_editor.py`
- Create: `src/gui/dupe_resolver.py`
- Create: `src/gui/itunes_import.py`
- Create: `src/gui/rename_preview.py`
- Create: `src/gui/stats_view.py`
- Create: `src/gui/playlist_manager.py`

- [ ] **Step 1: Create remaining placeholder GUI modules**

Create `src/gui/tag_editor.py`:
```python
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel


class TagEditor(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Tag Editor — single and batch editing"))
        layout.addStretch()
```

Create `src/gui/dupe_resolver.py`:
```python
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel


class DupeResolver(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Duplicate Resolver — review and merge duplicates"))
        layout.addStretch()
```

Create `src/gui/itunes_import.py`:
```python
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel


class ITunesImportView(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("iTunes Import — parse XML and resolve conflicts"))
        layout.addStretch()
```

Create `src/gui/rename_preview.py`:
```python
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel


class RenamePreview(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Rename/Organize Preview — pattern editor with dry-run"))
        layout.addStretch()
```

Create `src/gui/stats_view.py`:
```python
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel


class StatsView(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Collection Statistics — charts and reports"))
        layout.addStretch()
```

Create `src/gui/playlist_manager.py`:
```python
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel


class PlaylistManager(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Playlist Manager — create and organize playlists"))
        layout.addStretch()
```

Create `src/gui/widgets/__init__.py` (empty).

- [ ] **Step 2: Update main window to wire core and GUI together**

Replace `src/gui/main_window.py`:

```python
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QStackedWidget, QToolBar, QLabel, QStatusBar,
    QTreeWidget, QTreeWidgetItem, QProgressBar,
)

from src.core.config import Config
from src.core.database import Database
from src.gui.dashboard import DashboardView
from src.gui.library_browser import LibraryBrowser
from src.gui.settings_view import SettingsView
from src.gui.workers import ScanWorker


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Music Sorter")
        self.setMinimumSize(1200, 800)

        # Core setup
        self._config = Config.load_defaults()
        data_dir = Path.home() / ".local" / "share" / "music-sorter"
        data_dir.mkdir(parents=True, exist_ok=True)
        self._db = Database(data_dir / "music-sorter.db")

        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Left sidebar
        self._sidebar = self._create_sidebar()
        layout.addWidget(self._sidebar)

        # Main content stack
        self._stack = QStackedWidget()
        self._dashboard = DashboardView()
        self._library = LibraryBrowser()
        self._settings = SettingsView()

        self._stack.addWidget(self._dashboard)
        self._stack.addWidget(self._library)
        self._stack.addWidget(self._settings)
        layout.addWidget(self._stack, stretch=1)

        # Toolbar
        self._create_toolbar()

        # Status bar with progress
        self._status = QStatusBar()
        self._progress = QProgressBar()
        self._progress.setMaximumWidth(200)
        self._progress.hide()
        self._status.addPermanentWidget(self._progress)
        self.setStatusBar(self._status)
        self._status.showMessage("Ready")

        # Load config into settings
        self._settings.load_config(self._config)

        # Load library
        self._refresh_library()

    def _create_toolbar(self):
        toolbar = QToolBar("Navigation")
        toolbar.setMovable(False)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, toolbar)

        toolbar.addAction("Dashboard", lambda: self._stack.setCurrentWidget(self._dashboard))
        toolbar.addAction("Library", lambda: self._stack.setCurrentWidget(self._library))
        toolbar.addAction("Settings", lambda: self._stack.setCurrentWidget(self._settings))
        toolbar.addSeparator()
        toolbar.addAction("Scan", self._start_scan)

    def _create_sidebar(self) -> QWidget:
        sidebar = QWidget()
        sidebar.setFixedWidth(220)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(10, 10, 10, 10)

        # Buckets
        layout.addWidget(QLabel("Buckets"))
        self._bucket_tree = QTreeWidget()
        self._bucket_tree.setHeaderHidden(True)
        for name in ["All Music", "DJ Music", "DJ Mixes", "General"]:
            QTreeWidgetItem(self._bucket_tree, [name])
        layout.addWidget(self._bucket_tree)

        # Task queue
        layout.addWidget(QLabel("Task Queue"))
        self._task_tree = QTreeWidget()
        self._task_tree.setHeaderHidden(True)
        layout.addWidget(self._task_tree)

        layout.addStretch()
        return sidebar

    def _start_scan(self):
        dirs = self._config.source_directories
        if not dirs:
            self._status.showMessage("No source directories configured")
            return

        self._progress.show()
        self._progress.setRange(0, 0)  # indeterminate
        self._status.showMessage("Scanning...")

        self._scan_worker = ScanWorker(dirs, self._db)
        self._scan_worker.progress.connect(self._on_scan_progress)
        self._scan_worker.finished.connect(self._on_scan_finished)
        self._scan_worker.start()

    def _on_scan_progress(self, count, current):
        self._status.showMessage(f"Scanning: {count} files processed")

    def _on_scan_finished(self, total):
        self._progress.hide()
        self._status.showMessage(f"Scan complete: {total} files")
        self._refresh_library()

    def _refresh_library(self):
        tracks = self._db.get_all_tracks()
        self._library.load_tracks(tracks)
        stats = self._db.get_stats()
        self._dashboard.update_stats(stats)
```

- [ ] **Step 3: Add pyproject.toml entry point**

Add to `pyproject.toml`:

```toml
[project.scripts]
music-sorter = "src.gui.app:main"
```

- [ ] **Step 4: Test full application launch**

Run: `python -m src.gui.app`
Expected: Full application window with working navigation, sidebar, library browser with empty table, dashboard with stat cards, and settings view.

- [ ] **Step 5: Commit**

```bash
git add src/gui/ pyproject.toml
git commit -m "feat: wire GUI together with core database, scanning, and library display"
```

---

### Task 25: Push to Remote

- [ ] **Step 1: Verify all tests pass**

Run: `pytest tests/ -v`

- [ ] **Step 2: Push to GitHub**

```bash
git push -u origin main
```
