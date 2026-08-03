import re
from dataclasses import dataclass

NON_TRIP = {
    "driver salary": "Driver Salary", "salary": "Salary", "office expense": "Office Expense",
    "office exp": "Office Expense", "office rent": "Office Rent", "electricity": "Electricity Bill",
    "laptop advance": "Laptop Advance", "administrative expense": "Administrative Expense",
    "employee reimbursement": "Employee Reimbursement",
}

@dataclass
class Classification:
    classification: str
    reason: str


def classify_remark(remark, known_suffixes=()):
    """Return Confirmed Trip, Potential Trip, or Confirmed Non-trip.

    A salary/office rule always wins, so incidental four-digit amounts cannot become
    vehicles. Route/date/type evidence is intentionally broader than master matching:
    an unknown vehicle remains reviewable instead of disappearing.
    """
    raw = re.sub(r"\s+", " ", str(remark or "")).strip()
    text = f" {raw.lower()} "
    for phrase, reason in NON_TRIP.items():
        if phrase in text:
            return Classification("Confirmed Non-trip", reason)
    route = bool(re.search(r"\b[A-Za-z][A-Za-z .'-]*\s+to\s+[A-Za-z][A-Za-z .'-]*", raw, re.I))
    vehicle_type = bool(re.search(r"\b0?\d{1,2}\s*[- ]?mt\b", raw, re.I))
    trip_marker = bool(re.search(r"\b(?:TA|TP|TRP|TRIP|\d+TRP)\b", raw, re.I))
    date = bool(re.search(r"\b\d{1,2}[\s./-]+\d{1,2}[\s./-]+(?:\d{2}|\d{4})\b", raw))
    leading_ids = re.findall(r"^\s*(\d{4})(?:\s+(\d{4}))?\b", raw)
    has_id = bool(leading_ids) or bool(re.search(r"\b[A-Z]{2}\s*\d{1,2}\s*[A-Z]{1,3}\s*\d{4}\b", raw, re.I))
    balance = bool(re.search(r"\bbalance payment\b", raw, re.I))
    date_range_trip = bool(re.search(r"\b\d{1,2}[\s./-]+\d{1,2}[\s./-]+(?:\d{2}|\d{4})\s+to\s+\d{1,2}", raw, re.I) and trip_marker)
    if date_range_trip and has_id:
        return Classification("Potential Trip", "Grouped trip/date range needs review")
    if route and has_id and balance:
        return Classification("Potential Trip", "Route-linked balance payment needs review")
    if route and has_id and (date or vehicle_type or trip_marker):
        if len(re.findall(r"^\s*\d{4}", raw)) and re.match(r"^\s*\d{4}\s+\d{4}\b", raw):
            return Classification("Potential Trip", "Multiple vehicle identifiers need review")
        return Classification("Confirmed Trip", "Vehicle and route evidence")
    if route and (vehicle_type or (date and trip_marker) or trip_marker):
        return Classification("Potential Trip", "Route evidence needs review")
    return Classification("Potential Trip", "No decisive non-trip rule; user decision required")
