from pathlib import Path
import pytest
from src.core.config import Config
from src.gui.settings_view import SettingsView


def test_get_organize_directory_returns_none_when_empty(qtbot):
    view = SettingsView()
    qtbot.addWidget(view)
    assert view.get_organize_directory() is None


def test_get_organize_directory_returns_path_when_set(qtbot):
    view = SettingsView()
    qtbot.addWidget(view)
    view._organize_path.setText("/music/organized")
    assert view.get_organize_directory() == Path("/music/organized")


def test_load_config_populates_organize_directory(qtbot):
    view = SettingsView()
    qtbot.addWidget(view)
    config = Config({"organize_directory": "/music/organized"})
    view.load_config(config)
    assert view.get_organize_directory() == Path("/music/organized")


def test_overlap_warning_hidden_when_path_is_clear(qtbot):
    view = SettingsView()
    qtbot.addWidget(view)
    view._dir_list.addItem("/music/source")
    view._organize_path.setText("/music/organized")
    assert view._overlap_warning.isHidden()


def test_overlap_warning_shown_when_dest_is_under_source(qtbot):
    view = SettingsView()
    qtbot.addWidget(view)
    view._dir_list.addItem("/music/source")
    view._organize_path.setText("/music/source/organized")
    assert not view._overlap_warning.isHidden()


def test_overlap_warning_shown_when_source_is_under_dest(qtbot):
    view = SettingsView()
    qtbot.addWidget(view)
    view._dir_list.addItem("/music/source/sub")
    view._organize_path.setText("/music/source")
    assert not view._overlap_warning.isHidden()


def test_overlap_warning_shown_when_dest_equals_source(qtbot):
    view = SettingsView()
    qtbot.addWidget(view)
    view._dir_list.addItem("/music/source")
    view._organize_path.setText("/music/source")
    assert not view._overlap_warning.isHidden()


def test_load_config_clears_organize_directory_when_none(qtbot):
    view = SettingsView()
    qtbot.addWidget(view)
    # First load sets a path
    view.load_config(Config({"organize_directory": "/music/organized"}))
    assert view.get_organize_directory() == Path("/music/organized")
    # Second load with no organize_directory clears it
    view.load_config(Config({}))
    assert view.get_organize_directory() is None
