from __future__ import annotations

import datetime as _dt
import copy
import sqlite3
import time

from sqlalchemy import delete, select, update
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from web.item_service import merge_imported, mode_policy, stamp_sheet_rows
from web.models import Job, PendingImportRecord, WorkspaceRecord


_SQLITE_WRITE_ATTEMPTS = 4
_SQLITE_WRITE_RETRY_SECONDS = 0.025


def _json_safe(value):
    """Make a value safe for a JSON column.

    Spreadsheet cells can arrive as datetime/date/time objects (openpyxl reads
    dated cells that way), which the JSON encoder cannot serialize. Convert those
    to ISO strings, recursing through dicts/lists so nested row values are also
    covered.
    """
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (_dt.datetime, _dt.date, _dt.time)):
        return value.isoformat()
    return value


class WorkspaceNotFound(LookupError):
    pass


class PendingImportNotFound(LookupError):
    pass


class EmptySheetSelection(ValueError):
    pass


class DuplicateSheetSelection(ValueError):
    pass


class UnknownSheetSelection(ValueError):
    def __init__(self, sheet_name: str) -> None:
        self.sheet_name = sheet_name
        super().__init__(sheet_name)


class WorkspaceBusy(RuntimeError):
    pass


def is_sqlite_busy(error: OperationalError) -> bool:
    """Recognize only SQLite's driver-provided BUSY/LOCKED result codes."""
    code = getattr(error.orig, 'sqlite_errorcode', None)
    if not isinstance(code, int):
        return False
    return (code & 0xFF) in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED)


def _acquire_sqlite_write(session: Session) -> None:
    if session.get_bind().dialect.name != 'sqlite':
        return
    for attempt in range(_SQLITE_WRITE_ATTEMPTS):
        try:
            connection = session.connection()
            driver_connection = connection.connection.driver_connection
            if driver_connection.in_transaction:
                return
            connection.exec_driver_sql('BEGIN IMMEDIATE')
            return
        except OperationalError as error:
            session.rollback()
            if not is_sqlite_busy(error):
                raise
            if attempt + 1 == _SQLITE_WRITE_ATTEMPTS:
                raise WorkspaceBusy() from error
            time.sleep(_SQLITE_WRITE_RETRY_SECONDS * (attempt + 1))


class WorkspaceRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(
        self, owner_user_id: str, mode: str, filename: str = '',
        criteria: list[dict] | None = None,
    ) -> WorkspaceRecord:
        mode_policy(mode)
        workspace = WorkspaceRecord(
            owner_user_id=owner_user_id,
            mode=mode,
            filename=filename,
            criteria=[_json_safe(dict(row)) for row in (criteria or [])],
            occurrences=[],
        )
        self._session.add(workspace)
        self._session.flush()
        return workspace

    def get_owned(
        self, owner_user_id: str, workspace_id: str,
    ) -> WorkspaceRecord:
        workspace = self._session.scalar(
            select(WorkspaceRecord).where(
                WorkspaceRecord.id == workspace_id,
                WorkspaceRecord.owner_user_id == owner_user_id,
            )
        )
        if workspace is None:
            raise WorkspaceNotFound()
        return workspace

    def delete_owned(self, owner_user_id: str, workspace_id: str) -> None:
        workspace = self._session.scalar(
            select(WorkspaceRecord).where(
                WorkspaceRecord.id == workspace_id,
                WorkspaceRecord.owner_user_id == owner_user_id,
            ).with_for_update()
        )
        if workspace is None:
            raise WorkspaceNotFound()
        active_job = self._session.scalar(
            select(Job.id).where(
                Job.workspace_id == workspace_id,
                Job.status.in_(('queued', 'running')),
            ).limit(1)
        )
        if active_job is not None:
            raise WorkspaceBusy()
        self._session.delete(workspace)
        self._session.flush()

    def replace_template(
        self, owner_user_id: str, workspace_id: str, filename: str,
        criteria: list[dict],
    ) -> WorkspaceRecord:
        workspace = self._update_workspace(
            owner_user_id,
            workspace_id,
            filename=filename,
            criteria=[dict(row) for row in criteria],
            occurrences=[],
            group_meta={},
            skipped=[],
            results=[],
            not_found=[],
        )
        return workspace

    def add_pending(
        self, owner_user_id: str, workspace_id: str, sheets: list,
        skipped: list,
    ) -> PendingImportRecord:
        self.get_owned(owner_user_id, workspace_id)
        pending = PendingImportRecord(
            owner_user_id=owner_user_id,
            workspace_id=workspace_id,
            sheets=[
                (sheet_name, [_json_safe(dict(row)) for row in rows])
                for sheet_name, rows in sheets
            ],
            skipped=_json_safe(list(skipped)),
        )
        self._session.add(pending)
        self._session.flush()
        return pending

    def apply_pending(
        self, owner_user_id: str, pending_id: str, selected_sheets: list[str],
    ) -> WorkspaceRecord:
        if not isinstance(selected_sheets, list) or not selected_sheets:
            raise EmptySheetSelection()
        if (not all(isinstance(name, str) for name in selected_sheets)
                or len(selected_sheets) != len(set(selected_sheets))):
            raise DuplicateSheetSelection()

        _acquire_sqlite_write(self._session)
        try:
            with self._session.begin_nested():
                claimed = self._session.execute(
                    delete(PendingImportRecord).where(
                        PendingImportRecord.id == pending_id,
                        PendingImportRecord.owner_user_id == owner_user_id,
                    ).returning(
                        PendingImportRecord.workspace_id,
                        PendingImportRecord.sheets,
                        PendingImportRecord.skipped,
                    )
                ).mappings().one_or_none()
                if claimed is None:
                    raise PendingImportNotFound()

                workspace_id = claimed['workspace_id']
                sheets = copy.deepcopy(claimed['sheets'])
                pending_skipped = copy.deepcopy(claimed['skipped'])
                available = [sheet_name for sheet_name, _rows in sheets]
                if len(available) != len(set(available)):
                    raise DuplicateSheetSelection()
                available_set = set(available)
                unknown = [
                    name for name in selected_sheets if name not in available_set]
                if unknown:
                    raise UnknownSheetSelection(unknown[0])

                workspace = self._session.scalar(
                    select(WorkspaceRecord).where(
                        WorkspaceRecord.id == workspace_id,
                        WorkspaceRecord.owner_user_id == owner_user_id,
                    ).with_for_update()
                )
                if workspace is None:
                    raise PendingImportNotFound()

                selected = set(selected_sheets)
                items = []
                for sheet_name, rows in sheets:
                    if sheet_name in selected:
                        items.extend(
                            stamp_sheet_rows(sheet_name, rows)
                            if workspace.mode == 'event' else rows)
                merged = merge_imported(
                    workspace.criteria, workspace.occurrences,
                    workspace.group_meta, items)
                return self._update_workspace(
                    owner_user_id,
                    workspace.id,
                    criteria=merged.criteria,
                    occurrences=merged.occurrences,
                    group_meta=merged.group_meta,
                    skipped=list(workspace.skipped) + list(pending_skipped),
                    results=[],
                    not_found=[],
                )
        except OperationalError as error:
            self._session.rollback()
            if is_sqlite_busy(error):
                raise WorkspaceBusy() from error
            raise

    def claim_pending_rows(
        self, owner_user_id: str, pending_id: str,
        selected_sheets: list[str],
    ) -> tuple[str, list[dict], list]:
        """Consume an owner-scoped pending import without merging a workspace.

        Mastercode WR needs the established pending/exact-sheet safety but its
        selected rows go to an import preview, not into Item Finder results.
        """
        if not isinstance(selected_sheets, list) or not selected_sheets:
            raise EmptySheetSelection()
        if (not all(isinstance(name, str) for name in selected_sheets)
                or len(selected_sheets) != len(set(selected_sheets))):
            raise DuplicateSheetSelection()

        _acquire_sqlite_write(self._session)
        try:
            with self._session.begin_nested():
                claimed = self._session.execute(
                    delete(PendingImportRecord).where(
                        PendingImportRecord.id == pending_id,
                        PendingImportRecord.owner_user_id == owner_user_id,
                    ).returning(
                        PendingImportRecord.workspace_id,
                        PendingImportRecord.sheets,
                        PendingImportRecord.skipped,
                    )
                ).mappings().one_or_none()
                if claimed is None:
                    raise PendingImportNotFound()
                sheets = copy.deepcopy(claimed['sheets'])
                available = [name for name, _rows in sheets]
                if len(available) != len(set(available)):
                    raise DuplicateSheetSelection()
                unknown = [name for name in selected_sheets
                           if name not in set(available)]
                if unknown:
                    raise UnknownSheetSelection(unknown[0])
                wanted = set(selected_sheets)
                rows = [dict(row) for name, sheet_rows in sheets
                        if name in wanted for row in sheet_rows]
                return (claimed['workspace_id'], rows,
                        copy.deepcopy(claimed['skipped']))
        except OperationalError as error:
            self._session.rollback()
            if is_sqlite_busy(error):
                raise WorkspaceBusy() from error
            raise

    def save_results(
        self, owner_user_id: str, workspace_id: str, *, game: str, results: list,
        not_found: list,
    ) -> WorkspaceRecord:
        return self._update_workspace(
            owner_user_id,
            workspace_id,
            game=game,
            results=list(results),
            not_found=list(not_found),
        )

    def _update_workspace(
        self, owner_user_id: str, workspace_id: str, **values,
    ) -> WorkspaceRecord:
        # Every JSON column funnels through here; sanitize so spreadsheet-sourced
        # datetime cells never reach the JSON encoder.
        values = {key: _json_safe(item) for key, item in values.items()}
        workspace = self._session.scalar(
            update(WorkspaceRecord).where(
                WorkspaceRecord.id == workspace_id,
                WorkspaceRecord.owner_user_id == owner_user_id,
            ).values(**values).returning(WorkspaceRecord)
        )
        if workspace is None:
            raise WorkspaceNotFound()
        return workspace
