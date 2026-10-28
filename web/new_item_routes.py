"""New Item public API, with shared application auth and existing DB lifecycle."""
import asyncio
import os
import tempfile
from copy import deepcopy
from typing import Any, Literal

from fastapi import Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt
from sqlalchemy.orm import Session

from web.item_service import missing_criteria, parse_workbook_locked
from web.aztek_locator import AztekLocatorError
from web.models import User
from web.new_item_domain import GAMES, compare_new_item, creation_identity, finder_snapshot, new_draft, text
from web.new_item_import import (drafts_from_sheets, new_item_template_bytes,
                                 read_new_item_workbook)
from web.new_item_store import NewItemConflict, NewItemNotFound, NewItemRepository
from web.new_item_media import ImageDecoderUnavailable, MAX_IMAGE_BYTES, validate_image
from web.request_limits import WORKBOOK_BODY_MAX
from web.workspaces import WorkspaceNotFound, WorkspaceRepository


class StrictRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')


class ApplyImport(StrictRequest):
    pending_id: str
    selected_sheets: list[str]
    game: str


class EditDraft(StrictRequest):
    revision: StrictInt = Field(ge=1)
    values: dict[str, Any]
    confirmed_fields: list[str] | None = None


class SelectedDraft(StrictRequest):
    id: str
    revision: StrictInt = Field(ge=1)


class ConfirmDrafts(StrictRequest):
    selected: list[SelectedDraft]
    game: str


class FinderSelection(StrictRequest):
    workspace_id: str
    selected_missing_indexes: list[StrictInt]
    game: str
    snapshot_token: str | None = None


class HandoffSelection(StrictRequest):
    selected_ids: list[str]
    occurrence_ids: list[str]
    game: str


class AcknowledgeProblem(StrictRequest):
    action: Literal['skip', 'continue']
    expected_history_count: StrictInt = Field(ge=0)


class UseExisting(StrictRequest):
    revision: StrictInt = Field(ge=1)
    game: str
    search_id: str
    item_id: str


class CreateDecision(SelectedDraft):
    decision: Literal['create_new']
    search_id: str | None = None


class RunNewItems(StrictRequest):
    selected: list[CreateDecision] = Field(min_length=1, max_length=100)
    game: str
    group_identical: StrictBool = False


class ResolveCreation(StrictRequest):
    revision: StrictInt = Field(ge=1)
    game: str
    item_id: str = Field(pattern=r'^[1-9][0-9]*$')
    expected_history_count: StrictInt = Field(ge=0)


