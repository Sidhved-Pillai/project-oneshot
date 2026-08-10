import datetime as dt
import json
import os

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from src.ai_intake import DTR_REVIEW_COLUMNS, extract_intake, result_to_records
from src.config import ROOT
from src.operational_dtr_export import export_operational_dtr
from src.rtgs_report import RTGS_COLUMNS, RTGS_REVIEW_COLUMNS, canonical_rtgs_record, export_rtgs, normalize_rtgs_records
from src.workflow_ai import convert_rtgs_to_dtr, revise_intake
from src.workflow_store import RequestStore


load_dotenv(ROOT / ".env")
st.set_page_config(page_title="Project Oneshot", page_icon="🚚", layout="wide")
STORE_INTERFACE_VERSION = 5


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


def clean_number(value):
    if value is None or (isinstance(value, str) and not value.strip()) or (not isinstance(value, str) and pd.isna(value)):
        return 0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0


def optional_number(value):
    if value is None or (isinstance(value, str) and not value.strip()) or (not isinstance(value, str) and pd.isna(value)):
        return ""
    try:
        return float(value)
    except (TypeError, ValueError):
        return ""


def clean_text(value):
    if value is None or (not isinstance(value, str) and pd.isna(value)):
        return ""
    return str(value).strip()


def record_date(value):
    parsed = pd.to_datetime(value, errors="coerce")
    return parsed.date() if not pd.isna(parsed) else dt.date.today()


def request_values(mode, record, batch_id, operator):
    if mode == "DTR":
        payload = {column: clean_text(value) if column not in {
            "Company Freight", "Revenue", "Transporter Freight", "Loading & Unloading",
            "RTGS ADVANCE", "Cash Adv.", "UPI", "Diesel Qty", "Diesel Adv.", "Billtee",
            "Total Adv.", "Balance Amt.", "Payment", "SG & Bisleri Damages", "Debit Amt.",
        } else optional_number(value) for column, value in record.items() if column != "Sr No."}
        return {
            "report_scope": "DTR", "batch_id": batch_id, "dtr_data": payload,
            "trip_date": record_date(record.get("Date")),
            "vehicle_number": clean_text(record.get("Vehicle No.")).upper().replace(" ", ""),
            "vehicle_type": clean_text(record.get("Vehicle Type")),
            "ownership_type": clean_text(record.get("Own/Outside Veh.")),
            "from_location": clean_text(record.get("From")), "to_location": clean_text(record.get("To")),
            "company_name": clean_text(record.get("Compnay Name")), "branch": clean_text(record.get("Branch")),
            "invoice_number": clean_text(record.get("Invoice No.")),
            "beneficiary_name": clean_text(record.get("Benificiary Name")),
            "transporter_name": clean_text(record.get("Transporter Name")),
            "amount": clean_number(record.get("Debit Amt.")) or clean_number(record.get("Payment")),
            "revenue": clean_number(record.get("Revenue")),
            "transporter_freight": clean_number(record.get("Transporter Freight")),
            "rtgs_advance": clean_number(record.get("RTGS ADVANCE")),
            "cash_advance": clean_number(record.get("Cash Adv.")), "upi": clean_number(record.get("UPI")),
            "diesel_quantity": clean_number(record.get("Diesel Qty")) or None,
            "diesel_advance": clean_number(record.get("Diesel Adv.")),
            "total_advance": clean_number(record.get("Total Adv.")),
            "balance_amount": clean_number(record.get("Balance Amt.")),
            "payment": clean_number(record.get("Payment")), "status": "Draft",
            "notes": clean_text(record.get("Review Notes")), "created_by": operator,
        }
    payload = {column: clean_text(value) for column, value in record.items() if column != "AMOUNT"}
    payload["AMOUNT"] = optional_number(record.get("AMOUNT"))
    return {
        "report_scope": "RTGS", "batch_id": batch_id, "rtgs_data": payload,
        "trip_date": record_date(record.get("PYMT_DATE")), "vehicle_number": "",
        "beneficiary_name": clean_text(record.get("BNF_NAME")),
        "amount": clean_number(record.get("AMOUNT")), "payment_mode": clean_text(record.get("PYMT_MODE")),
        "transporter_freight": clean_number(record.get("Transporter Freight")),
        "status": "Draft", "notes": clean_text(record.get("Review Notes")), "created_by": operator,
    }


