from pathlib import Path
import pytest
from src.core.models import Track
from src.gui.library_browser import LibraryBrowser


def _make_track(title="T", artist="A", bucket=None):
    t = Track(
        file_path=Path("/tmp/a.mp3"), file_size=1000, bitrate=320, duration=200.0,
        title=title, artist=artist, genre="House", bpm=128.0, tag_completeness=0.9,
    )
    t.bucket = bucket
    return t


def test_library_browser_loads_tracks(qtbot):
    browser = LibraryBrowser(visible_columns=["title", "artist", "genre"])
    qtbot.addWidget(browser)
    browser.load_tracks([_make_track("Song A", "DJ X"), _make_track("Song B", "DJ Y")])
    assert browser.track_count() == 2


def test_library_browser_column_count_matches_visible(qtbot):
    browser = LibraryBrowser(visible_columns=["title", "artist", "bpm"])
    qtbot.addWidget(browser)
    assert browser.column_count() == 3


def test_library_browser_filter_by_bucket(qtbot):
    t1 = _make_track("A", "X", bucket="DJ Music")
    t2 = _make_track("B", "Y", bucket="General")
    browser = LibraryBrowser(visible_columns=["title", "artist"])
    qtbot.addWidget(browser)
    browser.load_tracks([t1, t2])
    browser.filter_by_bucket("DJ Music")
    assert browser.visible_row_count() == 1


def test_library_browser_filter_by_fn(qtbot):
    t1 = _make_track(title="Complete")
    t1.tag_completeness = 0.95
    t2 = _make_track(title="Incomplete")
    t2.tag_completeness = 0.2
    browser = LibraryBrowser(visible_columns=["title"])
    qtbot.addWidget(browser)
    browser.load_tracks([t1, t2])
    browser.filter_by_fn(lambda t: t.tag_completeness < 0.4)
    assert browser.visible_row_count() == 1


def test_library_browser_filter_uncategorized(qtbot):
    t1 = _make_track("A", bucket="DJ Music")
    t2 = _make_track("B", bucket=None)
    t3 = _make_track("C", bucket=None)
    browser = LibraryBrowser(visible_columns=["title"])
    qtbot.addWidget(browser)
    browser.load_tracks([t1, t2, t3])
    browser.filter_by_bucket("Uncategorized")
    assert browser.visible_row_count() == 2


def test_library_browser_clear_filter(qtbot):
    t1 = _make_track("A", bucket="DJ Music")
    t2 = _make_track("B", bucket="General")
    browser = LibraryBrowser(visible_columns=["title"])
    qtbot.addWidget(browser)
    browser.load_tracks([t1, t2])
    browser.filter_by_bucket("DJ Music")
    assert browser.visible_row_count() == 1
    browser.clear_filter()
    assert browser.visible_row_count() == 2
