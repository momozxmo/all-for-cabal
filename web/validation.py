"""Pure, fail-closed validation for values sent to live Aztek forms."""
from __future__ import annotations

import re
from decimal import Decimal


MAX_DECIMAL_TEXT_LENGTH = 64

POSITIVE_INT_RULE = 'ต้องเป็นจำนวนเต็มมากกว่า 0'
NON_NEGATIVE_INT_RULE = 'ต้องเป็นจำนวนเต็มตั้งแต่ 0 ขึ้นไป'
PLAIN_DECIMAL_RULE = 'ต้องเป็นเลขทศนิยมในรูปแบบปกติ'
STRICT_BOOL_RULE = 'ต้องเป็น true หรือ false แบบ JSON boolean'
TEXT_RULE = 'ต้องเป็นข้อความ'

_POSITIVE = re.compile(r'[1-9][0-9]*\Z')
_NON_NEGATIVE = re.compile(r'(?:0|[1-9][0-9]*)\Z')
_PLAIN_DECIMAL = re.compile(r'(?:0|[1-9][0-9]*)(?:\.[0-9]+)?\Z')


class PayloadValueError(ValueError):
    """A public-safe validation error containing no submitted value."""

    def __init__(self, label: str, rule: str) -> None:
        self.label = label
        self.rule = rule
        self.detail = f'{label} {rule}' if rule else label
        super().__init__(self.detail)


def _integer_text(value: object, label: str, *, pattern: re.Pattern[str],
                  rule: str, max_length: int) -> str:
    if type(value) is int:
        text = str(value)
    elif isinstance(value, str):
        text = value.strip()
    else:
        raise PayloadValueError(label, rule)
    if len(text) > max_length or pattern.fullmatch(text) is None:
        raise PayloadValueError(label, rule)
    return text


def positive_int_text(value: object, label: str, *, max_length: int = 12) -> str:
    return _integer_text(
        value, label, pattern=_POSITIVE, rule=POSITIVE_INT_RULE,
        max_length=max_length)


def non_negative_int_text(
    value: object,
    label: str,
    *,
    max_length: int = 12,
) -> str:
    return _integer_text(
        value, label, pattern=_NON_NEGATIVE, rule=NON_NEGATIVE_INT_RULE,
        max_length=max_length)


def plain_decimal_text(
    value: object,
    label: str,
    *,
    minimum: Decimal,
    maximum: Decimal | None = None,
    places: int | None = None,
    max_length: int = MAX_DECIMAL_TEXT_LENGTH,
) -> str:
    if type(value) is int:
        text = str(value)
    elif isinstance(value, str):
        text = value.strip()
    else:
        raise PayloadValueError(label, PLAIN_DECIMAL_RULE)

    if len(text) > max_length or _PLAIN_DECIMAL.fullmatch(text) is None:
        raise PayloadValueError(label, PLAIN_DECIMAL_RULE)
    if places is not None and '.' in text and len(text.rsplit('.', 1)[1]) > places:
        raise PayloadValueError(label, PLAIN_DECIMAL_RULE)

    number = Decimal(text)
    if not number.is_finite() or number < minimum:
        raise PayloadValueError(label, PLAIN_DECIMAL_RULE)
    if maximum is not None and number > maximum:
        raise PayloadValueError(label, PLAIN_DECIMAL_RULE)

    canonical = format(number, 'f')
    if '.' in canonical:
        canonical = canonical.rstrip('0').rstrip('.')
    return canonical or '0'


def strict_bool(value: object, label: str) -> bool:
    if type(value) is not bool:
        raise PayloadValueError(label, STRICT_BOOL_RULE)
    return value


def optional_text(value: object, label: str, *, max_length: int) -> str:
    if not isinstance(value, str):
        raise PayloadValueError(label, TEXT_RULE)
    text = value.strip()
    if len(text) > max_length:
        raise PayloadValueError(
            label, f'ต้องเป็นข้อความยาวไม่เกิน {max_length} ตัวอักษร')
    return text


__all__ = [
    'MAX_DECIMAL_TEXT_LENGTH',
    'NON_NEGATIVE_INT_RULE',
    'PLAIN_DECIMAL_RULE',
    'POSITIVE_INT_RULE',
    'PayloadValueError',
    'STRICT_BOOL_RULE',
    'TEXT_RULE',
    'non_negative_int_text',
    'optional_text',
    'plain_decimal_text',
    'positive_int_text',
    'strict_bool',
]
