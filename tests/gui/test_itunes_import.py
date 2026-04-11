from pathlib import Path
import pytest
from src.core.models import TagConflict
from src.gui.itunes_import import ITunesImport


def _conflict(field="title", file_val="A", itunes_val="B"):
    return TagConflict(file_path=Path("/tmp/a.mp3"), field=field,
                       local_value=file_val, incoming_value=itunes_val)


def test_itunes_import_loads_conflicts(qtbot):
    view = ITunesImport()
    qtbot.addWidget(view)
    conflicts = [_conflict("title", "Old Title", "New Title"),
                 _conflict("artist", "Old", "New")]
    view.load_conflicts(conflicts)
    assert view.conflict_count() == 2


def test_itunes_import_empty(qtbot):
    view = ITunesImport()
    qtbot.addWidget(view)
    view.load_conflicts([])
    assert view.conflict_count() == 0
