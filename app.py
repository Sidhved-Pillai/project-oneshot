import datetime as dt
import hashlib
import json
import os

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from src.ai_intake import DTR_REVIEW_COLUMNS, extract_intake
from src.config import ROOT
from src.operational_dtr_export import export_operational_dtr
from src.pnl_report import DIRECT_EXPENSE_COLUMNS, export_pnl, pnl_summary
from src.rtgs_report import RTGS_REVIEW_COLUMNS, export_rtgs, normalize_rtgs_records
from src.workflow_store import RequestStore

load_dotenv(ROOT / ".env")
st.set_page_config(page_title="Project Oneshot", page_icon="🚚", layout="wide")
STORE_INTERFACE_VERSION = 6
PAYMENT_FIELDS = {"UPI": "upi", "Diesel": "diesel_advance", "Cash": "cash_advance", "RTGS": "rtgs_advance"}


def secret(name):
    if os.getenv(name):
        return os.environ[name]
    try:
        return st.secrets.get(name)
    except (FileNotFoundError, KeyError):
        return None


@st.cache_resource
def get_store(url, interface_version):
    return RequestStore(url)


def clean_text(value):
    return "" if value is None or (not isinstance(value, str) and pd.isna(value)) else str(value).strip()


def number(value):
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def as_date(value):
    parsed = pd.to_datetime(value, errors="coerce")
    return parsed.date() if not pd.isna(parsed) else dt.date.today()


def unpack(value):
    if isinstance(value, dict):
        return value
    try:
        return json.loads(value or "{}")
    except (TypeError, json.JSONDecodeError):
        return {}


def request_label(row_or_number, date=None):
    if isinstance(row_or_number, dict):
        date = row_or_number.get("trip_date")
        row_or_number = row_or_number.get("request_number", "")
    suffix = clean_text(row_or_number).split("-")[-1].lstrip("0") or "1"
    return f"Request - {as_date(date):%d/%m/%y} · {suffix}"


def rtgs_remark(row):
    existing = unpack(row.get("rtgs_data")).get("REMARK") or row.get("notes")
    if clean_text(existing):
        return clean_text(existing)
    digits = "".join(character for character in clean_text(row.get("vehicle_number")) if character.isdigit())[-4:]
    origin, destination = clean_text(row.get("from_location")), clean_text(row.get("to_location"))
    route = f"{origin} to {destination}" if origin and destination else origin or destination
    parts = [digits, route, clean_text(row.get("vehicle_type")), f"{as_date(row.get('trip_date')):%d %m %Y}", "TA"]
    return " ".join(part for part in parts if part).strip()


def evidence(upload, audio):
    files = []
    if upload:
        files.append({"filename": upload.name, "mime_type": upload.type or "application/octet-stream", "data": upload.getvalue()})
    if audio:
        files.append({"filename": "voice-instruction.wav", "mime_type": audio.type or "audio/wav", "data": audio.getvalue()})
    return files


def autofill(files, instruction, prefix, mode="ENTRY"):
    if not files:
        return
    signature = hashlib.sha256(b"".join(item["data"] for item in files) + instruction.encode()).hexdigest()
    if st.session_state.get(f"{prefix}_evidence_hash") == signature:
        return
    st.session_state[f"{prefix}_evidence_hash"] = signature
    try:
        with st.spinner("Reading the evidence and filling the form…"):
            result, _ = extract_intake(secret("GEMINI_API_KEY"), mode, instruction, files, secret("GEMINI_MODEL"))
        if not result.rows:
            st.warning("No clear trip details were found. Complete the form manually.")
            return
        expense_keys = {
            "route_expense": "category_0", "bill_discounting": "category_1", "salary": "category_2",
            "driver_salary": "category_3", "rent": "category_4", "office_general_expenses": "category_5",
            "conveyance": "category_6", "emi": "category_7", "insurance": "category_8",
            "vehicle_tax": "category_9", "repair_maintenance": "category_10", "interest": "category_11",
            "beneficiary_name": "beneficiary", "vehicle_number": "vehicle",
        }
        for field, value in result.rows[0].model_dump().items():
            if value not in (None, ""):
                state_field = expense_keys.get(field, field) if mode == "EXPENSE" else field
                st.session_state[f"{prefix}_{state_field}"] = as_date(value) if field == "date" else value
        st.success("Form populated from the evidence. Please review every field before saving.")
    except Exception as exc:
        st.error(f"Could not auto-fill the form: {exc}")