def dtr_payload(row):
    raw = json.loads(row.get("dtr_data") or "{}")
    fallbacks = {
        "Branch": row.get("branch"), "Compnay Name": row.get("company_name"), "Date": row.get("trip_date"),
        "Vehicle No.": row.get("vehicle_number"), "Vehicle Type": row.get("vehicle_type"),
        "Own/Outside Veh.": row.get("ownership_type"), "From": row.get("from_location"),
        "Invoice No.": row.get("invoice_number"), "To": row.get("to_location"),
        "Revenue": row.get("revenue"), "Transporter Freight": row.get("transporter_freight"),
        "RTGS ADVANCE": row.get("rtgs_advance"), "Cash Adv.": row.get("cash_advance"),
        "UPI": row.get("upi"), "Diesel Qty": row.get("diesel_quantity"),
        "Diesel Adv.": row.get("diesel_advance"), "Total Adv.": row.get("total_advance"),
        "Balance Amt.": row.get("balance_amount"), "Payment": row.get("payment"),
        "Benificiary Name": row.get("beneficiary_name"), "Transporter Name": row.get("transporter_name"),
        "Review Notes": row.get("notes"),
    }
    return {column: raw.get(column, fallbacks.get(column, "")) for column in DTR_REVIEW_COLUMNS if column != "Sr No."}


try:
    store = get_store(secret("DATABASE_URL"), STORE_INTERFACE_VERSION)
except Exception as exc:
    st.error(f"Database connection failed: {exc}")
    st.stop()

st.markdown("""
<style>
:root {color-scheme:light}.stApp,[data-testid="stAppViewContainer"],[data-testid="stHeader"]{background:#faf9fc;color:#17151c}
.brand{font-size:clamp(2.2rem,5vw,3.7rem);font-weight:800;letter-spacing:-.045em;line-height:1.05}.brand span{color:#7c3aed}
.subtitle{color:#625a6b;margin:.25rem 0 1.2rem}div[data-testid="stMetric"]{background:white;border:1px solid #e8e2f0;border-radius:14px;padding:.8rem 1rem}
.stButton>button,.stDownloadButton>button{border-radius:10px}
</style>
<div class="brand">Project <span>Oneshot</span></div>
<div class="subtitle">Upload the evidence, explain the job, review the draft, and save.</div>
""", unsafe_allow_html=True)
st.caption("🟢 Persistent database connected" if store.is_durable_cloud else "🟠 Local database mode")

def rtgs_records(batch_id):
    rows = store.get_batch_requests(batch_id, "RTGS")
    records = []
    for row in rows:
        data = json.loads(row.get("rtgs_data") or "{}")
        data = canonical_rtgs_record(data)
        data["Review Notes"] = row.get("notes", "")
        records.append({column: data.get(column, "") for column in RTGS_REVIEW_COLUMNS})
    return records


def dtr_records(batch_id):
    rows = store.get_batch_requests(batch_id, "DTR")
    records = []
    for index, row in enumerate(rows, 1):
        records.append({"Sr No.": index, **dtr_payload(row)})
    return records


def active_records(frame, mode):
    ignored = {"Sr No.", "Review Notes"}
    columns = [column for column in frame.columns if column not in ignored]
    return [row for row in frame.to_dict("records") if any(clean_text(row.get(column)) for column in columns)]


def sync_records(batch_id, mode, records, operator, source):
    values = [request_values(mode, record, batch_id, operator) for record in records]
    for value in values:
        value["status"] = "Verified"
    return store.sync_batch_records(batch_id, mode, values, operator, source)


def batch_name(batch):
    return batch.get("request_label") or batch["batch_id"]


def source_files(batch_id):
    return [{"filename": item["filename"], "mime_type": item["mime_type"], "data": item["payload"]}
            for item in store.get_attachments(batch_id)]


new_tab, rtgs_tab, pending_tab, dtr_tab, delete_tab = st.tabs([
    "New Entry", "RTGS Records", "Pending DTR updation", "DTR Records", "Delete Records From Memory",
])

