from pathlib import Path
from PySide6.QtCore import QThread, Signal
from src.core.database import Database
from src.core.scanner import scan_directories
from src.core.tagger import read_tags


class ScanWorker(QThread):
    progress = Signal(int, str)
    finished = Signal(int)

    def __init__(self, directories, db):
        super().__init__()
        self._directories = directories
        self._db = db
        self._cancelled = False

    def run(self):
        paths = scan_directories(self._directories, on_progress=self._on_scan_progress)
        for i, path in enumerate(paths):
            if self._cancelled:
                break
            try:
                track = read_tags(path)
                mtime = path.stat().st_mtime
                self._db.upsert_track(track, file_mtime=mtime)
            except Exception:
                pass
            self.progress.emit(i + 1, str(path))
        self.finished.emit(len(paths))

    def _on_scan_progress(self, count, current_dir):
        self.progress.emit(count, current_dir)

    def cancel(self):
        self._cancelled = True
