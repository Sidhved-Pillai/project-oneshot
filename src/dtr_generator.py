import pandas as pd
from .column_mapping import CONSOLIDATED_ALIASES, resolve_columns
from .remark_classifier import classify_remark
from .remark_parser import parse_remark
from .vehicle_matcher import resolve_vehicle, choose_vehicle_type
from .beneficiary_matcher import find_beneficiary

DTR_COLUMNS = ["Sr No.", "Branch", "Compnay Name", "Date", "Vehicle No.", "Vehicle Type",
               "Own/Outside Vehicle", "From", "Invoice No.", "To", "Revenue", "Transporter Freight",
               "RTGS ADVANCE", "Cash Adv.", "UPI", "Diesel Qty", "Diesel Adv.", "Total Adv.",
               "Balance Amt.", "Payment", "Benificiary Name", "Transporter Name"]
FINANCIAL_COLUMNS = DTR_COLUMNS[10:20]
POTENTIAL_CONTROL_COLUMNS = ["Include in DTR", "Original Remark", "Original Beneficiary Name"]
INTERNAL_COLUMNS = ["_row_id", "_vehicle_identifiers", "_vehicle_choices", "_type_conflict", "_needs_review"]


def _draft(raw, mapping, parsed, vehicles, beneficiaries, row_id):
    vehicle_no, vehicle, choices = resolve_vehicle(parsed["vehicle_identifiers"], vehicles)
    vehicle_type, type_conflict = choose_vehicle_type(parsed["vehicle_type"], vehicle.get("Vehicle Type", ""))
    account = raw.get(mapping.get("Beneficiary Account No", ""), "")
    bene_matches = find_beneficiary(account, beneficiaries) if not beneficiaries.empty else []
    bene = bene_matches[0] if len(bene_matches) == 1 else {}
    row = {c: "" for c in DTR_COLUMNS}
    row.update({"Date": parsed["date"], "Vehicle No.": vehicle_no, "Vehicle Type": vehicle_type,
                "Own/Outside Vehicle": vehicle.get("Ownership Type", ""), "From": parsed["from_location"],
                "Invoice No.": parsed["invoice_number"], "To": parsed["to_location"],
                "Benificiary Name": raw.get(mapping["Beneficiary Name"], ""),
                "Transporter Name": bene.get("Transporter Name", "") or vehicle.get("Transporter Name", "")})
    row.update({"_row_id": row_id, "_vehicle_identifiers": parsed["vehicle_identifiers"],
                "_vehicle_choices": choices, "_type_conflict": type_conflict,
                "_needs_review": type_conflict or len(choices) != 1})
    return row


def generate_dtr(source, vehicles, beneficiaries):
    mapping = resolve_columns(source.columns, CONSOLIDATED_ALIASES)
    missing = [c for c in ("Remark", "Beneficiary Name") if c not in mapping]
    if missing: raise ValueError("Missing required consolidated column(s): " + ", ".join(missing))
    suffixes = vehicles["Last 4 Digits"].astype(str).tolist() if not vehicles.empty else []
    confirmed, potential, non_trip = [], [], []
    for source_index, raw in source.iterrows():
        remark = raw.get(mapping["Remark"], "")
        cls = classify_remark(remark, suffixes)
        base_audit = {"Original Remark": remark, "Original Beneficiary Name": raw.get(mapping["Beneficiary Name"], ""),
                      "Reason": cls.reason, "_row_id": int(source_index)}
        if cls.classification == "Confirmed Non-trip":
            non_trip.append(base_audit); continue
        draft = _draft(raw, mapping, parse_remark(remark), vehicles, beneficiaries, int(source_index))
        if cls.classification == "Confirmed Trip": confirmed.append(draft)
        else:
            draft.update({"Include in DTR": False, "Original Remark": remark,
                          "Original Beneficiary Name": raw.get(mapping["Beneficiary Name"], "")})
            potential.append(draft)
    confirmed_df = pd.DataFrame(confirmed, columns=DTR_COLUMNS + INTERNAL_COLUMNS)
    potential_df = pd.DataFrame(potential, columns=POTENTIAL_CONTROL_COLUMNS + DTR_COLUMNS + INTERNAL_COLUMNS)
    for df in (confirmed_df, potential_df):
        if not df.empty: df["Sr No."] = range(1, len(df) + 1)
    return confirmed_df, potential_df, pd.DataFrame(non_trip)


def final_review_rows(confirmed, potential):
    selected = potential[potential["Include in DTR"].fillna(False)] if not potential.empty else potential
    records = confirmed.reindex(columns=DTR_COLUMNS).to_dict("records") + selected.reindex(columns=DTR_COLUMNS).to_dict("records")
    final = pd.DataFrame(records, columns=DTR_COLUMNS)
    final["Sr No."] = range(1, len(final) + 1)
    for col in FINANCIAL_COLUMNS: final[col] = ""
    return final
