# Adding Tools

Tools discovers utilities from folders under `tools/`. Each tool owns its
manifest and Python entry point, which keeps the launcher small and easy to
extend.

## Folder Layout

```text
tools/
  my_tool/
    __init__.py
    manifest.json
    tool.py
```

## Manifest

Create a `manifest.json` file with the required fields:

```json
{
  "id": "my_tool",
  "name": "My Tool",
  "description": "Describe what this utility does.",
  "entry_point": "tools.my_tool.tool:MyTool",
  "version": "0.1.0",
  "category": "General",
  "tags": ["example"]
}
```

## Tool Class

The entry point must expose a class that accepts `ToolContext` and returns a
`QWidget` from `create_widget`.

```python
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from shared.tool_base import ToolContext


class MyTool:
    def __init__(self, context: ToolContext) -> None:
        self.context = context

    def create_widget(self, parent: QWidget | None = None) -> QWidget:
        widget = QWidget(parent)
        layout = QVBoxLayout(widget)
        layout.addWidget(QLabel("My Tool"))
        return widget
```

Restart the app and the new tool card will appear automatically.