def file_values(files):
    source = next((f for f in files if f["mime_type"].startswith("image/") or f["mime_type"] == "application/pdf"), None)
    return {"source_filename": source["filename"] if source else "", "source_mime_type": source["mime_type"] if source else "", "source_image": source["data"] if source else None}


def trip_payload(v, files):
    payments = {name: number(v[field]) for name, field in PAYMENT_FIELDS.items()}
    total = sum(payments.values())
    dtr = {
        "Branch": v["branch"], "Compnay Name": v["company_name"], "Date": v["date"], "Vehicle No.": v["vehicle_number"],
        "Vehicle Type": v["vehicle_capacity"], "Own/Outside Veh.": v["ownership_type"], "From": v["from_location"],
        "To": v["to_location"], "LR No.": v["lr_invoice_number"], "Invoice No.": v["lr_invoice_number"],
        "Revenue": v["revenue"], "Transporter Freight": v["transporter_freight"], "RTGS ADVANCE": v["rtgs_advance"],
        "Cash Adv.": v["cash_advance"], "UPI": v["upi"], "Diesel Adv.": v["diesel_advance"], "Total Adv.": total,
        "Balance Amt.": max(number(v["transporter_freight"]) - total, 0), "Benificiary Name": v["beneficiary_name"],
        "Transporter Name": v["transporter_name"], "Veh Placed by": v["vehicle_placed_by"], "Remark": v["remarks"],
    }
    rtgs = {"BNF_NAME": v["beneficiary_name"], "BENE_ACC_NO": v["beneficiary_account_number"], "BENE_IFSC": v["beneficiary_ifsc_code"], "AMOUNT": v["rtgs_advance"], "REMARK": v["remarks"], "Origin Area": v["branch"]}
    return {
        "report_scope": "Both", "trip_date": v["date"], "vehicle_number": v["vehicle_number"], "vehicle_type": v["vehicle_capacity"],
        "ownership_type": v["ownership_type"], "from_location": v["from_location"], "to_location": v["to_location"],
        "company_name": v["company_name"], "branch": v["branch"], "invoice_number": v["lr_invoice_number"],
        "beneficiary_name": v["beneficiary_name"], "transporter_name": v["transporter_name"], "amount": total,
        "payment_mode": ", ".join(name for name, amount in payments.items() if amount), "revenue": v["revenue"],
        "transporter_freight": v["transporter_freight"], "rtgs_advance": v["rtgs_advance"], "cash_advance": v["cash_advance"],
        "upi": v["upi"], "diesel_advance": v["diesel_advance"], "total_advance": total,
        "balance_amount": max(number(v["transporter_freight"]) - total, 0), "status": "Submitted", "notes": v["remarks"],
        "dtr_data": dtr, "rtgs_data": rtgs, **file_values(files),
    }


def expense_payload(v, files):
    payments = {name: number(v[field]) for name, field in PAYMENT_FIELDS.items()}
    categories = {name: number(v[name]) for name in DIRECT_EXPENSE_COLUMNS}
    return {
        "report_scope": "Expense", "trip_date": v["date"], "vehicle_number": v["vehicle_number"],
        "beneficiary_name": v["beneficiary_name"], "expense_type": ", ".join(k for k, val in categories.items() if val),
        "amount": sum(categories.values()), "payment_mode": ", ".join(k for k, val in payments.items() if val),
        "rtgs_advance": payments["RTGS"], "cash_advance": payments["Cash"], "upi": payments["UPI"],
        "diesel_advance": payments["Diesel"], "total_advance": sum(payments.values()), "notes": v["remarks"],
        "status": "Submitted", "dtr_data": {"categories": categories, "payments": payments}, **file_values(files),
    }


