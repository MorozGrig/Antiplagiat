"""MinHash/LSH and Elasticsearch-based material similarity search.

The persisted MinHash signature is a PostgreSQL INTEGER[] (signed 32-bit
values), so this module uses a deterministic 31-bit hash function. This keeps
all 128 signature values losslessly storable and reconstructable.
"""
from __future__ import annotations

import hashlib
import logging
import re
from typing import Any
from uuid import UUID

from datasketch import MinHash, MinHashLSH
from sqlalchemy import select

from app.config import get_settings
from app.models.models import Material, MaterialHash, MaterialTextContent

logger = logging.getLogger(__name__)

MINHASH_NUM_PERM = 128
LSH_THRESHOLD = 0.3
_TOKEN_RE = re.compile(r"\w+", flags=re.UNICODE)


def _postgres_safe_hash(value: bytes) -> int:
    """Stable positive 31-bit hash suitable for PostgreSQL INTEGER."""
    digest = hashlib.blake2s(value, digest_size=4).digest()
    return int.from_bytes(digest, "big") & 0x7FFFFFFF


def _tokens(text: str) -> set[str]:
    return set(_TOKEN_RE.findall((text or "").lower()))


def _minhash_from_text(text: str) -> MinHash:
    signature = MinHash(num_perm=MINHASH_NUM_PERM, hashfunc=_postgres_safe_hash)
    for token in _tokens(text):
        signature.update(token.encode("utf-8"))
    return signature


def build_minhash_signature(normalized_text: str) -> list[int]:
    """Build a 128-value MinHash signature as a PostgreSQL-safe integer list."""
    if not normalized_text or not normalized_text.strip():
        return []
    # PostgreSQL INTEGER is signed 32-bit while datasketch uses uint32 values.\n    # Store the same 32 bits as signed integers and reverse the mapping on load.\n    return [\n        value if value < (1 << 31) else value - (1 << 32)\n        for value in (int(item) for item in _minhash_from_text(normalized_text).hashvalues)\n    ]


def _minhash_from_signature(values: list[int] | tuple[int, ...]) -> MinHash:
    if len(values) != MINHASH_NUM_PERM:
        raise ValueError(
            f"Ожидалась MinHash-сигнатура из {MINHASH_NUM_PERM} значений, "
            f"получено {len(values)}"
        )
    result = MinHash(num_perm=MINHASH_NUM_PERM, hashfunc=_postgres_safe_hash)
    result.hashvalues = [int(value) & 0xFFFFFFFF for value in values]
    return result


