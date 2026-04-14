import pytest
from unittest.mock import MagicMock, patch


def _make_mock_env(bucket_counts=None):
    """Return (mock_config, mock_db) suitable for patching MainWindow deps."""
    mock_config = MagicMock()
    mock_config.source_directories = []
    mock_config.itunes_xml_path = None
    mock_config.library_columns = {"visible": ["title", "artist"]}
    mock_config.rename_patterns = {}
    mock_config.deduplication = {"duration_tolerance": 2.0, "similarity_threshold": 0.85}

    mock_db = MagicMock()
    mock_db.get_all_tracks.return_value = []
    mock_db.get_stats.return_value = {
        "total_tracks": 0,
        "genre_counts": {},
        "bucket_counts": bucket_counts or {},
        "bitrate_counts": {},
    }
    mock_db.get_all_smart_playlists.return_value = []
    return mock_config, mock_db


def test_main_window_starts_without_crash(qtbot):
    """MainWindow should instantiate without crashing (using mock DB and config)."""
    mock_config, mock_db = _make_mock_env()
    with patch("src.gui.main_window.Database") as MockDB, \
         patch("src.gui.main_window.Config.load_user_config") as mock_cfg:
        mock_cfg.return_value = mock_config
        MockDB.return_value = mock_db
        from src.gui.main_window import MainWindow
        win = MainWindow()
        qtbot.addWidget(win)
        assert win.windowTitle() == "Music Sorter"


def test_sidebar_buckets_dynamic(qtbot):
    """Sidebar bucket items should reflect whatever buckets exist in the DB."""
    mock_config, mock_db = _make_mock_env(
        bucket_counts={"DJ Music": 10, "DJ Mixes": 5, "My Custom Bucket": 3}
    )
    with patch("src.gui.main_window.Database") as MockDB, \
         patch("src.gui.main_window.Config.load_user_config") as mock_cfg:
        mock_cfg.return_value = mock_config
        MockDB.return_value = mock_db
        from src.gui.main_window import MainWindow
        win = MainWindow()
        qtbot.addWidget(win)

    bucket_names = set(win._bucket_items.keys())
    assert "All Music" in bucket_names
    assert "DJ Music" in bucket_names
    assert "DJ Mixes" in bucket_names
    assert "My Custom Bucket" in bucket_names


def test_sidebar_buckets_update_on_refresh(qtbot):
    """After a library refresh, new buckets should appear and removed ones should go."""
    mock_config, mock_db = _make_mock_env(bucket_counts={"DJ Music": 10})
    with patch("src.gui.main_window.Database") as MockDB, \
         patch("src.gui.main_window.Config.load_user_config") as mock_cfg:
        mock_cfg.return_value = mock_config
        MockDB.return_value = mock_db
        from src.gui.main_window import MainWindow
        win = MainWindow()
        qtbot.addWidget(win)

    assert "DJ Music" in win._bucket_items
    assert "New Bucket" not in win._bucket_items

    # Simulate a new bucket appearing (e.g. after user tags a track)
    mock_db.get_stats.return_value = {
        "total_tracks": 0, "genre_counts": {}, "bitrate_counts": {},
        "bucket_counts": {"DJ Music": 10, "New Bucket": 2},
    }
    win._refresh_library()

    assert "New Bucket" in win._bucket_items
    assert "DJ Music" in win._bucket_items


def test_sidebar_shows_uncategorized_for_untagged_tracks(qtbot):
    """Tracks with no bucket should appear under Uncategorized in the sidebar."""
    from pathlib import Path
    from src.core.models import Track

    mock_config, mock_db = _make_mock_env(bucket_counts={"DJ Music": 1})
    untagged = Track(
        file_path=Path("/tmp/a.mp3"), file_size=1000, bitrate=320, duration=200.0,
        bucket=None,
    )
    mock_db.get_all_tracks.return_value = [untagged]

    with patch("src.gui.main_window.Database") as MockDB, \
         patch("src.gui.main_window.Config.load_user_config") as mock_cfg:
        mock_cfg.return_value = mock_config
        MockDB.return_value = mock_db
        from src.gui.main_window import MainWindow
        win = MainWindow()
        qtbot.addWidget(win)

    assert "Uncategorized" in win._bucket_items


