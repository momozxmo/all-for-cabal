from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, event, pool

from web import models
from web.models import Base
from web.settings import Settings


config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata
_SQLITE_BUSY_TIMEOUT_MS = 250


def _configure_sqlite_connection(dbapi_connection, _connection_record) -> None:
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute('PRAGMA foreign_keys=ON')
        cursor.execute(f'PRAGMA busy_timeout={_SQLITE_BUSY_TIMEOUT_MS}')
    finally:
        cursor.close()


def database_url() -> str:
    url = Settings.from_env().database_url
    config.set_main_option('sqlalchemy.url', url.replace('%', '%%'))
    return url


def run_migrations_offline() -> None:
    context.configure(
        url=database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={'paramstyle': 'named'},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    database_url()
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix='sqlalchemy.',
        poolclass=pool.NullPool,
    )
    if connectable.dialect.name == 'sqlite':
        event.listen(connectable, 'connect', _configure_sqlite_connection)

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        if connection.dialect.name == 'sqlite':
            connection.exec_driver_sql('BEGIN')
            try:
                context.run_migrations()
            except BaseException:
                connection.rollback()
                raise
            else:
                connection.commit()
        else:
            with context.begin_transaction():
                context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