def trip_form(prefix):
    st.markdown("#### 1. Basic information")
    c1, c2 = st.columns(2)
    v = {"date": c1.date_input("Date *", value=st.session_state.get(f"{prefix}_date", dt.date.today()), key=f"{prefix}_date"), "branch": c2.text_input("Branch *", key=f"{prefix}_branch", placeholder="e.g., Pune"), "company_name": st.text_input("Company name *", key=f"{prefix}_company_name")}
    c1, c2 = st.columns(2)
    v["from_location"] = c1.text_input("From *", key=f"{prefix}_from_location")
    v["to_location"] = c2.text_input("To *", key=f"{prefix}_to_location")
    v["lr_invoice_number"] = st.text_input("LR / Invoice number", key=f"{prefix}_lr_invoice_number")
    st.markdown("#### 2. Vehicle information")
    c1, c2, c3 = st.columns(3)
    v["vehicle_number"] = c1.text_input("Vehicle number *", key=f"{prefix}_vehicle_number")
    v["vehicle_capacity"] = c2.text_input("Vehicle capacity", key=f"{prefix}_vehicle_capacity", placeholder="e.g., 20MT")
    choices = ["", "Own", "Outside"]
    current = st.session_state.get(f"{prefix}_ownership_type", "")
    v["ownership_type"] = c3.selectbox("Own or outside", choices, index=choices.index(current) if current in choices else 0, key=f"{prefix}_ownership_type")
    v["vehicle_placed_by"] = st.text_input("Vehicle placed by", key=f"{prefix}_vehicle_placed_by")
    st.markdown("#### 3. Beneficiary details")
    c1, c2 = st.columns(2)
    v["beneficiary_name"] = c1.text_input("Beneficiary name", key=f"{prefix}_beneficiary_name")
    v["transporter_name"] = c2.text_input("Transporter name", key=f"{prefix}_transporter_name")
    c1, c2 = st.columns(2)
    v["beneficiary_account_number"] = c1.text_input("Account number", key=f"{prefix}_beneficiary_account_number")
    v["beneficiary_ifsc_code"] = c2.text_input("IFSC code", key=f"{prefix}_beneficiary_ifsc_code")
    st.markdown("#### 4. Payment details")
    c1, c2 = st.columns(2)
    v["revenue"] = c1.number_input("Revenue freight (₹)", min_value=0.0, key=f"{prefix}_revenue")
    v["transporter_freight"] = c2.number_input("Transporter freight (₹)", min_value=0.0, key=f"{prefix}_transporter_freight")
    st.caption("Enter amounts in every payment mode used. More than one mode is supported.")
    for col, (label, field) in zip(st.columns(4), PAYMENT_FIELDS.items()):
        v[field] = col.number_input(f"{label} (₹)", min_value=0.0, key=f"{prefix}_{field}")
    total = sum(number(v[f]) for f in PAYMENT_FIELDS.values())
    summary = st.columns(3)
    summary[0].metric("Transporter freight", f"₹{number(v['transporter_freight']):,.2f}")
    summary[1].metric("Total advance", f"₹{total:,.2f}")
    summary[2].metric("Balance payable", f"₹{max(number(v['transporter_freight']) - total, 0):,.2f}")
    v["remarks"] = st.text_area("Remarks", key=f"{prefix}_remarks")
    return v


try:
    store = get_store(secret("DATABASE_URL"), STORE_INTERFACE_VERSION)
except Exception as exc:
    st.error(f"Database connection failed: {exc}")
    st.stop()

