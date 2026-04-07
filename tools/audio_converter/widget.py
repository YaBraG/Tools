from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QProcess, Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from shared.tool_base import ToolContext
from tools.audio_converter.backend import (
    SUPPORTED_OUTPUT_FORMATS,
    AudioConversionError,
    AudioConversionService,
    ConversionOptions,
    FFmpegNotFoundError,
)


class AudioDropZone(QFrame):
    file_dropped = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("audioDropZone")
        self.setAcceptDrops(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(6)

        title = QLabel("Drop an audio file here")
        title.setObjectName("dropZoneTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.subtitle = QLabel("or use Choose file")
        self.subtitle.setObjectName("dropZoneSubtitle")
        self.subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.subtitle.setWordWrap(True)

        layout.addWidget(title)
        layout.addWidget(self.subtitle)

    def set_selected_file(self, path: Path | None) -> None:
        if path is None:
            self.subtitle.setText("or use Choose file")
            return

        self.subtitle.setText(path.name)

    def dragEnterEvent(self, event) -> None:  # noqa: N802
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            return

        event.ignore()

    def dropEvent(self, event) -> None:  # noqa: N802
        for url in event.mimeData().urls():
            if url.isLocalFile():
                self.file_dropped.emit(Path(url.toLocalFile()))
                event.acceptProposedAction()
                return

        event.ignore()


class AudioConverterWidget(QWidget):
    def __init__(self, context: ToolContext, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.service = AudioConversionService(context)
        self.input_file: Path | None = None
        self.output_folder: Path | None = None
        self.process: QProcess | None = None
        self.process_stderr = ""
        self.process_output_file: Path | None = None

        self._build_ui()
        self._update_ffmpeg_status()
        self._update_preview()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        title = QLabel("Audio Converter")
        title.setObjectName("panelTitle")

        body = QLabel(
            "Convert one audio file to MP3, WAV, or FLAC. FFmpeg does the "
            "conversion, and Tools keeps the workflow simple and safe."
        )
        body.setObjectName("panelBody")
        body.setWordWrap(True)

        self.drop_zone = AudioDropZone()
        self.drop_zone.file_dropped.connect(self._set_input_file)

        input_row = QHBoxLayout()
        input_row.setSpacing(10)
        self.input_label = QLabel("Input: none selected")
        self.input_label.setObjectName("mutedLabel")

        self.input_button = QPushButton("Choose file")
        self.input_button.setObjectName("secondaryButton")
        self.input_button.clicked.connect(self._choose_input_file)
        input_row.addWidget(self.input_label, 1)
        input_row.addWidget(self.input_button)

        output_row = QHBoxLayout()
        output_row.setSpacing(10)
        self.output_label = QLabel("Output folder: none selected")
        self.output_label.setObjectName("mutedLabel")

        self.output_button = QPushButton("Choose folder")
        self.output_button.setObjectName("secondaryButton")
        self.output_button.clicked.connect(self._choose_output_folder)
        output_row.addWidget(self.output_label, 1)
        output_row.addWidget(self.output_button)

        format_row = QHBoxLayout()
        format_row.setSpacing(10)
        format_label = QLabel("Output format")
        format_label.setObjectName("mutedLabel")

        self.format_combo = QComboBox()
        self.format_combo.setObjectName("formatCombo")
        self.format_combo.addItems(SUPPORTED_OUTPUT_FORMATS)
        self.format_combo.currentTextChanged.connect(lambda _: self._update_preview())
        format_row.addWidget(format_label)
        format_row.addWidget(self.format_combo)
        format_row.addStretch(1)

        self.preview_label = QLabel("Output preview: choose an input and output folder")
        self.preview_label.setObjectName("mutedLabel")
        self.preview_label.setWordWrap(True)

        self.ffmpeg_label = QLabel()
        self.ffmpeg_label.setObjectName("mutedLabel")
        self.ffmpeg_label.setWordWrap(True)

        self.status_label = QLabel("Status: waiting")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setWordWrap(True)

        self.convert_button = QPushButton("Convert")
        self.convert_button.setObjectName("primaryButton")
        self.convert_button.clicked.connect(self._start_conversion)

        layout.addWidget(title)
        layout.addWidget(body)
        layout.addWidget(self.drop_zone)
        layout.addLayout(input_row)
        layout.addLayout(output_row)
        layout.addLayout(format_row)
        layout.addWidget(self.preview_label)
        layout.addWidget(self.ffmpeg_label)
        layout.addWidget(self.status_label)
        layout.addStretch(1)
        layout.addWidget(self.convert_button, 0, Qt.AlignmentFlag.AlignRight)

    def _choose_input_file(self) -> None:
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "Choose audio file",
            "",
            "Audio files (*.mp3 *.wav *.flac *.aac *.m4a *.ogg *.wma);;All files (*.*)",
        )
        if file_name:
            self._set_input_file(Path(file_name))

    def _choose_output_folder(self) -> None:
        folder_name = QFileDialog.getExistingDirectory(self, "Choose output folder")
        if folder_name:
            self.output_folder = Path(folder_name)
            self.output_label.setText(f"Output folder: {self.output_folder}")
            self._set_status("Status: output folder selected")
            self._update_preview()

    def _set_input_file(self, path: Path) -> None:
        if not path.exists() or not path.is_file():
            self._set_status(f"Input file does not exist: {path}", "error")
            return

        self.input_file = path
        self.input_label.setText(f"Input: {path.name}")
        self.drop_zone.set_selected_file(path)
        self._set_status("Status: input file selected")
        self._update_preview()

    def _start_conversion(self) -> None:
        if self.input_file is None:
            self._set_status("Choose an input audio file first.", "error")
            return

        if self.output_folder is None:
            self._set_status("Choose an output folder first.", "error")
            return

        options = ConversionOptions(
            input_file=self.input_file,
            output_folder=self.output_folder,
            output_format=self.format_combo.currentText(),
        )

        try:
            command = self.service.build_command(options)
        except FFmpegNotFoundError as error:
            self._set_status(str(error), "error")
            self._update_ffmpeg_status()
            return
        except AudioConversionError as error:
            self._set_status(str(error), "error")
            return

        self.process = QProcess(self)
        self.process_stderr = ""
        self.process_output_file = command.output_file
        self.process.setProgram(str(command.ffmpeg_path))
        self.process.setArguments(command.arguments)
        self.process.setProcessChannelMode(QProcess.ProcessChannelMode.SeparateChannels)
        self.process.readyReadStandardError.connect(self._read_stderr)
        self.process.finished.connect(self._handle_finished)
        self.process.errorOccurred.connect(self._handle_process_error)

        self._set_busy(True)
        self._set_status(f"Converting to {command.output_file.name}...")
        self.process.start()

    def _read_stderr(self) -> None:
        if self.process is None:
            return

        chunk = bytes(self.process.readAllStandardError()).decode(
            "utf-8",
            errors="replace",
        )
        self.process_stderr += chunk

    def _handle_finished(
        self,
        exit_code: int,
        exit_status: QProcess.ExitStatus,
    ) -> None:
        output_file = self.process_output_file
        stderr = self.process_stderr.strip()
        self._set_busy(False)

        if exit_status == QProcess.ExitStatus.NormalExit and exit_code == 0:
            self._set_status(f"Success. Created: {output_file}", "success")
        else:
            details = self._short_error(stderr)
            self._set_status(
                "FFmpeg could not convert this file. The input may be "
                f"unsupported or the conversion failed.\n\n{details}",
                "error",
            )

        self.process = None
        self.process_output_file = None

    def _handle_process_error(self, error: QProcess.ProcessError) -> None:
        if error == QProcess.ProcessError.FailedToStart:
            self._set_busy(False)
            self._set_status(
                "FFmpeg could not be started. Check that the detected FFmpeg "
                "path still exists and is executable.",
                "error",
            )
            self.process = None
            self.process_output_file = None

    def _update_preview(self) -> None:
        if self.input_file is None or self.output_folder is None:
            self.preview_label.setText(
                "Output preview: choose an input and output folder"
            )
            return

        output_file = self.service.get_output_file(
            self.input_file,
            self.output_folder,
            self.format_combo.currentText(),
        )
        self.preview_label.setText(f"Output preview: {output_file}")

    def _update_ffmpeg_status(self) -> None:
        ffmpeg_path = self.service.detect_ffmpeg()
        if ffmpeg_path is None:
            self.ffmpeg_label.setText(
                "FFmpeg: not found. Install FFmpeg, add it to PATH, set "
                "TOOLS_FFMPEG_PATH, or place ffmpeg.exe next to Tools.exe."
            )
            return

        self.ffmpeg_label.setText(f"FFmpeg: {ffmpeg_path}")

    def _set_status(self, message: str, kind: str = "info") -> None:
        object_name = {
            "success": "successLabel",
            "error": "errorLabel",
        }.get(kind, "statusLabel")
        self.status_label.setObjectName(object_name)
        self.status_label.setText(message)
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)

    def _set_busy(self, is_busy: bool) -> None:
        self.convert_button.setEnabled(not is_busy)
        self.format_combo.setEnabled(not is_busy)
        self.input_button.setEnabled(not is_busy)
        self.output_button.setEnabled(not is_busy)
        self.drop_zone.setEnabled(not is_busy)

    @staticmethod
    def _short_error(stderr: str) -> str:
        if not stderr:
            return "No FFmpeg details were returned."

        return stderr[-1200:]
