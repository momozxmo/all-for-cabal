from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (Boolean, CheckConstraint, DateTime, ForeignKey, Index,
                        JSON, String, Text, text)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator


def uuid_hex() -> str:
    return uuid.uuid4().hex


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class UTCDateTime(TypeDecorator[datetime]):
    """Store datetimes as UTC and return aware UTC values from every backend."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(
        self, value: datetime | None, dialect: Any
    ) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError('UTCDateTime values must be timezone-aware')
        value = value.astimezone(timezone.utc)
        if dialect.name == 'sqlite':
            return value.replace(tzinfo=None)
        return value

    def process_result_value(
        self, value: datetime | None, dialect: Any
    ) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), default=utc_now, onupdate=utc_now, nullable=False
    )


class User(TimestampMixin, Base):
    __tablename__ = 'users'
    __table_args__ = (
        CheckConstraint("role in ('admin', 'member')", name='ck_users_role'),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uuid_hex)
    username: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True, index=True
    )
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default='member')
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_login_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    password_changed_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), default=utc_now, nullable=False
    )

    web_sessions: Mapped[list[WebSession]] = relationship(back_populates='user')
    pairing_tokens: Mapped[list[PairingToken]] = relationship(back_populates='user')
    aztek_session: Mapped[AztekSession | None] = relationship(
        back_populates='user', uselist=False
    )
    workspaces: Mapped[list[WorkspaceRecord]] = relationship(back_populates='owner')
    pending_imports: Mapped[list[PendingImportRecord]] = relationship(
        back_populates='owner'
    )
    jobs: Mapped[list[Job]] = relationship(back_populates='owner')
    audit_logs: Mapped[list[AuditLog]] = relationship(back_populates='user')


class WebSession(Base):
    __tablename__ = 'web_sessions'

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uuid_hex)
    user_id: Mapped[str] = mapped_column(
        String(32), ForeignKey('users.id'), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True, index=True
    )
    user_agent: Mapped[str | None] = mapped_column(Text)
    ip_address: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), default=utc_now, nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    last_seen_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    revoked_at: Mapped[datetime | None] = mapped_column(UTCDateTime())

    user: Mapped[User] = relationship(back_populates='web_sessions')


class PairingToken(Base):
    __tablename__ = 'pairing_tokens'
    __table_args__ = (
        Index(
            'uq_pairing_tokens_one_pending_user', 'user_id', unique=True,
            sqlite_where=text("status = 'pending' AND used_at IS NULL"),
            postgresql_where=text("status = 'pending' AND used_at IS NULL"),
        ),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uuid_hex)
    user_id: Mapped[str] = mapped_column(
        String(32), ForeignKey('users.id'), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True, index=True
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default='pending')
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), default=utc_now, nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(UTCDateTime())

    user: Mapped[User] = relationship(back_populates='pairing_tokens')


class AztekSession(TimestampMixin, Base):
    __tablename__ = 'aztek_sessions'

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uuid_hex)
    user_id: Mapped[str] = mapped_column(
        String(32), ForeignKey('users.id'), nullable=False, unique=True, index=True
    )
    encrypted_state: Mapped[str] = mapped_column(Text, nullable=False)
    account_label: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(32), nullable=False, default='active')
    expires_hint_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    last_validated_at: Mapped[datetime | None] = mapped_column(UTCDateTime())

    user: Mapped[User] = relationship(back_populates='aztek_session')


class WorkspaceRecord(TimestampMixin, Base):
    __tablename__ = 'workspaces'

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uuid_hex)
    owner_user_id: Mapped[str] = mapped_column(
        String(32), ForeignKey('users.id'), nullable=False, index=True
    )
    mode: Mapped[str] = mapped_column(String(32), nullable=False)
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    game: Mapped[str | None] = mapped_column(String(255))
    criteria: Mapped[list[Any]] = mapped_column(JSON, default=list, nullable=False)
    occurrences: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict, nullable=False
    )
    group_meta: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict, nullable=False
    )
    skipped: Mapped[list[Any]] = mapped_column(JSON, default=list, nullable=False)
    results: Mapped[list[Any]] = mapped_column(JSON, default=list, nullable=False)
    not_found: Mapped[list[Any]] = mapped_column(JSON, default=list, nullable=False)

    owner: Mapped[User] = relationship(back_populates='workspaces')
    pending_imports: Mapped[list[PendingImportRecord]] = relationship(
        back_populates='workspace', passive_deletes='all'
    )
    jobs: Mapped[list[Job]] = relationship(
        back_populates='workspace', passive_deletes='all')


class PendingImportRecord(TimestampMixin, Base):
    __tablename__ = 'pending_imports'

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uuid_hex)
    owner_user_id: Mapped[str] = mapped_column(
        String(32), ForeignKey('users.id'), nullable=False, index=True
    )
    workspace_id: Mapped[str] = mapped_column(
        String(32), ForeignKey('workspaces.id', ondelete='CASCADE'),
        nullable=False, index=True
    )
    sheets: Mapped[list[Any]] = mapped_column(JSON, default=list, nullable=False)
    skipped: Mapped[list[Any]] = mapped_column(JSON, default=list, nullable=False)

    owner: Mapped[User] = relationship(back_populates='pending_imports')
    workspace: Mapped[WorkspaceRecord] = relationship(back_populates='pending_imports')


class Job(TimestampMixin, Base):
    __tablename__ = 'jobs'

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uuid_hex)
    owner_user_id: Mapped[str] = mapped_column(
        String(32), ForeignKey('users.id'), nullable=False, index=True
    )
    workspace_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey('workspaces.id', ondelete='SET NULL'), index=True
    )
    tool: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default='queued')
    config: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    result: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    log: Mapped[list[Any]] = mapped_column(JSON, default=list, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime())

    owner: Mapped[User] = relationship(back_populates='jobs')
    workspace: Mapped[WorkspaceRecord | None] = relationship(back_populates='jobs')


class AuditLog(Base):
    __tablename__ = 'audit_logs'

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uuid_hex)
    user_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey('users.id'), index=True
    )
    action: Mapped[str] = mapped_column(String(255), nullable=False)
    tool: Mapped[str | None] = mapped_column(String(64))
    resource_type: Mapped[str | None] = mapped_column(String(64))
    resource_id: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    account_label: Mapped[str | None] = mapped_column(String(255))
    ip_address: Mapped[str | None] = mapped_column(String(255))
    user_agent: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), default=utc_now, nullable=False
    )

    user: Mapped[User | None] = relationship(back_populates='audit_logs')
