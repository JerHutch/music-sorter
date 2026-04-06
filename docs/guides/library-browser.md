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

The **Task Queue** in the left sidebar shows actionable groups with live counts updated after each scan:

- **Missing Tags** — tracks below the completeness threshold
- **No Artwork** — tracks missing embedded album art

Click any Task Queue item to instantly filter the Library to just those tracks. Click a bucket to filter by bucket. Selecting **All Music** clears the filter.

## Column Configuration

Available columns include: title, artist, album artist, album, track number, disc number, year, genre, BPM, key, bitrate, duration, file path, file size, bucket, tag completeness, tag source, and has artwork.

**Right-click any column header** to open the column visibility menu. Check or uncheck columns to show or hide them. Drag column headers to reorder them. Your column choices are saved automatically to your configuration file.

## Selecting Tracks

- Click a row to select a single track.
- `Ctrl+click` to add/remove tracks from the selection.
- `Shift+click` to select a range.
- `Ctrl+A` to select all visible tracks.

Selecting one or more tracks opens the **Tag Editor** panel on the right side of the Library view. The panel closes automatically when the selection is cleared.
