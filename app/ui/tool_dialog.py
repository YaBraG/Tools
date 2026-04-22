from __future__ import annotations

from typing import Any

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
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
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
        self.setWindowFlag(Qt.WindowType.WindowMinimizeButtonHint, True)
        self.setWindowFlag(Qt.WindowType.WindowMaximizeButtonHint, True)
        self.setModal(False)
        self.setWindowModality(Qt.WindowModality.NonModal)
        self.setWindowTitle(f"{manifest.name} - Tools")
        self.resize(self._initial_size())
        self.setMinimumSize(900, 620)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        header = QHBoxLayout()
        header.setSpacing(12)

        title_area = QVBoxLayout()
        title_area.setSpacing(4)

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

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setObjectName("dialogScroll")
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setWidget(content)

        layout.addWidget(scroll_area, 1)

    @staticmethod
    def _initial_size() -> QSize:
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return QSize(1140, 780)

        available = screen.availableGeometry()
        width = min(1240, max(980, available.width() - 96))
        height = min(860, max(680, available.height() - 96))
        return QSize(width, height)
