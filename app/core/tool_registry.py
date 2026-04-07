from __future__ import annotations

import importlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.core.paths import ASSETS_DIR, ROOT_DIR, TOOLS_DIR
from shared.tool_base import ToolContext

REQUIRED_MANIFEST_FIELDS = {"id", "name", "description", "entry_point"}


@dataclass(frozen=True)
class ToolManifest:
    id: str
    name: str
    description: str
    entry_point: str
    version: str = "0.1.0"
    category: str = "General"
    tags: tuple[str, ...] = ()
    manifest_path: Path | None = field(default=None, compare=False, repr=False)

    @classmethod
    def from_file(cls, manifest_path: Path) -> "ToolManifest":
        with manifest_path.open("r", encoding="utf-8") as file:
            data = json.load(file)

        missing_fields = REQUIRED_MANIFEST_FIELDS.difference(data)
        if missing_fields:
            missing = ", ".join(sorted(missing_fields))
            raise ValueError(f"Manifest is missing required field(s): {missing}")

        tags = data.get("tags", ())
        if isinstance(tags, str):
            tags = (tags,)

        return cls(
            id=str(data["id"]),
            name=str(data["name"]),
            description=str(data["description"]),
            entry_point=str(data["entry_point"]),
            version=str(data.get("version", "0.1.0")),
            category=str(data.get("category", "General")),
            tags=tuple(str(tag) for tag in tags),
            manifest_path=manifest_path,
        )

    @property
    def searchable_text(self) -> str:
        return " ".join(
            [self.name, self.description, self.category, *self.tags]
        ).lower()


class ToolRegistry:
    """Discovers tool manifests and loads tool classes on demand."""

    def __init__(
        self,
        tools_dir: Path = TOOLS_DIR,
        context: ToolContext | None = None,
    ) -> None:
        self.tools_dir = tools_dir
        self.context = context or ToolContext(
            app_name="Tools",
            root_dir=ROOT_DIR,
            assets_dir=ASSETS_DIR,
            tools_dir=tools_dir,
        )
        self.discovery_errors: list[str] = []

    def discover_tools(self) -> list[ToolManifest]:
        self.discovery_errors.clear()

        if not self.tools_dir.exists():
            return []

        manifests: list[ToolManifest] = []
        for manifest_path in sorted(self.tools_dir.glob("*/manifest.json")):
            try:
                manifests.append(ToolManifest.from_file(manifest_path))
            except (OSError, ValueError, json.JSONDecodeError) as error:
                self.discovery_errors.append(
                    f"{manifest_path.parent.name}: {error}"
                )

        return sorted(manifests, key=lambda manifest: manifest.name.lower())

    def create_tool(self, manifest: ToolManifest) -> Any:
        module_name, separator, class_name = manifest.entry_point.partition(":")
        if not separator or not module_name or not class_name:
            raise ValueError(
                f"Invalid entry_point for {manifest.name}: {manifest.entry_point}"
            )

        module = importlib.import_module(module_name)
        tool_class = getattr(module, class_name)
        return tool_class(self.context)