st.markdown("""<style>:root{color-scheme:light}.stApp,[data-testid="stAppViewContainer"],[data-testid="stHeader"]{background:#f5f7f7;color:#17212b}.block-container{max-width:1180px;padding-top:2rem}.brand{font-size:2.5rem;font-weight:800;letter-spacing:-.04em;color:#102a2a}.brand span{color:#0f766e}.subtitle{color:#667085;margin:.2rem 0 1.4rem}.stTabs [data-baseweb="tab-list"]{gap:8px;background:#fff;padding:8px;border:1px solid #e4e8e7;border-radius:14px}.stTabs [data-baseweb="tab"]{border-radius:10px;padding:8px 18px}.stTabs [aria-selected="true"]{background:#e6f4f1;color:#075e57}div[data-testid="stVerticalBlockBorderWrapper"]{background:#fff;border-color:#dfe7e5!important;border-radius:16px}.stButton>button,.stDownloadButton>button{border-radius:10px}div[data-testid="stMetric"]{background:#f1f8f6;border:1px solid #d9ebe7;border-radius:12px;padding:.8rem 1rem}</style><div class="brand">Project <span>Oneshot</span></div><div class="subtitle">One record. Every operations report.</div>""", unsafe_allow_html=True)
st.caption("🟢 Persistent database connected" if store.is_durable_cloud else "🟠 Local database mode")
new_tab, expense_tab, records_tab, reports_tab = st.tabs(["New Entry", "Direct Expenses", "Records", "Generate Reports"])

with new_tab:
    st.subheader("New trip entry")
    st.caption("Upload evidence or record an English, Hindi, or Marathi instruction. Oneshot fills the form for review.")
    c1, c2 = st.columns(2)
    upload = c1.file_uploader("Upload photo or PDF", type=["jpg", "jpeg", "png", "webp", "pdf"], key="trip_upload")
    audio = c2.audio_input("Voice instruction · English / हिन्दी / मराठी", key="trip_audio")
    instruction = st.text_input("Optional typed instruction", placeholder="e.g., Invoice number is 12234", key="trip_instruction")
    files = evidence(upload, audio)
    autofill(files, instruction, "trip")
    with st.container(border=True):
        values = trip_form("trip")
        if st.button("Save record", type="primary", disabled=not values["branch"] or not values["vehicle_number"], key="save_trip"):
            saved = store.create({**trip_payload(values, files), "created_by": "Operations user"})
            st.success(f"Saved {request_label(saved, values['date'])}. Entries remain filled for the next record.")

with expense_tab:
    st.subheader("Direct expense")
    st.caption("Upload a bill or record a voice instruction to fill the expense form automatically.")
    c1, c2 = st.columns(2)
    expense_upload = c1.file_uploader("Attach bill or receipt", type=["jpg", "jpeg", "png", "webp", "pdf"], key="expense_upload")
    expense_audio = c2.audio_input("Voice instruction · English / हिन्दी / मराठी", key="expense_audio")
    expense_instruction = st.text_input("Optional expense instruction", key="expense_instruction")
    expense_files = evidence(expense_upload, expense_audio)
    autofill(expense_files, expense_instruction, "expense", "EXPENSE")
    with st.container(border=True):
        c1, c2, c3 = st.columns(3)
        v = {"date": c1.date_input("Date *", key="expense_date"), "beneficiary_name": c2.text_input("Beneficiary name", key="expense_beneficiary"), "vehicle_number": c3.text_input("Vehicle name / number", key="expense_vehicle")}
        st.markdown("#### Expense breakdown")
        cols = st.columns(3)
        for i, category in enumerate(DIRECT_EXPENSE_COLUMNS):
            v[category] = cols[i % 3].number_input(f"{category} (₹)", min_value=0.0, key=f"expense_category_{i}")
        v["remarks"] = st.text_area("Remarks", key="expense_remarks")
        st.markdown("#### Mode of payment")
        st.caption("Fill every mode used for this expense.")
        for col, (label, field) in zip(st.columns(4), PAYMENT_FIELDS.items()):
            v[field] = col.number_input(f"{label} (₹)", min_value=0.0, key=f"expense_{field}")
        expense_total = sum(number(v[name]) for name in DIRECT_EXPENSE_COLUMNS)
        paid_total = sum(number(v[field]) for field in PAYMENT_FIELDS.values())
        c1, c2 = st.columns(2)
        c1.metric("Total direct expense", f"₹{expense_total:,.2f}")
        c2.metric("Payment modes total", f"₹{paid_total:,.2f}")
        if paid_total and abs(expense_total - paid_total) > 0.01:
            st.warning("Expense total and payment-mode total do not match. Review before saving.")
        if st.button("Save direct expense", type="primary", key="save_expense"):
            saved = store.create({**expense_payload(v, expense_files), "created_by": "Operations user"})
            st.success(f"Saved {request_label(saved, v['date'])}.")

