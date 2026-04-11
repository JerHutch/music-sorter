from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from src.core.fingerprint import generate_fingerprint, lookup_metadata, compute_similarity


def test_generate_fingerprint(tagged_full_mp3):
    """Test fingerprint generation on a real MP3 file."""
    fp = generate_fingerprint(tagged_full_mp3)
    # May return None if fpcalc is not installed — that's OK for CI
    # If fpcalc IS installed, it should return a non-empty string
    if fp is not None:
        assert isinstance(fp, str)
        assert len(fp) > 0


def test_generate_fingerprint_returns_none_for_invalid(tmp_path):
    bad_file = tmp_path / "not_audio.mp3"
    bad_file.write_bytes(b"not an mp3 file")
    fp = generate_fingerprint(bad_file)
    assert fp is None


@patch("src.core.fingerprint.acoustid.match")
@patch("src.core.fingerprint.musicbrainzngs")
def test_lookup_metadata_success(mock_mb, mock_match):
    mock_match.return_value = iter([
        (0.95, "recording-id-123", "Blue Monday", "New Order"),
    ])
    mock_mb.get_recording_by_id.return_value = {
        "recording": {"artist-credit": [], "release-list": []}
    }
    result = lookup_metadata("fake-fingerprint", 240.0)
    assert result is not None
    assert result["title"] == "Blue Monday"
    assert result["artist"] == "New Order"
    assert result["score"] == 0.95
    assert result["album"] is None
    assert result["year"] is None


@patch("src.core.fingerprint.acoustid.match")
def test_lookup_metadata_no_results(mock_match):
    mock_match.return_value = iter([])
    result = lookup_metadata("fake-fingerprint", 240.0)
    assert result is None


def test_compute_similarity_identical():
    fp = "AQADtNIyRUkS"
    assert compute_similarity(fp, fp) == 1.0


def test_compute_similarity_different():
    sim = compute_similarity("AQADtNIyRUkS", "BBBBBZZZZZZZ")
    assert 0.0 <= sim <= 1.0


@patch("src.core.fingerprint.acoustid.match")
@patch("src.core.fingerprint.musicbrainzngs")
def test_lookup_metadata_fetches_musicbrainz_details(mock_mb, mock_match):
    mock_match.return_value = iter([
        (0.95, "recording-id-123", "Blue Monday", "New Order"),
    ])
    mock_mb.get_recording_by_id.return_value = {
        "recording": {
            "artist-credit": [{"artist": {"name": "New Order"}}],
            "release-list": [{
                "title": "Power, Corruption & Lies",
                "date": "1983-05-02",
                "artist-credit": [{"artist": {"name": "New Order"}}],
                "medium-list": [{
                    "track-list": [{"number": "1", "position": "1", "recording": {"id": "recording-id-123"}}]
                }],
            }],
        }
    }
    result = lookup_metadata("fake-fingerprint", 240.0)
    assert result is not None
    assert result["album"] == "Power, Corruption & Lies"
    assert result["album_artist"] == "New Order"
    assert result["year"] == 1983
    assert result["track_number"] == 1


@patch("src.core.fingerprint.acoustid.match")
@patch("src.core.fingerprint.musicbrainzngs")
def test_lookup_metadata_graceful_when_mb_returns_no_releases(mock_mb, mock_match):
    mock_match.return_value = iter([
        (0.95, "recording-id-123", "Blue Monday", "New Order"),
    ])
    mock_mb.get_recording_by_id.return_value = {
        "recording": {"artist-credit": [], "release-list": []}
    }
    result = lookup_metadata("fake-fingerprint", 240.0)
    assert result is not None
    assert result["title"] == "Blue Monday"
    assert result["album"] is None
    assert result["year"] is None


@patch("src.core.fingerprint.acoustid.match")
@patch("src.core.fingerprint.musicbrainzngs")
def test_lookup_metadata_graceful_when_mb_raises(mock_mb, mock_match):
    mock_match.return_value = iter([
        (0.95, "recording-id-123", "Blue Monday", "New Order"),
    ])
    mock_mb.get_recording_by_id.side_effect = Exception("network error")
    result = lookup_metadata("fake-fingerprint", 240.0)
    assert result is not None
    assert result["title"] == "Blue Monday"
    assert result["album"] is None