def jaccard_similarity(left_text: str, right_text: str) -> float:
    """Exact token-set Jaccard similarity in the range 0.0..1.0."""
    left = _tokens(left_text)
    right = _tokens(right_text)
    if not left and not right:
        return 1.0
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def _elasticsearch_candidates(
    normalized_text: str,
    *,
    exclude_material_id: UUID,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Run Elasticsearch more_like_this; failures do not stop the DB/LSH path."""
    settings = get_settings()
    try:
        from elasticsearch import Elasticsearch
    except ImportError:
        logger.warning("elasticsearch package is unavailable; skipping MLT search")
        return []

    client = None
    try:
        client = Elasticsearch(
            settings.elasticsearch_url,
            request_timeout=settings.elasticsearch_request_timeout,
            verify_certs=settings.elasticsearch_verify_certs,
        )
        response = client.search(
            index=settings.elasticsearch_index_materials,
            size=limit,
            query={
                "bool": {
                    "must": [
                        {
                            "more_like_this": {
                                "fields": ["normalized_text"],
                                "like": normalized_text[:100_000],
                                "min_term_freq": 1,
                                "min_doc_freq": 1,
                                "max_query_terms": 50,
                                "minimum_should_match": "20%",
                            }
                        }
                    ],
                    "must_not": [{"term": {"material_id": str(exclude_material_id)}}],
                }
            },
            source_includes=["material_id", "normalized_text"],
        )
        hits = response.get("hits", {}).get("hits", [])
        results: list[dict[str, Any]] = []
        for hit in hits:
            source = hit.get("_source") or {}
            candidate_id = source.get("material_id") or hit.get("_id")
            candidate_text = source.get("normalized_text")
            if not candidate_id or not candidate_text:
                # MLT's _score is ranking-dependent and cannot be converted
                # honestly into a similarity percentage.
                continue
            try:
                candidate_uuid = UUID(str(candidate_id))
            except (TypeError, ValueError):
                continue
            if candidate_uuid == exclude_material_id:
                continue
            results.append(
                {
                    "matched_material_id": str(candidate_uuid),
                    "similarity": jaccard_similarity(normalized_text, candidate_text),
                    "source": "elasticsearch",
                }
            )
        return results
    except Exception:
        logger.exception("Elasticsearch more_like_this request failed")
        return []
    finally:
        if client is not None:
            try:
                client.close()
            except Exception:
                logger.debug("Could not close Elasticsearch client", exc_info=True)


def index_material_text(
    *,
    material_id: UUID | str,
    normalized_text: str,
) -> bool:
    """Upsert or remove one material in Elasticsearch for more_like_this.

    Elasticsearch is an auxiliary candidate source. A temporary ES outage must
    not prevent the authoritative PostgreSQL/LSH pipeline from completing.
    """
    settings = get_settings()
    client = None
    try:
        from elasticsearch import Elasticsearch, NotFoundError
        client = Elasticsearch(
            settings.elasticsearch_url,
            request_timeout=settings.elasticsearch_request_timeout,
            verify_certs=settings.elasticsearch_verify_certs,
        )
        index_name = settings.elasticsearch_index_materials
        document_id = str(UUID(str(material_id)))
        if normalized_text and normalized_text.strip():
            client.index(
                index=index_name,
                id=document_id,
                document={
                    "material_id": document_id,
                    "normalized_text": normalized_text[:1_000_000],
                },
                refresh="wait_for",
            )
        else:
            try:
                client.delete(index=index_name, id=document_id, refresh="wait_for")
            except NotFoundError:
                pass
        return True
    except Exception:
        logger.exception("Could not synchronize material %s to Elasticsearch", material_id)
        return False
    finally:
        if client is not None:
            try:
                client.close()
            except Exception:
                logger.debug("Could not close Elasticsearch client", exc_info=True)


def find_similar_materials(
    *,
    session,
    material_id: UUID | str,
    normalized_text: str,
    minhash_signature: list[int] | None = None,
    threshold: float = LSH_THRESHOLD,
    elasticsearch_limit: int = 50,
) -> list[dict[str, Any]]:
    """Find similar materials via MinHashLSH and Elasticsearch more_like_this.

    Returns dicts accepted by tasks_processing.process_material:
    matched_material_id, similarity_percentage, check_method and
    matching_fragments (optional). Similarity is exact token Jaccard, not
    Elasticsearch's uncalibrated relevance score.
    """
    target_id = UUID(str(material_id))
    if not normalized_text or not normalized_text.strip():
        return []

    signature_values = minhash_signature or build_minhash_signature(normalized_text)
    if not signature_values:
        return []

    # Load persisted signatures and texts; this also makes LSH reusable across
    # worker processes without relying on a process-local in-memory index.
    rows = session.execute(
        select(
            MaterialHash.material_id,
            MaterialHash.minhash_signature,
            MaterialTextContent.normalized_text,
        )
        .join(
            MaterialTextContent,
            MaterialTextContent.material_id == MaterialHash.material_id,
        )
        .where(MaterialHash.material_id != target_id)
        .where(MaterialHash.minhash_signature.is_not(None))
    ).all()

    lsh = MinHashLSH(threshold=threshold, num_perm=MINHASH_NUM_PERM)
    candidate_texts: dict[str, str] = {}
    for row_id, row_signature, row_text in rows:
        if not row_signature or len(row_signature) != MINHASH_NUM_PERM or not row_text:
            continue
        key = str(row_id)
        try:
            lsh.insert(key, _minhash_from_signature(row_signature))
            candidate_texts[key] = row_text
        except ValueError:
            logger.warning("Skipping invalid MinHash signature for material %s", key)

    target_minhash = _minhash_from_signature(signature_values)
    lsh_keys = set(lsh.query(target_minhash))

    # Merge LSH and Elasticsearch candidates; exact Jaccard is the final score.
    candidates: dict[str, dict[str, Any]] = {}
    for key in lsh_keys:
        score = jaccard_similarity(normalized_text, candidate_texts[key])
        candidates[key] = {
            "matched_material_id": key,
            "similarity_percentage": round(score * 100.0, 2),
            "check_method": "jaccard",
            "matching_fragments": None,
        }

    es_hits = _elasticsearch_candidates(
        normalized_text,
        exclude_material_id=target_id,
        limit=elasticsearch_limit,
    )
    for hit in es_hits:
        key = hit["matched_material_id"]
        score = float(hit["similarity"])
        if score <= 0:
            continue
        percentage = round(score * 100.0, 2)
        existing = candidates.get(key)
        if existing is None or percentage > existing["similarity_percentage"]:
            candidates[key] = {
                "matched_material_id": key,
                "similarity_percentage": percentage,
                "check_method": "hybrid" if existing is not None else "jaccard",
                "matching_fragments": None,
            }
        elif existing is not None:
            existing["check_method"] = "hybrid"

    # Do not emit stale Elasticsearch documents: similarity_checks has a FK
    # to materials, so every candidate must still exist in PostgreSQL.
    candidate_ids = [UUID(key) for key in candidates]
    existing_ids = (
        set(session.scalars(select(Material.id).where(Material.id.in_(candidate_ids))).all())
        if candidate_ids else set()
    )

    # Keep only actual textual overlap; LSH's threshold is a candidate filter.
    return sorted(
        (
            item for item in candidates.values()
            if item["similarity_percentage"] > 0
            and UUID(item["matched_material_id"]) in existing_ids
        ),
        key=lambda item: item["similarity_percentage"],
        reverse=True,
    )


# Public alias for callers/tests that use the longer descriptive name.
calculate_minhash_signature = build_minhash_signature
