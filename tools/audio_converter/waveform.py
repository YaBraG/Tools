from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

from tools.audio_converter.models import MIN_TRIM_SPAN_SECONDS


class AudioWaveformWidget(QWidget):
    file_dropped = Signal(object)
    trim_changed = Signal(float, float)
    seek_requested = Signal(float)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setMinimumHeight(260)
        self.waveform_points: tuple[float, ...] = ()
        self.duration_seconds = 0.0
        self.trim_start_seconds = 0.0
        self.trim_end_seconds = 0.0
        self.playback_seconds = 0.0
        self.trim_editable = True
        self.file_name = ""
        self._drag_handle: str | None = None

    def sizeHint(self) -> QSize:  # noqa: D401
        return QSize(900, 280)

    def minimumSizeHint(self) -> QSize:  # noqa: D401
        return QSize(420, 240)

    def set_audio(
        self,
        file_name: str,
        waveform_points: tuple[float, ...],
        duration_seconds: float,
    ) -> None:
        self.file_name = file_name
        self.waveform_points = waveform_points
        self.duration_seconds = duration_seconds
        self.playback_seconds = 0.0
        self.update()

    def clear_audio(self) -> None:
        self.file_name = ""
        self.waveform_points = ()
        self.duration_seconds = 0.0
        self.trim_start_seconds = 0.0
        self.trim_end_seconds = 0.0
        self.playback_seconds = 0.0
        self.update()

    def set_trim_range(self, start_seconds: float, end_seconds: float) -> None:
        self.trim_start_seconds = start_seconds
        self.trim_end_seconds = end_seconds
        self.update()

    def set_playback_seconds(self, playback_seconds: float) -> None:
        self.playback_seconds = playback_seconds
        self.update()

    def set_trim_editable(self, trim_editable: bool) -> None:
        self.trim_editable = trim_editable
        self.update()

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

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if not self.waveform_points or self.duration_seconds <= 0:
            return

        start_x, end_x = self._trim_handle_positions()
        cursor_x = event.position().x()
        if self.trim_editable and abs(cursor_x - start_x) <= 10:
            self._drag_handle = "start"
            return
        if self.trim_editable and abs(cursor_x - end_x) <= 10:
            self._drag_handle = "end"
            return

        self.seek_requested.emit(self._seconds_for_x(cursor_x))

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_handle is None or self.duration_seconds <= 0:
            return

        cursor_seconds = self._seconds_for_x(event.position().x())
        if self._drag_handle == "start":
            new_start = min(
                cursor_seconds,
                self.trim_end_seconds - MIN_TRIM_SPAN_SECONDS,
            )
            new_start = max(0.0, new_start)
            self.trim_changed.emit(new_start, self.trim_end_seconds)
            return

        new_end = max(
            cursor_seconds,
            self.trim_start_seconds + MIN_TRIM_SPAN_SECONDS,
        )
        new_end = min(self.duration_seconds, new_end)
        self.trim_changed.emit(self.trim_start_seconds, new_end)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: ARG002
        self._drag_handle = None

    def paintEvent(self, event) -> None:  # noqa: N802, ARG002
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(0, 0, -1, -1)

        background = QPainterPath()
        background.addRoundedRect(QRectF(rect), 18, 18)
        painter.fillPath(background, QColor("#0F172A"))
        painter.setPen(QPen(QColor("#253044"), 1))
        painter.drawPath(background)

        if not self.waveform_points:
            self._draw_empty_state(painter, QRectF(rect))
            return

        content_rect = QRectF(rect.adjusted(18, 18, -18, -18))
        self._draw_selection_overlay(painter, content_rect)
        self._draw_waveform(painter, content_rect)
        self._draw_trim_handles(painter, content_rect)
        self._draw_playhead(painter, content_rect)
        self._draw_time_labels(painter, content_rect)

    def _draw_empty_state(self, painter: QPainter, rect: QRectF) -> None:
        painter.setPen(QColor("#F8FAFC"))
        title_rect = QRectF(rect.left(), rect.center().y() - 26, rect.width(), 24)
        painter.drawText(title_rect, Qt.AlignmentFlag.AlignCenter, "Waveform preview")

        painter.setPen(QColor("#94A3B8"))
        subtitle_rect = QRectF(rect.left(), rect.center().y() + 4, rect.width(), 20)
        painter.drawText(
            subtitle_rect,
            Qt.AlignmentFlag.AlignCenter,
            "Use the file card above or drop audio here",
        )

    def _draw_selection_overlay(self, painter: QPainter, rect: QRectF) -> None:
        start_x, end_x = self._trim_handle_positions(rect)
        dim_color = QColor("#020617")
        dim_color.setAlpha(120)
        painter.fillRect(QRectF(rect.left(), rect.top(), start_x - rect.left(), rect.height()), dim_color)
        painter.fillRect(QRectF(end_x, rect.top(), rect.right() - end_x, rect.height()), dim_color)

    def _draw_waveform(self, painter: QPainter, rect: QRectF) -> None:
        count = len(self.waveform_points)
        if count == 0:
            return

        gap = 2
        bar_width = max(2.0, (rect.width() - (count - 1) * gap) / count)
        center_y = rect.center().y()

        start_x, end_x = self._trim_handle_positions(rect)
        for index, value in enumerate(self.waveform_points):
            height = max(8.0, value * rect.height() * 0.9)
            x = rect.left() + index * (bar_width + gap)
            bar_rect = QRectF(x, center_y - height / 2.0, bar_width, height)
            color = QColor("#60A5FA") if start_x <= x <= end_x else QColor("#334155")
            painter.fillRect(bar_rect, color)

    def _draw_trim_handles(self, painter: QPainter, rect: QRectF) -> None:
        start_x, end_x = self._trim_handle_positions(rect)
        handle_pen = QPen(QColor("#F8FAFC"), 2)
        painter.setPen(handle_pen)
        painter.drawLine(QPointF(start_x, rect.top()), QPointF(start_x, rect.bottom()))
        painter.drawLine(QPointF(end_x, rect.top()), QPointF(end_x, rect.bottom()))

        painter.fillRect(QRectF(start_x - 3, rect.top(), 6, rect.height()), QColor("#F8FAFC"))
        painter.fillRect(QRectF(end_x - 3, rect.top(), 6, rect.height()), QColor("#F8FAFC"))

    def _draw_playhead(self, painter: QPainter, rect: QRectF) -> None:
        if self.duration_seconds <= 0:
            return
        position_ratio = min(max(self.playback_seconds / self.duration_seconds, 0.0), 1.0)
        x = rect.left() + position_ratio * rect.width()
        pen = QPen(QColor("#22C55E"), 2)
        painter.setPen(pen)
        painter.drawLine(QPointF(x, rect.top()), QPointF(x, rect.bottom()))

    def _draw_time_labels(self, painter: QPainter, rect: QRectF) -> None:
        painter.setPen(QColor("#64748B"))
        painter.drawText(
            QRectF(rect.left(), rect.bottom() + 6, 80, 18),
            Qt.AlignmentFlag.AlignLeft,
            self._format_time(0.0),
        )
        painter.drawText(
            QRectF(rect.right() - 80, rect.bottom() + 6, 80, 18),
            Qt.AlignmentFlag.AlignRight,
            self._format_time(self.duration_seconds),
        )

    def _trim_handle_positions(self, rect: QRectF | None = None) -> tuple[float, float]:
        draw_rect = rect or QRectF(self.rect().adjusted(18, 18, -18, -18))
        if self.duration_seconds <= 0:
            return draw_rect.left(), draw_rect.right()

        start_ratio = min(max(self.trim_start_seconds / self.duration_seconds, 0.0), 1.0)
        end_ratio = min(max(self.trim_end_seconds / self.duration_seconds, 0.0), 1.0)
        return (
            draw_rect.left() + start_ratio * draw_rect.width(),
            draw_rect.left() + end_ratio * draw_rect.width(),
        )

    def _seconds_for_x(self, x_position: float) -> float:
        rect = QRectF(self.rect().adjusted(18, 18, -18, -18))
        if self.duration_seconds <= 0 or rect.width() <= 0:
            return 0.0

        ratio = (x_position - rect.left()) / rect.width()
        ratio = min(max(ratio, 0.0), 1.0)
        return ratio * self.duration_seconds

    @staticmethod
    def _format_time(seconds: float) -> str:
        total_seconds = max(0, int(round(seconds)))
        minutes, seconds_part = divmod(total_seconds, 60)
        hours, minutes = divmod(minutes, 60)
        if hours:
            return f"{hours}:{minutes:02d}:{seconds_part:02d}"
        return f"{minutes}:{seconds_part:02d}"
