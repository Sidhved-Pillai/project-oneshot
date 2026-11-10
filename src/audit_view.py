"""Readable audit events and safe, field-level snapshot comparisons."""
import datetime as dt
import json
from zoneinfo import ZoneInfo

IGNORED = {'id', 'request_number', 'batch_id', 'created_at', 'updated_at', 'source_image'}
LABELS = {'revenue':'Revenue', 'amount':'Amount', 'upi':'UPI', 'notes':'Remarks', 'branch':'Branch', 'status':'Status', 'dtr_data': 'DTR', 'rtgs_data': 'Payment', 'trip_date': 'Date',
          'company_name': 'Company', 'vehicle_number': 'Vehicle', 'created_by': 'Created by',
          'is_archived': 'Archived', 'expense_type': 'Expense heading'}


def object_value(value):
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, dict):
                return parsed
        except (ValueError, TypeError):
            pass
    return value


def flatten(snapshot, prefix=''):
    result = {}
    for key, value in (snapshot or {}).items():
        if key in IGNORED or key.startswith('_'):
            continue
        label = LABELS.get(key, key.replace('_', ' ').capitalize() if '_' in key else key)
        path = f'{prefix} / {label}' if prefix else label
        value = object_value(value)
        if isinstance(value, dict):
            result.update(flatten(value, path))
        else:
            result[path] = value
    return result


def changes(before, after):
    old, new = flatten(before), flatten(after)
    return [(key, old.get(key), new.get(key)) for key in dict.fromkeys([*old, *new])
            if str(old.get(key) or '') != str(new.get(key) or '')]


def event_data(row):
    data = object_value(row.get('details', ''))
    return data if isinstance(data, dict) else {'message': str(data or '')}


def category(row):
    action = row.get('action', '').lower()
    if any(word in action for word in ('report', 'download')):
        return 'Generated Report', 'purple'
    if 'delet' in action:
        return 'Deleted Record', 'red'
    if any(word in action for word in ('creat', 'add', 'restor')):
        return 'Added Record', 'green'
    return 'Updated Record', 'blue'


def module(row):
    data = event_data(row)
    snap = data.get('after') or data.get('before') or {}
    if 'report' in row.get('action', '').lower():
        return 'Reports'
    if snap.get('report_scope') == 'Expense' or 'expense' in row.get('action', '').lower():
        return 'Direct Expenses'
    if any(x in row.get('action', '').lower() for x in ('rtgs', 'upi', 'billtee', 'balance')):
        return 'Payments'
    return 'Records'


def local_time(value):
    if isinstance(value, str):
        value = dt.datetime.fromisoformat(value)
    if not value:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=dt.timezone.utc)
    return value.astimezone(ZoneInfo('Asia/Kolkata'))
