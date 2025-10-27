"""Qt worker infrastructure for executing OCR tasks off the UI thread."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from PIL import Image
from PySide6.QtCore import QObject, QRunnable, Signal, Slot

from ocr import OcrConfig, OcrError, perform_ocr


class WorkerSignals(QObject):
    """Signal bundle emitted by :class:`OcrWorker`."""

    completed = Signal(str)
    failed = Signal(str)


@dataclass(slots=True)
class OcrWorker(QRunnable):
    """Background job that runs OCR using :func:`perform_ocr`."""

    image: Image.Image
    config: Optional[OcrConfig]

    def __post_init__(self) -> None:
        super().__init__()
        self.signals = WorkerSignals()

    @Slot()
    def run(self) -> None:  # type: ignore[override]
        """Execute the OCR job and propagate results via signals."""

        try:
            text = perform_ocr(self.image, self.config)
        except OcrError as exc:
            self.signals.failed.emit(str(exc))
        except Exception as exc:  # pragma: no cover - defensive safety net
            self.signals.failed.emit(f"Unexpected error: {exc}")
        else:
            self.signals.completed.emit(text)


__all__ = ["OcrWorker", "WorkerSignals"]
