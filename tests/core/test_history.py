import json
from pathlib import Path
import pytest
from src.core.history import History

@pytest.fixture
def history(tmp_path):
    return History(tmp_path / "history.jsonl", tmp_path / "trash")

def test_log_tag_write(history):
    history.log_tag_write(Path("/song.mp3"), "artist", "Old", "New")
    entries = history.get_entries()
    assert len(entries) == 1
    assert entries[0]["action"] == "tag_write"
    assert entries[0]["old_value"] == "Old"
    assert entries[0]["new_value"] == "New"

def test_log_rename(history):
    history.log_rename(Path("/old.mp3"), Path("/new.mp3"))
    entries = history.get_entries()
    assert len(entries) == 1
    assert entries[0]["action"] == "rename"

def test_log_delete(history, tmp_path):
    src = tmp_path / "song.mp3"
    src.write_bytes(b"mp3 data")
    snapshot = {"title": "Song", "artist": "Artist"}
    history.log_delete(src, snapshot)
    entries = history.get_entries()
    assert len(entries) == 1
    assert entries[0]["action"] == "delete"
    assert not src.exists()
    trash_path = Path(entries[0]["metadata"]["trash_path"])
    assert trash_path.exists()

def test_undo_tag_write(history):
    history.log_tag_write(Path("/song.mp3"), "artist", "Old", "New")
    entry = history.get_entries()[-1]
    undo_op = history.get_undo_operation(entry)
    assert undo_op["action"] == "tag_write"
    assert undo_op["field"] == "artist"
    assert undo_op["value"] == "Old"

def test_undo_rename(history):
    history.log_rename(Path("/old.mp3"), Path("/new.mp3"))
    entry = history.get_entries()[-1]
    undo_op = history.get_undo_operation(entry)
    assert undo_op["action"] == "rename"
    assert undo_op["source"] == "/new.mp3"
    assert undo_op["destination"] == "/old.mp3"

def test_undo_delete(history, tmp_path):
    src = tmp_path / "song.mp3"
    src.write_bytes(b"mp3 data")
    history.log_delete(src, {"title": "Song"})
    entry = history.get_entries()[-1]
    undo_op = history.get_undo_operation(entry)
    assert undo_op["action"] == "restore"
    assert undo_op["destination"] == str(src)

def test_session_grouping(history):
    session = history.begin_session("dedup_batch")
    history.log_tag_write(Path("/a.mp3"), "artist", "Old", "New", session_id=session)
    history.log_tag_write(Path("/b.mp3"), "genre", "Rock", "Pop", session_id=session)
    entries = history.get_session_entries(session)
    assert len(entries) == 2
    assert all(e["session_id"] == session for e in entries)
