from __future__ import annotations

from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from shared.tool_base import ToolContext


class FileRenamerTool:
    def __init__(self, context: ToolContext) -> None:
        self.context = context

    def create_widget(self, parent: QWidget | None = None) -> QWidget:
        return FileRenamerPlaceholderWidget(parent)


class FileRenamerPlaceholderWidget(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.preview_count = 0
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        intro_panel = QFrame()
        intro_panel.setObjectName("workspacePanel")
        intro_layout = QVBoxLayout(intro_panel)
        intro_layout.setContentsMargins(18, 18, 18, 18)
        intro_layout.setSpacing(10)

        title = QLabel("File Renamer Test Window")
        title.setObjectName("panelTitle")

        body = QLabel(
            "This is a live placeholder window for validating multi-tool window "
            "behavior. It does not rename files yet, but it behaves like a real "
            "tool window inside Tools."
        )
        body.setObjectName("panelBody")
        body.setWordWrap(True)

        intro_layout.addWidget(title)
        intro_layout.addWidget(body)

        details_panel = QFrame()
        details_panel.setObjectName("workspacePanel")
        details_layout = QVBoxLayout(details_panel)
        details_layout.setContentsMargins(18, 18, 18, 18)
        details_layout.setSpacing(12)

        source_label = QLabel("Source folder: demo-project-assets")
        source_label.setObjectName("panelBody")

        rule_label = QLabel("Rename pattern: image_{num:03}")
        rule_label.setObjectName("panelBody")

        note_label = QLabel("Safety note: dummy mode only, no file operations are performed.")
        note_label.setObjectName("mutedLabel")
        note_label.setWordWrap(True)

        status_row = QHBoxLayout()
        status_row.setSpacing(12)

        self.status_label = QLabel("Window alive. Dummy preview has not been run yet.")
        self.status_label.setObjectName("panelBody")
        self.status_label.setWordWrap(True)

        self.counter_label = QLabel("0 previews")
        self.counter_label.setObjectName("valueBadge")

        status_row.addWidget(self.status_label, 1)
        status_row.addWidget(self.counter_label)

        button_row = QHBoxLayout()
        button_row.setSpacing(10)

        preview_button = QPushButton("Run Dummy Preview")
        preview_button.setObjectName("primaryButton")
        preview_button.clicked.connect(self._run_dummy_preview)

        reset_button = QPushButton("Reset Dummy State")
        reset_button.setObjectName("secondaryButton")
        reset_button.clicked.connect(self._reset_dummy_state)

        button_row.addWidget(preview_button)
        button_row.addWidget(reset_button)
        button_row.addStretch(1)

        details_layout.addWidget(source_label)
        details_layout.addWidget(rule_label)
        details_layout.addLayout(status_row)
        details_layout.addWidget(note_label)
        details_layout.addLayout(button_row)

        layout.addWidget(intro_panel)
        layout.addWidget(details_panel)
        layout.addStretch(1)

    def _run_dummy_preview(self) -> None:
        self.preview_count += 1
        self.counter_label.setText(f"{self.preview_count} preview{'s' if self.preview_count != 1 else ''}")
        self.status_label.setText(
            f"Dummy preview ran successfully. This window is still active after {self.preview_count} interaction"
            f"{'s' if self.preview_count != 1 else ''}."
        )

    def _reset_dummy_state(self) -> None:
        self.preview_count = 0
        self.counter_label.setText("0 previews")
        self.status_label.setText("Window alive. Dummy preview has not been run yet.")
