"""Permissions and identifiers for separately requested trip balance payments."""

import datetime as dt
import json

BALANCE_PAYMENT_USERS = {"Ashok", "Ajit", "Nitish", "Sid", "Vinod", "Nikhil"}
BALANCE_PREFIX = "BALANCE:"


def can_send_balance(user, row):
    if user not in BALANCE_PAYMENT_USERS or row.get("report_scope") == "Expense":
        return False
    if row.get("is_archived") or row.get("status") == "Cancelled":
        return False
    branch = str(row.get("branch") or "").strip().casefold()
    if user == "Ashok":
        return branch in {"vadodara", "vadodra", "baroda"}
    if user == "Nitish":
        return branch == "pune"
    return True


def balance_rtgs_rows(trips, payments):
    """Build newest-first RTGS rows independently of the trip-date filter."""
    trips_by_number = {row.get("request_number"): row for row in trips}
    rows = []
    for payment in sorted(
        payments.values(), key=lambda row: str(row.get("created_at") or ""), reverse=True,
    ):
        number = payment.get("request_number")
        trip = trips_by_number.get(number)
        if not trip:
            continue
        raw = payment.get("rtgs_data") or "{}"
        data = json.loads(raw) if isinstance(raw, str) else dict(raw)
        created_at = payment.get("created_at")
        if isinstance(created_at, (dt.datetime, dt.date)):
            requested_date = created_at.date() if isinstance(created_at, dt.datetime) else created_at
        else:
            try:
                requested_date = dt.date.fromisoformat(str(created_at)[:10])
            except (TypeError, ValueError):
                requested_date = trip.get("trip_date")
        rows.append({
            **trip,
            "request_number": BALANCE_PREFIX + number,
            "trip_date": requested_date,
            "rtgs_advance": payment.get("amount"),
            "rtgs_done": payment.get("rtgs_done"),
            "rtgs_data": payment.get("rtgs_data"),
            "_balance_payment": True,
            "beneficiary_name": data.get("BNF_NAME", ""),
        })
    return rows
