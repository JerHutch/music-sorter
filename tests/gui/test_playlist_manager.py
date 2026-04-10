from pathlib import Path
from unittest.mock import MagicMock
import pytest
from src.core.models import SmartPlaylist
from src.gui.playlist_manager import PlaylistManager


def test_playlist_manager_loads_playlists(qtbot):
    db = MagicMock()
    db.get_all_smart_playlists.return_value = [
        SmartPlaylist(name="Set A", folder="DJ"),
        SmartPlaylist(name="Set B", folder=None),
    ]
    manager = PlaylistManager(db=db)
    qtbot.addWidget(manager)
    assert manager.playlist_count() == 2


def test_playlist_manager_empty_state(qtbot):
    db = MagicMock()
    db.get_all_smart_playlists.return_value = []
    manager = PlaylistManager(db=db)
    qtbot.addWidget(manager)
    assert manager.playlist_count() == 0
