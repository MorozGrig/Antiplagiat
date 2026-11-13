"""SQLAlchemy 2.0 модели — 100% соответствие предоставленной схеме PostgreSQL.

Особенности маппинга:
- UUID (Postgres)          -> sqlalchemy.dialects.postgresql.UUID
- varchar(50)[]            -> ARRAY(String(50))
- jsonb                    -> JSONB
- numeric(5,2)             -> NUMERIC(5, 2)
- bigint                   -> BIGINT
- bigserial (processing_log)-> BIGSERIAL
- timestamptz              -> TIMESTAMP(timezone=True)
- ENUM-типы               -> postgresql.ENUM(name='..._enum', native_enum=True),
                             значения строго из app/models/enums.py
- sequence `registration_number_seq` и функция `generate_registration_number()`
  определены как SQL-объекты; DEFAULT для registration_number не навязывается —
  номер генерируется бизнес-логикой через SELECT generate_registration_number().
"""

from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    ForeignKey,
    Integer,
    Numeric,
    Sequence,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, BIGINT, ENUM as PgENUM, JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.models.enums import (
    CertificateStatus,
    CheckMethod,
    DisputeStatus,
    MaterialStatus,
    ProcessingStatus,
    UserRole,
    UserStatus,
)

# --------------------------------------------------------------------------- #
# Нативные PG ENUM-типы (созданы в схеме; SQLAlchemy ссылается на них по имени)
# --------------------------------------------------------------------------- #


def _pg_enum(python_enum: type, type_name: str) -> PgENUM:
    """Построить postgresql.ENUM по python-enum с фиксированным именем типа.

    `create_type=False` — типы уже созданы DDL/миграцией и пересоздаваться
    SQLAlchemy не должны.
    """
    return PgENUM(
        *[e.value for e in python_enum],
        name=type_name,
        native_enum=True,
        create_type=False,
    )


# Последовательность из схемы (используется в DDL-дефолтах/миграциях)
registration_number_seq = Sequence(
    "registration_number_seq",
    metadata=None,  # привяжем к Base.metadata ниже
    start=1,
    increment=1,
    cache=1,
)


class Base(DeclarativeBase):
    """Базовый класс всех моделей."""


registration_number_seq.metadata = Base.metadata


# --------------------------------------------------------------------------- #
# users
# --------------------------------------------------------------------------- #
class User(Base):
    __tablename__ = "users"
    __table_args__ = {"schema": "public"}

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    username: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    email: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        _pg_enum(UserRole, "user_role_enum"),
        nullable=False,
        server_default=UserRole.user.value,
    )
    status: Mapped[UserStatus] = mapped_column(
        _pg_enum(UserStatus, "user_status_enum"),
        nullable=False,
        server_default=UserStatus.active.value,
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.current_timestamp()
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.current_timestamp()
    )

    # Служебное имя PK для self-ссылок в copyright_disputes
    materials: Mapped[List["Material"]] = relationship(
        "Material", back_populates="author", foreign_keys="Material.author_id"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<User id={self.id} username={self.username!r} role={self.role}>"


# --------------------------------------------------------------------------- #
# materials
# --------------------------------------------------------------------------- #
class Material(Base):
    __tablename__ = "materials"
    __table_args__ = {"schema": "public"}

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    # Номер RM-YYYY-NNNNNN; генерируется функцией generate_registration_number()
    registration_number: Mapped[str] = mapped_column(String(30), nullable=False, unique=True)
    author_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("public.users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    tags: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String(50)), nullable=True, server_default="{}"
    )
    sha256_hash: Mapped[str] = mapped_column(String(64), nullable=False)  # char(64)
    file_s3_path: Mapped[str] = mapped_column(String(512), nullable=False)
    file_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[MaterialStatus] = mapped_column(
        _pg_enum(MaterialStatus, "material_status_enum"),
        nullable=False,
        server_default=MaterialStatus.on_moderation.value,
    )
    is_public: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )
    uniqueness_score: Mapped[Optional[float]] = mapped_column(
        Numeric(5, 2), nullable=True
    )
    processing_status: Mapped[ProcessingStatus] = mapped_column(
        _pg_enum(ProcessingStatus, "processing_status_enum"),
        nullable=False,
        server_default=ProcessingStatus.pending.value,
    )
    is_duplicate: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    duplicate_of: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("public.materials.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.current_timestamp()
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.current_timestamp()
    )

    author: Mapped["User"] = relationship(
        "User", back_populates="materials", foreign_keys=[author_id]
    )
    text_content: Mapped[Optional["MaterialTextContent"]] = relationship(
        "MaterialTextContent",
        back_populates="material",
        uselist=False,
        cascade="all, delete-orphan",
    )
    hashes: Mapped[Optional["MaterialHash"]] = relationship(
        "MaterialHash",
        back_populates="material",
        uselist=False,
        cascade="all, delete-orphan",
    )
    certificate: Mapped[Optional["Certificate"]] = relationship(
        "Certificate", back_populates="material", uselist=False
    )
    duplicates: Mapped[List["Material"]] = relationship(
        "Material", foreign_keys=[duplicate_of]
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Material id={self.id} reg={self.registration_number!r}>"


# --------------------------------------------------------------------------- #
# material_text_content
# --------------------------------------------------------------------------- #
class MaterialTextContent(Base):
    __tablename__ = "material_text_content"
    __table_args__ = {"schema": "public"}

    material_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("public.materials.id", ondelete="CASCADE"),
        primary_key=True,
    )
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_text: Mapped[str] = mapped_column(Text, nullable=False)
    language_code: Mapped[Optional[str]] = mapped_column(String(2), nullable=True)  # char(2)
    word_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    extracted_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.current_timestamp()
    )

    material: Mapped["Material"] = relationship(
        "Material", back_populates="text_content", foreign_keys=[material_id]
    )


