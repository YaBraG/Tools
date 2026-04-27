from __future__ import annotations

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.core.tool_registry import ToolManifest


class ToolCard(QFrame):
    launch_requested = Signal(object)

    def __init__(self, manifest: ToolManifest, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.manifest = manifest
        self.setObjectName("toolCard")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        header = QHBoxLayout()
        header.setSpacing(10)

        name = QLabel(manifest.name)
        name.setObjectName("toolName")
        name.setWordWrap(True)

        category = QLabel(manifest.category)
        category.setObjectName("toolCategory")
        category.setAlignment(Qt.AlignmentFlag.AlignCenter)

        header.addWidget(name, 1)
        header.addWidget(category)

        description = QLabel(manifest.description)
        description.setObjectName("toolDescription")
        description.setWordWrap(True)

        tags = QLabel(self._format_tags(manifest))
        tags.setObjectName("toolTags")

        launch_button = QPushButton("Open")
        launch_button.setObjectName("primaryButton")
        launch_button.setCursor(Qt.CursorShape.PointingHandCursor)
        launch_button.clicked.connect(self._emit_launch)

        layout.addLayout(header)
        layout.addWidget(description)
        layout.addStretch(1)
        layout.addWidget(tags)
        layout.addWidget(launch_button)

    def _emit_launch(self) -> None:
        self.launch_requested.emit(self.manifest)

    @staticmethod
    def _format_tags(manifest: ToolManifest) -> str:
        if not manifest.tags:
            return manifest.category.lower()

        return ", ".join(manifest.tags)
