from __future__ import annotations
import re
import unicodedata
from src.core.models import Track

def normalize_case(value: str, mode: str) -> str:
    if mode == "title": return value.title()
    elif mode == "upper": return value.upper()
    elif mode == "lower": return value.lower()
    return value

def normalize_artist_prefix(artist: str, mode: str) -> str:
    if mode == "the_first":
        match = re.match(r"^(.+),\s*(The|A|An)$", artist, re.IGNORECASE)
        if match: return f"{match.group(2)} {match.group(1)}"
    elif mode == "the_last":
        match = re.match(r"^(The|A|An)\s+(.+)$", artist, re.IGNORECASE)
        if match: return f"{match.group(2)}, {match.group(1)}"
    return artist

def normalize_genre(genre: str, genre_map: dict[str, str]) -> str:
    return genre_map.get(genre, genre)

def normalize_whitespace(value: str) -> str:
    value = unicodedata.normalize("NFC", value)
    return re.sub(r"\s+", " ", value).strip()

def apply_custom_rule(value: str, rule: dict) -> str:
    return re.sub(rule["find"], rule["replace"], value)

def scan_normalizations(tracks: list[Track], config: dict) -> list[tuple[Track, str, str, str]]:
    changes = []
    case_mode = config.get("case_mode", "as_is")
    artist_prefix = config.get("artist_prefix", "the_first")
    genre_map = config.get("genre_map", {})
    custom_rules = config.get("custom_rules", [])
    text_fields = ["title", "album"]
    for track in tracks:
        for field in text_fields:
            value = getattr(track, field, None)
            if value is None: continue
            cleaned = normalize_whitespace(value)
            normalized = normalize_case(cleaned, case_mode)
            if normalized != value:
                changes.append((track, field, value, normalized))
        if track.artist:
            cleaned = normalize_whitespace(track.artist)
            normalized = normalize_artist_prefix(cleaned, artist_prefix)
            if normalized != track.artist:
                changes.append((track, "artist", track.artist, normalized))
        if track.genre and track.genre in genre_map:
            new_genre = genre_map[track.genre]
            if new_genre != track.genre:
                changes.append((track, "genre", track.genre, new_genre))
        for rule in custom_rules:
            field = rule["field"]
            value = getattr(track, field, None)
            if value is None: continue
            new_value = apply_custom_rule(value, rule)
            if new_value != value:
                changes.append((track, field, value, new_value))
    return changes
