
"""add performance indexes

Revision ID: fa4746e9a912
Revises: 123b78d8b5fb
Create Date: 2026-11-25
"""

from alembic import op


revision = "fa4746e9a912"
down_revision = "123b78d8b5fb"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_materials_sha256_hash",
        "materials",
        ["sha256_hash"],
        schema="public",
    )

    op.create_index(
        "ix_processing_log_material_started_at",
        "processing_log",
        ["material_id", "started_at"],
        schema="public",
        postgresql_ops={"started_at": "DESC"},
    )

    op.create_index(
        "ix_copyright_disputes_complainant_created_at",
        "copyright_disputes",
        ["complainant_id", "created_at"],
        schema="public",
        postgresql_ops={"created_at": "DESC"},
    )

    op.create_index(
        "ix_copyright_disputes_status_created_at",
        "copyright_disputes",
        ["status", "created_at"],
        schema="public",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_copyright_disputes_status_created_at",
        table_name="copyright_disputes",
        schema="public",
    )

    op.drop_index(
        "ix_copyright_disputes_complainant_created_at",
        table_name="copyright_disputes",
        schema="public",
    )

    op.drop_index(
        "ix_processing_log_material_started_at",
        table_name="processing_log",
        schema="public",
    )

    op.drop_index(
        "ix_materials_sha256_hash",
        table_name="materials",
        schema="public",
    )
