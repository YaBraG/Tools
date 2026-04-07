from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget


@dataclass(frozen=True)
class ToolContext:
    app_name: str
    root_dir: Path
    assets_dir: Path
    tools_dir: Path


class ToolPlugin(Protocol):
    def create_widget(self, parent: QWidget | None = None) -> QWidget:
        """Return the root widget for this tool."""

