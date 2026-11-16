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
        saved = payment.get("rtgs_data") or "{}"
        saved = json.loads(saved) if isinstance(saved, str) else dict(saved)
        trip = trips_by_number.get(saved.get("_source_request_number", number))
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
        settled = payment.get('_settled_amount', 0)
        remaining = payment.get('_awaiting_amount', payment.get('amount'))
        report_amount = remaining if settled and remaining else payment.get('amount')
        data['AMOUNT'] = float(report_amount or 0)
        rows.append({
            **trip,
            "request_number": BALANCE_PREFIX + number,
            "trip_date": requested_date,
            "rtgs_advance": report_amount,
            "rtgs_done": (not bool(remaining)) if settled or payment.get("_has_settlement_activity") else payment.get("rtgs_done"),
            "rtgs_data": json.dumps(data, default=str),
            "_balance_payment": True,
            "beneficiary_name": data.get("BNF_NAME", ""),
        })
    return rows
