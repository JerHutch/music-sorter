# Tag Editing

Music Sorter can edit ID3 tags for individual tracks or in bulk across many tracks at once. All tag writes go through a preview dialog before anything is saved to disk.

## Supported Tag Fields

| Field | ID3 Frame |
|---|---|
| Title | TIT2 |
| Artist | TPE1 |
| Album Artist | TPE2 |
| Album | TALB |
| Track Number | TRCK |
| Disc Number | TPOS |
| Year | TDRC |
| Genre | TCON |
| BPM | TBPM |
| Key | TKEY |
| Bucket | TXXX:MUSIC_SORTER_BUCKET |

The bucket field uses a custom TXXX (user-defined text) frame so it doesn't interfere with standard players or DJ software.

## Single Track Editing

1. Click a track in the Library browser to select it.
2. The Tag Editor panel slides open on the right side of the Library view.
3. Edit any fields you want to change.
4. Click **Save**. A preview dialog lists exactly which fields will be written.
5. Confirm to apply.

Changes are written to the MP3 file and the database is updated. The operation is logged to history and can be undone.

## Batch Editing

Batch editing lets you set the same tag value across many tracks at once — for example, fixing a misspelled artist name or setting the genre for an entire album.

1. Select multiple tracks in the Library browser (`Ctrl+click`, `Shift+click`, or `Ctrl+A`).
2. The Tag Editor panel shows shared fields. Fields where all selected tracks have the same value show that value. Fields with mixed values show **[Multiple]**.
3. Edit any field. Leaving a field blank or as **[Multiple]** leaves each track's existing value unchanged.
4. Click **Save**. A preview dialog lists every track and field that will change.
5. Confirm to apply.

## Tag Completeness

A track's **tag completeness** score (0–100%) reflects how many required tags are populated. Required tags are configured per-bucket in your config file. See [Configuration Reference](configuration.md#required-tags) for details.

Tracks with low completeness appear in the **Missing Tags** queue in the sidebar.

## Auto-Tagging via AcoustID

For tracks with unknown or incorrect metadata, Music Sorter can look up tags via audio fingerprinting:

1. Select one or more tracks.
2. Click **Auto-Tag Selected** in the toolbar.
3. Music Sorter generates a Chromaprint audio fingerprint for each track and queries the AcoustID API.
4. Results (title, artist, album, MusicBrainz IDs) are presented for review before any tags are written.

This requires the `chromaprint`/`fpcalc` system binary to be installed. See the [main README](../../README.md#requirements) for install instructions.
