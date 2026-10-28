"""Owned, durable New Item drafts on the existing Job storage."""
from copy import deepcopy
import base64
from hashlib import sha256
import re
from uuid import uuid4

from sqlalchemy import select, update

from web.models import Job, utc_now
from web.new_item_domain import (FIELDS, GAMES, compare_new_item, creation_identity, freeze_draft, group_drafts, normalize_values,
                                 view_draft)
from web.workspaces import WorkspaceRepository


class NewItemNotFound(LookupError):
    pass


class NewItemConflict(ValueError):
    pass


class NewItemRepository:
    def __init__(self, session):
        self.session = session

    def owned(self, owner_id, identity, tool='new_item'):
        job = self.session.scalar(select(Job).where(
            Job.id == identity, Job.owner_user_id == owner_id, Job.tool == tool))
        if job is None:
            raise NewItemNotFound()
        return job

    def preview(self, owner_id, data, game, filename, source_mode='template'):
        job = Job(owner_user_id=owner_id, tool='new_item_import', status='pending',
                  config={'schema_version': 1, 'game': game, 'filename': filename,
                          'source_mode': source_mode, 'data': data},
                  result={}, log=[])
        self.session.add(job)
        self.session.flush()
        return {'pending_id': job.id, 'sheets': [
            {'name': s['name'], 'row_count': len(s['rows']), 'hidden': s['hidden']}
            for s in data['sheets']], 'warnings': data['warnings']}

    def add_drafts(self, owner_id, drafts, source_mode='event'):
        source_mode = 'event' if source_mode == 'template' else source_mode
        if source_mode not in ('event', 'itemcode', 'shop'):
            raise ValueError('โหมดเอกสารต้นทางไม่ถูกต้อง')
        queue_id = uuid4().hex
        result = []
        for draft in group_drafts(drafts):
            job = Job(id=draft['draft_id'], owner_user_id=owner_id, tool='new_item',
                      status='draft', config={'schema_version': 1, 'queue_id': queue_id,
                                              'draft': draft, 'source_mode': source_mode}, result={}, log=[])
            self.session.add(job)
            result.append(view_draft(draft))
        self.session.flush()
        return {'queue_id': queue_id, 'drafts': result}

    def claim_preview(self, owner_id, identity):
        changed = self.session.execute(update(Job).where(
            Job.id == identity, Job.owner_user_id == owner_id,
            Job.tool == 'new_item_import', Job.status == 'pending'
        ).values(status='applied'))
        if changed.rowcount != 1:
            raise NewItemConflict('พรีวิวนี้ถูกนำเข้าแล้ว')

    def drafts(self, owner_id):
        jobs = self.session.scalars(select(Job).where(
            Job.owner_user_id == owner_id, Job.tool == 'new_item').order_by(Job.created_at, Job.id))
        return [dict(view_draft(j.config['draft']), state=j.status,
                     image=deepcopy(j.config.get('image_summary'))) for j in jobs]

    def editable(self, owner_id, identity, revision):
        job = self.owned(owner_id, identity)
        if job.status != 'draft' or job.config['draft']['revision'] != revision:
            raise NewItemConflict('ร่างเปลี่ยนแล้วหรือยืนยันแล้ว กรุณาโหลดใหม่')
        return job

    def attach_image(self, owner_id, identity, revision, content, metadata, name):
        job = self.editable(owner_id, identity, revision)
        digest = sha256(content).hexdigest()
        summary = dict(metadata, sha256=digest, name=str(name or 'image').replace('\\', '/').rsplit('/', 1)[-1][:200])
        asset = Job(owner_user_id=owner_id, tool='new_item_image', status='stored',
                    config={'schema_version': 1, 'draft_id': identity, **summary,
                            'content_b64': base64.b64encode(content).decode('ascii')}, result={}, log=[])
        self.session.add(asset)
        self.session.flush()
        config = deepcopy(job.config)
        config['image_asset_id'], config['image_summary'] = asset.id, summary
        config['draft']['values']['image_key'] = 'sha256:' + digest
        config['draft']['revision'] += 1
        changed = self.session.execute(update(Job).where(
            Job.id == identity, Job.owner_user_id == owner_id, Job.status == 'draft',
            Job.config['draft']['revision'].as_integer() == revision).values(config=config))
        if changed.rowcount != 1:
            raise NewItemConflict('ร่างเปลี่ยนระหว่างแนบรูป กรุณาโหลดใหม่')
        self.session.flush()
        return dict(view_draft(config['draft']), image=summary)

    def verified_image(self, owner_id, job):
        key = job.config.get('draft', {}).get('values', {}).get('image_key')
        identity = job.config.get('image_asset_id')
        if not key and not identity:
            return None
        try:
            asset = self.owned(owner_id, identity, 'new_item_image')
            config = asset.config
            content = base64.b64decode(config.get('content_b64', ''), validate=True)
            digest = sha256(content).hexdigest()
            if (config.get('schema_version') != 1 or config.get('draft_id') != job.id or
                    key != 'sha256:' + digest or config.get('sha256') != digest or
                    config.get('size') != len(content) or not 0 < len(content) <= 5_000_000 or
                    config.get('media_type') not in ('image/png', 'image/jpeg', 'image/webp')):
                raise ValueError()
            return content, config['media_type']
        except (ValueError, TypeError, NewItemNotFound):
            raise NewItemConflict('รูปที่อ้างอิงเปลี่ยนหรือไม่ใช่รูปของร่างนี้ กรุณาแนบใหม่') from None

    def remove_image(self, owner_id, identity, revision):
        job = self.editable(owner_id, identity, revision)
        if not job.config.get('image_asset_id'):
            raise NewItemConflict('ร่างนี้ไม่มีรูปที่แนบไว้')
        config = deepcopy(job.config)
        config.pop('image_asset_id', None)
        config.pop('image_summary', None)
        config['draft']['values']['image_key'] = None
        config['draft']['revision'] += 1
        changed = self.session.execute(update(Job).where(
            Job.id == identity, Job.owner_user_id == owner_id, Job.status == 'draft',
            Job.config['draft']['revision'].as_integer() == revision).values(config=config))
        if changed.rowcount != 1:
            raise NewItemConflict('ร่างเปลี่ยนระหว่างนำรูปออก กรุณาโหลดใหม่')
        self.session.flush()
        # Recoverable: remove only the editable reference, not stored image bytes.
        return dict(view_draft(config['draft']), image=None)

    def edit(self, owner_id, identity, revision, changes, confirmed_fields):
        job = self.owned(owner_id, identity)
        if job.status != 'draft' or job.config['draft']['revision'] != revision:
            raise NewItemConflict('ร่างเปลี่ยนแล้วหรือยืนยันแล้ว กรุณาโหลดข้อมูลใหม่')
        if set(changes) - set(FIELDS) or set(confirmed_fields or []) - set(FIELDS):
            raise ValueError('ไม่รู้จักช่องข้อมูล Item')
        if 'image_key' in changes:
            raise ValueError('กรุณาใช้การแนบรูปที่ตรวจสิทธิ์แล้ว')
        config = deepcopy(job.config)
        draft = config['draft']
        draft['values'] = normalize_values(dict(draft['values'], **changes))
        if confirmed_fields is not None:
            draft['confirmed_fields'] = list(confirmed_fields)
        draft['revision'] += 1
        changed = self.session.execute(update(Job).where(
            Job.id == job.id, Job.owner_user_id == owner_id, Job.status == 'draft',
            Job.config['draft']['revision'].as_integer() == revision).values(config=config))
        if changed.rowcount != 1:
            raise NewItemConflict('ร่างเปลี่ยนแล้ว กรุณาโหลดข้อมูลใหม่')
        self.session.flush()
        return view_draft(draft)

    def confirm(self, owner_id, selected, game):
        if not selected or len({entry.id for entry in selected}) != len(selected):
            raise ValueError('กรุณาเลือกรายการที่ไม่ซ้ำ')
        prepared = []
        for entry in selected:
            job = self.owned(owner_id, entry.id)
            draft = job.config['draft']
            if job.status != 'draft' or draft['revision'] != entry.revision:
                raise NewItemConflict('ร่างเปลี่ยนแล้วหรือยืนยันแล้ว')
            if draft['game'] != game:
                raise ValueError('เกมของรายการไม่ตรงกับชุดที่ยืนยัน')
            self.verified_image(owner_id, job)
            prepared.append((job, freeze_draft(draft)))
        for job, frozen in prepared:
            config = deepcopy(job.config)
            config['frozen'] = frozen
            changed = self.session.execute(update(Job).where(
                Job.id == job.id, Job.status == 'draft',
                Job.config['draft']['revision'].as_integer() == frozen['revision']
            ).values(config=config, status='confirmed'))
            if changed.rowcount != 1:
                raise NewItemConflict('ร่างเปลี่ยนระหว่างยืนยัน')
        return {'items': [frozen for job, frozen in prepared]}

    def saved_checkpoint(self, owner_id, identity):
        job = self.owned(owner_id, identity)
        frozen = job.config.get('frozen') or {}
        creation = (job.result or {}).get('creation') or {}
        item_id = creation.get('item_id')
        detail_url = (creation.get('evidence') or {}).get('detail_url')
        if (job.config.get('schema_version') != 1 or creation.get('state') != 'saved' or
                frozen.get('game') not in GAMES or
                frozen.get('game') != job.config.get('draft', {}).get('game') or
                not isinstance(item_id, str) or not re.fullmatch(r'[1-9][0-9]*', item_id) or
                not isinstance(detail_url, str) or not detail_url):
            raise NewItemConflict('ยังไม่มี checkpoint การบันทึกที่ยืนยันเกมและ Item ID ได้')
        return job, deepcopy(frozen), item_id, detail_url

    def confirmed_checkpoint(self, owner_id, identity, revision, game):
        job = self.owned(owner_id, identity)
        frozen = job.config.get('frozen') or {}
        if (job.status != 'confirmed' or job.config.get('schema_version') != 1 or
                game not in GAMES or frozen.get('game') != game or
                frozen.get('revision') != revision or
                job.config.get('draft', {}).get('revision') != revision):
            raise NewItemConflict('ต้องใช้ร่างที่ยืนยันแล้ว เกมและ revision เดิมเท่านั้น')
        return job, deepcopy(frozen)

    def claim_submission(self, owner_id, identity, frozen):
        """Commit the at-most-once claim before the browser forwards its POST."""
        self.session.refresh(self.owned(owner_id, identity))
        job, current = self.confirmed_checkpoint(owner_id, identity, frozen['revision'], frozen['game'])
        if current != frozen or (job.result or {}).get('creation'):
            raise NewItemConflict('รายการเปลี่ยนแล้วหรือเคยส่งบันทึก ห้ามส่งซ้ำ')
        previous_config, previous_result = deepcopy(job.config), deepcopy(job.result)
        creation = {'state': 'submitting', 'source': 'created', 'attempt_id': uuid4().hex,
                    'started_at': utc_now().isoformat()}
        changed = self.session.execute(update(Job).where(
            Job.id == identity, Job.owner_user_id == owner_id, Job.tool == 'new_item',
            Job.status == 'confirmed', Job.config == previous_config, Job.result == previous_result
        ).values(status='submitting', result={'creation': creation}))
        if changed.rowcount != 1:
            raise NewItemConflict('มีการส่งรายการนี้แล้ว ห้ามส่งซ้ำ')
        self.session.commit()
        return creation['attempt_id']

    def require_acknowledged_problems(self, owner_id, game):
        """A new explicit scope cannot silently bypass an unresolved stop."""
        records = self.session.scalars(select(Job).where(
            Job.owner_user_id == owner_id, Job.tool == 'new_item',
            Job.config['frozen']['game'].as_string() == game
        ).execution_options(populate_existing=True))
        for job in records:
            result = job.result or {}
            creation, checked = result.get('creation') or {}, result.get('recheck') or {}
            if (creation.get('state') != 'unconfirmed' and
                    checked.get('outcome') not in ('mismatch', 'failed') and
                    not (creation.get('state') == 'saved' and
                         (not checked or checked.get('incomplete') is not False))):
                continue
            history = job.log or []
            last_check = max((i for i, entry in enumerate(history) if entry.get('recheck')), default=-1)
            acknowledged = any(
                i > last_check and entry.get('event') == 'operator_acknowledgement' and
                entry.get('creation_state') == creation.get('state') and
                entry.get('recheck_outcome') == checked.get('outcome')
                for i, entry in enumerate(history))
            if not acknowledged:
                raise NewItemConflict('มีรายการที่ยังไม่ผ่านหรือยืนยันผลไม่ได้ กรุณารับทราบ/ข้ามก่อนเลือกชุดใหม่')

    def claim_submission_group(self, owner_id, members):
        """Claim every selected identical record in one committed transaction."""
        if len(members) == 1:
            identity, frozen = members[0]
            return self.claim_submission(owner_id, identity, frozen)
        identities = [identity for identity, _ in members]
        if (not identities or len(set(identities)) != len(identities) or
                len({creation_identity(frozen) for _, frozen in members}) != 1):
            raise NewItemConflict('กลุ่มสร้างต้องมีร่างไม่ซ้ำและค่าที่ใช้สร้างตรงกันทุกช่อง')
        creation = {'state': 'submitting', 'source': 'created', 'attempt_id': uuid4().hex,
                    'started_at': utc_now().isoformat(), 'cohort_ids': identities}
        try:
            for identity, frozen in members:
                self.session.refresh(self.owned(owner_id, identity))
                job, current = self.confirmed_checkpoint(owner_id, identity, frozen['revision'], frozen['game'])
                if current != frozen or (job.result or {}).get('creation'):
                    raise NewItemConflict('รายการในกลุ่มเปลี่ยนแล้วหรือเคยส่งบันทึก ห้ามส่งซ้ำ')
                config, result = deepcopy(job.config), deepcopy(job.result)
                changed = self.session.execute(update(Job).where(
                    Job.id == identity, Job.owner_user_id == owner_id, Job.tool == 'new_item',
                    Job.status == 'confirmed', Job.config == config, Job.result == result
                ).values(status='submitting', result={'creation': deepcopy(creation)}))
                if changed.rowcount != 1:
                    raise NewItemConflict('มีการส่งรายการในกลุ่มนี้แล้ว ห้ามส่งซ้ำ')
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
        return creation['attempt_id']

    def finish_submission_group(self, owner_id, members, attempt_id, *, item_id=None, detail_url=None):
        """Save the same proven receipt (or uncertainty) on ALL claimed members."""
        if len(members) == 1:
            identity, _ = members[0]
            return {identity: self.finish_submission(owner_id, identity, attempt_id,
                                                    item_id=item_id, detail_url=detail_url)}
        identities = [identity for identity, _ in members]
        if (not attempt_id or not identities or len(set(identities)) != len(identities) or
                len({creation_identity(frozen) for _, frozen in members}) != 1):
            raise NewItemConflict('checkpoint กลุ่มสร้างไม่ถูกต้อง')
        if item_id is not None and (not isinstance(item_id, str) or
                not re.fullmatch(r'[1-9][0-9]*', item_id) or not detail_url):
            raise NewItemConflict('ผลบันทึกยังไม่มี Item ID ที่ยืนยันได้')
        state, results = ('saved' if item_id is not None else 'unconfirmed'), {}
        try:
            for identity, frozen in members:
                job = self.owned(owner_id, identity)
                self.session.refresh(job)
                previous = deepcopy(job.result or {})
                creation = previous.get('creation') or {}
                if (job.status != 'submitting' or creation.get('state') != 'submitting' or
                        creation.get('attempt_id') != attempt_id or
                        creation.get('cohort_ids') != identities or job.config.get('frozen') != frozen):
                    raise NewItemConflict('checkpoint การส่งในกลุ่มเปลี่ยนแล้ว ห้ามส่งซ้ำ')
                creation = dict(creation, state=state)
                if item_id is not None:
                    creation.update(item_id=item_id, evidence={'detail_url': detail_url,
                        'source': 'create_post_response', 'id_path': 'data.data.id'})
                else:
                    creation['message'] = 'ส่งคำขอแล้วแต่ยังยืนยันผลไม่ได้ ห้ามสร้างซ้ำ ให้ตรวจรายการเดิมก่อน'
                result = dict(previous, creation=creation)
                changed = self.session.execute(update(Job).where(
                    Job.id == identity, Job.owner_user_id == owner_id, Job.tool == 'new_item',
                    Job.status == 'submitting', Job.result == previous, Job.config == job.config
                ).values(status=state, result=result))
                if changed.rowcount != 1:
                    raise NewItemConflict('checkpoint กลุ่มเปลี่ยนระหว่างบันทึก')
                results[identity] = result
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
        return results

    def record_response_receipt_group(self, owner_id, members, attempt_id, item_id):
        """Keep minimal causal proof before the separate saved-state commit."""
        if (not attempt_id or not members or not isinstance(item_id, str) or
                not re.fullmatch(r'[1-9][0-9]*', item_id) or
                len({key for key, _ in members}) != len(members) or
                len({creation_identity(frozen) for _, frozen in members}) != 1):
            raise NewItemConflict('หลักฐานคำตอบของกลุ่มสร้างไม่ถูกต้อง')
        try:
            for identity, frozen in members:
                job = self.owned(owner_id, identity)
                self.session.refresh(job)
                previous = deepcopy(job.result or {})
                creation = previous.get('creation') or {}
                if (job.status != 'submitting' or creation.get('state') != 'submitting' or
                        creation.get('source') != 'created' or creation.get('attempt_id') != attempt_id or
                        creation.get('receipt') or job.config.get('frozen') != frozen or
                        (len(members) > 1 and creation.get('cohort_ids') != [key for key, _ in members])):
                    raise NewItemConflict('รอบส่งเปลี่ยนแล้ว ไม่รับหลักฐานจากรอบอื่น')
                receipt = {'source': 'matched_create_post_response', 'id_path': 'data.data.id',
                           'record_id': item_id, 'game': frozen['game'],
                           'revision': frozen['revision'], 'payload_hash': frozen['payload_hash'],
                           'attempt_id': attempt_id, 'received_at': utc_now().isoformat()}
                updated = self.session.execute(update(Job).where(
                    Job.id == identity, Job.owner_user_id == owner_id, Job.tool == 'new_item',
                    Job.status == 'submitting', Job.result == previous, Job.config == job.config
                ).values(result=dict(previous, creation=dict(creation, receipt=receipt))))
                if updated.rowcount != 1:
                    raise NewItemConflict('รอบส่งเปลี่ยนระหว่างเก็บหลักฐาน')
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise

    def receipt_checkpoint(self, owner_id, identity, revision, game, item_id, history_count):
        """Client IDs are claims only; the captured response must bind this attempt."""
        job = self.owned(owner_id, identity)
        self.session.refresh(job)
        frozen = job.config.get('frozen') or {}
        creation = (job.result or {}).get('creation') or {}
        receipt = creation.get('receipt') or {}
        if (job.config.get('schema_version') != 1 or job.status != 'unconfirmed' or
                creation.get('state') != 'unconfirmed' or creation.get('source') != 'created' or
                frozen.get('game') != game or game not in GAMES or
                job.config.get('draft', {}).get('game') != game or
                frozen.get('revision') != revision or
                len(job.log or []) != history_count or
                not isinstance(item_id, str) or not re.fullmatch(r'[1-9][0-9]*', item_id) or
                receipt.get('source') != 'matched_create_post_response' or
                receipt.get('id_path') != 'data.data.id' or receipt.get('record_id') != item_id or
                not creation.get('attempt_id') or receipt.get('attempt_id') != creation['attempt_id'] or
                receipt.get('game') != game or receipt.get('revision') != revision or
                receipt.get('payload_hash') != frozen.get('payload_hash')):
            raise NewItemConflict('ยังไม่มีหลักฐานคำตอบของรอบส่งนี้ที่ยืนยันเกมและ Item ID ได้ ห้ามสร้างซ้ำ')
        return job, deepcopy(frozen)

    def resolve_response_receipt(self, owner_id, identity, revision, game, item_id, history_count, detail_url):
        job, frozen = self.receipt_checkpoint(owner_id, identity, revision, game, item_id, history_count)
        previous, log = deepcopy(job.result), deepcopy(job.log or [])
        creation = dict(previous['creation'], state='saved', item_id=item_id,
                        resolved_at=utc_now().isoformat(), evidence={
                            'detail_url': detail_url, 'source': 'create_post_response',
                            'id_path': 'data.data.id'})
        result = dict(previous, creation=creation)
        result.pop('recheck', None)  # An old check can never authorize this recovery.
        updated = self.session.execute(update(Job).where(
            Job.id == identity, Job.owner_user_id == owner_id, Job.tool == 'new_item',
            Job.status == 'unconfirmed', Job.result == previous, Job.log == log, Job.config == job.config
        ).values(status='saved', result=result))
        if updated.rowcount != 1:
            raise NewItemConflict('มีการกู้รายการนี้แล้ว กรุณาโหลดสถานะล่าสุด')
        self.session.commit()  # Save proven ID before any new browser read can fail.
        return frozen

    def require_current_search(self, job, frozen, search_id):
        snapshot = job.config.get('search') or {}
        if (not search_id or snapshot.get('search_id') != search_id or
                snapshot.get('draft_id') != job.id or snapshot.get('game') != frozen['game'] or
                snapshot.get('revision') != frozen['revision'] or
                snapshot.get('payload_hash') != frozen['payload_hash']):
            raise NewItemConflict('กรุณาค้นหา Item เดิมและตรวจผลล่าสุดก่อนยืนยันสร้างใหม่')

    def finish_submission(self, owner_id, identity, attempt_id, *, item_id=None, detail_url=None):
        """Persist saved identity or uncertainty, never reset to a runnable draft."""
        job = self.owned(owner_id, identity)
        self.session.refresh(job)
        previous = deepcopy(job.result or {})
        creation = previous.get('creation') or {}
        if (job.status != 'submitting' or creation.get('state') != 'submitting' or
                creation.get('attempt_id') != attempt_id):
            raise NewItemConflict('checkpoint การส่งเปลี่ยนแล้ว ห้ามส่งซ้ำ')
        state = 'unconfirmed'
        creation = dict(creation, state=state)
        if item_id is not None:
            if not isinstance(item_id, str) or not re.fullmatch(r'[1-9][0-9]*', item_id) or not detail_url:
                raise NewItemConflict('ผลบันทึกยังไม่มี Item ID ที่ยืนยันได้')
            state = 'saved'
            creation.update(state=state, item_id=item_id, evidence={
                'detail_url': detail_url, 'source': 'create_post_response', 'id_path': 'data.data.id'})
        else:
            creation['message'] = 'ส่งคำขอแล้วแต่ยังยืนยันผลไม่ได้ ห้ามสร้างซ้ำ ให้ตรวจรายการเดิมก่อน'
        result = dict(previous, creation=creation)
        changed = self.session.execute(update(Job).where(
            Job.id == identity, Job.owner_user_id == owner_id, Job.tool == 'new_item',
            Job.status == 'submitting', Job.result == previous
        ).values(status=state, result=result))
        if changed.rowcount != 1:
            raise NewItemConflict('checkpoint การส่งเปลี่ยนระหว่างบันทึก')
        self.session.commit()
        return result

    def record_search(self, owner_id, identity, frozen, candidates):
        job, current = self.confirmed_checkpoint(owner_id, identity, frozen['revision'], frozen['game'])
        if current != frozen:
            raise NewItemConflict('ร่างเปลี่ยนระหว่างค้นหา')
        previous = deepcopy(job.config)
        snapshot = {'draft_id': identity, 'game': frozen['game'], 'revision': frozen['revision'],
                    'payload_hash': frozen['payload_hash'], 'search_id': uuid4().hex,
                    'candidates': deepcopy(candidates)}
        config = dict(previous, search=snapshot)
        changed = self.session.execute(update(Job).where(
            Job.id == identity, Job.owner_user_id == owner_id, Job.status == 'confirmed',
            Job.config == previous).values(config=config))
        if changed.rowcount != 1:
            raise NewItemConflict('รายการเปลี่ยนระหว่างบันทึกผลค้นหา')
        self.session.flush()
        return snapshot

    def existing_candidate(self, owner_id, identity, revision, game, search_id, item_id):
        job, frozen = self.confirmed_checkpoint(owner_id, identity, revision, game)
        snapshot = job.config.get('search') or {}
        matches = [c for c in snapshot.get('candidates', []) if c.get('item_id') == item_id]
        if (snapshot.get('search_id') != search_id or snapshot.get('game') != game or
                snapshot.get('revision') != revision or
                snapshot.get('payload_hash') != frozen['payload_hash'] or len(matches) != 1):
            raise NewItemConflict('ผลค้นหาหรือ ID ที่เลือกไม่ใช่ผลล่าสุดของร่างนี้')
        return job, frozen, deepcopy(matches[0])

    def use_existing(self, owner_id, identity, revision, game, search_id, item_id, checked):
        job, frozen, candidate = self.existing_candidate(
            owner_id, identity, revision, game, search_id, item_id)
        actual = checked.get('actual') or {}
        evidence = actual.get('evidence') or {}
        if (actual.get('game') != game or actual.get('item_id') != item_id or
                evidence.get('identity_verified') is not True or
                evidence.get('detail_url') != candidate['detail_url']):
            raise NewItemConflict('ยังยืนยันตัวตน Item เดิมจากหน้ารายละเอียดไม่ได้')
        # Recompute from actual instead of accepting any caller's outcome flag.
        verified = compare_new_item(frozen, actual, expected_item_id=item_id)
        previous_config, previous_log = deepcopy(job.config), deepcopy(job.log or [])
        creation = {'state': 'saved', 'source': 'existing', 'item_id': item_id,
                    'evidence': {'detail_url': candidate['detail_url'], 'search_id': search_id}}
        result = {'creation': creation, 'recheck': verified}
        history = [*previous_log, {'event': 'use_existing', 'checked_at': utc_now().isoformat(),
                                  'game': game, 'item_id': item_id, 'recheck': verified}]
        changed = self.session.execute(update(Job).where(
            Job.id == identity, Job.owner_user_id == owner_id, Job.status == 'confirmed',
            Job.config == previous_config, Job.log == previous_log
        ).values(status='saved', result=result, log=history))
        if changed.rowcount != 1:
            raise NewItemConflict('มีการเลือกหรือตรวจรายการนี้ไปแล้ว กรุณาโหลดใหม่')
        self.session.flush()
        return result

    def append_recheck(self, owner_id, identity, checked, *, frozen, item_id, detail_url):
        job = self.owned(owner_id, identity)
        self.session.refresh(job)
        _, current, current_id, current_url = self.saved_checkpoint(owner_id, identity)
        if current != frozen or current_id != item_id or current_url != detail_url:
            raise NewItemConflict('checkpoint เปลี่ยนระหว่างตรวจ กรุณาโหลดข้อมูลใหม่')
        previous_result, previous_log = deepcopy(job.result), deepcopy(job.log or [])
        result = dict(previous_result, recheck=deepcopy(checked))
        history = [*previous_log, {'checked_at': utc_now().isoformat(),
                                 'game': frozen['game'], 'item_id': item_id,
                                 'recheck': deepcopy(checked)}]
        updated = self.session.execute(update(Job).where(
            Job.id == identity, Job.owner_user_id == owner_id, Job.tool == 'new_item',
            Job.result == previous_result, Job.log == previous_log
        ).values(result=result, log=history))
        if updated.rowcount != 1:
            raise NewItemConflict('ผลตรวจเปลี่ยนระหว่างบันทึก กรุณาโหลดข้อมูลใหม่')
        self.session.flush()
        return result

    def history(self, owner_id):
        jobs = self.session.scalars(select(Job).where(
            Job.owner_user_id == owner_id, Job.tool == 'new_item'
        ).order_by(Job.created_at.desc(), Job.id))
        return [{'id': job.id, 'state': job.status,
                 'frozen': deepcopy(job.config.get('frozen')),
                 'search': deepcopy(job.config.get('search')),
                 'result': deepcopy(job.result or {}), 'history': deepcopy(job.log or [])}
                for job in jobs]

    def acknowledge(self, owner_id, identity, action, expected_history_count):
        job = self.owned(owner_id, identity)
        result, history = deepcopy(job.result or {}), deepcopy(job.log or [])
        creation, checked = result.get('creation') or {}, result.get('recheck') or {}
        if len(history) != expected_history_count:
            raise NewItemConflict('ประวัติเปลี่ยนแล้ว กรุณาโหลดผลล่าสุดก่อนรับทราบ')
        if not (creation.get('state') == 'unconfirmed' or
                checked.get('outcome') in ('mismatch', 'failed') or
                (creation.get('state') == 'saved' and
                 (not checked or checked.get('incomplete') is not False))):
            raise NewItemConflict('ยังไม่มีปัญหาที่ต้องรับทราบในรายการนี้')
        if action not in ('skip', 'continue'):
            raise ValueError('การรับทราบไม่ถูกต้อง')
        entry = {'event': 'operator_acknowledgement', 'action': action,
                 'recorded_at': utc_now().isoformat(), 'creation_state': creation.get('state'),
                 'recheck_outcome': checked.get('outcome')}
        updated = self.session.execute(update(Job).where(
            Job.id == identity, Job.owner_user_id == owner_id, Job.tool == 'new_item',
            Job.result == result, Job.log == history
        ).values(log=[*history, entry]))
        if updated.rowcount != 1:
            raise NewItemConflict('ผลเปลี่ยนระหว่างรับทราบ กรุณาโหลดใหม่')
        self.session.flush()
        # Intent only: no state reset, recheck rewrite, queue resume or browser.
        return {'result': result, 'acknowledgement': entry}

    def recover_interrupted(self):
        """Startup only: a dead process cannot finish or safely replay a write."""
        saved = list(self.session.scalars(select(Job).where(
            Job.tool == 'new_item', Job.status == 'saved')))
        for job in saved:
            result = job.result or {}
            creation = result.get('creation') or {}
            if (job.config.get('schema_version') == 1 and creation.get('source') == 'created'
                    and creation.get('state') == 'saved' and not result.get('recheck')):
                _, frozen, item_id, detail_url = self.saved_checkpoint(job.owner_user_id, job.id)
                checked = compare_new_item(frozen, {
                    'game': frozen['game'], 'item_id': item_id, 'values': {},
                    'readable_fields': [], 'image_present': None, 'evidence': {}
                }, expected_item_id=item_id)
                checked['error'] = 'บันทึกได้ ID แล้ว แต่โปรแกรมปิดก่อนตรวจครบ ห้ามสร้างซ้ำ ให้ตรวจรายการเดิม'
                self.append_recheck(job.owner_user_id, job.id, checked, frozen=frozen,
                                    item_id=item_id, detail_url=detail_url)
        records = self.session.scalars(select(Job).where(
            Job.tool == 'new_item', Job.status == 'submitting'))
        recovered = 0
        for job in records:
            previous = deepcopy(job.result or {})
            creation = previous.get('creation') or {}
            if job.config.get('schema_version') != 1 or creation.get('state') != 'submitting':
                continue  # Unknown schema/state needs explicit diagnosis, not a reset.
            history = deepcopy(job.log or [])
            result = dict(previous, creation=dict(creation, state='unconfirmed',
                                                  reason='interrupted'))
            updated = self.session.execute(update(Job).where(
                Job.id == job.id, Job.tool == 'new_item', Job.status == 'submitting',
                Job.result == previous, Job.log == history
            ).values(status='unconfirmed', result=result, log=[*history, {
                'event': 'creation_interrupted', 'recorded_at': utc_now().isoformat(),
                'creation_state': 'unconfirmed'}]))
            recovered += updated.rowcount
        self.session.flush()
        return recovered

    def handoff_passed(self, owner_id, selected_ids, occurrence_ids, game):
        """Materialize only explicit passed selections in a separate Finder workspace."""
        if (game not in GAMES or not selected_ids or not occurrence_ids or
                len(set(selected_ids)) != len(selected_ids) or
                len(set(occurrence_ids)) != len(occurrence_ids)):
            raise ValueError('กรุณาเลือกรายการและแถวอ้างอิงที่ไม่ซ้ำ')
        wanted, available, prepared = set(occurrence_ids), set(), []
        for identity in selected_ids:
            job, frozen, item_id, _ = self.saved_checkpoint(owner_id, identity)
            if frozen['game'] != game:
                raise ValueError('เกมของรายการที่เลือกไม่ตรงกัน')
            checked = (job.result or {}).get('recheck') or {}
            attempts = [entry for entry in (job.log or []) if 'recheck' in entry]
            if (checked.get('outcome') != 'passed' or checked.get('incomplete') is not False or
                    not attempts or attempts[-1].get('recheck') != checked or
                    attempts[-1].get('game') != game or attempts[-1].get('item_id') != item_id):
                raise NewItemConflict('ส่งต่อได้เฉพาะผลตรวจรอบล่าสุดที่ผ่านครบเท่านั้น')
            verified = compare_new_item(frozen, checked.get('actual') or {}, expected_item_id=item_id)
            if verified['outcome'] != 'passed' or verified['incomplete']:
                raise NewItemConflict('ข้อมูลหรือ checkpoint ไม่ตรงกับผลตรวจที่ผ่าน')
            occurrences = frozen['occurrences']
            available.update(o['occurrence_id'] for o in occurrences)
            chosen = [o for o in occurrences if o['occurrence_id'] in wanted]
            if not chosen:
                raise ValueError('ทุกรายการที่เลือกต้องมีแถวอ้างอิงที่เลือกด้วย')
            refs = {r['occurrence_id']: r for r in frozen['references']}
            prepared.extend((item_id, checked['actual']['values'],
                             dict(o, _handoff_scope=o.get('workspace_id') or job.config.get('queue_id') or job.id,
                                  _handoff_mode=job.config.get('source_mode')), refs[o['occurrence_id']])
                            for o in chosen)
        if not wanted <= available:
            raise ValueError('แถวอ้างอิงที่เลือกไม่ได้อยู่ในรายการเหล่านี้')
        repository = WorkspaceRepository(self.session)
        sources = {}
        for _, _, occurrence, _ in prepared:
            source_id = occurrence.get('workspace_id')
            if source_id and source_id not in sources:
                source = repository.get_owned(owner_id, source_id)
                if source.game != game:
                    raise NewItemConflict('เกมของพื้นที่ต้นทางเปลี่ยนแล้ว')
                sources[source_id] = source
        modes = {source.mode for source in sources.values()}
        modes.update(origin['_handoff_mode'] for _, _, origin, _ in prepared if origin['_handoff_mode'])
        if modes - {'event', 'itemcode', 'shop'}:
            raise NewItemConflict('ไม่รู้จักโหมดเอกสารต้นทาง')
        if len(modes) > 1:
            raise ValueError('กรุณาส่งต่อแยกตามโหมดเอกสารต้นทาง')
        # History/selection order is not document order. Keep each source/group's
        # rows in their retained position, independently of newest-first UI history.
        scope_order = {scope: index for index, scope in enumerate(dict.fromkeys(
            entry[2]['_handoff_scope'] for entry in prepared))}
        prepared.sort(key=lambda entry: (
            scope_order[entry[2]['_handoff_scope']], entry[2].get('group_key') or entry[2].get('sheet') or '',
            entry[2].get('position') if isinstance(entry[2].get('position'), int) else 0,
            entry[2].get('row') if isinstance(entry[2].get('row'), int) else 0))
        scopes = {}
        for _, _, origin, _ in prepared:
            key = origin.get('group_key') or origin.get('sheet') or 'New Item'
            scopes.setdefault(key, set()).add(origin['_handoff_scope'])
        rows, occurrences, criteria, groups = [], [], [], {}
        for item_id, actual, origin, reference in prepared:
            raw_group = origin.get('group_key') or origin.get('sheet') or 'New Item'
            group = (origin['_handoff_scope'] + ':' + raw_group
                     if len(scopes[raw_group]) > 1 else raw_group)
            downstream = origin.get('downstream') or {}
            source = sources.get(origin.get('workspace_id'))
            group_meta = ((source.group_meta or {}).get(raw_group) if source else None) or downstream.get('group_meta') or {}
            label = group_meta.get('group') or origin.get('sheet') or raw_group
            amount = origin.get('amount')
            document = dict(deepcopy(reference['values']), filename=origin.get('filename'),
                            sheet=origin.get('sheet'), source_row=origin.get('row'), qty=amount,
                            source_workspace_id=origin.get('workspace_id'))
            # Original Bundle metadata is separate from New Item's comparison
            # reference: rates/tier/quantity are not Item creation fields.
            if downstream.get('document_reference') is not None:
                document = deepcopy(downstream['document_reference'])
            for key in ('rate', 'tier'):
                if key in downstream:
                    document.setdefault(key, downstream[key])
            criterion = {'kind': actual['kind'], 'opt': actual['option'],
                         'dur': actual['duration'], 'name': actual['name']}
            if criterion not in criteria:
                criteria.append(criterion)
            occurrence = dict(criterion, amt=amount, sources=[label], group_keys=[group],
                              source_sheet=origin.get('sheet'), source_row=origin.get('row'),
                              position=origin.get('position'), occurrence_id=origin['occurrence_id'],
                              source_workspace_id=origin.get('workspace_id'), document_reference=document,
                              aztek_id=item_id,
                              **{key: downstream[key] for key in ('rate', 'tier') if key in downstream})
            occurrences.append(occurrence)
            rows.append({'aztek_id': item_id, 'item_name': actual['name'],
                         'item_kind': actual['kind'], 'item_option': actual['option'],
                         'duration_index': actual['duration'], 'sources': [label],
                         'group_keys': [group], 'groups': label, 'amt': amount,
                         'file_name': reference['values'].get('name'),
                         'occurrence_id': origin['occurrence_id'],
                         'new_item_bound': True,
                         **{key: downstream[key] for key in ('rate', 'tier') if key in downstream},
                         'source_workspace_id': origin.get('workspace_id'), 'document_reference': document})
            source = sources.get(origin.get('workspace_id'))
            groups[group] = deepcopy((source.group_meta or {}).get(raw_group, {'group': label})
                                     if source else group_meta or {'group': label})
            groups[group]['group_key'] = group
        destination = repository.create(owner_id, next(iter(modes), 'event'), 'New Item — selected', criteria)
        destination.game, destination.results = game, rows
        destination.occurrences, destination.group_meta = occurrences, groups
        destination.not_found = []
        self.session.flush()
        return {'workspace_id': destination.id, 'game': game, 'count': len(rows)}
