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


def test_tag_editor_highlights_missing_required_fields(qtbot):
    """Required fields that are empty should have a non-default stylesheet."""
    editor = TagEditor()
    qtbot.addWidget(editor)
    # Track with no title, artist, album, genre, year, or bucket
    track = Track(
        file_path=Path("/tmp/a.mp3"), file_size=1000, bitrate=320, duration=200.0,
    )
    editor.load_track(track)
    # title is required and empty — should have non-empty stylesheet
    assert editor._fields["title"].styleSheet() != ""
    # bpm is not required — should have no styling applied
    assert editor._fields["bpm"].styleSheet() == ""


def test_tag_editor_no_highlight_when_required_fields_filled(qtbot):
    """Required fields that are filled should have no highlight styling."""
    editor = TagEditor()
    qtbot.addWidget(editor)
    track = _make_track(title="Title", artist="Artist")
    track.album = "Album"
    track.genre = "House"
    track.year = 2024
    track.bucket = "DJ Music"
    editor.load_track(track)
    for field in ("title", "artist", "album", "genre", "year", "bucket"):
        assert editor._fields[field].styleSheet() == "", f"{field} should not be highlighted"


def test_tag_editor_batch_multiple_not_highlighted(qtbot):
    """In batch mode, a field showing [Multiple] is not considered missing."""
    editor = TagEditor()
    qtbot.addWidget(editor)
    t1 = _make_track("/tmp/a.mp3", title="Song A")
    t2 = _make_track("/tmp/b.mp3", title="Song B")
    editor.load_tracks([t1, t2])
    # title shows [Multiple] — should not be highlighted as missing
    assert editor._fields["title"].styleSheet() == ""
