from __future__ import annotations

import time
from pathlib import Path

import pytest

from src.core.models import SimpleRule, RuleGroup, SmartPlaylist, Track
from src.core.playlist import (
    FIELD_REGISTRY,
    OPERATORS_BY_TYPE,
    evaluate_rule,
    evaluate_playlist,
    generate_m3u,
    generate_pls,
)


def _track(path="/music/song.mp3", **kwargs) -> Track:
    defaults = dict(
        file_path=Path(path),
        file_size=5_000_000,
        bitrate=320,
        duration=240.0,
        title="Song",
        artist="Artist",
        has_artwork=False,
        tag_completeness=0.8,
        date_added=time.time() - 3600,
    )
    defaults.update(kwargs)
    return Track(**defaults)


# ---------------------------------------------------------------------------
# generate_m3u / generate_pls (unchanged behaviour)
# ---------------------------------------------------------------------------

def test_generate_m3u(tmp_path):
    tracks = [
        _track("/music/a.mp3", title="Song A", artist="Artist A", duration=180.0),
        _track("/music/b.mp3", title="Song B", artist="Artist B", duration=200.0),
    ]
    output = tmp_path / "playlist.m3u"
    generate_m3u(tracks, output)
    content = output.read_text()
    assert "#EXTM3U" in content
    assert "#EXTINF:180,Artist A - Song A" in content
    assert "/music/a.mp3" in content


def test_generate_pls(tmp_path):
    tracks = [
        _track("/music/a.mp3", title="Song A", duration=180.0),
        _track("/music/b.mp3", title="Song B", duration=200.0),
    ]
    output = tmp_path / "playlist.pls"
    generate_pls(tracks, output)
    content = output.read_text()
    assert "[playlist]" in content
    assert "File1=/music/a.mp3" in content
    assert "NumberOfEntries=2" in content


# ---------------------------------------------------------------------------
# Field registry
# ---------------------------------------------------------------------------

def test_field_registry_contains_expected_fields():
    for field in ("title", "artist", "genre", "bpm", "has_artwork", "date_added"):
        assert field in FIELD_REGISTRY


def test_operators_by_type_keys():
    for t in ("string", "number", "boolean", "date"):
        assert t in OPERATORS_BY_TYPE


# ---------------------------------------------------------------------------
# String operators
# ---------------------------------------------------------------------------

def test_string_contains():
    rule = SimpleRule(field="genre", operator="contains", value="elec")
    assert evaluate_rule(rule, _track(genre="Electronic")) is True
    assert evaluate_rule(rule, _track(genre="Rock")) is False


def test_string_contains_case_insensitive():
    rule = SimpleRule(field="artist", operator="contains", value="beatles")
    assert evaluate_rule(rule, _track(artist="The Beatles")) is True


def test_string_does_not_contain():
    rule = SimpleRule(field="genre", operator="does_not_contain", value="Jazz")
    assert evaluate_rule(rule, _track(genre="Rock")) is True
    assert evaluate_rule(rule, _track(genre="Jazz")) is False


def test_string_is():
    rule = SimpleRule(field="genre", operator="is", value="Jazz")
    assert evaluate_rule(rule, _track(genre="Jazz")) is True
    assert evaluate_rule(rule, _track(genre="Rock")) is False


def test_string_is_not():
    rule = SimpleRule(field="genre", operator="is_not", value="Jazz")
    assert evaluate_rule(rule, _track(genre="Rock")) is True
    assert evaluate_rule(rule, _track(genre="Jazz")) is False


def test_string_starts_with():
    rule = SimpleRule(field="artist", operator="starts_with", value="The")
    assert evaluate_rule(rule, _track(artist="The Beatles")) is True
    assert evaluate_rule(rule, _track(artist="Beatles")) is False


def test_string_ends_with():
    rule = SimpleRule(field="title", operator="ends_with", value="wall")
    assert evaluate_rule(rule, _track(title="Wonderwall")) is True
    assert evaluate_rule(rule, _track(title="Wonder")) is False


# ---------------------------------------------------------------------------
# Number operators
# ---------------------------------------------------------------------------

