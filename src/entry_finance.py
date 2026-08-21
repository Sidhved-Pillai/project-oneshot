from decimal import Decimal


def is_own_vehicle(ownership_type):
    """Recognize both current and historical labels for company-owned vehicles."""
    return str(ownership_type or "").strip().casefold().startswith("own")


def applicable_transporter_freight(ownership_type, amount):
    """Own vehicles never carry transporter freight."""
    return Decimal("0") if is_own_vehicle(ownership_type) else Decimal(str(amount or 0))


def financial_values(expense_type, payment_mode, amount, diesel_quantity=None):
    """Translate the simple entry controls into the existing DTR financial columns."""
    amount = Decimal(str(amount or 0))
    values = {
        "revenue": Decimal("0"), "transporter_freight": Decimal("0"),
        "rtgs_advance": Decimal("0"), "cash_advance": Decimal("0"),
        "upi": Decimal("0"), "diesel_advance": Decimal("0"),
        "total_advance": Decimal("0"), "balance_amount": Decimal("0"),
        "payment": Decimal("0"), "diesel_quantity": diesel_quantity,
    }
    if expense_type == "Revenue":
        values["revenue"] = amount
    elif expense_type == "Transporter Freight":
        values["transporter_freight"] = amount
    elif expense_type == "Balance Payment":
        values["payment"] = amount
    elif expense_type == "Trip Advance":
        target = {
            "RTGS/Bank Transfer": "rtgs_advance", "Cash": "cash_advance",
            "UPI": "upi", "Diesel": "diesel_advance",
        }.get(payment_mode)
        if target:
            values[target] = amount
            values["total_advance"] = amount
    return values


def advance_summary(transporter_freight, *advance_amounts):
    """Return exact advance and payable totals; a negative balance means overpayment."""
    freight = Decimal(str(transporter_freight or 0))
    total_advance = sum((Decimal(str(value or 0)) for value in advance_amounts), Decimal("0"))
    return {"transporter_freight": freight, "total_advance": total_advance, "balance_payable": freight - total_advance}
