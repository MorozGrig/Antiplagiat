"""Доменные исключения приложения + обработчики для FastAPI.

Бизнес-правило №1 (ТЗ): точный дубликат по SHA-256 -> загрузка ОТКЛОНЯЕТСЯ,
запись в БД НЕ создаётся, HTTP 409 с указанием на существующий материал.
"""

from typing import Any, Optional

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse


class AppError(Exception):
    """Базовое доменное исключение."""

    status_code: int = status.HTTP_400_BAD_REQUEST
    error_code: str = "app_error"

    def __init__(self, message: str, *, details: Optional[dict[str, Any]] = None) -> None:
        self.message = message
        self.details = details or {}
        super().__init__(message)

    def to_payload(self) -> dict[str, Any]:
        return {
            "error": self.error_code,
            "message": self.message,
            "details": self.details,
        }


class ValidationAppError(AppError):
    """Некорректные входные данные (размер, MIME и т.п.)."""

    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    error_code = "validation_error"


class FileTooLargeError(ValidationAppError):
    """Файл превышает MAX_FILE_SIZE (настраивается через env)."""

    error_code = "file_too_large"

    def __init__(self, size_bytes: int, max_bytes: int) -> None:
        super().__init__(
            f"Размер файла {size_bytes} байт превышает максимально допустимый {max_bytes} байт.",
            details={"file_size_bytes": size_bytes, "max_file_size_bytes": max_bytes},
        )


class UnsupportedFileTypeError(ValidationAppError):
    """MIME-тип не входит в ALLOWED_MIME_TYPES."""

    error_code = "unsupported_file_type"

    def __init__(self, content_type: str, allowed: list[str]) -> None:
        super().__init__(
            f"Тип файла '{content_type}' не поддерживается.",
            details={"content_type": content_type, "allowed_mime_types": allowed},
        )


class DuplicateMaterialError(AppError):
    """HTTP 409: найден точный дубликат по SHA-256 (бизнес-правила №1/№2)."""

    status_code = status.HTTP_409_CONFLICT
    error_code = "duplicate_material"

    def __init__(
        self,
        *,
        sha256_hash: str,
        existing_material_id: str,
        existing_registration_number: str,
        existing_title: str,
        author_id: str,
        created_at: Optional[str] = None,
    ) -> None:
        super().__init__(
            "Материал с таким SHA-256 уже зарегистрирован в реестре. Загрузка отклонена.",
            details={
                "sha256_hash": sha256_hash,
                "existing_material": {
                    "id": existing_material_id,
                    "registration_number": existing_registration_number,
                    "title": existing_title,
                    "author_id": author_id,
                    "created_at": created_at,
                },
            },
        )
        self.existing_material_id = existing_material_id
        self.existing_registration_number = existing_registration_number


class NotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    error_code = "not_found"


# --------------------------------------------------------------------------- #
# Регистрация обработчиков в FastAPI
# --------------------------------------------------------------------------- #


def register_exception_handlers(app: FastAPI) -> None:
    """Подключает обработчики доменных исключений к приложению."""

    @app.exception_handler(AppError)
    async def _app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content=exc.to_payload())
