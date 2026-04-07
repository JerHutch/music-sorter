from __future__ import annotations
from pathlib import Path
from unittest.mock import patch

import pytest
from src.core.models import Track
from src.gui.workers import ArtworkWorker

_PNG_1X1 = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
    b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00"
    b"\x00\x00\x0cIDATx\x9cc\xf8\xcf\xc0\x00\x00\x03\x01"
    b"\x01\x00\xc9\xfe\x92\xef\x00\x00\x00\x00IEND\xaeB`\x82"
)


def _make_track(tmp_path, title="T"):
    p = tmp_path / f"{title}.mp3"
    p.write_bytes(b"")
    return Track(
        file_path=p, file_size=1000, bitrate=320, duration=200.0,
        title=title, artist="Artist", album="Album", tag_completeness=0.9,
    )


def test_artwork_worker_local_found_embeds_and_signals_success(qtbot, tmp_path):
    track = _make_track(tmp_path)
    worker = ArtworkWorker([track])
    results = []
    worker.finished.connect(lambda t, ok, data: results.append((t, ok, data)))
    with patch("src.gui.workers.find_local_artwork", return_value=_PNG_1X1) as mock_find, \
         patch("src.gui.workers.embed_artwork") as mock_embed:
        with qtbot.waitSignal(worker.done, timeout=5000):
            worker.start()
    mock_find.assert_called_once_with(track.file_path)
    mock_embed.assert_called_once_with(track.file_path, _PNG_1X1)
    assert results == [(track, True, _PNG_1X1)]


def test_artwork_worker_falls_back_to_musicbrainz(qtbot, tmp_path):
    track = _make_track(tmp_path)
    worker = ArtworkWorker([track])
    results = []
    worker.finished.connect(lambda t, ok, data: results.append((t, ok, data)))
    with patch("src.gui.workers.find_local_artwork", return_value=None), \
         patch("src.gui.workers.search_cover_art", return_value=_PNG_1X1) as mock_mb, \
         patch("src.gui.workers.embed_artwork") as mock_embed:
        with qtbot.waitSignal(worker.done, timeout=5000):
            worker.start()
    mock_mb.assert_called_once_with("Artist", "Album")
    mock_embed.assert_called_once_with(track.file_path, _PNG_1X1)
    assert results == [(track, True, _PNG_1X1)]


def test_artwork_worker_no_results_emits_status_message(qtbot, tmp_path):
    track = _make_track(tmp_path)
    worker = ArtworkWorker([track])
    messages = []
    results = []
    worker.status_message.connect(messages.append)
    worker.finished.connect(lambda t, ok, data: results.append((t, ok, data)))
    with patch("src.gui.workers.find_local_artwork", return_value=None), \
         patch("src.gui.workers.search_cover_art", return_value=None):
        with qtbot.waitSignal(worker.done, timeout=5000):
            worker.start()
    assert results == [(track, False, b"")]
    assert any("No artwork" in m for m in messages)


def test_artwork_worker_musicbrainz_unavailable_emits_status(qtbot, tmp_path):
    track = _make_track(tmp_path)
    worker = ArtworkWorker([track])
    messages = []
    worker.status_message.connect(messages.append)
    with patch("src.gui.workers.find_local_artwork", return_value=None), \
         patch("src.core.artwork.musicbrainzngs", None):
        with qtbot.waitSignal(worker.done, timeout=5000):
            worker.start()
    assert any("unavailable" in m.lower() for m in messages)


def test_artwork_worker_processes_multiple_tracks(qtbot, tmp_path):
    tracks = [_make_track(tmp_path, f"T{i}") for i in range(3)]
    worker = ArtworkWorker(tracks)
    results = []
    worker.finished.connect(lambda t, ok, data: results.append((t, ok, data)))
    with patch("src.gui.workers.find_local_artwork", return_value=_PNG_1X1), \
         patch("src.gui.workers.embed_artwork"):
        with qtbot.waitSignal(worker.done, timeout=5000):
            worker.start()
    assert len(results) == 3
    assert all(ok for _, ok, _ in results)
