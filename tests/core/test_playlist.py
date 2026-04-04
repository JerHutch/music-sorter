from pathlib import Path
import pytest
from src.core.playlist import generate_m3u, generate_pls, filter_tracks_for_playlist
from src.core.models import Track, PlaylistDefinition

def _track(path="/music/song.mp3", **kwargs):
    defaults = dict(file_path=Path(path), file_size=5_000_000, bitrate=320, duration=240.0, title="Song", artist="Artist", has_artwork=False)
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
    playlist = PlaylistDefinition(name="DJ House", filters={"bucket": "DJ Music", "genre": ["House"]})
    result = filter_tracks_for_playlist(tracks, playlist)
    assert len(result) == 1
    assert result[0].genre == "House"

def test_filter_tracks_bpm_range():
    tracks = [_track("/a.mp3", bpm=120.0), _track("/b.mp3", bpm=130.0), _track("/c.mp3", bpm=145.0)]
    playlist = PlaylistDefinition(name="Mid Tempo", filters={"bpm": {"min": 125, "max": 140}})
    result = filter_tracks_for_playlist(tracks, playlist)
    assert len(result) == 1
    assert result[0].bpm == 130.0

def test_filter_tracks_sort():
    tracks = [_track("/a.mp3", bpm=140.0), _track("/b.mp3", bpm=120.0), _track("/c.mp3", bpm=130.0)]
    playlist = PlaylistDefinition(name="Sorted", filters={}, sort_by="bpm")
    result = filter_tracks_for_playlist(tracks, playlist)
    bpms = [t.bpm for t in result]
    assert bpms == [120.0, 130.0, 140.0]
