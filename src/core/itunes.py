from __future__ import annotations
import plistlib
from pathlib import Path
from urllib.parse import unquote, urlparse
from src.core.models import TagConflict, Track

_FIELD_MAP = {
    "Name": "title", "Artist": "artist", "Album Artist": "album_artist",
    "Album": "album", "Genre": "genre", "Year": "year",
    "Track Number": "track_number", "BPM": "bpm",
}

def parse_itunes_xml(xml_path: Path) -> list[dict]:
    with open(xml_path, "rb") as f:
        plist = plistlib.load(f)
    entries = []
    for track_id, track_data in plist.get("Tracks", {}).items():
        entry = {field_name: track_data.get(xml_key) for xml_key, field_name in _FIELD_MAP.items()}
        location = track_data.get("Location", "")
        entry["location"] = Path(unquote(urlparse(location).path)) if location else None
        entries.append(entry)
    return entries

def match_itunes_to_files(itunes_entries, tracks, source_directories):
    track_by_name = {t.file_path.name: t for t in tracks}
    matched, unmatched = [], []
    for entry in itunes_entries:
        location = entry.get("location")
        found = False
        if location and location.name in track_by_name:
            matched.append((entry, track_by_name[location.name]))
            found = True
        if not found:
            unmatched.append(entry)
    return matched, unmatched

def resolve_conflicts(track, itunes_entry):
    conflicts = []
    for field in ["title", "artist", "album_artist", "album", "genre", "year", "track_number", "bpm"]:
        file_val = getattr(track, field, None)
        itunes_val = itunes_entry.get(field)
        if file_val is None and itunes_val is not None:
            setattr(track, field, itunes_val)
        elif file_val is not None and itunes_val is not None and str(file_val) != str(itunes_val):
            conflicts.append(TagConflict(file_path=track.file_path, field=field, local_value=str(file_val), incoming_value=str(itunes_val)))
    return conflicts
