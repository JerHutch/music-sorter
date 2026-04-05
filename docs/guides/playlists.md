# Playlist Manager

Music Sorter generates smart playlists by querying your library with filter criteria. Playlists are saved as definitions and can be regenerated any time your collection changes.

Output formats: **M3U** and **PLS**.

> **Note:** The playlist manager UI is currently in progress. The playlist generation logic in the core library is complete. This guide describes the full intended workflow.

## Playlist Definitions

Each playlist is defined by:

- **Name** — displayed in the playlist tree
- **Folder** — organizational path within the playlist tree (e.g. `DJ/Sets`)
- **Format** — M3U or PLS
- **Filters** — criteria tracks must match to be included
- **Sort** — field to sort results by

Example definition (stored internally as YAML/JSON):

```yaml
name: "High Energy DJ Set"
folder: "DJ/Sets"
format: m3u
filters:
  bucket: "DJ Music"
  bpm: { min: 125, max: 140 }
  genre: ["House", "Techno", "Trance"]
  key: ["8A", "9A", "10A"]
sort_by: bpm
```

## Available Filter Criteria

| Filter | Type | Example |
|---|---|---|
| bucket | exact match | `"DJ Music"` |
| genre | list (any of) | `["House", "Techno"]` |
| bpm | range | `{ min: 120, max: 135 }` |
| key | list (any of) | `["8A", "9A"]` |
| artist | exact match or list | `"Aphex Twin"` |
| year | range | `{ min: 2000, max: 2010 }` |
| has_artwork | boolean | `true` |
| tag_completeness | minimum value | `0.8` |

## Using the Playlist Manager

The Playlist Manager is accessed from the left sidebar under **Saved Playlists**.

### Creating a Playlist

1. Right-click in the playlist tree → **New Playlist**.
2. Fill in the name, folder, format, and filter criteria.
3. Click **Generate** to create the playlist file.

The output file is written to the path configured in Settings under the playlist's folder path.

### Organizing Playlists

- Right-click a folder to create a subfolder, rename, or delete it.
- Drag playlists between folders to reorganize them.

### Regenerating Playlists

After scanning new tracks or editing tags:

- Click **Generate** on an individual playlist to regenerate it.
- Click **Re-generate All** to update every saved playlist at once.

This is useful after importing new music, finishing a deduplication session, or running normalization.

## Output Location

Playlist files are written to the directory configured in Settings. The folder path in the playlist definition creates subdirectories:

```
~/Music/Playlists/
├── DJ/
│   └── Sets/
│       └── High Energy DJ Set.m3u
└── General/
    └── Favourites.m3u
```

Configure the playlist root directory in Settings.
