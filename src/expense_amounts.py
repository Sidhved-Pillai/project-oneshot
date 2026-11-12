"""Shared positive expense amounts for the dropdown and its matching predicate."""
import json
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


def currency(value):
    try:
        amount = Decimal(str(value or 0).replace(',', ''))
        return amount.quantize(Decimal('.01'), rounding=ROUND_HALF_UP) if amount.is_finite() else None
    except (ValueError, TypeError, InvalidOperation):
        return None


def expense_amounts(row):
    if row.get('report_scope') != 'Expense' or row.get('is_archived') or row.get('status') == 'Cancelled':
        return set()
    raw = row.get('dtr_data') or {}
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (ValueError, TypeError):
            raw = {}
    categories = raw.get('categories') if isinstance(raw, dict) else None
    if isinstance(categories, dict) and categories:
        amounts = {value for item in categories.values() if (value := currency(item)) is not None and value > 0}
        total = sum((currency(item) or Decimal(0) for item in categories.values()), Decimal(0))
        return amounts | ({total} if total > 0 else set())
    amount = currency(row.get('amount'))
    return {amount} if amount is not None and amount > 0 else set()
