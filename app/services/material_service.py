"""Бизнес-логика регистрации материала: загрузка -> SHA-256 -> проверка дубликата -> S3 -> БД.

Строгое соответствие бизнес-правилам ТЗ:

1. ТОЧНЫЙ ДУБЛИКАТ (совпадение SHA-256 с любым материалом реестра):
   - загрузка ОТКЛОНЯЕТСЯ (DuplicateMaterialError -> HTTP 409);
   - запись в materials НЕ создаётся; файл в S3 НЕ грузится;
   - в ответе — id, номер регистрации и заголовок существующего материала.
2. Повтор того же файла тем же автором блокируется так же (дубликат),
   версионность не реализуется.
3. Проверка идёт по всему реестру (не только по материалам автора) —
   sha256-индекс уникальности глобальный.
4. Размер файла ограничен MAX_FILE_SIZE (env), MIME — ALLOWED_MIME_TYPES.

Порядок операций важен: хэш и проверка дубля — ДО записи в S3 и ДО INSERT,
чтобы отклонённый дубликат не оставлял следов ни в хранилище, ни в БД.
"""

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4

from fastapi import UploadFile
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.core.exceptions import (
    DuplicateMaterialError,
    FileTooLargeError,
    UnsupportedFileTypeError,
)
from app.services.hashing_service import HashResult, compute_sha256_from_stream
from app.services.storage_service import StorageService

_HEX64_RE = re.compile(r"^[0-9a-f]{64}$")


@dataclass
class DuplicateInfo:
    """Данные найденного точного дубликата."""

    material_id: str
    registration_number: str
    title: str
    author_id: str
    created_at: Optional[str] = None


@dataclass
class RegistrationResult:
    """Результат успешной регистрации (для сериализации в схеме ответа)."""

    material_id: str
    registration_number: str
    sha256_hash: str
    file_s3_path: str
    file_type: str
    file_size_bytes: int
    title: str
    status: str = "on_moderation"
    processing_status: str = "pending"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# --------------------------------------------------------------------------- #
# Вспомогательные проверки
# --------------------------------------------------------------------------- #


def validate_upload(
    *, size_bytes: int, content_type: str, settings: Optional[Settings] = None
) -> None:
    """Проверки размера (MAX_FILE_SIZE) и MIME (ALLOWED_MIME_TYPES)."""
    s = settings or get_settings()
    if size_bytes <= 0:
        raise FileTooLargeError(size_bytes=0, max_bytes=s.max_file_size)  # пустой файл недопустим
    if size_bytes > s.max_file_size:
        raise FileTooLargeError(size_bytes=size_bytes, max_bytes=s.max_file_size)
    if content_type not in s.allowed_mime_types:
        raise UnsupportedFileTypeError(content_type=content_type, allowed=list(s.allowed_mime_types))


async def find_duplicate_by_sha256(session: AsyncSession, sha256_hex: str) -> Optional[DuplicateInfo]:
    """Поиск точного дубликата по SHA-256 (SQLAlchemy Core / текстовый SQL).

    Индекс по materials.sha256_hash делает запрос O(log N). Возвращает самого
    раннего зарегистрированного материала с таким хэшем.
    """
    stmt = text(
        """
        SELECT id                   AS material_id,
               registration_number,
               title,
               author_id            AS author_id,
               created_at
        FROM public.materials
        WHERE sha256_hash = :sha256
        ORDER BY created_at ASC
        LIMIT 1
        """
    )
    row = (await session.execute(stmt, {"sha256": sha256_hex})).mappings().first()
    if row is None:
        return None
    created_at = row["created_at"]
    return DuplicateInfo(
        material_id=str(row["material_id"]),
        registration_number=row["registration_number"],
        title=row["title"],
        author_id=str(row["author_id"]),
        created_at=created_at.isoformat() if isinstance(created_at, datetime) else None,
    )


async def generate_registration_number(session: AsyncSession) -> str:
    """Вызывает PL/pgSQL-функцию из схемы: RM-YYYY-NNNNNN (через sequence)."""
    value = (await session.execute(text("SELECT public.generate_registration_number()"))).scalar_one()
    return str(value)


# --------------------------------------------------------------------------- #
# Основной сервисный метод
# --------------------------------------------------------------------------- #


