from __future__ import annotations

import array
import json
import math
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from shared.tool_base import ToolContext
from tools.audio_converter.models import (
    AudioEditState,
    AudioFileInfo,
    ExportPlan,
    MAX_PITCH,
    MAX_SPEED,
    MIN_PITCH,
    MIN_SPEED,
    MIN_TRIM_SPAN_SECONDS,
    SUPPORTED_INPUT_FORMATS,
    SUPPORTED_OUTPUT_FORMATS,
)


class AudioToolsError(ValueError):
    """Raised when audio workspace action cannot complete safely."""


class FFmpegNotFoundError(AudioToolsError):
    """Raised when FFmpeg cannot be found."""


@dataclass(frozen=True)
class FFmpegInstallation:
    ffmpeg_path: Path
    ffprobe_path: Path | None
    source: str


class FFmpegLocator:
    def __init__(self, context: ToolContext) -> None:
        self.context = context

    def find(self) -> FFmpegInstallation | None:
        for bundled_folder in self._bundled_folders():
            installation = self._from_folder(bundled_folder, "bundled")
            if installation is not None:
                return installation

        env_path = os.environ.get("TOOLS_FFMPEG_PATH")
        if env_path:
            installation = self._from_path(Path(env_path), "TOOLS_FFMPEG_PATH")
            if installation is not None:
                return installation

        path_match = shutil.which("ffmpeg")
        if path_match:
            ffmpeg_path = Path(path_match)
            return FFmpegInstallation(
                ffmpeg_path=ffmpeg_path,
                ffprobe_path=self._sibling_ffprobe(ffmpeg_path)
                or self._which_ffprobe(),
                source="PATH",
            )

        return None

    def _bundled_folders(self) -> list[Path]:
        assets_dir = self.context.assets_dir
        return [assets_dir / "ffmpeg" / "bin", assets_dir / "ffmpeg"]

    def _from_path(self, path: Path, source: str) -> FFmpegInstallation | None:
        if path.is_dir():
            return self._from_folder(path, source) or self._from_folder(path / "bin", source)

        if path.exists() and path.is_file():
            return FFmpegInstallation(
                ffmpeg_path=path,
                ffprobe_path=self._sibling_ffprobe(path),
                source=source,
            )

        return None

    def _from_folder(self, folder: Path, source: str) -> FFmpegInstallation | None:
        ffmpeg_path = folder / "ffmpeg.exe"
        if not ffmpeg_path.exists() or not ffmpeg_path.is_file():
            return None

        return FFmpegInstallation(
            ffmpeg_path=ffmpeg_path,
            ffprobe_path=self._sibling_ffprobe(ffmpeg_path),
            source=source,
        )

    @staticmethod
    def _sibling_ffprobe(ffmpeg_path: Path) -> Path | None:
        ffprobe_path = ffmpeg_path.parent / "ffprobe.exe"
        if ffprobe_path.exists() and ffprobe_path.is_file():
            return ffprobe_path
        return None

    @staticmethod
    def _which_ffprobe() -> Path | None:
        path_match = shutil.which("ffprobe")
        return Path(path_match) if path_match else None


