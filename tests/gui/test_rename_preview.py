from pathlib import Path
import pytest
from src.core.models import Track, RenameOperation, SmartPlaylist, SimpleRule
from src.core.config import Config
from src.gui.rename_preview import RenamePreview


def _track(path="/tmp/a.mp3"):
    return Track(
        file_path=Path(path), file_size=1000, bitrate=320, duration=200.0,
        title="Test Song", artist="DJ X", genre="House", bpm=128.0,
        bucket="DJ Music", tag_completeness=0.9,
    )


def _track_bucket(path, bucket):
    return Track(
        file_path=Path(path), file_size=1000, bitrate=320, duration=200.0,
        title="Test Song", artist="DJ X", genre="House", bpm=128.0,
        bucket=bucket, tag_completeness=0.9,
    )


def _make_config(patterns: dict) -> Config:
    return Config({"rename_patterns": patterns})


def test_rename_preview_loads_plan(qtbot):
    view = RenamePreview()
    qtbot.addWidget(view)
    ops = [
        RenameOperation(source=Path("/tmp/a.mp3"), destination=Path("/music/b.mp3")),
        RenameOperation(source=Path("/tmp/c.mp3"), destination=Path("/music/d.mp3")),
    ]
    view.load_plan(ops)
    assert view.operation_count() == 2


def test_rename_preview_execute_btn_disabled_before_plan(qtbot):
    view = RenamePreview()
    qtbot.addWidget(view)
    assert not view.is_execute_enabled()


def test_rename_preview_execute_btn_enabled_after_plan(qtbot):
    view = RenamePreview()
    qtbot.addWidget(view)
    ops = [RenameOperation(source=Path("/tmp/a.mp3"), destination=Path("/music/b.mp3"))]
    view.load_plan(ops)
    assert view.is_execute_enabled()


def test_scope_defaults_to_all_tracks(qtbot):
    """With no scope set, all tracks are used for preview/dry-run."""
    view = RenamePreview()
    qtbot.addWidget(view)
    tracks = [
        _track_bucket("/tmp/a.mp3", "DJ Music"),
        _track_bucket("/tmp/b.mp3", "General"),
    ]
    view.set_tracks(tracks)
    assert view.active_track_count() == 2


def test_scope_bucket_filters_tracks(qtbot):
    """Selecting a bucket scope reduces active tracks to that bucket only."""
    view = RenamePreview()
    qtbot.addWidget(view)
    tracks = [
        _track_bucket("/tmp/a.mp3", "DJ Music"),
        _track_bucket("/tmp/b.mp3", "General"),
        _track_bucket("/tmp/c.mp3", "DJ Music"),
    ]
    config = _make_config({"default": "{title}.mp3", "DJ Music": "{artist} - {title}.mp3"})
    view.set_tracks(tracks)
    view.set_config(config)
    view.select_scope("DJ Music")
    assert view.active_track_count() == 2


def test_scope_bucket_loads_pattern(qtbot):
    """Selecting a bucket auto-loads that bucket's rename pattern."""
    view = RenamePreview()
    qtbot.addWidget(view)
    config = _make_config({"default": "{title}.mp3", "DJ Music": "{artist} - {title}.mp3"})
    view.set_tracks([_track_bucket("/tmp/a.mp3", "DJ Music")])
    view.set_config(config)
    view.select_scope("DJ Music")
    assert view.current_pattern() == "{artist} - {title}.mp3"


def test_scope_all_tracks_loads_default_pattern(qtbot):
    """Switching back to All Tracks loads the default pattern."""
    view = RenamePreview()
    qtbot.addWidget(view)
    config = _make_config({"default": "{title}.mp3", "DJ Music": "{artist} - {title}.mp3"})
    view.set_tracks([_track_bucket("/tmp/a.mp3", "DJ Music")])
    view.set_config(config)
    view.select_scope("DJ Music")
    view.select_scope("All Tracks")
    assert view.active_track_count() == 1
    assert view.current_pattern() == "{title}.mp3"


def test_scope_playlist_filters_tracks(qtbot):
    """Selecting a playlist scope filters tracks to those matching the playlist rules."""
    from src.core.playlist import evaluate_playlist as _ep  # verify the same logic
    view = RenamePreview()
    qtbot.addWidget(view)
    tracks = [
        _track_bucket("/tmp/a.mp3", "DJ Music"),
        _track_bucket("/tmp/b.mp3", "General"),
        _track_bucket("/tmp/c.mp3", "DJ Music"),
    ]
    # Playlist matches only "DJ Music" bucket tracks
    playlist = SmartPlaylist(
        name="My DJ Playlist",
        rules=[SimpleRule(field="bucket", operator="is", value="DJ Music")],
    )
    config = _make_config({"default": "{title}.mp3"})
    view.set_tracks(tracks)
    view.set_config(config)
    view.set_playlists([playlist])
    view.select_scope("My DJ Playlist")
    assert view.active_track_count() == 2