with new_tab:
    st.subheader("Upload Trip Details Here")
    uploads = st.file_uploader(
        "WhatsApp images or PDFs", type=["jpg", "jpeg", "png", "webp", "pdf"],
        accept_multiple_files=True, key="rtgs_uploads",
    )
    prompt = st.text_area(
        "Trip and beneficiary details",
        placeholder="Paste the WhatsApp trip message and beneficiary name here. Keep the image/message pairs in WhatsApp order.",
        height=130, key="rtgs_prompt",
    )
    st.caption("Files and instructions are sent to Gemini. Review every beneficiary, account number, IFSC and amount before saving.")
    if st.button("Generate live RTGS review", type="primary", disabled=not uploads and not prompt.strip()):
        files = [{"filename": item.name, "mime_type": item.type or "application/octet-stream", "data": item.getvalue()} for item in uploads]
        if any(len(item["data"]) > 8 * 1024 * 1024 for item in files):
            st.error("Each uploaded file must be 8 MB or smaller.")
        else:
            try:
                with st.spinner("Reading the payment evidence and creating RTGS rows…"):
                    result, model_used = extract_intake(secret("GEMINI_API_KEY"), "RTGS", prompt, files, secret("GEMINI_MODEL"))
                records = normalize_rtgs_records(result_to_records("RTGS", result), dt.date.today())
                st.session_state.update({
                    "new_rtgs_draft": pd.DataFrame(records), "new_rtgs_original": records,
                    "new_rtgs_files": files, "new_rtgs_prompt_saved": prompt,
                    "new_rtgs_summary": result.summary, "new_rtgs_model": model_used,
                })
            except Exception as exc:
                st.error(f"Could not generate the RTGS draft: {exc}")
    if "new_rtgs_draft" in st.session_state:
        st.subheader("Live RTGS review")
        st.caption("Correct the table before saving. You can add or remove rows.")
        reviewed_rtgs = st.data_editor(st.session_state["new_rtgs_draft"], num_rows="dynamic", hide_index=True,
                                       width="stretch", key="new_rtgs_editor")
        if st.button("Save RTGS Record & Prepare Download", type="primary"):
            records = normalize_rtgs_records(active_records(reviewed_rtgs, "RTGS"), dt.date.today())
            if not records:
                st.error("There are no non-empty RTGS rows to save.")
            else:
                batch_id = store.create_batch(
                    "RTGS", "Nikhat", st.session_state["new_rtgs_prompt_saved"], st.session_state["new_rtgs_files"],
                    st.session_state["new_rtgs_original"], st.session_state.get("new_rtgs_summary", ""),
                    st.session_state.get("new_rtgs_model", ""),
                )
                numbers = sync_records(batch_id, "RTGS", records, "Nikhat", "initial_review")
                batch = store.get_batch(batch_id)
                st.session_state["new_rtgs_download"] = {
                    "label": batch_name(batch), "payload": export_rtgs(pd.DataFrame(records), dt.date.today()),
                }
                st.success(f"Saved {batch_name(batch)} with {len(numbers)} RTGS row(s). It is now pending for Shyam.")
                for key in ["new_rtgs_draft", "new_rtgs_original", "new_rtgs_files", "new_rtgs_prompt_saved", "new_rtgs_summary", "new_rtgs_model"]:
                    st.session_state.pop(key, None)
    if st.session_state.get("new_rtgs_download"):
        download = st.session_state["new_rtgs_download"]
        st.download_button("Download RTGS Report", download["payload"], f"{download['label'].replace('/', '-')}.xls",
                           "application/vnd.ms-excel", type="primary")