def register_new_item_routes(router, *, require_user, get_db):
    def handle_error(error):
        if isinstance(error, (NewItemNotFound, WorkspaceNotFound)):
            raise HTTPException(404, 'ไม่พบรายการ') from None
        raise HTTPException(409 if isinstance(error, NewItemConflict) else 400, str(error)) from None

    @router.get('/api/new-items/template')
    def template(user: User = Depends(require_user)):
        return Response(new_item_template_bytes(), media_type=
                        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                        headers={'Content-Disposition': 'attachment; filename="new-items.xlsx"'})

    @router.post('/api/new-items/import')
    async def import_preview(file: UploadFile = File(...), game: str = Form(...),
                             mode: str = Form('template'), user: User = Depends(require_user),
                             db: Session = Depends(get_db)):
        if game not in GAMES or mode not in ('template', 'event', 'itemcode', 'shop'):
            raise HTTPException(400, 'เกมหรือโหมดนำเข้าไม่ถูกต้อง')
        if not (file.filename or '').lower().endswith('.xlsx'):
            raise HTTPException(400, 'กรุณาเลือกไฟล์ .xlsx')
        content = await file.read(WORKBOOK_BODY_MAX + 1)
        if len(content) > WORKBOOK_BODY_MAX:
            raise HTTPException(413, 'workbook_too_large')
        path = None
        try:
            with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as stream:
                path = stream.name
                stream.write(content)
            data = await asyncio.to_thread(parse_workbook_locked,
                                            lambda p: read_new_item_workbook(p, mode), path)
            return NewItemRepository(db).preview(user.id, data, game, file.filename, mode)
        except ValueError as error:
            handle_error(error)
        except Exception:
            raise HTTPException(400, 'อ่านไฟล์ New Item ไม่สำเร็จ') from None
        finally:
            if path is not None:
                os.unlink(path)

    @router.post('/api/new-items/import/apply')
    def apply_import(payload: ApplyImport, user: User = Depends(require_user),
                     db: Session = Depends(get_db)):
        repo = NewItemRepository(db)
        try:
            job = repo.owned(user.id, payload.pending_id, 'new_item_import')
            if job.status != 'pending':
                raise NewItemConflict('พรีวิวนี้ถูกนำเข้าแล้ว')
            config = job.config
            if payload.game != config['game']:
                raise ValueError('เกมไม่ตรงกับพรีวิว')
            drafts = drafts_from_sheets(config['data'], payload.selected_sheets,
                                       payload.game, config['filename'])
            repo.claim_preview(user.id, job.id)
            result = repo.add_drafts(user.id, drafts, source_mode=config.get('source_mode', 'template'))
            return result
        except (ValueError, NewItemNotFound) as error:
            handle_error(error)

    @router.get('/api/new-items/drafts')
    def drafts(user: User = Depends(require_user), db: Session = Depends(get_db)):
        return {'drafts': NewItemRepository(db).drafts(user.id)}

    @router.patch('/api/new-items/drafts/{draft_id}')
    def edit(draft_id: str, payload: EditDraft, user: User = Depends(require_user),
             db: Session = Depends(get_db)):
        try:
            return NewItemRepository(db).edit(user.id, draft_id, payload.revision,
                                              payload.values, payload.confirmed_fields)
        except (ValueError, NewItemNotFound) as error:
            handle_error(error)

    @router.post('/api/new-items/confirm')
    def confirm(payload: ConfirmDrafts, user: User = Depends(require_user),
                db: Session = Depends(get_db)):
        try:
            return NewItemRepository(db).confirm(user.id, payload.selected, payload.game)
        except (ValueError, NewItemNotFound) as error:
            handle_error(error)

    @router.post('/api/new-items/drafts/{draft_id}/image')
    async def attach_image(draft_id: str, revision: int = Form(..., ge=1), file: UploadFile = File(...),
                           user: User = Depends(require_user), db: Session = Depends(get_db)):
        repo = NewItemRepository(db)
        try:
            repo.editable(user.id, draft_id, revision)
            content = await file.read(MAX_IMAGE_BYTES + 1)
            if len(content) > MAX_IMAGE_BYTES:
                raise HTTPException(413, 'รูปต้องไม่เกิน 5 MB')
            metadata = await asyncio.to_thread(validate_image, content, file.content_type)
            return repo.attach_image(user.id, draft_id, revision, content, metadata, file.filename)
        except ImageDecoderUnavailable:
            raise HTTPException(503, 'ตัวตรวจรูปยังไม่พร้อม กรุณาใช้ environment ที่ตั้งค่าไว้สำหรับรูป') from None
        except (ValueError, NewItemNotFound) as error:
            handle_error(error)

    @router.get('/api/new-items/drafts/{draft_id}/image')
    def attached_image(draft_id: str, user: User = Depends(require_user), db: Session = Depends(get_db)):
        repo = NewItemRepository(db)
        try:
            stored = repo.verified_image(user.id, repo.owned(user.id, draft_id))
            if stored is None:
                raise NewItemNotFound()
            content, media_type = stored
            return Response(content, media_type=media_type, headers={
                'Cache-Control': 'private, no-store', 'X-Content-Type-Options': 'nosniff',
                'Cross-Origin-Resource-Policy': 'same-origin'})
        except (ValueError, NewItemNotFound) as error:
            handle_error(error)

    @router.delete('/api/new-items/drafts/{draft_id}/image')
    def remove_image(draft_id: str, revision: int = Query(..., ge=1),
                     user: User = Depends(require_user), db: Session = Depends(get_db)):
        try:
            return NewItemRepository(db).remove_image(user.id, draft_id, revision)
        except (ValueError, NewItemNotFound) as error:
            handle_error(error)

    @router.post('/api/new-items/from-finder')
    def from_finder(payload: FinderSelection, user: User = Depends(require_user),
                    db: Session = Depends(get_db)):
        try:
            workspace = WorkspaceRepository(db).get_owned(user.id, payload.workspace_id)
            if payload.game not in GAMES or workspace.game != payload.game:
                raise ValueError('เกมไม่ตรงกับพื้นที่ทำงาน')
            if payload.snapshot_token != finder_snapshot(workspace):
                raise NewItemConflict('รายการต้นทางเปลี่ยนแล้ว กรุณาโหลดพื้นที่งานใหม่ก่อนเลือก')
            missing = missing_criteria(workspace.criteria, workspace.results)
            indexes = payload.selected_missing_indexes
            if not indexes or len(indexes) != len(set(indexes)) or any(
                    i < 0 or i >= len(missing) for i in indexes):
                raise ValueError('กรุณาเลือกรายการไม่พบที่มีอยู่และไม่ซ้ำ')
            drafts = []
            for index in indexes:
                criterion = missing[index]
                def key(row):
                    return tuple(text(row.get(k)) for k in ('kind', 'opt', 'dur', 'name'))
                rows = [(pos, row) for pos, row in enumerate(workspace.occurrences or [])
                        if key(row) == key(criterion)]
                if not rows:
                    rows = [(index, criterion)]
                for pos, row in rows:
                    reference = row.get('document_reference') or {}
                    values = {k: reference.get(k, row.get(source)) for k, source in
                              [('name', 'name'), ('kind', 'kind'), ('option', 'opt'), ('duration', 'dur')]}
                    keys = row.get('group_keys') or ['']
                    for group in keys:
                        drafts.append(new_draft(payload.game, values, {
                            'workspace_id': workspace.id, 'filename': workspace.filename,
                            'sheet': row.get('source_sheet') or reference.get('sheet') or '',
                            'row': row.get('source_row') or reference.get('source_row'),
                            'amount': text(row.get('amt')), 'group_key': group, 'position': pos,
                            'downstream': {key: deepcopy(row[key]) for key in
                                           ('rate', 'tier', 'document_reference') if key in row}}))
            return NewItemRepository(db).add_drafts(user.id, drafts, source_mode=workspace.mode)
        except (ValueError, WorkspaceNotFound) as error:
            handle_error(error)

    @router.get('/api/new-items/history')
    def history(user: User = Depends(require_user), db: Session = Depends(get_db)):
        return {'rows': NewItemRepository(db).history(user.id)}

    @router.post('/api/new-items/handoff')
    def handoff(payload: HandoffSelection, user: User = Depends(require_user),
                db: Session = Depends(get_db)):
        try:
            return NewItemRepository(db).handoff_passed(
                user.id, payload.selected_ids, payload.occurrence_ids, payload.game)
        except (ValueError, NewItemNotFound, WorkspaceNotFound) as error:
            handle_error(error)

    @router.post('/api/new-items/run')
    async def run_new_items(payload: RunNewItems, request: Request,
                            user: User = Depends(require_user), db: Session = Depends(get_db)):
        from web import new_item_runner
        repo = NewItemRepository(db)
        try:
            if len({entry.id for entry in payload.selected}) != len(payload.selected):
                raise ValueError('กรุณาเลือกร่างที่ไม่ซ้ำ')
            def prepare_all():
                prepared = []
                identities = set()
                for entry in payload.selected:
                    db.refresh(repo.owned(user.id, entry.id))
                    job, frozen = repo.confirmed_checkpoint(user.id, entry.id, entry.revision, payload.game)
                    key = creation_identity(frozen)
                    if key in identities and not payload.group_identical:
                        raise NewItemConflict('ร่างที่เลือกมีค่าที่ใช้สร้างเหมือนกัน ห้ามสร้างซ้ำ ให้เลือกหนึ่งรายการแล้วใช้ ID เดิมกับแถวอื่น')
                    identities.add(key)
                    repo.require_current_search(job, frozen, entry.search_id)
                    image = repo.verified_image(user.id, job)
                    new_item_runner.validate_create_scope(frozen)
                    prepared.append((entry.id, frozen, image))
                repo.require_acknowledged_problems(user.id, payload.game)
                return prepared

            prepare_all()  # The whole selected scope must be valid before any browser work.
            storage = request.app.state.aztek_session_service.load_storage_state(db, user)
            if storage is None:
                raise NewItemConflict('เซสชัน Aztek หมดอายุ กรุณาเชื่อมใหม่')
            async with request.app.state.browser_gate.slot():
                prepared = prepare_all()  # Reject stale/duplicate work after waiting for the gate.
                groups = {}
                for identity, frozen, image in prepared:
                    groups.setdefault(creation_identity(frozen), []).append((identity, frozen, image))
                items, processed = [], set()
                searches = {entry.id: entry.search_id for entry in payload.selected}
                for group in groups.values():
                    identity, first, image = group[0]
                    members = [(key, snapshot) for key, snapshot, _ in group]
                    frozen = deepcopy(first)
                    frozen['references'] = [deepcopy(ref) for _, f in members for ref in f['references']]
                    frozen['occurrences'] = [deepcopy(row) for _, f in members for row in f['occurrences']]
                    attempt_id = None

                    def on_submit():
                        nonlocal attempt_id
                        for key, snapshot, member_image in group:
                            job = repo.owned(user.id, key)
                            db.refresh(job)
                            repo.require_current_search(job, snapshot, searches[key])
                            if repo.verified_image(user.id, job) != member_image:
                                raise NewItemConflict('รูปของร่างเปลี่ยนแล้ว กรุณาโหลดใหม่')
                        attempt_id = repo.claim_submission_group(user.id, members)

                    def on_saved(item_id, detail_url):
                        repo.record_response_receipt_group(user.id, members, attempt_id, item_id)
                        repo.finish_submission_group(user.id, members, attempt_id,
                                                     item_id=item_id, detail_url=detail_url)

                    try:
                        checked = await new_item_runner.create_new_item(
                            frozen, storage_state=storage, image=image,
                            on_submit=on_submit, on_saved=on_saved)
                    except Exception:
                        job = repo.owned(user.id, identity)
                        db.refresh(job)
                        if job.status == 'submitting' and attempt_id:
                            results = repo.finish_submission_group(user.id, members, attempt_id)
                            items.extend({'id': key, 'result': result} for key, result in results.items())
                            processed.update(results)
                            break
                        if job.status != 'saved' or not attempt_id:
                            raise NewItemConflict(
                                'ยังไม่ได้ส่งบันทึก: ยืนยันฟอร์มหรือคำขอไม่ได้ ร่างยังอยู่') from None
                        _, _, item_id, _ = repo.saved_checkpoint(user.id, identity)
                        checked = compare_new_item(frozen, {
                            'game': frozen['game'], 'item_id': item_id, 'values': {},
                            'readable_fields': [], 'image_present': None, 'evidence': {}
                        }, expected_item_id=item_id)
                        checked['error'] = 'บันทึกได้ ID แล้ว แต่อ่านกลับไม่ครบ ห้ามสร้างซ้ำ'
                    group_items = []
                    try:
                        for key, original in members:
                            _, _, item_id, detail_url = repo.saved_checkpoint(user.id, key)
                            member_check = compare_new_item(original, checked.get('actual') or {}, expected_item_id=item_id)
                            if checked.get('error'):
                                member_check['error'] = checked['error']
                            result = repo.append_recheck(user.id, key, member_check, frozen=original,
                                                         item_id=item_id, detail_url=detail_url)
                            group_items.append({'id': key, 'result': result})
                        db.commit()
                    except Exception:
                        db.rollback()
                        raise
                    items.extend(group_items)
                    processed.update(key for key, _ in members)
                    if any(row['result']['recheck']['outcome'] != 'passed' or
                           row['result']['recheck']['incomplete'] for row in group_items):
                        break
                return {'items': items, 'remaining_ids': [entry.id for entry in payload.selected if entry.id not in processed]}
        except (ValueError, NewItemNotFound) as error:
            handle_error(error)

    @router.post('/api/new-items/search')
    async def search_existing(payload: ConfirmDrafts, request: Request,
                              user: User = Depends(require_user), db: Session = Depends(get_db)):
        from web import new_item_runner
        repo = NewItemRepository(db)
        try:
            if not payload.selected or len({r.id for r in payload.selected}) != len(payload.selected):
                raise ValueError('กรุณาเลือกร่างที่ไม่ซ้ำ')
            for entry in payload.selected:
                repo.confirmed_checkpoint(user.id, entry.id, entry.revision, payload.game)
            storage = request.app.state.aztek_session_service.load_storage_state(db, user)
            if storage is None:
                raise NewItemConflict('เซสชัน Aztek หมดอายุ กรุณาเชื่อมใหม่')
            async with request.app.state.browser_gate.slot():
                prepared = []
                for entry in payload.selected:
                    db.refresh(repo.owned(user.id, entry.id))
                    _, frozen = repo.confirmed_checkpoint(user.id, entry.id, entry.revision, payload.game)
                    prepared.append((entry.id, frozen))
                found = []
                for identity, frozen in prepared:
                    try:
                        candidates = await new_item_runner.search_existing_new_items(frozen, storage_state=storage)
                    except Exception:
                        raise NewItemConflict('ค้นหา Item เดิมไม่สำเร็จหรือยืนยันลิงก์ไม่ได้ ร่างยังอยู่และไม่มีการสร้าง') from None
                    found.append((identity, frozen, candidates))
                return {'searches': [repo.record_search(user.id, identity, frozen, candidates)
                                     for identity, frozen, candidates in found]}
        except (ValueError, NewItemNotFound) as error:
            handle_error(error)

    @router.post('/api/new-items/{draft_id}/use-existing')
    async def use_existing(draft_id: str, payload: UseExisting, request: Request,
                           user: User = Depends(require_user), db: Session = Depends(get_db)):
        from web import new_item_runner
        repo = NewItemRepository(db)
        arguments = (user.id, draft_id, payload.revision, payload.game, payload.search_id, payload.item_id)
        try:
            repo.existing_candidate(*arguments)
            storage = request.app.state.aztek_session_service.load_storage_state(db, user)
            if storage is None:
                raise NewItemConflict('เซสชัน Aztek หมดอายุ กรุณาเชื่อมใหม่')
            async with request.app.state.browser_gate.slot():
                db.refresh(repo.owned(user.id, draft_id))
                _, frozen, candidate = repo.existing_candidate(*arguments)
                try:
                    checked = await new_item_runner.read_existing_new_item(
                        frozen, item_id=payload.item_id, detail_url=candidate['detail_url'], storage_state=storage)
                except Exception:
                    raise NewItemConflict('อ่านยืนยัน Item เดิมไม่สำเร็จ ร่างยังอยู่และไม่มีการสร้าง') from None
                db.refresh(repo.owned(user.id, draft_id))
                return repo.use_existing(*arguments, checked)
        except (ValueError, NewItemNotFound) as error:
            handle_error(error)

    @router.post('/api/new-items/{draft_id}/resolve')
    async def resolve_creation(draft_id: str, payload: ResolveCreation, request: Request,
                               user: User = Depends(require_user), db: Session = Depends(get_db)):
        from web import new_item_runner
        repo = NewItemRepository(db)
        args = (user.id, draft_id, payload.revision, payload.game, payload.item_id,
                payload.expected_history_count)
        try:
            _, frozen = repo.receipt_checkpoint(*args)
            new_item_runner.validate_create_scope(frozen)
            storage = request.app.state.aztek_session_service.load_storage_state(db, user)
            if storage is None:
                raise NewItemConflict('เซสชัน Aztek หมดอายุ กรุณาเชื่อมใหม่')
            async with request.app.state.browser_gate.slot():
                detail_url = new_item_runner.saved_detail_url(payload.game, payload.item_id)
                frozen = repo.resolve_response_receipt(*args, detail_url)
                try:
                    checked = await new_item_runner.read_existing_new_item(
                        frozen, item_id=payload.item_id, detail_url=detail_url, storage_state=storage)
                except Exception as error:
                    checked = compare_new_item(frozen, {
                        'game': frozen['game'], 'item_id': payload.item_id, 'values': {},
                        'readable_fields': [], 'image_present': None, 'evidence': {}
                    }, expected_item_id=payload.item_id)
                    checked['error'] = (str(error) if isinstance(error, AztekLocatorError) else
                                        'กู้ Item ID ได้จากคำตอบเดิม แต่อ่านตรวจไม่สำเร็จ; ไม่มีการสร้างซ้ำ')
                result = repo.append_recheck(user.id, draft_id, checked, frozen=frozen,
                                             item_id=payload.item_id, detail_url=detail_url)
                db.commit()
                return result
        except (ValueError, NewItemNotFound) as error:
            handle_error(error)

    @router.post('/api/new-items/{draft_id}/recheck')
    async def recheck(draft_id: str, payload: StrictRequest, request: Request,
                      user: User = Depends(require_user), db: Session = Depends(get_db)):
        from web import new_item_runner
        repo = NewItemRepository(db)
        try:
            repo.saved_checkpoint(user.id, draft_id)
            storage = request.app.state.aztek_session_service.load_storage_state(db, user)
            if storage is None:
                raise NewItemConflict('เซสชัน Aztek หมดอายุ กรุณาเชื่อมใหม่')
            async with request.app.state.browser_gate.slot():
                db.refresh(repo.owned(user.id, draft_id))
                _, frozen, item_id, detail_url = repo.saved_checkpoint(user.id, draft_id)
                try:
                    checked = await new_item_runner.read_existing_new_item(
                        frozen, item_id=item_id, detail_url=detail_url, storage_state=storage)
                except Exception as error:
                    # Do not persist arbitrary browser exception text: it may contain
                    # request URLs, session material or user-supplied content.
                    checked = compare_new_item(frozen, {
                        'game': frozen['game'], 'item_id': item_id, 'values': {},
                        'readable_fields': [], 'image_present': None, 'evidence': {}
                    }, expected_item_id=item_id)
                    # Reader locator messages contain only fixed control labels,
                    # never raw page values or browser request diagnostics.
                    checked['error'] = (str(error) if isinstance(error, AztekLocatorError) else
                                        'อ่าน Item เดิมไม่สำเร็จ ยังไม่ผ่านการตรวจ; ไม่มีการสร้างซ้ำ')
                result = repo.append_recheck(user.id, draft_id, checked, frozen=frozen,
                                             item_id=item_id, detail_url=detail_url)
                db.commit()
                return result
        except (ValueError, NewItemNotFound) as error:
            handle_error(error)

    @router.post('/api/new-items/{draft_id}/acknowledge')
    def acknowledge(draft_id: str, payload: AcknowledgeProblem, user: User = Depends(require_user),
                    db: Session = Depends(get_db)):
        try:
            return NewItemRepository(db).acknowledge(
                user.id, draft_id, payload.action, payload.expected_history_count)
        except (ValueError, NewItemNotFound) as error:
            handle_error(error)
