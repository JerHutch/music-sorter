# Tag Normalization

The normalization engine applies configurable rules to clean up inconsistent tag values across your collection — fixing capitalization, consolidating genre aliases, handling artist name formatting, and more.

## How It Works

1. Music Sorter scans your library and computes proposed changes for every track based on your normalization rules.
2. The results are shown as a dry-run preview — a table of (track, field, current value, proposed value).
3. You review and confirm. Changes are written and logged to history.

Nothing is written until you explicitly confirm.

## Built-in Rule Types

### Case Normalization

Controls how text fields are capitalized.

```yaml
normalization:
  case_mode: "title"    # title case (default)
  # case_mode: "as-is"  # leave as found
```

Title case applies standard title casing: "the dark side of the moon" → "The Dark Side of the Moon".

### Artist Prefix Handling

Determines whether "The" stays at the front of artist names or is moved to the end.

```yaml
normalization:
  artist_prefix: "the_first"   # "The Beatles" (default)
  # artist_prefix: "the_last"  # "Beatles, The"
```

### Genre Mapping

Consolidates genre aliases to a canonical form.

```yaml
normalization:
  genre_map:
    "Hip Hop": "Hip-Hop"
    "HipHop": "Hip-Hop"
    "Drum And Bass": "Drum & Bass"
    "DnB": "Drum & Bass"
    "D&B": "Drum & Bass"
```

Any genre value matching a key is replaced with the corresponding value. Matching is case-insensitive.

### Whitespace and Unicode Cleanup

Applied automatically:
- Leading and trailing whitespace trimmed
- Multiple consecutive spaces collapsed to one
- Unicode normalization (NFC form)
- Smart quotes converted to straight quotes

### Custom Regex Rules

For precise find/replace on any field:

```yaml
normalization:
  custom_rules:
    - field: artist
      find: "Deadmau5"
      replace: "deadmau5"
    - field: genre
      find: "^Electro$"
      replace: "Electro House"
```

`find` is a Python regular expression. Use anchors (`^`, `$`) for exact matches.

## Running Normalization

From the Library browser, select the tracks you want to normalize (or select all), then:

1. Open **Settings → Normalization** to review your configured rules.
2. Click **Preview Normalization** to see all proposed changes.
3. Review the preview table. Deselect any rows you don't want to apply.
4. Click **Apply** to write changes.

All writes are logged to history and can be undone individually or as a group.

## Tips

- Run normalization before deduplication. Consistent tags make duplicate detection and merge decisions easier.
- Start with the genre map — genre is often the most inconsistent field in large collections.
- Use custom regex rules for edge cases like artist names with unusual capitalization that title case gets wrong.
