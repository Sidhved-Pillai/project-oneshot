import datetime as dt

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
