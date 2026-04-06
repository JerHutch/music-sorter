from unittest.mock import patch, MagicMock
from pathlib import Path
import pytest
from src.core.models import Track, DupeGroup, TagConflict, RenameOperation
from src.gui.workers import DedupeWorker, TagWriteWorker, ITunesWorker, RenameWorker


def _make_track(path="/tmp/a.mp3", bitrate=320, completeness=0.8):
    return Track(
        file_path=Path(path), file_size=1000, bitrate=bitrate, duration=200.0,
        title="Test", artist="Artist", tag_completeness=completeness,
    )


def test_dedupe_worker_emits_finished(qtbot):
    tracks = [_make_track("/tmp/a.mp3"), _make_track("/tmp/b.mp3")]
    dupe_groups = [DupeGroup(tracks=tracks)]
    with patch("src.gui.workers.find_duplicates", return_value=dupe_groups):
        worker = DedupeWorker(tracks, duration_tolerance=2.0, similarity_threshold=0.85)
        results = []
        worker.finished.connect(results.append)
        with qtbot.waitSignal(worker.finished, timeout=3000):
            worker.start()
    assert results == [dupe_groups]


def test_tag_write_worker_emits_finished(qtbot, tmp_path):
    track = _make_track(str(tmp_path / "a.mp3"))
    with patch("src.gui.workers.write_tags") as mock_write:
        with patch("src.gui.workers.upsert_track_in_db") as mock_upsert:
            worker = TagWriteWorker([(track, ["title", "artist"])], db=MagicMock())
            done = []
            worker.finished.connect(done.append)
            with qtbot.waitSignal(worker.finished, timeout=3000):
                worker.start()
    mock_write.assert_called_once()
    assert len(done) == 1


def test_itunes_worker_emits_finished(qtbot, tmp_path):
    xml_path = tmp_path / "iTunes.xml"
    xml_path.write_bytes(b"")
    tracks = [_make_track()]
    entries = [{"title": "Test", "artist": "Artist", "location": Path("/tmp/a.mp3")}]
    conflicts = [TagConflict(Path("/tmp/a.mp3"), "title", "Test", "Different")]
    with patch("src.gui.workers.parse_itunes_xml", return_value=entries):
        with patch("src.gui.workers.match_itunes_to_files", return_value=([(entries[0], tracks[0])], [])):
            with patch("src.gui.workers.resolve_itunes_conflicts", return_value=conflicts):
                worker = ITunesWorker(xml_path, tracks, source_directories=[])
                results = []
                worker.finished.connect(results.append)
                with qtbot.waitSignal(worker.finished, timeout=3000):
                    worker.start()
    assert results[0] == conflicts


def test_rename_worker_emits_progress_and_finished(qtbot, tmp_path):
    ops = [RenameOperation(source=tmp_path / "a.mp3", destination=tmp_path / "b.mp3")]
    with patch("src.gui.workers.execute_rename_plan", return_value=ops):
        worker = RenameWorker(ops, dry_run=False)
        progress_signals = []
        done = []
        worker.progress.connect(lambda c, t: progress_signals.append((c, t)))
        worker.finished.connect(done.append)
        with qtbot.waitSignal(worker.finished, timeout=3000):
            worker.start()
    assert len(done) == 1
