"""Entry point and high-level UI composition for the OCR desktop app."""
from __future__ import annotations

import sys
from typing import Optional

from PIL import Image, ImageQt
from PySide6.QtCore import QSettings, QThreadPool, Qt
from PySide6.QtGui import QGuiApplication, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
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
    ratio = (
        pixmap.devicePixelRatioF()
        if hasattr(pixmap, "devicePixelRatioF")
        else pixmap.devicePixelRatio()
    )
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
        self.setMinimumSize(520, 360)
        self._ocr_config: Optional[OcrConfig] = None
        self._global_hotkey: Optional[GlobalHotkey] = None
        self._settings = QSettings("ORC-WIN", "SelectionOCR")

        self._configure_palette()

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        header = QLabel("Selection-based OCR for Windows 10/11")
        header.setObjectName("appTitleLabel")
        header.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        header.setWordWrap(True)
        layout.addWidget(header)

        subheader = QLabel(
            "Gunakan tombol di bawah untuk memilih area layar dan ekstraksi teks secara instan."
        )
        subheader.setObjectName("subtitleLabel")
        subheader.setWordWrap(True)
        layout.addWidget(subheader)

        control_frame = QFrame()
        control_frame.setObjectName("controlFrame")
        control_frame.setFrameShape(QFrame.Shape.StyledPanel)
        control_layout = QVBoxLayout(control_frame)
        control_layout.setContentsMargins(12, 12, 12, 12)
        control_layout.setSpacing(8)
        layout.addWidget(control_frame)

        toggle_row = QHBoxLayout()
        control_layout.addLayout(toggle_row)

        self.auto_copy_checkbox = QCheckBox("Auto Copy to Clipboard")
        self.auto_copy_checkbox.setToolTip(
            "Jika aktif, hasil OCR otomatis tersalin ke clipboard setiap selesai diproses."
        )
        self.auto_copy_checkbox.setChecked(self._load_auto_copy_preference())
        self.auto_copy_checkbox.toggled.connect(self._on_auto_copy_toggled)
        toggle_row.addWidget(self.auto_copy_checkbox)
        toggle_row.addStretch(1)

        button_row = QHBoxLayout()
        control_layout.addLayout(button_row)

        self.select_button = QPushButton("Select Area (Ctrl+Shift+O)")
        self.select_button.clicked.connect(self.start_selection)
        self.select_button.setToolTip("Mulai mode seleksi layar untuk menangkap teks.")
        button_row.addWidget(self.select_button)

        self.copy_button = QPushButton("Copy to Clipboard")
        self.copy_button.clicked.connect(self.copy_to_clipboard)
        self.copy_button.setEnabled(False)
        self.copy_button.setToolTip("Salin hasil OCR terbaru ke clipboard.")
        button_row.addWidget(self.copy_button)

        self.output_edit = QTextEdit()
        self.output_edit.setPlaceholderText("OCR result will appear here…")
        self.output_edit.setAcceptRichText(False)
        self.output_edit.textChanged.connect(self._on_output_text_changed)
        layout.addWidget(self.output_edit, 1)

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.length_label = QLabel("0 karakter")
        self.length_label.setObjectName("lengthLabel")
        self.status_bar.addPermanentWidget(self.length_label)

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
        self.copy_button.setEnabled(False)
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
        self._set_output_text("")

        image = _pixmap_to_pillow(pixmap)
        worker = OcrWorker(image=image, config=self.ocr_config)
        worker.signals.completed.connect(self.on_ocr_complete)
        worker.signals.failed.connect(self.on_ocr_failed)
        self.thread_pool.start(worker)

    def on_ocr_complete(self, text: str) -> None:
        """Handle successful OCR completion."""

        self._set_output_text(text)
        self.copy_button.setEnabled(bool(text))
        self.select_button.setEnabled(True)

        if self.auto_copy_checkbox.isChecked() and text:
            self._copy_text_to_clipboard(
                text,
                announce=True,
                message="OCR selesai – hasil otomatis tersalin.",
            )
        else:
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
        self._copy_text_to_clipboard(text, announce=True)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _configure_palette(self) -> None:
        """Apply lightweight styling to polish the UI."""

        self.setStyleSheet(
            """
            #appTitleLabel {
                font-size: 20px;
                font-weight: 600;
            }
            #subtitleLabel {
                color: #5c5f66;
            }
            #controlFrame {
                border: 1px solid rgba(92, 95, 102, 0.25);
                border-radius: 8px;
                background-color: rgba(255, 255, 255, 0.65);
            }
            #lengthLabel {
                color: #3d3f45;
                font-weight: 500;
            }
            QTextEdit {
                font-family: "Cascadia Code", "Consolas", "Courier New", monospace;
                font-size: 12pt;
                line-height: 1.45em;
                border-radius: 6px;
                border: 1px solid rgba(92, 95, 102, 0.2);
                padding: 8px;
            }
            QPushButton {
                padding: 8px 14px;
            }
            QPushButton:disabled {
                color: #8b8d92;
            }
        """
        )

    def _load_auto_copy_preference(self) -> bool:
        value = self._settings.value("auto_copy", True)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in {"true", "1", "yes", "on"}
        return True

    def _on_auto_copy_toggled(self, checked: bool) -> None:
        """Persist the auto copy preference when the checkbox changes."""

        self._settings.setValue("auto_copy", checked)
        self.status_bar.showMessage(
            "Auto copy aktif." if checked else "Auto copy dinonaktifkan.",
            2200,
        )

    def _set_output_text(self, text: str) -> None:
        """Populate the output editor without breaking change tracking."""

        block_state = self.output_edit.blockSignals(True)
        self.output_edit.setPlainText(text)
        self.output_edit.blockSignals(block_state)
        self._update_character_count(text)

    def _on_output_text_changed(self) -> None:
        """Update UI counters when the output text changes manually."""

        text = self.output_edit.toPlainText()
        self._update_character_count(text)
        self.copy_button.setEnabled(bool(text))

    def _update_character_count(self, text: str) -> None:
        """Reflect the current number of characters in the status bar label."""

        length = len(text)
        self.length_label.setText(
            f"{length} karakter" if length else "0 karakter"
        )

    def _copy_text_to_clipboard(
        self, text: str, *, announce: bool, message: str | None = None
    ) -> None:
        """Copy ``text`` to the clipboard and optionally emit a status message."""

        QApplication.clipboard().setText(text)
        if announce:
            self.status_bar.showMessage(
                message or "Text copied to clipboard",
                2500,
            )

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
        self._settings.sync()
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
