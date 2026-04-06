# iTunes style smart playlists

- Lets extend the playlist functionality to support full iTunes style smart playlists.  
- There should be playlist section in the sidebar showing our created smart playlists.  
- We should be able to mark a playlist to be hidden from the sidebar, show on default.
- This means that we need to add smart playlists to the database to persist the query between sessions.
- 

# iTunes-Style Smart Playlists: Design Overview

Smart playlists are essentially **saved queries** against a music library. The user defines rules, and the playlist is dynamically populated with any tracks that match. Here's how the system breaks down.

---

## Core Concepts

**Rule** — A single condition, composed of three parts:
- **Field** — what property to evaluate (e.g., Artist, Genre, Play Count, Date Added)
- **Operator** — how to compare it (e.g., "contains", "is", "is greater than")
- **Value** — what to compare against (e.g., "Rock", 5, a date)

**Rule Group** — A collection of rules combined with a boolean connector:
- `Match ALL of the following` (AND logic)
- `Match ANY of the following` (OR logic)

iTunes also supports **nested groups**, so you can build compound logic like:
> (Genre is "Jazz" OR Genre is "Blues") AND Play Count > 10

**Smart Playlist** — The top-level object, containing:
- One or more rules/rule groups
- Optional **limit** (e.g., "limit to 25 songs, selected by most recently played")
- Optional **live updating** toggle (re-evaluate rules as the library changes)

---

## Field Types & Their Operators

Fields have a **type** that determines which operators are available:

| Field Type  | Examples                          | Operators                                                                 |
|-------------|-----------------------------------|---------------------------------------------------------------------------|
| **String**  | Title, Artist, Album, Genre       | contains, does not contain, is, is not, starts with, ends with            |
| **Number**  | Play Count, Rating, BPM           | is, is not, is greater than, is less than, is in the range                |
| **Date**    | Date Added, Last Played           | is, is before, is after, is in the last X days                            |
| **Boolean** | Has Artwork, Is Checked           | is true, is false                                                         |
| **Enum**    | Media Kind                        | is, is not (from a fixed list of values)                                  |

---

## Data Model (Simplified)

```
SmartPlaylist
├── name: string
├── conjunction: "AND" | "OR"   // top-level rule connector
├── limit: LimitConfig?
│   ├── enabled: bool
│   ├── count: int
│   ├── unit: "items" | "minutes" | "hours" | "MB" | "GB"
│   └── selectedBy: "random" | "name" | "rating" | "most_recently_added" | ...
├── liveUpdating: bool
└── rules: Rule[]

Rule = SimpleRule | RuleGroup

SimpleRule
├── field: FieldDefinition
├── operator: Operator
└── value: string | number | date | bool

RuleGroup
├── conjunction: "AND" | "OR"
└── rules: Rule[]
```

---

## Evaluation Logic

At query time, walk the rule tree recursively:

```
evaluate(node, track):
  if node is SimpleRule:
    return applyOperator(track[node.field], node.operator, node.value)
  
  if node is RuleGroup:
    results = [evaluate(child, track) for child in node.rules]
    if node.conjunction == "AND": return all(results)
    if node.conjunction == "OR":  return any(results)
```

Apply this to every track in the library to get the matching set, then apply the limit/sort if configured.

---

## Implementation Tips

**Separate field metadata from evaluation.** Define a registry of fields — each entry knows its type, display name, and which operators are valid for it. The UI and the evaluator both read from this registry, so adding a new field is one change.

**Serialize rules as a tree of tagged unions.** Each node should have a `type` discriminator (`"simple"` vs `"group"`) so deserialization is unambiguous. JSON works well for this.

**Dates are tricky.** "In the last 30 days" is a *relative* date — you'll need to distinguish stored absolute dates from relative ones, and re-evaluate relative rules at runtime rather than storing a computed cutoff date.

**Limit + sort ordering matters.** If the user says "top 25 by rating," you need to sort the full match set first, *then* slice. Make sure your limit logic has access to the sort key.

**Live updating** just means the playlist result is not cached — it's re-evaluated each time it's displayed. You can implement a "static snapshot" mode too, where results are frozen at creation time.
