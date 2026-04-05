from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable

logger = logging.getLogger(__name__)


def scan_directories(
    directories: list[Path],
    on_progress: Callable[[int, str], None] | None = None,
) -> list[Path]:
    logger.info("Scanning %d director%s", len(directories), "y" if len(directories) == 1 else "ies")
    results: list[Path] = []
    for root_dir in directories:
        if not root_dir.is_dir():
            logger.warning("Skipping non-existent directory: %s", root_dir)
            continue
        for path in root_dir.rglob("*"):
            if path.is_file() and path.suffix.lower() == ".mp3":
                results.append(path)
                if on_progress:
                    on_progress(len(results), str(path.parent))
    logger.info("Scan complete: found %d MP3 file%s", len(results), "" if len(results) == 1 else "s")
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
