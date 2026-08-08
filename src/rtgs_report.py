import datetime as dt
import json
import re
from io import BytesIO

import pandas as pd
import xlwt


# Exact field order used by the ICICI PAB vendor-upload workbook.
RTGS_COLUMNS = [
    "PYMT_PROD_TYPE_CODE", "PYMT_MODE", "DEBIT_ACC_NO", "BNF_NAME",
    "BENE_ACC_NO", "BENE_IFSC", "AMOUNT", "DEBIT_NARR", "CREDIT_NARR",
    "MOBILE_NUM", "EMAIL_ID", "REMARK", "PYMT_DATE", "REF_NO",
    "ADDL_INFO1", "ADDL_INFO2", "ADDL_INFO3", "ADDL_INFO4", "ADDL_INFO5",
]
RTGS_REVIEW_COLUMNS = [*RTGS_COLUMNS, "Transporter Freight", "Origin Area", "Review Notes"]
DEBIT_ACCOUNT_NUMBER = "123305002576"
BRANCH_EMAILS = {
    "wada": "Ajitthakur@billtee.com",
    "pune": "jhanitish942@gmail.com",
    "baroda": "Ashoksharma@billtee.com",
    "vadodara": "Ashoksharma@billtee.com",
}
LEGACY_COLUMNS = {
    "Pymt_Prod_Type_Code": "PYMT_PROD_TYPE_CODE", "Pymt_Mode": "PYMT_MODE",
    "Debit_Acct_no": "DEBIT_ACC_NO", "Beneficiary Name": "BNF_NAME",
    "Beneficiary Account No": "BENE_ACC_NO", "Bene_IFSC_Code": "BENE_IFSC",
    "Amount": "AMOUNT", "Debit narration": "DEBIT_NARR", "Credit narration": "CREDIT_NARR",
    "Mobile Numder": "MOBILE_NUM", "Email id": "EMAIL_ID", "Remark": "REMARK",
    "Pymt_Date": "PYMT_DATE", "Reference_no": "REF_NO", "Addl_Info1": "ADDL_INFO1",
    "Addl_Info2": "ADDL_INFO2", "Addl_Info3": "ADDL_INFO3", "Addl_Info4": "ADDL_INFO4",
    "Addl_Info5": "ADDL_INFO5",
}


def canonical_rtgs_record(record):
    out = dict(record)
    for old, new in LEGACY_COLUMNS.items():
        if out.get(new, "") in (None, "") and old in out:
            out[new] = out[old]
    return out


def _clean_alphanumeric(value, spaces=True):
    pattern = r"[^A-Za-z0-9 ]" if spaces else r"[^A-Za-z0-9]"
    return re.sub(r"\s+", " ", re.sub(pattern, "", str(value or ""))).strip()


def _digits(value):
    return re.sub(r"\D", "", str(value or ""))


def _amount(value):
    try:
        return float(str(value or 0).replace(",", ""))
    except (TypeError, ValueError):
        return 0.0


def _payment_date(value=None):
    parsed = pd.to_datetime(value, errors="coerce", dayfirst=True)
    if pd.isna(parsed):
        return dt.date.today()
    return parsed.date()


def _infer_area(text):
    value = str(text or "").lower()
    if any(place in value for place in ("talegaon", "pune", "kamshet", "thane")):
        return "pune"
    if any(place in value for place in ("jhagadia", "baroda", "vadodara")):
        return "baroda"
    if any(place in value for place in ("wada", "vasai", "bhiwandi")):
        return "wada"
    return ""


def normalize_rtgs_record(record, payment_date=None):
    """Apply deterministic ICICI rules after AI extraction and manual editing."""
    record = canonical_rtgs_record(record)
    out = {column: record.get(column, "") for column in RTGS_REVIEW_COLUMNS}
    out["PYMT_PROD_TYPE_CODE"] = "PAB_VENDOR"
    out["DEBIT_ACC_NO"] = DEBIT_ACCOUNT_NUMBER
    out["BNF_NAME"] = re.sub(r"\s+", " ", re.sub(r"[^A-Za-z ]", "", str(out["BNF_NAME"] or ""))).strip()
    out["BENE_ACC_NO"] = _digits(out["BENE_ACC_NO"])
    out["BENE_IFSC"] = _clean_alphanumeric(out["BENE_IFSC"], spaces=False).upper()
    out["PYMT_MODE"] = "FT" if out["BENE_IFSC"].startswith("ICIC") else "NEFT"
    out["DEBIT_NARR"] = _clean_alphanumeric(out["DEBIT_NARR"])
    out["CREDIT_NARR"] = _clean_alphanumeric(out["CREDIT_NARR"])
    out["MOBILE_NUM"] = _digits(out["MOBILE_NUM"])[-10:]
    out["REMARK"] = _clean_alphanumeric(out["REMARK"])
    out["REF_NO"] = _clean_alphanumeric(out["REF_NO"])
    for column in ("ADDL_INFO1", "ADDL_INFO2", "ADDL_INFO3", "ADDL_INFO4", "ADDL_INFO5"):
        out[column] = _clean_alphanumeric(out[column])
    out["PYMT_DATE"] = _payment_date(payment_date)
    origin = str(record.get("Origin Area", "") or record.get("Branch", "")).strip().lower()
    if not origin:
        origin = _infer_area(record.get("REMARK", ""))
    for area, email in BRANCH_EMAILS.items():
        if origin.startswith(area):
            out["EMAIL_ID"] = email
            break
    return out


