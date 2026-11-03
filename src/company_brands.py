"""Evidence-based Saint Gobain business names; never infer a missing business."""
import json
import re
from difflib import SequenceMatcher


def saint_gobain_brand(value):
    words = re.findall(r'[a-z]+', str(value or '').casefold())
    compact = ''.join(words)
    saint = ('sg' in words or 'saintgobain' in compact or ('saint' in compact and 'gob' in compact)
             or SequenceMatcher(None, ' '.join(words[:2]), 'saint gobain').ratio() >= .78)
    candidates = set()
    for brand in ('Gyproc', 'Weber'):
        token = brand.casefold()
        for word in words:
            if word == token or (len(word) >= 5 and SequenceMatcher(None, word, token).ratio() >= .8):
                # A standalone business name, or a business attached to Saint Gobain.
                if saint or len(words) == 1 or set(words) <= {word, 'business', 'india', 'private', 'limited', 'pvt', 'ltd'}:
                    candidates.add(brand)
    return 'Saint Gobain - ' + candidates.pop() if len(candidates) == 1 else None


def company_brand_update(row):
    if row.get('report_scope') == 'Expense':
        return None
    raw = row.get('dtr_data') or {}
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (TypeError, ValueError):
            return None
    if not isinstance(raw, dict):
        return None
    names = [row.get('company_name'), raw.get('Compnay Name'), raw.get('Company Name'), raw.get('company_name')]
    brands = {brand for name in names if (brand := saint_gobain_brand(name))}
    if len(brands) != 1:
        return None
    company = brands.pop()
    updated = dict(raw)
    updated['Compnay Name'] = company
    for field in ('Company Name', 'company_name'):
        if field in updated:
            updated[field] = company
    if row.get('company_name') == company and raw == updated:
        return None
    return {'company_name': company, 'dtr_data': updated}