with rtgs_tab:
    st.subheader("RTGS Records")
    batches = store.list_batches()
    if not batches:
        st.info("No RTGS records have been saved yet.")
    else:
        date_col1, date_col2 = st.columns(2)
        start_date = date_col1.date_input("Created from", value=dt.date.today() - dt.timedelta(days=30), key="rtgs_from")
        end_date = date_col2.date_input("Created to", value=dt.date.today(), key="rtgs_to")
        batches = [batch for batch in batches if start_date <= record_date(batch.get("created_at")) <= end_date]
        labels = {batch_name(batch): batch for batch in batches if batch.get("row_counts", {}).get("RTGS", 0)}
        if not labels:
            st.info("No RTGS records have been saved yet.")
        else:
            label = st.selectbox("Select request", list(labels), key="rtgs_batch_select")
            batch = labels[label]
            base = st.session_state.get(f"rtgs_ai_{batch['batch_id']}") or rtgs_records(batch["batch_id"])
            edit_key = f"rtgs_editing_{batch['batch_id']}"
            if st.button("Edit RTGS Record", key=f"rtgs_edit_{batch['batch_id']}"):
                st.session_state[edit_key] = not st.session_state.get(edit_key, False)
            if st.session_state.get(edit_key):
                rtgs_frame = st.data_editor(pd.DataFrame(base), num_rows="dynamic", hide_index=True, width="stretch",
                                            key=f"rtgs_batch_editor_{batch['batch_id']}")
            else:
                rtgs_frame = pd.DataFrame(base)
                st.dataframe(rtgs_frame, hide_index=True, width="stretch")
            instruction = st.text_area("Ask Oneshot to change this RTGS request", key=f"rtgs_change_{batch['batch_id']}",
                                       disabled=not st.session_state.get(edit_key), placeholder="Example: Change the beneficiary name in row 2.")
            c1, c2 = st.columns(2)
            if c1.button("Apply prompt to RTGS table", disabled=not instruction.strip(), key=f"rtgs_ai_button_{batch['batch_id']}"):
                try:
                    result, _ = revise_intake(secret("GEMINI_API_KEY"), "RTGS", rtgs_frame.to_dict("records"), instruction,
                                              [], secret("GEMINI_MODEL"))
                    st.session_state[f"rtgs_ai_{batch['batch_id']}"] = normalize_rtgs_records(
                        result_to_records("RTGS", result), dt.date.today()
                    )
                    st.rerun()
                except Exception as exc:
                    st.error(f"Could not apply the requested changes: {exc}")
            if c2.button("Save RTGS changes", type="primary", disabled=not st.session_state.get(edit_key), key=f"rtgs_save_{batch['batch_id']}"):
                records = normalize_rtgs_records(active_records(rtgs_frame, "RTGS"), dt.date.today())
                sync_records(batch["batch_id"], "RTGS", records, "Nikhat", "manual_or_ai_edit")
                st.success(f"Saved changes to {label}.")
            st.download_button("Download current RTGS Report", export_rtgs(rtgs_frame, dt.date.today()),
                               f"{label.replace('/', '-')}.xls", "application/vnd.ms-excel")

