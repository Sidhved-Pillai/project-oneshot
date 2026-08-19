import datetime as dt
import hashlib
import json
import os

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from streamlit_mic_recorder import mic_recorder

from src.ai_intake import DTR_REVIEW_COLUMNS, extract_intake
from src.business_memory import build_business_memory, recall
from src.config import ROOT
from src.entry_finance import advance_summary
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
        audio_bytes = audio.get("bytes") if isinstance(audio, dict) else audio.getvalue()
        audio_type = "audio/wav" if isinstance(audio, dict) else audio.type or "audio/wav"
        files.append({"filename": "voice-instruction.wav", "mime_type": audio_type, "data": audio_bytes})
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
                state_key = f"{prefix}_{state_field}"
                current = st.session_state.get(state_key)
                blank = current in (None, "", 0, 0.0) or (field == "date" and current == dt.date.today())
                if blank:
                    st.session_state[state_key] = as_date(value) if field == "date" else value
        st.success("Form populated from the evidence. Please review every field before saving.")
    except Exception as exc:
        st.error(f"Could not auto-fill the form: {exc}")


def file_values(files):
    source = next((f for f in files if f["mime_type"].startswith("image/") or f["mime_type"] == "application/pdf"), None)
    return {"source_filename": source["filename"] if source else "", "source_mime_type": source["mime_type"] if source else "", "source_image": source["data"] if source else None}


def trip_payload(v, files):
    payments = {name: number(v[field]) for name, field in PAYMENT_FIELDS.items()}
    summary = advance_summary(v["transporter_freight"], *payments.values())
    total, balance = float(summary["total_advance"]), float(summary["balance_payable"])
    dtr = {
        "Branch": v["branch"], "Compnay Name": v["company_name"], "Date": v["date"], "Vehicle No.": v["vehicle_number"],
        "Vehicle Type": v["vehicle_capacity"], "Own/Outside Veh.": v["ownership_type"], "From": v["from_location"],
        "To": v["to_location"], "LR No.": v["lr_invoice_number"], "Invoice No.": v["lr_invoice_number"],
        "Revenue": v["revenue"], "Transporter Freight": v["transporter_freight"], "RTGS ADVANCE": v["rtgs_advance"],
        "Cash Adv.": v["cash_advance"], "UPI": v["upi"], "Diesel Adv.": v["diesel_advance"], "Total Adv.": total,
        "Balance Amt.": balance, "Benificiary Name": v["beneficiary_name"],
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
        "balance_amount": balance, "status": "Verified", "notes": v["remarks"],
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
        "status": "Verified", "dtr_data": {"categories": categories, "payments": payments}, **file_values(files),
    }


def page_intro(kicker, title, description, icon):
    st.markdown(
        f"""<div class="page-intro"><div class="page-icon">{icon}</div><div>
        <div class="eyebrow">{kicker}</div><h2>{title}</h2><p>{description}</p>
        </div></div>""", unsafe_allow_html=True,
    )


def workflow_steps(items, active=0):
    steps = "".join(
        f'<div class="flow-step {"active" if index == active else ""}"><span>{index + 1}</span>{item}</div>'
        for index, item in enumerate(items)
    )
    st.markdown(f'<div class="flow-strip">{steps}</div>', unsafe_allow_html=True)


def apply_memory(prefix, fields):
    """Suggestions only fill blanks; they never replace evidence or user values."""
    for field, value in fields.items():
        key = f"{prefix}_{field}"
        if st.session_state.get(key) in (None, "", 0, 0.0):
            st.session_state[key] = value[0]


