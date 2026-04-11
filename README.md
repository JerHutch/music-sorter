# Music Sorter

A desktop application for organizing, tagging, deduplicating, and restructuring MP3 music collections. Built for large libraries (10,000+ files) with DJ-specific workflows in mind.

**Not a music player.** Music Sorter manages your collection metadata and file organization.

## Features

| Feature | Status |
|---|---|
| Library scanner with incremental rescan | Implemented |
| Tag reading/writing (ID3v1, ID3v2.3, ID3v2.4) | Implemented |
| SQLite cache with fast startup | Implemented |
| Library browser with sortable columns | Implemented |
| Dashboard with collection overview | Implemented |
| Settings/configuration UI | Implemented |
| Background scan worker | Implemented |
| BPM and key detection (librosa) | Implemented |
| Audio fingerprinting (Chromaprint/AcoustID) | Implemented |
| Duplicate detection and merge logic | Implemented |
| iTunes XML import and conflict resolution | Implemented |
| File renaming with pattern engine | Implemented |
| Folder reorganization | Implemented |
| Tag normalization rules engine | Implemented |
| Smart playlist generation (M3U/PLS) | Implemented |
| Album artwork fetch and embed (MusicBrainz) | Implemented |
| Operation history and undo | Implemented |
| Tag editor UI (single and batch) | Implemented |
| Duplicate resolver UI | Implemented |
| iTunes import UI | Implemented |
| Rename/organize preview UI | Implemented |
| Statistics charts view | Implemented |
| Playlist manager UI | Implemented |
| Sidebar live counts and filtering | Implemented |
| Configurable column visibility and order | Implemented |

## Requirements

**Python:** 3.12 or newer

**System dependency — chromaprint:**
```sh
# Arch / CachyOS / Manjaro
pacman -S chromaprint

# Ubuntu / Debian
apt install libchromaprint-tools

# macOS (Homebrew)
brew install chromaprint
```

## Installation

[uv](https://docs.astral.sh/uv/) is required. Install it with:

```sh
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Then:

```sh
# Clone the repository
git clone <repo-url>
cd music-sorter

# Install all dependencies (including dev tools) into .venv
uv sync
```

## Running

```sh
uv run music-sorter

# Or directly
uv run python -m src.gui.app
```

## Development

```sh
# Run all tests
uv run pytest

# Run with coverage report
uv run pytest --cov=src --cov-report=term-missing

# Run a specific test file
uv run pytest tests/core/test_tagger.py

# Add a dependency
uv add <package>

# Add a dev-only dependency
uv add --dev <package>
```

The core library (`src/core/`) has no Qt dependency and can be tested without a display. GUI tests use `pytest-qt` and require a running display or a virtual framebuffer (e.g. `Xvfb`).

## Configuration

On first launch, Music Sorter uses built-in defaults. User settings are saved to:

- **Linux:** `~/.config/music-sorter/config.yaml`
- **Database cache:** `~/.local/share/music-sorter/library.db`

See [Configuration Reference](docs/guides/configuration.md) for all available options.

## Documentation

- [Getting Started](docs/guides/getting-started.md) — first launch, scanning your library, basic workflows
- [Library Browser](docs/guides/library-browser.md) — browsing, searching, and filtering tracks
- [Tag Editing](docs/guides/tag-editing.md) — editing tags for single tracks and in bulk
- [Duplicate Resolution](docs/guides/deduplication.md) — finding and merging duplicate files
- [iTunes Import](docs/guides/itunes-import.md) — importing metadata from an iTunes XML library
- [Renaming and Organizing](docs/guides/rename-organize.md) — pattern-based file renaming and folder restructuring
- [Tag Normalization](docs/guides/normalization.md) — cleaning up inconsistent tag values
- [Playlist Manager](docs/guides/playlists.md) — creating smart playlists by filter criteria
- [Artwork](docs/guides/artwork.md) — fetching and embedding album art
- [Configuration Reference](docs/guides/configuration.md) — all config options explained
- [Undo and History](docs/guides/history.md) — reviewing and reversing operations

## Architecture

```
src/
├── core/       # Pure Python library — no Qt. All business logic lives here.
└── gui/        # PySide6 frontend — thin rendering and dispatch layer.
```

The core/GUI separation means all core logic is testable without a display. See [docs/superpowers/specs/2026-04-04-music-sorter-design.md](docs/superpowers/specs/2026-04-04-music-sorter-design.md) for the full design specification.

## Tech Stack

- **GUI:** PySide6 (Qt6)
- **Tag I/O:** mutagen
- **Audio fingerprinting:** pyacoustid + chromaprint (system)
- **BPM / key detection:** librosa
- **Metadata lookup:** musicbrainzngs
- **Database:** SQLite (stdlib)
- **Configuration:** PyYAML
- **Charts:** PySide6.QtCharts (bundled with PySide6)
- **Tests:** pytest + pytest-cov + pytest-qt
- **Package manager:** uv
