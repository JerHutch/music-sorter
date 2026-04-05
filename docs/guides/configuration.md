# Configuration Reference

Music Sorter stores configuration in YAML. The application ships with built-in defaults. User overrides are saved separately and merged on top at startup.

**Config location (Linux):** `~/.config/music-sorter/config.yaml`

---

## Source Directories

```yaml
source_directories:
  - /home/user/Music/collection
  - /mnt/external/Music
itunes_xml_path: /home/user/Music/iTunes Music Library.xml
```

`itunes_xml_path` is optional. Leave it unset if you don't use iTunes.

---

## Required Tags

Determines which fields must be populated for a track to be considered "complete." Drives the `tag_completeness` score and the Missing Tags queue.

```yaml
required_tags:
  global:
    - title
    - artist
    - album
    - genre
    - year
    - bucket
  per_bucket:
    DJ Music:
      - bpm
      - key
```

`global` applies to all tracks. `per_bucket` adds additional requirements for tracks in that bucket.

---

## Rename Patterns

Per-bucket filename patterns. See [Renaming and Organizing](rename-organize.md) for full token and syntax documentation.

```yaml
rename_patterns:
  default: "{bucket}/{genre}/{artist}/{?album:{album}/}{track:02d} - {title}.mp3"
  DJ Music: "{bucket}/{genre}/{artist} - {title} [{bpm}bpm {key}].mp3"
  DJ Mixes: "{bucket}/{artist}/{title}.mp3"
```

---

## Analysis Settings

Controls which analyses run per bucket. BPM and key detection are expensive; disable them for buckets where you don't need them.

```yaml
analysis:
  DJ Music:
    bpm: true
    key: true
    artwork: true
  DJ Mixes:
    bpm: false
    key: false
    artwork: true
  General:
    bpm: false
    key: false
    artwork: true
```

---

## Normalization Rules

```yaml
normalization:
  artist_prefix: "the_first"    # "The Beatles" — use "the_last" for "Beatles, The"
  case_mode: "title"             # title case. Use "as-is" to skip case normalization
  genre_map:
    "Hip Hop": "Hip-Hop"
    "HipHop": "Hip-Hop"
    "Drum And Bass": "Drum & Bass"
    "DnB": "Drum & Bass"
  custom_rules:
    - field: artist
      find: "Deadmau5"
      replace: "deadmau5"
```

---

## Deduplication

```yaml
deduplication:
  similarity_threshold: 0.85   # fingerprint similarity cutoff (0.0–1.0)
  duration_tolerance: 2        # seconds tolerance for duration pre-filter
  trash_directory: ~/.local/share/music-sorter/trash
```

---

## Library Columns

Controls which columns are visible in the Library browser and their order.

```yaml
library_columns:
  visible:
    - title
    - artist
    - album
    - genre
    - bpm
    - key
    - bitrate
    - tag_completeness
  order:
    - title
    - artist
    - album
    - genre
    - bpm
    - key
    - bitrate
    - tag_completeness
```

All available column names: `title`, `artist`, `album_artist`, `album`, `track_number`, `disc_number`, `year`, `genre`, `bpm`, `key`, `bitrate`, `duration`, `file_path`, `file_size`, `bucket`, `tag_completeness`, `tag_source`, `has_artwork`.

---

## Playlist Output

```yaml
playlists:
  output_directory: ~/Music/Playlists
```

---

## History and Trash

```yaml
history:
  log_path: ~/.local/share/music-sorter/history.jsonl
  trash_directory: ~/.local/share/music-sorter/trash
```

The history log is append-only JSONL. The trash directory holds files moved there by deduplication until you explicitly empty it.

---

## Force Rescan

To drop and rebuild the entire SQLite cache from disk, go to **Settings → Database → Force Rescan**. This is useful if the cache gets out of sync or after moving large numbers of files outside of Music Sorter.
