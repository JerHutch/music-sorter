from pathlib import Path
import pytest
from src.core.organizer import execute_rename_plan, cleanup_empty_dirs
from src.core.models import RenameOperation

def test_execute_rename_plan(tmp_path):
    src = tmp_path / "old" / "song.mp3"
    src.parent.mkdir(parents=True)
    src.write_bytes(b"fake mp3 data")
    dst = tmp_path / "new" / "Artist" / "song.mp3"
    plan = [RenameOperation(source=src, destination=dst)]
    results = execute_rename_plan(plan)
    assert dst.exists()
    assert not src.exists()
    assert results[0].status == "complete"

def test_execute_rename_plan_creates_dirs(tmp_path):
    src = tmp_path / "song.mp3"
    src.write_bytes(b"data")
    dst = tmp_path / "deep" / "nested" / "dir" / "song.mp3"
    plan = [RenameOperation(source=src, destination=dst)]
    execute_rename_plan(plan)
    assert dst.exists()

def test_execute_rename_plan_dry_run(tmp_path):
    src = tmp_path / "song.mp3"
    src.write_bytes(b"data")
    dst = tmp_path / "new" / "song.mp3"
    plan = [RenameOperation(source=src, destination=dst)]
    results = execute_rename_plan(plan, dry_run=True)
    assert src.exists()
    assert not dst.exists()
    assert results[0].status == "pending"

def test_execute_rename_plan_source_missing(tmp_path):
    src = tmp_path / "missing.mp3"
    dst = tmp_path / "new.mp3"
    plan = [RenameOperation(source=src, destination=dst)]
    results = execute_rename_plan(plan)
    assert results[0].status == "error"

def test_cleanup_empty_dirs(tmp_path):
    empty = tmp_path / "a" / "b" / "c"
    empty.mkdir(parents=True)
    notempty = tmp_path / "d"
    notempty.mkdir()
    (notempty / "file.txt").write_text("content")
    removed = cleanup_empty_dirs(tmp_path)
    assert not empty.exists()
    assert notempty.exists()
    assert len(removed) > 0
