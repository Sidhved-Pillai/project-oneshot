import datetime as dt
import json

import pandas as pd


PERIOD_EXPENSE_CATEGORIES = ("Insurance", "Vehicle Tax")


def _as_date(value):
    parsed = pd.to_datetime(value, errors="coerce")
    return parsed.date() if not pd.isna(parsed) else None


def normalize_period(value):
    """Return a valid inclusive (start, end) period or None."""
    if isinstance(value, dict):
        start, end = _as_date(value.get("start")), _as_date(value.get("end"))
    elif isinstance(value, (list, tuple)) and len(value) == 2:
        start, end = _as_date(value[0]), _as_date(value[1])
    else:
        return None
    if not start or not end:
        return None
    return (start, end) if start <= end else (end, start)


def serialize_period(value):
    period = normalize_period(value)
    return {"start": period[0].isoformat(), "end": period[1].isoformat()} if period else {}


def expense_periods(record):
    data = record.get("dtr_data") or {}
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except (TypeError, ValueError):
            data = {}
    return data.get("periods", {}) if isinstance(data, dict) else {}


def allocate_expenses_for_period(expense_rows, start_date, end_date):
    """Prorate period expenses and retain ordinary expenses only on their entry date."""
    selected = []
    for source in expense_rows:
        categories = dict(source.get("categories") or {})
        periods = expense_periods(source)
        entry_date = _as_date(source.get("trip_date"))
        allocated = {}
        for category, raw_amount in categories.items():
            amount = float(raw_amount or 0)
            period = normalize_period(periods.get(category)) if category in PERIOD_EXPENSE_CATEGORIES else None
            if period:
                period_start, period_end = period
                overlap_start, overlap_end = max(start_date, period_start), min(end_date, period_end)
                overlap_days = max(0, (overlap_end - overlap_start).days + 1)
                period_days = (period_end - period_start).days + 1
                allocated[category] = amount * overlap_days / period_days
            else:
                allocated[category] = amount if entry_date and start_date <= entry_date <= end_date else 0.0
        if any(abs(value) > 1e-9 for value in allocated.values()):
            copy = {**source, "categories": allocated, "amount": sum(allocated.values())}
            selected.append(copy)
    return selected
