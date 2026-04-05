from __future__ import annotations
import logging
import shutil
from pathlib import Path
from src.core.models import RenameOperation

logger = logging.getLogger(__name__)


def execute_rename_plan(plan, dry_run=False, on_progress=None):
    for i, op in enumerate(plan):
        if dry_run:
            continue
        if not op.source.exists():
            logger.error("Source file not found, skipping: %s", op.source)
            op.status = "error"
            continue
        try:
            op.destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(op.source), str(op.destination))
            op.status = "complete"
            logger.info("Moved: %s → %s", op.source, op.destination)
        except OSError:
            logger.error("Failed to move: %s → %s", op.source, op.destination, exc_info=True)
            op.status = "error"
        if on_progress:
            on_progress(i + 1, len(plan))
    return plan


def cleanup_empty_dirs(root):
    removed = []
    for dirpath in sorted(root.rglob("*"), key=lambda p: len(p.parts), reverse=True):
        if dirpath.is_dir() and not any(dirpath.iterdir()):
            dirpath.rmdir()
            removed.append(dirpath)
            logger.debug("Removed empty directory: %s", dirpath)
    return removed
