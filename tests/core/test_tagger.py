from pathlib import Path

from src.core.tagger import COMPLETENESS_FIELDS, read_tags, write_tags


def test_read_tags_fully_tagged(tagged_full_mp3):
    track = read_tags(tagged_full_mp3)
    assert track.title == "Blue Monday"
    assert track.artist == "New Order"
    assert track.album_artist == "New Order"
    assert track.album == "Power, Corruption & Lies"
    assert track.track_number == 5
    assert track.disc_number == 1
    assert track.year == 1983
    assert track.genre == "Synth-Pop"
    assert track.bpm == 130.0
    assert track.bucket == "DJ Music"
    assert track.file_path == tagged_full_mp3
    assert track.bitrate > 0
    assert track.duration > 0


def test_read_tags_partial(tagged_partial_mp3):
    track = read_tags(tagged_partial_mp3)
    assert track.title == "Strobe"
    assert track.artist == "Deadmau5"
    assert track.genre == "Progressive House"
    assert track.album is None
    assert track.year is None
    assert track.bpm is None
    assert track.bucket is None


def test_read_tags_untagged(untagged_mp3):
    track = read_tags(untagged_mp3)
    assert track.title is None
    assert track.artist is None
    assert track.file_size > 0


def test_write_tags(tagged_partial_mp3):
    track = read_tags(tagged_partial_mp3)
    track.album = "For Lack of a Better Name"
    track.year = 2009
    track.bucket = "DJ Music"
    track.bpm = 128.0

    write_tags(tagged_partial_mp3, track, ["album", "year", "bucket", "bpm"])

    reloaded = read_tags(tagged_partial_mp3)
    assert reloaded.album == "For Lack of a Better Name"
    assert reloaded.year == 2009
    assert reloaded.bucket == "DJ Music"
    assert reloaded.bpm == 128.0
    # Original tags preserved
    assert reloaded.title == "Strobe"
    assert reloaded.artist == "Deadmau5"


def test_write_tags_dry_run(tagged_partial_mp3):
    track = read_tags(tagged_partial_mp3)
    track.album = "Changed Album"

    write_tags(tagged_partial_mp3, track, ["album"], dry_run=True)

    reloaded = read_tags(tagged_partial_mp3)
    assert reloaded.album is None  # unchanged because dry_run


def test_write_tags_adds_id3_to_untagged(untagged_mp3):
    track = read_tags(untagged_mp3)
    track.title = "New Song"
    track.artist = "New Artist"

    write_tags(untagged_mp3, track, ["title", "artist"])

    reloaded = read_tags(untagged_mp3)
    assert reloaded.title == "New Song"
    assert reloaded.artist == "New Artist"


def test_read_tags_computes_completeness_for_full_track(tagged_full_mp3):
    """read_tags should set tag_completeness > 0 when fields are present."""
    track = read_tags(tagged_full_mp3)
    assert track.tag_completeness > 0.0


def test_read_tags_completeness_partial_track(tagged_partial_mp3):
    """Partial track (missing album, year, bucket) should have completeness < 1.0."""
    track = read_tags(tagged_partial_mp3)
    assert 0.0 < track.tag_completeness < 1.0


def test_read_tags_completeness_untagged(untagged_mp3):
    """Untagged track should have completeness == 0.0."""
    track = read_tags(untagged_mp3)
    assert track.tag_completeness == 0.0


def test_completeness_fields_is_public():
    """COMPLETENESS_FIELDS should be importable and non-empty."""
    assert len(COMPLETENESS_FIELDS) > 0


def test_compute_completeness_with_config():
    from src.core.config import Config
    from src.core.models import Track

    config = Config.load_defaults()
    t = Track(
        file_path=Path("/test.mp3"), file_size=100, bitrate=320, duration=100.0,
        title="Test", artist="Artist", album="Album", genre="Rock", year=2020, bucket="General",
    )
    required = config.get_required_tags("General")
    completeness = t.compute_completeness(required)
    assert completeness == 1.0

    dj_required = config.get_required_tags("DJ Music")
    dj_completeness = t.compute_completeness(dj_required)
    assert dj_completeness < 1.0  # missing bpm and key
