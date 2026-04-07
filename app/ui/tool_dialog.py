from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.core.tool_registry import ToolManifest


class ToolDialog(QDialog):
    def __init__(
        self,
        manifest: ToolManifest,
        tool: Any,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self.setObjectName("toolDialog")
        self.setWindowTitle(f"{manifest.name} - Tools")
        self.resize(720, 460)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(18)

        header = QHBoxLayout()
        header.setSpacing(14)

        title_area = QVBoxLayout()
        title_area.setSpacing(6)

        title = QLabel(manifest.name)
        title.setObjectName("dialogTitle")

        description = QLabel(manifest.description)
        description.setObjectName("toolDescription")
        description.setWordWrap(True)

        title_area.addWidget(title)
        title_area.addWidget(description)

        close_button = QPushButton("Close")
        close_button.setObjectName("secondaryButton")
        close_button.clicked.connect(self.accept)

        header.addLayout(title_area, 1)
        header.addWidget(close_button)
        layout.addLayout(header)

        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setObjectName("dialogSeparator")
        layout.addWidget(separator)

        content = tool.create_widget(self)
        if not isinstance(content, QWidget):
            raise TypeError(f"{manifest.entry_point} did not return a QWidget")

        layout.addWidget(content, 1)

