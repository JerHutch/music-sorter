from pathlib import Path
import pytest
from src.core.models import Track
from src.gui.library_browser import LibraryBrowser, _track_cell_value


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


def test_status_label_reflects_bucket_filter(qtbot):
    t1 = _make_track("A", bucket="House")
    t2 = _make_track("B", bucket="Techno")
    t3 = _make_track("C", bucket="House")
    browser = LibraryBrowser(visible_columns=["title"])
    qtbot.addWidget(browser)
    browser.load_tracks([t1, t2, t3])
    assert browser.status_text() == "3 tracks"
    browser.filter_by_bucket("House")
    assert browser.status_text() == "2 tracks"
    browser.clear_filter()
    assert browser.status_text() == "3 tracks"


def test_status_label_reflects_search_filter(qtbot):
    t1 = _make_track("Alpha Song", "Artist X")
    t2 = _make_track("Beta Track", "Artist Y")
    t3 = _make_track("Alpha Remix", "Artist Z")
    browser = LibraryBrowser(visible_columns=["title", "artist"])
    qtbot.addWidget(browser)
    browser.load_tracks([t1, t2, t3])
    assert browser.status_text() == "3 tracks"
    # Simulate text search — proxy filters rows, status label must update
    browser._search_box.setText("Alpha")
    assert browser.visible_row_count() == 2
    assert browser.status_text() == "2 tracks"
    browser._search_box.setText("")
    assert browser.status_text() == "3 tracks"


def test_status_label_search_combined_with_bucket_filter(qtbot):
    t1 = _make_track("Alpha Song", bucket="House")
    t2 = _make_track("Beta Track", bucket="House")
    t3 = _make_track("Alpha Remix", bucket="Techno")
    browser = LibraryBrowser(visible_columns=["title"])
    qtbot.addWidget(browser)
    browser.load_tracks([t1, t2, t3])
    browser.filter_by_bucket("House")
    assert browser.status_text() == "2 tracks"
    browser._search_box.setText("Alpha")
    assert browser.visible_row_count() == 1
    assert browser.status_text() == "1 track"


def test_process_all_requested_emits_selected_tracks(qtbot):
    t1 = _make_track("Song A", "DJ X")
    t2 = _make_track("Song B", "DJ Y")
    browser = LibraryBrowser(visible_columns=["title", "artist"])
    qtbot.addWidget(browser)
    browser.show()
    browser.load_tracks([t1, t2])

    received = []
    browser.process_all_requested.connect(received.append)

    # Select all rows
    browser._table.selectAll()
    browser._btn_full_process.click()

    assert len(received) == 1
    emitted_tracks = received[0]
    assert len(emitted_tracks) == 2
    assert set(t.title for t in emitted_tracks) == {"Song A", "Song B"}


def test_btn_full_process_enabled_iff_selection(qtbot):
    t1 = _make_track("Song A", "DJ X")
    browser = LibraryBrowser(visible_columns=["title"])
    qtbot.addWidget(browser)
    browser.show()
    browser.load_tracks([t1])

    assert not browser._btn_full_process.isEnabled()

    browser._table.selectAll()
    assert browser._btn_full_process.isEnabled()

    browser._table.clearSelection()
    assert not browser._btn_full_process.isEnabled()


def test_acoustid_no_match_renders_as_yes(qtbot):
    t = _make_track()
    t.acoustid_no_match = True
    assert _track_cell_value(t, "acoustid_no_match") == "Yes"

    t2 = _make_track()
    t2.acoustid_no_match = False
    assert _track_cell_value(t2, "acoustid_no_match") == "No"
