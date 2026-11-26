"""Расчёт SHA-256 материала.

Хэш считается поблочно (стриминг), поэтому файл целиком никогда
не держится в памяти — важно для лимита MAX_FILE_SIZE и будущих стримов.

Ключевые свойства (под бизнес-правила ТЗ):
- Хэш считается над СЫРЫМИ байтами файла (до любых конвертаций),
  поэтому повторная загрузка того же файла тем же автором даёт тот же
  хэш и блокируется как дубликат (правила №1, №2).
- Для видео SHA-256 — единственный метод проверки (правило №3).
"""

import hashlib
from dataclasses import dataclass

DEFAULT_CHUNK_SIZE = 64 * 1024  # 64 KiB


@dataclass(frozen=True)
class HashResult:
    sha256: str          # hex-строка длиной 64 символа (char(64) в БД)
    size_bytes: int      # фактический размер содержимого


def compute_sha256_from_bytes(data: bytes) -> HashResult:
    """SHA-256 для небольших буферов в памяти (тесты, unit-логика)."""
    return HashResult(sha256=hashlib.sha256(data).hexdigest(), size_bytes=len(data))


def compute_sha256_from_stream(
    stream,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    max_bytes: int | None = None,
) -> HashResult:
    """Вычисляет SHA-256 потоково, при необходимости ограничивая размер."""
    hasher = hashlib.sha256()
    total = 0

    try:
        stream.seek(0)
    except (OSError, ValueError):
        pass

    try:
        while True:
            read_size = chunk_size

            if max_bytes is not None:
                remaining = max_bytes - total
                read_size = min(chunk_size, remaining + 1)

            chunk = stream.read(read_size)

            if not chunk:
                break

            if isinstance(chunk, str):
                chunk = chunk.encode("utf-8")

            total += len(chunk)

            if max_bytes is not None and total > max_bytes:
                raise ValueError(
                    f"File exceeds the maximum allowed size of {max_bytes} bytes"
                )

            hasher.update(chunk)

    finally:
        try:
            stream.seek(0)
        except (OSError, ValueError):
            pass

    return HashResult(
        sha256=hasher.hexdigest(),
        size_bytes=total,
    )


def compute_sha256_from_path(path: str) -> HashResult:
    """SHA-256 файла на диске (Celery-воркеры, миграционные скрипты)."""
    with open(path, "rb") as fh:
        return compute_sha256_from_stream(fh)
