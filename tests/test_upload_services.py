"""Тесты сервиса загрузки/хэширования/проверки дубликатов.

- hashing_service и material_service проверяются на in-memory SQLite
  (текстовый SQL совместим; специфичные PG-функции не используются в тесте);
- S3 мокируется через moto (MinIO-совместимый интерфейс boto3).
"""

import io
from datetime import datetime, timezone
from uuid import uuid4

import pytest
import pytest_asyncio
from fastapi import UploadFile
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.exceptions import DuplicateMaterialError, FileTooLargeError, UnsupportedFileTypeError
from app.services.hashing_service import compute_sha256_from_bytes, compute_sha256_from_stream
from app.services.material_service import register_material, validate_upload, verify_hash_exists

# SQLite не поддерживает PG-массивы: в тестовой таблице колонка tags есть,
# но bind-параметр ARRAY сериализуется в JSON-строку простымListAdapter.
def _array_adapter(value):  # pragma: no cover - адаптер диалекта
    if value is None:
        return None
    import json as _json
    return _json.dumps(list(value))


# --------------------------------------------------------------------------- #
# Хэширование
# --------------------------------------------------------------------------- #

def test_sha256_stream_matches_hashlib():
    data = b"hello registry" * 1000
    expected = compute_sha256_from_bytes(data)
    got = compute_sha256_from_stream(io.BytesIO(data))
    assert got.sha256 == expected.sha256
    assert len(got.sha256) == 64
    assert got.size_bytes == len(data)


def test_sha256_stream_rewinds_for_next_consumer():
    """После хэширования поток готов к загрузке в S3 (seek(0))."""
    data = b"x" * 100_000
    stream = io.BytesIO(data)
    compute_sha256_from_stream(stream)
    assert stream.read() == data


# --------------------------------------------------------------------------- #
# Валидации (MAX_FILE_SIZE / MIME)
# --------------------------------------------------------------------------- #

class _S:
    max_file_size = 10 * 1024 * 1024
    allowed_mime_types = ["application/pdf", "video/mp4"]


def test_validate_too_large():
    with pytest.raises(FileTooLargeError):
        validate_upload(size_bytes=_S.max_file_size + 1, content_type="application/pdf", settings=_S())


def test_validate_bad_mime():
    with pytest.raises(UnsupportedFileTypeError):
        validate_upload(size_bytes=10, content_type="application/x-msdownload", settings=_S())


def test_validate_ok():
    validate_upload(size_bytes=10, content_type="application/pdf", settings=_S())


# --------------------------------------------------------------------------- #
# Регистрация + дубликаты (SQLite)
# --------------------------------------------------------------------------- #

@pytest_asyncio.fixture
async def session():
    """SQLite-сессия с ATTACH схемы `public` (как в PostgreSQL) + заглушкой
    generate_registration_number(). Продакшн-SQL (`public.materials`,
    `now()`) выполняется без упрощений.
    """
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as s:
        await s.execute(text("ATTACH DATABASE ':memory:' AS public"))
        await s.execute(text(
            """
            CREATE TABLE public.materials (
                id TEXT PRIMARY KEY,
                registration_number TEXT UNIQUE NOT NULL,
                author_id TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                category TEXT NOT NULL,
                tags TEXT,
                sha256_hash TEXT NOT NULL,
                file_s3_path TEXT NOT NULL,
                file_type TEXT NOT NULL,
                file_size_bytes INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'on_moderation',
                is_public INTEGER NOT NULL DEFAULT 1,
                uniqueness_score REAL,
                processing_status TEXT NOT NULL DEFAULT 'pending',
                is_duplicate INTEGER NOT NULL DEFAULT 0,
                duplicate_of TEXT,
                created_at TIMESTAMP NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        ))
        # Заглушка PL/pgSQL-функции из схемы БД: в SQLite детерминированный
        # номер эмулируется на python-уровне (monkeypatch ниже).
        yield s
    await engine.dispose()


@pytest.fixture(autouse=True)
def _stub_pg_number_function(monkeypatch):
    """Подменяем вызов generate_registration_number() для тестов на SQLite."""
    counter = {"n": 0}

    async def fake_gen(session):
        counter["n"] += 1
        return f"RM-2026-{counter['n']:06d}"

    monkeypatch.setattr(
        "app.services.material_service.generate_registration_number", fake_gen
    )


class FakeStorage:
    bucket_files = "materials"

    def __init__(self):
        self.uploaded: dict[str, bytes] = {}

    @staticmethod
    def build_object_key(*, material_id, sha256_hex, content_type, filename=None, now=None):
        return f"materials/{material_id}/{sha256_hex[:16]}.pdf"

    def upload_fileobj(self, fileobj, *, key, content_type, content_length=None, bucket=None):
        self.uploaded[key] = fileobj.read()
        return key


def _upload(data: bytes, name: str = "doc.pdf", mime: str = "application/pdf") -> UploadFile:
    return UploadFile(filename=name, file=io.BytesIO(data), headers={"content-type": mime})


@pytest.mark.asyncio
async def test_register_success_and_duplicate_rejected(session, monkeypatch):
    # заглушка PG-функции генерации номера
    async def fake_gen(s):
        return f"RM-2026-{uuid4().int % 10**6:06d}"
    monkeypatch.setattr("app.services.material_service.generate_registration_number", fake_gen)

    storage = FakeStorage()
    payload = b"%PDF-1.4 fake content"

    result = await register_material(
        session=session, storage=storage, upload=_upload(payload),
        author_id=str(uuid4()), title="Моя статья", category="articles",
    )
    await session.commit()

    assert result.sha256_hash == compute_sha256_from_bytes(payload).sha256
    assert len(storage.uploaded) == 1  # файл загружен в S3

    rows = (await session.execute(text("SELECT COUNT(*) FROM materials"))).scalar()
    assert rows == 1

    # --- повтор того же файла (тот же автор) -> 409, БД/S3 не изменились ----
    second_author = str(uuid4())
    with pytest.raises(DuplicateMaterialError) as exc_info:
        await register_material(
            session=session, storage=storage, upload=_upload(payload),
            author_id=second_author, title="Копия", category="articles",
        )
    err = exc_info.value
    assert err.status_code == 409
    assert err.existing_material_id == result.material_id
    assert err.existing_registration_number == result.registration_number
    assert err.details["existing_material"]["title"] == "Моя статья"

    rows_after = (await session.execute(text("SELECT COUNT(*) FROM materials"))).scalar()
    assert rows_after == 1          # запись НЕ создана
    assert len(storage.uploaded) == 1  # второй файл в S3 НЕ грузился

    # публичная верификация по хэшу находит материал
    info = await verify_hash_exists(session, result.sha256_hash.upper())
    assert info and info.material_id == result.material_id


@pytest.mark.asyncio
async def test_empty_file_rejected(session):
    with pytest.raises(FileTooLargeError):
        await register_material(
            session=session, storage=FakeStorage(), upload=_upload(b""),
            author_id=str(uuid4()), title="t", category="c",
        )
