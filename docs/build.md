# Build

This project builds a Windows desktop app with PyInstaller and prepares a
Windows installer with Inno Setup.

## Requirements

- Windows
- Python 3.12
- Inno Setup 6 for installer creation: https://jrsoftware.org/isdl.php
- Bundled FFmpeg runtime files under `assets\ffmpeg`

Install Inno Setup with winget:

```powershell
winget install --id JRSoftware.InnoSetup -e -s winget -i
```

Inno Setup is only required for the installer step. If it is not installed,
the build script still creates the PyInstaller app bundle.

FFmpeg is vendored in the repository under `assets\ffmpeg`. The build script
fails if `bin\ffmpeg.exe`, `bin\ffprobe.exe`, `README.txt`, `LICENSE`, or
`THIRD_PARTY_NOTICES.md` is missing.

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
- Bundled FFmpeg in the app bundle:
  `dist\Tools\_internal\assets\ffmpeg\bin\ffmpeg.exe`
- Bundled FFprobe in the app bundle:
  `dist\Tools\_internal\assets\ffmpeg\bin\ffprobe.exe`

The version is read from `app/metadata.py`.

## How Tool Manifests Are Bundled

The PyInstaller spec file scans `tools/*/manifest.json`, includes those
manifests as bundled data, and adds tool modules as hidden imports. At runtime,
`app/core/paths.py` detects PyInstaller's bundled resource directory and points
tool discovery there.

This keeps local development and packaged builds using the same manifest-based
tool registry.

The PyInstaller spec includes the whole `assets` folder, which includes
`assets\ffmpeg`, and also includes `certifi` data so the packaged updater can
verify GitHub TLS certificates with an explicit CA bundle. Inno Setup installs
the full PyInstaller output recursively, so the installer includes the bundled
FFmpeg files automatically.

The bundled FFmpeg build is `8.1-essentials_build-www.gyan.dev`, licensed as
GPL v3. Keep `assets\ffmpeg\README.txt`, `assets\ffmpeg\LICENSE`, and
`assets\ffmpeg\THIRD_PARTY_NOTICES.md` with the binaries. Confirm license and
source-code information before replacing the binaries.

PyInstaller spec-file reference:
https://pyinstaller.org/en/stable/spec-files.html#adding-data-files