def test_batch_artwork_scan_shows_progress_bar(qtbot):
    from pathlib import Path
    from src.core.models import Track
    mock_config, mock_db = _make_mock_env()
    with patch("src.gui.main_window.Database") as MockDB, \
         patch("src.gui.main_window.Config.load_user_config") as mock_cfg:
        mock_cfg.return_value = mock_config
        MockDB.return_value = mock_db
        from src.gui.main_window import MainWindow
        win = MainWindow()
        qtbot.addWidget(win)
        win.show()

    tracks = [
        Track(file_path=Path(f"/tmp/{i}.mp3"), file_size=1000, bitrate=320, duration=200.0)
        for i in range(2)
    ]
    with patch("src.gui.main_window.ArtworkWorker") as MockWorker:
        mock_instance = MagicMock()
        MockWorker.return_value = mock_instance
        win._on_artwork_scan(tracks)

    assert win._progress_bar.isVisible()
    assert win._progress_bar.maximum() == 2
    assert win._progress_bar.value() == 0


def test_single_artwork_scan_does_not_show_progress_bar(qtbot):
    from pathlib import Path
    from src.core.models import Track
    mock_config, mock_db = _make_mock_env()
    with patch("src.gui.main_window.Database") as MockDB, \
         patch("src.gui.main_window.Config.load_user_config") as mock_cfg:
        mock_cfg.return_value = mock_config
        MockDB.return_value = mock_db
        from src.gui.main_window import MainWindow
        win = MainWindow()
        qtbot.addWidget(win)
        win.show()

    tracks = [
        Track(file_path=Path("/tmp/a.mp3"), file_size=1000, bitrate=320, duration=200.0)
    ]
    with patch("src.gui.main_window.ArtworkWorker") as MockWorker:
        mock_instance = MagicMock()
        MockWorker.return_value = mock_instance
        win._on_artwork_scan(tracks)

    assert not win._progress_bar.isVisible()


def test_batch_tag_write_shows_progress_bar(qtbot):
    from pathlib import Path
    from src.core.models import Track
    mock_config, mock_db = _make_mock_env()
    with patch("src.gui.main_window.Database") as MockDB, \
         patch("src.gui.main_window.Config.load_user_config") as mock_cfg:
        mock_cfg.return_value = mock_config
        MockDB.return_value = mock_db
        from src.gui.main_window import MainWindow
        win = MainWindow()
        qtbot.addWidget(win)
        win.show()

    tracks = [
        Track(file_path=Path(f"/tmp/{i}.mp3"), file_size=1000, bitrate=320, duration=200.0)
        for i in range(2)
    ]
    with patch("src.gui.main_window.TagWriteWorker") as MockWorker:
        mock_instance = MagicMock()
        MockWorker.return_value = mock_instance
        win._on_tag_save(tracks, {"title": "New Title"})

    assert win._progress_bar.isVisible()
    assert win._progress_bar.maximum() == 2
    assert win._progress_bar.value() == 0


def test_single_tag_write_does_not_show_progress_bar(qtbot):
    from pathlib import Path
    from src.core.models import Track
    mock_config, mock_db = _make_mock_env()
    with patch("src.gui.main_window.Database") as MockDB, \
         patch("src.gui.main_window.Config.load_user_config") as mock_cfg:
        mock_cfg.return_value = mock_config
        MockDB.return_value = mock_db
        from src.gui.main_window import MainWindow
        win = MainWindow()
        qtbot.addWidget(win)
        win.show()

    tracks = [
        Track(file_path=Path("/tmp/a.mp3"), file_size=1000, bitrate=320, duration=200.0)
    ]
    with patch("src.gui.main_window.TagWriteWorker") as MockWorker:
        mock_instance = MagicMock()
        MockWorker.return_value = mock_instance
        win._on_tag_save(tracks, {"title": "New Title"})

    assert not win._progress_bar.isVisible()


def test_batch_artwork_scan_hides_progress_bar_on_done(qtbot):
    from pathlib import Path
    from src.core.models import Track
    mock_config, mock_db = _make_mock_env()
    with patch("src.gui.main_window.Database") as MockDB, \
         patch("src.gui.main_window.Config.load_user_config") as mock_cfg:
        mock_cfg.return_value = mock_config
        MockDB.return_value = mock_db
        from src.gui.main_window import MainWindow
        win = MainWindow()
        qtbot.addWidget(win)
        win.show()

    tracks = [
        Track(file_path=Path(f"/tmp/{i}.mp3"), file_size=1000, bitrate=320, duration=200.0)
        for i in range(2)
    ]
    with patch("src.gui.main_window.ArtworkWorker") as MockWorker:
        mock_instance = MagicMock()
        MockWorker.return_value = mock_instance
        win._on_artwork_scan(tracks)

    assert win._progress_bar.isVisible()

    # Simulate ArtworkWorker.done firing — hide lambda is the first of two done.connect calls
    hide_fn = mock_instance.done.connect.call_args_list[-2][0][0]
    hide_fn()

    assert not win._progress_bar.isVisible()


