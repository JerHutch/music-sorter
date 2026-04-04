from __future__ import annotations

from pathlib import Path
from typing import Callable


def scan_directories(
    directories: list[Path],
    on_progress: Callable[[int, str], None] | None = None,
) -> list[Path]:
    results: list[Path] = []
    for root_dir in directories:
        if not root_dir.is_dir():
            continue
        for path in root_dir.rglob("*"):
            if path.is_file() and path.suffix.lower() == ".mp3":
                results.append(path)
                if on_progress:
                    on_progress(len(results), str(path.parent))
    return results


def find_empty_directories(directories: list[Path]) -> list[Path]:
    empty: list[Path] = []
    for root_dir in directories:
        if not root_dir.is_dir():
            continue
        for path in root_dir.rglob("*"):
            if path.is_dir() and not any(path.iterdir()):
                empty.append(path)
    return empty
