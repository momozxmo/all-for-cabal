from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session, sessionmaker

from web.settings import Settings


SQLITE_BUSY_TIMEOUT_MS = 250


class Database:
    def __init__(self, settings: Settings) -> None:
        connect_args = {}
        url = make_url(settings.database_url)
        if url.drivername.startswith('sqlite'):
            connect_args['check_same_thread'] = False
        self.engine: Engine = create_engine(
            settings.database_url,
            connect_args=connect_args,
            future=True,
        )
        if url.drivername.startswith('sqlite'):
            event.listen(self.engine, 'connect', self._enable_sqlite_foreign_keys)
        self._session_factory = sessionmaker(
            bind=self.engine,
            expire_on_commit=False,
            future=True,
        )

    @staticmethod
    def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute('PRAGMA foreign_keys=ON')
            cursor.execute(f'PRAGMA busy_timeout={SQLITE_BUSY_TIMEOUT_MS}')
        finally:
            cursor.close()

    @contextmanager
    def session(self) -> Iterator[Session]:
        session = self._session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