with pending_tab:
    st.subheader("Pending DTR updation")
    pending = [batch for batch in store.list_batches("Pending") if batch.get("row_counts", {}).get("RTGS", 0)]
    if not pending:
        st.success("No RTGS requests are waiting for DTR work.")
    else:
        pending_labels = {batch_name(batch): batch for batch in pending}
        label = st.selectbox("View Request", list(pending_labels), key="pending_batch")
        batch = pending_labels[label]
        finalized_rtgs = rtgs_records(batch["batch_id"])
        st.markdown("##### Nikhat's finalized RTGS table")
        st.dataframe(pd.DataFrame(finalized_rtgs), hide_index=True, width="stretch")
        dtr_instruction = st.text_area("Instructions for DTR creation", key=f"dtr_create_prompt_{batch['batch_id']}",
                                       placeholder="Add any known DTR details. Missing LR, invoice, diesel, UPI, revenue and freight can be completed later.")
        extra_uploads = st.file_uploader(
            "Upload diesel expenses, LR, invoices, UPI details or other DTR images",
            type=["jpg", "jpeg", "png", "webp", "pdf"], accept_multiple_files=True,
            key=f"dtr_uploads_{batch['batch_id']}",
        )
        if st.button("Create DTR Spreadsheet", type="primary", key=f"create_dtr_{batch['batch_id']}"):
            try:
                new_files = [{"filename": item.name, "mime_type": item.type or "application/octet-stream", "data": item.getvalue()}
                             for item in extra_uploads]
                if new_files:
                    store.add_attachments(batch["batch_id"], new_files)
                with st.spinner("Creating Shyam's DTR draft from the finalized RTGS request…"):
                    result, _ = convert_rtgs_to_dtr(secret("GEMINI_API_KEY"), finalized_rtgs, dtr_instruction,
                                                    source_files(batch["batch_id"]), secret("GEMINI_MODEL"))
                st.session_state[f"pending_dtr_{batch['batch_id']}"] = result_to_records("DTR", result)
                st.rerun()
            except Exception as exc:
                st.error(f"Could not create the DTR draft: {exc}")
        draft_key = f"pending_dtr_{batch['batch_id']}"
        if draft_key in st.session_state:
            dtr_frame = st.data_editor(pd.DataFrame(st.session_state[draft_key]), num_rows="dynamic", hide_index=True,
                                       width="stretch", key=f"pending_dtr_editor_{batch['batch_id']}")
            update_prompt = st.text_area("Ask Oneshot to update this DTR", key=f"pending_dtr_change_{batch['batch_id']}")
            update_uploads = st.file_uploader(
                "Upload more evidence for this update", type=["jpg", "jpeg", "png", "webp", "pdf"],
                accept_multiple_files=True, key=f"dtr_update_uploads_{batch['batch_id']}",
            )
            if st.button("Update DTR", disabled=not update_prompt.strip() and not update_uploads,
                         key=f"pending_dtr_ai_{batch['batch_id']}"):
                try:
                    new_files = [{"filename": item.name, "mime_type": item.type or "application/octet-stream", "data": item.getvalue()}
                                 for item in update_uploads]
                    if new_files:
                        store.add_attachments(batch["batch_id"], new_files)
                    result, _ = revise_intake(secret("GEMINI_API_KEY"), "DTR", dtr_frame.to_dict("records"), update_prompt,
                                              new_files, secret("GEMINI_MODEL"))
                    st.session_state[draft_key] = result_to_records("DTR", result)
                    st.rerun()
                except Exception as exc:
                    st.error(f"Could not update the DTR draft: {exc}")
            if st.button("Save DTR Changes & Prepare Download", type="primary", key=f"pending_dtr_save_{batch['batch_id']}"):
                records = active_records(dtr_frame, "DTR")
                sync_records(batch["batch_id"], "DTR", records, "Shyam", "dtr_creation")
                store.set_batch_dtr_status(batch["batch_id"], "Completed")
                st.session_state["dtr_download"] = {"label": label, "payload": export_operational_dtr(pd.DataFrame(records))}
                st.session_state.pop(draft_key, None)
                st.success(f"Saved DTR for {label}. It is now available under DTR Records.")
        if st.session_state.get("dtr_download") and st.session_state["dtr_download"]["label"] == label:
            st.download_button("Download DTR Excel", st.session_state["dtr_download"]["payload"], f"DTR-{label}.xlsx",
                               "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", type="primary")

with dtr_tab:
    st.subheader("DTR Records")
    completed = store.list_batches("Completed")
    if not completed:
        st.info("No DTR reports have been completed yet.")
    else:
        completed_labels = {batch_name(batch): batch for batch in completed}
        label = st.selectbox("Select DTR request", list(completed_labels), key="completed_batch")
        batch = completed_labels[label]
        dtr_frame = pd.DataFrame(dtr_records(batch["batch_id"]))
        st.dataframe(dtr_frame, hide_index=True, width="stretch")
        c1, c2 = st.columns(2)
        c1.download_button("Download DTR Spreadsheet", export_operational_dtr(dtr_frame),
                           f"DTR-{label.replace('/', '-')}.xlsx",
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        rtgs_frame = pd.DataFrame(rtgs_records(batch["batch_id"]))
        c2.download_button("Download RTGS Spreadsheet", export_rtgs(rtgs_frame, dt.date.today()),
                           f"{label.replace('/', '-')}.xls", "application/vnd.ms-excel")

with delete_tab:
    st.subheader("Delete Records From Memory")
    st.error("Deletion is permanent. No record is ever removed automatically; this is the only deletion control.")
    batches = store.list_batches()
    if not batches:
        st.info("There are no saved records to delete.")
    else:
        deletion_labels = {batch_name(batch): batch for batch in batches}
        label = st.selectbox("Select the complete request to delete", list(deletion_labels), key="delete_batch")
        batch = deletion_labels[label]
        st.write({"Request": label, "Created": str(batch.get("created_at")), "Rows": batch.get("row_counts", {})})
        confirmation = st.text_input(f"Type {label} to confirm permanent deletion", key="delete_confirmation")
        acknowledged = st.checkbox("I understand that the RTGS rows, DTR rows, source files and revision history will be permanently deleted.")
        if st.button("Permanently Delete This Request", disabled=confirmation != label or not acknowledged, type="primary"):
            result = store.delete_batch(batch["batch_id"])
            st.success(f"Deleted {label} and {result['requests']} associated record row(s). This cannot be recovered.")
            st.rerun()
