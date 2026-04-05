from __future__ import annotations
import json
import logging
import sys
from logging.handlers import TimedRotatingFileHandler

import pytest

from src.core.config import Config
from src.core.logging_setup import JSONFormatter, setup_logging


@pytest.fixture
def clean_root_logger():
    """Save and restore root logger state around each test."""
    root = logging.getLogger()
    original_level = root.level
    original_handlers = list(root.handlers)
    # Clear all existing handlers
    for h in root.handlers[:]:
        root.removeHandler(h)
        h.close()
    yield root
    # Clean up handlers added during test
    for h in root.handlers[:]:
        root.removeHandler(h)
        h.close()
    # Restore original handlers
    for h in original_handlers:
        root.addHandler(h)
    root.setLevel(original_level)


def _make_config(tmp_path, level="INFO", console_level="WARNING"):
    return Config({
        "logging": {
            "level": level,
            "console_level": console_level,
            "file": str(tmp_path / "app.log"),
            "max_days": 3,
        }
    })


# --- JSONFormatter ---

def test_json_formatter_required_fields():
    formatter = JSONFormatter()
    record = logging.LogRecord(
        name="src.core.scanner", level=logging.WARNING,
        pathname="", lineno=0, msg="test message", args=(), exc_info=None,
    )
    data = json.loads(formatter.format(record))
    assert data["level"] == "WARNING"
    assert data["logger"] == "src.core.scanner"
    assert data["msg"] == "test message"
    assert "ts" in data
    assert "thread" in data


def test_json_formatter_no_exc_field_when_no_exception():
    formatter = JSONFormatter()
    record = logging.LogRecord(
        name="test", level=logging.INFO,
        pathname="", lineno=0, msg="ok", args=(), exc_info=None,
    )
    data = json.loads(formatter.format(record))
    assert "exc" not in data


def test_json_formatter_includes_exc_on_exception():
    formatter = JSONFormatter()
    try:
        raise ValueError("boom")
    except ValueError:
        exc_info = sys.exc_info()
    record = logging.LogRecord(
        name="test", level=logging.ERROR,
        pathname="", lineno=0, msg="error", args=(), exc_info=exc_info,
    )
    data = json.loads(formatter.format(record))
    assert "exc" in data
    assert "ValueError" in data["exc"]
    assert "boom" in data["exc"]


# --- setup_logging ---

def test_setup_logging_attaches_two_handlers(tmp_path, clean_root_logger):
    config = _make_config(tmp_path)
    setup_logging(config)
    # Count only our handlers: TimedRotatingFileHandler and logging.StreamHandler (not subclasses like LogCaptureHandler)
    our_handlers = [h for h in clean_root_logger.handlers
                    if isinstance(h, TimedRotatingFileHandler) or type(h) is logging.StreamHandler]
    assert len(our_handlers) == 2


def test_setup_logging_root_level_from_config(tmp_path, clean_root_logger):
    config = _make_config(tmp_path, level="DEBUG")
    setup_logging(config)
    assert clean_root_logger.level == logging.DEBUG


def test_setup_logging_console_level(tmp_path, clean_root_logger):
    config = _make_config(tmp_path, level="INFO", console_level="ERROR")
    setup_logging(config)
    console = [h for h in clean_root_logger.handlers if type(h) is logging.StreamHandler]
    assert len(console) == 1
    assert console[0].level == logging.ERROR


def test_setup_logging_file_handler_uses_json_formatter(tmp_path, clean_root_logger):
    config = _make_config(tmp_path)
    setup_logging(config)
    file_handlers = [h for h in clean_root_logger.handlers if isinstance(h, TimedRotatingFileHandler)]
    assert len(file_handlers) == 1
    assert isinstance(file_handlers[0].formatter, JSONFormatter)


def test_setup_logging_creates_log_directory(tmp_path, clean_root_logger):
    log_path = tmp_path / "nested" / "logs" / "app.log"
    config = Config({"logging": {
        "level": "INFO", "console_level": "WARNING",
        "file": str(log_path), "max_days": 3,
    }})
    setup_logging(config)
    assert log_path.parent.exists()
