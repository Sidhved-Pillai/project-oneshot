"""Import records from Records exports or operational DTR workbooks."""

import re
from io import BytesIO

import pandas as pd

from .records_export import EXPENSE_EXPORT_COLUMNS, RECORD_EXPORT_COLUMNS
from .text_normalization import canonical_company, canonical_ownership


DTR_HEADER_MAP = {
    "srno": "Record", "record": "Record", "recordtype": "Record Type",
    "date": "Date", "status": "Status", "createdby": "Created By", "branch": "Branch",
    "companyname": "Company Name", "compnayname": "Company Name",
    "vehicleno": "Vehicle Number", "vehiclenumber": "Vehicle Number",
    "vehicletype": "Vehicle Capacity", "vehiclecapacity": "Vehicle Capacity",
    "ownoutsideveh": "Own / Outside", "ownoutside": "Own / Outside",
    "from": "From", "to": "To", "lrno": "LR Number", "lrnumber": "LR Number",
    "invoiceno": "Invoice Number", "invoicenumber": "Invoice Number",
    "beneficiaryname": "Beneficiary Name", "benificiaryname": "Beneficiary Name",
    "accountnumber": "Account Number", "beneficiaryaccountno": "Account Number",
    "ifsccode": "IFSC Code", "ifsc": "IFSC Code", "transportername": "Transporter Name",
    "vehplacedby": "Vehicle Placed By", "vehicleplacedby": "Vehicle Placed By",
    "companyfreight": "Revenue Freight", "revenue": "Revenue Freight",
    "revenuefreight": "Revenue Freight", "transporterfreight": "Transporter Freight",
    "rtgsadvance": "RTGS", "rtgs": "RTGS", "cashadv": "Cash", "cash": "Cash",
    "upi": "UPI", "dieseladv": "Diesel", "diesel": "Diesel", "dieselqty": "Diesel Qty",
    "dieselrate": "Diesel Rate", "tollexpense": "Toll Expense",
    "repairsmaintenance": "Repairs & Maintenance", "repairreason": "Repair Reason",
    "billtee": "Billtee", "totaladv": "Total Advance", "totaladvance": "Total Advance",
    "balanceamt": "Balance Amount", "balanceamount": "Balance Amount", "payment": "Payment",
    "paymentmode": "Payment Mode", "dieselpumpname": "Diesel Pump Name",
    "cardname": "Card Name", "remark": "Remarks", "remarks": "Remarks",
}


def _blank(value):
    return value is None or (not isinstance(value, (list, dict)) and pd.isna(value))


def _text(value):
    if _blank(value):
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return re.sub(r"\s+", " ", str(value)).strip()


def _number(value):
    if _blank(value) or _text(value) == "":
        return 0.0
    cleaned = re.sub(r"[^0-9.\-]", "", _text(value))
    try:
        return float(cleaned or 0)
    except ValueError:
        return 0.0


def _date(value):
    if _blank(value) or _text(value) == "":
        return None
    if isinstance(value, (int, float)):
        parsed = pd.to_datetime(value, unit="D", origin="1899-12-30", errors="coerce")
    else:
        parsed = pd.to_datetime(value, dayfirst=True, errors="coerce")
    return None if pd.isna(parsed) else parsed.date()


def _header_key(value):
    return re.sub(r"[^a-z0-9]", "", _text(value).casefold())


def read_records_excel(data):
    """Read either the Records download or a DTR-shaped Excel sheet."""
    workbook = pd.ExcelFile(BytesIO(data))
    sheet = "Records" if "Records" in workbook.sheet_names else workbook.sheet_names[0]
    raw = pd.read_excel(workbook, sheet_name=sheet, header=None, dtype=object)
    header_row = None
    for index in range(min(30, len(raw))):
        recognized = [DTR_HEADER_MAP.get(_header_key(value)) for value in raw.iloc[index].tolist()]
        recognized = {value for value in recognized if value}
        if "Date" in recognized and "Vehicle Number" in recognized and len(recognized) >= 4:
            header_row = index
            break
    if header_row is None:
        raise ValueError("Could not find a DTR or Records header row in this workbook.")
    source = raw.iloc[header_row + 1:].copy()
    source.columns = [_text(value) for value in raw.iloc[header_row].tolist()]
    normalized = pd.DataFrame(index=source.index)
    for column in source.columns:
        target = DTR_HEADER_MAP.get(_header_key(column), _text(column))
        if not target:
            continue
        if target in normalized:
            normalized[target] = normalized[target].combine_first(source[column])
        else:
            normalized[target] = source[column]
    frame = normalized
    frame = frame.dropna(how="all").reset_index(drop=True)
    if len(frame) > 2000:
        raise ValueError("The workbook contains more than 2,000 rows. Import it in smaller files.")
    if "Date" not in frame.columns or "Vehicle Number" not in frame.columns:
        raise ValueError("This does not match the DTR or Records Download Excel format.")
    return frame


def _period(start, end):
    start_date, end_date = _date(start), _date(end)
    if not start_date and not end_date:
        return None
    start_date = start_date or end_date
    end_date = end_date or start_date
    return {"start": start_date.isoformat(), "end": end_date.isoformat()}


def _identity(values):
    invoice = re.sub(r"\s+", "", _text(values.get("invoice_number"))).casefold()
    if invoice:
        return "invoice", invoice
    return (
        "trip", values.get("trip_date"), re.sub(r"[^a-z0-9]", "", _text(values.get("vehicle_number")).casefold()),
        _text(values.get("from_location")).casefold(), _text(values.get("to_location")).casefold(),
        round(_number(values.get("revenue")), 2), round(_number(values.get("amount")), 2),
    )


def _existing_identities(records, owner):
    return {
        _identity(record) for record in records or []
        if _text(record.get("created_by")) == owner and record.get("status") != "Cancelled"
    }


