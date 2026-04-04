from pathlib import Path

from src.core.models import Track


def test_track_creation_with_all_fields():
    track = Track(
        file_path=Path("/music/song.mp3"),
        file_size=5_000_000,
        bitrate=320,
        duration=240.5,
        title="Blue Monday",
        artist="New Order",
        album_artist="New Order",
        album="Power, Corruption & Lies",
        track_number=5,
        disc_number=1,
        year=1983,
        genre="Synth-Pop",
        bpm=130.0,
        key="5A",
        bucket="DJ Music",
        fingerprint="AQADtNIyRUkS",
        tag_completeness=1.0,
        tag_source="file",
        has_artwork=True,
    )
    assert track.title == "Blue Monday"
    assert track.file_path == Path("/music/song.mp3")
    assert track.bitrate == 320
    assert track.bucket == "DJ Music"


def test_track_creation_with_minimal_fields():
    track = Track(
        file_path=Path("/music/unknown.mp3"),
        file_size=3_000_000,
        bitrate=192,
        duration=180.0,
    )
    assert track.title is None
    assert track.artist is None
    assert track.bpm is None
    assert track.bucket is None
    assert track.tag_completeness == 0.0
    assert track.has_artwork is False


def test_track_tag_completeness_calculation():
    required = ["title", "artist", "album", "genre", "year", "bucket"]
    track = Track(
        file_path=Path("/music/partial.mp3"),
        file_size=4_000_000,
        bitrate=256,
        duration=200.0,
        title="Strobe",
        artist="Deadmau5",
        genre="Progressive House",
    )
    completeness = track.compute_completeness(required)
    assert completeness == 3 / 6  # title, artist, genre out of 6


from src.core.models import (
    DupeGroup,
    HistoryEntry,
    NormalizationRule,
    PlaylistDefinition,
    RenameOperation,
    TagConflict,
)


def test_dupe_group_best_track():
    low = Track(
        file_path=Path("/music/song_128.mp3"),
        file_size=2_000_000,
        bitrate=128,
        duration=240.0,
        title="Song",
        artist="Artist",
    )
    high = Track(
        file_path=Path("/music/song_320.mp3"),
        file_size=5_000_000,
        bitrate=320,
        duration=240.0,
        title="Song",
    )
    group = DupeGroup(tracks=[low, high])
    best = group.best_track()
    assert best.file_path == Path("/music/song_320.mp3")


def test_dupe_group_best_track_tiebreak_by_completeness():
    a = Track(
        file_path=Path("/a.mp3"),
        file_size=5_000_000,
        bitrate=320,
        duration=240.0,
        tag_completeness=0.5,
    )
    b = Track(
        file_path=Path("/b.mp3"),
        file_size=5_000_000,
        bitrate=320,
        duration=240.0,
        tag_completeness=0.8,
    )
    group = DupeGroup(tracks=[a, b])
    assert group.best_track().file_path == Path("/b.mp3")


def test_tag_conflict():
    conflict = TagConflict(
        file_path=Path("/music/song.mp3"),
        field="genre",
        file_value="Electronic",
        itunes_value="Dance",
    )
    assert conflict.field == "genre"
    assert conflict.resolution is None


def test_rename_operation():
    op = RenameOperation(
        source=Path("/old/song.mp3"),
        destination=Path("/new/song.mp3"),
    )
    assert op.status == "pending"


def test_history_entry():
    entry = HistoryEntry(
        action="tag_write",
        file_path=Path("/music/song.mp3"),
        field="artist",
        old_value="Beetles",
        new_value="The Beatles",
    )
    assert entry.session_id is None
    assert entry.timestamp is not None


def test_normalization_rule():
    rule = NormalizationRule(
        field="genre",
        rule_type="mapping",
        parameters={"Hip Hop": "Hip-Hop"},
    )
    assert rule.field == "genre"


def test_playlist_definition():
    playlist = PlaylistDefinition(
        name="High Energy",
        folder="DJ/Sets",
        format="m3u",
        filters={"bucket": "DJ Music", "bpm": {"min": 125, "max": 140}},
        sort_by="bpm",
    )
    assert playlist.folder == "DJ/Sets"
