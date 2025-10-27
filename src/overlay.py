"""Screen overlay widget that enables selection-based screen capture."""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QPoint, QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QCursor, QGuiApplication, QPainter, QPixmap
from PySide6.QtWidgets import QRubberBand, QWidget


class ScreenCaptureOverlay(QWidget):
    """Semi-transparent overlay that allows users to draw a capture region."""

    selection_captured = Signal(QPixmap)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._origin = QPoint()
        self._current_rect = QRect()
        self._rubber_band = QRubberBand(QRubberBand.Rectangle, self)

        self.setWindowFlags(
            Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.Tool | Qt.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setMouseTracking(True)
        self.setCursor(Qt.CrossCursor)

    # ------------------------------------------------------------------
    # Lifecycle helpers
    # ------------------------------------------------------------------
    def begin_capture(self) -> None:
        """Display the overlay on the screen that currently hosts the cursor."""

        self._current_rect = QRect()
        self._rubber_band.hide()

        cursor_pos = QCursor.pos()
        screen = QGuiApplication.screenAt(cursor_pos) or QGuiApplication.primaryScreen()
        if screen is None:
            self.selection_captured.emit(QPixmap())
            return

        geometry = screen.geometry()
        self.setGeometry(geometry)
        if self.windowHandle() is not None:
            self.windowHandle().setScreen(screen)
        self.show()
        self.activateWindow()
        self.raise_()
        self.setFocus()
        self.update()

    def cancel(self) -> None:
        """Hide the overlay and emit an empty pixmap to signal cancellation."""

        self.hide()
        self.selection_captured.emit(QPixmap())

    # ------------------------------------------------------------------
    # Qt event handlers
    # ------------------------------------------------------------------
    def paintEvent(self, event) -> None:  # noqa: N802 - Qt API naming convention
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        overlay_color = QColor(0, 0, 0, 160)
        painter.fillRect(self.rect(), overlay_color)
        if not self._current_rect.isNull():
            painter.setCompositionMode(QPainter.CompositionMode_Clear)
            painter.fillRect(self._current_rect, QColor(0, 0, 0, 0))
        painter.end()

    def keyPressEvent(self, event) -> None:  # noqa: N802 - Qt API naming convention
        if event.key() in {Qt.Key_Escape, Qt.Key_Q}:
            event.accept()
            self.cancel()
            return
        super().keyPressEvent(event)

    def mousePressEvent(self, event) -> None:  # noqa: N802 - Qt API naming convention
        if event.button() == Qt.LeftButton:
            self._origin = event.pos()
            self._current_rect = QRect(self._origin, QSize())
            self._rubber_band.setGeometry(self._current_rect)
            self._rubber_band.show()
            event.accept()
            self.update()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802 - Qt API naming convention
        if not self._rubber_band.isVisible():
            return
        self._current_rect = QRect(self._origin, event.pos()).normalized()
        self._rubber_band.setGeometry(self._current_rect)
        self.update()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 - Qt API naming convention
        if event.button() == Qt.LeftButton and self._rubber_band.isVisible():
            self._rubber_band.hide()
            rect = QRect(self._origin, event.pos()).normalized()
            self._current_rect = rect
            if rect.width() < 5 or rect.height() < 5:
                self.cancel()
                return
            self.hide()
            self._emit_capture(rect)
        else:
            super().mouseReleaseEvent(event)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _emit_capture(self, rect: QRect) -> None:
        """Grab the pixels within ``rect`` and emit them as a :class:`QPixmap`."""

        global_top_left = self.mapToGlobal(rect.topLeft())
        screen = QGuiApplication.screenAt(global_top_left) or QGuiApplication.primaryScreen()
        if screen is None:
            self.selection_captured.emit(QPixmap())
            return

        capture = screen.grabWindow(
            0,
            global_top_left.x(),
            global_top_left.y(),
            rect.width(),
            rect.height(),
        )
        if capture.isNull():
            self.selection_captured.emit(QPixmap())
            return

        capture.setDevicePixelRatio(screen.devicePixelRatio())
        self.selection_captured.emit(capture)


__all__ = ["ScreenCaptureOverlay"]
