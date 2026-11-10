"""Consistent expense summaries and record editing permissions."""
import json
import math

RECORD_EDITORS = {'Nikhat', 'Shyam', 'Ajit', 'Sid'}


def can_edit_record(user, record):
    return user in RECORD_EDITORS or str(record.get('created_by') or '').strip() == user


def expense_summary(record):
    raw = record.get('dtr_data') or {}
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (TypeError, ValueError):
            return {}
    categories = raw.get('categories') if isinstance(raw, dict) else None
    if not isinstance(categories, dict):
        return {}
    values = {}
    for name, value in categories.items():
        try:
            amount = float(value or 0)
        except (TypeError, ValueError):
            raise ValueError('Expense amounts must be valid numbers.')
        if not math.isfinite(amount) or amount < 0:
            raise ValueError('Expense amounts must be finite and non-negative.')
        values[name] = amount
    return {'expense_type':', '.join(name for name, value in values.items() if value),
            'amount':round(sum(values.values()), 2)}
