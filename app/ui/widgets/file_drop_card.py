from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QMouseEvent
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget


class FileDropCard(QFrame):
    clicked = Signal()
    paths_dropped = Signal(list)

    def __init__(
        self,
        *,
        accepted_type_text: str,
        multi_file: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.accepted_type_text = accepted_type_text
        self.multi_file = multi_file

        self.setObjectName("fileDropCard")
        self.setAcceptDrops(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(6)

        self.title_label = QLabel()
        self.title_label.setObjectName("fileDropCardTitle")
        self.title_label.setWordWrap(True)

        self.meta_label = QLabel()
        self.meta_label.setObjectName("fileDropCardMeta")
        self.meta_label.setWordWrap(True)

        self.caption_label = QLabel()
        self.caption_label.setObjectName("mutedLabel")
        self.caption_label.setWordWrap(True)

        layout.addWidget(self.title_label)
        layout.addWidget(self.meta_label)
        layout.addWidget(self.caption_label)

    def set_empty_state(
        self,
        *,
        title: str,
        subtitle: str,
        caption: str | None = None,
    ) -> None:
        self.title_label.setText(title)
        self.meta_label.setText(subtitle)
        self.caption_label.setText(caption or self._default_caption())

    def set_loaded_state(
        self,
        *,
        title: str,
        subtitle: str,
        caption: str | None = None,
    ) -> None:
        self.title_label.setText(title)
        self.meta_label.setText(subtitle)
        self.caption_label.setText(caption or self._default_loaded_caption())

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.isEnabled():
            self.clicked.emit()
            event.accept()
            return
        super().mousePressEvent(event)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if self.isEnabled() and event.mimeData().hasUrls():
            self.setProperty("dropActive", True)
            self.style().unpolish(self)
            self.style().polish(self)
            event.acceptProposedAction()
            return
        super().dragEnterEvent(event)

    def dragLeaveEvent(self, event) -> None:  # type: ignore[override]
        self.setProperty("dropActive", False)
        self.style().unpolish(self)
        self.style().polish(self)
        super().dragLeaveEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:
        self.setProperty("dropActive", False)
        self.style().unpolish(self)
        self.style().polish(self)
        if not self.isEnabled():
            super().dropEvent(event)
            return
        urls = event.mimeData().urls()
        paths = [Path(url.toLocalFile()) for url in urls if url.isLocalFile()]
        if paths:
            self.paths_dropped.emit(paths)
            event.acceptProposedAction()
            return
        super().dropEvent(event)

    def _default_caption(self) -> str:
        selection_text = "Multiple files" if self.multi_file else "Single file"
        return f"Accepts: {self.accepted_type_text} | {selection_text}"

    def _default_loaded_caption(self) -> str:
        return self._default_caption()
