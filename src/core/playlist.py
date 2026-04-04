from __future__ import annotations
from pathlib import Path
from src.core.models import PlaylistDefinition, Track

def generate_m3u(tracks, output_path):
    lines = ["#EXTM3U"]
    for track in tracks:
        duration = int(track.duration)
        artist = track.artist or "Unknown"
        title = track.title or track.file_path.stem
        lines.append(f"#EXTINF:{duration},{artist} - {title}")
        lines.append(str(track.file_path))
    output_path.write_text("\n".join(lines) + "\n")

def generate_pls(tracks, output_path):
    lines = ["[playlist]"]
    for i, track in enumerate(tracks, 1):
        lines.append(f"File{i}={track.file_path}")
        lines.append(f"Title{i}={track.title or track.file_path.stem}")
        lines.append(f"Length{i}={int(track.duration)}")
    lines.append(f"NumberOfEntries={len(tracks)}")
    lines.append("Version=2")
    output_path.write_text("\n".join(lines) + "\n")

def filter_tracks_for_playlist(tracks, playlist):
    result = list(tracks)
    for field, value in playlist.filters.items():
        if isinstance(value, dict):
            min_val, max_val = value.get("min"), value.get("max")
            result = [t for t in result if getattr(t, field, None) is not None
                      and (min_val is None or getattr(t, field) >= min_val)
                      and (max_val is None or getattr(t, field) <= max_val)]
        elif isinstance(value, list):
            result = [t for t in result if getattr(t, field, None) in value]
        else:
            result = [t for t in result if getattr(t, field, None) == value]
    if playlist.sort_by:
        result.sort(key=lambda t: (getattr(t, playlist.sort_by, None) is None, getattr(t, playlist.sort_by, 0)))
    return result
