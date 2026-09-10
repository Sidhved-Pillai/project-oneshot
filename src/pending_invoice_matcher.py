import datetime as dt
import re
from difflib import SequenceMatcher

import pandas as pd

from .vehicle_normalization import canonical_vehicle_number


def _text(value):
    return " ".join(str(value or "").casefold().split())


def _identifier(value):
    return re.sub(r"[^A-Z0-9]", "", str(value or "").upper())


def _date(value):
    parsed = pd.to_datetime(value, errors="coerce", dayfirst=True)
    return parsed.date() if not pd.isna(parsed) else None


def _similar(left, right):
    left, right = _text(left), _text(right)
    return SequenceMatcher(None, left, right).ratio() if left and right else 0.0


def score_invoice_match(extracted, record):
    """Score one extracted invoice against one pending trip record."""
    raw = record.get("dtr_data") or {}
    if isinstance(raw, str):
        try:
            import json
            raw = json.loads(raw)
        except (TypeError, ValueError):
            raw = {}
    score, reasons = 0, []
    extracted_numbers = {
        _identifier(extracted.get("invoice_number")),
        _identifier(extracted.get("lr_number")),
    } - {""}
    record_numbers = {
        _identifier(record.get("invoice_number")),
        _identifier(raw.get("Invoice No.")),
        _identifier(raw.get("LR No.")),
    } - {""}
    if extracted_numbers & record_numbers:
        score += 100
        reasons.append("invoice or LR number")
    extracted_vehicle = canonical_vehicle_number(extracted.get("vehicle_number"))
    record_vehicle = canonical_vehicle_number(record.get("vehicle_number"))
    if extracted_vehicle and extracted_vehicle == record_vehicle:
        score += 45
        reasons.append("vehicle number")
    if _date(extracted.get("date")) and _date(extracted.get("date")) == _date(record.get("trip_date")):
        score += 25
        reasons.append("date")
    if _similar(extracted.get("company_name"), record.get("company_name")) >= 0.8:
        score += 15
        reasons.append("company")
    if _similar(extracted.get("from_location"), record.get("from_location")) >= 0.8:
        score += 10
        reasons.append("origin")
    if _similar(extracted.get("to_location"), record.get("to_location")) >= 0.8:
        score += 10
        reasons.append("destination")
    return score, reasons


def suggest_invoice_match(extracted, candidates):
    """Return a unique, sufficiently strong suggestion or no automatic match."""
    ranked = sorted(
        ((score_invoice_match(extracted, record), record) for record in candidates),
        key=lambda item: item[0][0], reverse=True,
    )
    if not ranked or ranked[0][0][0] < 45:
        return None, "Low", "No reliable match"
    (best_score, reasons), best = ranked[0]
    second_score = ranked[1][0][0] if len(ranked) > 1 else 0
    if second_score and best_score - second_score < 15:
        return None, "Review", "Multiple records have similar details"
    confidence = "High" if best_score >= 70 else "Review"
    return best, confidence, ", ".join(reasons)