def memory_prompt(prefix, title, source, suggestion, field_names):
    usable = {field: suggestion[field] for field in field_names if field in suggestion}
    missing = {field: value for field, value in usable.items() if st.session_state.get(f"{prefix}_{field}") in (None, "", 0, 0.0)}
    if not missing:
        return
    labels = {
        "vehicle_capacity": "Capacity", "transporter_name": "Transporter", "ownership_type": "Ownership",
        "vehicle_placed_by": "Placed by", "branch": "Branch", "beneficiary_account_number": "Account",
        "beneficiary_ifsc_code": "IFSC",
    }
    details = "".join(f'<span><b>{labels.get(field, field.title())}</b> {value[0]} · {value[1]} saved</span>' for field, value in missing.items())
    st.markdown(f'<div class="memory-card"><div><small>BUSINESS MEMORY</small><strong>{title}</strong><p>{details}</p></div></div>', unsafe_allow_html=True)
    st.button("Apply suggestion", key=f"memory_{prefix}_{source}", on_click=apply_memory, args=(prefix, missing), icon="✨")


def trip_form(prefix, memory):
    st.markdown("#### 1. Basic information")
    c1, c2 = st.columns(2)
    v = {"date": c1.date_input("Date *", value=st.session_state.get(f"{prefix}_date", dt.date.today()), key=f"{prefix}_date"), "branch": c2.text_input("Branch *", key=f"{prefix}_branch", placeholder="e.g., Pune"), "company_name": st.text_input("Company name *", key=f"{prefix}_company_name", placeholder="e.g., SG Logistics")}
    c1, c2 = st.columns(2)
    v["from_location"] = c1.text_input("From *", key=f"{prefix}_from_location", placeholder="e.g., Talegaon, Pune")
    v["to_location"] = c2.text_input("To *", key=f"{prefix}_to_location", placeholder="e.g., Bhiwandi, Thane")
    v["lr_invoice_number"] = st.text_input("LR / Invoice number", key=f"{prefix}_lr_invoice_number", placeholder="e.g., LR-12234")
    st.markdown("#### 2. Vehicle information")
    c1, c2, c3 = st.columns(3)
    v["vehicle_number"] = c1.text_input("Vehicle number *", key=f"{prefix}_vehicle_number", placeholder="e.g., MH14JL9818")
    v["vehicle_capacity"] = c2.text_input("Vehicle capacity", key=f"{prefix}_vehicle_capacity", placeholder="e.g., 20MT")
    choices = ["", "Own", "Outside"]
    current = st.session_state.get(f"{prefix}_ownership_type", "")
    v["ownership_type"] = c3.selectbox("Own or outside", choices, index=choices.index(current) if current in choices else 0, key=f"{prefix}_ownership_type")
    v["vehicle_placed_by"] = st.text_input("Vehicle placed by", key=f"{prefix}_vehicle_placed_by", placeholder="e.g., Ajit Thakur")
    memory_prompt(prefix, f"Known setup for {v['vehicle_number']}", f"vehicle_{v['vehicle_number']}", recall(memory, "vehicles", v["vehicle_number"]), ["vehicle_capacity", "transporter_name", "ownership_type", "vehicle_placed_by"])
    st.markdown("#### 3. Beneficiary details")
    c1, c2 = st.columns(2)
    v["beneficiary_name"] = c1.text_input("Beneficiary name", key=f"{prefix}_beneficiary_name", placeholder="e.g., XYZ Transport")
    v["transporter_name"] = c2.text_input("Transporter name", key=f"{prefix}_transporter_name", placeholder="e.g., XYZ Transport")
    c1, c2 = st.columns(2)
    v["beneficiary_account_number"] = c1.text_input("Account number", key=f"{prefix}_beneficiary_account_number", placeholder="e.g., 0206101019660")
    v["beneficiary_ifsc_code"] = c2.text_input("IFSC code", key=f"{prefix}_beneficiary_ifsc_code", placeholder="e.g., ICIC0001234")
    memory_prompt(prefix, f"Known branch for {v['company_name']}", f"company_{v['company_name']}", recall(memory, "companies", v["company_name"]), ["branch"])
    beneficiary_memory = recall(memory, "beneficiaries", v["beneficiary_name"])
    beneficiary_memory = {"beneficiary_account_number" if key == "account_number" else "beneficiary_ifsc_code" if key == "ifsc" else key: value for key, value in beneficiary_memory.items()}
    memory_prompt(prefix, f"Known beneficiary details for {v['beneficiary_name']}", f"beneficiary_{v['beneficiary_name']}", beneficiary_memory, ["beneficiary_account_number", "beneficiary_ifsc_code", "transporter_name"])
    st.markdown("#### 4. Payment details")
    c1, c2 = st.columns(2)
    v["revenue"] = c1.number_input("Revenue freight (₹)", min_value=0.0, value=None, placeholder="e.g., 50,000", key=f"{prefix}_revenue")
    v["transporter_freight"] = c2.number_input("Transporter freight (₹)", min_value=0.0, value=None, placeholder="e.g., 38,000", key=f"{prefix}_transporter_freight")
    st.caption("Enter amounts in every payment mode used. More than one mode is supported.")
    for col, (label, field) in zip(st.columns(4), PAYMENT_FIELDS.items()):
        v[field] = col.number_input(f"{label} (₹)", min_value=0.0, value=None, placeholder="e.g., 2,000", format="%.2f", key=f"{prefix}_{field}")
    payment = advance_summary(v["transporter_freight"], *(v[f] for f in PAYMENT_FIELDS.values()))
    total, balance = float(payment["total_advance"]), float(payment["balance_payable"])
    summary = st.columns(3)
    summary[0].metric("Transporter freight", f"₹{number(v['transporter_freight']):,.2f}")
    summary[1].metric("Total advance", f"₹{total:,.2f}")
    summary[2].metric("Balance payable", f"₹{balance:,.2f}", help="Transporter freight minus RTGS, Cash, UPI and Diesel advances. A negative amount indicates an overpayment.")
    if balance < 0:
        st.warning(f"Advance exceeds transporter freight by ₹{abs(balance):,.2f}. Please review the payment amounts.")
    v["remarks"] = st.text_area("Remarks", key=f"{prefix}_remarks", placeholder="e.g., Advance paid for Talegaon to Bhiwandi trip")
    return v


