"""One-time-safe RTGS completion for Vijay's two known transporters."""

import json

from .transporter_profiles import vijay_transporter_for_vehicle, vijay_transporter_profile


RTGS_BY_TRANSPORTER = {
    "Altaf Khan Transport": 2254.94,
    "Nisar Anwar Shaikh": 2287.67,
}
BACKFILL_MARKER = "_vijay_rtgs_backfill_20260923"


def _number(value):
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _data(value):
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
            return dict(parsed) if isinstance(parsed, dict) else {}
        except (TypeError, ValueError, json.JSONDecodeError):
            return {}
    return {}


def _transporter(row, dtr):
    name = str(row.get("transporter_name") or dtr.get("Transporter Name") or "").strip()
    folded = name.casefold()
    if "altaf" in folded:
        return "Altaf Khan Transport"
    if "nisar" in folded:
        return "Nisar Anwar Shaikh"
    return vijay_transporter_for_vehicle(row.get("vehicle_number"))


def vijay_missing_rtgs_updates(records):
    """Return idempotent record updates without replacing an existing RTGS value."""
    updates = []
    for row in records:
        if str(row.get("created_by") or "").strip() != "Vijay":
            continue
        if str(row.get("report_scope") or "").strip().casefold() == "expense":
            continue
        if _number(row.get("rtgs_advance")) != 0:
            continue

        dtr = _data(row.get("dtr_data"))
        if dtr.get(BACKFILL_MARKER):
            continue
        transporter = _transporter(row, dtr)
        rtgs = RTGS_BY_TRANSPORTER.get(transporter)
        if not rtgs:
            continue

        old_total = _number(row.get("total_advance"))
        old_balance = _number(row.get("balance_amount"))
        new_total = round(old_total + rtgs, 2)
        new_balance = round(old_balance - rtgs, 2)
        payments = {
            "RTGS": rtgs,
            "Cash": _number(row.get("cash_advance")),
            "UPI": _number(row.get("upi")),
            "Diesel": _number(row.get("diesel_advance")),
        }
        dtr.update({
            "RTGS ADVANCE": rtgs,
            "Total Adv.": new_total,
            "Balance Amt.": new_balance,
            "Transporter Name": transporter,
            BACKFILL_MARKER: True,
        })
        profile = vijay_transporter_profile(transporter)
        rtgs_data = _data(row.get("rtgs_data"))
        rtgs_data.update({
            "BNF_NAME": rtgs_data.get("BNF_NAME") or profile.get("beneficiary_name", ""),
            "BENE_ACC_NO": rtgs_data.get("BENE_ACC_NO") or profile.get("beneficiary_account_number", ""),
            "BENE_IFSC": rtgs_data.get("BENE_IFSC") or profile.get("beneficiary_ifsc_code", ""),
            "AMOUNT": rtgs,
            "REMARK": rtgs_data.get("REMARK") or row.get("notes", ""),
            "Origin Area": rtgs_data.get("Origin Area") or row.get("branch", ""),
        })
        updates.append((row["request_number"], {
            "transporter_name": transporter,
            "rtgs_advance": rtgs,
            "total_advance": new_total,
            "balance_amount": new_balance,
            "amount": new_total,
            "payment_mode": ", ".join(name for name, value in payments.items() if value),
            "dtr_data": dtr,
            "rtgs_data": rtgs_data,
        }))
    return updates
