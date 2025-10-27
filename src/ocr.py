"""High-level OCR utilities and configuration primitives."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Iterable, Optional

from PIL import Image, ImageOps
import pytesseract
from pytesseract import TesseractError, TesseractNotFoundError

DEFAULT_LANG = "ind+eng"


class OcrError(RuntimeError):
    """Application specific error raised when OCR fails for any reason."""


@dataclass(slots=True)
class OcrConfig:
    """Runtime configuration for invoking the Tesseract OCR engine.

    Parameters
    ----------
    languages:
        Language packs to use for recognition, expressed in the Tesseract language
        shorthand (defaults to Indonesian + English).
    tesseract_cmd:
        Optional override for the Tesseract executable path. When omitted the value
        of the ``TESSERACT_CMD`` environment variable is honoured if present.
    psm:
        Page segmentation mode. ``6`` works well for capturing regular text blocks
        while still being resilient to minor layout variations.
    oem:
        OCR engine mode. ``1`` enables the LSTM engine which provides the best
        balance between accuracy and performance for desktop OCR.
    extra_flags:
        Additional raw flags forwarded to Tesseract. This allows advanced users to
        configure DPI or turn on experimental features without modifying code.
    """

    languages: str = DEFAULT_LANG
    tesseract_cmd: Optional[str] = field(default=None)
    psm: int = 6
    oem: int = 1
    extra_flags: Iterable[str] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.tesseract_cmd is None:
            env_cmd = os.getenv("TESSERACT_CMD")
            if env_cmd:
                self.tesseract_cmd = env_cmd
        env_lang = os.getenv("OCR_LANGUAGES")
        if env_lang and self.languages == DEFAULT_LANG:
            self.languages = env_lang

    def apply(self) -> None:
        """Apply the configuration to the active pytesseract runtime."""

        if self.tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = self.tesseract_cmd

    def build_cli_flags(self) -> str:
        """Compose a CLI flag string consumed by Tesseract."""

        flags: list[str] = []
        if self.psm >= 0:
            flags.extend(["--psm", str(self.psm)])
        if self.oem >= 0:
            flags.extend(["--oem", str(self.oem)])
        flags.extend(self.extra_flags)
        return " ".join(flags)


def _preprocess_image(image: Image.Image) -> Image.Image:
    """Apply lightweight preprocessing to improve OCR accuracy.

    The preprocessing pipeline is intentionally conservative to keep the latency low
    while still improving contrast for common UI captures.
    """

    processed = image.convert("L") if image.mode not in {"L", "LA"} else image
    processed = ImageOps.autocontrast(processed, cutoff=0.5)
    return processed


def perform_ocr(image: Image.Image, config: Optional[OcrConfig] = None) -> str:
    """Run Tesseract OCR for ``image`` and return the detected text.

    Parameters
    ----------
    image:
        Pillow image instance containing the pixels to process.
    config:
        Optional :class:`OcrConfig` overriding runtime defaults.

    Raises
    ------
    OcrError
        Raised if Tesseract is missing or returns an error payload.
    """

    engine_config = config or OcrConfig()
    engine_config.apply()

    tesseract_kwargs = {
        "lang": engine_config.languages,
        "config": engine_config.build_cli_flags(),
    }

    processed = _preprocess_image(image)
    try:
        text = pytesseract.image_to_string(processed, **tesseract_kwargs)
    except TesseractNotFoundError as exc:  # pragma: no cover - environment specific
        raise OcrError(
            "Tesseract executable was not found. Set the TESSERACT_CMD environment "
            "variable or install Tesseract on this machine."
        ) from exc
    except TesseractError as exc:
        raise OcrError(f"Tesseract failed: {exc}") from exc

    return text.strip()


__all__ = ["OcrConfig", "OcrError", "perform_ocr"]
