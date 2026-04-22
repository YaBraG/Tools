from __future__ import annotations

import shutil
import tempfile
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QProcess, QSignalBlocker, Qt, QUrl
from PySide6.QtMultimedia import (
    QAudioInput,
    QAudioOutput,
    QMediaCaptureSession,
    QMediaDevices,
    QMediaFormat,
    QMediaPlayer,
    QMediaRecorder,
)
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QFileDialog,
    QDoubleSpinBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSlider,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.ui.widgets.file_drop_card import FileDropCard
from shared.tool_base import ToolContext
from tools.audio_converter.backend import (
    AudioToolsError,
    AudioToolsService,
    FFmpegNotFoundError,
)
from tools.audio_converter.models import (
    AudioEditState,
    AudioFileInfo,
    DEFAULT_EDITOR_MODE,
    EDITOR_MODES,
    MAX_PITCH,
    MAX_SPEED,
    MIN_PITCH,
    MIN_SPEED,
    MIN_TRIM_SPAN_SECONDS,
    SUPPORTED_INPUT_FORMATS,
    SUPPORTED_OUTPUT_FORMATS,
)
from tools.audio_converter.waveform import AudioWaveformWidget


class AudioToolsWidget(QWidget):
    def __init__(self, context: ToolContext, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.service = AudioToolsService(context)
        self.audio_file: AudioFileInfo | None = None
        self.state = AudioEditState(output_format="mp3")

        self.export_process: QProcess | None = None
        self.export_stderr = ""
        self.pending_output_path: Path | None = None

        self.preview_process: QProcess | None = None
        self.preview_stderr = ""
        self.pending_preview_signature: tuple[object, ...] | None = None

        self.preview_directory = Path(
            tempfile.mkdtemp(prefix="tools-audio-tools-preview-")
        )
        self.preview_output_path = self.preview_directory / "preview.wav"
        self.preview_signature: tuple[object, ...] | None = None

        self.current_media_signature: tuple[object, ...] | None = None
        self.current_media_kind = "none"
        self.current_media_duration_ms = 0
        self.current_source_range = (0.0, 0.0)
        self.is_busy = False

        self.capture_session: QMediaCaptureSession | None = None
        self.recording_audio_input: QAudioInput | None = None
        self.media_recorder: QMediaRecorder | None = None
        self.recording_output_path: Path | None = None
        self.is_recording = False
        self.is_finishing_recording = False
        self.recording_error_message = ""

        self.media_player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.media_player.setAudioOutput(self.audio_output)
        self.audio_output.setVolume(0.8)

        self.destroyed.connect(self._cleanup_preview_resources)

        self._build_ui()
        self._connect_media_signals()
        self._set_mode(DEFAULT_EDITOR_MODE)
        self._update_waveform()
        self._update_editor_ui()
        self._update_playback_hint()
        self._refresh_control_state()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        top_row = QHBoxLayout()
        top_row.setSpacing(8)

        self.file_label = QLabel("No audio loaded")
        self.file_label.setObjectName("workspaceTitle")

        self.record_button = QPushButton("Record Audio")
        self.record_button.setObjectName("secondaryButton")
        self.record_button.clicked.connect(self._toggle_recording)

        self.play_button = QPushButton("Preview")
        self.play_button.setObjectName("secondaryButton")
        self.play_button.clicked.connect(self._toggle_playback)

        self.reset_button = QPushButton("Reset")
        self.reset_button.setObjectName("secondaryButton")
        self.reset_button.clicked.connect(self._reset_state)

        top_row.addWidget(self.file_label, 1)
        top_row.addWidget(self.record_button)
        top_row.addWidget(self.play_button)
        top_row.addWidget(self.reset_button)

        supported_formats = ", ".join(extension.upper() for extension in SUPPORTED_INPUT_FORMATS)
        self.audio_file_card = FileDropCard(
            accepted_type_text="audio files",
            multi_file=False,
        )
        self.audio_file_card.clicked.connect(self._choose_audio_file)
        self.audio_file_card.paths_dropped.connect(self._handle_audio_file_drop)
        self.audio_file_card.set_empty_state(
            title="Click to select or drop an audio file",
            subtitle=f"Supported: {supported_formats}",
            caption="Accepts: audio files | Single file",
        )
        self.audio_file_card.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Maximum,
        )

        self.playback_hint_label = QLabel(
            "Preview: load audio to hear the current result."
        )
        self.playback_hint_label.setObjectName("mutedLabel")
        self.playback_hint_label.setWordWrap(True)

        self.mode_group = QButtonGroup(self)
        self.mode_group.setExclusive(True)
        mode_row = QHBoxLayout()
        mode_row.setSpacing(8)
        self.mode_buttons: dict[str, QPushButton] = {}
        for mode_key, label in (
            ("volume", "Volume"),
            ("speed", "Speed"),
            ("pitch", "Pitch"),
        ):
            button = QPushButton(label)
            button.setObjectName("modeTab")
            button.setCheckable(True)
            button.clicked.connect(
                lambda checked=False, mode=mode_key: self._set_mode(mode)
            )
            self.mode_group.addButton(button)
            self.mode_buttons[mode_key] = button
            mode_row.addWidget(button)
        mode_row.addStretch(1)

        self.waveform = AudioWaveformWidget()
        self.waveform.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self.waveform.file_dropped.connect(self._load_audio_file)
        self.waveform.trim_changed.connect(self._on_trim_changed)
        self.waveform.seek_requested.connect(self._seek_to_seconds)

        self.controls_panel = QFrame()
        self.controls_panel.setObjectName("workspacePanel")
        self.controls_panel.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Maximum,
        )
        controls_layout = QVBoxLayout(self.controls_panel)
        controls_layout.setContentsMargins(16, 16, 16, 16)
        controls_layout.setSpacing(12)

        controls_layout.addWidget(self._build_trim_page())
        self.mode_stack = QStackedWidget()
        self.mode_stack.addWidget(self._build_volume_page())
        self.mode_stack.addWidget(self._build_speed_page())
        self.mode_stack.addWidget(self._build_pitch_page())
        controls_layout.addWidget(self.mode_stack)

        export_panel = QFrame()
        export_panel.setObjectName("workspacePanel")
        export_panel.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Maximum,
        )
        export_layout = QVBoxLayout(export_panel)
        export_layout.setContentsMargins(16, 16, 16, 16)
        export_layout.setSpacing(10)

        export_top = QHBoxLayout()
        export_top.setSpacing(8)

        export_label = QLabel("Export format")
        export_label.setObjectName("mutedLabel")

        self.format_combo = QComboBox()
        self.format_combo.setObjectName("formatCombo")
        self.format_combo.addItems(SUPPORTED_OUTPUT_FORMATS)
        self.format_combo.currentTextChanged.connect(self._on_output_format_changed)

        self.export_button = QPushButton("Save Export")
        self.export_button.setObjectName("primaryButton")
        self.export_button.clicked.connect(self._start_export)

        export_top.addWidget(export_label)
        export_top.addWidget(self.format_combo)
        export_top.addStretch(1)
        export_top.addWidget(self.export_button)

        self.export_preview_label = QLabel("Export preview: load audio first")
        self.export_preview_label.setObjectName("mutedLabel")
        self.export_preview_label.setWordWrap(True)

        self.status_label = QLabel("Status: choose audio file to start.")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setWordWrap(True)

        export_layout.addLayout(export_top)
        export_layout.addWidget(self.export_preview_label)
        export_layout.addWidget(self.status_label)

        layout.addLayout(top_row)
        layout.addWidget(self.audio_file_card)
        layout.addWidget(self.playback_hint_label)
        layout.addLayout(mode_row)
        layout.addWidget(self.waveform, 1)
        layout.addWidget(self.controls_panel)
        layout.addWidget(export_panel)

    def _build_trim_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        help_text = QLabel(
            "Trim is always active. Drag waveform handles or type exact start and end times."
        )
        help_text.setObjectName("panelBody")
        help_text.setWordWrap(True)

        row = QHBoxLayout()
        row.setSpacing(10)

        start_label = QLabel("Start (s)")
        start_label.setObjectName("mutedLabel")
        self.trim_start_spin = QDoubleSpinBox()
        self.trim_start_spin.setObjectName("timeSpin")
        self.trim_start_spin.setDecimals(2)
        self.trim_start_spin.setSingleStep(0.01)
        self.trim_start_spin.valueChanged.connect(self._on_trim_spin_changed)

        end_label = QLabel("End (s)")
        end_label.setObjectName("mutedLabel")
        self.trim_end_spin = QDoubleSpinBox()
        self.trim_end_spin.setObjectName("timeSpin")
        self.trim_end_spin.setDecimals(2)
        self.trim_end_spin.setSingleStep(0.01)
        self.trim_end_spin.valueChanged.connect(self._on_trim_spin_changed)

        self.trim_summary_label = QLabel("Range: 0.00s -> 0.00s")
        self.trim_summary_label.setObjectName("mutedLabel")

        row.addWidget(start_label)
        row.addWidget(self.trim_start_spin)
        row.addSpacing(8)
        row.addWidget(end_label)
        row.addWidget(self.trim_end_spin)
        row.addStretch(1)

        layout.addWidget(help_text)
        layout.addLayout(row)
        layout.addWidget(self.trim_summary_label)
        return page

    def _build_volume_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        help_text = QLabel("Adjust playback loudness before export.")
        help_text.setObjectName("panelBody")

        row = QHBoxLayout()
        row.setSpacing(12)

        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setObjectName("editSlider")
        self.volume_slider.setRange(0, 200)
        self.volume_slider.setSingleStep(5)
        self.volume_slider.valueChanged.connect(self._on_volume_changed)

        self.volume_value_label = QLabel("100%")
        self.volume_value_label.setObjectName("valueBadge")

        row.addWidget(self.volume_slider, 1)
        row.addWidget(self.volume_value_label)

        layout.addWidget(help_text)
        layout.addLayout(row)
        return page

    def _build_speed_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        help_text = QLabel("Change playback speed from 0.5x to 2.0x.")
        help_text.setObjectName("panelBody")

        row = QHBoxLayout()
        row.setSpacing(12)

        self.speed_slider = QSlider(Qt.Orientation.Horizontal)
        self.speed_slider.setObjectName("editSlider")
        self.speed_slider.setRange(int(MIN_SPEED * 100), int(MAX_SPEED * 100))
        self.speed_slider.setSingleStep(5)
        self.speed_slider.valueChanged.connect(self._on_speed_changed)

        self.speed_value_label = QLabel("1.00x")
        self.speed_value_label.setObjectName("valueBadge")

        row.addWidget(self.speed_slider, 1)
        row.addWidget(self.speed_value_label)

        layout.addWidget(help_text)
        layout.addLayout(row)
        return page

    def _build_pitch_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        help_text = QLabel("Shift pitch from -12 to +12 semitones.")
        help_text.setObjectName("panelBody")

        row = QHBoxLayout()
        row.setSpacing(12)

        self.pitch_slider = QSlider(Qt.Orientation.Horizontal)
        self.pitch_slider.setObjectName("editSlider")
        self.pitch_slider.setRange(MIN_PITCH, MAX_PITCH)
        self.pitch_slider.setSingleStep(1)
        self.pitch_slider.valueChanged.connect(self._on_pitch_changed)

        self.pitch_value_label = QLabel("+0 st")
        self.pitch_value_label.setObjectName("valueBadge")

        row.addWidget(self.pitch_slider, 1)
        row.addWidget(self.pitch_value_label)

        layout.addWidget(help_text)
        layout.addLayout(row)
        return page

    def _connect_media_signals(self) -> None:
        self.media_player.positionChanged.connect(self._on_player_position_changed)
        self.media_player.durationChanged.connect(self._on_player_duration_changed)
        self.media_player.playbackStateChanged.connect(self._on_playback_state_changed)

    def _choose_recording_target(self) -> tuple[Path | None, str]:
        default_name = f"recording-{datetime.now():%Y%m%d-%H%M%S}.wav"
        selected_path, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Save recording as",
            default_name,
            self._recording_filters(),
        )
        if not selected_path:
            return None, "wav"

        output_format = self._format_from_dialog_selection(selected_path, selected_filter, "wav")
        output_path = self.service.normalize_output_path(Path(selected_path), output_format)
        if output_path.exists():
            self._set_status(
                f"Recording file already exists: {output_path}. Choose a new file name.",
                "error",
            )
            return None, output_format

        if not output_path.parent.exists():
            self._set_status(
                f"Recording folder does not exist: {output_path.parent}",
                "error",
            )
            return None, output_format

        return output_path, output_format

    @staticmethod
    def _recording_media_format(output_format: str) -> QMediaFormat:
        media_format = QMediaFormat()
        if output_format == "wav":
            media_format.setFileFormat(QMediaFormat.FileFormat.Wave)
            media_format.setAudioCodec(QMediaFormat.AudioCodec.Wave)
            return media_format
        if output_format == "mp3":
            media_format.setFileFormat(QMediaFormat.FileFormat.MP3)
            media_format.setAudioCodec(QMediaFormat.AudioCodec.MP3)
            return media_format
        if output_format == "flac":
            media_format.setFileFormat(QMediaFormat.FileFormat.FLAC)
            media_format.setAudioCodec(QMediaFormat.AudioCodec.FLAC)
            return media_format
        if output_format == "m4a":
            media_format.setFileFormat(QMediaFormat.FileFormat.Mpeg4Audio)
            media_format.setAudioCodec(QMediaFormat.AudioCodec.AAC)
            return media_format
        raise AudioToolsError(f"Unsupported recording format: {output_format}")

    def _choose_audio_file(self) -> None:
        filter_patterns = " ".join(f"*.{extension}" for extension in SUPPORTED_INPUT_FORMATS)
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "Open audio file",
            "",
            f"Audio files ({filter_patterns});;All files (*.*)",
        )
        if file_name:
            self._load_audio_file(Path(file_name))

    def _handle_audio_file_drop(self, paths: list[Path]) -> None:
        for path in paths:
            if path.suffix.lower().lstrip(".") in SUPPORTED_INPUT_FORMATS:
                self._load_audio_file(path)
                return
        self._set_status("Drop a supported audio file to load it.", "error")

    def _toggle_recording(self) -> None:
        if self.media_recorder is not None and self.is_recording:
            self._stop_recording()
            return
        self._start_recording()

    def _start_recording(self) -> None:
        output_path, output_format = self._choose_recording_target()
        if output_path is None:
            return

        audio_inputs = QMediaDevices.audioInputs()
        default_input = QMediaDevices.defaultAudioInput()
        if not audio_inputs:
            self._set_status(
                "No microphone is available. Connect or enable a microphone in Windows and try again.",
                "error",
            )
            return
        audio_input_device = default_input if not default_input.isNull() else audio_inputs[0]

        media_format = self._recording_media_format(output_format)
        if not media_format.isSupported(QMediaFormat.ConversionMode.Encode):
            self._set_status(
                f"This system cannot record directly to .{output_format}. Try WAV or another supported format.",
                "error",
            )
            return

        self._teardown_recording_session()
        self._reset_playback_state()

        self.capture_session = QMediaCaptureSession(self)
        self.recording_audio_input = QAudioInput(audio_input_device, self)
        self.media_recorder = QMediaRecorder(self)
        self.capture_session.setAudioInput(self.recording_audio_input)
        self.capture_session.setRecorder(self.media_recorder)
        self.media_recorder.setMediaFormat(media_format)
        self.media_recorder.setOutputLocation(QUrl.fromLocalFile(str(output_path)))
        self.media_recorder.setAudioSampleRate(44100)
        self.media_recorder.setAudioChannelCount(2)
        self.media_recorder.setQuality(QMediaRecorder.Quality.NormalQuality)
        self.media_recorder.recorderStateChanged.connect(self._on_recorder_state_changed)
        self.media_recorder.errorOccurred.connect(self._on_recorder_error)

        if not self.media_recorder.isAvailable():
            self._set_status(
                "Audio recording is unavailable on this system. Check Windows microphone access and multimedia support.",
                "error",
            )
            self._teardown_recording_session()
            return

        self.recording_output_path = output_path
        self.recording_error_message = ""
        self.is_recording = True
        self.is_finishing_recording = False
        self._refresh_control_state()
        self._update_playback_hint()
        self._set_status(
            f"Recording from {audio_input_device.description()}. Click Stop Recording when finished."
        )
        self.media_recorder.record()

    def _stop_recording(self) -> None:
        if self.media_recorder is None or not self.is_recording:
            return

        self.is_finishing_recording = True
        self._refresh_control_state()
        self._set_status("Finishing recording...")
        self.media_recorder.stop()

    def _load_audio_file(self, path: Path) -> None:
        self._reset_playback_state()

        try:
            self._set_busy(True)
            self._set_status("Loading audio workspace...")
            audio_file = self.service.inspect_audio_file(path)
        except (AudioToolsError, FFmpegNotFoundError) as error:
            self._set_status(self._format_error_message(error), "error")
            self._set_busy(False)
            self._update_playback_hint()
            return

        self.audio_file = audio_file
        self.state.reset(audio_file.editor_duration_seconds)
        self.file_label.setText(audio_file.display_name)
        self.audio_file_card.set_loaded_state(
            title=audio_file.display_name,
            subtitle=f"{audio_file.editor_duration_seconds:.2f}s ready to edit",
            caption="Click or drop another audio file to replace.",
        )
        self.waveform.set_audio(
            audio_file.display_name,
            audio_file.waveform_points,
            audio_file.editor_duration_seconds,
        )
        self._load_media_source(
            audio_file.path,
            media_kind="source",
            signature=self._current_result_signature(),
            source_range=(0.0, audio_file.editor_duration_seconds),
        )
        self._update_editor_ui()
        self._set_status("Audio loaded. Preview uses the current edits.")
        self._set_busy(False)

    def _set_mode(self, mode: str) -> None:
        if mode not in EDITOR_MODES:
            return
        self.state.active_mode = mode
        mode_index = EDITOR_MODES.index(mode)
        self.mode_stack.setCurrentIndex(mode_index)
        for mode_key, button in self.mode_buttons.items():
            button.setChecked(mode_key == mode)
        self._refresh_control_state()

    def _reset_state(self) -> None:
        if self.audio_file is None:
            self._reset_playback_state()
            self._set_idle_state("Workspace reset.")
            return

        self.state.reset(self.audio_file.editor_duration_seconds)
        self._reset_playback_state()
        self._restore_source_media_state(playhead_seconds=0.0)
        self._update_editor_ui()
        self._set_status("Workspace reset for the current file.")

    def _toggle_playback(self) -> None:
        if self.audio_file is None:
            self._set_status("Load audio file first.", "error")
            return

        if self.preview_process is not None:
            self._set_status("Preview is still generating...")
            return

        if self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.media_player.pause()
            return

        current_signature = self._current_result_signature()
        if (
            self.media_player.playbackState()
            == QMediaPlayer.PlaybackState.PausedState
            and self.current_media_signature == current_signature
        ):
            self.media_player.play()
        else:
            self._start_preview_playback()

    def _start_preview_playback(self) -> None:
        if self.audio_file is None:
            return

        signature = self._current_result_signature()
        if signature is None:
            return

        if not self._needs_processed_preview():
            self._load_media_source(
                self.audio_file.path,
                media_kind="source",
                signature=signature,
                source_range=(0.0, self.audio_file.editor_duration_seconds),
            )
            self.media_player.setPosition(0)
            self.media_player.play()
            self._set_status("Playing preview. No edits are active yet.")
            return

        if self.preview_signature == signature and self.preview_output_path.exists():
            self._load_media_source(
                self.preview_output_path,
                media_kind="preview",
                signature=signature,
                source_range=self._selected_source_range(),
            )
            self.media_player.setPosition(0)
            self.media_player.play()
            self._set_status("Playing edited preview.")
            return

        try:
            preview_plan = self.service.build_preview_plan(
                self.audio_file,
                self.state,
                self.preview_output_path,
            )
        except (AudioToolsError, FFmpegNotFoundError) as error:
            self._set_status(self._format_error_message(error), "error")
            self._update_playback_hint()
            return

        self.preview_process = QProcess(self)
        self.preview_stderr = ""
        self.pending_preview_signature = signature
        self.preview_process.setProgram(str(preview_plan.ffmpeg_path))
        self.preview_process.setArguments(preview_plan.arguments)
        self.preview_process.setProcessChannelMode(
            QProcess.ProcessChannelMode.SeparateChannels
        )
        self.preview_process.readyReadStandardError.connect(
            self._read_preview_stderr
        )
        self.preview_process.finished.connect(self._handle_preview_finished)
        self.preview_process.errorOccurred.connect(self._handle_preview_error)

        self._set_busy(True)
        self._set_status("Generating edited preview...")
        self._update_playback_hint()
        self.preview_process.start()

    def _seek_to_seconds(self, seconds: float) -> None:
        if self.audio_file is None:
            return
        if self.current_media_kind == "preview" and self.current_media_duration_ms > 0:
            start_seconds, end_seconds = self.current_source_range
            source_span = max(MIN_TRIM_SPAN_SECONDS, end_seconds - start_seconds)
            ratio = (seconds - start_seconds) / source_span
            ratio = min(max(ratio, 0.0), 1.0)
            self.media_player.setPosition(int(ratio * self.current_media_duration_ms))
            return
        self.media_player.setPosition(int(max(0.0, seconds) * 1000))

    def _on_player_position_changed(self, position_ms: int) -> None:
        if self.current_media_kind == "preview" and self.current_media_duration_ms > 0:
            start_seconds, end_seconds = self.current_source_range
            source_span = max(MIN_TRIM_SPAN_SECONDS, end_seconds - start_seconds)
            progress = min(max(position_ms / self.current_media_duration_ms, 0.0), 1.0)
            self.waveform.set_playback_seconds(start_seconds + source_span * progress)
            return
        self.waveform.set_playback_seconds(position_ms / 1000.0)

    def _on_player_duration_changed(self, duration_ms: int) -> None:
        self.current_media_duration_ms = max(0, duration_ms)

    def _on_playback_state_changed(self, state: QMediaPlayer.PlaybackState) -> None:
        self.play_button.setText(
            "Pause Preview"
            if state == QMediaPlayer.PlaybackState.PlayingState
            else "Preview"
        )
        if state == QMediaPlayer.PlaybackState.StoppedState:
            self.waveform.set_playback_seconds(
                self.current_source_range[0]
                if self.current_media_kind == "preview"
                else 0.0
            )
        self._update_playback_hint()

    def _on_trim_changed(self, start_seconds: float, end_seconds: float) -> None:
        if self.audio_file is None:
            return
        start_seconds, end_seconds = self._normalize_trim_range(
            start_seconds,
            end_seconds,
            preserve="end",
        )
        self.state.trim_start_seconds = start_seconds
        self.state.trim_end_seconds = end_seconds
        self._mark_preview_dirty()
        self._update_editor_ui()

    def _on_trim_spin_changed(self) -> None:
        if self.audio_file is None:
            return

        preserve = "end" if self.sender() is self.trim_start_spin else "start"
        start_seconds, end_seconds = self._normalize_trim_range(
            self.trim_start_spin.value(),
            self.trim_end_spin.value(),
            preserve=preserve,
        )
        self.state.trim_start_seconds = start_seconds
        self.state.trim_end_seconds = end_seconds
        self._mark_preview_dirty()
        self._update_editor_ui()

    def _on_volume_changed(self, value: int) -> None:
        self.state.volume_percent = value
        self._mark_preview_dirty()
        self.volume_value_label.setText(f"{value}%")
        self._update_playback_hint()

    def _on_speed_changed(self, value: int) -> None:
        self.state.speed_percent = value
        self._mark_preview_dirty()
        self.speed_value_label.setText(f"{value / 100.0:.2f}x")
        self._update_playback_hint()

    def _on_pitch_changed(self, value: int) -> None:
        self.state.pitch_semitones = value
        self._mark_preview_dirty()
        self.pitch_value_label.setText(f"{value:+d} st")
        self._update_playback_hint()

    def _on_output_format_changed(self, output_format: str) -> None:
        self.state.output_format = output_format
        self._update_export_preview()

    def _start_export(self) -> None:
        if self.audio_file is None:
            self._set_status("Load audio file first.", "error")
            return

        suggested_path = self.service.suggested_output_path(self.audio_file, self.state)
        selected_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save exported audio",
            str(suggested_path),
            self._export_filter(self.state.output_format),
        )
        if not selected_path:
            return

        output_path = self.service.normalize_output_path(
            Path(selected_path),
            self.state.output_format,
        )

        try:
            export_plan = self.service.build_export_plan(self.audio_file, self.state, output_path)
        except (AudioToolsError, FFmpegNotFoundError) as error:
            self._set_status(self._format_error_message(error), "error")
            return

        self.export_process = QProcess(self)
        self.export_stderr = ""
        self.pending_output_path = export_plan.output_file
        self.export_process.setProgram(str(export_plan.ffmpeg_path))
        self.export_process.setArguments(export_plan.arguments)
        self.export_process.setProcessChannelMode(QProcess.ProcessChannelMode.SeparateChannels)
        self.export_process.readyReadStandardError.connect(self._read_export_stderr)
        self.export_process.finished.connect(self._handle_export_finished)
        self.export_process.errorOccurred.connect(self._handle_export_error)

        self._set_busy(True)
        self._set_status(f"Exporting {export_plan.output_file.name}...")
        self.export_process.start()

    def _read_export_stderr(self) -> None:
        if self.export_process is None:
            return
        chunk = bytes(self.export_process.readAllStandardError()).decode(
            "utf-8",
            errors="replace",
        )
        self.export_stderr += chunk

    def _read_preview_stderr(self) -> None:
        if self.preview_process is None:
            return
        chunk = bytes(self.preview_process.readAllStandardError()).decode(
            "utf-8",
            errors="replace",
        )
        self.preview_stderr += chunk

    def _handle_export_finished(
        self,
        exit_code: int,
        exit_status: QProcess.ExitStatus,
    ) -> None:
        output_path = self.pending_output_path
        self._set_busy(False)
        self.export_process = None
        self.pending_output_path = None

        if exit_status == QProcess.ExitStatus.NormalExit and exit_code == 0 and output_path is not None:
            self.state.last_export_path = output_path
            self._update_export_preview()
            self._set_status(f"Export complete: {output_path}", "success")
            self._prompt_load_exported_file(output_path)
        else:
            details = self._short_error(self.export_stderr)
            self._set_status(
                "FFmpeg export failed. Check trim range, output path, or input format.\n\n"
                f"{details}",
                "error",
            )
        self.export_stderr = ""

    def _handle_preview_finished(
        self,
        exit_code: int,
        exit_status: QProcess.ExitStatus,
    ) -> None:
        self._set_busy(False)

        if (
            exit_status == QProcess.ExitStatus.NormalExit
            and exit_code == 0
            and self.preview_output_path.exists()
            and self.pending_preview_signature is not None
        ):
            self.preview_signature = self.pending_preview_signature
            self._load_media_source(
                self.preview_output_path,
                media_kind="preview",
                signature=self.preview_signature,
                source_range=self._selected_source_range(),
            )
            self.media_player.setPosition(0)
            self.media_player.play()
            self._set_status("Playing edited preview.")
        else:
            details = self._short_error(self.preview_stderr)
            self._set_status(
                "Preview generation failed. Try a smaller trim range or check FFmpeg.\n\n"
                f"{details}",
                "error",
            )

        self.preview_process = None
        self.pending_preview_signature = None
        self.preview_stderr = ""
        self._update_playback_hint()

    def _handle_export_error(self, error: QProcess.ProcessError) -> None:
        if error == QProcess.ProcessError.FailedToStart:
            self._set_busy(False)
            self._set_status(
                "FFmpeg could not start.\n\n"
                f"{self._ffmpeg_failure_details()}",
                "error",
            )
            self.export_process = None
            self.pending_output_path = None

    def _handle_preview_error(self, error: QProcess.ProcessError) -> None:
        if error == QProcess.ProcessError.FailedToStart:
            self._set_busy(False)
            self._set_status(
                "Preview FFmpeg process could not start.\n\n"
                f"{self._ffmpeg_failure_details()}",
                "error",
            )
            self.preview_process = None
            self.pending_preview_signature = None
            self.preview_stderr = ""
            self._update_playback_hint()

    def _on_recorder_state_changed(
        self,
        state: QMediaRecorder.RecorderState,
    ) -> None:
        if state == QMediaRecorder.RecorderState.RecordingState:
            self.is_recording = True
            self.is_finishing_recording = False
            self._refresh_control_state()
            self._update_playback_hint()
            return

        if state != QMediaRecorder.RecorderState.StoppedState:
            return

        was_recording = self.is_recording or self.is_finishing_recording
        self.is_recording = False
        self.is_finishing_recording = False
        self._refresh_control_state()
        self._update_playback_hint()

        output_path = self._resolved_recording_output_path()
        error_message = self.recording_error_message
        self._teardown_recording_session()
        if not was_recording:
            return

        if error_message:
            self._set_status(error_message, "error")
            return

        if output_path is None or not output_path.exists() or output_path.stat().st_size == 0:
            if output_path is not None and output_path.exists():
                output_path.unlink(missing_ok=True)
            self._set_status(
                "Recording stopped, but no audio file was created. Check microphone permissions and try again.",
                "error",
            )
            return

        self._load_audio_file(output_path)
        if self.audio_file is not None and self.audio_file.path == output_path:
            self._set_status(f"Recording saved and loaded: {output_path}", "success")

    def _on_recorder_error(
        self,
        error: QMediaRecorder.Error,
        error_message: str,
    ) -> None:
        if error == QMediaRecorder.Error.NoError:
            return

        details = error_message.strip()
        if not details and self.media_recorder is not None:
            details = self.media_recorder.errorString().strip()
        if details:
            details = f"\n\n{details}"
        self.recording_error_message = (
            "Recording failed. Check microphone privacy settings, device availability, "
            "or the selected recording format."
            f"{details}"
        )

    def _resolved_recording_output_path(self) -> Path | None:
        if self.media_recorder is not None:
            actual_location = self.media_recorder.actualLocation().toLocalFile()
            if actual_location:
                return Path(actual_location)
        return self.recording_output_path

    def _teardown_recording_session(self) -> None:
        if self.media_recorder is not None:
            self.media_recorder.deleteLater()
        if self.recording_audio_input is not None:
            self.recording_audio_input.deleteLater()
        if self.capture_session is not None:
            self.capture_session.deleteLater()
        self.media_recorder = None
        self.recording_audio_input = None
        self.capture_session = None
        self.recording_output_path = None
        self.recording_error_message = ""

    def _update_editor_ui(self) -> None:
        if self.audio_file is None:
            with QSignalBlocker(self.trim_start_spin):
                self.trim_start_spin.setRange(0.0, 0.0)
                self.trim_start_spin.setValue(self.state.trim_start_seconds)
            with QSignalBlocker(self.trim_end_spin):
                self.trim_end_spin.setRange(0.0, 0.0)
                self.trim_end_spin.setValue(self.state.trim_end_seconds)
            with QSignalBlocker(self.volume_slider):
                self.volume_slider.setValue(self.state.volume_percent)
            with QSignalBlocker(self.speed_slider):
                self.speed_slider.setValue(self.state.speed_percent)
            with QSignalBlocker(self.pitch_slider):
                self.pitch_slider.setValue(self.state.pitch_semitones)
            with QSignalBlocker(self.format_combo):
                self.format_combo.setCurrentText(self.state.output_format)
            self.volume_value_label.setText(f"{self.state.volume_percent}%")
            self.speed_value_label.setText(f"{self.state.speed_multiplier:.2f}x")
            self.pitch_value_label.setText(f"{self.state.pitch_semitones:+d} st")
            self._update_export_preview()
            self._update_trim_summary()
            self._update_playback_hint()
            return

        duration = self.audio_file.editor_duration_seconds
        with QSignalBlocker(self.trim_start_spin):
            self.trim_start_spin.setRange(0.0, max(0.0, duration))
            self.trim_start_spin.setValue(self.state.trim_start_seconds)

        with QSignalBlocker(self.trim_end_spin):
            self.trim_end_spin.setRange(0.0, max(0.0, duration))
            self.trim_end_spin.setValue(self.state.trim_end_seconds)

        with QSignalBlocker(self.volume_slider):
            self.volume_slider.setValue(self.state.volume_percent)
        with QSignalBlocker(self.speed_slider):
            self.speed_slider.setValue(self.state.speed_percent)
        with QSignalBlocker(self.pitch_slider):
            self.pitch_slider.setValue(self.state.pitch_semitones)
        with QSignalBlocker(self.format_combo):
            self.format_combo.setCurrentText(self.state.output_format)

        self.volume_value_label.setText(f"{self.state.volume_percent}%")
        self.speed_value_label.setText(f"{self.state.speed_multiplier:.2f}x")
        self.pitch_value_label.setText(f"{self.state.pitch_semitones:+d} st")

        self._update_waveform()
        self._update_trim_summary()
        self._update_export_preview()
        self._update_playback_hint()

    def _update_waveform(self) -> None:
        if self.audio_file is None:
            self.waveform.clear_audio()
            return

        self.waveform.set_trim_range(
            self.state.trim_start_seconds,
            self.state.trim_end_seconds,
        )

    def _update_trim_summary(self) -> None:
        self.trim_summary_label.setText(
            f"Range: {self.state.trim_start_seconds:.2f}s -> {self.state.trim_end_seconds:.2f}s"
        )

    def _update_export_preview(self) -> None:
        if self.audio_file is None:
            self.export_preview_label.setText("Export preview: load audio first")
            return

        suggested_path = self.service.suggested_output_path(self.audio_file, self.state)
        if self.state.last_export_path is not None:
            self.export_preview_label.setText(
                f"Export preview: {suggested_path}\nLast export: {self.state.last_export_path}"
            )
            return
        self.export_preview_label.setText(f"Export preview: {suggested_path}")

    def _update_playback_hint(self) -> None:
        if self.is_finishing_recording:
            message = "Recording: finalizing the saved file..."
        elif self.is_recording:
            message = "Recording: capturing microphone input. Stop recording to return to preview."
        elif self.audio_file is None:
            message = "Preview: load audio to hear the current result."
        elif self.preview_process is not None:
            message = "Preview: generating edited audio..."
        elif self.current_media_kind == "preview":
            message = "Preview: edited result."
        elif self._needs_processed_preview():
            message = "Preview: press Preview to render the current edits."
        else:
            message = "Preview: no edits yet, this will play the original file."
        self.playback_hint_label.setText(message)

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
        self.is_busy = is_busy
        self._refresh_control_state()

    def _refresh_control_state(self) -> None:
        controls_enabled = not self.is_busy and not self.is_recording and not self.is_finishing_recording
        has_audio = self.audio_file is not None
        self.audio_file_card.setEnabled(not self.is_busy and not self.is_recording)
        self.record_button.setEnabled(not self.is_busy and not self.is_finishing_recording)
        self.record_button.setText(
            "Stopping..."
            if self.is_finishing_recording
            else "Stop Recording"
            if self.is_recording
            else "Record Audio"
        )
        self.play_button.setEnabled(controls_enabled and has_audio)
        self.reset_button.setEnabled(controls_enabled)
        self.export_button.setEnabled(controls_enabled and has_audio)
        self.format_combo.setEnabled(controls_enabled and has_audio)
        self.waveform.setEnabled(controls_enabled)
        self.waveform.set_trim_editable(controls_enabled)
        for button in self.mode_buttons.values():
            button.setEnabled(controls_enabled and has_audio)
        for control in (
            self.trim_start_spin,
            self.trim_end_spin,
            self.volume_slider,
            self.speed_slider,
            self.pitch_slider,
        ):
            control.setEnabled(controls_enabled and has_audio)

    def _prompt_load_exported_file(self, output_path: Path) -> None:
        response = QMessageBox.question(
            self,
            "Export complete",
            "The export finished successfully.\n\n"
            f"Current file: {self.file_label.text()}\n"
            f"New file: {output_path.name}\n\n"
            "Load the exported audio into Audio Tools now?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if response != QMessageBox.StandardButton.Yes:
            return

        self._load_audio_file(output_path)
        if self.audio_file is not None and self.audio_file.path == output_path:
            self._set_status(f"Loaded exported audio: {output_path}", "success")

    def _load_media_source(
        self,
        media_path: Path,
        *,
        media_kind: str,
        signature: tuple[object, ...] | None,
        source_range: tuple[float, float],
    ) -> None:
        current_path = self.media_player.source().toLocalFile()
        if (
            current_path != str(media_path)
            or self.current_media_kind != media_kind
            or self.current_media_signature != signature
        ):
            self.media_player.stop()
            self.media_player.setSource(QUrl.fromLocalFile(str(media_path)))

        self.current_media_kind = media_kind
        self.current_media_signature = signature
        self.current_media_duration_ms = 0
        self.current_source_range = source_range
        self.waveform.set_playback_seconds(
            source_range[0] if media_kind == "preview" else 0.0
        )

    def _mark_preview_dirty(self) -> None:
        self.media_player.stop()
        self.preview_signature = None
        self.current_media_signature = None
        self.current_media_kind = "source" if self.audio_file is not None else "none"
        self.current_media_duration_ms = 0
        if self.audio_file is not None:
            self._restore_source_media_state(
                playhead_seconds=self.state.trim_start_seconds
            )
        else:
            self.current_source_range = (0.0, 0.0)
            self.waveform.set_playback_seconds(0.0)
        self._remove_preview_file()

    def _reset_playback_state(self) -> None:
        self.media_player.stop()
        self.media_player.setSource(QUrl())
        self.preview_signature = None
        self.pending_preview_signature = None
        self.preview_stderr = ""
        self.current_media_signature = None
        self.current_media_kind = "none"
        self.current_media_duration_ms = 0
        self.current_source_range = (0.0, 0.0)
        self._remove_preview_file()

    def _restore_source_media_state(self, *, playhead_seconds: float) -> None:
        if self.audio_file is None:
            self.current_media_kind = "none"
            self.current_media_signature = None
            self.current_media_duration_ms = 0
            self.current_source_range = (0.0, 0.0)
            self.waveform.set_playback_seconds(0.0)
            self.media_player.setSource(QUrl())
            return

        self._load_media_source(
            self.audio_file.path,
            media_kind="source",
            signature=None,
            source_range=(0.0, self.audio_file.editor_duration_seconds),
        )
        self.waveform.set_playback_seconds(
            max(0.0, min(playhead_seconds, self.audio_file.editor_duration_seconds))
        )

    def _set_idle_state(self, message: str) -> None:
        self.audio_file = None
        self.state = AudioEditState(output_format="mp3")
        self.file_label.setText("No audio loaded")
        supported_formats = ", ".join(extension.upper() for extension in SUPPORTED_INPUT_FORMATS)
        self.audio_file_card.set_empty_state(
            title="Click to select or drop an audio file",
            subtitle=f"Supported: {supported_formats}",
            caption="Accepts: audio files | Single file",
        )
        self.waveform.clear_audio()
        self._set_mode(DEFAULT_EDITOR_MODE)
        self._update_editor_ui()
        self._set_status(message)

    def _normalize_trim_range(
        self,
        start_seconds: float,
        end_seconds: float,
        *,
        preserve: str,
    ) -> tuple[float, float]:
        if self.audio_file is None:
            return 0.0, 0.0

        duration = self.audio_file.editor_duration_seconds
        start_seconds = round(max(0.0, min(start_seconds, duration)), 2)
        end_seconds = round(max(0.0, min(end_seconds, duration)), 2)

        if end_seconds - start_seconds < MIN_TRIM_SPAN_SECONDS:
            if preserve == "end":
                end_seconds = round(
                    min(duration, start_seconds + MIN_TRIM_SPAN_SECONDS),
                    2,
                )
                if end_seconds - start_seconds < MIN_TRIM_SPAN_SECONDS:
                    start_seconds = round(
                        max(0.0, end_seconds - MIN_TRIM_SPAN_SECONDS),
                        2,
                    )
            else:
                start_seconds = round(
                    max(0.0, end_seconds - MIN_TRIM_SPAN_SECONDS),
                    2,
                )
                if end_seconds - start_seconds < MIN_TRIM_SPAN_SECONDS:
                    end_seconds = round(
                        min(duration, start_seconds + MIN_TRIM_SPAN_SECONDS),
                        2,
                    )

        return start_seconds, end_seconds

    def _needs_processed_preview(self) -> bool:
        if self.audio_file is None:
            return False

        trim_changed = (
            self.state.trim_start_seconds > 0.0
            or abs(self.state.trim_end_seconds - self.audio_file.editor_duration_seconds)
            >= 0.005
        )
        return (
            trim_changed
            or self.state.volume_percent != 100
            or self.state.speed_percent != 100
            or self.state.pitch_semitones != 0
        )

    def _current_result_signature(self) -> tuple[object, ...] | None:
        if self.audio_file is None:
            return None

        stat = self.audio_file.path.stat()
        return (
            str(self.audio_file.path),
            stat.st_mtime_ns,
            round(self.state.trim_start_seconds, 2),
            round(self.state.trim_end_seconds, 2),
            self.state.volume_percent,
            self.state.speed_percent,
            self.state.pitch_semitones,
        )

    def _selected_source_range(self) -> tuple[float, float]:
        if self.audio_file is None:
            return (0.0, 0.0)
        return (
            self.state.trim_start_seconds,
            self.state.trim_end_seconds,
        )

    def _remove_preview_file(self) -> None:
        if self.preview_output_path.exists():
            try:
                self.preview_output_path.unlink(missing_ok=True)
            except PermissionError:
                pass

    def _ffmpeg_failure_details(self) -> str:
        installation = self.service.detect_ffmpeg()
        if installation is None:
            return (
                "No FFmpeg installation was found. Checked bundled app files, "
                "TOOLS_FFMPEG_PATH, and system PATH."
            )

        probe_path = installation.ffprobe_path or "missing"
        return (
            f"Detected FFmpeg source: {installation.source}\n"
            f"ffmpeg: {installation.ffmpeg_path}\n"
            f"ffprobe: {probe_path}"
        )

    def _format_error_message(self, error: Exception) -> str:
        if isinstance(error, FFmpegNotFoundError):
            return f"{error}\n\n{self._ffmpeg_failure_details()}"
        return str(error)

    def _cleanup_preview_resources(self, *_: object) -> None:
        if self.preview_process is not None:
            self.preview_process.kill()
            self.preview_process.waitForFinished(1000)
        if self.export_process is not None:
            self.export_process.kill()
            self.export_process.waitForFinished(1000)
        if self.media_recorder is not None and self.media_recorder.recorderState() != QMediaRecorder.RecorderState.StoppedState:
            self.media_recorder.stop()
        self._teardown_recording_session()
        self.media_player.stop()
        self.media_player.setSource(QUrl())
        shutil.rmtree(self.preview_directory, ignore_errors=True)

    @staticmethod
    def _export_filter(output_format: str) -> str:
        return f"{AudioToolsWidget._dialog_filters()[output_format]};;All files (*.*)"

    @staticmethod
    def _recording_filters() -> str:
        return ";;".join(AudioToolsWidget._dialog_filters().values())

    @staticmethod
    def _dialog_filters() -> dict[str, str]:
        return {
            "mp3": "MP3 Audio (*.mp3)",
            "wav": "WAV Audio (*.wav)",
            "flac": "FLAC Audio (*.flac)",
            "m4a": "M4A Audio (*.m4a)",
        }

    @staticmethod
    def _format_from_dialog_selection(
        selected_path: str,
        selected_filter: str,
        fallback_format: str,
    ) -> str:
        extension = Path(selected_path).suffix.lower().lstrip(".")
        if extension in SUPPORTED_OUTPUT_FORMATS:
            return extension

        for output_format, dialog_filter in AudioToolsWidget._dialog_filters().items():
            if selected_filter == dialog_filter:
                return output_format
        return fallback_format

    @staticmethod
    def _short_error(stderr: str) -> str:
        if not stderr:
            return "No FFmpeg details were returned."
        return stderr[-1200:]
