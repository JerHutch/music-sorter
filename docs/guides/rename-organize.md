# Renaming and Organizing

Music Sorter can rename files and restructure your folder hierarchy based on tag values and configurable per-bucket patterns. Every operation runs as a dry-run preview before any files are moved.

## How It Works

1. You configure a rename pattern per bucket (see [Configuration Reference](configuration.md#rename-patterns)).
2. Music Sorter generates a rename plan: a list of (old path → new path) operations for every affected track.
3. You review the plan in the preview UI. Collision warnings are highlighted.
4. You confirm and Music Sorter executes the moves, creates any needed directories, and cleans up empty directories left behind.

All moves are logged to history and can be undone.

## Prerequisites

Before running a rename, set an **Organize Destination** directory in Settings:

1. Click **Settings** in the top navigation bar.
2. Under **Organize**, click **Browse…** and select a folder where renamed files will be moved. This must be a directory separate from your source directories.
3. Click anywhere else — the setting saves automatically.

If no Organize Destination is configured, the dry-run preview is blocked with a reminder message.

## Pattern Syntax

Patterns use `{token}` substitution. All token values are sanitized for filesystem safety (illegal characters are stripped or replaced).

**Available tokens:**

| Token | Description |
|---|---|
| `{title}` | Track title |
| `{artist}` | Artist |
| `{album_artist}` | Album artist |
| `{album}` | Album name |
| `{track}` | Track number |
| `{disc}` | Disc number |
| `{year}` | Year |
| `{genre}` | Genre |
| `{bpm}` | BPM (rounded to integer) |
| `{key}` | Camelot key notation (e.g. `8A`) |
| `{bucket}` | Bucket name |
| `{bitrate}` | Bitrate in kbps |

**Format modifiers** use Python format spec syntax:
- `{track:02d}` — zero-pad track number to 2 digits
- `{title:.50}` — truncate title to 50 characters

**Conditional blocks:**
- `{?tag:content}` — include `content` only if `tag` has a value
- `{?tag:if_present|if_missing}` — include different text depending on whether the tag is set

**Example patterns:**

```yaml
rename_patterns:
  # General: Bucket/Genre/Artist/Album/01 - Title.mp3
  default: "{bucket}/{genre}/{artist}/{?album:{album}/}{track:02d} - {title}.mp3"

  # DJ Music: Bucket/Genre/Artist - Title [128bpm 8A].mp3
  DJ Music: "{bucket}/{genre}/{artist} - {title} [{bpm}bpm {key}].mp3"

  # DJ Mixes: Bucket/Artist/Title.mp3
  DJ Mixes: "{bucket}/{artist}/{title}.mp3"
```

## Using the Rename Preview

1. Click **Organize** in the top navigation bar, then select the **Rename / Organize** tab.
2. Use the **Scope** dropdown to choose which tracks to act on:
   - **All Tracks** — the entire library (default)
   - A **bucket name** — only tracks tagged with that bucket; the pattern input auto-loads the bucket's configured rename pattern
   - A **playlist name** — only tracks matching that smart playlist's rules; the default pattern is loaded
3. The pattern editor shows the current rename pattern. Edit it and the live preview beneath it updates immediately, showing sample output from the first track in scope.
4. Click **Generate Dry-Run Preview** to build the full table: every old path → new path for tracks in scope. Scroll through and look for anything unexpected.
5. **Collision warnings** (two tracks mapping to the same destination) are highlighted. Music Sorter automatically appends a suffix like `(2)` to resolve collisions, but you should review them.
6. Click **Execute Rename** to run the moves. Progress is shown in the status bar.

## Safety Rules

- Files are **moved**, not copied. Disk usage doesn't double during reorganization.
- Music Sorter **never overwrites** an existing file at the destination.
- Empty source directories are cleaned up automatically after moves.
- Collisions are detected before execution and resolved with `(2)`, `(3)` suffixes.
- All moves are logged to history. The destination paths in the log let you undo moves even after the source directories are gone.
