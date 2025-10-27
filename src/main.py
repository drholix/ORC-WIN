"""Entry point and high-level UI composition for the OCR desktop app."""
from __future__ import annotations

import sys
from typing import Optional

from PIL import Image, ImageQt
from PySide6.QtCore import QThreadPool, Qt
from PySide6.QtGui import QGuiApplication, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStatusBar,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from hotkeys import GlobalHotkey
from ocr import OcrConfig
from overlay import ScreenCaptureOverlay
from worker import OcrWorker


def _pixmap_to_pillow(pixmap) -> Image.Image:
    """Convert a :class:`~PySide6.QtGui.QPixmap` to a high-DPI aware Pillow image."""

    image = ImageQt.fromqpixmap(pixmap)
    pil_image = image.copy()
    ratio = pixmap.devicePixelRatioF() if hasattr(pixmap, "devicePixelRatioF") else pixmap.devicePixelRatio()
    if ratio and ratio != 1:
        width = int(round(pixmap.width() * ratio))
        height = int(round(pixmap.height() * ratio))
        if pil_image.size != (width, height):
            pil_image = pil_image.resize((width, height), Image.LANCZOS)
    return pil_image


class MainWindow(QMainWindow):
    """Top-level window hosting the OCR workflow."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("ORC-WIN · Selection OCR")
        self.setMinimumSize(460, 320)
        self._ocr_config: Optional[OcrConfig] = None
        self._global_hotkey: Optional[GlobalHotkey] = None

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        button_row = QHBoxLayout()
        layout.addLayout(button_row)

        self.select_button = QPushButton("Select Area (Ctrl+Shift+O)")
        self.select_button.clicked.connect(self.start_selection)
        button_row.addWidget(self.select_button)

        self.copy_button = QPushButton("Copy to Clipboard")
        self.copy_button.clicked.connect(self.copy_to_clipboard)
        self.copy_button.setEnabled(False)
        button_row.addWidget(self.copy_button)

        self.output_edit = QTextEdit()
        self.output_edit.setPlaceholderText("OCR result will appear here…")
        self.output_edit.setAcceptRichText(False)
        layout.addWidget(self.output_edit, 1)

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        self.thread_pool = QThreadPool()
        self.thread_pool.setMaxThreadCount(1)
        self.thread_pool.setExpiryTimeout(-1)

        self.overlay = ScreenCaptureOverlay(self)
        self.overlay.selection_captured.connect(self.handle_capture)

        self._install_shortcuts()

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------
    @property
    def ocr_config(self) -> OcrConfig:
        if self._ocr_config is None:
            self._ocr_config = OcrConfig()
        return self._ocr_config

    # ------------------------------------------------------------------
    # User actions
    # ------------------------------------------------------------------
    def start_selection(self) -> None:
        """Begin the screen selection workflow."""

        if self.overlay.isVisible():
            return
        self.select_button.setEnabled(False)
        self.status_bar.showMessage("Select an area to capture…")
        self.overlay.begin_capture()

    def handle_capture(self, pixmap) -> None:
        """Receive the captured pixmap and queue OCR work."""

        if pixmap.isNull():
            self.status_bar.showMessage("Capture cancelled", 2000)
            self.select_button.setEnabled(True)
            self.select_button.setFocus()
            return

        self.status_bar.showMessage("Running OCR…")
        self.copy_button.setEnabled(False)
        self.output_edit.clear()

        image = _pixmap_to_pillow(pixmap)
        worker = OcrWorker(image=image, config=self.ocr_config)
        worker.signals.completed.connect(self.on_ocr_complete)
        worker.signals.failed.connect(self.on_ocr_failed)
        self.thread_pool.start(worker)

    def on_ocr_complete(self, text: str) -> None:
        """Handle successful OCR completion."""

        self.output_edit.setPlainText(text)
        self.copy_button.setEnabled(bool(text))
        self.select_button.setEnabled(True)
        self.status_bar.showMessage("OCR finished", 3000)

    def on_ocr_failed(self, error: str) -> None:
        """Display an error dialog when OCR fails."""

        self.select_button.setEnabled(True)
        self.copy_button.setEnabled(False)
        self.status_bar.clearMessage()
        QMessageBox.critical(self, "OCR Failed", error)

    def copy_to_clipboard(self) -> None:
        """Copy recognised text into the system clipboard."""

        text = self.output_edit.toPlainText()
        if not text:
            QMessageBox.information(self, "Copy", "No text to copy")
            return
        QApplication.clipboard().setText(text)
        self.status_bar.showMessage("Text copied to clipboard", 2000)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _install_shortcuts(self) -> None:
        """Configure keyboard shortcuts and global hotkeys."""

        local_shortcut = QShortcut(QKeySequence("Ctrl+Shift+O"), self)
        local_shortcut.activated.connect(self.start_selection)

        if not GlobalHotkey.is_supported():
            self.status_bar.showMessage(
                "Global hotkey unavailable on this platform.",
                5000,
            )
            return

        try:
            self._global_hotkey = GlobalHotkey(
                QKeySequence("Ctrl+Shift+O"), auto_register=True, parent=self
            )
        except RuntimeError:
            self._global_hotkey = None
            self.status_bar.showMessage(
                "Could not register global shortcut. Another application may be using it.",
                5000,
            )
            return

        self._global_hotkey.activated.connect(self.start_selection)

    # ------------------------------------------------------------------
    # Qt events
    # ------------------------------------------------------------------
    def closeEvent(self, event) -> None:  # noqa: N802 - Qt API naming convention
        """Ensure the global hotkey is released when the window closes."""

        if self._global_hotkey is not None and self._global_hotkey.isRegistered():
            self._global_hotkey.setRegistered(False)
        self.thread_pool.waitForDone(2000)
        super().closeEvent(event)


def run() -> int:
    """Bootstrap the Qt application and enter the main event loop."""

    if hasattr(QGuiApplication, "setHighDpiScaleFactorRoundingPolicy"):
        QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
        )

    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(run())
