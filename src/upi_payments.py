"""Explicit, separately tracked UPI payment requests for Nitish's own trips."""
from .balance_payments import balance_rtgs_rows, BALANCE_PREFIX

UPI_PREFIX = "UPI:"


def can_send_upi(user, row):
    return (user == "Nitish" and row.get("created_by") == "Nitish"
            and str(row.get("branch") or "").strip().casefold() == "pune"
            and row.get("report_scope") != "Expense"
            and not row.get("is_archived") and row.get("status") != "Cancelled"
            and float(row.get("upi") or 0) > 0)


def upi_rtgs_rows(trips, payments):
    rows = balance_rtgs_rows(trips, payments)
    for row in rows:
        row['request_number'] = UPI_PREFIX + row['request_number'].removeprefix(BALANCE_PREFIX)
        row.pop('_balance_payment', None)
        row['_upi_payment'] = True
    return rows
