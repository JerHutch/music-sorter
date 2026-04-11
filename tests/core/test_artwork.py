from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest
from src.core.artwork import search_cover_art, embed_artwork, has_artwork, find_local_artwork, read_artwork

_PNG_1X1 = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
    b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00"
    b"\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00"
    b"\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
)

def test_has_artwork_false(untagged_mp3):
    assert has_artwork(untagged_mp3) is False

def test_has_artwork_true_after_embed(untagged_mp3):
    embed_artwork(untagged_mp3, _PNG_1X1)
    assert has_artwork(untagged_mp3) is True

@patch("src.core.artwork.musicbrainzngs")
def test_search_cover_art_empty_artist_and_album_returns_none(mock_mb):
    result = search_cover_art("", "")
    mock_mb.search_releases.assert_not_called()
    assert result is None

@patch("src.core.artwork.musicbrainzngs")
def test_search_cover_art_success(mock_mb):
    mock_mb.search_releases.return_value = {"release-list": [{"id": "release-123", "score": "100"}]}
    mock_mb.get_image_front.return_value = b"\xff\xd8fake_image_data"
    result = search_cover_art("New Order", "Power, Corruption & Lies")
    assert result is not None
    assert len(result) > 0

@patch("src.core.artwork.musicbrainzngs")
def test_search_cover_art_not_found(mock_mb):
    mock_mb.search_releases.return_value = {"release-list": []}
    result = search_cover_art("Unknown Artist", "Unknown Album")
    assert result is None

def test_embed_artwork_dry_run(untagged_mp3):
    embed_artwork(untagged_mp3, b"fake_data", dry_run=True)
    assert has_artwork(untagged_mp3) is False


def test_find_local_artwork_finds_cover_jpg(tmp_path):
    mp3 = tmp_path / "track.mp3"
    mp3.write_bytes(b"")
    cover = tmp_path / "cover.jpg"
    cover.write_bytes(_PNG_1X1)
    result = find_local_artwork(mp3)
    assert result == _PNG_1X1


def test_find_local_artwork_priority_order(tmp_path):
    """cover.jpg beats folder.jpg"""
    mp3 = tmp_path / "track.mp3"
    mp3.write_bytes(b"")
    (tmp_path / "folder.jpg").write_bytes(b"folder")
    (tmp_path / "cover.jpg").write_bytes(b"cover")
    result = find_local_artwork(mp3)
    assert result == b"cover"


def test_find_local_artwork_none_when_missing(tmp_path):
    mp3 = tmp_path / "track.mp3"
    mp3.write_bytes(b"")
    assert find_local_artwork(mp3) is None


def test_find_local_artwork_case_insensitive(tmp_path):
    mp3 = tmp_path / "track.mp3"
    mp3.write_bytes(b"")
    (tmp_path / "Cover.JPG").write_bytes(b"upper")
    result = find_local_artwork(mp3)
    assert result == b"upper"


def test_read_artwork_returns_bytes(untagged_mp3):
    embed_artwork(untagged_mp3, _PNG_1X1)
    result = read_artwork(untagged_mp3)
    assert result == _PNG_1X1


def test_read_artwork_returns_none_when_absent(untagged_mp3):
    assert read_artwork(untagged_mp3) is None