with records_tab:
    st.subheader("Records")
    rows = store.list(status="All active")
    if not rows:
        st.info("No records have been saved yet.")
    else:
        labels = {request_label(row): row for row in rows}
        selected_label = st.selectbox("Select a record", list(labels), key="record_select")
        row = labels[selected_label]
        raw, is_expense = unpack(row.get("dtr_data")), row.get("report_scope") == "Expense"
        rtgs_raw = unpack(row.get("rtgs_data"))
        display = {"Date": row.get("trip_date"), "Type": "Direct expense" if is_expense else "Trip", "Branch": row.get("branch", ""), "Company": row.get("company_name", ""), "Vehicle": row.get("vehicle_number", ""), "Vehicle Capacity": row.get("vehicle_type", ""), "Own / Outside": row.get("ownership_type", ""), "From": row.get("from_location", ""), "To": row.get("to_location", ""), "LR / Invoice": row.get("invoice_number", ""), "Beneficiary": row.get("beneficiary_name", ""), "Account Number": rtgs_raw.get("BENE_ACC_NO", ""), "IFSC": rtgs_raw.get("BENE_IFSC", ""), "Vehicle Placed By": raw.get("Veh Placed by", ""), "Revenue": number(row.get("revenue")), "Transporter Freight": number(row.get("transporter_freight")), "RTGS": number(row.get("rtgs_advance")), "Cash": number(row.get("cash_advance")), "UPI": number(row.get("upi")), "Diesel": number(row.get("diesel_advance")), "Remarks": row.get("notes", "")}
        if is_expense:
            display.update(raw.get("categories", {}))
        edited = st.data_editor(pd.DataFrame([display]), hide_index=True, width="stretch", disabled=["Type"], key=f"record_editor_{row['request_number']}")
        if row.get("source_image"):
            st.markdown("#### Attached evidence")
            if clean_text(row.get("source_mime_type")).startswith("image/"):
                st.image(row["source_image"], caption=row.get("source_filename", "Evidence"), width=500)
            else:
                st.download_button("Open attached evidence", row["source_image"], row.get("source_filename", "evidence.pdf"), row.get("source_mime_type"))
        if st.button("Save record changes", type="primary", key=f"save_record_{row['request_number']}"):
            item = edited.iloc[0].to_dict()
            update_values = {"trip_date": as_date(item["Date"]), "branch": clean_text(item["Branch"]), "company_name": clean_text(item["Company"]), "vehicle_number": clean_text(item["Vehicle"]), "vehicle_type": clean_text(item["Vehicle Capacity"]), "ownership_type": clean_text(item["Own / Outside"]), "from_location": clean_text(item["From"]), "to_location": clean_text(item["To"]), "invoice_number": clean_text(item["LR / Invoice"]), "beneficiary_name": clean_text(item["Beneficiary"]), "revenue": number(item["Revenue"]), "transporter_freight": number(item["Transporter Freight"]), "rtgs_advance": number(item["RTGS"]), "cash_advance": number(item["Cash"]), "upi": number(item["UPI"]), "diesel_advance": number(item["Diesel"]), "notes": clean_text(item["Remarks"])}
            if is_expense:
                categories = {name: number(item.get(name)) for name in DIRECT_EXPENSE_COLUMNS}
                update_values.update({"amount": sum(categories.values()), "dtr_data": {**raw, "categories": categories}})
            else:
                total = sum(number(item[name]) for name in ("RTGS", "Cash", "UPI", "Diesel"))
                updated_dtr = {**raw, "Branch": item["Branch"], "Compnay Name": item["Company"], "Date": as_date(item["Date"]), "Vehicle No.": item["Vehicle"], "Vehicle Type": item["Vehicle Capacity"], "Own/Outside Veh.": item["Own / Outside"], "From": item["From"], "To": item["To"], "LR No.": item["LR / Invoice"], "Invoice No.": item["LR / Invoice"], "Revenue": item["Revenue"], "Transporter Freight": item["Transporter Freight"], "RTGS ADVANCE": item["RTGS"], "Cash Adv.": item["Cash"], "UPI": item["UPI"], "Diesel Adv.": item["Diesel"], "Total Adv.": total, "Benificiary Name": item["Beneficiary"], "Veh Placed by": item["Vehicle Placed By"], "Remark": item["Remarks"]}
                updated_rtgs = {**rtgs_raw, "BNF_NAME": item["Beneficiary"], "BENE_ACC_NO": item["Account Number"], "BENE_IFSC": item["IFSC"], "AMOUNT": item["RTGS"], "REMARK": item["Remarks"], "Origin Area": item["Branch"]}
                update_values.update({"amount": total, "total_advance": total, "dtr_data": updated_dtr, "rtgs_data": updated_rtgs})
            store.update(row["request_number"], update_values, "records_tab", "Operations user")
            st.success("Record updated. A revision snapshot was saved.")
            st.rerun()
        with st.expander("Delete records"):
            select_all = st.checkbox("Select all", key="records_delete_all")
            chosen = list(labels) if select_all else st.multiselect("Select records", list(labels), key="records_delete_selection")
            acknowledged = st.checkbox("I understand this permanently deletes the selected records.", key="records_delete_ack")
            if st.button("Delete selected records", disabled=not chosen or not acknowledged, key="records_delete"):
                for label in chosen:
                    store.delete_request(labels[label]["request_number"])
                st.success(f"Deleted {len(chosen)} record(s).")
                st.rerun()