def records_import_payloads(frame, existing_records=(), owner="Vijay"):
    """Convert exported rows into create-ready payloads and report skipped rows."""
    payloads, issues = [], []
    seen = _existing_identities(existing_records, owner)
    for offset, source in frame.iterrows():
        row_number = offset + 2
        get = lambda name: source.get(name, "")
        trip_date = _date(get("Date"))
        if not trip_date:
            issues.append(f"Row {row_number}: missing or invalid Date")
            continue
        is_expense = _text(get("Record Type")).casefold() in {"direct expense", "expense"}
        owner_branches = {"Vijay": "Andheri", "Ashok": "Vadodara"}
        branch = owner_branches.get(owner) or _text(get("Branch")) or "Andheri"
        payments = {
            "RTGS": _number(get("RTGS")), "Cash": _number(get("Cash")),
            "UPI": _number(get("UPI")), "Diesel": _number(get("Diesel")),
        }
        payment_mode = _text(get("Payment Mode")) or ", ".join(name for name, amount in payments.items() if amount)
        periods = {}
        insurance = _period(get("Insurance Period Start"), get("Insurance Period End"))
        vehicle_tax = _period(get("Vehicle Tax Period Start"), get("Vehicle Tax Period End"))
        if insurance:
            periods["Insurance"] = insurance
        if vehicle_tax:
            periods["Vehicle Tax"] = vehicle_tax
        categories = {column: _number(get(column)) for column in EXPENSE_EXPORT_COLUMNS}
        invoice = _text(get("Invoice Number"))
        company = canonical_company(get("Company Name"))
        ownership = canonical_ownership(get("Own / Outside"))
        dtr = {
            "Branch": branch, "Compnay Name": company, "Date": trip_date.isoformat(),
            "Vehicle No.": _text(get("Vehicle Number")), "Vehicle Type": _text(get("Vehicle Capacity")),
            "Own/Outside Veh.": ownership, "From": _text(get("From")),
            "To": _text(get("To")), "LR No.": _text(get("LR Number")), "Invoice No.": invoice,
            "Revenue": _number(get("Revenue Freight")), "Transporter Freight": _number(get("Transporter Freight")),
            "RTGS ADVANCE": payments["RTGS"], "Cash Adv.": payments["Cash"], "UPI": payments["UPI"],
            "Diesel Adv.": payments["Diesel"], "Diesel Qty": _number(get("Diesel Qty")),
            "Diesel Rate": _number(get("Diesel Rate")), "Toll Expense": _number(get("Toll Expense")),
            "Repairs & Maintenance": _number(get("Repairs & Maintenance")),
            "Repair Reason": _text(get("Repair Reason")), "Billtee": _number(get("Billtee")),
            "Total Adv.": _number(get("Total Advance")), "Balance Amt.": _number(get("Balance Amount")),
            "Payment": _number(get("Payment")), "Benificiary Name": _text(get("Beneficiary Name")),
            "Diesel Pump Name": _text(get("Diesel Pump Name")), "Card Name": _text(get("Card Name")),
            "Transporter Name": _text(get("Transporter Name")), "Veh Placed by": _text(get("Vehicle Placed By")),
            "Remark": _text(get("Remarks")),
        }
        if is_expense:
            dtr.update({
                "categories": categories, "periods": periods,
                "payments": {**payments, "Card": _number(get("Card"))},
                "Cardholders Name": _text(get("Cardholders Name")),
            })
        amount = sum(categories.values()) if is_expense else _number(get("Total Advance"))
        payload = {
            "report_scope": "Expense" if is_expense else "Both", "trip_date": trip_date,
            "vehicle_number": _text(get("Vehicle Number")), "vehicle_type": _text(get("Vehicle Capacity")),
            "ownership_type": ownership, "from_location": _text(get("From")),
            "to_location": _text(get("To")), "company_name": company, "branch": branch,
            "invoice_number": invoice, "beneficiary_name": _text(get("Beneficiary Name")),
            "transporter_name": _text(get("Transporter Name")), "expense_type": ", ".join(
                name for name, amount_value in categories.items() if amount_value
            ) if is_expense else "", "amount": amount, "payment_mode": payment_mode,
            "diesel_quantity": _number(get("Diesel Qty")) or None, "revenue": _number(get("Revenue Freight")),
            "transporter_freight": _number(get("Transporter Freight")), "rtgs_advance": payments["RTGS"],
            "cash_advance": payments["Cash"], "upi": payments["UPI"], "diesel_advance": payments["Diesel"],
            "total_advance": _number(get("Total Advance")), "balance_amount": _number(get("Balance Amount")),
            "payment": _number(get("Payment")), "status": "Verified", "notes": _text(get("Remarks")),
            "created_by": owner, "dtr_data": dtr,
            "rtgs_data": {
                "BNF_NAME": _text(get("Beneficiary Name")), "BENE_ACC_NO": _text(get("Account Number")),
                "BENE_IFSC": _text(get("IFSC Code")), "AMOUNT": payments["RTGS"],
                "REMARK": _text(get("Remarks")), "Origin Area": branch,
            },
        }
        identity = _identity(payload)
        if identity in seen:
            issues.append(f"Row {row_number}: already exists and was skipped")
            continue
        seen.add(identity)
        payloads.append(payload)
    return payloads, issues


def import_preview(payloads):
    return pd.DataFrame([{
        "Date": item["trip_date"], "Type": "Direct Expense" if item["report_scope"] == "Expense" else "Trip",
        "Vehicle": item["vehicle_number"], "From": item["from_location"], "To": item["to_location"],
        "Invoice Number": item["invoice_number"], "Revenue": item["revenue"],
    } for item in payloads])
