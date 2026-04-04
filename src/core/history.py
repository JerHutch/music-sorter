from __future__ import annotations
import json
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

class History:
    def __init__(self, log_path: Path, trash_dir: Path):
        self._log_path = log_path
        self._trash_dir = trash_dir
        self._trash_dir.mkdir(parents=True, exist_ok=True)
        if not self._log_path.exists():
            self._log_path.parent.mkdir(parents=True, exist_ok=True)
            self._log_path.touch()

    def _append(self, entry: dict) -> None:
        entry.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
        with open(self._log_path, "a") as f:
            f.write(json.dumps(entry) + "\n")

    def begin_session(self, label: str = "") -> str:
        return f"{label}_{uuid.uuid4().hex[:8]}"

    def log_tag_write(self, file_path, field, old_value, new_value, session_id=None):
        self._append({"action": "tag_write", "file_path": str(file_path), "field": field, "old_value": old_value, "new_value": new_value, "session_id": session_id})

    def log_rename(self, old_path, new_path, session_id=None):
        self._append({"action": "rename", "file_path": str(old_path), "metadata": {"new_path": str(new_path)}, "session_id": session_id})

    def log_delete(self, file_path, snapshot, session_id=None):
        trash_name = f"{uuid.uuid4().hex[:8]}_{file_path.name}"
        trash_path = self._trash_dir / trash_name
        if file_path.exists():
            shutil.move(str(file_path), str(trash_path))
        self._append({"action": "delete", "file_path": str(file_path), "session_id": session_id, "metadata": {"trash_path": str(trash_path), "snapshot": snapshot}})

    def get_entries(self):
        entries = []
        with open(self._log_path) as f:
            for line in f:
                line = line.strip()
                if line:
                    entries.append(json.loads(line))
        return entries

    def get_session_entries(self, session_id):
        return [e for e in self.get_entries() if e.get("session_id") == session_id]

    def get_undo_operation(self, entry):
        action = entry["action"]
        if action == "tag_write":
            return {"action": "tag_write", "file_path": entry["file_path"], "field": entry["field"], "value": entry["old_value"]}
        elif action == "rename":
            return {"action": "rename", "source": entry["metadata"]["new_path"], "destination": entry["file_path"]}
        elif action == "delete":
            return {"action": "restore", "source": entry["metadata"]["trash_path"], "destination": entry["file_path"]}
        raise ValueError(f"Unknown action: {action}")
