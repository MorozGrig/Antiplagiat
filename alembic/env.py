
import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

from app.config import settings
from app.models.models import Base


config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Используем URL из настроек приложения, не храним пароль в alembic.ini.
database_url = settings.async_database_url
config.set_main_option(
    "sqlalchemy.url",
    database_url.replace("%", "%%"),
)

# Метаданные всех моделей SQLAlchemy.
target_metadata = Base.metadata


def configure_context(**kwargs):
    context.configure(
        target_metadata=target_metadata,
        include_schemas=False,
        compare_type=True,
        compare_server_default=True,
        **kwargs,
    )


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")

    configure_context(
        url=url,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    configure_context(connection=connection)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
