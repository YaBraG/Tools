# Tools

Tools is a Windows-only desktop launcher and workbench for small local
utilities. It is built with Python and PySide6, uses a manifest-driven plugin
system, and is prepared for real end-user distribution with PyInstaller,
Inno Setup, and GitHub Releases.

Today the repo includes:

- Audio Tools: a real offline audio editing workspace powered by bundled FFmpeg
- File Renamer: placeholder tool scaffold

## Stack

- Python 3.12
- PySide6
- PyInstaller
- Inno Setup
- GitHub Releases
- Bundled FFmpeg
- certifi for updater CA certificates

## Run Locally

From the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python app/main.py
```

`python app/main.py` is the supported local entry point.

## Audio Tools

Audio Tools is the main real plugin in the current MVP. It opens one audio file
into a unified workspace instead of separate mini-tools.

Features in the first pass:

- Open one local audio file
- Record audio from the local microphone into `wav`, `mp3`, `flac`, or `m4a`
- Drag and drop onto the waveform area
- Keep trim controls available while switching between `Volume`, `Speed`, and `Pitch`
- Switch editor modes with top tabs:
  - Volume
  - Speed
  - Pitch
- Preview a waveform-style timeline
- Preview the current edited result from the same workspace
- Reset edits without touching the original file
- Export to `mp3`, `wav`, `flac`, or `m4a`
- Optionally load the exported file back into Audio Tools after save

Supported input formats:

- `mp3`
- `wav`
- `flac`
- `m4a`
- `aac`
- `ogg`

Supported export formats:

- `mp3`
- `wav`
- `flac`
- `m4a`

FFmpeg detection order:

1. Bundled FFmpeg in `assets\ffmpeg\bin`
2. Bundled FFmpeg in `assets\ffmpeg`
3. `TOOLS_FFMPEG_PATH`
4. `ffmpeg` on system `PATH`

In packaged builds, PyInstaller places bundled assets under
`dist\Tools\_internal\assets\ffmpeg`, and the app resolves that automatically.

See `docs/audio-tools.md` for behavior, testing, and FFmpeg notes.

## Build

Install Inno Setup 6 if you want the installer step:

```powershell
winget install --id JRSoftware.InnoSetup -e -s winget -i
```

Then build from the repository root:

```powershell
.\scripts\build.ps1
```

Current output examples for version `0.3.0`:

```text
dist\Tools\Tools.exe
dist\installer\Tools-Setup-v0.3.0.exe
```

To skip the installer and only build the PyInstaller app bundle:

```powershell
.\scripts\build.ps1 -SkipInstaller
```

See `docs/build.md`.

## Installer And Release Flow

1. Build the app and installer.
2. Tag the release version.
3. Push the tag.
4. Create a GitHub Release.
5. Upload the installer `.exe`.

Example for the current version:

```powershell
.\scripts\build.ps1
git tag v0.3.0
git push origin v0.3.0
```

Installer asset:

```text
dist\installer\Tools-Setup-v0.3.0.exe
```

See `docs/release.md`.

## Updates

End users can open `Settings` and click `Check for updates`.

The app:

1. Calls the GitHub latest-release API for `YaBraG/Tools`
2. Uses an explicit SSL context created from `certifi.where()`
3. Compares the latest release tag to `APP_VERSION`
4. Shows current version, latest version, and a download action if an update exists
5. Opens the new installer download or release page

The app does not patch itself in place and does not silently install updates.

See `docs/update-system.md`.

## Project Structure

```text
app/        Application entry point, UI, updater, and core registry logic
tools/      Manifest-backed tool plugins, including Audio Tools
shared/     Shared tool contracts
docs/       Build, release, update, and tool documentation
assets/     Static assets and bundled FFmpeg runtime files
packaging/  PyInstaller and Inno Setup files
scripts/    Windows build scripts
```

## Adding A New Tool

Create a folder under `tools/`:

```text
tools/
  my_tool/
    __init__.py
    manifest.json
    tool.py
```

Manifest example:

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

Then implement `MyTool.create_widget()` and return a PySide6 `QWidget`.

See `docs/adding-tools.md` for the full pattern.
