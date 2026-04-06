# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```sh
# Run all tests
pytest

# Run a single test file
pytest tests/core/test_tagger.py

# Run with coverage
pytest --cov=src --cov-report=term-missing

# Launch the app
music-sorter
# or
python -m src.gui.app
```

**System dependency required for fingerprinting:** `chromaprint` (pacman, apt, or brew).

## Architecture

```
src/
├── core/    # Pure Python — no Qt. All business logic.
└── gui/     # PySide6 — thin rendering and dispatch layer.
```

The strict core/GUI separation is the central design constraint: all `src/core/` modules must remain importable without Qt. GUI tests require a display or Xvfb; core tests do not.

### Core modules

| Module | Responsibility |
|---|---|
| `models.py` | Dataclasses: `Track`, `DupeGroup`, `TagConflict`, `RenameOperation`, `HistoryEntry`, `NormalizationRule`, `PlaylistDefinition` |
| `database.py` | SQLite cache (`~/.local/share/music-sorter/library.db`), FTS5 search, track upsert |
| `config.py` | YAML config with deep-merge defaults; user config at `~/.config/music-sorter/config.yaml` |
| `scanner.py` | Recursive MP3 discovery |
| `tagger.py` | mutagen-based ID3 read/write; computes `tag_completeness` |
| `analyzer.py` | BPM and key detection via librosa |
| `fingerprint.py` | Audio fingerprinting via pyacoustid + chromaprint |
| `deduplicator.py` | Fingerprint-based duplicate grouping |
| `organizer.py` | File rename/move execution |
| `renamer.py` | Pattern-based filename generation |
| `normalizer.py` | Tag normalization rules engine |
| `history.py` | Operation log and undo support |
| `playlist.py` | Smart playlist generation (M3U/PLS) |
| `artwork.py` | Album art fetch (MusicBrainz) and embed |
| `itunes.py` | iTunes XML parse, match, and conflict resolution |

### GUI modules

| Module | Responsibility |
|---|---|
| `main_window.py` | Top-level `QMainWindow`; owns `Config`, `Database`, worker threads; routes to page stack |
| `workers.py` | `QThread` subclasses: `ScanWorker`, `AnalyzeWorker`, `TagWriteWorker` |
| `library_browser.py` | Sortable track table with sidebar filter and live bucket counts |
| `dashboard.py` | Collection overview stats |
| `tag_editor.py` | Single and batch tag editing UI |
| `dupe_resolver.py` | Duplicate review and merge UI |
| `rename_preview.py` | Rename/organize preview |
| `itunes_import.py` | iTunes import and conflict resolution UI |
| `playlist_manager.py` | Playlist creation and management UI |
| `stats_view.py` | Charts (QtCharts) |
| `settings_view.py` | Config editor; emits `settings_changed` signal |

### Data flow

`MainWindow` loads `Config` and `Database` on startup. Background operations run in `workers.py` `QThread` subclasses that emit `Signal`s back to the main thread. `Database` is thread-safe (uses a lock internally). All file operations go through `core/` and are logged to `history` for undo.

### Key domain concepts

- **`bucket`** — custom ID3 TXXX frame used as a DJ-style crate/category tag
- **`tag_completeness`** — fraction of required tags (configurable) that are non-None, stored in DB
- **`fingerprint`** — Chromaprint acoustic fingerprint stored on `Track`; used for deduplication
- `DupeGroup.best_track()` picks highest bitrate, then highest completeness

## Test fixtures

Real (tiny) MP3 files live in `tests/fixtures/`: `tagged_full.mp3`, `tagged_partial.mp3`, `untagged.mp3`. The `tests/conftest.py` fixtures copy these to `tmp_path` before each test so originals are never mutated.
