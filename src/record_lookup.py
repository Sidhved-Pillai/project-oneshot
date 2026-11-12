"""Identifier searches use the same punctuation-insensitive values as duplicate checks."""
import json
import re

from .dtr_dates import parse_dtr_date
from .text_normalization import canonical_ownership
from .vehicle_normalization import canonical_vehicle_number
from .vehicle_placer import canonical_vehicle_placer


def normalized_identifier(value):
    return re.sub(r'[^a-z0-9]', '', str(value or '').casefold())


def data(row):
    raw = row.get('dtr_data') or {}
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (TypeError, ValueError):
            return {}
    return raw if isinstance(raw, dict) else {}


def identifier_matches(row, filters):
    raw = data(row)
    lr = row.get('lr_number') or raw.get('LR No.') or ''
    invoice = row.get('invoice_number') or raw.get('Invoice No.') or ''
    return (normalized_identifier(filters.get('lr_number')) in normalized_identifier(lr)
            and normalized_identifier(filters.get('invoice_number')) in normalized_identifier(invoice))


def outside_date_identifier_matches(scoped_rows, filters):
    """Recover targeted matches only; callers must apply access and type restrictions first."""
    if not any(normalized_identifier(filters.get(key)) for key in ('lr_number','invoice_number')):
        return []
    output = []
    for row in scoped_rows:
        if row.get('is_archived') or row.get('status') == 'Cancelled' or not identifier_matches(row, filters):
            continue
        date = parse_dtr_date(row.get('trip_date'))
        if date is None or filters['start'] <= date <= filters['end']:
            continue
        if filters.get('vehicle', 'All') != 'All' and canonical_vehicle_number(row.get('vehicle_number')) != filters['vehicle']:
            continue
        if filters.get('placer', 'All') != 'All' and canonical_vehicle_placer(data(row).get('Veh Placed by')) != filters['placer']:
            continue
        ownership = filters.get('ownership', 'Both')
        if ownership != 'Both' and canonical_ownership(row.get('ownership_type')) != ownership:
            continue
        output.append(row)
    return output
