# Undo and History

Music Sorter logs every operation that modifies files or tags to an append-only history log. This enables undo and provides a full audit trail of changes to your collection.

## What Gets Logged

Every modifying operation is recorded:

| Operation | What's logged |
|---|---|
| Tag write | File path, field, old value, new value |
| File rename / move | Old path, new path |
| File deletion (to trash) | File path, trash path, full tag snapshot |

The log is stored as JSONL at `~/.local/share/music-sorter/history.jsonl`. Each line is a self-contained JSON object.

Example entries:
```json
{"timestamp": "2026-04-05T14:00:00", "session_id": "abc123", "action": "tag_write", "file": "/path/to/file.mp3", "field": "artist", "old": "Beetles", "new": "The Beatles"}
{"timestamp": "2026-04-05T14:00:01", "session_id": "abc123", "action": "rename", "old_path": "/old/path.mp3", "new_path": "/new/path.mp3"}
{"timestamp": "2026-04-05T14:00:02", "session_id": "abc123", "action": "delete", "file": "/path/to/dupe.mp3", "trash_path": "/trash/dupe.mp3", "snapshot": {"title": "...", "artist": "..."}}
```

## Sessions

Operations from a single user action (e.g. "deduplicate all", "batch edit 50 tracks") share a `session_id`. This lets you undo an entire session as a single unit rather than reversing operations one by one.

## Undoing Operations

Open **Settings → History** to view the operation log and access undo.

Operations are reversed in LIFO (last-in, first-out) order:

- **Undo last operation** — reverses the most recent logged operation.
- **Undo last session** — reverses all operations from the most recent session ID.
- **Browse history** — view the full log and select a specific point to undo to.

Undo itself is logged — you can redo by undoing the undo.

## Trash

Files deleted during deduplication are moved to the trash directory (`~/.local/share/music-sorter/trash` by default), not permanently deleted. The trash holds them until you explicitly empty it.

**To review the trash:** Settings → History → View Trash. Shows all files currently in the trash with their original paths and the date they were moved.

**To restore a file:** Select it in the trash view and click **Restore**. The file is moved back to its original path and the deletion entry is removed from the history log.

**To empty the trash:** Settings → History → Empty Trash. This permanently deletes the files. This action cannot be undone.

> Only empty the trash after you're confident the right duplicates were kept.

## Log Rotation

The history log grows indefinitely. To trim it, go to **Settings → History → Clear Old Entries** and specify a cutoff date. Entries older than the cutoff are removed. The trash is not affected by log trimming.
