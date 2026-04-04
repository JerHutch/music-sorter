from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

from src.core.analyzer import detect_bpm, detect_key, _pitch_class_to_camelot


def test_pitch_class_to_camelot():
    assert _pitch_class_to_camelot(0, True) == "8B"   # C major
    assert _pitch_class_to_camelot(0, False) == "5A"   # C minor
    assert _pitch_class_to_camelot(7, True) == "9B"    # G major


@patch("src.core.analyzer.librosa")
def test_detect_bpm(mock_librosa):
    mock_librosa.load.return_value = (np.zeros(44100 * 30), 44100)
    mock_librosa.beat.beat_track.return_value = (128.5, np.array([0, 100, 200]))
    result = detect_bpm(Path("/fake/song.mp3"))
    assert result == 128.5
    mock_librosa.load.assert_called_once()


@patch("src.core.analyzer.librosa")
def test_detect_bpm_returns_none_on_error(mock_librosa):
    mock_librosa.load.side_effect = Exception("decode error")
    result = detect_bpm(Path("/fake/bad.mp3"))
    assert result is None


@patch("src.core.analyzer.librosa")
def test_detect_key(mock_librosa):
    chroma = np.zeros((12, 100))
    chroma[0, :] = 1.0  # C is dominant
    mock_librosa.load.return_value = (np.zeros(44100 * 30), 44100)
    mock_librosa.feature.chroma_cqt.return_value = chroma
    result = detect_key(Path("/fake/song.mp3"))
    assert result is not None
    assert result[-1] in ("A", "B")


@patch("src.core.analyzer.librosa")
def test_detect_key_returns_none_on_error(mock_librosa):
    mock_librosa.load.side_effect = Exception("decode error")
    result = detect_key(Path("/fake/bad.mp3"))
    assert result is None
