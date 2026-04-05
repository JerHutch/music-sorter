import pytest
from unittest.mock import MagicMock, patch


def test_main_window_starts_without_crash(qtbot):
    """MainWindow should instantiate without crashing (using mock DB and config)."""
    from src.core.models import Track
    from pathlib import Path

    with patch("src.gui.main_window.Database") as MockDB, \
         patch("src.gui.main_window.Config.load_user_config") as mock_cfg:

        mock_config = MagicMock()
        mock_config.source_directories = []
        mock_config.itunes_xml_path = None
        mock_config.library_columns = {"visible": ["title", "artist"]}
        mock_config.rename_patterns = {}
        mock_config.deduplication = {"duration_tolerance": 2.0, "similarity_threshold": 0.85}
        mock_cfg.return_value = mock_config

        mock_db = MagicMock()
        mock_db.get_all_tracks.return_value = []
        mock_db.get_stats.return_value = {
            "total_tracks": 0, "genre_counts": {}, "bucket_counts": {}, "bitrate_counts": {}
        }
        mock_db.get_all_playlists.return_value = []
        MockDB.return_value = mock_db

        from src.gui.main_window import MainWindow
        win = MainWindow()
        qtbot.addWidget(win)
        assert win.windowTitle() == "Music Sorter"
