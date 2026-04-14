from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from PySide6.QtCore import QProcess, QSignalBlocker, Qt, QUrl
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QFileDialog,
    QDoubleSpinBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from shared.tool_base import ToolContext
from tools.audio_converter.backend import (
    AudioToolsError,
    AudioToolsService,
    FFmpegNotFoundError,
)
from tools.audio_converter.models import (
    AudioEditState,
    AudioFileInfo,
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

        self.media_player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.media_player.setAudioOutput(self.audio_output)
        self.audio_output.setVolume(0.8)

        self.destroyed.connect(self._cleanup_preview_resources)

        self._build_ui()
        self._connect_media_signals()
        self._set_mode("trim")
        self._update_waveform()
        self._update_editor_ui()
        self._update_playback_hint()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        top_row = QHBoxLayout()
        top_row.setSpacing(10)

        self.file_label = QLabel("No audio loaded")
        self.file_label.setObjectName("workspaceTitle")

        self.open_button = QPushButton("Open Audio")
        self.open_button.setObjectName("secondaryButton")
        self.open_button.clicked.connect(self._choose_audio_file)

        self.play_button = QPushButton("Preview")
        self.play_button.setObjectName("secondaryButton")
        self.play_button.clicked.connect(self._toggle_playback)

        self.reset_button = QPushButton("Reset")
        self.reset_button.setObjectName("secondaryButton")
        self.reset_button.clicked.connect(self._reset_state)

        top_row.addWidget(self.file_label, 1)
        top_row.addWidget(self.open_button)
        top_row.addWidget(self.play_button)
        top_row.addWidget(self.reset_button)

        self.playback_hint_label = QLabel(
            "Preview: load audio to hear the current result."
        )
        self.playback_hint_label.setObjectName("mutedLabel")
        self.playback_hint_label.setWordWrap(True)

        self.mode_group = QButtonGroup(self)
        self.mode_group.setExclusive(True)
        mode_row = QHBoxLayout()
        mode_row.setSpacing(10)
        self.mode_buttons: dict[str, QPushButton] = {}
        for mode_key, label in (
            ("trim", "Trim"),
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
        self.waveform.file_dropped.connect(self._load_audio_file)
        self.waveform.trim_changed.connect(self._on_trim_changed)
        self.waveform.seek_requested.connect(self._seek_to_seconds)

        self.controls_panel = QFrame()
        self.controls_panel.setObjectName("workspacePanel")
        controls_layout = QVBoxLayout(self.controls_panel)
        controls_layout.setContentsMargins(18, 18, 18, 18)
        controls_layout.setSpacing(14)

        self.mode_stack = QStackedWidget()
        self.mode_stack.addWidget(self._build_trim_page())
        self.mode_stack.addWidget(self._build_volume_page())
        self.mode_stack.addWidget(self._build_speed_page())
        self.mode_stack.addWidget(self._build_pitch_page())
        controls_layout.addWidget(self.mode_stack)

        export_panel = QFrame()
        export_panel.setObjectName("workspacePanel")
        export_layout = QVBoxLayout(export_panel)
        export_layout.setContentsMargins(18, 18, 18, 18)
        export_layout.setSpacing(12)

        export_top = QHBoxLayout()
        export_top.setSpacing(10)

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
            "Set trim start and end. Drag waveform handles or type exact times."
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
        self.state.reset(audio_file.duration_seconds)
        self.file_label.setText(audio_file.display_name)
        self.waveform.set_audio(
            audio_file.display_name,
            audio_file.waveform_points,
            audio_file.duration_seconds,
        )
        self._load_media_source(
            audio_file.path,
            media_kind="source",
            signature=self._current_result_signature(),
            source_range=(0.0, audio_file.duration_seconds),
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
        self.waveform.set_trim_editable(mode == "trim")
        for mode_key, button in self.mode_buttons.items():
            button.setChecked(mode_key == mode)

    def _reset_state(self) -> None:
        if self.audio_file is None:
            self._reset_playback_state()
            self._set_idle_state("Workspace reset.")
            return

        self.state.reset(self.audio_file.duration_seconds)
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
                source_range=(0.0, self.audio_file.duration_seconds),
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

        if exit_status == QProcess.ExitStatus.NormalExit and exit_code == 0 and output_path is not None:
            self.state.last_export_path = output_path
            self._update_export_preview()
            self._set_status(f"Export complete: {output_path}", "success")
        else:
            details = self._short_error(self.export_stderr)
            self._set_status(
                "FFmpeg export failed. Check trim range, output path, or input format.\n\n"
                f"{details}",
                "error",
            )

        self.export_process = None
        self.pending_output_path = None

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

        duration = self.audio_file.duration_seconds
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
        if self.audio_file is None:
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
        self.open_button.setEnabled(not is_busy)
        self.play_button.setEnabled(not is_busy)
        self.reset_button.setEnabled(not is_busy)
        self.export_button.setEnabled(not is_busy)
        self.format_combo.setEnabled(not is_busy)
        self.waveform.setEnabled(not is_busy)
        self.waveform.set_trim_editable(
            self.state.active_mode == "trim" and not is_busy
        )
        for button in self.mode_buttons.values():
            button.setEnabled(not is_busy)
        for control in (
            self.trim_start_spin,
            self.trim_end_spin,
            self.volume_slider,
            self.speed_slider,
            self.pitch_slider,
        ):
            control.setEnabled(not is_busy)

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
            source_range=(0.0, self.audio_file.duration_seconds),
        )
        self.waveform.set_playback_seconds(
            max(0.0, min(playhead_seconds, self.audio_file.duration_seconds))
        )

    def _set_idle_state(self, message: str) -> None:
        self.audio_file = None
        self.state = AudioEditState(output_format="mp3")
        self.file_label.setText("No audio loaded")
        self.waveform.clear_audio()
        self._set_mode("trim")
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

        duration = self.audio_file.duration_seconds
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
            or abs(self.state.trim_end_seconds - self.audio_file.duration_seconds)
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
        self.media_player.stop()
        self.media_player.setSource(QUrl())
        shutil.rmtree(self.preview_directory, ignore_errors=True)

    @staticmethod
    def _export_filter(output_format: str) -> str:
        mapping = {
            "mp3": "MP3 Audio (*.mp3)",
            "wav": "WAV Audio (*.wav)",
            "flac": "FLAC Audio (*.flac)",
            "m4a": "M4A Audio (*.m4a)",
        }
        return f"{mapping[output_format]};;All files (*.*)"

    @staticmethod
    def _short_error(stderr: str) -> str:
        if not stderr:
            return "No FFmpeg details were returned."
        return stderr[-1200:]
