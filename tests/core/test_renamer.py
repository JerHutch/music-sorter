from pathlib import Path
import pytest
from src.core.renamer import render_pattern, sanitize_filename, generate_rename_plan
from src.core.models import Track, RenameOperation

def _track(**kwargs):
    defaults = dict(
        file_path=Path("/music/old.mp3"), file_size=5_000_000, bitrate=320,
        duration=240.0, title="Blue Monday", artist="New Order",
        album="Power, Corruption & Lies", genre="Synth-Pop",
        track_number=5, year=1983, bucket="DJ Music", bpm=130.0, key="5A",
        has_artwork=False,
    )
    defaults.update(kwargs)
    return Track(**defaults)

def test_render_simple_pattern():
    track = _track()
    result = render_pattern("{artist}/{album}/{title}.mp3", track)
    assert result == "New Order/Power, Corruption & Lies/Blue Monday.mp3"

def test_render_with_format_spec():
    track = _track()
    result = render_pattern("{track:02d} - {title}.mp3", track)
    assert result == "05 - Blue Monday.mp3"

def test_render_conditional_present():
    track = _track()
    result = render_pattern("{?album:{album}/}{title}.mp3", track)
    assert result == "Power, Corruption & Lies/Blue Monday.mp3"

def test_render_conditional_missing():
    track = _track(album=None)
    result = render_pattern("{?album:{album}/}{title}.mp3", track)
    assert result == "Blue Monday.mp3"

def test_render_conditional_with_fallback():
    track = _track(album_artist=None)
    result = render_pattern("{?album_artist:{album_artist}|{artist}}/{title}.mp3", track)
    assert result == "New Order/Blue Monday.mp3"

def test_render_conditional_with_fallback_present():
    track = _track(album_artist="New Order Collective")
    result = render_pattern("{?album_artist:{album_artist}|{artist}}/{title}.mp3", track)
    assert result == "New Order Collective/Blue Monday.mp3"

def test_render_dj_music_pattern():
    track = _track()
    result = render_pattern("{bucket}/{genre}/{artist} - {title} [{bpm}bpm {key}].mp3", track)
    assert result == "DJ Music/Synth-Pop/New Order - Blue Monday [130.0bpm 5A].mp3"

def test_sanitize_filename():
    assert sanitize_filename('Song: The "Best" Mix') == "Song_ The _Best_ Mix"
    assert sanitize_filename("trailing.  ") == "trailing"
    assert sanitize_filename("  leading") == "leading"

def test_generate_rename_plan():
    tracks = [
        _track(file_path=Path("/music/old1.mp3"), title="Song A", artist="Artist"),
        _track(file_path=Path("/music/old2.mp3"), title="Song B", artist="Artist"),
    ]
    patterns = {"default": "{artist}/{title}.mp3"}
    base_dir = Path("/output")
    plan = generate_rename_plan(tracks, patterns, base_dir)
    assert len(plan) == 2
    assert all(isinstance(op, RenameOperation) for op in plan)
    assert plan[0].destination == Path("/output/Artist/Song A.mp3")
    assert plan[1].destination == Path("/output/Artist/Song B.mp3")

def test_generate_rename_plan_collision():
    tracks = [
        _track(file_path=Path("/music/a.mp3"), title="Same", artist="Artist"),
        _track(file_path=Path("/music/b.mp3"), title="Same", artist="Artist"),
    ]
    patterns = {"default": "{artist}/{title}.mp3"}
    base_dir = Path("/output")
    plan = generate_rename_plan(tracks, patterns, base_dir)
    destinations = [op.destination for op in plan]
    assert len(set(destinations)) == 2
    assert any("(2)" in str(d) for d in destinations)

def test_generate_rename_plan_uses_bucket_pattern():
    track = _track(bucket="DJ Music")
    patterns = {"default": "{artist}/{title}.mp3", "DJ Music": "{bucket}/{artist} - {title}.mp3"}
    base_dir = Path("/output")
    plan = generate_rename_plan([track], patterns, base_dir)
    assert "DJ Music" in str(plan[0].destination)
