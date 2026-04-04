from pathlib import Path

from src.core.scanner import scan_directories, find_empty_directories


def test_scan_finds_mp3_files(music_dir_with_files):
    results = scan_directories([music_dir_with_files])
    filenames = {p.name for p in results}
    assert "blue_monday.mp3" in filenames
    assert "strobe.mp3" in filenames
    assert "unknown.mp3" in filenames
    assert len(results) == 3


def test_scan_ignores_non_mp3(music_dir_with_files):
    results = scan_directories([music_dir_with_files])
    extensions = {p.suffix.lower() for p in results}
    assert extensions == {".mp3"}


def test_scan_case_insensitive_extension(tmp_path):
    (tmp_path / "song.MP3").write_bytes(b"\xff" * 100)
    (tmp_path / "other.Mp3").write_bytes(b"\xff" * 100)
    results = scan_directories([tmp_path])
    assert len(results) == 2


def test_scan_multiple_directories(tmp_path):
    dir_a = tmp_path / "a"
    dir_b = tmp_path / "b"
    dir_a.mkdir()
    dir_b.mkdir()
    (dir_a / "song1.mp3").write_bytes(b"\xff" * 100)
    (dir_b / "song2.mp3").write_bytes(b"\xff" * 100)
    results = scan_directories([dir_a, dir_b])
    assert len(results) == 2


def test_scan_with_progress_callback(music_dir_with_files):
    progress_calls = []
    def on_progress(count, current_dir):
        progress_calls.append((count, current_dir))
    scan_directories([music_dir_with_files], on_progress=on_progress)
    assert len(progress_calls) > 0
    assert progress_calls[-1][0] == 3


def test_find_empty_directories(music_dir_with_files):
    empty_dirs = find_empty_directories([music_dir_with_files])
    empty_names = {d.name for d in empty_dirs}
    assert "Empty" in empty_names


def test_scan_nonexistent_directory(tmp_path):
    results = scan_directories([tmp_path / "nonexistent"])
    assert results == []
