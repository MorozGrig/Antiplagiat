
"""remove expert role and duplicate material status

Revision ID: 7a582bea933d
Revises: fa4746e9a912
Create Date: 2026-11-26 09:18:17.570187

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '7a582bea933d'
down_revision: Union[str, Sequence[str], None] = 'fa4746e9a912'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Remove expert role and duplicate material status."""

    # Создаём новые ENUM-типы без удаляемых значений.
    op.execute("""
        CREATE TYPE public.user_role_enum_new AS ENUM (
            'user', 'admin'
        )
    """)

    op.execute("""
        CREATE TYPE public.material_status_enum_new AS ENUM (
            'active', 'on_moderation', 'archived', 'blocked'
        )
    """)

    # Временно убираем значения по умолчанию.
    op.execute("""
        ALTER TABLE public.users
        ALTER COLUMN role DROP DEFAULT
    """)

    op.execute("""
        ALTER TABLE public.materials
        ALTER COLUMN status DROP DEFAULT
    """)

    # Переводим столбцы на новые ENUM-типы.
    op.execute("""
        ALTER TABLE public.users
        ALTER COLUMN role TYPE public.user_role_enum_new
        USING role::text::public.user_role_enum_new
    """)

    op.execute("""
        ALTER TABLE public.materials
        ALTER COLUMN status TYPE public.material_status_enum_new
        USING status::text::public.material_status_enum_new
    """)

    # Удаляем старые типы.
    op.execute("DROP TYPE public.user_role_enum")
    op.execute("DROP TYPE public.material_status_enum")

    # Новые типы получают исходные имена.
    op.execute("""
        ALTER TYPE public.user_role_enum_new
        RENAME TO user_role_enum
    """)

    op.execute("""
        ALTER TYPE public.material_status_enum_new
        RENAME TO material_status_enum
    """)

    # Восстанавливаем значения по умолчанию.
    op.execute("""
        ALTER TABLE public.users
        ALTER COLUMN role SET DEFAULT 'user'::public.user_role_enum
    """)

    op.execute("""
        ALTER TABLE public.materials
        ALTER COLUMN status SET DEFAULT 'on_moderation'::public.material_status_enum
    """)


def downgrade() -> None:
    """Restore expert role and duplicate material status."""

    # Создаём прежние ENUM-типы.
    op.execute("""
        CREATE TYPE public.user_role_enum_old AS ENUM (
            'user', 'expert', 'admin'
        )
    """)

    op.execute("""
        CREATE TYPE public.material_status_enum_old AS ENUM (
            'active', 'on_moderation', 'archived', 'blocked', 'duplicate'
        )
    """)

    # Временно убираем значения по умолчанию.
    op.execute("""
        ALTER TABLE public.users
        ALTER COLUMN role DROP DEFAULT
    """)

    op.execute("""
        ALTER TABLE public.materials
        ALTER COLUMN status DROP DEFAULT
    """)

    # Возвращаем столбцы на прежние ENUM-типы.
    op.execute("""
        ALTER TABLE public.users
        ALTER COLUMN role TYPE public.user_role_enum_old
        USING role::text::public.user_role_enum_old
    """)

    op.execute("""
        ALTER TABLE public.materials
        ALTER COLUMN status TYPE public.material_status_enum_old
        USING status::text::public.material_status_enum_old
    """)

    # Удаляем новые типы.
    op.execute("DROP TYPE public.user_role_enum")
    op.execute("DROP TYPE public.material_status_enum")

    # Восстанавливаем исходные имена типов.
    op.execute("""
        ALTER TYPE public.user_role_enum_old
        RENAME TO user_role_enum
    """)

    op.execute("""
        ALTER TYPE public.material_status_enum_old
        RENAME TO material_status_enum
    """)

    # Восстанавливаем значения по умолчанию.
    op.execute("""
        ALTER TABLE public.users
        ALTER COLUMN role SET DEFAULT 'user'::public.user_role_enum
    """)

    op.execute("""
        ALTER TABLE public.materials
        ALTER COLUMN status SET DEFAULT 'on_moderation'::public.material_status_enum
    """)
