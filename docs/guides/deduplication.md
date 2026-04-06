# Duplicate Resolution

Music Sorter uses a two-pass algorithm to find duplicate tracks without requiring identical filenames or tags. All duplicates are staged for your review before any files are deleted.

## How Duplicate Detection Works

**Pass 1 — Duration filter:** Tracks are grouped by audio duration within a 2-second tolerance. Only groups with 2 or more tracks proceed to the next pass. This makes the expensive fingerprint comparison step feasible on large libraries.

**Pass 2 — Fingerprint comparison:** Within each duration group, Chromaprint audio fingerprints are compared. Tracks with a similarity score above the configured threshold (default: 0.85) are grouped as duplicates.

This approach finds duplicates even when:
- Files have different names or are in different folders
- Tags differ between copies
- One copy has been re-encoded at a different bitrate

## Running Duplicate Detection

1. Click **Organize** in the top navigation bar.
2. Select the **Duplicates** tab.
3. Click **Find Duplicates** to start the scan.

A progress indicator appears during scanning. When complete, duplicate groups are displayed in the tree.

> Fingerprints must be generated before duplicates can be detected. If you haven't fingerprinted your library yet, run **Analyze** on your tracks first.

## Reviewing Duplicate Groups

The Duplicate Resolver shows a tree of duplicate groups. Expand each group to see its copies, each with:

- File path
- Bitrate
- Tag completeness score
- Per-track action dropdown: **Keep**, **Delete**, or **Delete (auto)**

**Auto-recommendation:** For each group, Music Sorter automatically sets the best copy to Keep and the rest to Delete (auto) based on:
1. Highest bitrate (primary criterion)
2. Highest tag completeness (tiebreaker)

## Resolving Groups

For each duplicate group:

- **Accept the auto-recommendation** as-is (the best copy is already set to Keep).
- **Override the keeper** — change a copy's action dropdown to Keep. There should be exactly one Keep per group.
- **Click Auto-Resolve All** to apply the auto-recommendation to every group at once.

When ready, click **Delete Selected** to remove the duplicates marked for deletion from the library.

## Tag Merging

When keeping one copy and discarding others, tags are merged using these rules:

- Non-empty value wins over empty
- Higher-quality source wins (iTunes > MusicBrainz > filename-parsed > existing file tag)
- True conflicts (two different non-empty values) are flagged for manual choice

## What Deletion Does

Deleting a duplicate removes it from the Music Sorter library database. The operation is logged to the operation history.

## Configuration

```yaml
deduplication:
  similarity_threshold: 0.85   # fingerprint similarity cutoff (0.0–1.0)
  duration_tolerance: 2        # seconds, for the pre-filter pass
  trash_directory: ~/Music/.trash
```

See [Configuration Reference](configuration.md) for details.
