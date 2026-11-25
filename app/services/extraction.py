"""Text extraction helpers for uploaded author materials.

The module deliberately does not OCR standalone images: OCR is only a fallback
for scanned PDFs, as required by the material-processing business rules.
"""
from __future__ import annotations

import logging
import mimetypes
from pathlib import Path
from typing import BinaryIO

logger = logging.getLogger(__name__)

# A PDF with only a handful of extracted characters is usually a scan, a cover
# page, or otherwise not meaningfully text-based.
PDF_OCR_MIN_TEXT_CHARS = 20

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}
VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv"}
TEXT_EXTENSIONS = {".txt"}
WORD_EXTENSIONS = {".docx"}
PDF_EXTENSIONS = {".pdf"}

MIME_TO_EXTENSION = {
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "text/plain": ".txt",
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "video/mp4": ".mp4",
    "video/quicktime": ".mov",
    "video/x-msvideo": ".avi",
    "video/x-matroska": ".mkv",
}


def detect_language(text: str) -> str | None:
    """Return 'ru' or 'en' using the dominant alphabet in extracted text.

    This lightweight detector avoids introducing another runtime dependency.
    It is intentionally conservative for empty or non-linguistic content.
    """
    cyrillic = 0
    latin = 0
    for char in text:
        if "\u0400" <= char <= "\u04ff":
            cyrillic += 1
        elif ("a" <= char.lower() <= "z"):
            latin += 1

    total = cyrillic + latin
    if total == 0:
        return None
    return "ru" if cyrillic >= latin else "en"


def _resolve_extension(file_path: str | Path, file_type: str | None) -> str:
    """Resolve extension from a filename or MIME/file-type value."""
    if file_type:
        normalized = str(file_type).strip().lower()
        if normalized in MIME_TO_EXTENSION:
            return MIME_TO_EXTENSION[normalized]
        # Accept extensions and enum-like values such as 'pdf' or 'FileType.pdf'.
        candidate = normalized.rsplit(".", 1)[-1]
        if not candidate.startswith("."):
            candidate = f".{candidate}"
        if candidate in (
            PDF_EXTENSIONS | WORD_EXTENSIONS | TEXT_EXTENSIONS
            | IMAGE_EXTENSIONS | VIDEO_EXTENSIONS
        ):
            return candidate

    path_extension = Path(file_path).suffix.lower()
    if path_extension:
        return path_extension

    guessed, _ = mimetypes.guess_type(str(file_path))
    return MIME_TO_EXTENSION.get(guessed or "", "")


def _read_txt(file_path: str | Path) -> str:
    """Read plain text, supporting common Windows-encoded Russian documents."""
    path = Path(file_path)
    data = path.read_bytes()
    for encoding in ("utf-8-sig", "cp1251", "utf-16", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    # latin-1 decodes every byte, so this is only a defensive fallback.
    return data.decode("utf-8", errors="replace")


def _extract_docx(file_path: str | Path) -> str:
    try:
        from docx import Document
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError("Для чтения DOCX установите пакет python-docx") from exc

    document = Document(str(file_path))
    chunks = [paragraph.text for paragraph in document.paragraphs if paragraph.text]
    # Include table cells: many academic documents store their text in tables.
    for table in document.tables:
        for row in table.rows:
            for cell in row.cells:
                if cell.text:
                    chunks.append(cell.text)
    return "\n".join(chunks)


def _extract_pdf_text(file_path: str | Path) -> str:
    try:
        import pdfplumber
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError("Для чтения PDF установите пакет pdfplumber") from exc

    with pdfplumber.open(str(file_path)) as pdf:
        return "\n".join((page.extract_text() or "") for page in pdf.pages).strip()


def _ocr_pdf(file_path: str | Path) -> str:
    """OCR PDF pages; called only when pdfplumber yields almost no text."""
    try:
        import pdfplumber
        import pytesseract
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(
            "Для OCR PDF установите pdfplumber, pytesseract и Tesseract OCR"
        ) from exc

    # Use the project's configured OCR language when available.
    try:
        from app.config import settings
        ocr_language = settings.ocr_language
    except Exception:  # Keep the service usable in isolated tests.
        ocr_language = "rus+eng"

    page_text: list[str] = []
    with pdfplumber.open(str(file_path)) as pdf:
        for page in pdf.pages:
            image = page.to_image(resolution=300).original
            text = pytesseract.image_to_string(image, lang=ocr_language)
            if text.strip():
                page_text.append(text.strip())
    return "\n".join(page_text).strip()


def extract_text(
    file_path: str | Path,
    file_type: str | None = None,
) -> tuple[str, str | None]:
    """Extract text and detect its language for a material file.

    Args:
        file_path: Path to a file already downloaded from object storage.
        file_type: Optional MIME type or extension (e.g. 'application/pdf',
            '.pdf', or 'pdf'). If omitted, the path suffix is used.

    Returns:
        A pair (raw_text, language_code). Media files return ("", None).
        language_code is 'ru', 'en', or None when no language can be inferred.

    Raises:
        FileNotFoundError: If the supplied file does not exist.
        ValueError: If the file format is not supported.
        RuntimeError: If a required parser/OCR dependency is unavailable.
    """
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"Файл материала не найден: {path}")

    extension = _resolve_extension(path, file_type)

    # Images and videos are intentionally hash-only: never invoke OCR here.
    if extension in IMAGE_EXTENSIONS or extension in VIDEO_EXTENSIONS:
        return "", None

    if extension in PDF_EXTENSIONS:
        raw_text = _extract_pdf_text(path)
        if len(raw_text.strip()) < PDF_OCR_MIN_TEXT_CHARS:
            logger.info("PDF %s appears to be scanned; starting OCR", path.name)
            raw_text = _ocr_pdf(path)
    elif extension in WORD_EXTENSIONS:
        raw_text = _extract_docx(path)
    elif extension in TEXT_EXTENSIONS:
        raw_text = _read_txt(path)
    else:
        raise ValueError(f"Неподдерживаемый формат файла: {extension or file_type!r}")

    raw_text = raw_text.strip()
    return raw_text, detect_language(raw_text)


# Descriptive alias for callers that prefer an explicit service function name.
extract_text_from_file = extract_text
