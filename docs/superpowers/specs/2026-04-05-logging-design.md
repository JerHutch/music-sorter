# Logging Design

**Date:** 2026-04-05
**Status:** Approved

## Overview

Add structured, multi-sink logging throughout the application using Python's stdlib `logging` module. This is separate from the existing operation audit trail in `src/core/history.py`. The goal is to surface errors, warnings, and diagnostic information that are currently invisible (e.g. silently swallowed exceptions in workers).

## Architecture

A single new file `src/core/logging_setup.py` owns all logging configuration. It exposes one public function:

```python
def setup_logging(config: Config) -> None: ...
```

Called once at app startup in `src/gui/app.py`. After that, every module acquires its own logger:

```python
import logging
logger = logging.getLogger(__name__)
```

Logger names follow the module hierarchy: `src.core.scanner`, `src.gui.workers`, etc.

`setup_logging` attaches two handlers to the root logger:

- `TimedRotatingFileHandler` — rotates at midnight, keeps N days, uses `JSONFormatter`
- `StreamHandler(sys.stderr)` — plain text, independently configurable level

## Config Schema

New `logging` block in `config/default_config.yaml`:

```yaml
logging:
  level: INFO             # root log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
  console_level: WARNING  # stderr level — can be quieter than the file
  file: ~/.music-sorter/logs/app.log  # ~ expanded at runtime via Path.expanduser()
  max_days: 7             # days of rotated log files to retain
```

`Config` gains a `logging` property returning this block as a dict. `setup_logging` reads from it exclusively.

## Log Formats

**File (JSON):**

```json
{"ts": "2026-04-05T14:32:01", "level": "WARNING", "logger": "src.core.scanner", "thread": "ScanWorker", "msg": "Could not read tags: bad_file.mp3"}
```

`exc` is omitted (not `null`) when there is no exception.

Implementation — `JSONFormatter` in `logging_setup.py`:

```python
class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "thread": record.threadName,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            entry["exc"] = self.formatException(record.exc_info)
        return json.dumps(entry)
```

**Console (plain text):**

```
2026-04-05 14:32:01 WARNING  [ScanWorker] src.core.scanner — Could not read tags: bad_file.mp3
```

Format string: `%(asctime)s %(levelname)-8s [%(threadName)s] %(name)s — %(message)s`

## Log Level Conventions

| Level | When to use |
|-------|------------|
| `DEBUG` | Per-file detail — reading tags, DB upserts, individual rename decisions |
| `INFO` | Operation summaries — scan started/finished, N files processed |
| `WARNING` | Non-fatal issues — missing tag, unrecognised file format, skipped file |
| `ERROR` | Recoverable failures — tag write failed, file not found, DB error |
| `CRITICAL` | Unrecoverable — config load failure, DB unavailable at startup |

## Key Callsites

| Module | What to log |
|--------|------------|
| `src/gui/workers.py` | Replace `except Exception: pass` with `logger.exception(...)` to capture full stack traces |
| `src/core/scanner.py` | `INFO` at scan start/end with file count; `WARNING` for unreadable paths |
| `src/core/tagger.py` | `DEBUG` per tag read; `ERROR` on write failure |
| `src/core/database.py` | `DEBUG` for upserts; `ERROR` for query failures |
| `src/core/artwork.py` | `INFO` for MusicBrainz lookups; `WARNING` on no result; `ERROR` on network failure |
| `src/core/organizer.py` | `INFO` for file moves; `ERROR` on filesystem errors |
| `src/core/renamer.py` | `INFO` for renames; `ERROR` on filesystem errors |
| `src/core/analyzer.py` | `DEBUG` per item; `INFO` for batch summaries |
| `src/core/fingerprint.py` | `DEBUG` per item; `ERROR` on fingerprint failure |
| `src/core/deduplicator.py` | `DEBUG` per item; `INFO` for duplicate group summaries |

## What This Is Not

- Not a replacement for `src/core/history.py` — history tracks undoable user operations (tag writes, renames, deletes). Logging tracks application events for diagnostics.
- Not a GUI log viewer — stderr + file only for now.
