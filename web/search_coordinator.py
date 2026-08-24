# -*- coding: utf-8 -*-
"""Per-user search lifecycle: concurrency gate, persisted jobs, session expiry.

The coordinator is the only place that turns a decrypted Aztek storage state
into a running search. It bounds concurrency with a semaphore, records each run
as a ``Job`` row, streams engine events to the caller, and — critically — never
lets ciphertext or another user's session reach the browser.
"""
from __future__ import annotations

import asyncio
import threading
from collections.abc import Awaitable, Callable
from contextlib import contextmanager

import aztek_core as core

from web import item_service, search_runner
from web.audit import write_audit
from web.browser_gate import BrowserOperationGate
from web.models import Job, User, utc_now
from web.security import InvalidEncryptedState
from web.workspaces import WorkspaceBusy, WorkspaceNotFound, WorkspaceRepository


_MAX_LOG_LINES = 500
# What a page gets replayed when it attaches to a search already in progress.
# Enough to read the story so far without holding a whole run in memory.
_MAX_REPLAY = 400


Emit = Callable[[dict], Awaitable[None]]


class LiveSearch:
    """A search running on its own, with whoever happens to be watching.

    The run belongs to the application, not to the socket that asked for it —
    a page that navigates to Create Bundle and back must find its search still
    going, and the job must be written down even if nobody is watching at all.
    """

    def __init__(self, job_id: str, finder, source_group_key: str = '') -> None:
        self.job_id = job_id
        self.finder = finder
        self.source_group_key = str(source_group_key or '').strip()
        self.history: list[dict] = []
        self.subscribers: set[asyncio.Queue] = set()
        self.done = False

    def publish(self, message: dict) -> None:
        self.history.append(message)
        if len(self.history) > _MAX_REPLAY:
            # Drop from the front: the recent end is the part worth reading.
            del self.history[:len(self.history) - _MAX_REPLAY]
        for queue in self.subscribers:
            queue.put_nowait(message)

    def finish(self) -> None:
        self.done = True
        for queue in self.subscribers:
            queue.put_nowait(None)


