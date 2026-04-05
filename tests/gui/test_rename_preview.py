from pathlib import Path
import pytest
from src.core.models import Track, RenameOperation
from src.gui.rename_preview import RenamePreview


def _track(path="/tmp/a.mp3"):
    return Track(
        file_path=Path(path), file_size=1000, bitrate=320, duration=200.0,
        title="Test Song", artist="DJ X", genre="House", bpm=128.0,
        bucket="DJ Music", tag_completeness=0.9,
    )


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
