from tests.pdf_fixtures import make_valid_pdf
import io
import zipfile

import pytest
from PIL import Image

from app.core.exceptions import ValidationAppError
from app.services.file_validation_service import (
    validate_file_content,
    validate_metadata,
)


DOCX_MIME = (
    "application/vnd.openxmlformats-officedocument."
    "wordprocessingml.document"
)


def make_docx():
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("word/document.xml", "<document/>")
    stream.seek(0)
    return stream


def make_image(format_name):
    stream = io.BytesIO()
    Image.new("RGB", (10, 10)).save(stream, format=format_name)
    stream.seek(0)
    return stream


def test_metadata_valid():
    validate_metadata(
        title="Тестовый материал",
        category="Наука",
        description="Описание",
        tags=["тест", "наука"],
    )


@pytest.mark.parametrize(
    "kwargs",
    [
        {"title": " ", "category": "Наука"},
        {"title": "x" * 256, "category": "Наука"},
        {"title": "Название", "category": " "},
        {"title": "Название", "category": "x" * 101},
    ],
)
def test_metadata_invalid(kwargs):
    values = {
        "title": "Название",
        "category": "Наука",
        "description": None,
        "tags": None,
    }
    values.update(kwargs)

    with pytest.raises(ValidationAppError):
        validate_metadata(**values)


def test_metadata_rejects_too_many_tags():
    with pytest.raises(ValidationAppError):
        validate_metadata(
            title="Название",
            category="Наука",
            description=None,
            tags=[f"tag{i}" for i in range(21)],
        )


@pytest.mark.parametrize(
    "payload",
    [
        "Обычный русский текст".encode("utf-8"),
        "Обычный русский текст".encode("cp1251"),
    ],
)
def test_txt_valid(payload):
    validate_file_content(
        stream=io.BytesIO(payload),
        content_type="text/plain",
    )


def test_txt_rejects_binary():
    with pytest.raises(ValidationAppError):
        validate_file_content(
            stream=io.BytesIO(b"\x00\x01\x02\x03"),
            content_type="text/plain",
        )


def test_pdf_valid_header():
    validate_file_content(
        stream=io.BytesIO(make_valid_pdf()),
        content_type="application/pdf",
    )


def test_pdf_rejects_wrong_signature():
    with pytest.raises(ValidationAppError):
        validate_file_content(
            stream=io.BytesIO(b"NOT A PDF"),
            content_type="application/pdf",
        )


def test_docx_valid_structure():
    validate_file_content(
        stream=make_docx(),
        content_type=DOCX_MIME,
    )


def test_docx_rejects_invalid_zip():
    with pytest.raises(ValidationAppError):
        validate_file_content(
            stream=io.BytesIO(b"not a zip"),
            content_type=DOCX_MIME,
        )


@pytest.mark.parametrize(
    "format_name,mime",
    [
        ("JPEG", "image/jpeg"),
        ("PNG", "image/png"),
    ],
)
def test_image_valid(format_name, mime):
    validate_file_content(
        stream=make_image(format_name),
        content_type=mime,
    )


def test_image_rejects_corrupted_content():
    with pytest.raises(ValidationAppError):
        validate_file_content(
            stream=io.BytesIO(b"\xff\xd8\xff corrupted image"),
            content_type="image/jpeg",
        )


@pytest.mark.parametrize(
    "mime,payload",
    [
        ("video/mp4", b"\x00\x00\x00\x18ftypisom"),
        ("video/quicktime", b"\x00\x00\x00\x18ftypqt  "),
        ("video/x-msvideo", b"RIFF\x00\x00\x00\x00AVI "),
        ("video/x-matroska", b"\x1a\x45\xdf\xa3" + b"\x00" * 12),
    ],
)
def test_video_container_signatures(mime, payload):
    validate_file_content(
        stream=io.BytesIO(payload),
        content_type=mime,
    )


def test_mp4_rejects_wrong_signature():
    with pytest.raises(ValidationAppError):
        validate_file_content(
            stream=io.BytesIO(b"not a video"),
            content_type="video/mp4",
        )
