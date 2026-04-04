from pathlib import Path

import pytest

from src.core.database import Database
from src.core.models import Track


@pytest.fixture
def db(tmp_path):
    return Database(tmp_path / "test.db")


def _make_track(path="/music/song.mp3", **kwargs):
    defaults = dict(
        file_path=Path(path), file_size=5_000_000, bitrate=320, duration=240.0,
        title="Blue Monday", artist="New Order", album="Power", genre="Synth-Pop",
        year=1983, bucket="DJ Music", tag_completeness=0.8, has_artwork=False,
    )
    defaults.update(kwargs)
    return Track(**defaults)


def test_insert_and_get_track(db):
    track = _make_track()
    db.upsert_track(track, file_mtime=1000.0)
    result = db.get_track(Path("/music/song.mp3"))
    assert result is not None
    assert result.title == "Blue Monday"
    assert result.artist == "New Order"


def test_upsert_updates_existing(db):
    track = _make_track()
    db.upsert_track(track, file_mtime=1000.0)
    track.title = "Updated Title"
    db.upsert_track(track, file_mtime=2000.0)
    result = db.get_track(Path("/music/song.mp3"))
    assert result.title == "Updated Title"


def test_delete_track(db):
    track = _make_track()
    db.upsert_track(track, file_mtime=1000.0)
    db.delete_track(Path("/music/song.mp3"))
    assert db.get_track(Path("/music/song.mp3")) is None


def test_get_all_tracks(db):
    db.upsert_track(_make_track("/a.mp3", title="A"), file_mtime=1000.0)
    db.upsert_track(_make_track("/b.mp3", title="B"), file_mtime=1000.0)
    tracks = db.get_all_tracks()
    assert len(tracks) == 2


def test_get_stale_paths(db):
    db.upsert_track(_make_track("/a.mp3"), file_mtime=1000.0)
    db.upsert_track(_make_track("/b.mp3"), file_mtime=2000.0)
    stale = db.get_stale_paths({Path("/a.mp3"): 1000.0, Path("/b.mp3"): 3000.0})
    assert Path("/b.mp3") in stale
    assert Path("/a.mp3") not in stale


def test_get_removed_paths(db):
    db.upsert_track(_make_track("/a.mp3"), file_mtime=1000.0)
    db.upsert_track(_make_track("/b.mp3"), file_mtime=1000.0)
    removed = db.get_removed_paths({Path("/a.mp3")})
    assert Path("/b.mp3") in removed
    assert Path("/a.mp3") not in removed


def test_search_tracks(db):
    db.upsert_track(_make_track("/a.mp3", title="Blue Monday", artist="New Order"), file_mtime=1000.0)
    db.upsert_track(_make_track("/b.mp3", title="Strobe", artist="Deadmau5"), file_mtime=1000.0)
    results = db.search("Monday")
    assert len(results) == 1
    assert results[0].title == "Blue Monday"


def test_get_stats(db):
    db.upsert_track(_make_track("/a.mp3", genre="House", bitrate=320, bucket="DJ Music", tag_completeness=1.0), file_mtime=1000.0)
    db.upsert_track(_make_track("/b.mp3", genre="Techno", bitrate=256, bucket="DJ Music", tag_completeness=0.5), file_mtime=1000.0)
    db.upsert_track(_make_track("/c.mp3", genre="House", bitrate=128, bucket="General", tag_completeness=0.0), file_mtime=1000.0)
    stats = db.get_stats()
    assert stats["total_tracks"] == 3
    assert stats["genre_counts"]["House"] == 2
    assert stats["bucket_counts"]["DJ Music"] == 2
    assert stats["bucket_counts"]["General"] == 1


def test_filter_tracks(db):
    db.upsert_track(_make_track("/a.mp3", bucket="DJ Music", genre="House", bpm=128.0), file_mtime=1000.0)
    db.upsert_track(_make_track("/b.mp3", bucket="DJ Music", genre="Techno", bpm=140.0), file_mtime=1000.0)
    db.upsert_track(_make_track("/c.mp3", bucket="General", genre="Rock"), file_mtime=1000.0)
    results = db.filter_tracks(bucket="DJ Music")
    assert len(results) == 2
    results = db.filter_tracks(bucket="DJ Music", genre="House")
    assert len(results) == 1
    assert results[0].genre == "House"
