import json
import re
from collections import Counter, defaultdict


def _text(value):
    return str(value or "").strip()


def _key(value):
    return re.sub(r"[^A-Z0-9]", "", _text(value).upper())


def _json(value):
    if isinstance(value, dict):
        return value
    try:
        return json.loads(value or "{}")
    except (TypeError, json.JSONDecodeError):
        return {}


def _winner(records, field):
    values = [_text(record.get(field)) for record in records if _text(record.get(field))]
    if not values:
        return "", 0
    normalized = Counter(_key(value) for value in values)
    winning_key, count = normalized.most_common(1)[0]
    return next(value for value in reversed(values) if _key(value) == winning_key), count


def build_business_memory(rows):
    """Learn deterministic associations from records explicitly saved by users."""
    vehicles, companies, beneficiaries = defaultdict(list), defaultdict(list), defaultdict(list)
    for row in reversed(rows):  # oldest to newest; newest spelling wins ties
        if row.get("status") not in {"Verified", "Submitted"} or row.get("report_scope") == "Expense":
            continue
        dtr, rtgs = _json(row.get("dtr_data")), _json(row.get("rtgs_data"))
        record = {
            **row,
            "vehicle_capacity": row.get("vehicle_type") or dtr.get("Vehicle Type"),
            "transporter_name": row.get("transporter_name") or dtr.get("Transporter Name"),
            "vehicle_placed_by": dtr.get("Veh Placed by"),
            "account_number": rtgs.get("BENE_ACC_NO"),
            "ifsc": rtgs.get("BENE_IFSC"),
        }
        if _key(row.get("vehicle_number")):
            vehicles[_key(row["vehicle_number"])].append(record)
        if _key(row.get("company_name")):
            companies[_key(row["company_name"])].append(record)
        if _key(row.get("beneficiary_name")):
            beneficiaries[_key(row["beneficiary_name"])].append(record)

    def compile_group(groups, fields):
        return {
            key: {field: value for field in fields if (value := _winner(records, field))[0]}
            for key, records in groups.items()
        }

    return {
        "vehicles": compile_group(vehicles, ["vehicle_capacity", "transporter_name", "ownership_type", "vehicle_placed_by"]),
        "companies": compile_group(companies, ["branch"]),
        "beneficiaries": compile_group(beneficiaries, ["account_number", "ifsc", "transporter_name"]),
    }


def recall(memory, category, lookup):
    """Return field -> (value, supporting record count) for an exact business key."""
    return memory.get(category, {}).get(_key(lookup), {})
