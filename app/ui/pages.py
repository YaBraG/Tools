from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget

from app.core.tool_registry import ToolManifest
from app.ui.widgets.tool_catalog import ToolCatalogWidget


class HomePage(QWidget):
    tool_requested = Signal(object)

    def __init__(self, tools: list[ToolManifest]) -> None:
        super().__init__()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(18)

        hero = QFrame()
        hero.setObjectName("heroPanel")
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(26, 24, 26, 24)
        hero_layout.setSpacing(10)

        title = QLabel("A focused launcher for your desktop utilities.")
        title.setObjectName("heroTitle")
        title.setWordWrap(True)

        description = QLabel(
            "Search, launch, and grow a collection of local Windows tools from "
            "one clean Python and PySide6 workbench."
        )
        description.setObjectName("heroDescription")
        description.setWordWrap(True)

        stats = QLabel(
            f"{len(tools)} tools detected | Manifest-based plugins | Windows desktop"
        )
        stats.setObjectName("heroMeta")

        hero_layout.addWidget(title)
        hero_layout.addWidget(description)
        hero_layout.addWidget(stats)
        layout.addWidget(hero)

        catalog = ToolCatalogWidget(
            tools,
            title="Launch a Tool",
            subtitle="Filter the available tools and open a placeholder workbench.",
        )
        catalog.tool_requested.connect(self.tool_requested.emit)
        layout.addWidget(catalog, 1)


class ToolsPage(QWidget):
    tool_requested = Signal(object)

    def __init__(self, tools: list[ToolManifest]) -> None:
        super().__init__()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(18)

        catalog = ToolCatalogWidget(
            tools,
            title="Tool Catalog",
            subtitle="Each card is discovered from a tool manifest under the tools folder.",
        )
        catalog.tool_requested.connect(self.tool_requested.emit)
        layout.addWidget(catalog, 1)


class SettingsPage(QWidget):
    def __init__(self) -> None:
        super().__init__()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        panel = _InfoPanel(
            "Settings",
            "This first scaffold keeps settings intentionally light. Future "
            "versions can add app preferences, default paths, and packaging "
            "configuration here without changing the tool plugin system.",
        )
        layout.addWidget(panel)
        layout.addStretch(1)


class AboutPage(QWidget):
    def __init__(
        self,
        tools: list[ToolManifest],
        discovery_errors: list[str],
    ) -> None:
        super().__init__()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(18)

        summary = (
            "Tools is a Windows-only desktop launcher and utility workbench "
            "built with Python 3.12, PySide6, and a simple manifest-driven "
            "tool system."
        )
        layout.addWidget(_InfoPanel("About Tools", summary))

        health = f"{len(tools)} tool manifests loaded."
        if discovery_errors:
            health += " Some manifests could not be loaded: " + "; ".join(
                discovery_errors
            )

        layout.addWidget(_InfoPanel("Registry Status", health))
        layout.addStretch(1)


class _InfoPanel(QFrame):
    def __init__(self, title: str, body: str) -> None:
        super().__init__()
        self.setObjectName("infoPanel")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(10)

        title_label = QLabel(title)
        title_label.setObjectName("panelTitle")

        body_label = QLabel(body)
        body_label.setObjectName("panelBody")
        body_label.setWordWrap(True)

        layout.addWidget(title_label)
        layout.addWidget(body_label)

