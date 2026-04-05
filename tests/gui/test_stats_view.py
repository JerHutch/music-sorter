import pytest
from src.gui.stats_view import StatsView


def test_stats_view_renders_without_data(qtbot):
    view = StatsView()
    qtbot.addWidget(view)
    view.update_stats({
        "fully_tagged": 0,
        "partially_tagged": 0,
        "missing_tags": 0,
        "genre_counts": {},
        "bitrate_counts": {},
        "bucket_counts": {},
    })


def test_stats_view_renders_with_data(qtbot):
    view = StatsView()
    qtbot.addWidget(view)
    view.update_stats({
        "fully_tagged": 100,
        "partially_tagged": 50,
        "missing_tags": 20,
        "genre_counts": {"House": 80, "Techno": 60, "Trance": 30},
        "bitrate_counts": {128: 40, 192: 60, 320: 70},
        "bucket_counts": {"DJ Music": 100, "General": 70},
    })


def test_stats_view_handles_missing_keys(qtbot):
    view = StatsView()
    qtbot.addWidget(view)
    view.update_stats({})  # should not raise
