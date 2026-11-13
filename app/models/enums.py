"""Python-аналоги ENUM-типов PostgreSQL (CREATE TYPE ... AS ENUM).

Имена значений строго соответствуют схеме БД.
`native_enum=True` + `name=...` в таблицах гарантируют использование
уже созданных в PostgreSQL enum-типов, а не анонимных.
"""

import enum

# Имена типов в PostgreSQL (public.<name>) и их значения — единый источник истины.


class UserRole(str, enum.Enum):
    user = "user"
    expert = "expert"
    admin = "admin"


class UserStatus(str, enum.Enum):
    active = "active"
    suspended = "suspended"
    banned = "banned"


class MaterialStatus(str, enum.Enum):
    active = "active"
    on_moderation = "on_moderation"
    archived = "archived"
    blocked = "blocked"
    duplicate = "duplicate"


class ProcessingStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"


class CertificateStatus(str, enum.Enum):
    valid = "valid"
    revoked = "revoked"


class CheckMethod(str, enum.Enum):
    sha256 = "sha256"
    simhash = "simhash"
    minhash = "minhash"
    jaccard = "jaccard"
    hybrid = "hybrid"


class DisputeStatus(str, enum.Enum):
    pending = "pending"
    under_review = "under_review"
    resolved = "resolved"
    rejected = "rejected"


# Маппинг: имя типа в PG -> python-enum (пригодится в миграциях/сервисах)
PG_ENUM_TYPES = {
    "user_role_enum": UserRole,
    "user_status_enum": UserStatus,
    "material_status_enum": MaterialStatus,
    "processing_status_enum": ProcessingStatus,
    "certificate_status_enum": CertificateStatus,
    "check_method_enum": CheckMethod,
    "dispute_status_enum": DisputeStatus,
}
