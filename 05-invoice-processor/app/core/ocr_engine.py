"""OCR Engine integrating pdf2image and pytesseract."""

import io
import logging

import pytesseract
from pdf2image import convert_from_bytes
from PIL import Image
from pypdf import PdfReader

from app.core.config import settings

logger = logging.getLogger(__name__)


class OCREngine:
    """Extracts raw text and metadata from PDF and image files using Tesseract."""

    def __init__(self, tesseract_cmd: str | None = None) -> None:
        cmd = tesseract_cmd or settings.tesseract_cmd
        if cmd:
            pytesseract.pytesseract.tesseract_cmd = cmd

    def count_pages(self, file_bytes: bytes, filename: str) -> int:
        """Determines page count for PDF or 1 for standard image files."""
        lower_name = filename.lower()
        if lower_name.endswith(".pdf"):
            try:
                reader = PdfReader(io.BytesIO(file_bytes))
                return len(reader.pages)
            except Exception as exc:
                logger.warning("Could not read PDF with pypdf: %s. Falling back to 1.", exc)
                return 1
        return 1

    def process_file(
        self,
        file_bytes: bytes,
        filename: str,
        lang: str = "spa+eng",
    ) -> tuple[str, int]:
        """Converts file to images and extracts raw text with Tesseract.

        Returns (raw_text, page_count).
        """
        lower_name = filename.lower()
        images: list[Image.Image] = []

        if lower_name.endswith(".pdf"):
            try:
                images = convert_from_bytes(file_bytes, dpi=200, fmt="png")
            except Exception as exc:
                logger.error("Failed to convert PDF to images: %s", exc)
                raise RuntimeError(f"Error converting PDF to images: {exc}") from exc
        else:
            try:
                image = Image.open(io.BytesIO(file_bytes)).convert("RGB")
                images = [image]
            except Exception as exc:
                logger.error("Failed to load image file: %s", exc)
                raise RuntimeError(f"Error loading image file: {exc}") from exc

        page_texts: list[str] = []
        for idx, img in enumerate(images, start=1):
            try:
                text = pytesseract.image_to_string(img, lang=lang)
                page_texts.append(text.strip())
            except Exception as exc:
                logger.error("OCR failed on page %d: %s", idx, exc)
                raise RuntimeError(f"OCR processing failed on page {idx}: {exc}") from exc

        combined_text = "\n\n".join(page_texts)
        return combined_text, len(images)


ocr_engine = OCREngine()
