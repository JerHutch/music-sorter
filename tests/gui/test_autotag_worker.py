from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from src.core.models import Track


def _make_track(path="/music/song.mp3", **kwargs) -> Track:
    defaults = dict(
        file_path=Path(path), file_size=1_000_000, bitrate=320, duration=240.0,
        title="Blue Monday", artist="New Order", album=None, album_artist=None,
        track_number=None, year=None,
    )
    defaults.update(kwargs)
    return Track(**defaults)


def _run_worker_sync(tracks, db):
    """Run AutoTagWorker synchronously by calling run() directly (no Qt event loop needed)."""
    from src.gui.workers import AutoTagWorker
    conflicts_out = []
    unmatched_out = []

    worker = AutoTagWorker(tracks, db)
    worker.finished.connect(lambda c, u: (conflicts_out.extend(c), unmatched_out.append(u)))
    worker.run()  # call directly — skips QThread machinery
    return conflicts_out, unmatched_out[0] if unmatched_out else 0


@patch("src.gui.workers.generate_fingerprint", return_value=None)
def test_no_fingerprint_marks_unmatched(mock_fp, tmp_path):
    from src.core.database import Database
    db = Database(tmp_path / "test.db")
    track = _make_track()
    db.upsert_track(track, file_mtime=1000.0)

    conflicts, unmatched = _run_worker_sync([track], db)

    assert unmatched == 1
    assert conflicts == []
    result = db.get_track(Path("/music/song.mp3"))
    assert result.acoustid_no_match is True


@patch("src.gui.workers.lookup_metadata", return_value=None)
@patch("src.gui.workers.generate_fingerprint", return_value=("fake-fp", 240.0))
def test_no_acoustid_match_marks_unmatched(mock_fp, mock_lookup, tmp_path):
    from src.core.database import Database
    db = Database(tmp_path / "test.db")
    track = _make_track()
    db.upsert_track(track, file_mtime=1000.0)

    conflicts, unmatched = _run_worker_sync([track], db)

    assert unmatched == 1
    assert conflicts == []
    result = db.get_track(Path("/music/song.mp3"))
    assert result.acoustid_no_match is True


@patch("src.gui.workers.lookup_metadata")
@patch("src.gui.workers.generate_fingerprint", return_value=("fake-fp", 240.0))
def test_matching_values_produce_no_conflict(mock_fp, mock_lookup, tmp_path):
    from src.core.database import Database
    mock_lookup.return_value = {
        "title": "Blue Monday", "artist": "New Order",
        "album": None, "album_artist": None, "track_number": None, "year": None,
    }
    db = Database(tmp_path / "test.db")
    track = _make_track(title="Blue Monday", artist="New Order")
    db.upsert_track(track, file_mtime=1000.0)

    conflicts, unmatched = _run_worker_sync([track], db)

    assert unmatched == 0
    assert conflicts == []


@patch("src.gui.workers.lookup_metadata")
@patch("src.gui.workers.generate_fingerprint", return_value=("fake-fp", 240.0))
def test_empty_field_produces_conflict(mock_fp, mock_lookup, tmp_path):
    from src.core.database import Database
    mock_lookup.return_value = {
        "title": "Blue Monday", "artist": "New Order",
        "album": "Power, Corruption & Lies", "album_artist": "New Order",
        "track_number": 1, "year": 1983,
    }
    db = Database(tmp_path / "test.db")
    track = _make_track(title="Blue Monday", artist="New Order",
                        album=None, album_artist=None, track_number=None, year=None)
    db.upsert_track(track, file_mtime=1000.0)

    conflicts, unmatched = _run_worker_sync([track], db)

    assert unmatched == 0
    conflict_fields = {c.field for c in conflicts}
    assert "album" in conflict_fields
    assert "year" in conflict_fields
    album_conflict = next(c for c in conflicts if c.field == "album")
    assert album_conflict.local_value == ""
    assert album_conflict.incoming_value == "Power, Corruption & Lies"


@patch("src.gui.workers.lookup_metadata")
@patch("src.gui.workers.generate_fingerprint", return_value=("fake-fp", 240.0))
def test_differing_existing_value_produces_conflict(mock_fp, mock_lookup, tmp_path):
    from src.core.database import Database
    mock_lookup.return_value = {
        "title": "Blue Monday", "artist": "New Order",
        "album": "Power, Corruption & Lies", "album_artist": None,
        "track_number": None, "year": 1983,
    }
    db = Database(tmp_path / "test.db")
    track = _make_track(title="Blue Monday", artist="New Order", album="Wrong Album", year=2000)
    db.upsert_track(track, file_mtime=1000.0)

    conflicts, unmatched = _run_worker_sync([track], db)

    album_conflict = next((c for c in conflicts if c.field == "album"), None)
    assert album_conflict is not None
    assert album_conflict.local_value == "Wrong Album"
    assert album_conflict.incoming_value == "Power, Corruption & Lies"

    year_conflict = next((c for c in conflicts if c.field == "year"), None)
    assert year_conflict is not None
    assert year_conflict.local_value == "2000"
    assert year_conflict.incoming_value == "1983"
