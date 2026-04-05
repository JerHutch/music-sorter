# Getting Started

## First Launch

Start Music Sorter with:

```sh
music-sorter
```

On first launch the library is empty. You'll see the Dashboard with zero counts and an empty Library browser.

## Adding Your Music

1. Click **Settings** in the top navigation bar.
2. Under **Source Directories**, click **Add Directory** and select a folder containing MP3 files. Repeat for each root folder you want to include.
3. Optionally set the path to your **iTunes XML** file if you want to pull metadata from iTunes.
4. Click **Save**.

## Scanning Your Library

Click **Scan** in the top navigation bar. Music Sorter walks all configured source directories recursively, reads every `.mp3` file's tags, and stores the results in a local SQLite cache.

Progress is shown in the status bar at the bottom of the window. Large libraries (10,000+ files) typically complete in under a minute on the first scan.

**Subsequent scans** are incremental — only files that have changed on disk since the last scan are re-read. Startup scans complete in seconds.

When the scan finishes, the Dashboard updates with collection statistics and the Library browser populates with all discovered tracks.

## Basic Workflow

A typical session looks like this:

1. **Scan** to pick up any new or changed files.
2. Check the **Dashboard** for an overview of missing tags, duplicates, and missing artwork.
3. Use the **Library** browser to find tracks that need attention. The Task Queue in the left sidebar shows actionable queues (Missing Tags, Duplicates, No Artwork, etc.).
4. Work through each queue:
   - Fix tags in the **Tag Editor** (single or batch).
   - Merge duplicates in the **Duplicate Resolver**.
   - Import metadata from iTunes via **iTunes Import**.
   - Fetch missing artwork via the **Artwork** workflow.
5. When tags are clean, use **Rename/Organize** to restructure files on disk according to your configured patterns.
6. Generate smart playlists via the **Playlist Manager**.

Every operation that modifies files supports a **dry-run preview** before anything is written. All changes are logged to the operation history and can be undone.

## Next Steps

- [Library Browser](library-browser.md) — searching and filtering your collection
- [Tag Editing](tag-editing.md) — fixing tags one at a time or in bulk
- [Configuration Reference](configuration.md) — setting up rename patterns, required tags, and more
