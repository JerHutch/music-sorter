from __future__ import annotations
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from src.core.models import Track
from src.gui.artwork_panel import ArtworkPanel

_PNG_1X1 = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
    b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00"
    b"\x00\x00\x0cIDATx\x9cc\xf8\xcf\xc0\x00\x00\x03\x01"
    b"\x01\x00\xc9\xfe\x92\xef\x00\x00\x00\x00IEND\xaeB`\x82"
)


def _make_track(tmp_path, title="Test Track"):
    p = tmp_path / "track.mp3"
    p.write_bytes(b"")
    return Track(
        file_path=p, file_size=1000, bitrate=320, duration=200.0,
        title=title, artist="Artist", album="Album", tag_completeness=0.9,
    )


def test_load_track_with_artwork_shows_image(qtbot, tmp_path):
    panel = ArtworkPanel()
    qtbot.addWidget(panel)
    track = _make_track(tmp_path)
    with patch("src.gui.artwork_panel.read_artwork", return_value=_PNG_1X1):
        panel.load_track(track)
    assert panel._image_label.isVisible()
    assert not panel._placeholder_label.isVisible()


def test_load_track_without_artwork_shows_placeholder(qtbot, tmp_path):
    panel = ArtworkPanel()
    qtbot.addWidget(panel)
    track = _make_track(tmp_path)
    with patch("src.gui.artwork_panel.read_artwork", return_value=None):
        panel.load_track(track)
    assert not panel._image_label.isVisible()
    assert panel._placeholder_label.isVisible()


def test_load_batch_shows_batch_ui(qtbot, tmp_path):
    panel = ArtworkPanel()
    qtbot.addWidget(panel)
    tracks = [_make_track(tmp_path, f"Track {i}") for i in range(3)]
    panel.load_batch(tracks)
    assert panel._batch_widget.isVisible()
    assert not panel._single_btns.isVisible()
    assert "3" in panel._batch_label.text()


def test_scan_requested_signal_fires(qtbot, tmp_path):
    panel = ArtworkPanel()
    qtbot.addWidget(panel)
    track = _make_track(tmp_path)
    with patch("src.gui.artwork_panel.read_artwork", return_value=None):
        panel.load_track(track)
    captured = []
    panel.scan_requested.connect(lambda tracks: captured.append(tracks))
    panel._scan_btn.click()
    assert captured == [[track]]


def test_upload_requested_signal_fires(qtbot, tmp_path):
    panel = ArtworkPanel()
    qtbot.addWidget(panel)
    track = _make_track(tmp_path)
    # Write a real PNG to disk so QImage can load it
    img_file = tmp_path / "cover.png"
    img_file.write_bytes(_PNG_1X1)
    with patch("src.gui.artwork_panel.read_artwork", return_value=None):
        panel.load_track(track)
    captured = []
    panel.upload_requested.connect(lambda tracks, data: captured.append((tracks, data)))
    with patch("src.gui.artwork_panel.QFileDialog.getOpenFileName",
               return_value=(str(img_file), "")):
        panel._upload_btn.click()
    assert len(captured) == 1
    assert captured[0][0] == [track]
    assert len(captured[0][1]) > 0


def test_set_scanning_disables_buttons(qtbot, tmp_path):
    panel = ArtworkPanel()
    qtbot.addWidget(panel)
    track = _make_track(tmp_path)
    with patch("src.gui.artwork_panel.read_artwork", return_value=None):
        panel.load_track(track)
    panel.set_scanning(True)
    assert not panel._scan_btn.isEnabled()
    assert not panel._upload_btn.isEnabled()
    assert not panel._batch_scan_btn.isEnabled()
    assert not panel._batch_upload_btn.isEnabled()
    panel.set_scanning(False)
    assert panel._scan_btn.isEnabled()
    assert panel._upload_btn.isEnabled()
    assert panel._batch_scan_btn.isEnabled()
    assert panel._batch_upload_btn.isEnabled()


def test_batch_upload_emits_all_tracks(qtbot, tmp_path):
    panel = ArtworkPanel()
    qtbot.addWidget(panel)
    tracks = [_make_track(tmp_path, f"Track {i}") for i in range(3)]
    panel.load_batch(tracks)
    img_file = tmp_path / "cover.png"
    img_file.write_bytes(_PNG_1X1)
    captured = []
    panel.upload_requested.connect(lambda ts, data: captured.append((ts, data)))
    with patch("src.gui.artwork_panel.QFileDialog.getOpenFileName",
               return_value=(str(img_file), "")):
        panel._batch_upload_btn.click()
    assert len(captured) == 1
    assert captured[0][0] == tracks
    assert len(captured[0][1]) > 0
