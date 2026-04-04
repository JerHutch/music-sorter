from pathlib import Path
import pytest
from src.core.normalizer import normalize_case, normalize_artist_prefix, normalize_genre, apply_custom_rule, scan_normalizations
from src.core.models import Track

def _track(**kwargs):
    defaults = dict(file_path=Path("/test.mp3"), file_size=1000, bitrate=320, duration=100.0, has_artwork=False)
    defaults.update(kwargs)
    return Track(**defaults)

def test_normalize_case_title():
    assert normalize_case("hello world", "title") == "Hello World"

def test_normalize_case_preserves_already_correct():
    assert normalize_case("Hello World", "title") == "Hello World"

def test_normalize_case_as_is():
    assert normalize_case("hElLo", "as_is") == "hElLo"

def test_normalize_artist_prefix_the_first():
    assert normalize_artist_prefix("Beatles, The", "the_first") == "The Beatles"

def test_normalize_artist_prefix_the_last():
    assert normalize_artist_prefix("The Beatles", "the_last") == "Beatles, The"

def test_normalize_artist_prefix_no_change():
    assert normalize_artist_prefix("Deadmau5", "the_first") == "Deadmau5"

def test_normalize_genre_mapping():
    genre_map = {"Hip Hop": "Hip-Hop", "HipHop": "Hip-Hop", "DnB": "Drum & Bass"}
    assert normalize_genre("Hip Hop", genre_map) == "Hip-Hop"
    assert normalize_genre("HipHop", genre_map) == "Hip-Hop"
    assert normalize_genre("Rock", genre_map) == "Rock"

def test_apply_custom_rule_regex():
    rule = {"field": "artist", "find": r"Deadmau\d", "replace": "deadmau5"}
    assert apply_custom_rule("Deadmau5", rule) == "deadmau5"
    assert apply_custom_rule("New Order", rule) == "New Order"

def test_scan_normalizations():
    tracks = [
        _track(title="hello world", artist="Beatles, The", genre="Hip Hop"),
        _track(title="LOUD SONG", artist="The Beatles", genre="Rock"),
    ]
    config = {
        "artist_prefix": "the_first",
        "case_mode": "title",
        "genre_map": {"Hip Hop": "Hip-Hop"},
        "custom_rules": [],
    }
    changes = scan_normalizations(tracks, config)
    assert len(changes) > 0
    fields_changed = {c[1] for c in changes}
    assert "title" in fields_changed or "artist" in fields_changed
