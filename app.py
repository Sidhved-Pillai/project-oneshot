import datetime as dt
import hashlib
import hmac
import json
import os

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

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
STORE_INTERFACE_VERSION = 7
PAYMENT_FIELDS = {"UPI": "upi", "Diesel": "diesel_advance", "Cash": "cash_advance", "RTGS": "rtgs_advance"}
BRANCHES = ["Wada", "Baroda", "Pune"]
SPECIAL_CODE_SALT = bytes.fromhex("28d7f0e0dfb9b32fecf4f4656d309042")
SPECIAL_CODE_HASH = bytes.fromhex("b17d745a7cfdb8fad453e479e3950b905f0505478fe8268461ae74fdbc2248fb")
MEMBER_CODE_HASHES = {
    "Ajit": "a25be184e5abecae4f87eef475fbecf9b2b51c9dc3e11a9022a0196798b1e88f",
    "Nikhat": "f4931443e89ce4e103cdcee1a82c297b3bbf26bdbc31fccf36b8de2b193e8845",
    "Nitish": "ea565453a2706b0e72df78364c854e9aaaf62848ef6b292efe341dea3b207177",
    "Gopal": "8422d601483b1cda8d20f11b17b482c756fb005912c2ac6f83baca98d6554e5c",
    "Shyam": "37d9997a10e64c52c8dfa34f66ffb078531f04cd9af2f6f455d45a3125068dba",
    "Nikhil": "40ed3b8fb38df58e9bef001c1bab0d0c9b08a4b13a84a9e7a9b4d549bb2c5e90",
    "Vinod": "17c4bc70c02f37310d326cff94f608c18de6e14c6df949eb51fbd37d0e7b52cb",
    "Manish": "a021c3c411a4a3cb971eeb978f3df49f172c31d58a270a7d8c7a4218a2eb24f9",
}
SPECIAL_MEMBERS = {"Sid", "Ajit", "Vinod", "Nikhil", "Shyam", "Nikhat"}
PNL_MEMBERS = {"Sid", "Ajit", "Vinod", "Nikhil"}
AUDITED_MEMBERS = {"Ajit", "Nikhat", "Shyam"}
LIMITED_RECORD_BRANCH = {"Nitish": "Pune", "Gopal": "Pune", "Manish": "Wada"}
ASCII_BOLD = str.maketrans(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789",
    "𝗔𝗕𝗖𝗗𝗘𝗙𝗚𝗛𝗜𝗝𝗞𝗟𝗠𝗡𝗢𝗣𝗤𝗥𝗦𝗧𝗨𝗩𝗪𝗫𝗬𝗭𝗮𝗯𝗰𝗱𝗲𝗳𝗴𝗵𝗶𝗷𝗸𝗹𝗺𝗻𝗼𝗽𝗾𝗿𝘀𝘁𝘂𝘃𝘄𝘅𝘆𝘇𝟬𝟭𝟮𝟯𝟰𝟱𝟲𝟳𝟴𝟵",
)


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


def is_own_vehicle(ownership_type):
    return clean_text(ownership_type).casefold().startswith("own")


def ownership_matches(ownership_type, selected):
    if selected in (None, "", "Both"):
        return True
    return is_own_vehicle(ownership_type) if selected == "Own" else clean_text(ownership_type).casefold().startswith("outside")


def applicable_transporter_freight(ownership_type, amount):
    return 0.0 if is_own_vehicle(ownership_type) else number(amount)


def verify_special_access_code(value):
    entered = clean_text(value)
    configured = clean_text(secret("SPECIAL_ACCESS_CODE"))
    if configured:
        return hmac.compare_digest(entered, configured)
    candidate = hashlib.pbkdf2_hmac("sha256", entered.encode(), SPECIAL_CODE_SALT, 600_000)
    return hmac.compare_digest(candidate, SPECIAL_CODE_HASH)


def identify_member(value):
    if verify_special_access_code(value):
        return "Sid"
    candidate = hashlib.pbkdf2_hmac("sha256", clean_text(value).encode(), SPECIAL_CODE_SALT, 600_000)
    for member, digest in MEMBER_CODE_HASHES.items():
        if hmac.compare_digest(candidate, bytes.fromhex(digest)):
            return member
    return None


def require_authentication():
    if st.session_state.get("authenticated"):
        return
    st.markdown("""
    <style>
    [data-testid="stAppViewContainer"]{background:radial-gradient(circle at 50% 18%,rgba(41,151,255,.16),transparent 28rem),#f5f5f7}
    [data-testid="stHeader"]{background:transparent}.block-container{max-width:520px;padding-top:15vh}
    .login-heading{text-align:center;margin-bottom:24px}.login-heading h1{margin:0;color:#1d1d1f;font:800 2rem -apple-system,BlinkMacSystemFont,'SF Pro Display',sans-serif;letter-spacing:-.045em}.login-heading p{margin:8px 0 0;color:#6e6e73;font-size:.95rem}
    [data-testid="stForm"]{padding:24px;border:1px solid rgba(255,255,255,.9);border-radius:24px;background:rgba(255,255,255,.72);box-shadow:0 18px 50px rgba(31,52,78,.12);backdrop-filter:blur(24px);-webkit-backdrop-filter:blur(24px)}
    [data-testid="InputInstructions"]{display:none!important}
    [data-testid="stFormSubmitButton"] button{width:100%;min-height:44px;border:0;border-radius:999px;color:#fff;background:#0071e3;font-weight:700}
    </style>
    <div class="login-heading"><h1>Project Oneshot</h1><p>Enter the member access code to continue.</p></div>
    """, unsafe_allow_html=True)
    with st.form("special_member_login"):
        access_code = st.text_input("6-digit access code", type="password", max_chars=6, key="special_access_code")
        submitted = st.form_submit_button("Continue", use_container_width=True)
    if submitted:
        member = identify_member(access_code) if len(access_code) == 6 and access_code.isdigit() else None
        if member:
            st.session_state["authenticated"] = True
            st.session_state["authenticated_user"] = member
            st.session_state["is_special_member"] = member in SPECIAL_MEMBERS
            st.session_state["welcome_pending"] = True
            st.session_state.pop("special_access_code", None)
            st.rerun()
        st.error("Incorrect access code. Please try again.")
    st.stop()


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


def record_select_label(row):
    dtr = unpack(row.get("dtr_data"))
    placed_by = clean_text(dtr.get("Veh Placed by")) or "Not specified"
    billtee = number(dtr.get("Billtee"))
    billtee_text = f"{billtee:,.0f}" if billtee.is_integer() else f"{billtee:,.2f}"
    details = f"{placed_by}, Billtee Amt: {billtee_text}".translate(ASCII_BOLD)
    return f"{request_label(row)} [{details}]"


def trip_leaderboard(rows):
    totals = {}
    for row in rows:
        if row.get("report_scope") == "Expense":
            continue
        dtr = unpack(row.get("dtr_data"))
        name = clean_text(dtr.get("Veh Placed by")) or "Not specified"
        trip_count, revenue = totals.get(name, (0, 0.0))
        totals[name] = (trip_count + 1, revenue + number(row.get("revenue")))
    return sorted(
        ((name, trip_count, revenue) for name, (trip_count, revenue) in totals.items()),
        key=lambda item: (-item[2], -item[1], item[0].casefold()),
    )


