"""Сервис S3-совместимого хранилища (MinIO для локальной разработки, boto3).

Возможности:
- ensure_buckets()            — создание бакетов при старте приложения;
- upload_fileobj / upload_bytes — стриминговая загрузка исходников материалов;
- upload_certificate_pdf      — загрузка PDF-свидетельств во второй бакет;
- build_object_key            — детерминированный ключ вида
                                 materials/{YYYY}/{MM}/{material_uuid}/{sha256[:16]}.{ext}
- download / presigned URL / delete / exists.

Клиент синхронный (boto3): используется как в FastAPI (через run_in_threadpool
или напрямую — операции небольшие), так и в Celery-воркерах.
"""

import io
from datetime import datetime, timezone
from functools import lru_cache
from typing import BinaryIO, Optional

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import ClientError

from app.config import Settings, get_settings

# Расширения по MIME (для человекочитаемых ключей в S3)
_MIME_EXT = {
    "application/pdf": "pdf",
    "application/msword": "doc",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "text/plain": "txt",
    "image/jpeg": "jpg",
    "image/png": "png",
    "video/mp4": "mp4",
    "video/quicktime": "mov",
    "video/x-msvideo": "avi",
    "video/x-matroska": "mkv",
}


def _sanitize_ext(filename: Optional[str], content_type: str) -> str:
    """Безопасное расширение: из имени файла (только [a-z0-9]{1,8}) или из MIME."""
    if filename and "." in filename:
        candidate = filename.rsplit(".", 1)[-1].lower()
        if candidate.isalnum() and len(candidate) <= 8:
            return candidate
    return _MIME_EXT.get(content_type, "bin")


class StorageService:
    """Тонкая обёртка над boto3 S3 с настройками приложения."""

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or get_settings()
        self._client = boto3.client(
            "s3",
            endpoint_url=self.settings.s3_endpoint_url,
            aws_access_key_id=self.settings.s3_access_key,
            aws_secret_access_key=self.settings.s3_secret_key,
            region_name=self.settings.s3_region,
            use_ssl=self.settings.s3_use_ssl,
            config=BotoConfig(signature_version="s3v4", retries={"max_attempts": 3}),
        )

    # ------------------------------ buckets -------------------------------- #
    @property
    def bucket_files(self) -> str:
        return self.settings.s3_bucket_files

    @property
    def bucket_certificates(self) -> str:
        return self.settings.s3_bucket_certificates

    def ensure_buckets(self) -> list[str]:
        """Создаёт недостающие бакеты (идемпотентно). Возвращает список созданных."""
        created: list[str] = []
        existing = {b["Name"] for b in self._client.list_buckets().get("Buckets", [])}
        for bucket in (self.bucket_files, self.bucket_certificates):
            if bucket not in existing:
                self._client.create_bucket(Bucket=bucket)
                created.append(bucket)
        return created

    # ------------------------------- keys ---------------------------------- #
    @staticmethod
    def build_object_key(
        *,
        material_id: str,
        sha256_hex: str,
        content_type: str,
        filename: Optional[str] = None,
        now: Optional[datetime] = None,
    ) -> str:
        """Детерминированный ключ объекта для материала.

        Пример: materials/2026/11/6f1c...-uuid/ab12cd34ef56ab78.pdf
        Префикс sha256 делает ключ уникальным по содержимому и упрощает аудит.
        """
        now = now or datetime.now(timezone.utc)
        ext = _sanitize_ext(filename, content_type)
        return (
            f"materials/{now:%Y/%m}/{material_id}/{sha256_hex[:16]}.{ext}"
        )

    @staticmethod
    def build_certificate_key(certificate_number: str) -> str:
        safe = "".join(ch for ch in certificate_number if ch.isalnum() or ch in "-_")
        return f"certificates/{safe}.pdf"

    # ------------------------------ uploads -------------------------------- #
    def upload_fileobj(
        self,
        fileobj: BinaryIO,
        *,
        key: str,
        content_type: str,
        bucket: Optional[str] = None,
    ) -> str:
        """Стриминговая загрузка file-like объекта; возвращает key.

        Гарантии корректности байтов (важно после хэширования потоковым
        SHA-256 — позиция потока может быть не в начале):
        - если поток ищущий — делаем seek(0);
        - Content-Length берём из фактического остатка потока (seek/tell),
          иначе boto3/s3transfer может недогрузить данные.
        """
        try:
            fileobj.seek(0)
            size = os.fstat(fileobj.fileno()).st_size if False else _remaining_size(fileobj)
            extra = {"ContentType": content_type}
            if size is not None:
                extra["ContentLength"] = size  # разрешён для put_object-вызовов s3transfer
            self._client.upload_fileobj(
                Fileobj=fileobj,
                Bucket=bucket or self.bucket_files,
                Key=key,
                ExtraArgs=extra,
            )
        except TypeError:
            # Some s3transfer versions reject ContentLength in multipart path:
            fileobj.seek(0)
            self._client.upload_fileobj(
                Fileobj=fileobj,
                Bucket=bucket or self.bucket_files,
                Key=key,
                ExtraArgs={"ContentType": content_type},
            )
        return key

    def upload_bytes(
        self,
        data: bytes,
        *,
        key: str,
        content_type: str,
        bucket: Optional[str] = None,
    ) -> str:
        return self.upload_fileobj(
            io.BytesIO(data), key=key, content_type=content_type, bucket=bucket
        )

    def upload_certificate_pdf(self, pdf_bytes: bytes, certificate_number: str) -> str:
        """Загрузка PDF-свидетельства; возвращает полный путь s3://bucket/key."""
        key = self.build_certificate_key(certificate_number)
        self.upload_bytes(
            pdf_bytes,
            key=key,
            content_type="application/pdf",
            bucket=self.bucket_certificates,
        )
        return f"s3://{self.bucket_certificates}/{key}"

    # ----------------------------- downloads ------------------------------- #
    def download_bytes(self, *, key: str, bucket: Optional[str] = None) -> bytes:
        buf = io.BytesIO()
        self._client.download_fileobj(bucket or self.bucket_files, key, buf)
        buf.seek(0)
        return buf.read()

    def presigned_get_url(
        self, *, key: str, bucket: Optional[str] = None, expiry_seconds: Optional[int] = None
    ) -> str:
        return self._client.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket or self.bucket_files, "Key": key},
            ExpiresIn=expiry_seconds
            or self.settings.s3_presigned_url_expiry_seconds,
        )

    def object_exists(self, *, key: str, bucket: Optional[str] = None) -> bool:
        try:
            self._client.head_object(Bucket=bucket or self.bucket_files, Key=key)
            return True
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "")
            if code in ("404", "NoSuchKey", "NotFound"):
                return False
            raise

    def delete_object(self, *, key: str, bucket: Optional[str] = None) -> None:
        self._client.delete_object(Bucket=bucket or self.bucket_files, Key=key)


@lru_cache
def get_storage_service() -> StorageService:
    """Синглтон сервиса (DI через Depends(get_storage_service) в FastAPI)."""
    return StorageService()
