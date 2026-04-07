# Audio Converter

Audio Converter is the first real tool in the Tools workbench. It converts one
input audio file to `mp3`, `wav`, or `flac` using the bundled FFmpeg runtime.

## What It Does

- Select one input audio file.
- Select an output folder.
- Choose `mp3`, `wav`, or `flac`.
- Preview the output filename.
- Start conversion.
- Show status, success, and error messages.

The output filename uses the input file stem plus the selected format. For
example:

```text
song.wav -> song.mp3
```

If that output file already exists, the converter stops and asks the user to
choose a different folder or format. It does not overwrite files.

## FFmpeg Detection

The tool checks for FFmpeg in this order:

1. Bundled FFmpeg under `assets\ffmpeg\bin`
2. Bundled FFmpeg under `assets\ffmpeg`
3. `TOOLS_FFMPEG_PATH`, pointing to `ffmpeg.exe` or a folder containing it
4. `ffmpeg` on system `PATH`

For local development, bundled FFmpeg lives at `assets\ffmpeg\bin`. In
packaged builds, PyInstaller places it under `_internal\assets\ffmpeg\bin`,
and the app resolves that path automatically.

If FFmpeg is missing, the tool shows a clear message and does not crash.

The status text identifies the active source as bundled FFmpeg,
`TOOLS_FFMPEG_PATH`, or system `PATH`.

## Bundled Files

The bundled runtime files live here:

```text
assets/
  ffmpeg/
    LICENSE
    README.txt
    THIRD_PARTY_NOTICES.md
    bin/
      ffmpeg.exe
      ffprobe.exe
```

The included build is `8.1-essentials_build-www.gyan.dev`, licensed as GPL v3.
The upstream FFmpeg project and Windows build source links are documented in
`assets\ffmpeg\THIRD_PARTY_NOTICES.md`.

## Test Locally

The normal local run uses the bundled FFmpeg automatically:

```powershell
python app/main.py
```

To override the bundled copy for debugging:

```powershell
$env:TOOLS_FFMPEG_PATH = "C:\path\to\ffmpeg.exe"
python app/main.py
```

Then open `Audio Converter`, choose an input file, choose an output folder,
choose a format, and click `Convert`.

To check PATH-based fallback detection, temporarily move or rename
`assets\ffmpeg\bin\ffmpeg.exe`, then run:

```powershell
ffmpeg -version
python app/main.py
```

## Future Expansion

The backend already models conversion options for speed, volume, trim, and
pitch. The MVP UI does not expose those controls yet.
