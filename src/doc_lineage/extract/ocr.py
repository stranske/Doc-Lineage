"""Optional local OCR backends for pages without a text layer."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PIL.Image import Image


class OCRBackend(ABC):
    """Recognize text from a rendered page image."""

    @abstractmethod
    def recognize(self, image: Image, *, rotation: int = 0) -> str | None:
        """Return recognized text or ``None`` when recognition is unavailable."""


class TesseractOCRBackend(OCRBackend):
    """Local Tesseract OCR when the optional dependency is installed."""

    def recognize(self, image: Image, *, rotation: int = 0) -> str | None:
        try:
            import pytesseract
        except ImportError:
            return None

        rotated = image
        if rotation % 360 != 0:
            rotated = image.rotate(-rotation, expand=True)
        text = pytesseract.image_to_string(rotated).strip()
        return text or None


class CallableOCRBackend(OCRBackend):
    """Test helper that delegates recognition to a callable."""

    def __init__(self, recognizer: object) -> None:
        self._recognizer = recognizer

    def recognize(self, image: Image, *, rotation: int = 0) -> str | None:
        result = self._recognizer(image, rotation=rotation)
        if result is None:
            return None
        text = str(result).strip()
        return text or None


def default_ocr_backend() -> OCRBackend | None:
    """Return the default OCR backend when its runtime dependency exists."""
    try:
        import pytesseract  # noqa: F401
    except ImportError:
        return None
    return TesseractOCRBackend()