class AudioToolsService:
    def __init__(self, context: ToolContext) -> None:
        self.context = context
        self.ffmpeg_locator = FFmpegLocator(context)

    def detect_ffmpeg(self) -> FFmpegInstallation | None:
        return self.ffmpeg_locator.find()

    def inspect_audio_file(
        self,
        input_file: Path,
        waveform_bars: int = 180,
    ) -> AudioFileInfo:
        self._validate_input_file(input_file)
        installation = self._require_ffmpeg()

        if installation.ffprobe_path is None:
            raise AudioToolsError(
                "FFprobe was not found next to FFmpeg. Reinstall Tools to restore bundled audio tools."
            )

        probe_payload = self._run_subprocess(
            [
                str(installation.ffprobe_path),
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "json",
                str(input_file),
            ],
            "FFprobe could not read this audio file.",
        )
        duration_seconds = self._parse_duration(probe_payload)
        if duration_seconds <= 0:
            raise AudioToolsError("Could not determine audio duration for this file.")

        waveform_points = self._build_waveform(
            installation.ffmpeg_path,
            input_file,
            waveform_bars,
        )

        return AudioFileInfo(
            path=input_file,
            duration_seconds=duration_seconds,
            waveform_points=waveform_points,
        )

    def build_export_plan(
        self,
        audio_file: AudioFileInfo,
        state: AudioEditState,
        output_file: Path,
    ) -> ExportPlan:
        self._validate_input_file(audio_file.path)
        self._validate_state(audio_file, state)
        installation = self._require_ffmpeg()

        output_format = output_file.suffix.lower().lstrip(".") or state.output_format
        if output_format not in SUPPORTED_OUTPUT_FORMATS:
            raise AudioToolsError(f"Unsupported output format: {output_format}")

        if output_file.exists():
            raise AudioToolsError(f"Output file already exists: {output_file}")

        if not output_file.parent.exists():
            raise AudioToolsError(f"Output folder does not exist: {output_file.parent}")

        filters = self._build_filters(audio_file.duration_seconds, state)
        arguments = self._build_ffmpeg_arguments(
            audio_file.path,
            output_file,
            output_format,
            filters,
            overwrite=False,
        )

        return ExportPlan(
            ffmpeg_path=installation.ffmpeg_path,
            arguments=arguments,
            output_file=output_file,
            applied_filters=tuple(filters),
        )

    def build_preview_plan(
        self,
        audio_file: AudioFileInfo,
        state: AudioEditState,
        output_file: Path,
    ) -> ExportPlan:
        self._validate_input_file(audio_file.path)
        self._validate_state(audio_file, state)
        installation = self._require_ffmpeg()

        if not output_file.parent.exists():
            raise AudioToolsError(f"Preview folder does not exist: {output_file.parent}")

        normalized_output = output_file.with_suffix(".wav")
        filters = self._build_filters(audio_file.duration_seconds, state)
        arguments = self._build_ffmpeg_arguments(
            audio_file.path,
            normalized_output,
            "wav",
            filters,
            overwrite=True,
        )

        return ExportPlan(
            ffmpeg_path=installation.ffmpeg_path,
            arguments=arguments,
            output_file=normalized_output,
            applied_filters=tuple(filters),
        )

    def suggested_output_path(self, audio_file: AudioFileInfo, state: AudioEditState) -> Path:
        return audio_file.path.with_name(state.export_file_name(audio_file.path))

    @staticmethod
    def normalize_output_path(output_file: Path, output_format: str) -> Path:
        normalized_format = output_format.lower().strip()
        if output_file.suffix.lower() != f".{normalized_format}":
            return output_file.with_suffix(f".{normalized_format}")
        return output_file

    def _require_ffmpeg(self) -> FFmpegInstallation:
        installation = self.detect_ffmpeg()
        if installation is None:
            raise FFmpegNotFoundError(
                "FFmpeg was not found. Reinstall Tools to restore bundled FFmpeg files, "
                "set TOOLS_FFMPEG_PATH, or add FFmpeg to PATH."
            )
        return installation

    @staticmethod
    def _validate_input_file(input_file: Path) -> None:
        if not input_file.exists() or not input_file.is_file():
            raise AudioToolsError("Choose audio file first.")

        extension = input_file.suffix.lower().lstrip(".")
        if extension not in SUPPORTED_INPUT_FORMATS:
            raise AudioToolsError(
                "Unsupported input format. Use mp3, wav, flac, m4a, aac, or ogg."
            )

    @staticmethod
    def _validate_state(audio_file: AudioFileInfo, state: AudioEditState) -> None:
        if state.output_format not in SUPPORTED_OUTPUT_FORMATS:
            raise AudioToolsError(f"Unsupported output format: {state.output_format}")

        if not (0.0 <= state.trim_start_seconds < state.trim_end_seconds <= audio_file.duration_seconds):
            raise AudioToolsError("Trim range is invalid.")

        if state.trim_end_seconds - state.trim_start_seconds < MIN_TRIM_SPAN_SECONDS:
            raise AudioToolsError("Trim range is too small.")

        if not (MIN_SPEED <= state.speed_multiplier <= MAX_SPEED):
            raise AudioToolsError("Speed must stay between 0.5x and 2.0x.")

        if not (MIN_PITCH <= state.pitch_semitones <= MAX_PITCH):
            raise AudioToolsError("Pitch must stay between -12 and +12 semitones.")

    def _build_waveform(
        self,
        ffmpeg_path: Path,
        input_file: Path,
        waveform_bars: int,
    ) -> tuple[float, ...]:
        process = subprocess.run(
            [
                str(ffmpeg_path),
                "-v",
                "error",
                "-i",
                str(input_file),
                "-map",
                "0:a:0",
                "-ac",
                "1",
                "-ar",
                "1200",
                "-f",
                "s16le",
                "-",
            ],
            capture_output=True,
            check=False,
        )

        if process.returncode != 0 or not process.stdout:
            raise AudioToolsError("FFmpeg could not generate waveform preview for this file.")

        samples = array.array("h")
        samples.frombytes(process.stdout)
        if sys.byteorder != "little":
            samples.byteswap()

        if not samples:
            return tuple(0.0 for _ in range(waveform_bars))

        chunk_size = max(1, math.ceil(len(samples) / waveform_bars))
        points: list[float] = []
        for index in range(0, len(samples), chunk_size):
            chunk = samples[index : index + chunk_size]
            peak = max(abs(sample) for sample in chunk)
            points.append(max(0.04, peak / 32768.0))

        if len(points) > waveform_bars:
            points = points[:waveform_bars]

        if len(points) < waveform_bars:
            points.extend([0.04] * (waveform_bars - len(points)))

        return tuple(points)

    @staticmethod
    def _parse_duration(probe_payload: str) -> float:
        try:
            data = json.loads(probe_payload)
        except json.JSONDecodeError as error:
            raise AudioToolsError("FFprobe returned invalid metadata.") from error

        format_data = data.get("format", {})
        duration = format_data.get("duration")
        try:
            return float(duration)
        except (TypeError, ValueError) as error:
            raise AudioToolsError("FFprobe did not report valid duration.") from error

    @staticmethod
    def _codec_arguments(output_format: str) -> list[str]:
        if output_format == "mp3":
            return ["-codec:a", "libmp3lame", "-q:a", "2"]

        if output_format == "wav":
            return ["-codec:a", "pcm_s16le"]

        if output_format == "flac":
            return ["-codec:a", "flac"]

        if output_format == "m4a":
            return ["-codec:a", "aac", "-b:a", "192k", "-movflags", "+faststart"]

        raise AudioToolsError(f"Unsupported output format: {output_format}")

    @classmethod
    def _build_ffmpeg_arguments(
        cls,
        input_file: Path,
        output_file: Path,
        output_format: str,
        filters: list[str],
        *,
        overwrite: bool,
    ) -> list[str]:
        arguments = [
            "-hide_banner",
            "-y" if overwrite else "-n",
            "-i",
            str(input_file),
        ]
        if filters:
            arguments.extend(["-filter:a", ",".join(filters)])
        arguments.extend(cls._codec_arguments(output_format))
        arguments.append(str(output_file))
        return arguments

    @staticmethod
    def _build_filters(duration_seconds: float, state: AudioEditState) -> list[str]:
        filters: list[str] = []
        if (
            state.trim_start_seconds > 0.0
            or state.trim_end_seconds < duration_seconds
        ):
            filters.append(
                f"atrim=start={state.trim_start_seconds:g}:end={state.trim_end_seconds:g}"
            )
            filters.append("asetpts=PTS-STARTPTS")

        if state.volume_percent != 100:
            filters.append(f"volume={state.volume_multiplier:g}")

        if state.pitch_semitones != 0:
            pitch_factor = math.pow(2.0, state.pitch_semitones / 12.0)
            filters.append(f"rubberband=pitch={pitch_factor:.6f}")

        if state.speed_percent != 100:
            filters.extend(AudioToolsService._atempo_filters(state.speed_multiplier))

        return filters

    @staticmethod
    def _atempo_filters(speed_multiplier: float) -> list[str]:
        remaining = speed_multiplier
        filters: list[str] = []

        while remaining < 0.5 or remaining > 2.0:
            if remaining < 0.5:
                filters.append("atempo=0.5")
                remaining /= 0.5
            else:
                filters.append("atempo=2.0")
                remaining /= 2.0

        filters.append(f"atempo={remaining:g}")
        return filters

    @staticmethod
    def _run_subprocess(command: list[str], failure_message: str) -> str:
        process = subprocess.run(command, capture_output=True, text=True, check=False)
        if process.returncode != 0:
            details = (process.stderr or process.stdout or "").strip()
            if details:
                raise AudioToolsError(f"{failure_message}\n\n{details[-1200:]}")
            raise AudioToolsError(failure_message)
        return process.stdout
