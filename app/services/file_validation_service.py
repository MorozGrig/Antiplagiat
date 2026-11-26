
from __future__ import annotations

import io
import pdfplumber
import zipfile
from pathlib import Path

from PIL import Image

from app.config import Settings, get_settings
from app.core.exceptions import ValidationAppError


MIME_SIGNATURES = {
    "application/pdf": (b"%PDF-",),
    "image/jpeg": (b"\xff\xd8\xff",),
    "image/png": (b"\x89PNG\r\n\x1a\n",),
    "video/x-msvideo": (b"RIFF",),
    "video/x-matroska": (b"\x1a\x45\xdf\xa3",),
}

MIME_EXTENSIONS = {
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


def _invalid(message: str) -> None:
    raise ValidationAppError(message)


def validate_metadata(
    *,
    title: str,
    category: str,
    description: str | None,
    tags: list[str] | None,
) -> None:
    if not title or not title.strip() or len(title.strip()) > 255:
        _invalid("Название должно содержать от 1 до 255 символов.")

    if not category or not category.strip() or len(category.strip()) > 100:
        _invalid("Категория должна содержать от 1 до 100 символов.")

    if description is not None and len(description) > 10000:
        _invalid("Описание не должно превышать 10000 символов.")

    if tags is not None:
        if len(tags) > 20:
            _invalid("Допускается не более 20 тегов.")

        for tag in tags:
            if not tag or not tag.strip() or len(tag.strip()) > 50:
                _invalid("Каждый тег должен содержать от 1 до 50 символов.")


def validate_file_content(
    *,
    stream,
    content_type: str,
    settings: Settings | None = None,
) -> None:
    s = settings or get_settings()

    if content_type not in s.allowed_mime_types:
        _invalid("Тип файла не поддерживается.")

    try:
        stream.seek(0)
        header = stream.read(32)
        stream.seek(0)
    except (AttributeError, OSError, ValueError) as exc:
        raise ValidationAppError("Не удалось прочитать файл.") from exc

    signatures = MIME_SIGNATURES.get(content_type)

    if signatures and not any(header.startswith(sig) for sig in signatures):
        _invalid("Содержимое файла не соответствует заявленному формату.")
    if content_type == "application/pdf":
        try:
            stream.seek(0)
            with pdfplumber.open(stream) as pdf:
                if not pdf.pages:
                    _invalid("PDF не содержит страниц.")
        except ValidationAppError:
            raise
        except Exception as exc:
            raise ValidationAppError(
                "Файл не является корректным PDF-документом."
            ) from exc
        finally:
            stream.seek(0)

    if content_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        try:
            with zipfile.ZipFile(stream) as archive:
                names = set(archive.namelist())
                if "word/document.xml" not in names:
                    _invalid("DOCX не содержит основного документа.")
                if "[Content_Types].xml" not in names:
                    _invalid("Некорректная структура DOCX.")
        except (zipfile.BadZipFile, OSError):
            _invalid("Файл не является корректным DOCX.")
        finally:
            stream.seek(0)

    elif content_type == "text/plain":
        try:
            stream.seek(0)
            data = stream.read()
            if b"\x00" in data:
                _invalid("Текстовый файл содержит недопустимые нулевые байты.")
            for encoding in ("utf-8-sig", "cp1251", "utf-16"):
                try:
                    data.decode(encoding)
                    break
                except UnicodeDecodeError:
                    continue
            else:
                _invalid("Не удалось определить кодировку текстового файла.")
        finally:
            stream.seek(0)

    elif content_type in ("image/jpeg", "image/png"):
        try:
            stream.seek(0)
            with Image.open(stream) as image:
                image.verify()
        except Exception as exc:
            raise ValidationAppError("Повреждённый файл изображения.") from exc
        finally:
            stream.seek(0)

    elif content_type in ("video/mp4", "video/quicktime"):
        # ISO Base Media File Format: the ftyp box starts at byte offset 4.
        if len(header) < 12 or header[4:8] != b"ftyp":
            _invalid("Файл не имеет корректной структуры MP4/MOV.")

    elif content_type == "video/x-msvideo":
        if len(header) < 12 or header[8:12] != b"AVI ":
            _invalid("Файл не имеет корректной структуры AVI.")

    elif content_type == "video/x-matroska":
        if not header.startswith(b"\x1a\x45\xdf\xa3"):
            _invalid("Файл не имеет корректной структуры MKV.")
