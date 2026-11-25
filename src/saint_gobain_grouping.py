"""One-time grouping of legacy Saint Gobain trips without changing their DTR."""
import json
import re
from collections import Counter, defaultdict

from .company_brands import saint_gobain_brand
from .company_catalog import is_saint_gobain_name, is_unresolved_saint_gobain


BRANDS = ('Saint Gobain - Gyproc', 'Saint Gobain - Weber')


def _dtr(row):
    data = row.get('dtr_data') or {}
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except (TypeError, ValueError):
            return {}
    return data if isinstance(data, dict) else {}


def _text(value):
    return re.sub(r'[^a-z0-9]+', ' ', str(value or '').casefold()).strip()


def _features(row):
    data = _dtr(row)
    source = _text(row.get('from_location') or data.get('From'))
    destination = _text(row.get('to_location') or data.get('To'))
    branch = _text(row.get('branch'))
    invoice = _text(row.get('invoice_number') or data.get('Invoice No.'))
    prefix = re.match(r'[a-z]{3,}|[0-9]{4,}', invoice)
    customer = _text(data.get('Customer Name'))
    return [
        ('customer', customer) if customer else None,
        ('invoice_prefix', prefix.group()[:6]) if prefix else None,
        ('route', source, destination) if source and destination else None,
        ('source', source) if source else None,
        ('destination', destination) if destination else None,
        ('branch', branch) if branch else None,
    ]


def _explicit_brand(row):
    data = _dtr(row)
    # DTR is the source of truth when it contains a business name.
    for key in ('Compnay Name', 'Company Name', 'company_name'):
        brand = saint_gobain_brand(data.get(key))
        if brand:
            return brand
    for key, value in data.items():
        if key not in {'Compnay Name', 'Company Name', 'company_name'} and isinstance(value, str):
            words = re.findall(r'\b(?:gyproc|weber)\b', value.casefold())
            if len(set(words)) == 1 and words:
                return 'Saint Gobain - ' + words[0].capitalize()
    return saint_gobain_brand(row.get('company_name'))


def group_legacy_trips(rows):
    """Return {request_number: (group, reason)} for every unresolved active trip.

    Use explicit DTR evidence first, then patterns of already labelled trips.
    A final majority fallback is necessary because old generic DTRs can contain
    no business-specific evidence at all.
    """
    rows = list(rows)
    evidence = defaultdict(Counter)
    totals = Counter()
    for row in rows:
        data = _dtr(row)
        if not any(is_saint_gobain_name(value) for value in (
                row.get('company_name'), data.get('Compnay Name'), data.get('Company Name'))):
            continue
        brand = _explicit_brand(row)
        if brand not in BRANDS:
            continue
        totals[brand] += 1
        for feature in _features(row):
            if feature:
                evidence[feature][brand] += 1
    assignments = {}
    for row in rows:
        if not is_unresolved_saint_gobain(row):
            continue
        brand = _explicit_brand(row)
        if brand in BRANDS:
            reason = 'explicit DTR or record business'
        else:
            brand = None
            for feature in _features(row):
                if not feature:
                    continue
                scores = evidence[feature]
                if scores['Saint Gobain - Gyproc'] != scores['Saint Gobain - Weber']:
                    brand = max(BRANDS, key=lambda name: scores[name])
                    reason = 'matching historical ' + feature[0]
                    break
            if brand is None:
                brand = max(BRANDS, key=lambda name: (totals[name], -BRANDS.index(name)))
                reason = 'historical majority fallback' if totals else 'no labelled precedent fallback'
        assignments[row['request_number']] = brand, reason
    return assignments
