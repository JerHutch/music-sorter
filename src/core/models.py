from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field as dc_field
from datetime import datetime, timezone
from pathlib import Path


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
    rules: list[SimpleRule | RuleGroup]


@dataclass
class SmartPlaylist:
    """A named smart playlist with a rule tree."""

    name: str
    conjunction: str = "AND"
    rules: list = dc_field(default_factory=list)  # list[SimpleRule | RuleGroup]
    limit_count: int | None = None
    limit_order: str | None = None
    sort_by: str | None = None
    folder: str | None = None
    format: str = "m3u"
    show_in_sidebar: bool = True


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
    date_added: float | None = None  # Unix timestamp (time.time()) set on first scan

    def compute_completeness(self, required_tags: list[str]) -> float:
        """Compute tag completeness as fraction of required tags that are non-None."""
        if not required_tags:
            return 1.0
        filled = sum(1 for tag in required_tags if getattr(self, tag, None) is not None)
        return filled / len(required_tags)


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
    timestamp: str = dc_field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
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
