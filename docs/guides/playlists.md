# Playlist Manager

Music Sorter generates smart playlists by evaluating filter rules against your library. Playlists are saved as definitions and can be regenerated any time your collection changes.

Output formats: **M3U** and **PLS**.

## Opening the Playlist Manager

Click **Playlists** in the top navigation bar. The left panel shows the playlist tree; the right panel is the editor for the selected playlist.

## Creating a Playlist

1. Click **+ Playlist** in the toolbar above the tree.
2. Enter a name when prompted — the playlist appears in the tree and is selected.
3. Fill in the editor on the right (name, folder, format, rules, sort, limit).
4. Click **Save**.

The playlist appears in the sidebar immediately after saving if **Show in sidebar** is checked.

## Creating a Folder

Click **+ Folder**, enter a folder name, then enter the name of the first playlist inside it. Folders are a visual grouping in the tree — they map to the **Folder** field on each playlist.

To add more playlists to an existing folder, create a playlist normally and type the folder name in the **Folder** field of the editor.

## The Editor

| Field | Description |
|---|---|
| **Name** | Display name for the playlist |
| **Folder** | Tree folder (e.g. `DJ/Sets`) and the output directory for generated files |
| **Format** | M3U or PLS |
| **Sort by** | Field to sort matched tracks before writing (BPM, artist, title, genre, year, bitrate, date added) |
| **Limit** | Cap the track count; combine with an order (random, BPM, artist, title, date added) |
| **Show in sidebar** | Show this playlist in the main window sidebar for one-click filtering |

## Building Rules

Rules determine which tracks are included. Rules are evaluated in real time — the **matching tracks** count below the editor updates as you edit.

### Match mode

At the top of the rule builder, choose:

- **ALL** — a track must pass every rule (logical AND)
- **ANY** — a track passes if it matches at least one rule (logical OR)

### Adding rules

Click **+ Add Rule** to add a rule row. Each row has three parts:

1. **Field** — what to test (see table below)
2. **Operator** — how to compare (depends on field type)
3. **Value** — what to compare against

Click **−** to remove a rule row.

### Rule groups

Click **+ Add Group** to add a sub-group with its own ALL/ANY conjunction. Groups can be used to express logic like "BPM ≥ 125 AND (genre contains House OR genre contains Techno)".

### Available fields

| Field | Type | Notes |
|---|---|---|
| Title | string | Track title tag |
| Artist | string | |
| Album | string | |
| Album Artist | string | |
| Genre | string | |
| Bucket | string | DJ crate/category tag (custom TXXX frame) |
| Key | string | Musical key (e.g. `8A`, `Cm`) |
| BPM | number | |
| Year | number | |
| Track # | number | |
| Bitrate | number | kbps |
| Duration (s) | number | Length in seconds |
| Tag Completeness | number | 0.0–1.0 fraction of required tags present |
| Has Artwork | boolean | |
| Date Added | date | Unix timestamp of when the track was scanned |

### Operators by field type

**String fields**

| Operator | Matches if… |
|---|---|
| contains | field includes the value (case-insensitive) |
| does not contain | field does not include the value |
| is | exact match |
| is not | not an exact match |
| starts with | field begins with the value |
| ends with | field ends with the value |

**Number fields**

| Operator | Matches if… |
|---|---|
| is | equal |
| is not | not equal |
| > | greater than |
| < | less than |
| ≥ | greater than or equal |
| ≤ | less than or equal |
| in range | enter two comma-separated values: `min, max` |

**Boolean fields** (Has Artwork)

| Operator | Matches if… |
|---|---|
| is true | value is set / truthy |
| is false | value is unset / falsy |

**Date fields** (Date Added)

| Operator | Matches if… |
|---|---|
| is | exact timestamp match |
| before | earlier than value |
| after | later than value |
| in last N days | added within the last N days |

## Generating Playlist Files

After saving a playlist definition, click **Generate File…** to write it to disk. A file picker opens; the filename defaults to the playlist name with the chosen extension.

If no tracks match the current rules, a notice is shown and no file is written.

## Regenerating All Playlists

Click **Re-generate All** to update every saved playlist at once. Playlists without a **Folder** path are skipped (nowhere to write). This is useful after:

- Scanning new music into the library
- Finishing a deduplication or tag normalization session
- Editing BPM or key values on tracks

## Sidebar Integration

Playlists with **Show in sidebar** checked appear in the **Playlists** section of the main window sidebar. Clicking a playlist in the sidebar filters the Library view to show only matching tracks — no file is generated.

The sidebar updates immediately when a playlist is created, saved, renamed, or deleted.

## Renaming and Deleting

Right-click a playlist in the tree to **Rename** or **Delete** it.

## Output File Location

The **Folder** field is both the tree folder name and the filesystem directory where files are written. Relative paths are resolved from the home directory. The directory is created automatically if it doesn't exist.

```
~/DJ/Sets/
└── High Energy.m3u

~/General/
└── Favourites.pls
```
