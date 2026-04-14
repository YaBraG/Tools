# Audio Tools

Audio Tools is the current real editing workspace inside the Tools desktop app.
It replaces the old one-shot Audio Converter flow with one unified editor.

## Workspace Flow

1. Open `Audio Tools`
2. Choose one input file or drop it on the waveform area
3. Switch modes from the top tab row
4. Adjust settings without changing the source file
5. Click `Preview` to hear the current edited result
6. Click `Save Export`
7. Choose the output file location and export format

The original input file is never modified in place.

## Modes

### Trim

- Numeric start and end inputs
- Draggable waveform range handles
- Validation for invalid or too-small trim ranges

FFmpeg filters:

```text
atrim=start=...:end=...,asetpts=PTS-STARTPTS
```

### Volume

- Horizontal slider
- Visible percentage value

FFmpeg filter:

```text
volume=...
```

### Speed

- Horizontal slider
- Visible multiplier from `0.50x` to `2.00x`

FFmpeg filter:

```text
atempo=...
```

If a multiplier ever needed multiple `atempo` stages, the backend already
supports chaining them.

### Pitch

- Horizontal slider
- Visible semitone shift from `-12` to `+12`

FFmpeg filter:

```text
rubberband=pitch=...
```

The bundled FFmpeg build includes `librubberband`, so pitch export works
without a separate install.

## Supported Formats

Input:

- `mp3`
- `wav`
- `flac`
- `m4a`
- `aac`
- `ogg`

Export:

- `mp3`
- `wav`
- `flac`
- `m4a`

## FFmpeg Detection

The backend checks in this order:

1. `assets\ffmpeg\bin`
2. `assets\ffmpeg`
3. `TOOLS_FFMPEG_PATH`
4. system `PATH`

Bundled FFmpeg is the default path for normal users.

If FFmpeg or FFprobe is missing, Audio Tools shows a clear status error instead
of crashing.

The normal workspace no longer shows FFmpeg path/runtime details. Those details
only appear in error messaging when FFmpeg actually fails.

## Bundled Runtime Files

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

In packaged builds these files end up under:

```text
dist\Tools\_internal\assets\ffmpeg\
```

## How To Test

Run the app:

```powershell
python app/main.py
```

Then test these paths:

### Trim

1. Open a supported audio file
2. Drag the trim handles or edit start/end values
3. Use `Preview` and confirm playback starts at the selected trim range
4. Export to a new file
5. Confirm the output duration matches the selected range

### Volume

1. Load a file
2. Switch to `Volume`
3. Move the slider away from `100%`
4. Use `Preview` and confirm the edited result plays
5. Export
6. Confirm the output loudness changes

### Speed

1. Load a file
2. Switch to `Speed`
3. Set `0.50x` or `1.50x`
4. Use `Preview` and confirm the edited result plays at the changed speed
5. Export
6. Confirm playback duration changes as expected

### Pitch

1. Load a file
2. Switch to `Pitch`
3. Set `+4 st` or `-4 st`
4. Use `Preview` and confirm the edited result plays with the pitch shift
5. Export
6. Confirm pitch shifts while the export still succeeds through bundled FFmpeg

## First-Pass Limits

- Preview playback is generated from a temporary processed file, not true
  sample-by-sample live DSP
- The waveform is a simplified generated preview, not a sample-accurate editor
- Save/export applies the current UI state once; there is no history stack yet
- No recording, batch mode, equalizer, reverse, or multi-file workflow yet