class SearchCoordinator:
    def __init__(self, database, settings, aztek_session_service,
                 browser_gate: BrowserOperationGate | None = None) -> None:
        self._database = database
        self._settings = settings
        self._aztek = aztek_session_service
        self._browser_gate = browser_gate or BrowserOperationGate(
            settings.browser_concurrency)
        # Searches in flight, by workspace. One per workspace: starting a search
        # already wipes that workspace's results, so two at once would fight.
        self._live: dict[str, LiveSearch] = {}
        self._registry_lock = threading.Lock()
        self._starting: set[str] = set()
        self._deleting: set[str] = set()

    def live(self, workspace_id: str) -> LiveSearch | None:
        with self._registry_lock:
            return self._live.get(workspace_id)

    @contextmanager
    def deletion_guard(self, workspace_id: str):
        with self._registry_lock:
            if (workspace_id in self._starting
                    or workspace_id in self._live
                    or workspace_id in self._deleting):
                raise WorkspaceBusy()
            self._deleting.add(workspace_id)
        try:
            yield
        finally:
            with self._registry_lock:
                self._deleting.discard(workspace_id)

    def stop(self, workspace_id: str) -> bool:
        """Ask a running search to wind up. Closing a page no longer does this."""
        with self._registry_lock:
            live = self._live.get(workspace_id)
        if live is None:
            return False
        live.finder._cancel = True
        return True

    async def attach(self, workspace_id: str, emit: Emit,
                     source_group_key: str = '') -> bool:
        """Stream a running search to one more watcher, from the start.

        The log so far is replayed before live events, so a page that comes
        back mid-run reads the whole story rather than joining silently.
        """
        with self._registry_lock:
            live = self._live.get(workspace_id)
        if live is None or live.done:
            return False
        requested_scope = str(source_group_key or '').strip()
        if live.source_group_key != requested_scope:
            await emit({'type': 'error', 'code': 'search_scope_mismatch',
                        'msg': 'การค้นหาที่ค้างอยู่เป็นคนละกลุ่ม Product'})
            await emit({'type': 'done', 'count': 0, 'not_found': []})
            return False
        queue: asyncio.Queue = asyncio.Queue()
        for message in list(live.history):
            queue.put_nowait(message)
        live.subscribers.add(queue)
        try:
            while True:
                message = await queue.get()
                if message is None:
                    break
                await emit(message)
        except Exception:  # noqa: BLE001 - this watcher left; the run carries on
            pass
        finally:
            live.subscribers.discard(queue)
        return True

    def resolve_headed(self, wants_headed: bool) -> bool:
        """Whether this run may open a watchable window.

        A headed browser needs a display the server can draw on, which only a
        local run has. A hosted server refuses regardless of what the client
        asks for, so a forged flag cannot stall a search on a missing display.
        """
        return bool(wants_headed) and self._settings.app_env != 'production'

    async def start(self, user_id: str, workspace_id: str,
                    request_data: dict, emit: Emit) -> bool:
        source_group_key = str(
            request_data.get('source_group_key') or '').strip()
        with self._registry_lock:
            live = self._live.get(workspace_id)
            busy = workspace_id in self._starting or workspace_id in self._deleting
            if live is None and not busy:
                self._starting.add(workspace_id)

        if live is not None:
            if live.source_group_key != source_group_key:
                await emit({'type': 'error', 'code': 'search_scope_mismatch',
                            'msg': 'การค้นหาที่ค้างอยู่เป็นคนละกลุ่ม Product'})
                await emit({'type': 'done', 'count': 0, 'not_found': []})
                return False
            return True
        if busy:
            await emit({
                'type': 'error', 'code': 'workspace_busy',
                'msg': 'workspace กำลังใช้งานอยู่',
            })
            await emit({'type': 'done', 'count': 0, 'not_found': []})
            return False

        try:
            return await self._start_reserved(
                user_id, workspace_id, request_data, emit)
        finally:
            with self._registry_lock:
                self._starting.discard(workspace_id)

    async def _start_reserved(self, user_id: str, workspace_id: str,
                              request_data: dict, emit: Emit) -> bool:
        """Set a search going as a task of its own. True if one is now running.

        Everything that can refuse the run — no workspace, no Aztek session, a
        malformed request — is settled here and reported to the caller, so the
        detached task only ever contains work that is actually going to happen.
        """
        source_group_key = str(
            request_data.get('source_group_key') or '').strip()
        game = str(request_data.get('game') or '')
        web_mode = request_data.get('web_mode')
        wants_headed = bool(request_data.get('headed'))
        headed = self.resolve_headed(wants_headed)

        # 1. Load owned workspace, snapshot its data, and decrypt the session.
        with self._database.session() as db:
            repository = WorkspaceRepository(db)
            try:
                workspace = repository.get_owned(user_id, workspace_id)
            except WorkspaceNotFound:
                await emit({'type': 'error', 'code': 'workspace_not_found',
                            'msg': 'ไม่พบงาน Item Finder นี้'})
                return False
            mode = workspace.mode
            criteria = list(workspace.criteria)
            occurrences = list(workspace.occurrences)
            kept = list(workspace.results)
            all_occurrences = list(occurrences)
            previous_results = list(kept)
            if not web_mode:
                web_mode = None
            user = db.get(User, user_id)
            try:
                storage_state = self._aztek.load_storage_state(db, user)
            except InvalidEncryptedState:
                storage_state = None

        if source_group_key:
            criteria = item_service.rows_for_source_group(
                criteria, source_group_key)
            occurrences = item_service.rows_for_source_group(
                occurrences, source_group_key)
            kept = item_service.rows_for_source_group(
                kept, source_group_key)
            if not criteria:
                await emit({'type': 'error', 'code': 'source_group_not_found',
                            'msg': 'ไม่พบรายการ Item Finder ของ Product กลุ่มนี้'})
                await emit({'type': 'done', 'count': 0, 'not_found': []})
                return False

        # 2. A connected Aztek session is required before any browser launch.
        if storage_state is None:
            await emit({'type': 'error', 'code': 'aztek_session_required',
                        'msg': 'ยังไม่ได้เชื่อมเซสชัน Aztek — ไปที่หน้า /account'})
            await emit({'type': 'done', 'count': 0, 'not_found': []})
            return False

        # 3. A retry runs only the rows that came back empty, and keeps what the
        # first pass found. A full run starts clean — its results are invalid
        # from the moment it begins, even if it later fails.
        only_missing = bool(request_data.get('only_missing'))
        if only_missing:
            criteria = item_service.missing_criteria(criteria, kept)
            if not criteria:
                await emit({'type': 'log', 'level': 'SUCCESS',
                            'msg': 'ไม่มีรายการที่หาไม่เจอแล้ว — ไม่ต้องค้นซ้ำ'})
                await emit({'type': 'done', 'count': len(kept), 'not_found': []})
                return False
            await emit({'type': 'log', 'level': 'STEP',
                        'msg': 'ค้นซ้ำเฉพาะที่หาไม่เจอ %d รายการ (ผลเดิม %d รายการยังอยู่)'
                               % (len(criteria), len(kept))})
        else:
            kept = []
            cleared_results = (
                item_service.replace_results_for_source_group(
                    previous_results, [], source_group_key, all_occurrences)
                if source_group_key else [])
            with self._database.session() as db:
                WorkspaceRepository(db).save_results(
                    user_id, workspace_id, game=game,
                    results=cleared_results, not_found=[])

        if wants_headed and not headed:
            await emit({'type': 'log', 'level': 'WARNING',
                        'msg': 'เซิร์ฟเวอร์นี้ไม่มีหน้าจอ — ค้นหาแบบไม่เปิดหน้าต่างแทน'})

        # 4. Validate the search request before creating a job.
        try:
            data = search_runner.build_search_data(
                game, criteria, web_mode, mode=mode, headed=headed)
        except Exception as error:
            await emit({'type': 'log', 'msg': str(error), 'level': 'ERROR'})
            await emit({'type': 'done', 'count': 0, 'not_found': []})
            return False

        # 5. Persist a queued job, then run it as a task of the application.
        with self._database.session() as db:
            job = Job(owner_user_id=user_id, workspace_id=workspace_id,
                      tool='item_finder', status='queued',
                      config={'game': game, 'mode': mode,
                              'web_mode': web_mode or '', 'headed': headed,
                              'only_missing': only_missing,
                              'source_group_key': source_group_key})
            db.add(job)
            db.flush()
            job_id = job.id

        live = LiveSearch(job_id, None, source_group_key)
        finder_failed = False
        try:
            live.finder = search_runner.HeadlessFinder(
                lambda msg, level='INFO': live.publish(
                    {'type': 'log', 'msg': msg, 'level': level}),
                lambda item: live.publish(
                    {'type': 'result', 'item': search_runner.result_view(item)}),
                lambda cur, total, name: live.publish(
                    {'type': 'progress', 'cur': cur, 'total': total, 'name': name}),
                occurrences=occurrences,
                on_reset=lambda: live.publish({'type': 'reset_results'}),
            )
        except BaseException as error:
            self._fail_unstarted_job(job_id, error)
            finder_failed = True
        if finder_failed:
            await self._emit_start_failed(emit)
            return False
        live.publish({'type': 'job', 'job_id': job_id, 'status': 'queued'})
        with self._registry_lock:
            self._live[workspace_id] = live
            self._starting.discard(workspace_id)
        # Not awaited: the run outlives this call, and the caller goes on to
        # attach to it like any other watcher.
        scheduler_failed = False
        try:
            asyncio.ensure_future(
                self._drive(live, user_id, workspace_id, job_id, game, data,
                            storage_state, kept, occurrences, previous_results,
                            all_occurrences, source_group_key))
        except BaseException as error:
            try:
                self._fail_unstarted_job(job_id, error)
            finally:
                with self._registry_lock:
                    if self._live.get(workspace_id) is live:
                        self._starting.add(workspace_id)
                        self._live.pop(workspace_id, None)
                live.finish()
            scheduler_failed = True
        if scheduler_failed:
            await self._emit_start_failed(emit)
            return False
        return True

    async def _drive(self, live: LiveSearch, user_id, workspace_id, job_id,
                     game, data, storage_state, kept=(), occurrences=(),
                     previous_results=(), all_occurrences=(),
                     source_group_key='') -> None:
        """Run one search to its end and write down what happened.

        Nothing in here depends on anyone watching: the job row and the results
        are recorded whether the page that started it is still open or not.
        """
        finder = live.finder
        log_lines: list[str] = []
        outcome = {'status': 'failed', 'code': None, 'reason': None,
                   'results': [], 'not_found': []}

        def say(message):
            if message.get('type') == 'log' and len(log_lines) < _MAX_LOG_LINES:
                log_lines.append('%s: %s' % (
                    message.get('level', 'INFO'), message.get('msg', '')))
            live.publish(message)

        try:
            async with self._browser_gate.slot():
                say({'type': 'job', 'job_id': job_id, 'status': 'running'})
                self._mark_job_running(job_id)
                await finder.run(data, storage_state)
            # Persist the same view that was streamed to the browser so a
            # workspace reload keeps every derived field (params, groups, and
            # the name_mismatch highlight flag).
            fresh = [search_runner.result_view(row) for row in finder._results]
            # A retry only ran the rows that came back empty, so what the first
            # pass found has to be folded back in — and put back in document
            # order, or the newcomers would pile up at the bottom.
            scoped_results = (
                item_service.merge_found(kept, fresh, occurrences) if kept
                else fresh)
            outcome['results'] = (
                item_service.replace_results_for_source_group(
                    previous_results, scoped_results, source_group_key,
                    all_occurrences)
                if source_group_key else scoped_results)
            outcome['not_found'] = list(finder._not_found)
            outcome['status'] = 'cancelled' if finder._cancel else 'done'
            streamed_results = scoped_results if source_group_key else outcome['results']
            if kept:
                say({'type': 'reset_results'})
                for row in streamed_results:
                    say({'type': 'result', 'item': row})
            say({'type': 'done', 'count': len(streamed_results),
                 'not_found': outcome['not_found']})
        except search_runner.AztekSessionExpired as error:
            outcome['code'] = 'aztek_session_expired'
            outcome['reason'] = str(error)
            say({'type': 'error', 'code': 'aztek_session_expired',
                 'msg': str(error)})
            say({'type': 'done', 'count': 0, 'not_found': []})
        except core.BrowserBusy as error:
            outcome['code'] = 'browser_busy'
            outcome['reason'] = str(error)
            say({'type': 'log', 'msg': str(error), 'level': 'ERROR'})
            say({'type': 'done', 'count': 0, 'not_found': []})
        except Exception as error:  # noqa: BLE001 - surface as a failed job
            outcome['code'] = 'error'
            outcome['reason'] = str(error)
            say({'type': 'log', 'msg': 'error: %s' % error, 'level': 'ERROR'})
            say({'type': 'done', 'count': 0, 'not_found': []})
        finally:
            try:
                self._finalize(user_id, workspace_id, job_id, game, outcome,
                               log_lines)
            finally:
                # Last of all: until this clears, the workspace reports a search
                # in progress and a second one is refused.
                with self._registry_lock:
                    if self._live.get(workspace_id) is live:
                        self._live.pop(workspace_id, None)
                live.finish()

    def sweep_interrupted_jobs(self) -> int:
        """Fail off jobs from a previous process, at startup.

        A run only exists while the task driving it does, so a job still marked
        running after a restart has nobody left to finish it — and a page would
        wait on it forever.
        """
        from sqlalchemy import select

        with self._database.session() as db:
            stale = db.scalars(
                select(Job).where(Job.status.in_(('queued', 'running')))).all()
            for job in stale:
                job.status = 'failed'
                job.finished_at = utc_now()
                job.result = {'count': 0, 'not_found': [], 'code': 'interrupted',
                              'reason': 'เซิร์ฟเวอร์รีสตาร์ตระหว่างค้นหา'}
            return len(stale)

    def _mark_job_running(self, job_id: str) -> None:
        with self._database.session() as db:
            job = db.get(Job, job_id)
            if job is not None:
                job.status = 'running'
                job.started_at = utc_now()

    def _fail_unstarted_job(self, job_id: str, _error: BaseException) -> None:
        with self._database.session() as db:
            job = db.get(Job, job_id)
            if job is not None:
                job.status = 'failed'
                job.finished_at = utc_now()
                job.result = {
                    'count': 0, 'not_found': [], 'code': 'start_failed',
                    'reason': 'search_start_failed',
                }

    @staticmethod
    async def _emit_start_failed(emit: Emit) -> None:
        await emit({
            'type': 'error', 'code': 'search_start_failed',
            'msg': 'เริ่มการค้นหาไม่สำเร็จ',
        })
        await emit({'type': 'done', 'count': 0, 'not_found': []})

    def _finalize(self, user_id, workspace_id, job_id, game, outcome,
                  log_lines) -> None:
        status = outcome['status']
        with self._database.session() as db:
            job = db.get(Job, job_id)
            if job is not None:
                job.status = status
                job.finished_at = utc_now()
                job.log = log_lines
                job.result = {
                    'count': len(outcome['results']),
                    'not_found': outcome['not_found'],
                    'code': outcome['code'],
                    'reason': outcome['reason'],
                }

            if status in ('done', 'cancelled'):
                WorkspaceRepository(db).save_results(
                    user_id, workspace_id, game=game,
                    results=outcome['results'], not_found=outcome['not_found'])
                user = db.get(User, user_id)
                session = self._aztek_session_for(db, user)
                if session is not None:
                    session.last_validated_at = utc_now()
                if status == 'done':
                    write_audit(
                        db, user_id=user_id, action='item_finder.completed',
                        status='success',
                        summary={'count': len(outcome['results']), 'game': game},
                        tool='item_finder', resource_type='workspace',
                        resource_id=workspace_id)
            else:
                if outcome['code'] == 'aztek_session_expired':
                    user = db.get(User, user_id)
                    self._aztek.mark_expired(db, user)
                    write_audit(
                        db, user_id=user_id, action='aztek.expired',
                        status='failure', tool='aztek',
                        resource_type='aztek_session', resource_id=user_id)
                write_audit(
                    db, user_id=user_id, action='item_finder.failed',
                    status='failure',
                    summary={'game': game, 'reason': outcome['code'] or 'error'},
                    tool='item_finder', resource_type='workspace',
                    resource_id=workspace_id)

    def _aztek_session_for(self, db, user):
        if user is None:
            return None
        # Reuse the service's lookup shape without exposing ciphertext.
        from sqlalchemy import select

        from web.models import AztekSession
        return db.scalar(
            select(AztekSession).where(AztekSession.user_id == user.id))
