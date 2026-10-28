"""New Item drafts and references: no browser, credentials or mutable originals."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import re
from typing import Any, TypedDict
from uuid import uuid4

GAMES = ('CabalPC TH', 'CabalPC SEA', 'CabalM TH', 'CabalM SEA')
FIELDS = ('name', 'kind', 'option', 'duration', 'item_type', 'tradeable',
          'description', 'image_key')
NUMBERS = ('kind', 'option', 'duration')


def finder_snapshot(workspace) -> str:
    """Bind positional selection to the complete current source, not a UI index."""
    source = {key: getattr(workspace, key) for key in
              ('id', 'game', 'mode', 'criteria', 'results', 'occurrences', 'group_meta')}
    return hashlib.sha256(json.dumps(source, sort_keys=True, ensure_ascii=False,
                                     default=str).encode()).hexdigest()


class Occurrence(TypedDict):
    occurrence_id: str
    original: dict[str, Any]
    amount: str | None
    filename: str
    sheet: str
    row: int | None
    position: int
    group_key: str
    workspace_id: str | None


class Draft(TypedDict):
    draft_id: str
    revision: int
    game: str
    values: dict[str, Any]
    confirmed_fields: list[str]
    occurrences: list[Occurrence]


class FrozenItem(TypedDict):
    draft_id: str
    revision: int
    game: str
    submitted_values: dict[str, Any]
    references: list[dict]
    occurrences: list[Occurrence]
    payload_hash: str


class ActualItem(TypedDict):
    game: str
    item_id: str
    values: dict[str, Any]
    readable_fields: list[str]
    image_present: bool | None
    evidence: dict


class Recheck(TypedDict):
    outcome: str
    incomplete: bool
    differences: list[str]
    per_occurrence: list[dict]
    actual: ActualItem
    image_status: str


def creation_identity(frozen) -> str:
    """Exact creation values only; references and selected records stay separate."""
    return json.dumps([frozen['game'], frozen['submitted_values']], sort_keys=True,
                      ensure_ascii=False)


def text(value):
    if value is None or value == '':
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip() or None


def normalize_values(values: dict) -> dict:
    if set(values) - set(FIELDS):
        raise ValueError('ไม่รู้จักช่องข้อมูล Item')
    if any(isinstance(value, (dict, list, tuple)) or
           (isinstance(value, bool) and key != 'tradeable')
           for key, value in values.items()):
        raise ValueError('ชนิดข้อมูล Item ไม่ถูกต้อง')
    result = {key: text(values.get(key)) for key in FIELDS}
    raw = values.get('tradeable')
    if raw is None or raw == '':
        result['tradeable'] = None
    elif isinstance(raw, bool):
        result['tradeable'] = raw
    elif str(raw).strip().lower() in ('true', 'yes', '1', 'false', 'no', '0'):
        result['tradeable'] = str(raw).strip().lower() in ('true', 'yes', '1')
    else:
        # Keep invalid source data visible and not-ready rather than guessing.
        result['tradeable'] = text(raw)
    return result


def new_draft(game: str, values: dict, occurrence: dict) -> Draft:
    if game not in GAMES:
        raise ValueError('ไม่รองรับเกมนี้')
    original = normalize_values(values)
    submitted = deepcopy(original)
    if original['item_type'] is None:
        submitted['item_type'] = 'GENERAL'
    if original['tradeable'] is None:
        submitted['tradeable'] = False
    occurrence = deepcopy(occurrence)
    occurrence.update(occurrence_id=uuid4().hex, original=original)
    return {'draft_id': uuid4().hex, 'revision': 1, 'game': game,
            'values': submitted, 'confirmed_fields': [], 'occurrences': [occurrence]}


def readiness(draft: Draft) -> list[str]:
    values = draft['values']
    errors = []
    if not isinstance(values.get('name'), str) or not values['name'].strip():
        errors.append('name')
    for key in NUMBERS:
        value = values.get(key)
        if not isinstance(value, str) or not re.fullmatch(r'[0-9]+', value):
            errors.append(key)
    permitted = ('GENERAL', 'CABALPC_PREMIUM') if draft['game'].startswith('CabalPC ') else ('GENERAL',)
    if values.get('item_type') not in permitted:
        errors.append('item_type')
    if not isinstance(values.get('tradeable'), bool):
        errors.append('tradeable')
    for key in ('item_type', 'tradeable'):
        if any(o['original'][key] is None for o in draft['occurrences']):
            if key not in draft['confirmed_fields']:
                errors.append('confirm_' + key)
    return errors


def view_draft(draft: Draft) -> dict:
    result = deepcopy(draft)
    result['errors'] = readiness(draft)
    result['ready'] = not result['errors']
    return result


def group_drafts(drafts: list[Draft]) -> list[Draft]:
    grouped = {}
    for draft in drafts:
        identity = json.dumps([draft['game'], draft['values']], sort_keys=True, ensure_ascii=False)
        if identity in grouped:
            grouped[identity]['occurrences'].extend(deepcopy(draft['occurrences']))
        else:
            grouped[identity] = deepcopy(draft)
    return list(grouped.values())


def freeze_draft(draft: Draft) -> FrozenItem:
    if readiness(draft):
        raise ValueError('ข้อมูล Item ยังไม่พร้อมหรือยังไม่ยืนยันค่าเริ่มต้น')
    references = []
    for occurrence in draft['occurrences']:
        original = deepcopy(occurrence['original'])
        values, provenance = {}, {}
        for key in FIELDS:
            document_value = (original[key] is not None and
                              (key not in NUMBERS or bool(re.fullmatch(r'[0-9]+', str(original[key])))))
            if document_value:
                values[key], provenance[key] = original[key], 'document'
            else:
                values[key] = draft['values'][key]
                provenance[key] = ('confirmed_default' if key in ('item_type', 'tradeable')
                                   and draft['values'][key] == {'item_type': 'GENERAL', 'tradeable': False}[key]
                                   else 'manual' if values[key] is not None else 'missing')
        references.append({'occurrence_id': occurrence['occurrence_id'], 'original': original,
                           'values': values, 'provenance': provenance})
    payload = deepcopy(draft['values'])
    digest = hashlib.sha256(json.dumps([draft['game'], payload], sort_keys=True,
                                      ensure_ascii=False).encode()).hexdigest()
    return {'draft_id': draft['draft_id'], 'revision': draft['revision'], 'game': draft['game'],
            'submitted_values': payload, 'references': references,
            'occurrences': deepcopy(draft['occurrences']), 'payload_hash': digest}


def compare_new_item(frozen: FrozenItem, actual: ActualItem, *,
                     expected_item_id: str) -> Recheck:
    """Compare fresh observed fields with each original/manual reference.

    The authoritative ID comes from the stored creation checkpoint, never from
    the readback itself. This pure boundary makes no claim that a reader/create
    adapter exists or that these inputs came from a live Aztek page.
    """
    differences, incomplete = [], False
    if frozen.get('game') not in GAMES:
        incomplete = True
    if not actual.get('game'):
        incomplete = True
    elif actual['game'] != frozen.get('game'):
        differences.append('game')
    valid_id = lambda value: isinstance(value, str) and re.fullmatch(r'[1-9][0-9]*', value)
    if not valid_id(expected_item_id) or not valid_id(actual.get('item_id')):
        incomplete = True
    elif actual['item_id'] != expected_item_id:
        differences.append('item_id')
    observed = actual.get('values')
    observed = observed if isinstance(observed, dict) else {}
    readable = actual.get('readable_fields')
    readable = set(readable) if isinstance(readable, list) else set()
    submitted = frozen.get('submitted_values') or {}
    references = frozen.get('references') or []
    occurrences = frozen.get('occurrences') or []
    if (not references or not occurrences or
            {r.get('occurrence_id') for r in references} !=
            {o.get('occurrence_id') for o in occurrences}):
        incomplete = True
    image_status = 'not_requested'
    if submitted.get('image_key'):
        image = actual.get('image_present')
        if image is True:
            image_status = 'present_not_content_verified'
        elif image is False:
            image_status = 'missing'
            differences.append('image')
        else:
            image_status = 'unreadable'
            incomplete = True
    identity_differences = list(differences)
    identity_incomplete = incomplete
    compared = []
    for reference in references:
        values = reference.get('values') or {}
        row_differences, missing = list(identity_differences), identity_incomplete
        required = ['name', 'kind', 'option', 'duration', 'item_type', 'tradeable']
        if submitted.get('description') is not None or values.get('description') is not None:
            required.append('description')
        for key in required:
            expected, saved = values.get(key), observed.get(key)
            known = key in readable and expected is not None and saved is not None
            if key in NUMBERS:
                known = (known and not isinstance(saved, bool) and
                         bool(re.fullmatch(r'[0-9]+', str(saved))) and
                         bool(re.fullmatch(r'[0-9]+', str(expected))))
            elif key == 'tradeable':
                known = known and isinstance(expected, bool) and isinstance(saved, bool)
            else:
                known = known and isinstance(expected, str) and isinstance(saved, str)
                if key != 'description':
                    known = known and bool(expected.strip()) and bool(saved.strip())
            if not known:
                missing = True
            elif (int(expected) != int(saved) if key in NUMBERS else expected != saved):
                row_differences.append(key)
        incomplete = incomplete or missing
        for key in row_differences:
            if key not in differences:
                differences.append(key)
        compared.append({'occurrence_id': reference.get('occurrence_id'),
                         'original': deepcopy(reference.get('original') or {}),
                         'reference': deepcopy(values),
                         'provenance': deepcopy(reference.get('provenance') or {}),
                         'submitted': deepcopy(submitted), 'actual': deepcopy(observed),
                         'different': row_differences, 'incomplete': missing,
                         'outcome': 'mismatch' if row_differences else 'failed' if missing else 'passed'})
    return {'outcome': 'mismatch' if differences else 'failed' if incomplete else 'passed',
            'incomplete': incomplete, 'differences': differences, 'per_occurrence': compared,
            'actual': deepcopy(actual), 'image_status': image_status}
