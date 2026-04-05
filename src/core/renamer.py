from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from src.core.models import RenameOperation, Track

# Characters forbidden in filenames on Windows/cross-platform
_FORBIDDEN = re.compile(r'[<>:"/\\|?*]')

# Token aliases: pattern token -> Track attribute name
_TOKEN_ALIASES = {
    "track": "track_number",
    "disc": "disc_number",
}

import logging
logger = logging.getLogger(__name__)


def sanitize_filename(name: str) -> str:
    """Replace forbidden characters with '_', strip leading/trailing spaces and trailing dots."""
    name = _FORBIDDEN.sub("_", name)
    # Strip leading spaces and trailing spaces/dots
    name = name.lstrip(" ").rstrip(". ")
    return name


def _get_track_value(track: Track, token: str) -> Any:
    """Resolve a token name to a Track field value, handling aliases."""
    attr = _TOKEN_ALIASES.get(token, token)
    return getattr(track, attr, None)


def _expand_inner(inner: str, track: Track) -> str:
    """Expand simple {token} and {token:format} references within a string."""
    def replace_token(m: re.Match) -> str:
        token = m.group(1)
        fmt = m.group(2)
        value = _get_track_value(track, token)
        if value is None:
            return ""
        if fmt:
            return format(value, fmt)
        return str(value)

    return re.sub(r"\{(\w+)(?::([^}]+))?\}", replace_token, inner)


# Matches simple tokens: {token} or {token:format}
_TOKEN_RE = re.compile(r"\{(\w+)(?::([^}]+))?\}")


def _parse_conditionals(pattern: str, track: Track) -> str:
    """Parse and expand conditional blocks {?tag:body} where body may contain nested braces."""
    result = []
    i = 0
    n = len(pattern)

    while i < n:
        # Look for {? start
        if pattern[i] == "{" and i + 1 < n and pattern[i + 1] == "?":
            # Find the tag name (up to the colon)
            colon_pos = pattern.index(":", i + 2)
            tag = pattern[i + 2:colon_pos]

            # Now find the matching closing } by tracking brace depth
            depth = 1
            j = colon_pos + 1
            while j < n and depth > 0:
                if pattern[j] == "{":
                    depth += 1
                elif pattern[j] == "}":
                    depth -= 1
                j += 1
            # j is now one past the closing }
            body = pattern[colon_pos + 1:j - 1]

            value = _get_track_value(track, tag)

            # Check for top-level | (fallback separator) in body
            depth2 = 0
            split_idx = None
            for k, ch in enumerate(body):
                if ch == "{":
                    depth2 += 1
                elif ch == "}":
                    depth2 -= 1
                elif ch == "|" and depth2 == 0:
                    split_idx = k
                    break

            if split_idx is not None:
                if_present = body[:split_idx]
                if_missing = body[split_idx + 1:]
                if value is not None:
                    result.append(_expand_inner(if_present, track))
                else:
                    result.append(_expand_inner(if_missing, track))
            else:
                if value is not None:
                    result.append(_expand_inner(body, track))
                # else: omit entirely

            i = j
        else:
            result.append(pattern[i])
            i += 1

    return "".join(result)


def render_pattern(pattern: str, track: Track) -> str:
    """Render a filename pattern using track metadata.

    Supports:
    - Simple tokens: {artist}, {title}, {year}
    - Format specs: {track:02d}
    - Conditionals: {?album:{album}/} - include if album is set
    - Conditionals with fallback: {?album_artist:{album_artist}|{artist}}
    """
    # First pass: expand conditionals
    result = _parse_conditionals(pattern, track)

    # Second pass: expand simple tokens
    def expand_token(m: re.Match) -> str:
        token = m.group(1)
        fmt = m.group(2)
        value = _get_track_value(track, token)
        if value is None:
            return ""
        if fmt:
            return format(value, fmt)
        return str(value)

    result = _TOKEN_RE.sub(expand_token, result)
    return result


def _sanitize_path_components(rendered: str) -> str:
    """Sanitize each path component individually, preserving '/' separators."""
    parts = rendered.split("/")
    sanitized = [sanitize_filename(p) for p in parts]
    return "/".join(sanitized)


def generate_rename_plan(
    tracks: list[Track],
    patterns: dict[str, str],
    base_dir: Path,
) -> list[RenameOperation]:
    """Generate a list of RenameOperation objects for the given tracks.

    Picks the bucket-specific pattern if available, else falls back to 'default'.
    Handles destination collisions by appending (2), (3), etc.
    """
    logger.debug("Generating rename plan for %d tracks", len(tracks))
    used_destinations: set[Path] = set()
    operations: list[RenameOperation] = []

    for track in tracks:
        # Select pattern: bucket-specific first, then default
        bucket = track.bucket
        pattern = patterns.get(bucket, patterns.get("default", "{title}.mp3")) if bucket else patterns.get("default", "{title}.mp3")

        rendered = render_pattern(pattern, track)
        rendered = _sanitize_path_components(rendered)

        destination = base_dir / rendered

        # Handle collisions
        if destination in used_destinations:
            stem = destination.stem
            suffix = destination.suffix
            parent = destination.parent
            counter = 2
            while destination in used_destinations:
                destination = parent / f"{stem} ({counter}){suffix}"
                counter += 1

        used_destinations.add(destination)
        operations.append(RenameOperation(source=track.file_path, destination=destination))

    logger.info("Rename plan generated: %d operation%s", len(operations), "" if len(operations) == 1 else "s")
    return operations
