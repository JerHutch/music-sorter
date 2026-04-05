# iTunes Import

Music Sorter can import track metadata from an iTunes Music Library XML file. This is a one-time or occasional operation to pull in play counts, custom genre edits, or other metadata you've maintained in iTunes.

> **Note:** The iTunes import UI is currently in progress. The parsing and conflict resolution logic in the core library is complete. This guide describes the full intended workflow.

## How It Works

1. Music Sorter parses the iTunes XML plist and extracts metadata for each track: title, artist, album artist, album, track number, genre, year, BPM, and file location.
2. Each iTunes entry is matched to a file on disk:
   - **Path match** — the iTunes `file:///` URI is converted to a local path and checked against your source directories.
   - **Fingerprint fallback** — if the file has moved or been renamed, matching falls back to audio fingerprint comparison.
   - Unmatched entries are reported but ignored.
3. For each matched track, iTunes values are compared to the current MP3 tags and conflicts are surfaced for resolution.

## Conflict Resolution Rules

| Scenario | Default behavior |
|---|---|
| MP3 tag is empty, iTunes has a value | Auto-fill from iTunes |
| MP3 tag has a value, iTunes is empty | Keep MP3 tag (no change) |
| Both match | No action needed |
| Both have different non-empty values | Flagged as a conflict for you to resolve |

## Running the Import

1. Go to **Settings** and set the **iTunes XML path** (or enter it directly in the import dialog).
2. Open the iTunes Import view from the **Import** tab (planned) or the sidebar.
3. Click **Choose iTunes XML** if not already set, then click **Start Import**.
4. A progress bar shows parsing and matching status.
5. When complete, the conflict resolution table appears.

## Resolving Conflicts

The conflict table shows one row per conflict:

| Column | Description |
|---|---|
| File | Path to the MP3 file |
| Field | Tag field with a conflict (e.g. "genre") |
| Current Value | What the MP3 file currently contains |
| iTunes Value | What iTunes has for this track |
| Action | Keep File / Use iTunes toggle |

Work through conflicts row by row, or use the bulk rule buttons:

- **Always prefer iTunes for [field]** — resolves all remaining conflicts for that field in favor of iTunes.
- **Always prefer file for [field]** — resolves all remaining conflicts for that field in favor of the MP3 file.

Click **Apply** to preview the changes, then confirm to write them. All writes are logged to history and can be undone.

## Tips

- Run iTunes import before deduplication — richer tags make the merge step easier.
- If iTunes has BPM values you've set manually, use "Always prefer iTunes for BPM" to pull them all in at once.
- The import can be re-run after adding new tracks to iTunes; only new conflicts will be surfaced.
