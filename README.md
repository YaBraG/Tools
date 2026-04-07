# Tools

Tools is a Windows-only desktop launcher and workbench for small local
utilities. It is built as a clean Python + PySide6 application with a
manifest-driven plugin system so new tools can be added without changing the
main window.

This repository currently contains a distribution-ready MVP scaffold: a dark
desktop UI, sidebar navigation, searchable tool cards, a real Audio Converter
tool, one File Renamer placeholder, PyInstaller packaging, Inno Setup installer
preparation, and a simple GitHub Releases update checker.

## Stack

- Python 3.12
- PySide6 for the desktop UI
- PyInstaller for Windows app packaging
- Inno Setup for the Windows installer
- GitHub Releases for release downloads and update checks
- FFmpeg for the Audio Converter backend
- Manifest-based tool discovery under `tools/`

## Run Locally

From the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python app/main.py
```

## Build

Install Inno Setup 6 if you want the installer step:

```powershell
winget install --id JRSoftware.InnoSetup -e -s winget -i
```

Then build from the repository root:

```powershell
.\scripts\build.ps1
```

Outputs:

```text
dist\Tools\Tools.exe
dist\installer\Tools-Setup-v0.1.0.exe
```

If Inno Setup is not installed, the script still builds the PyInstaller app
bundle and prints a warning for the installer step.

To skip the installer intentionally:

```powershell
.\scripts\build.ps1 -SkipInstaller
```

See `docs/build.md` for details.

## Release Flow

Tools uses GitHub Releases for distribution:

```powershell
.\scripts\build.ps1
git tag v0.1.0
git push origin v0.1.0
```

Create a GitHub Release for the tag and upload:

```text
dist\installer\Tools-Setup-v0.1.0.exe
```

See `docs/release.md` for the full checklist.

## Updates

End users can open Settings and click **Check for updates**. The app checks:

```text
https://api.github.com/repos/YaBraG/Tools/releases/latest
```

If a newer version exists, the app shows the current version, latest version,
and a **Download update** button. The user downloads the installer, closes
Tools, and runs the installer to update. The app does not patch itself in
place and does not silently install updates.

See `docs/update-system.md` for implementation details.

## Audio Converter

Audio Converter can convert one input audio file to `mp3`, `wav`, or `flac`.
It uses FFmpeg and shows clear validation messages for missing input files,
missing output folders, missing FFmpeg, existing output files, and failed
conversions.

FFmpeg is detected in this order:

```text
TOOLS_FFMPEG_PATH
app folder\ffmpeg.exe
app folder\ffmpeg\ffmpeg.exe
app folder\ffmpeg\bin\ffmpeg.exe
assets\ffmpeg\ffmpeg.exe
assets\ffmpeg\bin\ffmpeg.exe
ffmpeg on PATH
```

See `docs/audio-converter.md` for testing and packaging notes.

## Project Structure

```text
app/        PySide6 application entry point, UI, update flow, and core registry logic
tools/      Manifest-backed tool plugins, including Audio Converter
shared/     Shared contracts for tools
docs/       Project documentation
assets/     Static assets placeholder for future icons, images, and optional FFmpeg files
packaging/  PyInstaller and Inno Setup packaging files
scripts/    Windows build scripts
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
