from __future__ import annotations

import logging
from src.core.fingerprint import compute_similarity
from src.core.models import DupeGroup, TagConflict, Track

logger = logging.getLogger(__name__)

_MERGEABLE_FIELDS = [
    "title", "artist", "album_artist", "album", "track_number",
    "disc_number", "year", "genre", "bpm", "key", "bucket",
]


def find_duration_groups(tracks: list[Track], tolerance: float = 2.0) -> list[list[Track]]:
    if not tracks:
        return []
    sorted_tracks = sorted(tracks, key=lambda t: t.duration)
    groups: list[list[Track]] = []
    current_group: list[Track] = [sorted_tracks[0]]
    for track in sorted_tracks[1:]:
        if track.duration - current_group[0].duration <= tolerance:
            current_group.append(track)
        else:
            groups.append(current_group)
            current_group = [track]
    groups.append(current_group)
    return groups


def find_duplicates(
    tracks: list[Track],
    duration_tolerance: float = 2.0,
    similarity_threshold: float = 0.85,
    on_progress: callable = None,
) -> list[DupeGroup]:
    logger.debug("Starting duplicate detection for %d tracks", len(tracks))
    duration_groups = find_duration_groups(tracks, duration_tolerance)
    dupe_groups: list[DupeGroup] = []
    processed = 0
    for group in duration_groups:
        if len(group) < 2:
            processed += len(group)
            continue
        matched = set()
        for i, track_a in enumerate(group):
            if i in matched or not track_a.fingerprint:
                continue
            cluster = [track_a]
            for j in range(i + 1, len(group)):
                if j in matched or not group[j].fingerprint:
                    continue
                sim = compute_similarity(track_a.fingerprint, group[j].fingerprint)
                if sim >= similarity_threshold:
                    cluster.append(group[j])
                    matched.add(j)
            if len(cluster) >= 2:
                matched.add(i)
                dupe_groups.append(DupeGroup(tracks=cluster))
        processed += len(group)
        if on_progress:
            on_progress(processed, len(tracks))
    logger.info("Duplicate detection complete: %d duplicate group%s found", len(dupe_groups), "" if len(dupe_groups) == 1 else "s")
    return dupe_groups


def merge_tags(keeper: Track, inferiors: list[Track]) -> list[TagConflict]:
    conflicts: list[TagConflict] = []
    for field in _MERGEABLE_FIELDS:
        keeper_val = getattr(keeper, field)
        for inferior in inferiors:
            inf_val = getattr(inferior, field)
            if inf_val is None:
                continue
            if keeper_val is None:
                setattr(keeper, field, inf_val)
                keeper_val = inf_val
            elif keeper_val != inf_val:
                conflicts.append(TagConflict(
                    file_path=keeper.file_path,
                    field=field,
                    file_value=str(keeper_val),
                    itunes_value=str(inf_val),
                ))
                break
    return conflicts
