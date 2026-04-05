from pathlib import Path
import pytest
from src.core.models import Track
from src.gui.tag_editor import TagEditor


def _make_track(path="/tmp/a.mp3", title="Test", artist="Artist"):
    return Track(
        file_path=Path(path), file_size=1000, bitrate=320, duration=200.0,
        title=title, artist=artist, genre="House", tag_completeness=0.8,
    )


def test_tag_editor_single_track_populates_fields(qtbot):
    editor = TagEditor()
    qtbot.addWidget(editor)
    track = _make_track(title="My Song", artist="DJ X")
    editor.load_track(track)
    assert editor.get_field_value("title") == "My Song"
    assert editor.get_field_value("artist") == "DJ X"


def test_tag_editor_batch_shows_multiple_for_divergent(qtbot):
    editor = TagEditor()
    qtbot.addWidget(editor)
    t1 = _make_track("/tmp/a.mp3", title="Song A", artist="Same Artist")
    t2 = _make_track("/tmp/b.mp3", title="Song B", artist="Same Artist")
    editor.load_tracks([t1, t2])
    assert editor.get_field_value("title") == "[Multiple]"
    assert editor.get_field_value("artist") == "Same Artist"


def test_tag_editor_batch_shows_shared_value_for_same(qtbot):
    editor = TagEditor()
    qtbot.addWidget(editor)
    t1 = _make_track()
    t2 = _make_track()
    t1.genre = "Techno"
    t2.genre = "Techno"
    editor.load_tracks([t1, t2])
    assert editor.get_field_value("genre") == "Techno"


def test_tag_editor_empty_when_no_tracks(qtbot):
    editor = TagEditor()
    qtbot.addWidget(editor)
    editor.load_tracks([])
    assert editor.get_field_value("title") == ""
