from __future__ import annotations

from PySide6.QtWidgets import QWidget

from shared.tool_base import ToolContext
from tools.pdf_tools.widget import PdfToolsWidget


class PdfToolsTool:
    def __init__(self, context: ToolContext) -> None:
        self.context = context

    def create_widget(self, parent: QWidget | None = None) -> QWidget:
        return PdfToolsWidget(self.context, parent)

