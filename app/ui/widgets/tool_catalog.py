from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QLabel,
    QLineEdit,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.core.tool_registry import ToolManifest
from app.ui.widgets.tool_card import ToolCard


class ToolCatalogWidget(QFrame):
    tool_requested = Signal(object)

    def __init__(
        self,
        tools: list[ToolManifest],
        title: str,
        subtitle: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("catalogPanel")
        self.cards: list[ToolCard] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 24)
        layout.setSpacing(16)

        title_label = QLabel(title)
        title_label.setObjectName("catalogTitle")

        subtitle_label = QLabel(subtitle)
        subtitle_label.setObjectName("catalogSubtitle")
        subtitle_label.setWordWrap(True)

        self.search_input = QLineEdit()
        self.search_input.setObjectName("toolSearch")
        self.search_input.setPlaceholderText("Search tools by name, category, or tag")
        self.search_input.textChanged.connect(self._apply_filter)

        layout.addWidget(title_label)
        layout.addWidget(subtitle_label)
        layout.addWidget(self.search_input)

        self.scroll_area = QScrollArea()
        self.scroll_area.setObjectName("toolScroll")
        self.scroll_area.setWidgetResizable(True)

        self.grid_viewport = QWidget()
        self.grid_viewport.setObjectName("toolGridViewport")
        self.grid = QGridLayout(self.grid_viewport)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setHorizontalSpacing(16)
        self.grid.setVerticalSpacing(16)
        self.grid.setColumnStretch(0, 1)
        self.grid.setColumnStretch(1, 1)

        self.empty_state = QLabel("No tools match your search.")
        self.empty_state.setObjectName("emptyState")

        for manifest in tools:
            card = ToolCard(manifest)
            card.launch_requested.connect(self._request_tool)
            self.cards.append(card)

        self.scroll_area.setWidget(self.grid_viewport)
        layout.addWidget(self.scroll_area, 1)
        self._apply_filter("")

    def _request_tool(self, manifest: ToolManifest) -> None:
        self.tool_requested.emit(manifest)

    def _apply_filter(self, text: str) -> None:
        query = text.strip().lower()
        visible_cards = [
            card
            for card in self.cards
            if not query or query in card.manifest.searchable_text
        ]

        while self.grid.count():
            self.grid.takeAt(0)

        for card in self.cards:
            card.setVisible(card in visible_cards)

        if not visible_cards:
            self.empty_state.setVisible(True)
            self.grid.addWidget(self.empty_state, 0, 0, 1, 2)
            return

        self.empty_state.setVisible(False)
        for index, card in enumerate(visible_cards):
            row = index // 2
            column = index % 2
            self.grid.addWidget(card, row, column)

