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
    assert entries[1]["title"] == "Strobe"


def test_parse_itunes_location_decoding(itunes_xml):
    entries = parse_itunes_xml(itunes_xml)
    blue = entries[0]
    assert blue["location"] == Path("/music/Electronic/New Order/blue_monday.mp3")


def test_match_itunes_to_files(itunes_xml, music_dir_with_files):
    entries = parse_itunes_xml(itunes_xml)
    tracks = [
        Track(file_path=music_dir_with_files / "Electronic" / "New Order" / "blue_monday.mp3",
              file_size=1000, bitrate=128, duration=100.0, title="Blue Monday", artist="New Order", genre="Electronic"),
        Track(file_path=music_dir_with_files / "House" / "Deadmau5" / "strobe.mp3",
              file_size=1000, bitrate=128, duration=100.0, title="Strobe", artist="Deadmau5"),
    ]
    matched, unmatched = match_itunes_to_files(entries, tracks, [music_dir_with_files])
    assert len(matched) >= 1
    assert any(e["title"] == "Nonexistent Track" for e in unmatched)


def test_resolve_conflicts_auto_fill():
    track = Track(file_path=Path("/test.mp3"), file_size=1000, bitrate=128, duration=100.0, title="Song", artist=None)
    itunes_entry = {"title": "Song", "artist": "The Artist", "album": "The Album"}
    conflicts = resolve_conflicts(track, itunes_entry)
    assert track.artist == "The Artist"
    assert track.album == "The Album"
    assert len(conflicts) == 0


def test_resolve_conflicts_keeps_file_when_itunes_empty():
    track = Track(file_path=Path("/test.mp3"), file_size=1000, bitrate=128, duration=100.0, title="Song", artist="File Artist")
    itunes_entry = {"title": "Song", "artist": None}
    conflicts = resolve_conflicts(track, itunes_entry)
    assert track.artist == "File Artist"
    assert len(conflicts) == 0


def test_resolve_conflicts_flags_difference():
    track = Track(file_path=Path("/test.mp3"), file_size=1000, bitrate=128, duration=100.0, title="Song", genre="Rock")
    itunes_entry = {"title": "Song", "genre": "Electronic"}
    conflicts = resolve_conflicts(track, itunes_entry)
    assert len(conflicts) == 1
    assert conflicts[0].field == "genre"
    assert conflicts[0].local_value == "Rock"       # renamed from file_value
    assert conflicts[0].incoming_value == "Electronic"  # renamed from itunes_value
