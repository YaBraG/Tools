# Tools

Tools is a Windows-only desktop launcher and workbench for small local
utilities. It is built as a clean Python + PySide6 application with a
manifest-driven plugin system so new tools can be added without changing the
main window.

This repository currently contains the first MVP scaffold: a dark desktop UI,
sidebar navigation, searchable tool cards, and two placeholder tools.

## Stack

- Python 3.12
- PySide6 for the desktop UI
- PyInstaller for future Windows packaging
- Manifest-based tool discovery under `tools/`

## Run Locally

From the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python app/main.py
```

## Project Structure

```text
app/      PySide6 application entry point, UI, and core registry logic
tools/    Manifest-backed tool plugins
shared/   Shared contracts for tools
docs/     Project documentation
assets/   Static assets placeholder for future icons and images
```

## Adding a New Tool

Create a folder under `tools/` with this shape:

```text
tools/
  my_tool/
    __init__.py
    manifest.json
    tool.py
```

Add a manifest:

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

Then implement `MyTool` with a `create_widget()` method that returns a PySide6
`QWidget`. See `docs/adding-tools.md` for a complete example.

Restart the app and the new card will appear automatically.
