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


import time as _time
from src.core.models import SmartPlaylist, SimpleRule, RuleGroup


def test_date_added_set_on_first_upsert(tmp_path):
    db = Database(tmp_path / "lib.db")
    track = _make_track()
    before = _time.time()
    db.upsert_track(track, file_mtime=1000.0)
    after = _time.time()
    row = db._conn.execute(
        "SELECT date_added FROM tracks WHERE file_path = ?",
        (str(track.file_path),),
    ).fetchone()
    assert row is not None
    assert before <= row["date_added"] <= after


def test_date_added_not_overwritten_on_re_upsert(tmp_path):
    db = Database(tmp_path / "lib.db")
    track = _make_track()
    db.upsert_track(track, file_mtime=1000.0)
    row1 = db._conn.execute(
        "SELECT date_added FROM tracks WHERE file_path = ?",
        (str(track.file_path),),
    ).fetchone()
    original = row1["date_added"]
    _time.sleep(0.02)
    db.upsert_track(track, file_mtime=2000.0)
    row2 = db._conn.execute(
        "SELECT date_added FROM tracks WHERE file_path = ?",
        (str(track.file_path),),
    ).fetchone()
    assert row2["date_added"] == original


def test_upsert_and_get_smart_playlist(tmp_path):
    db = Database(tmp_path / "lib.db")
    playlist = SmartPlaylist(
        name="Jazz Night",
        conjunction="AND",
        rules=[
            SimpleRule(field="genre", operator="contains", value="Jazz"),
            RuleGroup(
                conjunction="OR",
                rules=[
                    SimpleRule(field="bpm", operator="gt", value=90),
                    SimpleRule(field="bpm", operator="lt", value=70),
                ],
            ),
        ],
        limit_count=50,
        limit_order="random",
        sort_by="bpm",
        folder="DJ/Sets",
        format="m3u",
        show_in_sidebar=True,
    )
    db.upsert_smart_playlist(playlist)
    playlists = db.get_all_smart_playlists()
    assert len(playlists) == 1
    p = playlists[0]
    assert p.name == "Jazz Night"
    assert p.conjunction == "AND"
    assert len(p.rules) == 2
    assert isinstance(p.rules[0], SimpleRule)
    assert p.rules[0].field == "genre"
    assert isinstance(p.rules[1], RuleGroup)
    assert p.rules[1].conjunction == "OR"
    assert len(p.rules[1].rules) == 2
    assert p.limit_count == 50
    assert p.limit_order == "random"
    assert p.sort_by == "bpm"
    assert p.folder == "DJ/Sets"
    assert p.show_in_sidebar is True


def test_upsert_smart_playlist_updates_existing(tmp_path):
    db = Database(tmp_path / "lib.db")
    db.upsert_smart_playlist(SmartPlaylist(name="Set A", rules=[
        SimpleRule(field="genre", operator="is", value="House"),
    ]))
    db.upsert_smart_playlist(SmartPlaylist(name="Set A", rules=[
        SimpleRule(field="genre", operator="is", value="Techno"),
    ]))
    playlists = db.get_all_smart_playlists()
    assert len(playlists) == 1
    assert isinstance(playlists[0].rules[0], SimpleRule)
    assert playlists[0].rules[0].value == "Techno"


def test_delete_smart_playlist(tmp_path):
    db = Database(tmp_path / "lib.db")
    db.upsert_smart_playlist(SmartPlaylist(name="Gone", rules=[]))
    db.delete_smart_playlist("Gone")
    assert db.get_all_smart_playlists() == []


def test_acoustid_no_match_column_roundtrip(db):
    track = _make_track(acoustid_no_match=True)
    db.upsert_track(track, file_mtime=1000.0)
    result = db.get_track(Path("/music/song.mp3"))
    assert result is not None
    assert result.acoustid_no_match is True


def test_acoustid_no_match_defaults_false(db):
    track = _make_track()
    db.upsert_track(track, file_mtime=1000.0)
    result = db.get_track(Path("/music/song.mp3"))
    assert result is not None
    assert result.acoustid_no_match is False


def test_acoustid_no_match_migration(tmp_path):
    """Opening a DB that was created without the column should add it transparently."""
    import sqlite3
    db_path = tmp_path / "old.db"
    # Create a DB without the column
    conn = sqlite3.connect(str(db_path))
    conn.execute("""CREATE TABLE tracks (
        file_path TEXT PRIMARY KEY, file_size INTEGER NOT NULL,
        bitrate INTEGER NOT NULL, duration REAL NOT NULL,
        title TEXT, artist TEXT, album_artist TEXT, album TEXT,
        track_number INTEGER, disc_number INTEGER, year INTEGER, genre TEXT,
        bpm REAL, key_ TEXT, bucket TEXT, fingerprint TEXT,
        tag_completeness REAL NOT NULL DEFAULT 0.0, tag_source TEXT,
        has_artwork INTEGER NOT NULL DEFAULT 0, file_mtime REAL NOT NULL DEFAULT 0.0,
        date_added REAL
    )""")
    conn.commit()
    conn.close()
    # Opening via Database should migrate it
    from src.core.database import Database
    db2 = Database(db_path)
    row = db2._conn.execute("PRAGMA table_info(tracks)").fetchall()
    col_names = [r[1] for r in row]
    assert "acoustid_no_match" in col_names