def test_number_gt():
    rule = SimpleRule(field="bpm", operator="gt", value=120)
    assert evaluate_rule(rule, _track(bpm=140.0)) is True
    assert evaluate_rule(rule, _track(bpm=100.0)) is False


def test_number_lt():
    rule = SimpleRule(field="bpm", operator="lt", value=120)
    assert evaluate_rule(rule, _track(bpm=100.0)) is True
    assert evaluate_rule(rule, _track(bpm=140.0)) is False


def test_number_gte():
    rule = SimpleRule(field="bpm", operator="gte", value=120)
    assert evaluate_rule(rule, _track(bpm=120.0)) is True
    assert evaluate_rule(rule, _track(bpm=119.0)) is False


def test_number_lte():
    rule = SimpleRule(field="bpm", operator="lte", value=120)
    assert evaluate_rule(rule, _track(bpm=120.0)) is True
    assert evaluate_rule(rule, _track(bpm=121.0)) is False


def test_number_is():
    rule = SimpleRule(field="year", operator="is", value=2020)
    assert evaluate_rule(rule, _track(year=2020)) is True
    assert evaluate_rule(rule, _track(year=2021)) is False


def test_number_is_not():
    rule = SimpleRule(field="year", operator="is_not", value=2021)
    assert evaluate_rule(rule, _track(year=2020)) is True
    assert evaluate_rule(rule, _track(year=2021)) is False


def test_number_in_range():
    rule = SimpleRule(field="bpm", operator="in_range", value=(120, 140))
    assert evaluate_rule(rule, _track(bpm=128.0)) is True
    assert evaluate_rule(rule, _track(bpm=100.0)) is False
    assert evaluate_rule(rule, _track(bpm=150.0)) is False


# ---------------------------------------------------------------------------
# Boolean operators
# ---------------------------------------------------------------------------

def test_boolean_is_true():
    rule = SimpleRule(field="has_artwork", operator="is_true", value=None)
    assert evaluate_rule(rule, _track(has_artwork=True)) is True
    assert evaluate_rule(rule, _track(has_artwork=False)) is False


def test_boolean_is_false():
    rule = SimpleRule(field="has_artwork", operator="is_false", value=None)
    assert evaluate_rule(rule, _track(has_artwork=False)) is True
    assert evaluate_rule(rule, _track(has_artwork=True)) is False


# ---------------------------------------------------------------------------
# Date operators
# ---------------------------------------------------------------------------

def test_date_before():
    old = time.time() - 86400 * 30
    recent = time.time() - 3600
    cutoff = time.time() - 86400 * 7
    rule = SimpleRule(field="date_added", operator="before", value=cutoff)
    assert evaluate_rule(rule, _track(date_added=old)) is True
    assert evaluate_rule(rule, _track(date_added=recent)) is False


def test_date_after():
    old = time.time() - 86400 * 30
    recent = time.time() - 3600
    cutoff = time.time() - 86400 * 7
    rule = SimpleRule(field="date_added", operator="after", value=cutoff)
    assert evaluate_rule(rule, _track(date_added=recent)) is True
    assert evaluate_rule(rule, _track(date_added=old)) is False


def test_date_in_last_days():
    recent = time.time() - 3600  # 1 hour ago
    old = time.time() - 86400 * 30  # 30 days ago
    rule = SimpleRule(field="date_added", operator="in_last_days", value=7)
    assert evaluate_rule(rule, _track(date_added=recent)) is True
    assert evaluate_rule(rule, _track(date_added=old)) is False


# ---------------------------------------------------------------------------
# None field value
# ---------------------------------------------------------------------------

def test_none_field_returns_false():
    rule = SimpleRule(field="genre", operator="contains", value="Jazz")
    assert evaluate_rule(rule, _track(genre=None)) is False


def test_none_bpm_returns_false():
    rule = SimpleRule(field="bpm", operator="gt", value=100)
    assert evaluate_rule(rule, _track(bpm=None)) is False


# ---------------------------------------------------------------------------
# RuleGroup
# ---------------------------------------------------------------------------

def test_rule_group_and_all_match():
    group = RuleGroup(conjunction="AND", rules=[
        SimpleRule(field="genre", operator="is", value="Jazz"),
        SimpleRule(field="bpm", operator="gt", value=90),
    ])
    assert evaluate_rule(group, _track(genre="Jazz", bpm=100.0)) is True


