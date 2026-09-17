"""Optional local OCR backends for pages without a text layer."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from PIL.Image import Image


class Recognizer(Protocol):
    """Callable recognition hook used by :class:`CallableOCRBackend`."""

    def __call__(self, image: Image, *, rotation: int = 0) -> object | None: ...


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
        try:
            text = pytesseract.image_to_string(rotated).strip()
        except (OSError, RuntimeError, ValueError):
            # Covers pytesseract.TesseractNotFoundError (an OSError subclass) and
            # a Tesseract binary that is present but fails on this page: both are
            # "recognition unavailable", which the caller records as unreadable.
            return None
        return text or None


class CallableOCRBackend(OCRBackend):
    """Test helper that delegates recognition to a callable."""

    def __init__(self, recognizer: Recognizer) -> None:
        self._recognizer = recognizer

    def recognize(self, image: Image, *, rotation: int = 0) -> str | None:
        result = self._recognizer(image, rotation=rotation)
        if result is None:
            return None
        text = str(result).strip()
        return text or None


def default_ocr_backend() -> OCRBackend | None:
    """Return the default OCR backend only when Tesseract can actually run.

    Importing ``pytesseract`` proves nothing: the package is a wrapper around a
    separately installed ``tesseract`` executable. Probing the version is the
    cheapest call that fails when the binary is missing, and an absent backend
    has to surface as ``pages_unreadable`` rather than a silent skip.
    """
    try:
        import pytesseract
    except ImportError:
        return None
    try:
        pytesseract.get_tesseract_version()
    except (OSError, RuntimeError, ValueError):
        return None
    return TesseractOCRBackend()
