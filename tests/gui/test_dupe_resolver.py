from pathlib import Path
import pytest
from src.core.models import Track, DupeGroup
from src.gui.dupe_resolver import DupeResolver


def _track(path, bitrate=320, title="T"):
    return Track(file_path=Path(path), file_size=1000, bitrate=bitrate, duration=200.0,
                 title=title, artist="A", tag_completeness=0.8)


def test_dupe_resolver_loads_groups(qtbot):
    resolver = DupeResolver()
    qtbot.addWidget(resolver)
    groups = [
        DupeGroup(tracks=[_track("/tmp/a.mp3", 320), _track("/tmp/b.mp3", 192)]),
        DupeGroup(tracks=[_track("/tmp/c.mp3", 256), _track("/tmp/d.mp3", 128)]),
    ]
    resolver.load_groups(groups)
    assert resolver.group_count() == 2


def test_dupe_resolver_empty_state(qtbot):
    resolver = DupeResolver()
    qtbot.addWidget(resolver)
    resolver.load_groups([])
    assert resolver.group_count() == 0
