# Playlist Manager

Music Sorter generates smart playlists by querying your library with filter criteria. Playlists are saved as definitions and can be regenerated any time your collection changes.

Output formats: **M3U** and **PLS**.

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

Click **Playlists** in the top navigation bar to open the Playlist Manager. The left panel shows the playlist tree organized into folders; the right panel is the editor for the selected playlist.

### Creating a Playlist

1. Right-click in the playlist tree → **New Playlist**.
2. Fill in the name, folder path, format (M3U or PLS), filter criteria, and sort field in the editor panel on the right.
3. Click **Save** to store the definition.
4. Click **Generate** to write the playlist file to disk.

### Organizing with Folders

- Click **+ Folder** to add a folder to the tree. Folders are a visual grouping — they persist when a playlist is saved into them.
- Right-click a playlist or folder to rename or delete it.

### Regenerating Playlists

After scanning new tracks or editing tags:

- Select a playlist and click **Generate** to regenerate it.
- Click **Re-generate All** to update every saved playlist at once.

This is useful after importing new music, finishing a deduplication session, or running normalization.

## Output Location

The **Folder** field on each playlist is the filesystem directory where the file is written. Use an absolute path (e.g. `~/Music/Playlists/DJ/Sets`) or a path relative to your home directory. The directory is created automatically if it doesn't exist.

```
~/Music/Playlists/
├── DJ/
│   └── Sets/
│       └── High Energy DJ Set.m3u
└── General/
    └── Favourites.m3u
```