def test_rule_group_and_one_fails():
    group = RuleGroup(conjunction="AND", rules=[
        SimpleRule(field="genre", operator="is", value="Jazz"),
        SimpleRule(field="bpm", operator="gt", value=90),
    ])
    assert evaluate_rule(group, _track(genre="Rock", bpm=100.0)) is False


def test_rule_group_or_one_matches():
    group = RuleGroup(conjunction="OR", rules=[
        SimpleRule(field="genre", operator="is", value="Jazz"),
        SimpleRule(field="genre", operator="is", value="Blues"),
    ])
    assert evaluate_rule(group, _track(genre="Jazz")) is True
    assert evaluate_rule(group, _track(genre="Blues")) is True
    assert evaluate_rule(group, _track(genre="Rock")) is False


# ---------------------------------------------------------------------------
# evaluate_playlist
# ---------------------------------------------------------------------------

def test_evaluate_playlist_basic():
    tracks = [
        _track("/a.mp3", genre="Jazz"),
        _track("/b.mp3", genre="Rock"),
    ]
    playlist = SmartPlaylist(name="Jazz", rules=[
        SimpleRule(field="genre", operator="is", value="Jazz"),
    ])
    result = evaluate_playlist(playlist, tracks)
    assert len(result) == 1
    assert result[0].file_path == Path("/a.mp3")


def test_evaluate_playlist_empty_rules_returns_all():
    tracks = [_track(f"/{i}.mp3") for i in range(3)]
    assert len(evaluate_playlist(SmartPlaylist(name="All"), tracks)) == 3


def test_evaluate_playlist_top_level_or():
    tracks = [
        _track("/a.mp3", genre="Jazz"),
        _track("/b.mp3", genre="Blues"),
        _track("/c.mp3", genre="Rock"),
    ]
    playlist = SmartPlaylist(name="Jazz or Blues", conjunction="OR", rules=[
        SimpleRule(field="genre", operator="is", value="Jazz"),
        SimpleRule(field="genre", operator="is", value="Blues"),
    ])
    result = evaluate_playlist(playlist, tracks)
    assert len(result) == 2


def test_evaluate_playlist_sort_by():
    tracks = [
        _track("/a.mp3", bpm=140.0),
        _track("/b.mp3", bpm=90.0),
        _track("/c.mp3", bpm=120.0),
    ]
    playlist = SmartPlaylist(name="Sorted", sort_by="bpm")
    result = evaluate_playlist(playlist, tracks)
    assert [t.bpm for t in result] == [90.0, 120.0, 140.0]


def test_evaluate_playlist_limit():
    tracks = [_track(f"/{i}.mp3") for i in range(10)]
    playlist = SmartPlaylist(name="Limited", limit_count=3)
    result = evaluate_playlist(playlist, tracks)
    assert len(result) == 3


def test_evaluate_playlist_limit_by_field():
    tracks = [_track(f"/{i}.mp3", bpm=float(i * 10)) for i in range(5)]
    playlist = SmartPlaylist(name="Top2", limit_count=2, limit_order="bpm")
    result = evaluate_playlist(playlist, tracks)
    assert len(result) == 2
    assert result[0].bpm == 0.0
    assert result[1].bpm == 10.0


def test_evaluate_playlist_with_rule_group():
    tracks = [
        _track("/a.mp3", genre="Jazz", bpm=100.0),
        _track("/b.mp3", genre="Blues", bpm=80.0),
        _track("/c.mp3", genre="Rock", bpm=140.0),
    ]
    playlist = SmartPlaylist(name="Jazz or Blues with low BPM", conjunction="AND", rules=[
        RuleGroup(conjunction="OR", rules=[
            SimpleRule(field="genre", operator="is", value="Jazz"),
            SimpleRule(field="genre", operator="is", value="Blues"),
        ]),
        SimpleRule(field="bpm", operator="lt", value=120),
    ])
    result = evaluate_playlist(playlist, tracks)
    assert len(result) == 2
    paths = {t.file_path for t in result}
    assert Path("/a.mp3") in paths
    assert Path("/b.mp3") in paths