def test_batch_tag_write_hides_progress_bar_on_finished(qtbot):
    from pathlib import Path
    from src.core.models import Track
    mock_config, mock_db = _make_mock_env()
    with patch("src.gui.main_window.Database") as MockDB, \
         patch("src.gui.main_window.Config.load_user_config") as mock_cfg:
        mock_cfg.return_value = mock_config
        MockDB.return_value = mock_db
        from src.gui.main_window import MainWindow
        win = MainWindow()
        qtbot.addWidget(win)
        win.show()

    tracks = [
        Track(file_path=Path(f"/tmp/{i}.mp3"), file_size=1000, bitrate=320, duration=200.0)
        for i in range(2)
    ]
    with patch("src.gui.main_window.TagWriteWorker") as MockWorker:
        mock_instance = MagicMock()
        MockWorker.return_value = mock_instance
        win._on_tag_save(tracks, {"title": "New Title"})

    assert win._progress_bar.isVisible()

    # Simulate TagWriteWorker.finished firing — last finished.connect call is the hide lambda
    hide_fn = mock_instance.finished.connect.call_args_list[-1][0][0]
    hide_fn([])

    assert not win._progress_bar.isVisible()


def test_sidebar_playlists_section_hidden_when_empty(qtbot):
    """Playlists section is hidden when no playlists have show_in_sidebar=True."""
    mock_config, mock_db = _make_mock_env()
    with patch("src.gui.main_window.Database") as MockDB, \
         patch("src.gui.main_window.Config.load_user_config") as mock_cfg:
        mock_cfg.return_value = mock_config
        MockDB.return_value = mock_db
        from src.gui.main_window import MainWindow
        win = MainWindow()
        qtbot.addWidget(win)

    assert not win._playlists_section_lbl.isVisible()
    assert not win._playlists_tree.isVisible()


def test_sidebar_playlists_section_shows_sidebar_playlists(qtbot):
    """Playlists with show_in_sidebar=True appear in the sidebar section."""
    from src.core.models import SmartPlaylist
    mock_config, mock_db = _make_mock_env()
    pld_visible = SmartPlaylist(name="Road Trip", show_in_sidebar=True)
    pld_hidden = SmartPlaylist(name="Hidden Mix", show_in_sidebar=False)
    mock_db.get_all_smart_playlists.return_value = [pld_visible, pld_hidden]

    with patch("src.gui.main_window.Database") as MockDB, \
         patch("src.gui.main_window.Config.load_user_config") as mock_cfg:
        mock_cfg.return_value = mock_config
        MockDB.return_value = mock_db
        from src.gui.main_window import MainWindow
        win = MainWindow()
        qtbot.addWidget(win)
        win.show()

    assert win._playlists_section_lbl.isVisible()
    assert win._playlists_tree.isVisible()
    assert "Road Trip" in win._playlist_sidebar_items
    assert "Hidden Mix" not in win._playlist_sidebar_items


def test_sidebar_playlists_update_on_refresh(qtbot):
    """After _refresh_library, new sidebar playlists appear and removed ones go."""
    from src.core.models import SmartPlaylist
    mock_config, mock_db = _make_mock_env()
    mock_db.get_all_smart_playlists.return_value = [
        SmartPlaylist(name="Jazz Vibes", show_in_sidebar=True)
    ]

    with patch("src.gui.main_window.Database") as MockDB, \
         patch("src.gui.main_window.Config.load_user_config") as mock_cfg:
        mock_cfg.return_value = mock_config
        MockDB.return_value = mock_db
        from src.gui.main_window import MainWindow
        win = MainWindow()
        qtbot.addWidget(win)

    assert "Jazz Vibes" in win._playlist_sidebar_items
    assert "New Playlist" not in win._playlist_sidebar_items

    mock_db.get_all_smart_playlists.return_value = [
        SmartPlaylist(name="Jazz Vibes", show_in_sidebar=True),
        SmartPlaylist(name="New Playlist", show_in_sidebar=True),
    ]
    win._refresh_library()

    assert "Jazz Vibes" in win._playlist_sidebar_items
    assert "New Playlist" in win._playlist_sidebar_items
