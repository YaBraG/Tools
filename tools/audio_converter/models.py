from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

SUPPORTED_INPUT_FORMATS = ("mp3", "wav", "flac", "m4a", "aac", "ogg")
SUPPORTED_OUTPUT_FORMATS = ("mp3", "wav", "flac", "m4a")
EDITOR_MODES = ("volume", "speed", "pitch")
DEFAULT_EDITOR_MODE = "volume"
MIN_SPEED = 0.5
MAX_SPEED = 2.0
MIN_PITCH = -12
MAX_PITCH = 12
PITCH_PRECISION_DIGITS = 2
PITCH_STEP_SEMITONES = 0.01
PITCH_SLIDER_SCALE = 100
PITCH_EPSILON = PITCH_STEP_SEMITONES / 2.0
MIN_TRIM_SPAN_SECONDS = 0.05
TRIM_PRECISION_DIGITS = 2
TRIM_PRECISION_SECONDS = 0.01
TRIM_EPSILON_SECONDS = TRIM_PRECISION_SECONDS / 2.0


@dataclass(frozen=True)
class AudioFileInfo:
    path: Path
    duration_seconds: float
    waveform_points: tuple[float, ...]

    @property
    def display_name(self) -> str:
        return self.path.name

    @property
    def editor_duration_seconds(self) -> float:
        return round(self.duration_seconds, TRIM_PRECISION_DIGITS)


@dataclass
class AudioEditState:
    trim_start_seconds: float = 0.0
    trim_end_seconds: float = 0.0
    volume_percent: int = 100
    speed_percent: int = 100
    pitch_semitones: float = 0.0
    output_format: str = "mp3"
    last_export_path: Path | None = None
    active_mode: str = DEFAULT_EDITOR_MODE

    def reset(self, duration_seconds: float) -> None:
        self.trim_start_seconds = 0.0
        self.trim_end_seconds = duration_seconds
        self.volume_percent = 100
        self.speed_percent = 100
        self.pitch_semitones = 0.0
        self.last_export_path = None
        if self.output_format not in SUPPORTED_OUTPUT_FORMATS:
            self.output_format = "mp3"
        if self.active_mode not in EDITOR_MODES:
            self.active_mode = DEFAULT_EDITOR_MODE

    @property
    def speed_multiplier(self) -> float:
        return self.speed_percent / 100.0

    @property
    def volume_multiplier(self) -> float:
        return self.volume_percent / 100.0

    def export_file_name(self, input_path: Path) -> str:
        return f"{input_path.stem}-edited.{self.output_format}"

    def changed_mode_summary(self) -> tuple[str, ...]:
        summary: list[str] = []
        if self.trim_start_seconds > 0.0:
            summary.append("trim start")
        if self.trim_end_seconds > self.trim_start_seconds:
            summary.append("trim end")
        if self.volume_percent != 100:
            summary.append("volume")
        if self.speed_percent != 100:
            summary.append("speed")
        if abs(self.pitch_semitones) >= PITCH_EPSILON:
            summary.append("pitch")
        return tuple(summary)


@dataclass(frozen=True)
class ExportPlan:
    ffmpeg_path: Path
    arguments: list[str]
    output_file: Path
    applied_filters: tuple[str, ...] = field(default_factory=tuple)
