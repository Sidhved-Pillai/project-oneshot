import re


def key(value: object) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value).strip().lower())


DTR_ALIASES = {
    "Sr No.": ["sr no", "sr no."], "Branch": ["branch"],
    "Compnay Name": ["compnay name", "company name"], "Date": ["date"],
    "Vehicle No.": ["vehicle no", "vehicle number"],
    "Vehicle Type": ["vehicle type"],
    "Own/Outside Vehicle": ["own/outside veh", "own/outside vehicle", "ownership type"],
    "From": ["from"], "Invoice No.": ["invoice no", "invoice number"], "To": ["to"],
    "Revenue": ["revenue"], "Transporter Freight": ["transporter freight"],
    "RTGS ADVANCE": ["rtgs advance"], "Cash Adv.": ["cash adv"], "UPI": ["upi"],
    "Diesel Qty": ["diesel qty"], "Diesel Adv.": ["diesel adv"],
    "Total Adv.": ["total adv"], "Balance Amt.": ["balance amt"],
    "Payment": ["payment"], "Benificiary Name": ["benificiary name", "beneficiary name"],
    "Transporter Name": ["transporter name"],
}

CONSOLIDATED_ALIASES = {
    "Remark": ["remark", "remarks", "payment remark"],
    "Beneficiary Name": ["beneficiary name", "beneficiary"],
    "Beneficiary Account No": ["beneficiary account no", "beneficiary account number", "bene account no"],
    "Pymt_Date": ["pymt date", "payment date", "date"],
}


def map_columns(columns, aliases):
    lookup = {key(c): c for c in columns}
    return {target: lookup[key(alias)] for target, names in aliases.items()
            for alias in names if key(alias) in lookup and target not in locals().get("_", {})}


def resolve_columns(columns, aliases):
    lookup = {key(c): c for c in columns}
    result = {}
    for target, names in aliases.items():
        for name in names:
            if key(name) in lookup:
                result[target] = lookup[key(name)]
                break
    return result

