# Library Browser

The Library browser is the main view for exploring and selecting tracks. Access it by clicking **Library** in the top navigation bar.

## Track Table

All tracks discovered during the last scan are displayed in a sortable table. Click any column header to sort ascending; click again to sort descending.

**Tag completeness** is color-coded:
- Green — complete (all required tags present)
- Orange — partial (some required tags missing)
- Red — missing (most required tags absent)

## Searching

The search bar at the top of the Library view filters tracks by full-text match across title, artist, album artist, album, and genre fields. Results update as you type.

## Filtering by Bucket

Click a bucket in the left sidebar to filter the library to that bucket:

- **All Music** — no filter, show everything
- **DJ Music** — tracks tagged with the DJ Music bucket
- **DJ Mixes** — tracks tagged with the DJ Mixes bucket
- **General** — tracks tagged with the General bucket

The bucket is stored as a custom `MUSIC_SORTER_BUCKET` ID3 TXXX frame and does not interfere with standard players or DJ software.

## Task Queue Filters

The **Task Queue** in the left sidebar shows actionable groups with counts:

- **Missing Tags** — tracks below the completeness threshold
- **Duplicates** — tracks identified as duplicates
- **No Artwork** — tracks missing embedded album art
- **Ready to Organize** — tracks whose current path doesn't match their rename pattern
- **Empty Dirs** — directories that contain no MP3 files

> **Note:** Task Queue live counts and click-to-filter are planned for a future update. Currently the Task Queue shows static placeholder entries.

## Column Configuration

Available columns include: title, artist, album artist, album, track number, disc number, year, genre, BPM, key, bitrate, duration, file path, file size, bucket, tag completeness, tag source, and has artwork.

> **Note:** Right-click to show/hide columns and drag to reorder are planned for a future update. Column visibility and order will be persisted in your configuration file.

## Selecting Tracks

- Click a row to select a single track.
- `Ctrl+click` to add/remove tracks from the selection.
- `Shift+click` to select a range.
- `Ctrl+A` to select all visible tracks.

The status bar shows the number of currently selected tracks.

## Toolbar Actions

The toolbar above the track table applies actions to the selected tracks:

| Action | Description |
|---|---|
| Auto-Tag Selected | Look up metadata via AcoustID fingerprint for selected tracks |
| Batch Edit | Open the tag editor in batch mode for all selected tracks |
| Analyze | Run BPM and key detection on selected tracks |
| Organize | Preview and execute the rename/reorganize plan for selected tracks |