def trip_auto_remark(vehicle_number, origin, destination, vehicle_capacity, trip_date):
    digits = "".join(character for character in clean_text(vehicle_number) if character.isdigit())[-4:]
    origin, destination = clean_text(origin), clean_text(destination)
    route = f"{origin} to {destination}" if origin and destination else origin or destination
    parts = [digits, route, clean_text(vehicle_capacity), f"{as_date(trip_date):%d %m %Y}", "TA"]
    return " ".join(part for part in parts if part).strip()


def expense_auto_remark(vehicle_number, beneficiary_name, categories, expense_date):
    digits = "".join(character for character in clean_text(vehicle_number) if character.isdigit())[-4:]
    category_text = ", ".join(categories)
    parts = [digits, clean_text(beneficiary_name), category_text, f"{as_date(expense_date):%d %m %Y}", "DE"]
    return " ".join(part for part in parts if part).strip()


def sync_auto_remark(widget_key, generated):
    tracker_key = f"{widget_key}_generated"
    current = clean_text(st.session_state.get(widget_key))
    previous = clean_text(st.session_state.get(tracker_key))
    if generated and (not current or current == previous):
        st.session_state[widget_key] = generated
    st.session_state[tracker_key] = generated


def rtgs_remark(row):
    existing = unpack(row.get("rtgs_data")).get("REMARK") or row.get("notes")
    if clean_text(existing):
        return clean_text(existing)
    return trip_auto_remark(
        row.get("vehicle_number"), row.get("from_location"), row.get("to_location"),
        row.get("vehicle_type"), row.get("trip_date"),
    )


def evidence(upload, audio):
    files = []
    uploads = upload if isinstance(upload, list) else ([upload] if upload else [])
    for item in uploads:
        files.append({"filename": item.name, "mime_type": item.type or "application/octet-stream", "data": item.getvalue()})
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
                state_key = f"{prefix}_{state_field}"
                current = st.session_state.get(state_key)
                blank = current in (None, "", 0, 0.0) or (field == "date" and current == dt.date.today())
                if blank:
                    st.session_state[state_key] = as_date(value) if field == "date" else value
        st.success("Form populated from the evidence. Please review every field before saving.")
    except Exception as exc:
        st.error(f"Could not auto-fill the form: {exc}")


def file_values(files, preferred_filename=None):
    evidence_files = [f for f in files if f["mime_type"].startswith("image/") or f["mime_type"] == "application/pdf"]
    source = next((f for f in evidence_files if f["filename"] == preferred_filename), None)
    source = source or (evidence_files[-1] if evidence_files else None)
    return {"source_filename": source["filename"] if source else "", "source_mime_type": source["mime_type"] if source else "", "source_image": source["data"] if source else None}