with reports_tab:
    st.subheader("Generate reports")
    c1, c2 = st.columns(2)
    start = c1.date_input("Records from", value=dt.date.today() - dt.timedelta(days=30), key="report_from")
    end = c2.date_input("Records to", value=dt.date.today(), key="report_to")
    report_type = st.segmented_control("Report type", ["DTR", "RTGS", "P&L"], default="DTR", key="report_type")
    selected_rows = store.list(start, end, status="All active") if start <= end else []
    trips = [row for row in selected_rows if row.get("report_scope") != "Expense"]
    expenses = [row for row in selected_rows if row.get("report_scope") == "Expense"]
    st.caption(f"{len(trips)} trip record(s) and {len(expenses)} direct expense record(s) selected.")
    if report_type == "DTR":
        records = []
        for i, row in enumerate(reversed(trips), 1):
            data = unpack(row.get("dtr_data"))
            records.append({column: data.get(column, "") for column in DTR_REVIEW_COLUMNS} | {"Sr No.": i})
        frame = pd.DataFrame(records, columns=DTR_REVIEW_COLUMNS)
        st.dataframe(frame, hide_index=True, width="stretch")
        st.download_button("Download DTR report", export_operational_dtr(frame), f"DTR-{start}-{end}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", type="primary", disabled=frame.empty)
    elif report_type == "RTGS":
        records = []
        for row in reversed([item for item in trips if number(item.get("rtgs_advance")) > 0]):
            data = unpack(row.get("rtgs_data"))
            data["AMOUNT"], data["BNF_NAME"] = data.get("AMOUNT") or row.get("rtgs_advance"), data.get("BNF_NAME") or row.get("beneficiary_name")
            data["REMARK"] = rtgs_remark(row)
            records.append(data)
        records = normalize_rtgs_records(records, dt.date.today())
        frame = pd.DataFrame(records, columns=RTGS_REVIEW_COLUMNS)
        st.dataframe(frame, hide_index=True, width="stretch")
        st.download_button("Download bank-format RTGS report", export_rtgs(frame, dt.date.today()), f"RTGS-{start}-{end}.xls", "application/vnd.ms-excel", type="primary", disabled=frame.empty)
    else:
        expense_data = [{**row, "categories": unpack(row.get("dtr_data")).get("categories", {})} for row in expenses]
        frame = pd.DataFrame(pnl_summary(trips, expense_data))
        st.dataframe(frame, hide_index=True, width="stretch")
        st.download_button("Download P&L report", export_pnl(trips, expense_data, start, end), f"PNL-{start}-{end}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", type="primary")
