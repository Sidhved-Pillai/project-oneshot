import json


def _amount(value):
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def vijay_finance_summary(revenue=0, upi=0, diesel=0, cash=0, rtgs=0, toll=0, billtee=0):
    """Return Vijay's own-vehicle expense, advance and profit figures."""
    total_advance = sum(_amount(value) for value in (upi, diesel, cash, rtgs, billtee))
    total_expense = total_advance + _amount(toll)
    return {
        "total_expense": total_expense,
        "total_advance": total_advance,
        "profit_loss": _amount(revenue) - total_expense,
    }


def _data(value):
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return dict(parsed) if isinstance(parsed, dict) else {}
        except (TypeError, ValueError):
            return {}
    return {}


def project_vijay_records(records):
    """Present every Vijay trip with the current own-vehicle finance rules.

    This is a read projection, so older database rows remain auditable while all
    current screens and reports use the same calculation as new entries.
    """
    projected = []
    for source in records or []:
        row = dict(source)
        if str(row.get("created_by") or "").strip() != "Vijay" or row.get("report_scope") == "Expense":
            projected.append(row)
            continue
        dtr = _data(row.get("dtr_data"))
        finance = vijay_finance_summary(
            row.get("revenue"), row.get("upi"), row.get("diesel_advance"),
            row.get("cash_advance"), row.get("rtgs_advance"),
            dtr.get("Toll Expense"), dtr.get("Billtee"),
        )
        dtr.update({
            "LR No.": row.get("invoice_number") or dtr.get("Invoice No.", ""),
            "Own/Outside Veh.": "Own",
            "Transporter Freight": 0.0,
            "Total Adv.": finance["total_advance"],
            "Balance Amt.": finance["profit_loss"],
        })
        row.update({
            "ownership_type": "Own",
            "transporter_freight": 0.0,
            "amount": finance["total_expense"],
            "total_advance": finance["total_advance"],
            "balance_amount": finance["profit_loss"],
            "dtr_data": dtr,
        })
        projected.append(row)
    return projected
