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
