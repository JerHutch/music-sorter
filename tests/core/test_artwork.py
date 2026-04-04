from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest
from src.core.artwork import search_cover_art, embed_artwork, has_artwork

def test_has_artwork_false(untagged_mp3):
    assert has_artwork(untagged_mp3) is False

def test_has_artwork_true_after_embed(untagged_mp3):
    png_data = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
        b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00"
        b"\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00"
        b"\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    embed_artwork(untagged_mp3, png_data)
    assert has_artwork(untagged_mp3) is True

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
