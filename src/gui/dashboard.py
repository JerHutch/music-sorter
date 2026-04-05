from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QGroupBox,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont


class StatCard(QWidget):
    """A small card widget displaying a large number and a descriptive label."""

    def __init__(self, label: str, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._value_label = QLabel("0")
        value_font = QFont()
        value_font.setPointSize(28)
        value_font.setBold(True)
        self._value_label.setFont(value_font)
        self._value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        desc_label = QLabel(label)
        desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc_label.setWordWrap(True)

        layout.addWidget(self._value_label)
        layout.addWidget(desc_label)

        self.setFixedWidth(160)
        self.setStyleSheet(
            "StatCard { background: #f5f5f5; border: 1px solid #ddd; border-radius: 6px; }"
        )

    def set_value(self, value: int) -> None:
        self._value_label.setText(str(value))


class Dashboard(QWidget):
    """Dashboard view showing collection statistics at a glance."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        title = QLabel("Collection Overview")
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)

        # Stat cards row
        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(12)

        self._total_card = StatCard("Total Tracks")
        self._fully_tagged_card = StatCard("Fully Tagged")
        self._partially_tagged_card = StatCard("Partially Tagged")
        self._missing_tags_card = StatCard("Missing Tags")
        self._duplicates_card = StatCard("Duplicates")
        self._no_artwork_card = StatCard("No Artwork")

        for card in (
            self._total_card,
            self._fully_tagged_card,
            self._partially_tagged_card,
            self._missing_tags_card,
            self._duplicates_card,
            self._no_artwork_card,
        ):
            cards_layout.addWidget(card)

        cards_layout.addStretch()
        layout.addLayout(cards_layout)

        # Charts placeholder
        charts_group = QGroupBox("Distribution Charts")
        charts_inner = QVBoxLayout(charts_group)
        charts_inner.addWidget(QLabel("Charts will appear here once data is loaded."))
        layout.addWidget(charts_group)

        layout.addStretch()

    def update_stats(self, stats: dict) -> None:
        """Populate stat cards from a stats dict as returned by Database.get_stats()."""
        total = stats.get("total_tracks", 0)
        self._total_card.set_value(total)

        # These keys may be extended by the caller; fall back to 0 if absent
        self._fully_tagged_card.set_value(stats.get("fully_tagged", 0))
        self._partially_tagged_card.set_value(stats.get("partially_tagged", 0))
        self._missing_tags_card.set_value(stats.get("missing_tags", 0))
        self._duplicates_card.set_value(stats.get("duplicates", 0))
        self._no_artwork_card.set_value(stats.get("no_artwork", 0))
