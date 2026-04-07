# Audio Converter

Audio Converter is the first real tool in the Tools workbench. It converts one
input audio file to `mp3`, `wav`, or `flac` using FFmpeg.

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

1. `TOOLS_FFMPEG_PATH`
2. `ffmpeg.exe` next to the app
3. `ffmpeg\ffmpeg.exe` next to the app
4. `ffmpeg\bin\ffmpeg.exe` next to the app
5. `assets\ffmpeg\ffmpeg.exe`
6. `assets\ffmpeg\bin\ffmpeg.exe`
7. `ffmpeg` on `PATH`

For local development, the app root is the repository root. In packaged builds,
the app root is the folder containing `Tools.exe`.

If FFmpeg is missing, the tool shows a clear message and does not crash.

## Test Locally

Install FFmpeg or point Tools to a local FFmpeg executable:

```powershell
$env:TOOLS_FFMPEG_PATH = "C:\path\to\ffmpeg.exe"
python app/main.py
```

Then open `Audio Converter`, choose an input file, choose an output folder,
choose a format, and click `Convert`.

To check PATH-based detection:

```powershell
ffmpeg -version
python app/main.py
```

## Future Expansion

The backend already models conversion options for speed, volume, trim, and
pitch. The MVP UI does not expose those controls yet.

