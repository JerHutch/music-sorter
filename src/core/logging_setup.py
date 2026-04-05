from __future__ import annotations

import json
import logging
import sys
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

from src.core.config import Config

_CONSOLE_FORMAT = "%(asctime)s %(levelname)-8s [%(threadName)s] %(name)s — %(message)s"


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "thread": record.threadName,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            entry["exc"] = self.formatException(record.exc_info)
        return json.dumps(entry)


def setup_logging(config: Config) -> None:
    """Configure root logger with a rotating JSON file handler and a plain-text stderr handler.

    Call once at application startup before any logging occurs.
    """
    cfg = config.logging
    level = getattr(logging, str(cfg.get("level", "INFO")).upper(), logging.INFO)
    console_level = getattr(logging, str(cfg.get("console_level", "WARNING")).upper(), logging.WARNING)
    log_file = Path(str(cfg.get("file", "~/.music-sorter/logs/app.log"))).expanduser()
    max_days = int(cfg.get("max_days", 7))

    root = logging.getLogger()
    root.setLevel(level)

    # Rotating file handler — JSON
    log_file.parent.mkdir(parents=True, exist_ok=True)
    file_handler = TimedRotatingFileHandler(
        log_file, when="midnight", backupCount=max_days, encoding="utf-8",
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(JSONFormatter())
    root.addHandler(file_handler)

    # Console handler — plain text
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(console_level)
    console_handler.setFormatter(logging.Formatter(_CONSOLE_FORMAT))
    root.addHandler(console_handler)
