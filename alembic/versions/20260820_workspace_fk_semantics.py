"""Make workspace foreign keys explicit and bound pending pairing tokens.

Revision ID: 20260820_workspace_fks
Revises: 20260722_auth_sessions
Create Date: 2026-08-20
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = '20260820_workspace_fks'
down_revision = '20260722_auth_sessions'
branch_labels = None
depends_on = None


_FK_NAMING_CONVENTION = {
    'fk': 'fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s',
}
_PAIRING_PENDING_PREDICATE = sa.text(
    "status = 'pending' AND used_at IS NULL")


def _workspace_fk_name(table_name: str, foreign_keys: list[dict]) -> str:
    for foreign_key in foreign_keys:
        if (foreign_key.get('constrained_columns') == ['workspace_id']
                and foreign_key.get('referred_table') == 'workspaces'):
            return foreign_key.get('name') or (
                f'fk_{table_name}_workspace_id_workspaces')
    raise RuntimeError(f'workspace foreign key not found for {table_name}')


def _replace_workspace_fk(table_name: str, ondelete: str | None) -> None:
    bind = op.get_bind()
    foreign_keys = sa.inspect(bind).get_foreign_keys(table_name)
    old_name = _workspace_fk_name(table_name, foreign_keys)
    new_name = f'fk_{table_name}_workspace_id_workspaces'
    with op.batch_alter_table(
        table_name, naming_convention=_FK_NAMING_CONVENTION,
    ) as batch_op:
        batch_op.drop_constraint(old_name, type_='foreignkey')
        batch_op.create_foreign_key(
            new_name, 'workspaces', ['workspace_id'], ['id'],
            ondelete=ondelete)


def _expire_duplicate_pending_tokens(connection) -> None:
    rows = connection.execute(sa.text(
        "SELECT id, user_id FROM pairing_tokens "
        "WHERE status = 'pending' AND used_at IS NULL "
        "ORDER BY user_id ASC, created_at DESC, id DESC"
    )).mappings()
    seen_users: set[str] = set()
    duplicate_ids: list[str] = []
    for row in rows:
        user_id = row['user_id']
        if user_id in seen_users:
            duplicate_ids.append(row['id'])
        else:
            seen_users.add(user_id)
    for token_id in duplicate_ids:
        connection.execute(sa.text(
            "UPDATE pairing_tokens SET status = 'expired' "
            "WHERE id = :token_id AND status = 'pending' AND used_at IS NULL"
        ), {'token_id': token_id})


def upgrade() -> None:
    _replace_workspace_fk('pending_imports', 'CASCADE')
    _replace_workspace_fk('jobs', 'SET NULL')
    _expire_duplicate_pending_tokens(op.get_bind())
    op.create_index(
        'uq_pairing_tokens_one_pending_user',
        'pairing_tokens', ['user_id'], unique=True,
        sqlite_where=_PAIRING_PENDING_PREDICATE,
        postgresql_where=_PAIRING_PENDING_PREDICATE,
    )


def downgrade() -> None:
    op.drop_index(
        'uq_pairing_tokens_one_pending_user', table_name='pairing_tokens')
    _replace_workspace_fk('pending_imports', None)
    _replace_workspace_fk('jobs', None)
