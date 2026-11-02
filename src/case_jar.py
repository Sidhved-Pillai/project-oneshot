"""Kill-Bill product-row quantity rules for Vijay's Bisleri invoices."""
import math
import re


def case_jar_totals(items):
    cases = jars = 0.0
    found = False
    for item in items or []:
        item = item.model_dump() if hasattr(item, 'model_dump') else item
        if not isinstance(item, dict):
            continue
        description = str(item.get('description') or '').strip()
        value = item.get('quantity') if item.get('quantity') is not None else item.get('qty')
        match = re.search(r'[-+]?\d*\.?\d+', str(value or '').replace(',', ''))
        if not description or not match:
            continue
        quantity = float(match.group())
        if not math.isfinite(quantity) or quantity < 0:
            continue
        found = True
        if re.search(r'(?<!\d)20[\s.\-]*LTR', description.upper()):
            jars += quantity
        else:
            cases += quantity
    return (cases, jars) if found else (None, None)
