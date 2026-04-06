import pytest
from src.gui.stats_view import StatsView, ClickableChartView


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


def test_stats_view_zoom_in_hides_grid_shows_zoomed(qtbot):
    view = StatsView()
    qtbot.addWidget(view)
    # Before zoom: grid visible, zoomed hidden, back button hidden
    assert not view._grid_widget.isHidden()
    assert view._zoomed_widget.isHidden()
    assert view._back_btn.isHidden()

    view._zoom_in(view._completeness_view)

    assert view._grid_widget.isHidden()
    assert not view._zoomed_widget.isHidden()
    assert not view._back_btn.isHidden()
    assert view._current_zoomed is view._completeness_view


def test_stats_view_zoom_out_restores_grid(qtbot):
    view = StatsView()
    qtbot.addWidget(view)
    view._zoom_in(view._genre_view)
    view._zoom_out()

    assert not view._grid_widget.isHidden()
    assert view._zoomed_widget.isHidden()
    assert view._back_btn.isHidden()
    assert view._current_zoomed is None


def test_stats_view_zoom_in_ignored_when_already_zoomed(qtbot):
    view = StatsView()
    qtbot.addWidget(view)
    view._zoom_in(view._completeness_view)
    view._zoom_in(view._genre_view)  # should be a no-op
    assert view._current_zoomed is view._completeness_view


def test_clickable_chart_view_emits_clicked(qtbot):
    from PySide6.QtCharts import QChart
    chart = QChart()
    cv = ClickableChartView(chart)
    qtbot.addWidget(cv)
    signals = []
    cv.clicked.connect(lambda: signals.append(1))
    cv.clicked.emit()
    assert signals == [1]