async def register_material(
    *,
    session: AsyncSession,
    storage: StorageService,
    upload: UploadFile,
    author_id: UUID | str,
    title: str,
    category: str,
    description: Optional[str] = None,
    tags: Optional[list[str]] = None,
    settings: Optional[Settings] = None,
) -> RegistrationResult:
    """Полный конвейер приёма материала (до постановки Celery-задачи на антиплагиат).

    Шаги:
      1. побайтовый стриминг хэширования (SHA-256) + фактический размер;
      2. валидации размера/MIME;
      3. поиск точного дубликата -> 409 (без записи в S3 и БД);
      4. загрузка файла в MinIO/S3;
      5. INSERT в materials (status=on_moderation, processing_status=pending)
         с номером из generate_registration_number();
      6. возврат результата (Celery-задачу публикует слой API/очередь).
    """
    s = settings or get_settings()

    # 1. Хэш + размер (стриминг, без хранения всего файла в памяти)
    hash_res: HashResult = compute_sha256_from_stream(upload.file)
    content_type = (upload.content_type or "application/octet-stream").split(";")[0].strip()

    # 2. Валидации
    validate_upload(size_bytes=hash_res.size_bytes, content_type=content_type, settings=s)

    # 3. Точный дубликат? -> HTTP 409, ничего не сохраняем (правила №1, №2)
    duplicate = await find_duplicate_by_sha256(session, hash_res.sha256)
    if duplicate is not None:
        raise DuplicateMaterialError(
            sha256_hash=hash_res.sha256,
            existing_material_id=duplicate.material_id,
            existing_registration_number=duplicate.registration_number,
            existing_title=duplicate.title,
            author_id=duplicate.author_id,
            created_at=duplicate.created_at,
        )

    # 4. Файл уникален -> загружаем в S3 (ключ детерминирован по uuid+hash)
    material_id = uuid4()
    object_key = storage.build_object_key(
        material_id=str(material_id),
        sha256_hex=hash_res.sha256,
        content_type=content_type,
        filename=upload.filename,
    )
    upload.file.seek(0)
    storage.upload_fileobj(
        upload.file,
        key=object_key,
        content_type=content_type,
    )

    # 5. INSERT записи materials (Core SQL — без ORM-запросов в бизнес-логике).
    #    tags — PG varchar[]; asyncpg принимает python-list, sqlite3 (только для
    #    тестов) требует строковый литерал массива — нормализуем по диалекту.
    dialect = session.bind.dialect.name if session.bind is not None else "postgresql"
    tags_list = [t[:50] for t in (tags or [])][:20]
    tags_param = (
        "{" + ",".join(t.replace('"', "").replace(",", "") for t in tags_list) + "}"
        if dialect == "sqlite"
        else tags_list
    )
    registration_number = await generate_registration_number(session)
    insert_stmt = text(
        """
        INSERT INTO public.materials (
            id, registration_number, author_id, title, description, category, tags,
            sha256_hash, file_s3_path, file_type, file_size_bytes,
            status, is_public, uniqueness_score, processing_status,
            is_duplicate, duplicate_of, created_at, updated_at
        ) VALUES (
            :id, :registration_number, :author_id, :title, :description, :category, :tags,
            :sha256_hash, :file_s3_path, :file_type, :file_size_bytes,
            'on_moderation', true, NULL, 'pending',
            false, NULL, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
        )
        """
    )
    await session.execute(
        insert_stmt,
        {
            "id": str(material_id),
            "registration_number": registration_number,
            "author_id": str(author_id),
            "title": title[:255],
            "description": description,
            "category": category[:100],
            "tags": tags_param,
            "sha256_hash": hash_res.sha256,
            "file_s3_path": f"s3://{storage.bucket_files}/{object_key}",
            "file_type": content_type,
            "file_size_bytes": hash_res.size_bytes,
        },
    )
    # Явный flush: вызывающий код (API-слой) публикует Celery-задачу только
    # после того, как строка гарантированно будет видна воркеру.
    await session.flush()

    return RegistrationResult(
        material_id=str(material_id),
        registration_number=registration_number,
        sha256_hash=hash_res.sha256,
        file_s3_path=f"s3://{storage.bucket_files}/{object_key}",
        file_type=content_type,
        file_size_bytes=hash_res.size_bytes,
        title=title,
    )


async def verify_hash_exists(session: AsyncSession, sha256_hex: str) -> Optional[DuplicateInfo]:
    """Публичная верификация «по хэшу загруженного файла» переиспользует тот же поиск.

    Ожидается нормализованная hex-строка; невалидный формат молча возвращает None.
    """
    if not _HEX64_RE.match((sha256_hex or "").lower()):
        return None
    return await find_duplicate_by_sha256(session, sha256_hex.lower())