def normalize_rtgs_records(records, payment_date=None):
    grouped, positions = [], {}
    for record in records:
        remark = str(record.get("REMARK", ""))
        vehicle_match = re.search(r"\b(\d{4})\b", remark)
        vehicle = vehicle_match.group(1) if vehicle_match else ""
        key = (str(record.get("BNF_NAME", "")).strip().lower(), _digits(record.get("BENE_ACC_NO", "")),
               _clean_alphanumeric(record.get("BENE_IFSC", ""), spaces=False).upper(), vehicle)
        dates = re.findall(r"\b(\d{2})[\s/-](\d{2})[\s/-](\d{4})\b", remark)
        can_group = bool(all(key)) and "trp" not in remark.lower() and bool(dates)
        if can_group and key in positions:
            target = grouped[positions[key]]
            target["AMOUNT"] = _amount(target.get("AMOUNT")) + _amount(record.get("AMOUNT"))
            target["Transporter Freight"] = _amount(target.get("Transporter Freight")) + _amount(record.get("Transporter Freight"))
            target["_trip_dates"].extend(dates)
            target["_trip_count"] += 1
            continue
        copy = dict(record)
        if not copy.get("Origin Area"):
            copy["Origin Area"] = _infer_area(remark)
        if can_group:
            positions[key] = len(grouped)
            copy["_trip_dates"], copy["_trip_count"] = list(dates), 1
        grouped.append(copy)
    for record in grouped:
        if record.get("_trip_count", 1) > 1:
            first, last = record["_trip_dates"][0], record["_trip_dates"][-1]
            vehicle = re.search(r"\b(\d{4})\b", str(record.get("REMARK", ""))).group(1)
            record["REMARK"] = f"{vehicle} {' '.join(first)} to {' '.join(last)} {record['_trip_count']}Trp TA"
    return [normalize_rtgs_record(record, payment_date) for record in grouped]


def rows_to_rtgs(rows):
    records = []
    for row in rows:
        raw = row.get("rtgs_data") or "{}"
        data = json.loads(raw) if isinstance(raw, str) else dict(raw)
        data = canonical_rtgs_record(data)
        record = {column: data.get(column, "") for column in RTGS_REVIEW_COLUMNS}
        record["BNF_NAME"] = record["BNF_NAME"] or row.get("beneficiary_name", "")
        record["AMOUNT"] = record["AMOUNT"] if record["AMOUNT"] not in (None, "") else row.get("amount", "")
        records.append(record)
    return pd.DataFrame(records, columns=RTGS_COLUMNS)


def _style(font_colour="black", text=False, wrap=False, date=False):
    font = xlwt.Font()
    font.name = "Mulish SemiBold"
    font.height = 220
    font.colour_index = {"black": 8, "red": 10, "blue": 30}.get(font_colour, 8)
    alignment = xlwt.Alignment()
    alignment.horz = xlwt.Alignment.HORZ_CENTER
    alignment.vert = xlwt.Alignment.VERT_CENTER
    alignment.wrap = int(wrap)
    borders = xlwt.Borders()
    borders.left = borders.right = borders.top = borders.bottom = xlwt.Borders.THIN
    return _assembled_style(font, alignment, borders, "DD-MM-YYYY" if date else "@" if text else "General")


def _assembled_style(font, alignment, borders, number_format):
    style = xlwt.XFStyle()
    style.font, style.alignment, style.borders = font, alignment, borders
    style.num_format_str = number_format
    return style


def export_rtgs(df, payment_date=None):
    """Generate the legacy .xls layout accepted by the supplied ICICI template."""
    records = normalize_rtgs_records(df.to_dict("records"), payment_date or dt.date.today())
    book = xlwt.Workbook(encoding="utf-8")
    sheet = book.add_sheet("Sheet1")
    widths = [7168, 5778, 5778, 9362, 5229, 4242, 4681, 0, 0, 4827, 6802, 15360, 5778, 5778, 5778, 5778, 5778, 5778, 5778]
    for index, width in enumerate(widths):
        sheet.col(index).width = width
        if index in (7, 8):
            sheet.col(index).hidden = True
    sheet.row(0).height_mismatch = True
    sheet.row(0).height = 2749
    header_red = {0, 1, 2, 3, 4, 5, 6, 12}
    for col, name in enumerate(RTGS_COLUMNS):
        sheet.write(0, col, name, _style("red" if col in header_red else "black", wrap=True))
    text_columns = {2, 3, 4}
    for row_index, record in enumerate(records, 1):
        sheet.row(row_index).height_mismatch = True
        sheet.row(row_index).height = 285
        for col, name in enumerate(RTGS_COLUMNS):
            value = record.get(name, "")
            if name == "PYMT_DATE":
                value = _payment_date(value)
                style = _style(date=True, wrap=True)
            elif name == "EMAIL_ID":
                style = _style("blue")
            else:
                style = _style(text=col in text_columns, wrap=col in {0, 1, 2, 9})
            sheet.write(row_index, col, value, style)
    output = BytesIO()
    book.save(output)
    return output.getvalue()
