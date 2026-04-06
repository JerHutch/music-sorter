from __future__ import annotations

from PySide6.QtWidgets import QWidget, QGridLayout
from PySide6.QtCharts import (
    QChart, QChartView,
    QPieSeries,
    QBarSeries, QBarSet, QBarCategoryAxis, QValueAxis,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter


def _make_chart(title: str) -> QChart:
    chart = QChart()
    chart.setTitle(title)
    chart.setAnimationOptions(QChart.AnimationOption.NoAnimation)
    chart.legend().setVisible(True)
    chart.legend().setAlignment(Qt.AlignmentFlag.AlignBottom)
    return chart


def _chart_view(chart: QChart) -> QChartView:
    view = QChartView(chart)
    view.setRenderHint(QPainter.RenderHint.Antialiasing)
    view.setMinimumHeight(200)
    return view


class StatsView(QWidget):
    """Charts for tag completeness, genre distribution, bitrate, and storage."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QGridLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self._completeness_chart = _make_chart("Tag Completeness")
        self._completeness_view = _chart_view(self._completeness_chart)
        layout.addWidget(self._completeness_view, 0, 0)

        self._genre_chart = _make_chart("Genre Distribution")
        self._genre_view = _chart_view(self._genre_chart)
        layout.addWidget(self._genre_view, 0, 1)

        self._bitrate_chart = _make_chart("Bitrate Distribution")
        self._bitrate_view = _chart_view(self._bitrate_chart)
        layout.addWidget(self._bitrate_view, 1, 0)

        self._bucket_chart = _make_chart("Tracks per Bucket")
        self._bucket_view = _chart_view(self._bucket_chart)
        layout.addWidget(self._bucket_view, 1, 1)

    def update_stats(self, stats: dict) -> None:
        self._update_completeness(stats)
        self._update_genre(stats.get("genre_counts", {}))
        self._update_bitrate(stats.get("bitrate_counts", {}))
        self._update_bucket(stats.get("bucket_counts", {}))

    def _update_completeness(self, stats: dict) -> None:
        series = QPieSeries()
        fully = stats.get("fully_tagged", 0)
        partial = stats.get("partially_tagged", 0)
        missing = stats.get("missing_tags", 0)
        if fully + partial + missing == 0:
            series.append("No data", 1)
        else:
            if fully:
                series.append(f"Fully tagged ({fully})", fully)
            if partial:
                series.append(f"Partial ({partial})", partial)
            if missing:
                series.append(f"Missing ({missing})", missing)
        self._completeness_chart.removeAllSeries()
        self._completeness_chart.addSeries(series)

    def _update_genre(self, genre_counts: dict) -> None:
        self._genre_chart.removeAllSeries()
        for ax in list(self._genre_chart.axes()):
            self._genre_chart.removeAxis(ax)
        if not genre_counts:
            return
        top = sorted(genre_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        bar_set = QBarSet("Tracks")
        categories = []
        for genre, count in top:
            bar_set.append(count)
            categories.append(genre[:12])
        series = QBarSeries()
        series.append(bar_set)
        self._genre_chart.addSeries(series)
        axis_x = QBarCategoryAxis()
        axis_x.append(categories)
        axis_x.setLabelsAngle(-45)
        self._genre_chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
        series.attachAxis(axis_x)
        axis_y = QValueAxis()
        self._genre_chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
        series.attachAxis(axis_y)

    def _update_bitrate(self, bitrate_counts: dict) -> None:
        self._bitrate_chart.removeAllSeries()
        for ax in list(self._bitrate_chart.axes()):
            self._bitrate_chart.removeAxis(ax)
        if not bitrate_counts:
            return
        sorted_bitrates = sorted(bitrate_counts.items())
        bar_set = QBarSet("Tracks")
        categories = []
        for bitrate, count in sorted_bitrates:
            bar_set.append(count)
            categories.append(f"{bitrate}k")
        series = QBarSeries()
        series.append(bar_set)
        self._bitrate_chart.addSeries(series)
        axis_x = QBarCategoryAxis()
        axis_x.append(categories)
        self._bitrate_chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
        series.attachAxis(axis_x)
        axis_y = QValueAxis()
        self._bitrate_chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
        series.attachAxis(axis_y)

    def _update_bucket(self, bucket_counts: dict) -> None:
        self._bucket_chart.removeAllSeries()
        for ax in list(self._bucket_chart.axes()):
            self._bucket_chart.removeAxis(ax)
        if not bucket_counts:
            return
        bar_set = QBarSet("Tracks")
        categories = list(bucket_counts.keys())
        for cat in categories:
            bar_set.append(bucket_counts[cat])
        series = QBarSeries()
        series.append(bar_set)
        self._bucket_chart.addSeries(series)
        axis_x = QBarCategoryAxis()
        axis_x.append(categories)
        self._bucket_chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
        series.attachAxis(axis_x)
        axis_y = QValueAxis()
        self._bucket_chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
        series.attachAxis(axis_y)
