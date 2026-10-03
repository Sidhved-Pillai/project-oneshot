import datetime as dt
import json

import pandas as pd


TRIP_RECORDS = "Trip Records"
DIRECT_EXPENSES = "Direct Expenses"
RECORD_TYPES = (TRIP_RECORDS, DIRECT_EXPENSES)
SORT_ORDERS = ("Newest first", "Oldest first")


def is_direct_expense(record):
    return record.get("report_scope") == "Expense"


def filter_record_type(records, record_type):
    """Return only trips or direct expenses without altering the source rows."""
    want_expenses = record_type == DIRECT_EXPENSES
    return [record for record in records if is_direct_expense(record) == want_expenses]


def _number(value):
    try:
        return float(str(value or 0).replace(",", ""))
    except (TypeError, ValueError):
        return 0.0


def direct_expense_headings(records):
    """Return the individual populated expense headings available for filtering."""
    headings = set()
    for record in records:
        raw = record.get("dtr_data") or {}
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except (TypeError, ValueError):
                raw = {}
        categories = raw.get("categories", {}) if isinstance(raw, dict) else {}
        headings.update(
            str(name).strip() for name, value in categories.items()
            if str(name).strip() and _number(value) > 0
        )
        if not categories:
            headings.update(
                item.strip() for item in str(record.get("expense_type") or "").split(",")
                if item.strip()
            )
    return sorted(headings, key=str.casefold)


def filter_direct_expenses(records, amount=None, heading="All"):
    """Filter direct expenses by exact total amount and/or populated heading."""
    filtered = list(records)
    if amount is not None:
        filtered = [row for row in filtered if abs(_number(row.get("amount")) - float(amount)) < 0.005]
    if heading != "All":
        filtered = [row for row in filtered if heading in direct_expense_headings([row])]
    return filtered


def sort_records_by_date(records, order):
    """Sort records deterministically by date and then database id."""
    def key(record):
        parsed = pd.to_datetime(record.get("trip_date"), errors="coerce")
        record_date = parsed.date() if not pd.isna(parsed) else dt.date.min
        try:
            record_id = int(record.get("id") or 0)
        except (TypeError, ValueError):
            record_id = 0
        return record_date, record_id

    return sorted(records, key=key, reverse=order == "Newest first")


def has_invoice_evidence(record):
    """Check evidence availability from lightweight metadata, without loading bytes."""
    return bool(
        str(record.get("source_filename") or "").strip()
        or str(record.get("source_mime_type") or "").strip()
    )


def filter_without_invoice_evidence(records, enabled):
    return [record for record in records if not has_invoice_evidence(record)] if enabled else list(records)
