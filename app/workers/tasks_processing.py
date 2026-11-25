"""Celery pipeline for processing a registered material.

The normalization and similarity modules are imported lazily so this task module
can be imported independently while the remaining iteration-4 services are
being added. Their expected public interfaces are documented at the call sites.
"""
from __future__ import annotations

import logging
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from uuid import UUID

from celery import shared_task
from sqlalchemy import delete, select

from app.db.database import get_sync_session
from app.models.enums import ProcessingStatus
from app.models.models import (
    Material,
    MaterialHash,
    MaterialTextContent,
    ProcessingLog,
    SimilarityCheck,
)
from app.services.extraction import extract_text
from app.services.storage_service import StorageService

logger = logging.getLogger(__name__)


def _parse_s3_path(s3_path: str) -> tuple[str, str]:
    """Parse s3://bucket/key into a bucket and object key."""
    parsed = urlparse(s3_path)
    if parsed.scheme != "s3" or not parsed.netloc or not parsed.path.lstrip("/"):
        raise ValueError(f"Некорректный S3-путь материала: {s3_path!r}")
    return parsed.netloc, parsed.path.lstrip("/")


def _extension_for_file_type(file_type: str) -> str:
    """Derive a useful suffix for parsers from MIME type or extension."""
    value = (file_type or "").lower().strip()
    mime_extensions = {
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
    if value in mime_extensions:
        return mime_extensions[value]
    suffix = Path(value).suffix.lower()
    if suffix:
        return suffix
    if value and "/" not in value:
        return f".{value.lstrip('.')}"
    return ".bin"


def _write_log(
    session,
    material_id: UUID,
    step: str,
    status: str,
    *,
    details: dict[str, Any] | None = None,
    error_message: str | None = None,
) -> None:
    session.add(
        ProcessingLog(
            material_id=material_id,
            step=step,
            status=status,
            details=details,
            error_message=error_message,
            completed_at=(None if status == "started" else datetime.now(timezone.utc)),
        )
    )
    session.flush()


def _upsert_text_content(
    session,
    material_id: UUID,
    *,
    raw_text: str,
    normalized_text: str,
    language_code: str | None,
    word_count: int,
) -> None:
    row = session.get(MaterialTextContent, material_id)
    if row is None:
        row = MaterialTextContent(
            material_id=material_id,
            raw_text=raw_text,
            normalized_text=normalized_text,
            language_code=language_code,
            word_count=word_count,
        )
        session.add(row)
    else:
        row.raw_text = raw_text
        row.normalized_text = normalized_text
        row.language_code = language_code
        row.word_count = word_count
    session.flush()


def _upsert_hash(
    session, material_id: UUID, signature: list[int], simhash_value: int | None = None
) -> None:
    row = session.get(MaterialHash, material_id)
    if row is None:
        row = MaterialHash(
            material_id=material_id,
            minhash_signature=signature,
            simhash_value=simhash_value,
        )
        session.add(row)
    else:
        row.minhash_signature = signature
        row.simhash_value = simhash_value
    session.flush()


@shared_task(
    name="app.workers.tasks_processing.process_material",
    bind=True,
    autoretry_for=(),
)
def process_material(self, material_id: str) -> dict[str, Any]:
    """Run the full asynchronous processing pipeline for one material.

    Expected interfaces for the next iteration modules:
      * text_normalization.normalize_text(text, language_code) ->
        (normalized_text, word_count)
      * similarity.build_minhash_signature(normalized_text) -> list[int]
      * similarity.find_similar_materials(session, material_id,
        normalized_text, minhash_signature) -> list[dict] with
        matched_material_id, similarity_percentage, check_method and optional
        matching_fragments.

    The task returns a small serializable status object for Celery callers.
    """
    try:
        material_uuid = UUID(str(material_id))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Некорректный material_id: {material_id!r}") from exc

    with get_sync_session() as session:
        material = session.scalar(
            select(Material).where(Material.id == material_uuid).with_for_update()
        )
        if material is None:
            raise ValueError(f"Материал {material_id} не найден")

        material.processing_status = ProcessingStatus.processing
        session.flush()
        _write_log(session, material_uuid, "pipeline", "started")

        current_step = "extraction"
        try:
            # Step 1: fetch source object and extract text.
            bucket, object_key = _parse_s3_path(material.file_s3_path)
            storage = StorageService()
            file_bytes = storage.download_bytes(key=object_key, bucket=bucket)
            suffix = _extension_for_file_type(material.file_type)

            with tempfile.NamedTemporaryFile(suffix=suffix) as temp_file:
                temp_file.write(file_bytes)
                temp_file.flush()
                raw_text, language_code = extract_text(
                    temp_file.name, material.file_type
                )

            is_media_only = not raw_text.strip()
            _write_log(
                session,
                material_uuid,
                "extraction",
                "completed",
                details={
                    "raw_text_length": len(raw_text),
                    "language_code": language_code,
                    "text_extracted": bool(raw_text.strip()),
                },
            )

            current_step = "normalization"
            # Step 2: normalize text. Media without extractable text remain
            # hash-only and are assigned 100% uniqueness (unless exact dupes
            # were rejected at registration time).
            if is_media_only:
                normalized_text, word_count = "", 0
            else:
                from app.services.text_normalization import normalize_text

                normalized_text, word_count = normalize_text(raw_text, language_code)

            _upsert_text_content(
                session,
                material_uuid,
                raw_text=raw_text,
                normalized_text=normalized_text,
                language_code=language_code,
                word_count=word_count,
            )
            _write_log(
                session,
                material_uuid,
                "normalization",
                "completed",
                details={"word_count": word_count},
            )

            # Keep the MLT index synchronized. Elasticsearch is optional and
            # its helper deliberately degrades to False on service outages.
            from app.services.similarity import index_material_text
            index_material_text(
                material_id=material_uuid,
                normalized_text=normalized_text,
            )

            current_step = "minhash"
            # Step 3: MinHash signature (empty for image/video or empty text).
            if normalized_text.strip():
                from app.services.similarity import build_minhash_signature

                signature = build_minhash_signature(normalized_text)
            else:
                signature = []
            _upsert_hash(session, material_uuid, signature)
            _write_log(
                session,
                material_uuid,
                "minhash",
                "completed",
                details={"signature_length": len(signature)},
            )

            current_step = "similarity"
            # Step 4: similarity lookup. No text means no text-based matching.
            matches: list[dict[str, Any]] = []
            if normalized_text.strip():
                from app.services.similarity import find_similar_materials

                matches = find_similar_materials(
                    session=session,
                    material_id=material_uuid,
                    normalized_text=normalized_text,
                    minhash_signature=signature,
                )

            # Replace previous checks so retries/reprocessing are idempotent.
            session.execute(
                delete(SimilarityCheck).where(
                    SimilarityCheck.target_material_id == material_uuid
                )
            )
            for match in matches:
                session.add(
                    SimilarityCheck(
                        target_material_id=material_uuid,
                        matched_material_id=UUID(str(match["matched_material_id"])),
                        similarity_percentage=float(match["similarity_percentage"]),
                        check_method=match["check_method"],
                        matching_fragments=match.get("matching_fragments"),
                    )
                )
            session.flush()
            _write_log(
                session,
                material_uuid,
                "similarity",
                "completed",
                details={"matches_found": len(matches)},
            )

            current_step = "uniqueness_score"
            # Step 5: score is based on the maximum found similarity.
            max_similarity = max(
                (float(match["similarity_percentage"]) for match in matches),
                default=0.0,
            )
            material.uniqueness_score = round(max(0.0, 100.0 - max_similarity), 2)
            session.flush()
            _write_log(
                session,
                material_uuid,
                "uniqueness_score",
                "completed",
                details={
                    "max_similarity_percentage": max_similarity,
                    "uniqueness_score": float(material.uniqueness_score),
                },
            )

            # Step 6: complete.
            material.processing_status = ProcessingStatus.completed
            session.flush()
            _write_log(session, material_uuid, "pipeline", "completed")
            logger.info("Material %s processing completed", material_id)

            return {
                "material_id": str(material_uuid),
                "processing_status": ProcessingStatus.completed.value,
                "uniqueness_score": float(material.uniqueness_score),
                "matches_found": len(matches),
            }

        except Exception as exc:
            logger.exception("Material %s processing failed", material_id)
            # A failed SQL statement leaves the current transaction unusable.
            # Roll it back first, then persist the failure in a fresh transaction
            # so the status/log are not lost together with the failed pipeline.
            error_text = f"{type(exc).__name__}: {exc}"[:4000]
            session.rollback()
            # Remove a possibly indexed document if a later pipeline step failed.
            try:
                from app.services.similarity import index_material_text
                index_material_text(material_id=material_uuid, normalized_text="")
            except Exception:
                logger.exception("Could not remove failed material from Elasticsearch")
            try:
                with get_sync_session() as failure_session:
                    failed_material = failure_session.get(Material, material_uuid)
                    if failed_material is not None:
                        failed_material.processing_status = ProcessingStatus.failed
                        _write_log(
                            failure_session,
                            material_uuid,
                            current_step,
                            "failed",
                            error_message=error_text,
                        )
            except Exception:
                logger.exception(
                    "Could not persist failed status for material %s", material_id
                )
            return {
                "material_id": str(material_uuid),
                "processing_status": ProcessingStatus.failed.value,
                "error": error_text,
            }
