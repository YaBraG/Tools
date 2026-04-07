from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from shared.tool_base import ToolContext


class ImageConverterTool:
    def __init__(self, context: ToolContext) -> None:
        self.context = context

    def create_widget(self, parent: QWidget | None = None) -> QWidget:
        widget = QWidget(parent)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        title = QLabel("Image Converter Placeholder")
        title.setObjectName("panelTitle")

        body = QLabel(
            "This tool will host image selection, output format choices, and "
            "conversion progress. The placeholder confirms the plugin entry "
            "point loads correctly."
        )
        body.setObjectName("panelBody")
        body.setWordWrap(True)

        layout.addWidget(title)
        layout.addWidget(body)
        layout.addStretch(1)
        return widget

