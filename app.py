import datetime as dt
import json
import os

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from src.ai_intake import DTR_REVIEW_COLUMNS, extract_intake, result_to_records
from src.config import ROOT
from src.request_store import RequestStore
from src.rtgs_report import RTGS_COLUMNS


load_dotenv(ROOT / ".env")
st.set_page_config(page_title="Project Oneshot", page_icon="🚚", layout="wide")
STORE_INTERFACE_VERSION = 3


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


def optional_number(value):
    if value is None or (isinstance(value, str) and not value.strip()) or (not isinstance(value, str) and pd.isna(value)):
        return ""
    try:
        return float(value)
    except (TypeError, ValueError):
        return ""
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0


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
    payload = {column: clean_text(value) for column, value in record.items() if column != "Amount"}
    payload["Amount"] = optional_number(record.get("Amount"))
    return {
        "report_scope": "RTGS", "batch_id": batch_id, "rtgs_data": payload,
        "trip_date": record_date(record.get("Pymt_Date")), "vehicle_number": "",
        "beneficiary_name": clean_text(record.get("Beneficiary Name")),
        "amount": clean_number(record.get("Amount")), "payment_mode": clean_text(record.get("Pymt_Mode")),
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

new_tab, requests_tab = st.tabs(["New Entry", "Requests"])

with new_tab:
    st.subheader("Start an intake session")
    mode = st.segmented_control("Request mode", ["DTR", "RTGS"], default="DTR", selection_mode="single")
    operator_default = "Shyam" if mode == "DTR" else "Nikhat"
    c1, c2 = st.columns([1, 3])
    operator = c1.text_input("Operator", value=operator_default, key=f"operator_{mode}")
    uploads = c2.file_uploader(
        "WhatsApp images, diesel slips or PDFs", type=["jpg", "jpeg", "png", "webp", "pdf"],
        accept_multiple_files=True, key=f"uploads_{mode}",
    )
    prompt = st.text_area(
        "Tell Oneshot what these files contain",
        placeholder=("Paste the WhatsApp message here. Example: 28-07-2026, MH 14JL 2654, "
                     "Talegaon (SG) to Sangali (10 MT), Rs 1,000. Explain which image belongs to it."
                     if mode == "DTR" else
                     "Paste the payment message here and explain which bank image belongs to which payment. "
                     "Mention whether multiple trips should be one combined transfer."),
        height=110, key=f"prompt_{mode}",
    )
    st.caption("The uploaded files and your instructions are sent to the configured Google Gemini model for extraction. Review every draft before saving.")
    if uploads:
        st.caption("Attached: " + ", ".join(file.name for file in uploads))
        st.caption("Keep files in WhatsApp order. Oneshot treats each evidence photo and the trip text immediately following it as one pair.")
    if st.button("Generate live review", type="primary", disabled=not uploads and not prompt.strip()):
        files = [{"filename": item.name, "mime_type": item.type or "application/octet-stream", "data": item.getvalue()} for item in uploads]
        too_large = [item["filename"] for item in files if len(item["data"]) > 8 * 1024 * 1024]
        if too_large:
            st.error("Each file must be 8 MB or smaller: " + ", ".join(too_large))
        else:
            try:
                with st.spinner(f"Reading the {mode} evidence and building draft rows…"):
                    result, model_used = extract_intake(
                        secret("GEMINI_API_KEY"), mode, prompt, files, model=secret("GEMINI_MODEL")
                    )
                original_records = result_to_records(mode, result)
                st.session_state["ai_draft"] = pd.DataFrame(original_records)
                st.session_state["ai_original_records"] = original_records
                st.session_state["ai_draft_mode"] = mode
                st.session_state["ai_draft_summary"] = result.summary
                st.session_state["ai_draft_files"] = files
                st.session_state["ai_draft_prompt"] = prompt
                st.session_state["ai_draft_operator"] = operator
                st.session_state["ai_model_used"] = model_used
            except Exception as exc:
                st.error(f"Could not generate the draft: {exc}")

    if st.session_state.get("ai_draft_mode") == mode:
        st.divider()
        st.subheader("Live review table")
        st.caption("AI output is a draft. Correct it here, add or remove rows, and leave uncertain values blank.")
        if st.session_state.get("ai_draft_summary"):
            with st.chat_message("assistant"):
                st.write(st.session_state["ai_draft_summary"])
        draft = st.session_state["ai_draft"]
        if draft.empty:
            st.warning("No distinct records were found. Add more context or clearer images and generate again.")
        else:
            edited = st.data_editor(draft, num_rows="dynamic", hide_index=True, width="stretch", key=f"draft_editor_{mode}")
            if st.button(f"Save {len(edited)} reviewed {mode} row(s)", type="primary"):
                active_columns = [column for column in edited.columns if column not in ("Sr No.", "Review Notes")]
                records = [record for record in edited.to_dict("records") if any(clean_text(record.get(c)) for c in active_columns)]
                if not records:
                    st.error("There are no non-empty rows to save.")
                else:
                    batch_id = store.create_batch(
                        mode, st.session_state["ai_draft_operator"], st.session_state["ai_draft_prompt"],
                        st.session_state["ai_draft_files"], st.session_state["ai_original_records"],
                        st.session_state.get("ai_draft_summary", ""), st.session_state.get("ai_model_used", ""),
                    )
                    values = [request_values(mode, record, batch_id, st.session_state["ai_draft_operator"]) for record in records]
                    numbers = store.create_many(values)
                    st.success(f"Saved {len(numbers)} draft request(s): {numbers[0]}" + (f" to {numbers[-1]}" if len(numbers) > 1 else ""))
                    for key in ["ai_draft", "ai_original_records", "ai_draft_mode", "ai_draft_summary", "ai_draft_files", "ai_draft_prompt", "ai_draft_operator", "ai_model_used"]:
                        st.session_state.pop(key, None)

with requests_tab:
    st.subheader("Saved requests")
    c1, c2, c3, c4 = st.columns(4)
    start = c1.date_input("From", dt.date.today().replace(day=1), key="request_start")
    end = c2.date_input("To", dt.date.today(), key="request_end")
    request_mode = c3.selectbox("Mode", ["All", "DTR", "RTGS"])
    request_status = c4.selectbox("Status", ["All", "Draft", "Submitted", "Verified", "Paid", "Cancelled"])
    rows = store.list(start, end, request_status, report_kind=None if request_mode == "All" else request_mode)
    st.metric("Requests found", len(rows))
    if not rows:
        st.info("No saved requests match these filters.")
    else:
        overview = pd.DataFrame(rows)
        columns = ["request_number", "report_scope", "trip_date", "vehicle_number", "beneficiary_name", "amount", "status", "created_by", "batch_id"]
        st.dataframe(overview[columns], hide_index=True, width="stretch")
        selected_number = st.selectbox("Open request", [row["request_number"] for row in rows])
        selected = store.get(selected_number)
        st.caption(f"{selected['report_scope']} · {selected_number} · entered by {selected.get('created_by') or '—'}")
        payload = dtr_payload(selected) if selected["report_scope"] == "DTR" else {
            column: json.loads(selected.get("rtgs_data") or "{}").get(column, "") for column in RTGS_COLUMNS
        }
        payload["Review Notes"] = selected.get("notes", "")
        edit_frame = pd.DataFrame([payload])
        edited_request = st.data_editor(edit_frame, hide_index=True, width="stretch", key=f"request_editor_{selected_number}")
        c1, c2 = st.columns([1, 3])
        statuses = ["Draft", "Submitted", "Verified", "Paid", "Cancelled"]
        selected_status = selected["status"] if selected["status"] in statuses else "Draft"
        edit_status = c1.selectbox("Workflow status", statuses, index=statuses.index(selected_status), key=f"status_{selected_number}")
        if c2.button("Save request changes", type="primary"):
            record = edited_request.iloc[0].to_dict()
            values = request_values(selected["report_scope"], record, selected.get("batch_id"), selected.get("created_by", ""))
            values["status"] = edit_status
            store.update(selected_number, values)
            st.success(f"Updated {selected_number}.")
            st.rerun()
        attachments = store.get_attachments(selected.get("batch_id"))
        if not attachments and selected.get("source_image"):
            attachments = [{
                "id": f"legacy_{selected['id']}", "filename": selected.get("source_filename") or "source-file",
                "mime_type": selected.get("source_mime_type") or "application/octet-stream",
                "payload": selected["source_image"],
            }]
        if attachments:
            with st.expander(f"Source files ({len(attachments)})"):
                for attachment in attachments:
                    if attachment["mime_type"].startswith("image/"):
                        st.image(attachment["payload"], caption=attachment["filename"], width=500)
                    st.download_button(
                        f"Download {attachment['filename']}", attachment["payload"], attachment["filename"],
                        attachment["mime_type"], key=f"download_{attachment['id']}",
                    )
