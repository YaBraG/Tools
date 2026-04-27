from __future__ import annotations

from pathlib import Path

from tools.audio_converter.backend import AudioToolsService
from tools.audio_converter.models import AudioEditState, AudioFileInfo


def _make_audio_file(path: Path) -> AudioFileInfo:
    return AudioFileInfo(
        path=path,
        duration_seconds=8.0,
        waveform_points=(0.1, 0.2, 0.3),
    )


def test_audio_edit_state_accepts_fractional_pitch() -> None:
    state = AudioEditState(pitch_semitones=0.25)

    assert state.pitch_semitones == 0.25


def test_audio_filters_use_fractional_pitch() -> None:
    audio_file = _make_audio_file(Path("example.wav"))
    state = AudioEditState(
        trim_start_seconds=0.0,
        trim_end_seconds=audio_file.editor_duration_seconds,
        pitch_semitones=0.25,
    )

    filters = AudioToolsService._build_filters(audio_file, state)

    assert filters == ["rubberband=pitch=1.014545"]

