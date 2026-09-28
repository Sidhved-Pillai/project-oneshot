"""Link direct expenses to their source trips using invoice numbers."""

import re


def _invoice_parts(value):
    return {
        re.sub(r"[^a-z0-9]", "", part.casefold())
        for part in re.split(r"\s*/\s*", str(value or ""))
        if re.sub(r"[^a-z0-9]", "", part.casefold())
    }


def link_expenses_to_trips(expenses, trips):
    """Copy trip dimensions onto expenses having one unambiguous invoice match."""
    by_invoice = {}
    ambiguous = set()
    for trip in trips:
        for invoice in _invoice_parts(trip.get("invoice_number")):
            if invoice in by_invoice and by_invoice[invoice].get("request_number") != trip.get("request_number"):
                ambiguous.add(invoice)
            else:
                by_invoice[invoice] = trip

    linked = []
    for expense in expenses:
        matches = {
            by_invoice[invoice].get("request_number"): by_invoice[invoice]
            for invoice in _invoice_parts(expense.get("invoice_number"))
            if invoice in by_invoice and invoice not in ambiguous
        }
        if len(matches) != 1:
            linked.append(dict(expense))
            continue
        trip = next(iter(matches.values()))
        linked.append({
            **expense,
            "branch": trip.get("branch") or expense.get("branch"),
            "vehicle_number": trip.get("vehicle_number") or expense.get("vehicle_number"),
            "vehicle_type": trip.get("vehicle_type") or expense.get("vehicle_type"),
            "ownership_type": trip.get("ownership_type") or expense.get("ownership_type"),
            "linked_trip_request_number": trip.get("request_number", ""),
        })
    return linked
