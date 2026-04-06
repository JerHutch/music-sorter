from pathlib import Path
from unittest.mock import MagicMock
import pytest
from src.core.models import PlaylistDefinition
from src.gui.playlist_manager import PlaylistManager


def test_playlist_manager_loads_playlists(qtbot):
    db = MagicMock()
    db.get_all_playlists.return_value = [
        PlaylistDefinition(name="Set A", filters={"bucket": "DJ Music"}, folder="DJ"),
        PlaylistDefinition(name="Set B", filters={}, folder=None),
    ]
    manager = PlaylistManager(db=db)
    qtbot.addWidget(manager)
    assert manager.playlist_count() == 2


def test_playlist_manager_empty_state(qtbot):
    db = MagicMock()
    db.get_all_playlists.return_value = []
    manager = PlaylistManager(db=db)
    qtbot.addWidget(manager)
    assert manager.playlist_count() == 0
