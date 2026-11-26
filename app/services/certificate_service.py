"""PDF certificate generation and registration service.

A certificate is issued only for a successfully processed material with a
calculated uniqueness score. The PDF is rendered with WeasyPrint and stored in
the configured S3-compatible certificates bucket.
"""
from __future__ import annotations

import html
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select

from app.models.enums import CertificateStatus, ProcessingStatus
from app.models.models import Certificate, Material
from app.services.storage_service import StorageService, get_storage_service

logger = logging.getLogger(__name__)


class CertificateGenerationError(RuntimeError):
    """Raised when a material cannot be issued a certificate."""


def _certificate_number(material_id: UUID, issued_at: datetime) -> str:
    """Create a stable, human-readable number unique for this material."""
    return f"CERT-{issued_at:%Y}-{str(material_id).replace('-', '').upper()[:12]}"


def _safe(value: Any, fallback: str = "Не указано") -> str:
    if value is None or value == "":
        value = fallback
    return html.escape(str(value))


def _render_certificate_pdf(
    *,
    certificate_number: str,
    registration_number: str,
    title: str,
    author_name: str,
    author_email: str,
    category: str,
    sha256_hash: str,
    uniqueness_score: float,
    issued_at: datetime,
) -> bytes:
    """Render a self-contained A4 PDF document using WeasyPrint."""
    try:
        import os

        gtk_bin = r"C:\msys64\ucrt64\bin"
        if os.path.isdir(gtk_bin):
            os.add_dll_directory(gtk_bin)

        from weasyprint import HTML
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise CertificateGenerationError(
            "Для генерации PDF установите зависимость weasyprint"
        ) from exc

    issued_label = issued_at.astimezone(timezone.utc).strftime("%d.%m.%Y %H:%M UTC")
    score_label = f"{uniqueness_score:.2f}".replace(".", ",")
    escaped_hash = _safe(sha256_hash)

    document = f"""<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<title>Свидетельство { _safe(certificate_number) }</title>
<style>
  @page {{ size: A4; margin: 18mm; }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; color: #172033; font-family: "DejaVu Sans", sans-serif;
    font-size: 11pt; line-height: 1.55;
  }}
  .frame {{ border: 2px solid #263b60; min-height: 255mm; padding: 15mm 13mm; }}
  .inner {{ border: 1px solid #a9b6c9; min-height: 222mm; padding: 12mm 10mm; }}
  .eyebrow {{ text-align: center; text-transform: uppercase; letter-spacing: 2px;
    color: #536783; font-size: 9pt; }}
  h1 {{ margin: 8mm 0 2mm; text-align: center; font-size: 25pt; color: #20395f; }}
  .subtitle {{ text-align: center; color: #536783; margin-bottom: 12mm; }}
  .lead {{ text-align: center; font-size: 12pt; margin: 0 3mm 9mm; }}
  .material-title {{ text-align: center; font-size: 18pt; font-weight: bold;
    color: #20395f; margin: 8mm 0; }}
  .details {{ width: 100%; border-collapse: collapse; margin-top: 8mm; }}
  .details td {{ border-bottom: 1px solid #dce2eb; padding: 3mm 2mm; vertical-align: top; }}
  .details td:first-child {{ width: 38%; color: #536783; }}
  .score {{ margin: 9mm auto; padding: 5mm; border: 1px solid #9eafc7;
    text-align: center; width: 65%; }}
  .score strong {{ display: block; font-size: 27pt; color: #20395f; }}
  .foot {{ margin-top: 11mm; font-size: 8pt; color: #64748b; overflow-wrap: anywhere; }}
  .number {{ text-align: center; margin-top: 7mm; font-weight: bold; }}
  .seal {{ text-align: center; margin-top: 12mm; color: #536783; font-size: 9pt; }}
</style>
</head>
<body>
<div class="frame"><div class="inner">
  <div class="eyebrow">Внутренний реестр авторских материалов</div>
  <h1>СВИДЕТЕЛЬСТВО</h1>
  <div class="subtitle">о регистрации авторского материала</div>
  <p class="lead">Настоящим подтверждается, что в реестре зарегистрирован следующий материал:</p>
  <div class="material-title">{_safe(title)}</div>
  <p class="lead">Сведения об авторе и зарегистрированном материале:</p>
  <table class="details">
    <tr><td>Автор</td><td>{_safe(author_name)}</td></tr>
    <tr><td>Электронная почта</td><td>{_safe(author_email)}</td></tr>
    <tr><td>Категория</td><td>{_safe(category)}</td></tr>
    <tr><td>Регистрационный номер</td><td>{_safe(registration_number)}</td></tr>
    <tr><td>Дата выдачи</td><td>{_safe(issued_label)}</td></tr>
  </table>
  <div class="score">
    <span>Показатель уникальности на момент проверки</span>
    <strong>{_safe(score_label)}%</strong>
  </div>
  <div class="number">Номер свидетельства: {_safe(certificate_number)}</div>
  <div class="foot">
    <strong>Контрольная сумма SHA-256 исходного файла:</strong><br>
    {escaped_hash}
  </div>
  <div class="seal">Документ сформирован информационной системой автоматически.</div>
</div></div>
</body>
</html>"""

    try:
        return HTML(string=document).write_pdf()
    except Exception as exc:
        logger.exception("Could not render certificate PDF")
        raise CertificateGenerationError(
            f"Не удалось сформировать PDF-свидетельство: {exc}"
        ) from exc