try:
    store = get_store(secret("DATABASE_URL"), STORE_INTERFACE_VERSION)
except Exception as exc:
    st.error(f"Database connection failed: {exc}")
    st.stop()

business_memory = build_business_memory(store.list(status="All active"))

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@600;700;800&display=swap');
:root{color-scheme:light;--ink:#1d1d1f;--muted:#6e6e73;--teal:#0071e3;--teal2:#2997ff;--navy:#061b33;--line:#dfe5ec;--paper:#fff;--voice:#20a464}
@keyframes rise{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:translateY(0)}}
@keyframes breathe{0%,100%{box-shadow:0 0 0 0 rgba(18,165,148,.24)}50%{box-shadow:0 0 0 7px rgba(18,165,148,0)}}
@keyframes sheen{from{transform:translateX(-130%)}to{transform:translateX(180%)}}
@media(prefers-reduced-motion:reduce){*,*:before,*:after{animation:none!important;transition:none!important}}
html,body,[class*="css"]{font-family:'DM Sans',sans-serif}.stApp,[data-testid="stAppViewContainer"]{color:var(--ink);background:radial-gradient(circle at 8% 0%,rgba(41,151,255,.13),transparent 25rem),radial-gradient(circle at 94% 10%,rgba(100,80,255,.08),transparent 28rem),#f5f5f7}
[data-testid="stHeader"]{background:rgba(245,245,247,.78);backdrop-filter:blur(16px)}.block-container{max-width:1200px;padding:5.25rem 2rem 5rem}
.stTabs [data-baseweb="tab-list"]{width:max-content;max-width:100%;gap:2px;background:#e8e8ed;padding:6px;border:0;border-radius:999px;box-shadow:none;overflow-x:auto}.stTabs [data-baseweb="tab"]{height:48px;border-radius:999px;padding:10px 27px;color:#3a3a3c;font:500 .96rem 'DM Sans',sans-serif;white-space:nowrap;transition:all .2s ease}.stTabs [data-baseweb="tab"]:hover{color:#000;background:rgba(255,255,255,.62)}.stTabs [aria-selected="true"]{color:#fff!important;background:#1d1d1f!important;box-shadow:0 2px 8px rgba(0,0,0,.14)}.stTabs [data-baseweb="tab-highlight"]{display:none}.stTabs [data-baseweb="tab-panel"]{animation:rise .36s ease-out}
.page-intro{display:flex;gap:14px;align-items:center;margin:26px 0 18px}.page-icon{display:grid;place-items:center;width:48px;height:48px;border-radius:15px;background:linear-gradient(145deg,#e1f7f2,#f5fffd);border:1px solid #cbe9e3;font-size:1.35rem;box-shadow:0 8px 22px rgba(8,127,115,.09)}.eyebrow{color:var(--teal);font-size:.7rem;font-weight:800;letter-spacing:.12em;text-transform:uppercase}.page-intro h2{font:800 1.45rem 'Manrope';letter-spacing:-.025em;margin:2px 0}.page-intro p{margin:0;color:var(--muted);font-size:.9rem}.flow-strip{display:flex;gap:8px;margin:0 0 18px}.flow-step{display:flex;align-items:center;gap:7px;padding:8px 12px;border:1px solid var(--line);border-radius:999px;background:rgba(255,255,255,.75);color:#7b898d;font-size:.76rem;font-weight:700}.flow-step span{display:grid;place-items:center;width:20px;height:20px;border-radius:50%;background:#eaf1ef;color:#647572;font-size:.68rem}.flow-step.active{border-color:#b8e2da;background:#e8f7f4;color:#087468}.flow-step.active span{color:#fff;background:var(--teal)}.memory-card{margin:9px 0 5px;padding:12px 14px;border:1px solid #cae6df;border-radius:13px;background:linear-gradient(135deg,#f3fbf9,#f8f9ff);box-shadow:0 6px 18px rgba(8,127,115,.06)}.memory-card small{display:block;color:#087f73;font-size:.62rem;font-weight:800;letter-spacing:.1em}.memory-card strong{display:block;margin:2px 0;color:#24444a;font-size:.83rem}.memory-card p{display:flex;flex-wrap:wrap;gap:6px;margin:5px 0 0}.memory-card span{padding:4px 7px;border-radius:7px;background:#fff;border:1px solid #e1ece9;color:#60716f;font-size:.72rem}.memory-card span b{color:#1d514b;margin-right:3px}
div[data-testid="stVerticalBlockBorderWrapper"]{background:rgba(255,255,255,.92);border:1px solid rgba(215,228,224,.95)!important;border-radius:20px;box-shadow:0 12px 36px rgba(34,63,68,.075);transition:transform .2s ease,box-shadow .2s ease}div[data-testid="stVerticalBlockBorderWrapper"]:hover{box-shadow:0 16px 42px rgba(34,63,68,.1)}h4{font:800 1rem 'Manrope'!important;color:#214047!important;padding:10px 0 7px!important;border-bottom:1px solid #edf2f1}
[data-testid="stFileUploader"]{padding:13px;border-radius:17px;background:rgba(255,255,255,.78);border:1px solid var(--line)}[data-testid="stFileUploaderDropzone"]{border:1.5px dashed #8bbdec;background:linear-gradient(145deg,#f7fbff,#edf6ff);border-radius:13px;transition:all .2s ease}[data-testid="stFileUploaderDropzone"]:hover{border-color:var(--teal);transform:translateY(-1px);box-shadow:0 8px 20px rgba(0,113,227,.1)}.voice-label{margin:0 0 8px;color:#1d1d1f;font-size:.9rem;font-weight:500}.voice-label+div iframe{border-radius:17px!important}
[data-baseweb="input"]>div,[data-baseweb="select"]>div,textarea{border-color:#dce3eb!important;border-radius:12px!important;background:#fff!important;transition:border .18s ease,box-shadow .18s ease!important}[data-baseweb="input"]>div:focus-within,[data-baseweb="select"]>div:focus-within,textarea:focus{border-color:#0071e3!important;box-shadow:0 0 0 3px rgba(0,113,227,.1)!important}.stButton>button,.stDownloadButton>button{border-radius:999px;font-weight:700;min-height:42px;padding-left:20px;padding-right:20px;transition:transform .18s ease,box-shadow .18s ease}.stButton>button[kind="primary"],.stDownloadButton>button[kind="primary"]{position:relative;overflow:hidden;border:0;color:#fff;background:#0071e3;box-shadow:0 7px 18px rgba(0,113,227,.22)}.stButton>button:hover,.stDownloadButton>button:hover{transform:translateY(-1px);box-shadow:0 10px 24px rgba(0,113,227,.28)}div[data-testid="stNumberInput"] button{display:none!important}div[data-testid="stNumberInput"] [data-baseweb="input"]{min-height:56px}div[data-testid="stNumberInput"] input{padding:10px 14px 20px!important;line-height:20px!important}
div[data-testid="stMetric"]{background:linear-gradient(145deg,#f8fbff,#eef6ff);border:1px solid #d6e7f7;border-radius:16px;padding:13px 16px;box-shadow:0 5px 16px rgba(0,80,160,.05)}[data-testid="stMetricLabel"]{color:#6e7781;font-weight:700}[data-testid="stMetricValue"]{font:800 1.28rem 'Manrope';color:#0066cc}[data-testid="stDataFrame"]{border:1px solid var(--line);border-radius:15px;overflow:hidden;box-shadow:0 8px 24px rgba(34,63,68,.06)}[data-testid="stAlert"]{border-radius:14px}details{border:1px solid var(--line)!important;border-radius:13px!important;background:rgba(255,255,255,.78)!important}
@media(max-width:700px){.block-container{padding:4.5rem .85rem 4rem}.app-hero{padding:17px}.status-pill{display:none}.stTabs [data-baseweb="tab"]{padding:8px 10px;font-size:.75rem}.flow-strip{overflow-x:auto}.flow-step{white-space:nowrap}.page-intro p{font-size:.82rem}}
</style>
""", unsafe_allow_html=True)
new_tab, expense_tab, records_tab, reports_tab = st.tabs(["New Entry", "Direct Expenses", "Records", "Generate Reports"])

with new_tab:
    page_intro("Smart capture", "New trip entry", "Add evidence once, review the details, and keep every report in sync.", "✦")
    workflow_steps(["Add evidence", "Review details", "Save record"], 0)
    c1, c2 = st.columns(2)
    upload = c1.file_uploader("Upload photo or PDF", type=["jpg", "jpeg", "png", "webp", "pdf"], key="trip_upload")
    with c2:
        st.markdown('<div class="voice-label">Voice instruction · English / हिन्दी / मराठी</div>', unsafe_allow_html=True)
        audio = mic_recorder(start_prompt="🎙️ Autofill with Voice Prompt", stop_prompt="✓ Stop and autofill", just_once=False, use_container_width=True, key="trip_audio")
    instruction = st.text_input("Optional typed instruction", placeholder="e.g., Invoice number is 12234", key="trip_instruction")
    files = evidence(upload, audio)
    if upload:
        autofill(evidence(upload, None), instruction, "trip")
    if audio:
        autofill(evidence(None, audio), instruction, "trip")
    with st.container(border=True):
        values = trip_form("trip", business_memory)
        if st.button("Save record", type="primary", disabled=not values["branch"] or not values["vehicle_number"], key="save_trip"):
            saved = store.create({**trip_payload(values, files), "created_by": "Operations user"})
            st.success(f"Saved {request_label(saved, values['date'])}. Entries remain filled for the next record.")

with expense_tab:
    page_intro("Expense capture", "Direct expense", "Turn bills and spoken notes into clean, categorised expense records.", "₹")
    workflow_steps(["Add receipt", "Categorise", "Save expense"], 0)
    c1, c2 = st.columns(2)
    expense_upload = c1.file_uploader("Attach bill or receipt", type=["jpg", "jpeg", "png", "webp", "pdf"], key="expense_upload")
    with c2:
        st.markdown('<div class="voice-label">Voice instruction · English / हिन्दी / मराठी</div>', unsafe_allow_html=True)
        expense_audio = mic_recorder(start_prompt="🎙️ Autofill with Voice Prompt", stop_prompt="✓ Stop and autofill", just_once=False, use_container_width=True, key="expense_audio")
    expense_instruction = st.text_input("Optional expense instruction", key="expense_instruction", placeholder="e.g., Driver salary ₹12,000 paid by RTGS")
    expense_files = evidence(expense_upload, expense_audio)
    if expense_upload:
        autofill(evidence(expense_upload, None), expense_instruction, "expense", "EXPENSE")
    if expense_audio:
        autofill(evidence(None, expense_audio), expense_instruction, "expense", "EXPENSE")
    with st.container(border=True):
        c1, c2, c3 = st.columns(3)
        v = {"date": c1.date_input("Date *", key="expense_date"), "beneficiary_name": c2.text_input("Beneficiary name", key="expense_beneficiary", placeholder="e.g., Rajesh Kumar"), "vehicle_number": c3.text_input("Vehicle name / number", key="expense_vehicle", placeholder="e.g., MH14JL9818")}
        st.markdown("#### Expense breakdown")
        cols = st.columns(3)
        for i, category in enumerate(DIRECT_EXPENSE_COLUMNS):
            v[category] = cols[i % 3].number_input(f"{category} (₹)", min_value=0.0, value=None, placeholder="e.g., 5,000", format="%.2f", key=f"expense_category_{i}")
        v["remarks"] = st.text_area("Remarks", key="expense_remarks", placeholder="e.g., August office rent")
        st.markdown("#### Mode of payment")
        st.caption("Fill every mode used for this expense.")
        for col, (label, field) in zip(st.columns(4), PAYMENT_FIELDS.items()):
            v[field] = col.number_input(f"{label} (₹)", min_value=0.0, value=None, placeholder="e.g., 5,000", format="%.2f", key=f"expense_{field}")
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
    page_intro("Single source of truth", "Records", "Find, review, edit, and manage every saved operations record.", "▤")
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
                payment = advance_summary(item["Transporter Freight"], *(item[name] for name in ("RTGS", "Cash", "UPI", "Diesel")))
                total, balance = float(payment["total_advance"]), float(payment["balance_payable"])
                updated_dtr = {**raw, "Branch": item["Branch"], "Compnay Name": item["Company"], "Date": as_date(item["Date"]), "Vehicle No.": item["Vehicle"], "Vehicle Type": item["Vehicle Capacity"], "Own/Outside Veh.": item["Own / Outside"], "From": item["From"], "To": item["To"], "LR No.": item["LR / Invoice"], "Invoice No.": item["LR / Invoice"], "Revenue": item["Revenue"], "Transporter Freight": item["Transporter Freight"], "RTGS ADVANCE": item["RTGS"], "Cash Adv.": item["Cash"], "UPI": item["UPI"], "Diesel Adv.": item["Diesel"], "Total Adv.": total, "Balance Amt.": balance, "Benificiary Name": item["Beneficiary"], "Veh Placed by": item["Vehicle Placed By"], "Remark": item["Remarks"]}
                updated_rtgs = {**rtgs_raw, "BNF_NAME": item["Beneficiary"], "BENE_ACC_NO": item["Account Number"], "BENE_IFSC": item["IFSC"], "AMOUNT": item["RTGS"], "REMARK": item["Remarks"], "Origin Area": item["Branch"]}
                update_values.update({"amount": total, "total_advance": total, "balance_amount": balance, "dtr_data": updated_dtr, "rtgs_data": updated_rtgs})
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
    page_intro("Report studio", "Generate reports", "Choose a period and create a ready-to-use DTR, RTGS, or P&L workbook.", "↗")
    workflow_steps(["Choose dates", "Select format", "Download"], 0)
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
