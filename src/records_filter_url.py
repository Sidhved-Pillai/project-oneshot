"""Serialize applied Records filters for browser refreshes."""
import datetime as dt
import json


FIELDS = frozenset({
    'start', 'end', 'record_type', 'branch', 'company', 'vehicle', 'placer',
    'ownership', 'amount', 'heading', 'without_evidence', 'order',
    'lr_number', 'invoice_number',
})


def encode_filters(filters):
    return json.dumps({key: value.isoformat() if isinstance(value, dt.date) else value
                       for key, value in filters.items() if key in FIELDS}, separators=(',', ':'))


def decode_filters(value):
    try:
        parsed = json.loads(value or '{}')
        if not isinstance(parsed, dict):
            return {}
        result = {key: item for key, item in parsed.items() if key in FIELDS}
        for key in ('start', 'end'):
            if key in result:
                result[key] = dt.date.fromisoformat(result[key])
        return result
    except (TypeError, ValueError):
        return {}