def generate_certificate(
    session,
    material_id: UUID | str,
    *,
    storage: StorageService | None = None,
) -> Certificate:
    """Generate, upload and persist a certificate for a processed material.

    The caller owns the SQLAlchemy transaction (e.g. get_sync_session()).
    Existing valid certificates are returned unchanged, making this operation
    idempotent for a given material_id.

    Raises:
        CertificateGenerationError: material is missing/not ready or PDF
            generation/upload fails.
    """
    try:
        material_uuid = UUID(str(material_id))
    except (TypeError, ValueError) as exc:
        raise CertificateGenerationError(
            f"Некорректный material_id: {material_id!r}"
        ) from exc

    # Lock the material row to reduce concurrent issuance races.
    material = session.scalar(
        select(Material)
        .where(Material.id == material_uuid)
        .with_for_update(of=Material)
    )
    if material is None:
        raise CertificateGenerationError(f"Материал {material_uuid} не найден")

    existing = session.scalar(
        select(Certificate).where(Certificate.material_id == material_uuid)
    )
    if existing is not None:
        if existing.status == CertificateStatus.valid:
            return existing
        raise CertificateGenerationError(
            "Для материала уже существует отозванное свидетельство; "
            "повторная выдача требует отдельной процедуры"
        )

    if material.processing_status != ProcessingStatus.completed:
        raise CertificateGenerationError(
            "Свидетельство можно выдать только после успешной обработки материала"
        )
    if material.uniqueness_score is None:
        raise CertificateGenerationError(
            "У материала ещё не рассчитан показатель уникальности"
        )

    issued_at = datetime.now(timezone.utc)
    certificate_number = _certificate_number(material_uuid, issued_at)
    author = material.author
    author_name = getattr(author, "username", None) or "Автор реестра"
    author_email = getattr(author, "email", None) or ""

    pdf_bytes = _render_certificate_pdf(
        certificate_number=certificate_number,
        registration_number=material.registration_number,
        title=material.title,
        author_name=author_name,
        author_email=author_email,
        category=material.category,
        sha256_hash=material.sha256_hash,
        uniqueness_score=float(material.uniqueness_score),
        issued_at=issued_at,
    )

    storage_service = storage or get_storage_service()
    s3_path = storage_service.upload_certificate_pdf(pdf_bytes, certificate_number)

    certificate_data = {
        "material_id": str(material_uuid),
        "registration_number": material.registration_number,
        "title": material.title,
        "author_id": str(material.author_id),
        "author_name": author_name,
        "author_email": author_email,
        "sha256_hash": material.sha256_hash,
        "uniqueness_score": float(material.uniqueness_score),
        "issued_at": issued_at.isoformat(),
        "file_format": "PDF",
    }
    certificate = Certificate(
        material_id=material_uuid,
        certificate_number=certificate_number,
        pdf_s3_path=s3_path,
        status=CertificateStatus.valid,
        certificate_data=certificate_data,
        issued_at=issued_at,
    )
    session.add(certificate)
    try:
        session.flush()
    except Exception:
        # If the DB insert fails, remove the uploaded object to avoid an orphan.
        try:
            key = storage_service.build_certificate_key(certificate_number)
            storage_service.delete_object(
                key=key, bucket=storage_service.bucket_certificates
            )
        except Exception:
            logger.exception("Failed to clean up orphaned certificate object %s", s3_path)
        raise

    logger.info(
        "Issued certificate %s for material %s",
        certificate_number,
        material_uuid,
    )
    return certificate


def generate_certificate_pdf(
    session,
    material_id: UUID | str,
    *,
    storage: StorageService | None = None,
) -> Certificate:
    """Backward-friendly explicit alias for generate_certificate()."""
    return generate_certificate(session, material_id, storage=storage)
