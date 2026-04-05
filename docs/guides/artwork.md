# Artwork

Music Sorter can fetch album artwork from MusicBrainz / Cover Art Archive and embed it directly into your MP3 files as an ID3 APIC frame.

## How It Works

1. For each track missing artwork, Music Sorter queries MusicBrainz by artist + album name to find the matching release.
2. The cover image is pulled from the Cover Art Archive.
3. All fetched images are staged in a preview before any files are written.
4. You confirm and the images are embedded as APIC frames.

## Running the Artwork Fetch

### Single Track

1. Select a track in the Library browser.
2. Right-click → **Fetch Artwork** (or use the toolbar action when implemented).
3. Music Sorter presents the fetched image for review.
4. Click **Embed** to write it, or **Skip** to leave the track unchanged.

### Batch Mode

1. Click **No Artwork** in the Task Queue sidebar to filter the library to tracks missing artwork.
2. Select all (`Ctrl+A`) or a subset.
3. Click **Fetch Artwork** in the toolbar.
4. Music Sorter queues all selected tracks, fetches art in bulk, and presents a review screen showing each proposed image before writing.
5. Confirm to embed all, or deselect individual tracks to skip them.

## Network Requirements

Artwork fetching queries the MusicBrainz API and Cover Art Archive. These are free public services. Music Sorter respects the MusicBrainz rate limit (1 request/second).

An internet connection is required. Fetched images are not cached locally beyond the current preview session.

## Image Format

Artwork is embedded as JPEG in the APIC frame (picture type: front cover, type code 3). Existing APIC frames are replaced.

## Tips

- Run artwork fetch after deduplication and normalization. Consistent artist/album tags improve match accuracy.
- For DJ mixes with no standard album entry in MusicBrainz, artwork may not be found automatically. You can embed artwork manually by dragging an image file onto the track in the tag editor (planned feature).
