from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from shared.tool_base import ToolContext

SUPPORTED_OUTPUT_FORMATS = ("mp3", "wav", "flac")


class AudioConversionError(ValueError):
    """Raised when conversion cannot be prepared safely."""


class FFmpegNotFoundError(AudioConversionError):
    """Raised when FFmpeg cannot be found."""


@dataclass(frozen=True)
class ConversionOptions:
    input_file: Path
    output_folder: Path
    output_format: str
    speed: float | None = None
    volume: float | None = None
    trim_start_seconds: float | None = None
    trim_end_seconds: float | None = None
    pitch_shift_semitones: float | None = None


@dataclass(frozen=True)
class ConversionCommand:
    ffmpeg_path: Path
    arguments: list[str]
    output_file: Path


class FFmpegLocator:
    def __init__(self, context: ToolContext) -> None:
        self.context = context

    def find(self) -> Path | None:
        for candidate in self._candidate_paths():
            if candidate and candidate.exists() and candidate.is_file():
                return candidate

        path_match = shutil.which("ffmpeg")
        return Path(path_match) if path_match else None

    def _candidate_paths(self) -> list[Path | None]:
        env_path = os.environ.get("TOOLS_FFMPEG_PATH")
        app_root = self.context.root_dir
        assets_dir = self.context.assets_dir

        return [
            Path(env_path) if env_path else None,
            app_root / "ffmpeg.exe",
            app_root / "ffmpeg" / "ffmpeg.exe",
            app_root / "ffmpeg" / "bin" / "ffmpeg.exe",
            assets_dir / "ffmpeg" / "ffmpeg.exe",
            assets_dir / "ffmpeg" / "bin" / "ffmpeg.exe",
        ]


class AudioConversionService:
    def __init__(self, context: ToolContext) -> None:
        self.context = context
        self.ffmpeg_locator = FFmpegLocator(context)

    def detect_ffmpeg(self) -> Path | None:
        return self.ffmpeg_locator.find()

    def build_command(self, options: ConversionOptions) -> ConversionCommand:
        output_format = options.output_format.lower().strip()
        if output_format not in SUPPORTED_OUTPUT_FORMATS:
            raise AudioConversionError(f"Unsupported output format: {output_format}")

        input_file = options.input_file
        output_folder = options.output_folder
        output_file = self.get_output_file(input_file, output_folder, output_format)

        if not input_file.exists() or not input_file.is_file():
            raise AudioConversionError("Choose an input audio file first.")

        if not output_folder.exists() or not output_folder.is_dir():
            raise AudioConversionError("Choose an output folder first.")

        if output_file.exists():
            raise AudioConversionError(f"Output file already exists: {output_file}")

        ffmpeg_path = self.detect_ffmpeg()
        if ffmpeg_path is None:
            raise FFmpegNotFoundError(
                "FFmpeg was not found. Install FFmpeg and add it to PATH, set "
                "TOOLS_FFMPEG_PATH, or place ffmpeg.exe next to Tools.exe."
            )

        arguments = [
            "-hide_banner",
            "-n",
            "-i",
            str(input_file),
            *self._codec_arguments(output_format),
            *self._filter_arguments(options),
            str(output_file),
        ]

        return ConversionCommand(
            ffmpeg_path=ffmpeg_path,
            arguments=arguments,
            output_file=output_file,
        )

    @staticmethod
    def get_output_file(
        input_file: Path,
        output_folder: Path,
        output_format: str,
    ) -> Path:
        return output_folder / f"{input_file.stem}.{output_format.lower()}"

    @staticmethod
    def _codec_arguments(output_format: str) -> list[str]:
        if output_format == "mp3":
            return ["-codec:a", "libmp3lame", "-q:a", "2"]

        if output_format == "wav":
            return ["-codec:a", "pcm_s16le"]

        if output_format == "flac":
            return ["-codec:a", "flac"]

        raise AudioConversionError(f"Unsupported output format: {output_format}")

    @staticmethod
    def _filter_arguments(options: ConversionOptions) -> list[str]:
        filters: list[str] = []

        if options.speed is not None:
            filters.append(f"atempo={options.speed:g}")

        if options.volume is not None:
            filters.append(f"volume={options.volume:g}")

        # Trim and pitch are intentionally modeled now, but not surfaced in the MVP UI.
        if options.trim_start_seconds is not None:
            filters.append(f"atrim=start={options.trim_start_seconds:g}")

        if options.trim_end_seconds is not None:
            filters.append(f"atrim=end={options.trim_end_seconds:g}")

        if options.pitch_shift_semitones is not None:
            raise AudioConversionError("Pitch shifting is not enabled in this MVP yet.")

        return ["-filter:a", ",".join(filters)] if filters else []
