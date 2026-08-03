import re
import pandas as pd


def normalize_vehicle(value):
    return re.sub(r"[^A-Z0-9]", "", str(value or "").upper())


def last_four(value):
    match = re.search(r"(\d{4})$", normalize_vehicle(value))
    return match.group(1) if match else ""


def normalize_vehicle_type(value):
    match = re.search(r"\b0?(\d{1,2})\s*[- ]?MT\b", str(value or ""), re.I)
    return f"{int(match.group(1))}MT" if match else ""


def all_dates(text):
    dates = []
    # Lookahead permits overlapping candidates. This lets `29 30 07 2026`
    # reject the invalid 29/30 candidate and still accept 30/07/2026.
    for match in re.finditer(r"(?=\b(\d{1,2})[\s./-]+(\d{1,2})[\s./-]+(\d{4}|\d{2})\b)", str(text or "")):
        year = int(match.group(3))
        if year < 100: year += 2000
        try: dates.append(pd.Timestamp(year=year, month=int(match.group(2)), day=int(match.group(1))))
        except ValueError: pass
    return dates


def parse_date(text):
    dates = all_dates(text)
    return dates[-1] if dates else None


def vehicle_identifiers(text):
    full = re.search(r"\b[A-Z]{2}\s*\d{1,2}\s*[A-Z]{1,3}\s*\d{4}\b", str(text or ""), re.I)
    if full: return [normalize_vehicle(full.group())]
    prefix = re.match(r"^\s*(\d{4})(?:\s+(\d{4}))?\b", str(text or ""))
    return [x for x in prefix.groups() if x] if prefix else []


def parse_remark(remark):
    """Best effort parse. For adjacent date days like `29 30 07 2026`, the
    final valid day-month-year sequence is used (30-07-2026)."""
    text = re.sub(r"\s+", " ", str(remark or "")).strip()
    pipe_parts = [part.strip() for part in text.split("|")] if "|" in text else []
    identifiers = vehicle_identifiers(text)
    result = {"date": parse_date(text), "vehicle_identifier": identifiers[0] if len(identifiers) == 1 else "",
              "vehicle_identifiers": identifiers, "vehicle_type": normalize_vehicle_type(text),
              "from_location": "", "to_location": "", "invoice_number": "",
              "company_name": pipe_parts[1] if len(pipe_parts) > 1 else ""}
    route_text = text
    if identifiers:
        prefix = r"^\s*" + r"\s+".join(re.escape(x) for x in identifiers) + r"\s+"
        route_text = re.sub(prefix, "", route_text, flags=re.I)
    route_source = pipe_parts[2] if len(pipe_parts) > 2 else route_text
    route = re.search(r"(?:^|\bfrom\b)\s*([A-Za-z][A-Za-z0-9 .'-]*?)\s+to\s+([A-Za-z][A-Za-z0-9 .'-]*?)(?=\s+\d+K\s+CARD\b|\s+0?\d{1,2}\s*[- ]?MT\b|\s+\d{1,2}[\s./-]+\d{1,2}[\s./-]+(?:\d{2}|\d{4})\b|\s+(?:INV(?:OICE)?|BILL)(?:\s+NO\.?)?\b|\s+(?:BALANCE|TA|TP|DIESEL|DIESAL|FREIGHT|\d+TRP)\b|$)", route_source, re.I)
    if route:
        result["from_location"] = route.group(1).strip(" ,.-").title()
        result["to_location"] = route.group(2).strip(" ,.-").title()
    inv = re.search(r"\b(?:INV(?:OICE)?|BILL)(?:\s+NO\.?)?\s*[:#-]?\s*([A-Z0-9][A-Z0-9/-]*)", text, re.I)
    if inv: result["invoice_number"] = inv.group(1)
    return result
