from pathlib import Path
from unittest.mock import patch, MagicMock

from src.core.models import Track


def _make_track(n: int) -> Track:
    return Track(
        file_path=Path(f"/music/track{n}.mp3"),
        file_size=1_000_000, bitrate=320, duration=240.0,
        title=f"Track {n}", artist="Artist", album=None,
        album_artist=None, track_number=None, year=None,
    )


@patch("src.gui.workers.upsert_track_in_db")
@patch("src.gui.workers.write_tags")
@patch("src.gui.workers.detect_key", return_value="Am")
@patch("src.gui.workers.detect_bpm", return_value=120.0)
def test_analyze_worker_cancel(mock_bpm, mock_key, mock_write, mock_upsert, tmp_path):
    from src.core.database import Database
    from src.gui.workers import AnalyzeWorker

    db = Database(tmp_path / "test.db")
    tracks = [_make_track(i) for i in range(5)]

    updated_out = []
    worker = AnalyzeWorker(tracks, db)
    worker.finished.connect(updated_out.extend)

    # Cancel after first progress signal
    call_count = 0
    def on_progress(completed, total):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            worker.cancel()

    worker.progress.connect(on_progress)
    worker.run()  # run directly (no QThread)

    # Should have processed fewer than all 5 tracks
    assert call_count < 5


@patch("src.gui.workers.lookup_metadata", return_value=None)
@patch("src.gui.workers.generate_fingerprint", return_value=("fake-fp", 240.0))
def test_autotag_worker_cancel(mock_fp, mock_lookup, tmp_path):
    from src.core.database import Database
    from src.gui.workers import AutoTagWorker

    db = Database(tmp_path / "test.db")
    tracks = [_make_track(i) for i in range(5)]
    for track in tracks:
        db.upsert_track(track, file_mtime=1000.0)

    progress_calls = []
    worker = AutoTagWorker(tracks, db, api_key="test-key")

    def on_progress(completed, total):
        progress_calls.append(completed)
        if completed == 1:
            worker.cancel()

    worker.progress.connect(on_progress)
    worker.run()

    assert len(progress_calls) < 5
    assert mock_fp.call_count < 5


@patch("src.gui.workers.find_local_artwork", return_value=None)
@patch("src.gui.workers._artwork_mod")
def test_artwork_worker_cancel(mock_artwork_mod, mock_find, tmp_path):
    from src.gui.workers import ArtworkWorker

    mock_artwork_mod.musicbrainzngs = None  # skip MusicBrainz path

    tracks = [_make_track(i) for i in range(5)]

    progress_calls = []
    worker = ArtworkWorker(tracks)

    def on_progress(completed, total):
        progress_calls.append(completed)
        if completed == 1:
            worker.cancel()

    worker.progress.connect(on_progress)
    worker.run()

    assert len(progress_calls) < 5
    assert mock_find.call_count < 5
