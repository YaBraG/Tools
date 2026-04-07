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
class FFmpegInstallation:
    ffmpeg_path: Path
    ffprobe_path: Path | None
    source: str


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

        return [
            assets_dir / "ffmpeg" / "bin",
            assets_dir / "ffmpeg",
        ]

    def _from_path(self, path: Path, source: str) -> FFmpegInstallation | None:
        if path.is_dir():
            return self._from_folder(path, source) or self._from_folder(
                path / "bin",
                source,
            )

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


class AudioConversionService:
    def __init__(self, context: ToolContext) -> None:
        self.context = context
        self.ffmpeg_locator = FFmpegLocator(context)

    def detect_ffmpeg(self) -> FFmpegInstallation | None:
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

        ffmpeg_installation = self.detect_ffmpeg()
        if ffmpeg_installation is None:
            raise FFmpegNotFoundError(
                "FFmpeg was not found. Reinstall Tools to restore the bundled "
                "FFmpeg files, set TOOLS_FFMPEG_PATH, or add FFmpeg to PATH."
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
            ffmpeg_path=ffmpeg_installation.ffmpeg_path,
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
