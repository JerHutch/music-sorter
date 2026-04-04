from pathlib import Path
from unittest.mock import patch

import pytest

from src.core.deduplicator import find_duration_groups, find_duplicates, merge_tags
from src.core.models import Track, DupeGroup


def _track(path, duration=240.0, bitrate=320, fingerprint="fp1", **kwargs):
    defaults = dict(
        file_path=Path(path), file_size=5_000_000, bitrate=bitrate,
        duration=duration, fingerprint=fingerprint,
        tag_completeness=0.5, has_artwork=False,
    )
    defaults.update(kwargs)
    return Track(**defaults)


def test_find_duration_groups():
    tracks = [
        _track("/a.mp3", duration=240.0),
        _track("/b.mp3", duration=241.0),
        _track("/c.mp3", duration=300.0),
    ]
    groups = find_duration_groups(tracks, tolerance=2.0)
    assert any(len(g) >= 2 for g in groups)
    two_group = [g for g in groups if len(g) >= 2][0]
    paths = {t.file_path for t in two_group}
    assert Path("/a.mp3") in paths
    assert Path("/b.mp3") in paths


def test_find_duration_groups_no_dupes():
    tracks = [
        _track("/a.mp3", duration=100.0),
        _track("/b.mp3", duration=200.0),
        _track("/c.mp3", duration=300.0),
    ]
    groups = find_duration_groups(tracks, tolerance=2.0)
    assert all(len(g) == 1 for g in groups)


@patch("src.core.deduplicator.compute_similarity")
def test_find_duplicates(mock_sim):
    def sim(fp1, fp2):
        if {fp1, fp2} == {"fp_same_1", "fp_same_2"}:
            return 0.95
        return 0.1
    mock_sim.side_effect = sim

    tracks = [
        _track("/a.mp3", duration=240.0, fingerprint="fp_same_1"),
        _track("/b.mp3", duration=241.0, fingerprint="fp_same_2"),
        _track("/c.mp3", duration=240.5, fingerprint="fp_different"),
    ]
    dupes = find_duplicates(tracks, duration_tolerance=2.0, similarity_threshold=0.85)
    assert len(dupes) == 1
    assert len(dupes[0].tracks) == 2


def test_merge_tags():
    keeper = _track("/a.mp3", bitrate=320, title="Song", artist=None, genre="Rock")
    inferior = _track("/b.mp3", bitrate=128, title="Song", artist="The Artist", genre="Pop")
    conflicts = merge_tags(keeper, [inferior])
    assert keeper.artist == "The Artist"
    assert any(c.field == "genre" for c in conflicts)


def test_merge_tags_no_conflicts():
    keeper = _track("/a.mp3", title="Song", artist="Artist")
    inferior = _track("/b.mp3", title="Song", artist="Artist")
    conflicts = merge_tags(keeper, [inferior])
    assert len(conflicts) == 0
