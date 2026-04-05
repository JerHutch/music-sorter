# Duplicate Resolution

Music Sorter uses a two-pass algorithm to find duplicate tracks without requiring identical filenames or tags. All duplicates are staged for your review before any files are deleted.

> **Note:** The duplicate resolver UI is currently in progress. The detection and merge logic in the core library is complete. This guide describes the full intended workflow.

## How Duplicate Detection Works

**Pass 1 — Duration filter:** Tracks are grouped by audio duration within a 2-second tolerance. Only groups with 2 or more tracks proceed to the next pass. This makes the expensive fingerprint comparison step feasible on large libraries.

**Pass 2 — Fingerprint comparison:** Within each duration group, Chromaprint audio fingerprints are compared. Tracks with a similarity score above the configured threshold (default: 0.85) are grouped as duplicates.

This approach finds duplicates even when:
- Files have different names or are in different folders
- Tags differ between copies
- One copy has been re-encoded at a different bitrate

## Running Duplicate Detection

1. Open the **Library** browser.
2. Click **Duplicates** in the Task Queue sidebar to see tracks flagged as duplicates.
3. Click **Resolve Duplicates** to open the Duplicate Resolver view.

Note: fingerprints must be generated before duplicates can be detected. If you haven't fingerprinted your library yet, run **Analyze** on your tracks first or wait for the background analysis to complete after scanning.

## Reviewing Duplicate Groups

The Duplicate Resolver shows a table of duplicate groups. Each group can be expanded to show all copies with:

- File path and size
- Bitrate
- Tag differences highlighted between copies

**Auto-recommendation:** For each group, Music Sorter automatically selects the best copy to keep based on:
1. Highest bitrate (primary criterion)
2. Highest tag completeness (tiebreaker)

## Resolving a Group

For each duplicate group you can:

- **Accept auto-recommendation** — keep the suggested copy, merge tags from other copies, move inferior copies to the trash directory.
- **Override the keeper** — click a different copy to designate it as the one to keep.
- **Resolve tag conflicts** — when two copies have different non-empty values for the same field, a dropdown lets you choose which value to use.
- **Skip** — leave this group unresolved for now.

After reviewing, click **Process Selected** or **Process All (Auto)** to execute your decisions.

## Tag Merging

When keeping one copy and discarding others, tags are merged using these rules:

- Non-empty value wins over empty
- Higher-quality source wins (iTunes > MusicBrainz > filename-parsed > existing file tag)
- True conflicts (two different non-empty values) are flagged for manual choice

## Trash, Not Delete

Inferior copies are **moved to a trash directory**, not permanently deleted. You can review the trash and empty it manually when you're confident the right copies were kept. The trash location is configured in Settings.

All deletions are logged to the operation history and can be undone until the trash is emptied.

## Configuration

```yaml
deduplication:
  similarity_threshold: 0.85   # fingerprint similarity cutoff (0.0–1.0)
  duration_tolerance: 2        # seconds, for the pre-filter pass
  trash_directory: ~/Music/.trash
```

See [Configuration Reference](configuration.md) for details.
