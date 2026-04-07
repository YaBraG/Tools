from __future__ import annotations

from PySide6.QtWidgets import QWidget

from shared.tool_base import ToolContext
from tools.audio_converter.widget import AudioConverterWidget


class AudioConverterTool:
    def __init__(self, context: ToolContext) -> None:
        self.context = context

    def create_widget(self, parent: QWidget | None = None) -> QWidget:
        return AudioConverterWidget(self.context, parent)