def trip_payload(v, files, invoice_filename=None):
    payments = {name: number(v[field]) for name, field in PAYMENT_FIELDS.items()}
    billtee = number(v["billtee"])
    repairs_maintenance = number(v.get("repairs_maintenance"))
    toll_expense = number(v.get("toll_expense"))
    transporter_freight = float(applicable_transporter_freight(v["ownership_type"], v["transporter_freight"]))
    if v.get("simplified"):
        total = sum(payments.values()) + toll_expense + repairs_maintenance
        balance = number(v["revenue"]) - total
    else:
        summary = advance_summary(transporter_freight, *payments.values(), billtee)
        total, balance = float(summary["total_advance"]), float(summary["balance_payable"])
    dtr = {
        "Branch": v["branch"], "Compnay Name": v["company_name"], "Date": v["date"], "Vehicle No.": v["vehicle_number"],
        "Vehicle Type": v["vehicle_capacity"], "Own/Outside Veh.": v["ownership_type"], "From": v["from_location"],
        "To": v["to_location"], "LR No.": v["lr_number"], "Invoice No.": v["invoice_number"],
        "Revenue": v["revenue"], "Transporter Freight": transporter_freight, "RTGS ADVANCE": v["rtgs_advance"],
        "Cash Adv.": v["cash_advance"], "UPI": v["upi"], "Diesel Adv.": v["diesel_advance"], "Billtee": billtee, "Total Adv.": total,
        "Balance Amt.": balance, "Toll Expense": toll_expense, "Repairs & Maintenance": repairs_maintenance,
        "Repair Reason": clean_text(v.get("repair_reason")), "Benificiary Name": v["beneficiary_name"],
        "Diesel Pump Name": v["diesel_pump_name"], "Card Name": v["card_name"],
        "Transporter Name": v["transporter_name"], "Veh Placed by": v["vehicle_placed_by"], "Remark": v["remarks"],
    }
    rtgs = {"BNF_NAME": v["beneficiary_name"], "BENE_ACC_NO": v["beneficiary_account_number"], "BENE_IFSC": v["beneficiary_ifsc_code"], "AMOUNT": v["rtgs_advance"], "REMARK": v["remarks"], "Origin Area": v["branch"]}
    return {
        "report_scope": "Both", "trip_date": v["date"], "vehicle_number": v["vehicle_number"], "vehicle_type": v["vehicle_capacity"],
        "ownership_type": v["ownership_type"], "from_location": v["from_location"], "to_location": v["to_location"],
        "company_name": v["company_name"], "branch": v["branch"], "invoice_number": v["invoice_number"],
        "beneficiary_name": v["beneficiary_name"], "transporter_name": v["transporter_name"], "amount": total,
        "payment_mode": ", ".join(name for name, amount in payments.items() if amount), "revenue": v["revenue"],
        "transporter_freight": transporter_freight, "rtgs_advance": v["rtgs_advance"], "cash_advance": v["cash_advance"],
        "upi": v["upi"], "diesel_advance": v["diesel_advance"], "total_advance": total,
        "balance_amount": balance, "status": "Verified", "notes": v["remarks"],
        "dtr_data": dtr, "rtgs_data": rtgs, **file_values(files, invoice_filename),
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
        "status": "Verified", "dtr_data": {
            "categories": categories, "payments": payments,
            "Diesel Pump Name": v["diesel_pump_name"], "Card Name": v["card_name"],
        }, **file_values(files),
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


def trip_form(prefix, memory, allowed_branches=None, simplified=False):
    v = {"simplified": simplified}
    st.markdown("#### 1. Basic information")
    c1, c2 = st.columns(2)
    branch_key = f"{prefix}_branch"
    available_branches = allowed_branches or BRANCHES
    branch_lookup = {branch.casefold(): branch for branch in available_branches}
    current_branch = branch_lookup.get(clean_text(st.session_state.get(branch_key)).casefold(), "")
    if st.session_state.get(branch_key) != current_branch:
        st.session_state[branch_key] = current_branch
    branch_choices = ["", *available_branches]
    v.update({"date": c1.date_input("Date *", value=st.session_state.get(f"{prefix}_date", dt.date.today()), format="DD/MM/YYYY", key=f"{prefix}_date"), "branch": c2.selectbox("Branch *", branch_choices, index=branch_choices.index(current_branch), key=branch_key, placeholder="Select a branch"), "company_name": st.text_input("Company name *", key=f"{prefix}_company_name", placeholder="e.g., SG Logistics")})
    c1, c2 = st.columns(2)
    v["from_location"] = c1.text_input("From *", key=f"{prefix}_from_location", placeholder="e.g., Talegaon, Pune")
    v["to_location"] = c2.text_input("To *", key=f"{prefix}_to_location", placeholder="e.g., Bhiwandi, Thane")
    c1, c2 = st.columns(2)
    v["lr_number"] = c1.text_input("LR number", key=f"{prefix}_lr_number", placeholder="e.g., LR-12234")
    v["invoice_number"] = c2.text_input("Invoice number", key=f"{prefix}_invoice_number", placeholder="e.g., INV-10595976")
    st.markdown("#### 2. Vehicle information")
    c1, c2, c3 = st.columns(3)
    v["vehicle_number"] = c1.text_input("Vehicle number *", key=f"{prefix}_vehicle_number", placeholder="e.g., MH14JL9818")
    v["vehicle_capacity"] = c2.text_input("Vehicle capacity", key=f"{prefix}_vehicle_capacity", placeholder="e.g., 20MT")
    choices = ["", "Own", "Outside"]
    current = st.session_state.get(f"{prefix}_ownership_type", "")
    v["ownership_type"] = c3.selectbox("Own or outside", choices, index=choices.index(current) if current in choices else 0, key=f"{prefix}_ownership_type")
    v["vehicle_placed_by"] = st.text_input("Vehicle placed by", key=f"{prefix}_vehicle_placed_by", placeholder="e.g., Ajit Thakur")
    memory_prompt(prefix, f"Known setup for {v['vehicle_number']}", f"vehicle_{v['vehicle_number']}", recall(memory, "vehicles", v["vehicle_number"]), ["vehicle_capacity", "transporter_name", "ownership_type", "vehicle_placed_by"])
    memory_prompt(prefix, f"Known branch for {v['company_name']}", f"company_{v['company_name']}", recall(memory, "companies", v["company_name"]), ["branch"])
    if simplified:
        v.update({"beneficiary_name": "", "transporter_name": "", "beneficiary_account_number": "", "beneficiary_ifsc_code": ""})
    else:
        st.markdown("#### 3. Beneficiary details")
        c1, c2 = st.columns(2)
        v["beneficiary_name"] = c1.text_input("Beneficiary name", key=f"{prefix}_beneficiary_name", placeholder="e.g., XYZ Transport")
        v["transporter_name"] = c2.text_input("Transporter name", key=f"{prefix}_transporter_name", placeholder="e.g., XYZ Transport")
        c1, c2 = st.columns(2)
        v["beneficiary_account_number"] = c1.text_input("Account number", key=f"{prefix}_beneficiary_account_number", placeholder="e.g., 0206101019660")
        v["beneficiary_ifsc_code"] = c2.text_input("IFSC code", key=f"{prefix}_beneficiary_ifsc_code", placeholder="e.g., ICIC0001234")
        beneficiary_memory = recall(memory, "beneficiaries", v["beneficiary_name"])
        beneficiary_memory = {"beneficiary_account_number" if key == "account_number" else "beneficiary_ifsc_code" if key == "ifsc" else key: value for key, value in beneficiary_memory.items()}
        memory_prompt(prefix, f"Known beneficiary details for {v['beneficiary_name']}", f"beneficiary_{v['beneficiary_name']}", beneficiary_memory, ["beneficiary_account_number", "beneficiary_ifsc_code", "transporter_name"])
    st.markdown(f"#### {'3' if simplified else '4'}. Payment details")
    if simplified:
        v["revenue"] = st.number_input("Revenue freight (₹)", min_value=0.0, value=None, placeholder="e.g., 50,000", key=f"{prefix}_revenue")
        v["transporter_freight"] = 0.0
    else:
        c1, c2 = st.columns(2)
        v["revenue"] = c1.number_input("Revenue freight (₹)", min_value=0.0, value=None, placeholder="e.g., 50,000", key=f"{prefix}_revenue")
        own_vehicle = is_own_vehicle(v["ownership_type"])
        transporter_freight_key = f"{prefix}_transporter_freight"
        if own_vehicle:
            st.session_state[transporter_freight_key] = None
        v["transporter_freight"] = c2.number_input("Transporter freight (₹)", min_value=0.0, value=None, placeholder="Not applicable for own vehicles" if own_vehicle else "e.g., 38,000", disabled=own_vehicle, key=transporter_freight_key)
        if own_vehicle:
            c2.caption("Not applicable for an own vehicle.")
    st.caption("Enter amounts in every payment mode used. Repairs and maintenance are deducted from Profit / Loss." if simplified else "Enter amounts in every payment mode used. Billtee is also deducted before calculating the balance payable.")
    if simplified:
        deduction_columns = st.columns(6)
        simplified_fields = [
            ("UPI", "upi"), ("Diesel", "diesel_advance"), ("Cash", "cash_advance"),
            ("Toll Expense", "toll_expense"), ("RTGS", "rtgs_advance"),
        ]
        for col, (label, field) in zip(deduction_columns, simplified_fields):
            v[field] = col.number_input(f"{label} (₹)", min_value=0.0, value=None, placeholder="e.g., 2,000", key=f"{prefix}_{field}")
        v["billtee"] = 0.0
        v["repairs_maintenance"] = deduction_columns[-1].number_input("Repairs & Maintenance (₹)", min_value=0.0, value=None, placeholder="e.g., 1,000", key=f"{prefix}_repairs_maintenance")
        v["repair_reason"] = st.text_input("Reason", key=f"{prefix}_repair_reason", placeholder="e.g., Tyre puncture repair") if number(v["repairs_maintenance"]) > 0 else ""
        if number(v["repairs_maintenance"]) > 0 and not clean_text(v["repair_reason"]):
            st.caption("Reason is required when Repairs & Maintenance has an amount.")
    else:
        deduction_columns = st.columns(5)
        for col, (label, field) in zip(deduction_columns, PAYMENT_FIELDS.items()):
            v[field] = col.number_input(f"{label} (₹)", min_value=0.0, value=None, placeholder="e.g., 2,000", key=f"{prefix}_{field}")
        v["billtee"] = deduction_columns[-1].number_input("Billtee (₹)", min_value=0.0, value=None, placeholder="e.g., 1,000", key=f"{prefix}_billtee")
        v["toll_expense"], v["repairs_maintenance"], v["repair_reason"] = 0.0, 0.0, ""
    if number(v["diesel_advance"]) > 0:
        pump_col, card_col = st.columns(2)
        v["diesel_pump_name"] = pump_col.text_input("Add Pumps", key=f"{prefix}_diesel_pump_name", placeholder="e.g., HP Petrol Pump")
        v["card_name"] = card_col.text_input("Card Name", key=f"{prefix}_card_name", placeholder="e.g., HPCL DriveTrack")
    else:
        v["diesel_pump_name"], v["card_name"] = "", ""
    if simplified:
        total = sum(number(v[field]) for field in PAYMENT_FIELDS.values()) + number(v["toll_expense"]) + number(v["repairs_maintenance"])
        balance = number(v["revenue"]) - total
    else:
        payment = advance_summary(v["transporter_freight"], *(v[f] for f in PAYMENT_FIELDS.values()), v["billtee"])
        total, balance = float(payment["total_advance"]), float(payment["balance_payable"])
    summary = st.columns(2 if simplified else 3)
    metric_offset = 0
    if not simplified:
        summary[0].metric("Transporter freight", f"₹{number(v['transporter_freight']):,.2f}")
        metric_offset = 1
    summary[metric_offset].metric("Total expense" if simplified else "Total advance", f"₹{total:,.2f}")
    if simplified:
        loss_class = " negative" if balance < 0 else ""
        summary[metric_offset + 1].markdown(f'<div class="profit-loss-card{loss_class}"><span>Profit / Loss</span><strong>₹{balance:,.2f}</strong></div>', unsafe_allow_html=True)
    else:
        summary[metric_offset + 1].metric("Balance payable", f"₹{balance:,.2f}", help="Transporter freight minus RTGS, Cash, UPI, Diesel and Billtee deductions. A negative amount indicates an overpayment.")
    if balance < 0 and not simplified:
        st.warning(f"Advance exceeds transporter freight by ₹{abs(balance):,.2f}. Please review the payment amounts.")
    remark_key = f"{prefix}_remarks"
    generated_remark = trip_auto_remark(v["vehicle_number"], v["from_location"], v["to_location"], v["vehicle_capacity"], v["date"])
    if any(clean_text(v[field]) for field in ("vehicle_number", "from_location", "to_location", "vehicle_capacity")):
        sync_auto_remark(remark_key, generated_remark)
    v["remarks"] = st.text_area("Remarks", key=remark_key, placeholder="Auto-filled from the trip details")
    return v


require_authentication()
if st.session_state.pop("welcome_pending", False):
    st.toast(f"Welcome {st.session_state['authenticated_user']}!", icon="👋")

try:
    store = get_store(secret("DATABASE_URL"), STORE_INTERFACE_VERSION)
except Exception as exc:
    st.error(f"Database connection failed: {exc}")
    st.stop()

business_memory = build_business_memory(store.list(status="All active"))
current_user = st.session_state.get("authenticated_user", "Unknown member")
is_special_member = current_user in SPECIAL_MEMBERS
can_use_direct_expenses = is_special_member or current_user == "Manish"
can_generate_reports = is_special_member
can_generate_pnl = current_user in PNL_MEMBERS
record_branch_scope = LIMITED_RECORD_BRANCH.get(current_user)
allowed_entry_branches = [record_branch_scope] if record_branch_scope else BRANCHES
if st.session_state.pop("reset_trip_form", False):
    for state_key in list(st.session_state):
        if state_key.startswith("trip_"):
            del st.session_state[state_key]
if saved_entry_notice := st.session_state.pop("saved_entry_notice", None):
    st.toast(saved_entry_notice, icon="✅")


def audit_action(action, request_number="", details=""):
    if current_user in AUDITED_MEMBERS:
        store.log_action(current_user, action, request_number, details)


@st.dialog("View evidence and edit record", width="large")
def view_record(row):
    raw, is_expense = unpack(row.get("dtr_data")), row.get("report_scope") == "Expense"
    is_manish_record = clean_text(row.get("created_by")) == "Manish" and not is_expense
    rtgs_raw = unpack(row.get("rtgs_data"))
    display = {
        "Date": row.get("trip_date"), "Type": "Direct expense" if is_expense else "Trip",
        "Branch": row.get("branch", ""), "Company": row.get("company_name", ""),
        "Vehicle": row.get("vehicle_number", ""), "Vehicle Capacity": row.get("vehicle_type", ""),
        "Own / Outside": row.get("ownership_type", ""), "From": row.get("from_location", ""),
        "To": row.get("to_location", ""), "LR No.": raw.get("LR No.", ""),
        "Invoice No.": raw.get("Invoice No.") or row.get("invoice_number", ""),
        "Beneficiary": row.get("beneficiary_name", ""), "Account Number": rtgs_raw.get("BENE_ACC_NO", ""),
        "IFSC": rtgs_raw.get("BENE_IFSC", ""), "Vehicle Placed By": raw.get("Veh Placed by", ""),
        "Revenue": number(row.get("revenue")), "Transporter Freight": number(row.get("transporter_freight")),
        "RTGS": number(row.get("rtgs_advance")), "Cash": number(row.get("cash_advance")),
        "UPI": number(row.get("upi")), "Diesel": number(row.get("diesel_advance")),
        "Add Pumps": raw.get("Diesel Pump Name", ""), "Card Name": raw.get("Card Name", ""),
        "Billtee": number(raw.get("Billtee")), "Remarks": row.get("notes", ""),
    }
    if is_expense:
        display.update(raw.get("categories", {}))
    if is_manish_record:
        display.pop("Billtee", None)
        display.update({
            "Toll Expense": number(raw.get("Toll Expense")),
            "Repairs & Maintenance": number(raw.get("Repairs & Maintenance")),
            "Reason": raw.get("Repair Reason", ""), "Profit / Loss": number(row.get("balance_amount")),
        })
    locked_columns = ["Type", "Branch"] if record_branch_scope else ["Type"]
    if is_manish_record:
        locked_columns.append("Profit / Loss")
    edited = st.data_editor(
        pd.DataFrame([display]), hide_index=True, width="stretch", disabled=locked_columns,
        key=f"record_editor_{row['request_number']}",
    )
    if row.get("source_image"):
        st.markdown("#### Invoice evidence")
        if clean_text(row.get("source_mime_type")).startswith("image/"):
            st.image(row["source_image"], caption=row.get("source_filename", "Invoice evidence"), width=500)
        else:
            st.download_button(
                "Open invoice evidence", row["source_image"], row.get("source_filename", "invoice.pdf"),
                row.get("source_mime_type"),
            )
    edited_item = edited.iloc[0].to_dict()
    repair_reason_missing = is_manish_record and number(edited_item.get("Repairs & Maintenance")) > 0 and not clean_text(edited_item.get("Reason"))
    if repair_reason_missing:
        st.caption("Reason is required before repair and maintenance changes can be saved.")
    if st.button("Save record changes", type="primary", key=f"save_record_{row['request_number']}", disabled=repair_reason_missing):
        item = edited_item
        ownership_type = clean_text(item["Own / Outside"])
        transporter_freight = float(applicable_transporter_freight(ownership_type, item["Transporter Freight"]))
        billtee = number(item.get("Billtee"))
        repairs_maintenance = number(item.get("Repairs & Maintenance"))
        toll_expense = number(item.get("Toll Expense"))
        update_values = {
            "trip_date": as_date(item["Date"]), "branch": clean_text(item["Branch"]),
            "company_name": clean_text(item["Company"]), "vehicle_number": clean_text(item["Vehicle"]),
            "vehicle_type": clean_text(item["Vehicle Capacity"]), "ownership_type": ownership_type,
            "from_location": clean_text(item["From"]), "to_location": clean_text(item["To"]),
            "invoice_number": clean_text(item["Invoice No."]), "beneficiary_name": clean_text(item["Beneficiary"]),
            "revenue": number(item["Revenue"]), "transporter_freight": transporter_freight,
            "rtgs_advance": number(item["RTGS"]), "cash_advance": number(item["Cash"]),
            "upi": number(item["UPI"]), "diesel_advance": number(item["Diesel"]),
            "notes": clean_text(item["Remarks"]),
        }
        if is_expense:
            categories = {name: number(item.get(name)) for name in DIRECT_EXPENSE_COLUMNS}
            update_values.update({
                "amount": sum(categories.values()),
                "dtr_data": {**raw, "categories": categories, "Diesel Pump Name": clean_text(item["Add Pumps"]), "Card Name": clean_text(item["Card Name"])},
            })
        else:
            if is_manish_record:
                total = sum(number(item[name]) for name in ("RTGS", "Cash", "UPI", "Diesel")) + toll_expense + repairs_maintenance
                balance = number(item["Revenue"]) - total
            else:
                payment = advance_summary(transporter_freight, *(item[name] for name in ("RTGS", "Cash", "UPI", "Diesel")), billtee)
                total, balance = float(payment["total_advance"]), float(payment["balance_payable"])
            updated_dtr = {
                **raw, "Branch": item["Branch"], "Compnay Name": item["Company"], "Date": as_date(item["Date"]),
                "Vehicle No.": item["Vehicle"], "Vehicle Type": item["Vehicle Capacity"],
                "Own/Outside Veh.": item["Own / Outside"], "From": item["From"], "To": item["To"],
                "LR No.": item["LR No."], "Invoice No.": item["Invoice No."], "Revenue": item["Revenue"],
                "Transporter Freight": transporter_freight, "RTGS ADVANCE": item["RTGS"], "Cash Adv.": item["Cash"],
                "UPI": item["UPI"], "Diesel Adv.": item["Diesel"], "Diesel Pump Name": clean_text(item["Add Pumps"]),
                "Card Name": clean_text(item["Card Name"]), "Billtee": billtee, "Total Adv.": total,
                "Balance Amt.": balance, "Toll Expense": toll_expense, "Repairs & Maintenance": repairs_maintenance,
                "Repair Reason": clean_text(item.get("Reason")), "Benificiary Name": item["Beneficiary"],
                "Veh Placed by": item["Vehicle Placed By"], "Remark": item["Remarks"],
            }
            updated_rtgs = {
                **rtgs_raw, "BNF_NAME": item["Beneficiary"], "BENE_ACC_NO": item["Account Number"],
                "BENE_IFSC": item["IFSC"], "AMOUNT": item["RTGS"], "REMARK": item["Remarks"],
                "Origin Area": item["Branch"],
            }
            update_values.update({
                "amount": total, "total_advance": total, "balance_amount": balance,
                "dtr_data": updated_dtr, "rtgs_data": updated_rtgs,
            })
        store.update(row["request_number"], update_values, "records_tab", current_user)
        audit_action("Updated record", row["request_number"], request_label(row))
        st.toast("Record updated. A revision snapshot was saved.", icon="✅")
        st.rerun()

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@600;700;800&display=swap');
:root{color-scheme:light;--ink:#1d1d1f;--muted:#6e6e73;--teal:#0071e3;--teal2:#2997ff;--navy:#061b33;--line:#dfe5ec;--paper:#fff;--voice:#20a464}
@keyframes rise{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:translateY(0)}}
@keyframes breathe{0%,100%{box-shadow:0 0 0 0 rgba(18,165,148,.24)}50%{box-shadow:0 0 0 7px rgba(18,165,148,0)}}
@keyframes sheen{from{transform:translateX(-130%)}to{transform:translateX(180%)}}
@media(prefers-reduced-motion:reduce){*,*:before,*:after{animation:none!important;transition:none!important}}
html,body,[class*="css"]{font-family:'DM Sans',sans-serif}.stApp,[data-testid="stAppViewContainer"]{color:var(--ink);background:radial-gradient(circle at 8% 0%,rgba(41,151,255,.13),transparent 25rem),radial-gradient(circle at 94% 10%,rgba(100,80,255,.08),transparent 28rem),#f5f5f7}
[data-testid="stHeader"]{background:rgba(245,245,247,.78);backdrop-filter:blur(16px)}.block-container{max-width:1200px;padding:5.25rem 2rem 5rem}.app-hero{position:relative;overflow:hidden;display:flex;align-items:center;justify-content:space-between;padding:22px 25px;margin-bottom:22px;color:#fff;background:linear-gradient(125deg,#061b33 0%,#064a91 52%,#0071e3 100%);border:1px solid rgba(255,255,255,.15);border-radius:24px;box-shadow:0 18px 50px rgba(0,75,155,.2);animation:rise .45s ease-out}.app-hero:after{content:"";position:absolute;inset:-70% auto -70% -30%;width:28%;background:linear-gradient(90deg,transparent,rgba(255,255,255,.12),transparent);transform:rotate(14deg);animation:sheen 7s ease-in-out infinite}.brand-row{display:flex;align-items:center;gap:14px}.brand-mark{display:grid;place-items:center;width:46px;height:46px;border-radius:14px;background:linear-gradient(145deg,#cbe8ff,#fff);color:#0062c7;font:800 1.25rem 'Manrope';box-shadow:inset 0 0 0 1px rgba(255,255,255,.5)}.brand{font:800 clamp(1.6rem,3vw,2.2rem) 'Manrope';letter-spacing:-.045em}.brand span{color:#7bc4ff}.subtitle{margin-top:3px;color:#d7eaff;font-size:.92rem}.status-pill{display:flex;align-items:center;gap:8px;padding:8px 12px;border:1px solid rgba(255,255,255,.2);border-radius:999px;background:rgba(255,255,255,.12);font-size:.78rem;font-weight:700;white-space:nowrap}.status-dot{width:8px;height:8px;border-radius:50%;background:#56efb5;animation:breathe 2.4s infinite}
.stTabs [data-baseweb="tab-list"]{position:relative;isolation:isolate;width:fit-content;max-width:100%;gap:5px;padding:7px;margin:0 0 3px;overflow-x:auto;border:1px solid rgba(255,255,255,.78);border-radius:999px;background:rgba(255,255,255,.3);box-shadow:inset 0 1px 0 rgba(255,255,255,.9),inset 0 -1px 0 rgba(80,80,90,.08),0 10px 30px rgba(40,45,55,.08);backdrop-filter:blur(24px) saturate(150%);-webkit-backdrop-filter:blur(24px) saturate(150%)}.stTabs [data-baseweb="tab-list"]:before{content:"";position:absolute;z-index:-1;inset:1px;border-radius:inherit;background:linear-gradient(115deg,rgba(255,255,255,.42),transparent 45%,rgba(255,255,255,.18));pointer-events:none}[data-testid="stTabs"] [data-testid="stTab"]{position:relative;height:45px;overflow:hidden;border:1px solid transparent;border-radius:999px;background-clip:padding-box;padding:9px 21px;color:#30343b;font-family:-apple-system,BlinkMacSystemFont,'SF Pro Display','DM Sans',sans-serif;font-size:.9rem;font-weight:600;letter-spacing:-.01em;white-space:nowrap;transition:color .22s ease,background .22s ease,box-shadow .22s ease,transform .22s ease}[data-testid="stTabs"] [data-testid="stTab"]:hover{color:#1d1d1f;background:#edf8fd;border-color:rgba(190,224,240,.82);border-radius:999px;box-shadow:inset 0 1px 0 rgba(255,255,255,.9),0 4px 12px rgba(77,145,175,.1);transform:translateY(-1px)}[data-testid="stTabs"] [data-testid="stTab"][aria-selected="true"]{color:#1d1d1f!important;border-color:rgba(255,255,255,.86)!important;background:rgba(255,255,255,.62)!important;box-shadow:inset 0 1px 0 rgba(255,255,255,.98),inset 0 -1px 0 rgba(70,70,80,.08),0 5px 14px rgba(35,40,50,.11)!important;text-shadow:none;transform:translateY(-1px)}[data-testid="stTabs"] [data-testid="stTab"][aria-selected="true"]:after{content:"";position:absolute;inset:2px 8px auto;height:40%;border-radius:999px;background:linear-gradient(180deg,rgba(255,255,255,.42),rgba(255,255,255,0));pointer-events:none}.stTabs [data-baseweb="tab-highlight"]{display:none}.stTabs [data-baseweb="tab-panel"]{animation:rise .36s ease-out}
[data-testid="stTabs"] [data-testid="stTab"]{overflow:hidden!important;border-radius:999px!important}[data-testid="stTabs"] [data-testid="stTab"]:hover{background:#edf8fd!important;border-color:rgba(190,224,240,.82)!important;border-radius:999px!important}[data-testid="stTabs"] [data-testid="stTab"][aria-selected="true"]>div:last-child{display:none!important}
[data-testid="stTabs"] [role="tablist"]{padding-bottom:8px!important}
.page-intro{display:flex;gap:14px;align-items:center;margin:26px 0 18px}.page-icon{display:grid;place-items:center;width:48px;height:48px;border-radius:15px;background:linear-gradient(145deg,#e1f7f2,#f5fffd);border:1px solid #cbe9e3;font-size:1.35rem;box-shadow:0 8px 22px rgba(8,127,115,.09)}.eyebrow{color:var(--teal);font-size:.7rem;font-weight:800;letter-spacing:.12em;text-transform:uppercase}.page-intro h2{font:800 1.45rem 'Manrope';letter-spacing:-.025em;margin:2px 0}.page-intro p{margin:0;color:var(--muted);font-size:.9rem}.flow-strip{display:flex;gap:8px;margin:0 0 18px}.flow-step{display:flex;align-items:center;gap:7px;padding:8px 12px;border:1px solid var(--line);border-radius:999px;background:rgba(255,255,255,.75);color:#7b898d;font-size:.76rem;font-weight:700}.flow-step span{display:grid;place-items:center;width:20px;height:20px;border-radius:50%;background:#eaf1ef;color:#647572;font-size:.68rem}.flow-step.active{border-color:#b8e2da;background:#e8f7f4;color:#087468}.flow-step.active span{color:#fff;background:var(--teal)}.memory-card{margin:9px 0 5px;padding:12px 14px;border:1px solid #cae6df;border-radius:13px;background:linear-gradient(135deg,#f3fbf9,#f8f9ff);box-shadow:0 6px 18px rgba(8,127,115,.06)}.memory-card small{display:block;color:#087f73;font-size:.62rem;font-weight:800;letter-spacing:.1em}.memory-card strong{display:block;margin:2px 0;color:#24444a;font-size:.83rem}.memory-card p{display:flex;flex-wrap:wrap;gap:6px;margin:5px 0 0}.memory-card span{padding:4px 7px;border-radius:7px;background:#fff;border:1px solid #e1ece9;color:#60716f;font-size:.72rem}.memory-card span b{color:#1d514b;margin-right:3px}
.billtee-board{width:100%;margin:6px 0 18px;border-collapse:separate;border-spacing:0;overflow:hidden;border:1px solid var(--line);border-radius:14px;background:rgba(255,255,255,.82)}.billtee-board th,.billtee-board td{padding:11px 15px;text-align:left;border-bottom:1px solid #edf1f5;font-weight:800}.billtee-board th{color:var(--muted);font-size:.75rem;text-transform:uppercase;letter-spacing:.05em}.billtee-board td:last-child,.billtee-board th:last-child{text-align:right}.billtee-board tr:last-child td{border-bottom:0}
div[data-testid="stVerticalBlockBorderWrapper"]{background:rgba(255,255,255,.92);border:1px solid rgba(215,228,224,.95)!important;border-radius:20px;box-shadow:0 12px 36px rgba(34,63,68,.075);transition:transform .2s ease,box-shadow .2s ease}div[data-testid="stVerticalBlockBorderWrapper"]:hover{box-shadow:0 16px 42px rgba(34,63,68,.1)}h4{font:800 1rem 'Manrope'!important;color:#214047!important;padding:10px 0 7px!important;border-bottom:1px solid #edf2f1}
[data-testid="stFileUploader"]{padding:13px;border-radius:17px;background:rgba(255,255,255,.78);border:1px solid var(--line)}[data-testid="stFileUploaderDropzone"]{border:1.5px dashed #8bbdec;background:linear-gradient(145deg,#f7fbff,#edf6ff);border-radius:13px;transition:all .2s ease}[data-testid="stFileUploaderDropzone"]:hover{border-color:var(--teal);transform:translateY(-1px);box-shadow:0 8px 20px rgba(0,113,227,.1)}[data-testid="stAudioInput"]{padding:13px;border:1px solid var(--line);border-radius:17px;background:rgba(255,255,255,.78)}[data-testid="stAudioInput"] button{color:#fff!important;background:#0071e3!important;border:2px solid #0071e3!important;border-radius:999px!important;box-shadow:0 3px 10px rgba(0,113,227,.25)!important}
[data-baseweb="input"]>div,[data-baseweb="select"]>div,textarea{border-color:#dce3eb!important;border-radius:12px!important;background:#fff!important;transition:border .18s ease,box-shadow .18s ease!important}[data-baseweb="input"]>div:focus-within,[data-baseweb="select"]>div:focus-within,textarea:focus{border-color:#0071e3!important;box-shadow:0 0 0 3px rgba(0,113,227,.1)!important}[data-testid="InputInstructions"]{display:none!important}[data-testid="stNumberInput"] button{display:none!important}.stButton>button,.stDownloadButton>button{border-radius:999px;font-weight:700;min-height:42px;padding-left:20px;padding-right:20px;transition:transform .18s ease,box-shadow .18s ease}.stButton>button[kind="primary"],.stDownloadButton>button[kind="primary"]{position:relative;overflow:hidden;border:0;color:#fff;background:#0071e3;box-shadow:0 7px 18px rgba(0,113,227,.22)}.stButton>button:hover,.stDownloadButton>button:hover{transform:translateY(-1px);box-shadow:0 10px 24px rgba(0,113,227,.28)}.st-key-trip_voice_autofill button,.st-key-expense_voice_autofill button{color:#fff!important;background:linear-gradient(135deg,#1f9d60,#27b974)!important;box-shadow:0 8px 20px rgba(31,157,96,.22)!important}.st-key-trip_voice_autofill button:disabled,.st-key-expense_voice_autofill button:disabled{color:#fff!important;background:#8fd5ae!important;opacity:.72!important}
div[data-testid="stMetric"]{background:linear-gradient(145deg,#f8fbff,#eef6ff);border:1px solid #d6e7f7;border-radius:16px;padding:13px 16px;box-shadow:0 5px 16px rgba(0,80,160,.05)}[data-testid="stMetricLabel"]{color:#6e7781;font-weight:700}[data-testid="stMetricValue"]{font:800 1.28rem 'Manrope';color:#0066cc}.profit-loss-card{min-height:91px;padding:13px 16px;border:1px solid #d6e7f7;border-radius:16px;background:linear-gradient(145deg,#f8fbff,#eef6ff);box-shadow:0 5px 16px rgba(0,80,160,.05)}.profit-loss-card span{display:block;color:#6e7781;font-weight:700}.profit-loss-card strong{display:block;margin-top:4px;color:#0066cc;font:800 1.28rem 'Manrope'}.profit-loss-card.negative strong{color:#d70015}[data-testid="stDataFrame"]{border:1px solid var(--line);border-radius:15px;overflow:hidden;box-shadow:0 8px 24px rgba(34,63,68,.06)}[data-testid="stAlert"]{border-radius:14px}details{border:1px solid var(--line)!important;border-radius:13px!important;background:rgba(255,255,255,.78)!important}
@media(max-width:700px){.block-container{padding:4.5rem .85rem 4rem}.app-hero{padding:17px}.status-pill{display:none}[data-testid="stTabs"] [data-testid="stTab"]{padding:8px 10px;font-size:.75rem}.flow-strip{overflow-x:auto}.flow-step{white-space:nowrap}.page-intro p{font-size:.82rem}}
</style>
<div class="app-hero"><div class="brand-row"><div class="brand-mark">1×</div><div><div class="brand">Project <span>Oneshot</span></div><div class="subtitle">One record. Every operations report.</div></div></div><div class="status-pill"><span class="status-dot"></span>WORKSPACE READY</div></div>
""", unsafe_allow_html=True)
hidden_tabs = []
if not can_use_direct_expenses:
    hidden_tabs.append(2)
if not can_generate_reports:
    hidden_tabs.append(4)
if not is_special_member:
    hidden_tabs.append(5)
if hidden_tabs:
    hidden_tab_css = "".join(
        f'[data-baseweb="tab-list"] [data-testid="stTab"]:nth-child({index}){{display:none!important}}'
        for index in hidden_tabs
    )
    st.markdown(f"<style>{hidden_tab_css}</style>", unsafe_allow_html=True)
new_tab, expense_tab, records_tab, reports_tab, logs_tab = st.tabs(["New Entry", "Direct Expenses", "Records", "Generate Reports", "Logs"])

with new_tab:
    page_intro("Smart capture", "New trip entry", "Add evidence once, review the details, and keep every report in sync.", "✦")
    workflow_steps(["Add evidence", "Review details", "Save and add another"], 0)
    c1, c2 = st.columns(2)
    upload = c1.file_uploader("Upload photos or PDFs", type=["jpg", "jpeg", "png", "webp", "pdf"], accept_multiple_files=True, key="trip_upload", help="Upload the cheque, invoice, and any supporting evidence together.")
    invoice_filename = None
    if upload:
        invoice_filename = c1.selectbox(
            "Invoice evidence shown in Records", [item.name for item in upload], index=len(upload) - 1,
            key="trip_invoice_evidence", help="All files are used for autofill; only this invoice file is displayed in Records.",
        )
    audio = c2.audio_input("Voice instruction · English / हिन्दी / मराठी", key="trip_audio")
    voice_autofill = c2.button("Autofill with Voice Prompt", type="primary", use_container_width=True, disabled=audio is None, key="trip_voice_autofill", icon="🎙️")
    files = evidence(upload, audio)
    if upload:
        autofill(evidence(upload, None), "", "trip")
    if voice_autofill:
        autofill(evidence(None, audio), "", "trip")
    with st.container(border=True):
        values = trip_form("trip", business_memory, allowed_entry_branches, simplified=current_user == "Manish")
        repair_reason_missing = current_user == "Manish" and number(values["repairs_maintenance"]) > 0 and not clean_text(values["repair_reason"])
        if st.button("Save and Another Entry", type="primary", disabled=not values["branch"] or not values["vehicle_number"] or repair_reason_missing, key="save_trip"):
            saved = store.create({**trip_payload(values, files, invoice_filename), "created_by": current_user})
            audit_action("Created trip record", saved, request_label(saved, values["date"]))
            st.session_state["saved_entry_notice"] = f"Saved {request_label(saved, values['date'])}. Ready for another entry."
            st.session_state["reset_trip_form"] = True
            st.rerun()

with expense_tab:
    if not can_use_direct_expenses:
        st.warning("Direct Expenses is not available for your account.")
    page_intro("Expense capture", "Direct expense", "Turn bills and spoken notes into clean, categorised expense records.", "₹")
    workflow_steps(["Add receipt", "Categorise", "Save expense"], 0)
    c1, c2 = st.columns(2)
    expense_upload = c1.file_uploader("Attach bills or receipts", type=["jpg", "jpeg", "png", "webp", "pdf"], accept_multiple_files=True, key="expense_upload", disabled=not can_use_direct_expenses)
    expense_audio = c2.audio_input("Voice instruction · English / हिन्दी / मराठी", key="expense_audio", disabled=not can_use_direct_expenses)
    expense_voice_autofill = c2.button("Autofill with Voice Prompt", type="primary", use_container_width=True, disabled=expense_audio is None or not can_use_direct_expenses, key="expense_voice_autofill", icon="🎙️")
    expense_files = evidence(expense_upload, expense_audio)
    if expense_upload:
        autofill(evidence(expense_upload, None), "", "expense", "EXPENSE")
    if expense_voice_autofill:
        autofill(evidence(None, expense_audio), "", "expense", "EXPENSE")
    with st.container(border=True):
        c1, c2, c3 = st.columns(3)
        v = {"date": c1.date_input("Date *", format="DD/MM/YYYY", key="expense_date"), "beneficiary_name": c2.text_input("Beneficiary name", key="expense_beneficiary", placeholder="e.g., Rajesh Kumar"), "vehicle_number": c3.text_input("Vehicle name / number", key="expense_vehicle", placeholder="e.g., MH14JL9818")}
        st.markdown("#### Expense breakdown")
        cols = st.columns(3)
        for i, category in enumerate(DIRECT_EXPENSE_COLUMNS):
            v[category] = cols[i % 3].number_input(f"{category} (₹)", min_value=0.0, value=None, placeholder="e.g., 5,000", key=f"expense_category_{i}")
        expense_categories = [category for category in DIRECT_EXPENSE_COLUMNS if number(v[category])]
        expense_generated_remark = expense_auto_remark(v["vehicle_number"], v["beneficiary_name"], expense_categories, v["date"])
        if clean_text(v["vehicle_number"]) or clean_text(v["beneficiary_name"]) or expense_categories:
            sync_auto_remark("expense_remarks", expense_generated_remark)
        v["remarks"] = st.text_area("Remarks", key="expense_remarks", placeholder="Auto-filled from the expense details")
        st.markdown("#### Mode of payment")
        st.caption("Fill every mode used for this expense.")
        for col, (label, field) in zip(st.columns(4), PAYMENT_FIELDS.items()):
            v[field] = col.number_input(f"{label} (₹)", min_value=0.0, value=None, placeholder="e.g., 5,000", key=f"expense_{field}")
        if number(v["diesel_advance"]) > 0:
            pump_col, card_col = st.columns(2)
            v["diesel_pump_name"] = pump_col.text_input("Add Pumps", key="expense_diesel_pump_name", placeholder="e.g., HP Petrol Pump")
            v["card_name"] = card_col.text_input("Card Name", key="expense_card_name", placeholder="e.g., HPCL DriveTrack")
        else:
            v["diesel_pump_name"], v["card_name"] = "", ""
        expense_total = sum(number(v[name]) for name in DIRECT_EXPENSE_COLUMNS)
        paid_total = sum(number(v[field]) for field in PAYMENT_FIELDS.values())
        c1, c2 = st.columns(2)
        c1.metric("Total direct expense", f"₹{expense_total:,.2f}")
        c2.metric("Payment modes total", f"₹{paid_total:,.2f}")
        if paid_total and abs(expense_total - paid_total) > 0.01:
            st.warning("Expense total and payment-mode total do not match. Review before saving.")
        if st.button("Save direct expense", type="primary", key="save_expense", disabled=not can_use_direct_expenses):
            saved = store.create({**expense_payload(v, expense_files), "created_by": current_user})
            audit_action("Created direct expense", saved, request_label(saved, v["date"]))
            st.success(f"Saved {request_label(saved, v['date'])}.")

with records_tab:
    page_intro("Single source of truth", "Records", "Find, review, edit, and manage every saved operations record.", "▤")
    rows = store.list(status="All active")
    if record_branch_scope:
        rows = [row for row in rows if clean_text(row.get("branch")).casefold() == record_branch_scope.casefold()]
        st.caption(f"Your account can access {record_branch_scope} records only.")
    if rows:
        record_dates = [as_date(row.get("trip_date")) for row in rows]
        placed_by_options = sorted({clean_text(unpack(row.get("dtr_data")).get("Veh Placed by")) for row in rows} - {""}, key=str.casefold)
        vehicle_options = sorted({clean_text(row.get("vehicle_number")) for row in rows} - {""}, key=str.casefold)
        st.markdown("#### Filter records")
        c1, c2, c3, c4, c5 = st.columns(5)
        filter_from = c1.date_input("Records from", value=min(record_dates), format="DD/MM/YYYY", key="records_filter_from")
        filter_to = c2.date_input("Records to", value=max(record_dates), format="DD/MM/YYYY", key="records_filter_to")
        placed_by_filter = c3.selectbox("Vehicle placed by", ["All", *placed_by_options], key="records_filter_placed_by")
        vehicle_filter = c4.selectbox("Vehicle no.", ["All", *vehicle_options], key="records_filter_vehicle")
        ownership_filter = c5.selectbox("Own or outside", ["Both", "Own", "Outside"], key="records_filter_ownership")
        date_filtered_rows = [row for row in rows if filter_from <= as_date(row.get("trip_date")) <= filter_to]
        rows = [
            row for row in date_filtered_rows
            if (placed_by_filter == "All" or clean_text(unpack(row.get("dtr_data")).get("Veh Placed by")) == placed_by_filter)
            and (vehicle_filter == "All" or clean_text(row.get("vehicle_number")) == vehicle_filter)
            and ownership_matches(row.get("ownership_type"), ownership_filter)
        ]
        leaderboard_rows = "".join(
            f"<tr><td>{rank}</td><td>{name}</td><td>{trip_count}</td><td>₹{revenue:,.2f}</td></tr>"
            for rank, (name, trip_count, revenue) in enumerate(trip_leaderboard(rows), 1)
        )
        st.markdown("#### Trip leaderboard")
        st.markdown(
            f'<table class="billtee-board"><thead><tr><th>Rank</th><th>Vehicle placed by</th><th>Trip count</th><th>Total revenue</th></tr></thead><tbody>{leaderboard_rows}</tbody></table>',
            unsafe_allow_html=True,
        )
    if not rows:
        st.info("No records match the selected filters.")
    else:
        labels = {record_select_label(row): row for row in rows}
        st.markdown("#### Live records")
        with st.container(height=420, border=True):
            header = st.columns([1.35, .8, .9, 1.1, 1.15, 1, .85])
            for column, title in zip(header, ("Record", "Date", "Branch", "Vehicle", "Placed by", "Revenue", "")):
                column.markdown(f"**{title}**")
            for record in rows:
                raw = unpack(record.get("dtr_data"))
                columns = st.columns([1.35, .8, .9, 1.1, 1.15, 1, .85], vertical_alignment="center")
                columns[0].write(request_label(record))
                columns[1].write(f"{as_date(record.get('trip_date')):%d/%m/%y}")
                columns[2].write(clean_text(record.get("branch")) or "—")
                columns[3].write(clean_text(record.get("vehicle_number")) or "—")
                columns[4].write(clean_text(raw.get("Veh Placed by")) or "—")
                columns[5].write(f"₹{number(record.get('revenue')):,.0f}")
                if columns[6].button("View Evidence", key=f"view_record_{record['request_number']}", use_container_width=True):
                    view_record(record)
        with st.expander("Delete records"):
            select_all = st.checkbox("Select all", key="records_delete_all")
            chosen = list(labels) if select_all else st.multiselect("Select records", list(labels), key="records_delete_selection")
            acknowledged = st.checkbox("I understand this permanently deletes the selected records.", key="records_delete_ack")
            if st.button("Delete selected records", disabled=not chosen or not acknowledged, key="records_delete"):
                for label in chosen:
                    request_number = labels[label]["request_number"]
                    if store.delete_request(request_number):
                        audit_action("Deleted record", request_number, label)
                st.success(f"Deleted {len(chosen)} record(s).")
                st.rerun()

with reports_tab:
    if not can_generate_reports:
        st.warning("Generate Reports is not available for your account.")
    page_intro("Report studio", "Generate reports", "Choose a period and create a ready-to-use DTR, RTGS, or P&L workbook.", "↗")
    workflow_steps(["Choose dates", "Select format", "Download"], 0)
    c1, c2 = st.columns(2)
    start = c1.date_input("Records from", value=dt.date.today() - dt.timedelta(days=30), format="DD/MM/YYYY", key="report_from")
    end = c2.date_input("Records to", value=dt.date.today(), format="DD/MM/YYYY", key="report_to")
    report_options = ["DTR", "RTGS", *(["P&L"] if can_generate_pnl else [])]
    report_type = st.segmented_control("Report type", report_options, default="DTR", key="report_type")
    pnl_ownership_filter = "Both"
    if report_type == "P&L":
        pnl_ownership_filter = st.segmented_control(
            "Own or outside vehicle", ["Both", "Own", "Outside"], default="Both", key="pnl_ownership_filter",
        )
    selected_rows = store.list(start, end, status="All active") if can_generate_reports and start <= end else []
    trips = [row for row in selected_rows if row.get("report_scope") != "Expense"]
    if report_type == "P&L":
        trips = [row for row in trips if ownership_matches(row.get("ownership_type"), pnl_ownership_filter)]
    expenses = [row for row in selected_rows if row.get("report_scope") == "Expense"]
    st.caption(f"{len(trips)} trip record(s) and {len(expenses)} direct expense record(s) selected.")
    if report_type == "DTR":
        records = []
        for i, row in enumerate(reversed(trips), 1):
            data = unpack(row.get("dtr_data"))
            records.append({column: data.get(column, "") for column in DTR_REVIEW_COLUMNS} | {"Sr No.": i})
        frame = pd.DataFrame(records, columns=DTR_REVIEW_COLUMNS)
        st.dataframe(frame, hide_index=True, width="stretch")
        st.download_button("Download DTR report", export_operational_dtr(frame), f"DTR-{start}-{end}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", type="primary", disabled=frame.empty or not can_generate_reports, on_click=audit_action, args=("Downloaded DTR report", "", f"{start:%d/%m/%Y} to {end:%d/%m/%Y}"))
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
        st.download_button("Download bank-format RTGS report", export_rtgs(frame, dt.date.today()), f"RTGS-{start}-{end}.xls", "application/vnd.ms-excel", type="primary", disabled=frame.empty or not can_generate_reports, on_click=audit_action, args=("Downloaded RTGS report", "", f"{start:%d/%m/%Y} to {end:%d/%m/%Y}"))
    else:
        expense_data = [{**row, "categories": unpack(row.get("dtr_data")).get("categories", {})} for row in expenses]
        frame = pd.DataFrame(pnl_summary(trips, expense_data))
        st.dataframe(frame, hide_index=True, width="stretch")
        st.download_button("Download P&L report", export_pnl(trips, expense_data, start, end), f"PNL-{start}-{end}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", type="primary", disabled=not can_generate_pnl, on_click=audit_action, args=("Downloaded P&L report", "", f"{start:%d/%m/%Y} to {end:%d/%m/%Y}"))

with logs_tab:
    page_intro("Restricted audit", "Logs", "Review record changes and report activity across the workspace.", "⌁")
    if not is_special_member:
        st.warning("Logs are available only to special members.")
    else:
        log_rows = store.list_activity_logs()
        if not log_rows:
            st.info("No activity has been recorded yet.")
        else:
            log_frame = pd.DataFrame([
                {
                    "Date & time": row.get("created_at"),
                    "Member": row.get("user_name", ""),
                    "Action": row.get("action", ""),
                    "Record": row.get("request_number", ""),
                    "Details": row.get("details", ""),
                }
                for row in log_rows
            ])
            st.dataframe(log_frame, hide_index=True, width="stretch")
