# Build

This project builds a Windows desktop app with PyInstaller and prepares a
Windows installer with Inno Setup.

## Requirements

- Windows
- Python 3.12
- Inno Setup 6 for installer creation: https://jrsoftware.org/isdl.php
- FFmpeg for Audio Converter runtime conversion

Install Inno Setup with winget:

```powershell
winget install --id JRSoftware.InnoSetup -e -s winget -i
```

Inno Setup is only required for the installer step. If it is not installed,
the build script still creates the PyInstaller app bundle.

FFmpeg is not vendored in the repository. The Audio Converter can use FFmpeg
from `TOOLS_FFMPEG_PATH`, from the installed app folder, from `assets\ffmpeg`,
or from `PATH`.

## Build Commands

From the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
.\scripts\build.ps1
```

To build only the PyInstaller app bundle:

```powershell
.\scripts\build.ps1 -SkipInstaller
```

## Outputs

- PyInstaller app bundle: `dist\Tools\Tools.exe`
- Inno Setup installer: `dist\installer\Tools-Setup-v0.1.0.exe`

The version is read from `app/metadata.py`.

## How Tool Manifests Are Bundled

The PyInstaller spec file scans `tools/*/manifest.json`, includes those
manifests as bundled data, and adds tool modules as hidden imports. At runtime,
`app/core/paths.py` detects PyInstaller's bundled resource directory and points
tool discovery there.

This keeps local development and packaged builds using the same manifest-based
tool registry.

If you want to bundle FFmpeg with a release, place the redistributable FFmpeg
executable at `assets\ffmpeg\ffmpeg.exe` or `assets\ffmpeg\bin\ffmpeg.exe`
before building. Confirm the FFmpeg license and distribution terms before
publishing.

PyInstaller spec-file reference:
https://pyinstaller.org/en/stable/spec-files.html#adding-data-files
