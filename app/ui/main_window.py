from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app import __version__
from app.core.tool_registry import ToolManifest, ToolRegistry
from app.ui.pages import AboutPage, HomePage, SettingsPage, ToolsPage
from app.ui.tool_dialog import ToolDialog


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()

        self.registry = ToolRegistry()
        self.tools = self.registry.discover_tools()
        self.nav_buttons: dict[str, QPushButton] = {}
        self.pages: dict[str, QWidget] = {}
        self.open_tool_windows: dict[str, ToolDialog] = {}

        self.setWindowTitle("Tools")
        self.resize(1180, 740)
        self.setMinimumSize(960, 620)

        self._build_ui()
        self._show_page("home")

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("appRoot")
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        root_layout.addWidget(self._build_sidebar())

        content = QFrame()
        content.setObjectName("contentFrame")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(28, 26, 28, 26)
        content_layout.setSpacing(18)

        self.stack = QStackedWidget()
        content_layout.addWidget(self.stack)
        root_layout.addWidget(content, 1)

        self._add_page("home", HomePage(self.tools))
        self._add_page("tools", ToolsPage(self.tools))
        self._add_page("settings", SettingsPage())
        self._add_page("about", AboutPage(self.tools, self.registry.discovery_errors))

        self.setCentralWidget(root)

    def _build_sidebar(self) -> QFrame:
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(220)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(20, 24, 20, 22)
        layout.setSpacing(12)

        title = QLabel("Tools")
        title.setObjectName("sidebarTitle")
        subtitle = QLabel("Desktop workbench")
        subtitle.setObjectName("sidebarSubtitle")
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addSpacing(24)

        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        for key, label in (
            ("home", "Home"),
            ("tools", "Tools"),
            ("settings", "Settings"),
            ("about", "About"),
        ):
            button = QPushButton(label)
            button.setObjectName("navButton")
            button.setCheckable(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(
                lambda checked=False, page=key: self._show_page(page)
            )
            self.nav_group.addButton(button)
            self.nav_buttons[key] = button
            layout.addWidget(button)

        layout.addStretch(1)

        version = QLabel(f"Version {__version__}")
        version.setObjectName("sidebarVersion")
        layout.addWidget(version)

        return sidebar

    def _add_page(self, key: str, page: QWidget) -> None:
        if hasattr(page, "tool_requested"):
            page.tool_requested.connect(self._open_tool)

        self.pages[key] = page
        self.stack.addWidget(page)

    def _show_page(self, key: str) -> None:
        page = self.pages.get(key)
        if page is None:
            return

        self.stack.setCurrentWidget(page)
        for page_key, button in self.nav_buttons.items():
            button.setChecked(page_key == key)

    def _open_tool(self, manifest: ToolManifest) -> None:
        existing_window = self.open_tool_windows.get(manifest.id)
        if existing_window is not None:
            self._focus_tool_window(existing_window)
            return

        try:
            tool = self.registry.create_tool(manifest)
            dialog = ToolDialog(manifest, tool, self)
            dialog.finished.connect(
                lambda _result, tool_id=manifest.id, window=dialog: self._on_tool_closed(
                    tool_id,
                    window,
                )
            )
            self.open_tool_windows[manifest.id] = dialog
            dialog.show()
            self._focus_tool_window(dialog)
        except Exception as error:
            QMessageBox.critical(
                self,
                "Unable to open tool",
                f"Tools could not open {manifest.name}.\n\n{error}",
            )

    def _focus_tool_window(self, window: ToolDialog) -> None:
        if window.isMinimized():
            window.showNormal()
        else:
            window.show()
        window.raise_()
        window.activateWindow()

    def _on_tool_closed(self, tool_id: str, window: ToolDialog) -> None:
        current_window = self.open_tool_windows.get(tool_id)
        if current_window is window:
            self.open_tool_windows.pop(tool_id, None)