# --------------------------------------------------------------------------- #
# material_hashes
# --------------------------------------------------------------------------- #
class MaterialHash(Base):
    __tablename__ = "material_hashes"
    __table_args__ = {"schema": "public"}

    material_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("public.materials.id", ondelete="CASCADE"),
        primary_key=True,
    )
    simhash_value: Mapped[Optional[int]] = mapped_column(BIGINT, nullable=True)
    minhash_signature: Mapped[Optional[List[int]]] = mapped_column(
        ARRAY(Integer), nullable=True, server_default="{}"
    )
    calculated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.current_timestamp()
    )

    material: Mapped["Material"] = relationship(
        "Material", back_populates="hashes", foreign_keys=[material_id]
    )


# --------------------------------------------------------------------------- #
# similarity_checks
# --------------------------------------------------------------------------- #
class SimilarityCheck(Base):
    __tablename__ = "similarity_checks"
    __table_args__ = (
        UniqueConstraint(
            "target_material_id", "matched_material_id", name="unique_material_pair"
        ),
        {"schema": "public"},
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    target_material_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("public.materials.id", ondelete="CASCADE"),
        nullable=False,
    )
    matched_material_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("public.materials.id", ondelete="CASCADE"),
        nullable=False,
    )
    similarity_percentage: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    check_method: Mapped[CheckMethod] = mapped_column(
        _pg_enum(CheckMethod, "check_method_enum"), nullable=False
    )
    matching_fragments: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    checked_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.current_timestamp()
    )

    target_material: Mapped["Material"] = relationship(
        "Material", foreign_keys=[target_material_id]
    )
    matched_material: Mapped["Material"] = relationship(
        "Material", foreign_keys=[matched_material_id]
    )


# --------------------------------------------------------------------------- #
# certificates
# --------------------------------------------------------------------------- #
class Certificate(Base):
    __tablename__ = "certificates"
    __table_args__ = {"schema": "public"}

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    material_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("public.materials.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )
    certificate_number: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    pdf_s3_path: Mapped[str] = mapped_column(String(512), nullable=False)
    status: Mapped[CertificateStatus] = mapped_column(
        _pg_enum(CertificateStatus, "certificate_status_enum"),
        nullable=False,
        server_default=CertificateStatus.valid.value,
    )
    certificate_data: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    issued_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.current_timestamp()
    )
    revoked_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )

    material: Mapped["Material"] = relationship(
        "Material", back_populates="certificate", foreign_keys=[material_id]
    )


# --------------------------------------------------------------------------- #
# copyright_disputes
# --------------------------------------------------------------------------- #
class CopyrightDispute(Base):
    __tablename__ = "copyright_disputes"
    __table_args__ = {"schema": "public"}

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    material_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("public.materials.id", ondelete="RESTRICT"),
        nullable=False,
    )
    original_material_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("public.materials.id", ondelete="RESTRICT"),
        nullable=True,
    )
    complainant_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("public.users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    status: Mapped[DisputeStatus] = mapped_column(
        _pg_enum(DisputeStatus, "dispute_status_enum"),
        nullable=False,
        server_default=DisputeStatus.pending.value,
    )
    resolution: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    resolved_by: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("public.users.id", ondelete="SET NULL"),
        nullable=True,
    )
    moderator_comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.current_timestamp()
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )

    material: Mapped["Material"] = relationship(
        "Material", foreign_keys=[material_id]
    )
    original_material: Mapped[Optional["Material"]] = relationship(
        "Material", foreign_keys=[original_material_id]
    )
    complainant: Mapped["User"] = relationship("User", foreign_keys=[complainant_id])
    resolver: Mapped[Optional["User"]] = relationship("User", foreign_keys=[resolved_by])


# --------------------------------------------------------------------------- #
# processing_log
# --------------------------------------------------------------------------- #
class ProcessingLog(Base):
    __tablename__ = "processing_log"
    __table_args__ = {"schema": "public"}

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    material_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("public.materials.id", ondelete="CASCADE"),
        nullable=True,
    )
    step: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    details: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.current_timestamp()
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )

    material: Mapped[Optional["Material"]] = relationship(
        "Material", foreign_keys=[material_id]
    )


ALL_MODELS = [
    User,
    Material,
    MaterialTextContent,
    MaterialHash,
    SimilarityCheck,
    Certificate,
    CopyrightDispute,
    ProcessingLog,
]
