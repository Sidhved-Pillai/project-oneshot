import datetime as dt
import hashlib
import hmac
import json
import os
import re
from difflib import SequenceMatcher

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from src.access_control import PRIVATE_RECORD_USERS, SELF_DELETE_USERS, can_delete_record, can_view_record
from src.ai_intake import extract_intake, merge_same_trip_intake_rows, should_autofill_field
from src.business_memory import build_business_memory, recall
from src.config import ROOT
from src.entry_finance import advance_summary, diesel_expense
from src.entry_state import clear_entry_state, clear_expense_state, entry_state_prefix, expense_state_prefix
from src.invoice_numbers import combined_invoice_number, normalized_invoice_numbers, reconcile_sequential_invoice_series, user_invoice_duplicates, verified_bisleri_invoice_numbers
from src.expense_periods import PERIOD_EXPENSE_CATEGORIES, allocate_expenses_for_period, expense_periods, normalize_period, serialize_period
from src.pending_invoice_matcher import suggest_invoice_match
from src.current_leaderboard import branch_trip_leaderboard
from src.record_filters import DIRECT_EXPENSES, RECORD_TYPES, TRIP_RECORDS, filter_record_type, filter_without_invoice_evidence, sort_records_by_date
from src.records_export import export_records_excel
from src.trip_dtr_report import DTR_REVIEW_COLUMNS, export_operational_dtr
from src.rtgs_report import RTGS_REVIEW_COLUMNS, export_rtgs, normalize_rtgs_records
from src.text_normalization import canonical_company, canonical_location, canonical_vehicle_capacity, plain_remark
from src.transporter_profiles import VIJAY_FREIGHT_RATES, VIJAY_TRANSPORTER_PROFILES, resolve_vijay_vehicle_number, vijay_transporter_for_vehicle, vijay_transporter_freight, vijay_transporter_profile
from src.vijay_locations import canonical_vijay_location
from src.vehicle_normalization import canonical_vehicle_number
from src.current_pnl_report import DIRECT_EXPENSE_COLUMNS, branch_pnl_summary, branch_vehicle_pnl_summary, vehicle_number_pnl_summary, export_pnl
from src.records_store_v10 import RequestStore

load_dotenv(ROOT / ".env")
st.set_page_config(page_title="Project Oneshot", page_icon="🚚", layout="wide")
STORE_INTERFACE_VERSION = 10
PAYMENT_FIELDS = {"UPI": "upi", "Diesel": "diesel_advance", "Cash": "cash_advance", "RTGS": "rtgs_advance"}
STANDARD_DIRECT_EXPENSE_COLUMNS = list(DIRECT_EXPENSE_COLUMNS)
MANISH_DIRECT_EXPENSE_COLUMNS = [
    "Driver's salary", "Office & General expenses", "EMI", "Conveyance",
    "Insurance", "Vehicle Tax", "Repair and maintenance", "Passing expense", "Extra Expense", "RTO Challan & Fine",
]
ALL_DIRECT_EXPENSE_COLUMNS = [*DIRECT_EXPENSE_COLUMNS, "Passing expense"]
BRANCHES = ["Wada", "Pune", "Andheri"]
SPECIAL_CODE_SALT = bytes.fromhex("28d7f0e0dfb9b32fecf4f4656d309042")
SPECIAL_CODE_HASH = bytes.fromhex("b17d745a7cfdb8fad453e479e3950b905f0505478fe8268461ae74fdbc2248fb")
MEMBER_CODE_HASHES = {
    "Ajit": "a25be184e5abecae4f87eef475fbecf9b2b51c9dc3e11a9022a0196798b1e88f",
    "Nikhat": "e94e52a5680d444dafa229a26b9f7abb3f8672074febc3926c8449b11884d0f3",
    "Nitish": "ea565453a2706b0e72df78364c854e9aaaf62848ef6b292efe341dea3b207177",
    "Gopal": "8422d601483b1cda8d20f11b17b482c756fb005912c2ac6f83baca98d6554e5c",
    "Shyam": "37d9997a10e64c52c8dfa34f66ffb078531f04cd9af2f6f455d45a3125068dba",
    "Nikhil": "40ed3b8fb38df58e9bef001c1bab0d0c9b08a4b13a84a9e7a9b4d549bb2c5e90",
    "Vinod": "48b3093ec26141bd7b8b150a7669023586f1bd3b53fd6a3a05777aa9e3d76aac",
    "Manish": "a021c3c411a4a3cb971eeb978f3df49f172c31d58a270a7d8c7a4218a2eb24f9",
    "Vijay": "d2c8a6da1a9291485a92dd8554cf42be1e28090b517a503b9d3e2fbfbc8469cb",
}
SPECIAL_MEMBERS = {"Sid", "Ajit", "Vinod", "Nikhil", "Shyam", "Nikhat"}
PNL_MEMBERS = {"Sid", "Ajit", "Vinod", "Nikhil"}
AUDITED_MEMBERS = {"Ajit", "Nikhat", "Shyam"}
LIMITED_RECORD_BRANCH = {"Nitish": "Pune", "Gopal": "Pune", "Manish": "Wada", "Vijay": "Andheri"}
CANONICAL_VEHICLE_PLACERS = ("Nitish Jha", "Ajit Thakur", "Manish Jha")
LOGIN_VEHICLE_PLACERS = {"Nitish": "Nitish Jha", "Ajit": "Ajit Thakur", "Manish": "Manish Jha"}
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


def canonical_vehicle_placer(value):
    original = clean_text(value)
    normalized = " ".join(re.findall(r"[a-z]+", original.casefold()))
    if not normalized:
        return original
    words = normalized.split()
    for canonical in CANONICAL_VEHICLE_PLACERS:
        target = canonical.casefold()
        if normalized == target:
            return canonical
        target_words = target.split()
        full_score = SequenceMatcher(None, normalized, target).ratio()
        word_match = len(words) == 2 and all(
            SequenceMatcher(None, word, target_word).ratio() >= 0.78
            for word, target_word in zip(words, target_words)
        )
        if full_score >= 0.82 or word_match:
            return canonical
    return original


def canonicalize_placer_state(key):
    st.session_state[key] = canonical_vehicle_placer(st.session_state.get(key, ""))


def apply_vijay_transporter_profile(prefix):
    profile = vijay_transporter_profile(st.session_state.get(f"{prefix}_transporter_name"))
    for field, value in profile.items():
        if field != "transporter_name":
            st.session_state[f"{prefix}_{field}"] = value


def apply_saved_transporter_profile(prefix):
    profile = recall(
        business_memory, "transporters",
        st.session_state.get(f"{prefix}_transporter_name"),
    )
    state_fields = {
        "beneficiary_name": "beneficiary_name",
        "account_number": "beneficiary_account_number",
        "ifsc": "beneficiary_ifsc_code",
    }
    for source_field, state_field in state_fields.items():
        value = profile.get(source_field, ("", 0))[0]
        # Clear details from the previous transporter when the selected/new
        # transporter has no saved value; never carry banking data across.
        st.session_state[f"{prefix}_{state_field}"] = value


def apply_vijay_freight_rate(prefix):
    revenue = st.session_state.get(f"{prefix}_revenue")
    st.session_state[f"{prefix}_transporter_freight"] = vijay_transporter_freight(revenue)


def apply_vijay_vehicle_profile(prefix, update_vehicle=True):
    vehicle_key = f"{prefix}_vehicle_number"
    resolved_vehicle = resolve_vijay_vehicle_number(st.session_state.get(vehicle_key))
    transporter = vijay_transporter_for_vehicle(resolved_vehicle)
    if not transporter:
        return
    if update_vehicle:
        st.session_state[vehicle_key] = resolved_vehicle
    st.session_state[f"{prefix}_transporter_name"] = transporter
    st.session_state[f"{prefix}_ownership_type"] = "Outside"
    for field, value in vijay_transporter_profile(transporter).items():
        st.session_state[f"{prefix}_{field}"] = value


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
    prefix = "Request"
    if isinstance(row_or_number, dict):
        if row_or_number.get("report_scope") == "Expense":
            prefix = "Expense Request"
        date = row_or_number.get("trip_date")
        row_or_number = row_or_number.get("request_number", "")
    suffix = clean_text(row_or_number).split("-")[-1].lstrip("0") or "1"
    return f"{prefix} - {as_date(date):%d/%m/%y} · {suffix}"


def record_select_label(row):
    dtr = unpack(row.get("dtr_data"))
    placed_by = canonical_vehicle_placer(dtr.get("Veh Placed by")) or "Not specified"
    billtee = number(dtr.get("Billtee"))
    billtee_text = f"{billtee:,.0f}" if billtee.is_integer() else f"{billtee:,.2f}"
    details = f"{placed_by}, Billtee Amt: {billtee_text}".translate(ASCII_BOLD)
    return f"{request_label(row)} [{details}]"


def duplicate_records(rows):
    """Return redundant copies while retaining the oldest record in each group."""
    grouped = {}
    duplicates = []
    for row in sorted(rows, key=lambda item: int(item.get("id") or 0)):
        invoice = clean_text(row.get("invoice_number")).casefold()
        signature = (
            row.get("report_scope"), as_date(row.get("trip_date")),
            re.sub(r"[^a-z0-9]", "", clean_text(row.get("vehicle_number")).casefold()),
            invoice or clean_text(row.get("from_location")).casefold(),
            "" if invoice else clean_text(row.get("to_location")).casefold(),
            "" if invoice else round(number(row.get("revenue")), 2),
            "" if invoice else round(number(row.get("amount")), 2),
        )
        if signature in grouped:
            duplicates.append(row)
        else:
            grouped[signature] = row
    return duplicates


def trip_auto_remark(vehicle_number, origin, destination, vehicle_capacity, trip_date):
    digits = "".join(character for character in clean_text(vehicle_number) if character.isdigit())[-4:]
    origin, destination = canonical_location(origin), canonical_location(destination)
    route = f"{origin} to {destination}" if origin and destination else origin or destination
    return plain_remark(digits, route, canonical_vehicle_capacity(vehicle_capacity), f"{as_date(trip_date):%d %m %Y}", "TA")


def expense_auto_remark(vehicle_number, beneficiary_name, categories, expense_date):
    digits = "".join(character for character in clean_text(vehicle_number) if character.isdigit())[-4:]
    category_text = " ".join(categories)
    return plain_remark(digits, clean_text(beneficiary_name), category_text, f"{as_date(expense_date):%d %m %Y}", "DE")


def sync_auto_remark(widget_key, generated):
    tracker_key = f"{widget_key}_generated"
    current = clean_text(st.session_state.get(widget_key))
    previous = clean_text(st.session_state.get(tracker_key))
    if generated and (not current or current == previous):
        st.session_state[widget_key] = generated
    st.session_state[tracker_key] = generated


def rtgs_remark(row):
    """Build the standard bank remark: vehicle, route, capacity, date, TA."""
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
            if mode == "ENTRY" and current_user == "Vijay" and len(files) > 1:
                # Extract each invoice independently. A combined multimodal
                # response can legally return one row yet overlook identifiers
                # on later images, even when every image describes one trip.
                individual_results = [
                    extract_intake(
                        secret("GEMINI_API_KEY"), mode, instruction, [item], secret("GEMINI_MODEL"),
                    )[0]
                    for item in files
                ]
                extracted_rows = [result.rows[0] for result in individual_results if result.rows]
                result = individual_results[0]
                merged = merge_same_trip_intake_rows(extracted_rows)
                if merged:
                    known_invoice_values = [
                        row.get("invoice_number") or unpack(row.get("dtr_data")).get("Invoice No.")
                        for row in normalization_rows
                    ]
                    reconciled = reconcile_sequential_invoice_series(
                        merged.invoice_numbers, known_invoice_values,
                    )
                    if reconciled is None:
                        merged.invoice_numbers = []
                        merged.invoice_number = ""
                        st.warning(
                            "The uploaded invoices appear sequential, but their printed series prefixes "
                            "could not be verified. Please enter each invoice number manually."
                        )
                    else:
                        merged.invoice_numbers = reconciled
                        merged.invoice_number = reconciled[0] if reconciled else ""
                result.rows = [merged] if merged else []
            else:
                result, _ = extract_intake(secret("GEMINI_API_KEY"), mode, instruction, files, secret("GEMINI_MODEL"))
            if mode == "ENTRY" and current_user == "Vijay" and result.rows:
                row = result.rows[0]
                raw_invoice_candidates = [*row.invoice_numbers, row.invoice_number]
                if not row.invoice_number and not row.invoice_numbers:
                    raw_invoice_candidates.append(row.lr_invoice_number)
                verified_invoices = verified_bisleri_invoice_numbers(raw_invoice_candidates)
                rejected = normalized_invoice_numbers(raw_invoice_candidates)
                row.invoice_numbers = verified_invoices
                row.invoice_number = verified_invoices[0] if verified_invoices else ""
                row.lr_invoice_number = ""
                if rejected and len(verified_invoices) < len(rejected):
                    st.warning(
                        "An extracted value did not match Bisleri's MUMCIN invoice-number format and was "
                        "not inserted. Please enter any missing invoice number manually."
                    )
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
            if field == "invoice_numbers":
                continue
            if value not in (None, "") and should_autofill_field(mode, field):
                state_field = expense_keys.get(field, field) if mode == "EXPENSE" else field
                state_key = f"{prefix}_{state_field}"
                current = st.session_state.get(state_key)
                blank = current in (None, "", 0, 0.0) or (field == "date" and current == dt.date.today())
                if blank:
                    st.session_state[state_key] = as_date(value) if field == "date" else value
        # Older cached AI responses used one combined identifier. Preserve it
        # as an invoice only when neither explicit field was extracted.
        if mode == "ENTRY":
            extracted_invoices = normalized_invoice_numbers(result.rows[0].invoice_numbers)
            if extracted_invoices:
                st.session_state[f"{prefix}_invoice_numbers"] = extracted_invoices
            if current_user == "Vijay":
                destination_evidence = " ".join(filter(None, (
                    result.rows[0].delivery_customer_code,
                    result.rows[0].delivery_address,
                    result.rows[0].to_location,
                )))
                if destination_evidence:
                    st.session_state[f"{prefix}_to_location"] = canonical_vijay_location(destination_evidence)
            legacy = clean_text(getattr(result.rows[0], "lr_invoice_number", ""))
            if legacy and not clean_text(st.session_state.get(f"{prefix}_invoice_number")) and not clean_text(st.session_state.get(f"{prefix}_lr_number")):
                st.session_state[f"{prefix}_invoice_number"] = legacy
        st.success("Form populated from the evidence. Please review every field before saving.")
    except Exception as exc:
        st.error(f"Could not auto-fill the form: {exc}")


def file_values(files, preferred_filename=None):
    evidence_files = [f for f in files if f["mime_type"].startswith("image/") or f["mime_type"] == "application/pdf"]
    source = next((f for f in evidence_files if f["filename"] == preferred_filename), None)
    source = source or (evidence_files[-1] if evidence_files else None)
    return {"source_filename": source["filename"] if source else "", "source_mime_type": source["mime_type"] if source else "", "source_image": source["data"] if source else None}


def trip_payload(v, files, invoice_filename=None):
    company = canonical_company(v["company_name"], KNOWN_COMPANIES)
    origin = canonical_location(v["from_location"], KNOWN_LOCATIONS)
    destination = canonical_location(v["to_location"], KNOWN_LOCATIONS)
    capacity = canonical_vehicle_capacity(v["vehicle_capacity"])
    vehicle_number = canonical_vehicle_number(v["vehicle_number"])
    remarks = trip_auto_remark(vehicle_number, origin, destination, capacity, v["date"])
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
        "Branch": v["branch"], "Compnay Name": company, "Date": v["date"], "Vehicle No.": vehicle_number,
        "Vehicle Type": capacity, "Own/Outside Veh.": v["ownership_type"], "From": origin,
        "To": destination, "LR No.": v["lr_number"], "Invoice No.": v["invoice_number"],
        "Revenue": v["revenue"], "Transporter Freight": transporter_freight, "RTGS ADVANCE": v["rtgs_advance"],
        "Cash Adv.": v["cash_advance"], "UPI": v["upi"], "Diesel Adv.": v["diesel_advance"], "Billtee": billtee, "Total Adv.": total,
        "Diesel Qty": number(v.get("diesel_quantity")), "Diesel Rate": number(v.get("diesel_rate")),
        "Balance Amt.": balance, "Toll Expense": toll_expense, "Repairs & Maintenance": repairs_maintenance,
        "Repair Reason": clean_text(v.get("repair_reason")), "Benificiary Name": v["beneficiary_name"],
        "Diesel Pump Name": v["diesel_pump_name"], "Card Name": v["card_name"],
        "Transporter Name": v["transporter_name"], "Veh Placed by": canonical_vehicle_placer(v["vehicle_placed_by"]), "Remark": remarks,
    }
    rtgs = {"BNF_NAME": v["beneficiary_name"], "BENE_ACC_NO": v["beneficiary_account_number"], "BENE_IFSC": v["beneficiary_ifsc_code"], "AMOUNT": v["rtgs_advance"], "REMARK": remarks, "Origin Area": v["branch"]}
    return {
        "report_scope": "Both", "trip_date": v["date"], "vehicle_number": vehicle_number, "vehicle_type": capacity,
        "ownership_type": v["ownership_type"], "from_location": origin, "to_location": destination,
        "company_name": company, "branch": v["branch"], "invoice_number": v["invoice_number"],
        "beneficiary_name": v["beneficiary_name"], "transporter_name": v["transporter_name"], "amount": total,
        "payment_mode": ", ".join(name for name, amount in payments.items() if amount), "revenue": v["revenue"],
        "transporter_freight": transporter_freight, "rtgs_advance": v["rtgs_advance"], "cash_advance": v["cash_advance"],
        "upi": v["upi"], "diesel_quantity": number(v.get("diesel_quantity")) or None,
        "diesel_advance": v["diesel_advance"], "total_advance": total,
        "balance_amount": balance, "status": "Verified", "notes": remarks,
        "dtr_data": dtr, "rtgs_data": rtgs, **file_values(files, invoice_filename),
    }


def expense_payload(v, files):
    payments = {name: number(v[field]) for name, field in PAYMENT_FIELDS.items()}
    card = number(v.get("card"))
    categories = {name: number(v.get(name)) for name in ALL_DIRECT_EXPENSE_COLUMNS}
    return {
        "report_scope": "Expense", "trip_date": v["date"], "vehicle_number": canonical_vehicle_number(v["vehicle_number"]),
        "vehicle_type": canonical_vehicle_capacity(v["vehicle_capacity"]), "ownership_type": v["ownership_type"],
        "branch": v["branch"],
        "beneficiary_name": v["beneficiary_name"], "expense_type": ", ".join(k for k, val in categories.items() if val),
        "amount": sum(categories.values()), "payment_mode": ", ".join([*(k for k, val in payments.items() if val), *(["Card"] if card else [])]),
        "rtgs_advance": payments["RTGS"], "cash_advance": payments["Cash"], "upi": payments["UPI"],
        "diesel_advance": payments["Diesel"], "total_advance": sum(payments.values()) + card, "notes": plain_remark(v["remarks"]),
        "status": "Verified", "dtr_data": {
            "categories": categories, "payments": {**payments, "Card": card},
            "periods": {
                category: serialize_period(v.get(f"{category}_period"))
                for category in PERIOD_EXPENSE_CATEGORIES if number(v.get(category))
            },
            "Diesel Pump Name": v["diesel_pump_name"], "Card Name": v["card_name"],
            "Cardholders Name": clean_text(v.get("cardholders_name")),
        }, "rtgs_data": {
            "BENE_ACC_NO": clean_text(v["beneficiary_account_number"]),
            "BENE_IFSC": clean_text(v["beneficiary_ifsc_code"]),
        }, **file_values(files),
    }


def page_intro(kicker, title, description, icon):
    eyebrow = f'<div class="eyebrow">{kicker}</div>' if kicker else ""
    st.markdown(
        f"""<div class="page-intro"><div class="page-icon">{icon}</div><div>
        {eyebrow}<h2>{title}</h2><p>{description}</p>
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
    v = {}
    normalization = {
        "company_name": lambda value: canonical_company(value, KNOWN_COMPANIES),
        "from_location": lambda value: canonical_location(value, KNOWN_LOCATIONS),
        "to_location": lambda value: canonical_location(value, KNOWN_LOCATIONS),
        "vehicle_capacity": canonical_vehicle_capacity,
        "vehicle_number": canonical_vehicle_number,
    }
    for field, normalizer in normalization.items():
        key = f"{prefix}_{field}"
        if clean_text(st.session_state.get(key)):
            st.session_state[key] = normalizer(st.session_state[key])
    if current_user == "Vijay":
        st.session_state[f"{prefix}_company_name"] = "Bisleri International Private Limited"
        st.session_state[f"{prefix}_vehicle_number"] = resolve_vijay_vehicle_number(
            st.session_state.get(f"{prefix}_vehicle_number"),
        )
        st.session_state[f"{prefix}_from_location"] = canonical_vijay_location(
            st.session_state.get(f"{prefix}_from_location"), origin=True,
        )
        st.session_state[f"{prefix}_to_location"] = canonical_vijay_location(
            st.session_state.get(f"{prefix}_to_location"),
        )
    st.markdown("#### 1. Basic information")
    c1, c2 = st.columns(2)
    branch_key = f"{prefix}_branch"
    available_branches = allowed_branches or BRANCHES
    if current_user == "Vijay" and "Andheri" in available_branches:
        st.session_state[branch_key] = "Andheri"
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
    if current_user == "Vijay":
        extracted_invoices = normalized_invoice_numbers(st.session_state.get(f"{prefix}_invoice_numbers", []))
        invoice_slots = max(1, int(st.session_state.get(f"{prefix}_invoice_slots", 1)), len(extracted_invoices))
        invoice_values = []
        for index in range(invoice_slots):
            key = f"{prefix}_invoice_number" if index == 0 else f"{prefix}_invoice_number_{index + 1}"
            if index < len(extracted_invoices) and not clean_text(st.session_state.get(key)):
                st.session_state[key] = extracted_invoices[index]
            invoice_values.append(c2.text_input(
                "Invoice number" if index == 0 else f"Invoice number {index + 1}",
                key=key, placeholder="e.g., MUMCIN270034867",
            ))
        v["invoice_number"] = combined_invoice_number(invoice_values)
    else:
        v["invoice_number"] = c2.text_input("Invoice number", key=f"{prefix}_invoice_number", placeholder="e.g., INV-10595976")
    duplicate_invoices = user_invoice_duplicates(normalization_rows, current_user, v["invoice_number"])
    if duplicate_invoices:
        labels = ", ".join(request_label(row) for row in duplicate_invoices[:3])
        c2.error(f"Duplicate detected: this invoice number already exists in {labels}.")
    st.markdown("#### 2. Vehicle information")
    c1, c2, c3 = st.columns(3)
    vehicle_input_kwargs = {
        "on_change": apply_vijay_vehicle_profile, "args": (prefix,),
    } if current_user == "Vijay" else {}
    v["vehicle_number"] = c1.text_input(
        "Vehicle number *", key=f"{prefix}_vehicle_number", placeholder="e.g., MH14JL9818",
        **vehicle_input_kwargs,
    )
    if current_user == "Vijay":
        # The vehicle widget is already instantiated here; its value was
        # resolved before rendering, so only apply dependent fields.
        apply_vijay_vehicle_profile(prefix, update_vehicle=False)
    v["vehicle_capacity"] = c2.text_input("Vehicle capacity", key=f"{prefix}_vehicle_capacity", placeholder="e.g., 20MT")
    choices = ["", "Own", "Outside"]
    current = st.session_state.get(f"{prefix}_ownership_type", "")
    v["ownership_type"] = c3.selectbox("Own or outside", choices, index=choices.index(current) if current in choices else 0, key=f"{prefix}_ownership_type")
    own_workflow = simplified or is_own_vehicle(v["ownership_type"])
    v["simplified"] = own_workflow
    placer_key = f"{prefix}_vehicle_placed_by"
    v["vehicle_placed_by"] = st.text_input(
        "Vehicle placed by", key=placer_key, placeholder="e.g., Ajit Thakur",
        on_change=canonicalize_placer_state, args=(placer_key,),
    )
    memory_prompt(prefix, f"Known setup for {v['vehicle_number']}", f"vehicle_{v['vehicle_number']}", recall(memory, "vehicles", v["vehicle_number"]), ["vehicle_capacity", "transporter_name", "ownership_type", "vehicle_placed_by"])
    memory_prompt(prefix, f"Known branch for {v['company_name']}", f"company_{v['company_name']}", recall(memory, "companies", v["company_name"]), ["branch"])
    if own_workflow:
        v.update({"beneficiary_name": "", "transporter_name": "", "beneficiary_account_number": "", "beneficiary_ifsc_code": ""})
    else:
        st.markdown("#### 3. Beneficiary details")
        c1, c2 = st.columns(2)
        if current_user == "Vijay":
            v["beneficiary_name"] = c1.text_input("Beneficiary name", key=f"{prefix}_beneficiary_name", placeholder="e.g., XYZ Transport")
            transporter_key = f"{prefix}_transporter_name"
            if st.session_state.get(transporter_key) not in ("", *VIJAY_TRANSPORTER_PROFILES):
                st.session_state[transporter_key] = ""
            v["transporter_name"] = c2.selectbox(
                "Transporter name", ["", *VIJAY_TRANSPORTER_PROFILES],
                key=transporter_key, placeholder="Select a transporter",
                on_change=apply_vijay_transporter_profile, args=(prefix,),
            )
        else:
            transporter_key = f"{prefix}_transporter_name"
            transporter_options = sorted({
                profile.get("transporter_name", ("", 0))[0]
                for profile in memory.get("transporters", {}).values()
                if profile.get("transporter_name", ("", 0))[0]
            }, key=str.casefold)
            current_transporter = clean_text(st.session_state.get(transporter_key))
            options = ["", *transporter_options]
            if current_transporter and current_transporter not in options:
                options.append(current_transporter)
            v["transporter_name"] = c1.selectbox(
                "Transporter name", options, key=transporter_key,
                placeholder="Type or select a transporter", accept_new_options=True,
                on_change=apply_saved_transporter_profile, args=(prefix,),
            )
            v["beneficiary_name"] = c2.text_input("Beneficiary name", key=f"{prefix}_beneficiary_name", placeholder="e.g., XYZ Transport")
        c1, c2 = st.columns(2)
        v["beneficiary_account_number"] = c1.text_input("Account number", key=f"{prefix}_beneficiary_account_number", placeholder="e.g., 0206101019660")
        v["beneficiary_ifsc_code"] = c2.text_input("IFSC code", key=f"{prefix}_beneficiary_ifsc_code", placeholder="e.g., ICIC0001234")
        beneficiary_memory = recall(memory, "beneficiaries", v["beneficiary_name"])
        beneficiary_memory = {"beneficiary_account_number" if key == "account_number" else "beneficiary_ifsc_code" if key == "ifsc" else key: value for key, value in beneficiary_memory.items()}
        memory_prompt(prefix, f"Known beneficiary details for {v['beneficiary_name']}", f"beneficiary_{v['beneficiary_name']}", beneficiary_memory, ["beneficiary_account_number", "beneficiary_ifsc_code", "transporter_name"])
    st.markdown(f"#### {'3' if own_workflow else '4'}. Payment details")
    if own_workflow:
        if current_user == "Vijay":
            revenue_key = f"{prefix}_revenue"
            if vijay_transporter_freight(st.session_state.get(revenue_key)) is None:
                st.session_state[revenue_key] = None
            v["revenue"] = st.selectbox(
                "Revenue freight (₹)", [None, *VIJAY_FREIGHT_RATES], key=revenue_key,
                format_func=lambda value: "Select revenue freight" if value is None else f"₹{value:,}",
                on_change=apply_vijay_freight_rate, args=(prefix,),
            )
        else:
            v["revenue"] = st.number_input("Revenue freight (₹)", min_value=0.0, value=None, placeholder="e.g., 50,000", key=f"{prefix}_revenue")
        v["transporter_freight"] = 0.0
    else:
        c1, c2 = st.columns(2)
        if current_user == "Vijay":
            revenue_key = f"{prefix}_revenue"
            if vijay_transporter_freight(st.session_state.get(revenue_key)) is None:
                st.session_state[revenue_key] = None
            v["revenue"] = c1.selectbox(
                "Revenue freight (₹)", [None, *VIJAY_FREIGHT_RATES], key=revenue_key,
                format_func=lambda value: "Select revenue freight" if value is None else f"₹{value:,}",
                on_change=apply_vijay_freight_rate, args=(prefix,),
            )
        else:
            v["revenue"] = c1.number_input("Revenue freight (₹)", min_value=0.0, value=None, placeholder="e.g., 50,000", key=f"{prefix}_revenue")
        own_vehicle = is_own_vehicle(v["ownership_type"])
        transporter_freight_key = f"{prefix}_transporter_freight"
        if own_vehicle:
            st.session_state[transporter_freight_key] = None
        v["transporter_freight"] = c2.number_input("Transporter freight (₹)", min_value=0.0, value=None, placeholder="Not applicable for own vehicles" if own_vehicle else "e.g., 38,000", disabled=own_vehicle or current_user == "Vijay", key=transporter_freight_key)
        if own_vehicle:
            c2.caption("Not applicable for an own vehicle.")
    st.caption("Enter amounts in every payment mode used. Repairs and maintenance are deducted from Profit / Loss." if own_workflow else "Enter amounts in every payment mode used. Billtee is also deducted before calculating the balance payable.")
    if simplified:
        deduction_columns = st.columns(6)
        v["upi"] = deduction_columns[0].number_input(
            "Route Expense (UPI) (₹)", min_value=0.0, value=None,
            placeholder="e.g., 2,000", key=f"{prefix}_upi",
        )
        v["diesel_quantity"] = deduction_columns[1].number_input(
            "Diesel Qty", min_value=0.0, value=None, placeholder="e.g., 100",
            key=f"{prefix}_diesel_quantity",
        )
        v["diesel_rate"] = deduction_columns[2].number_input(
            "Diesel Rate (₹)", min_value=0.0, value=None, placeholder="e.g., 90",
            key=f"{prefix}_diesel_rate",
        )
        diesel_total = float(diesel_expense(v["diesel_quantity"], v["diesel_rate"]))
        calculated_key = f"{prefix}_diesel_calculated"
        st.session_state[calculated_key] = diesel_total
        v["diesel_advance"] = deduction_columns[3].number_input(
            "Diesel (₹)", min_value=0.0, disabled=True, key=calculated_key,
            help="Automatically calculated from Diesel Qty × Diesel Rate.",
        )
        v["toll_expense"] = deduction_columns[4].number_input(
            "Toll Expense (₹)", min_value=0.0, value=None,
            placeholder="e.g., 2,000", key=f"{prefix}_toll_expense",
        )
        v["repairs_maintenance"] = deduction_columns[5].number_input(
            "Repairs & Maintenance (₹)", min_value=0.0, value=None,
            placeholder="e.g., 1,000", key=f"{prefix}_repairs_maintenance",
        )
        v["cash_advance"], v["rtgs_advance"], v["billtee"] = 0.0, 0.0, 0.0
        v["repair_reason"] = st.text_input("Reason", key=f"{prefix}_repair_reason", placeholder="e.g., Tyre puncture repair") if number(v["repairs_maintenance"]) > 0 else ""
        if number(v["repairs_maintenance"]) > 0 and not clean_text(v["repair_reason"]):
            st.caption("Reason is required when Repairs & Maintenance has an amount.")
    elif own_workflow:
        deduction_columns = st.columns(6)
        simplified_fields = [
            ("Route Expense (UPI)", "upi"), ("Diesel", "diesel_advance"), ("Cash", "cash_advance"),
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
    if own_workflow:
        total = sum(number(v[field]) for field in PAYMENT_FIELDS.values()) + number(v["toll_expense"]) + number(v["repairs_maintenance"])
        balance = number(v["revenue"]) - total
    else:
        payment = advance_summary(v["transporter_freight"], *(v[f] for f in PAYMENT_FIELDS.values()), v["billtee"])
        total, balance = float(payment["total_advance"]), float(payment["balance_payable"])
    summary = st.columns(2 if own_workflow else 3)
    metric_offset = 0
    if not own_workflow:
        summary[0].metric("Transporter freight", f"₹{number(v['transporter_freight']):,.2f}")
        metric_offset = 1
    summary[metric_offset].metric("Total expense" if own_workflow else "Total advance", f"₹{total:,.2f}")
    if own_workflow:
        loss_class = " negative" if balance < 0 else ""
        summary[metric_offset + 1].markdown(f'<div class="profit-loss-card{loss_class}"><span>Profit / Loss</span><strong>₹{balance:,.2f}</strong></div>', unsafe_allow_html=True)
    else:
        summary[metric_offset + 1].metric("Balance payable", f"₹{balance:,.2f}", help="Transporter freight minus RTGS, Cash, UPI, Diesel and Billtee deductions. A negative amount indicates an overpayment.")
    if balance < 0 and not own_workflow:
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

normalization_rows = store.list(status="All active")
business_memory = build_business_memory(normalization_rows)
KNOWN_COMPANIES = sorted({clean_text(row.get("company_name")) for row in normalization_rows} - {""}, key=str.casefold)
KNOWN_LOCATIONS = sorted({
    clean_text(row.get(field))
    for row in normalization_rows for field in ("from_location", "to_location")
} - {""}, key=str.casefold)
current_user = st.session_state.get("authenticated_user", "Unknown member")
is_special_member = current_user in SPECIAL_MEMBERS
can_use_direct_expenses = is_special_member or current_user in {"Manish", "Vijay"}
can_generate_reports = is_special_member
can_generate_pnl = current_user in PNL_MEMBERS
record_branch_scope = LIMITED_RECORD_BRANCH.get(current_user)
allowed_entry_branches = [record_branch_scope] if record_branch_scope else BRANCHES
if st.session_state.pop("reset_trip_form", False):
    clear_entry_state(st.session_state)
saved_entry_notice = st.session_state.pop("saved_entry_notice", None)
if st.session_state.pop("reset_expense_form", False):
    clear_expense_state(st.session_state)
saved_expense_notice = st.session_state.pop("saved_expense_notice", None)


def audit_action(action, request_number="", details=""):
    if current_user in AUDITED_MEMBERS:
        store.log_action(current_user, action, request_number, details)


def complete_rtgs_download(request_numbers, start, end):
    updated = store.mark_rtgs_done(request_numbers)
    audit_action(
        "Downloaded RTGS report", "",
        f"{start:%d/%m/%Y} to {end:%d/%m/%Y} · {updated} record(s)",
    )


@st.dialog("View evidence and edit record", width="large")
def view_record(row):
    if not can_view_record(current_user, row):
        st.error("You are not authorized to view this record.")
        return
    legacy_own_expense = (
        row.get("report_scope") == "Expense"
        and clean_text(row.get("created_by")) == current_user
        and not clean_text(row.get("branch"))
    )
    if record_branch_scope and clean_text(row.get("branch")).casefold() != record_branch_scope.casefold() and not legacy_own_expense:
        st.error("You are not authorized to view this record.")
        return
    request_number = row["request_number"]
    if st.session_state.get("evidence_request_number") != request_number:
        st.session_state["evidence_request_number"] = request_number
        st.session_state["evidence_record"] = store.get_evidence(request_number)
    evidence = st.session_state.get("evidence_record") or {}
    raw, is_expense = unpack(row.get("dtr_data")), row.get("report_scope") == "Expense"
    is_manish_expense = clean_text(row.get("created_by")) == "Manish" and is_expense
    is_own_record = is_own_vehicle(row.get("ownership_type")) and not is_expense
    rtgs_raw = unpack(row.get("rtgs_data"))
    display = {
        "Date": row.get("trip_date"), "Type": "Direct expense" if is_expense else "Trip",
        "Branch": row.get("branch", ""), "Company": row.get("company_name", ""),
        "Vehicle": row.get("vehicle_number", ""), "Vehicle Capacity": row.get("vehicle_type", ""),
        "Own / Outside": row.get("ownership_type", ""), "From": row.get("from_location", ""),
        "To": row.get("to_location", ""), "LR No.": raw.get("LR No.", ""),
        "Invoice No.": raw.get("Invoice No.") or row.get("invoice_number", ""),
        "Beneficiary": row.get("beneficiary_name", ""), "Account Number": rtgs_raw.get("BENE_ACC_NO", ""),
        "IFSC": rtgs_raw.get("BENE_IFSC", ""), "Transporter Name": row.get("transporter_name", ""),
        "Vehicle Placed By": raw.get("Veh Placed by", ""),
        "Revenue": number(row.get("revenue")), "Transporter Freight": number(row.get("transporter_freight")),
        "RTGS": number(row.get("rtgs_advance")), "Cash": number(row.get("cash_advance")),
        "UPI": number(row.get("upi")), "Diesel": number(row.get("diesel_advance")),
        "Add Pumps": raw.get("Diesel Pump Name", ""), "Card Name": raw.get("Card Name", ""),
        "Billtee": number(raw.get("Billtee")), "Remarks": row.get("notes", ""),
    }
    if not is_expense:
        display.update({
            "Diesel Qty": number(row.get("diesel_quantity")),
            "Diesel Rate": number(raw.get("Diesel Rate")),
        })
    if is_expense:
        display.update(raw.get("categories", {}))
        stored_periods = expense_periods(row)
        for category in PERIOD_EXPENSE_CATEGORIES:
            period = normalize_period(stored_periods.get(category))
            if period:
                display[f"{category} Period Start"] = period[0]
                display[f"{category} Period End"] = period[1]
        if is_manish_expense:
            display.update({
                "Card": number(raw.get("payments", {}).get("Card")),
                "Cardholders Name": raw.get("Cardholders Name", ""),
            })
    if is_own_record:
        display.pop("Billtee", None)
        display.update({
            "Toll Expense": number(raw.get("Toll Expense")),
            "Repairs & Maintenance": number(raw.get("Repairs & Maintenance")),
            "Reason": raw.get("Repair Reason", ""), "Profit / Loss": number(row.get("balance_amount")),
        })
    locked_columns = ["Type", "Branch"] if record_branch_scope else ["Type"]
    if is_own_record:
        locked_columns.append("Profit / Loss")
    edited = st.data_editor(
        pd.DataFrame([display]), hide_index=True, width="stretch", disabled=locked_columns,
        key=f"record_editor_{row['request_number']}",
    )
    has_evidence = bool(evidence.get("source_image"))
    replace_evidence_key = f"replace_record_evidence_{request_number}"
    replace_evidence = bool(st.session_state.get(replace_evidence_key))
    st.markdown("#### Invoice evidence")
    replacement_evidence = None
    if has_evidence and not replace_evidence:
        with st.container(key=f"evidence_image_frame_{request_number}"):
            if st.button(
                "Remove evidence", icon=":material/close:",
                key=f"remove_record_evidence_{request_number}",
                help="Replace this invoice evidence",
            ):
                st.session_state[replace_evidence_key] = True
                replace_evidence = True
            if not replace_evidence:
                if clean_text(evidence.get("source_mime_type")).startswith("image/"):
                    st.image(evidence["source_image"], caption=evidence.get("source_filename", "Invoice evidence"), width=500)
                else:
                    st.download_button(
                        "Open invoice evidence", evidence["source_image"], evidence.get("source_filename", "invoice.pdf"),
                        evidence.get("source_mime_type"),
                    )
    if not has_evidence or replace_evidence:
        if replace_evidence:
            st.warning("Choose a replacement invoice. The existing evidence will remain unchanged until you save.")
        else:
            st.caption("No invoice evidence is attached to this record.")
        replacement_evidence = st.file_uploader(
            "Upload replacement invoice evidence" if replace_evidence else "Upload invoice evidence",
            type=["png", "jpg", "jpeg", "webp", "pdf"],
            key=f"record_evidence_upload_{request_number}",
            help="Attach the invoice image or PDF, then click Save record changes.",
        )
    edited_item = edited.iloc[0].to_dict()
    repair_reason_missing = is_own_record and number(edited_item.get("Repairs & Maintenance")) > 0 and not clean_text(edited_item.get("Reason"))
    if repair_reason_missing:
        st.caption("Reason is required before repair and maintenance changes can be saved.")
    replacement_missing = replace_evidence and replacement_evidence is None
    if replacement_missing:
        st.caption("Upload the replacement invoice before saving record changes.")
    if st.button(
        "Save record changes", type="primary", key=f"save_record_{row['request_number']}",
        disabled=repair_reason_missing or replacement_missing,
    ):
        item = edited_item
        ownership_type = clean_text(item["Own / Outside"])
        transporter_freight = float(applicable_transporter_freight(ownership_type, item["Transporter Freight"]))
        billtee = number(item.get("Billtee"))
        repairs_maintenance = number(item.get("Repairs & Maintenance"))
        toll_expense = number(item.get("Toll Expense"))
        update_values = {
            "trip_date": as_date(item["Date"]), "branch": clean_text(item["Branch"]),
            "company_name": canonical_company(item["Company"], KNOWN_COMPANIES), "vehicle_number": canonical_vehicle_number(item["Vehicle"]),
            "vehicle_type": canonical_vehicle_capacity(item["Vehicle Capacity"]), "ownership_type": ownership_type,
            "from_location": canonical_location(item["From"], KNOWN_LOCATIONS), "to_location": canonical_location(item["To"], KNOWN_LOCATIONS),
            "invoice_number": clean_text(item["Invoice No."]), "beneficiary_name": clean_text(item["Beneficiary"]),
            "transporter_name": clean_text(item["Transporter Name"]),
            "revenue": number(item["Revenue"]), "transporter_freight": transporter_freight,
            "rtgs_advance": number(item["RTGS"]), "cash_advance": number(item["Cash"]),
            "upi": number(item["UPI"]), "diesel_quantity": number(item.get("Diesel Qty")) or None,
            "diesel_advance": number(item["Diesel"]),
            "notes": trip_auto_remark(item["Vehicle"], item["From"], item["To"], item["Vehicle Capacity"], as_date(item["Date"])) if not is_expense else plain_remark(item["Remarks"]),
        }
        if replacement_evidence is not None:
            update_values.update({
                "source_filename": replacement_evidence.name,
                "source_mime_type": replacement_evidence.type or "application/octet-stream",
                "source_image": replacement_evidence.getvalue(),
            })
        if is_expense:
            categories = {name: number(item.get(name)) for name in ALL_DIRECT_EXPENSE_COLUMNS}
            periods = dict(raw.get("periods", {}))
            for category in PERIOD_EXPENSE_CATEGORIES:
                start_key, end_key = f"{category} Period Start", f"{category} Period End"
                if start_key in item and end_key in item and number(item.get(category)):
                    periods[category] = serialize_period((item[start_key], item[end_key]))
                elif not number(item.get(category)):
                    periods.pop(category, None)
            card = number(item.get("Card")) if is_manish_expense else number(raw.get("payments", {}).get("Card"))
            payments = {
                "UPI": number(item["UPI"]), "Diesel": number(item["Diesel"]),
                "Cash": number(item["Cash"]), "RTGS": number(item["RTGS"]), "Card": card,
            }
            update_values.update({
                "amount": sum(categories.values()),
                "payment_mode": ", ".join(name for name, value in payments.items() if value),
                "total_advance": sum(payments.values()),
                "dtr_data": {
                    **raw, "categories": categories, "payments": payments, "periods": periods,
                    "Diesel Pump Name": clean_text(item["Add Pumps"]), "Card Name": clean_text(item["Card Name"]),
                    "Cardholders Name": clean_text(item.get("Cardholders Name")),
                },
                "rtgs_data": {
                    **rtgs_raw, "BENE_ACC_NO": clean_text(item["Account Number"]),
                    "BENE_IFSC": clean_text(item["IFSC"]),
                },
            })
        else:
            if is_own_record:
                total = sum(number(item[name]) for name in ("RTGS", "Cash", "UPI", "Diesel")) + toll_expense + repairs_maintenance
                balance = number(item["Revenue"]) - total
            else:
                payment = advance_summary(transporter_freight, *(item[name] for name in ("RTGS", "Cash", "UPI", "Diesel")), billtee)
                total, balance = float(payment["total_advance"]), float(payment["balance_payable"])
            normalized_company = canonical_company(item["Company"], KNOWN_COMPANIES)
            normalized_from = canonical_location(item["From"], KNOWN_LOCATIONS)
            normalized_to = canonical_location(item["To"], KNOWN_LOCATIONS)
            normalized_capacity = canonical_vehicle_capacity(item["Vehicle Capacity"])
            normalized_vehicle = canonical_vehicle_number(item["Vehicle"])
            normalized_remark = trip_auto_remark(normalized_vehicle, normalized_from, normalized_to, normalized_capacity, as_date(item["Date"]))
            update_values["notes"] = normalized_remark
            updated_dtr = {
                **raw, "Branch": item["Branch"], "Compnay Name": normalized_company, "Date": as_date(item["Date"]),
                "Vehicle No.": normalized_vehicle, "Vehicle Type": normalized_capacity,
                "Own/Outside Veh.": item["Own / Outside"], "From": normalized_from, "To": normalized_to,
                "LR No.": item["LR No."], "Invoice No.": item["Invoice No."], "Revenue": item["Revenue"],
                "Transporter Freight": transporter_freight, "RTGS ADVANCE": item["RTGS"], "Cash Adv.": item["Cash"],
                "UPI": item["UPI"], "Diesel Adv.": item["Diesel"], "Diesel Pump Name": clean_text(item["Add Pumps"]),
                "Card Name": clean_text(item["Card Name"]), "Billtee": billtee, "Total Adv.": total,
                "Balance Amt.": balance, "Toll Expense": toll_expense, "Repairs & Maintenance": repairs_maintenance,
                "Repair Reason": clean_text(item.get("Reason")), "Benificiary Name": item["Beneficiary"],
                "Transporter Name": clean_text(item["Transporter Name"]),
                "Diesel Qty": number(item.get("Diesel Qty")), "Diesel Rate": number(item.get("Diesel Rate")),
                "Veh Placed by": canonical_vehicle_placer(item["Vehicle Placed By"]), "Remark": normalized_remark,
            }
            updated_rtgs = {
                **rtgs_raw, "BNF_NAME": item["Beneficiary"], "BENE_ACC_NO": item["Account Number"],
                "BENE_IFSC": item["IFSC"], "AMOUNT": item["RTGS"], "REMARK": normalized_remark,
                "Origin Area": item["Branch"],
            }
            update_values.update({
                "amount": total, "total_advance": total, "balance_amount": balance,
                "payment_mode": ", ".join(
                    name for name in ("RTGS", "Cash", "UPI", "Diesel") if number(item.get(name))
                ),
                "dtr_data": updated_dtr, "rtgs_data": updated_rtgs,
            })
        store.update(row["request_number"], update_values, "records_tab", current_user)
        audit_action("Updated record", row["request_number"], request_label(row))
        st.session_state.pop(replace_evidence_key, None)
        st.session_state.pop("evidence_request_number", None)
        st.session_state.pop("evidence_record", None)
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
[data-baseweb="input"]>div,[data-baseweb="select"]>div,textarea{border-color:#dce3eb!important;border-radius:12px!important;background:#fff!important;transition:border .18s ease,box-shadow .18s ease!important}[data-baseweb="input"]>div:focus-within,[data-baseweb="select"]>div:focus-within,textarea:focus{border-color:#0071e3!important;box-shadow:0 0 0 3px rgba(0,113,227,.1)!important}[data-testid="InputInstructions"]{display:none!important}[data-testid="stNumberInput"] button{display:none!important}.stButton>button,.stDownloadButton>button{border-radius:999px;font-weight:700;min-height:42px;padding-left:20px;padding-right:20px;transition:transform .18s ease,box-shadow .18s ease}.stButton>button[kind="primary"],.stDownloadButton>button[kind="primary"]{position:relative;overflow:hidden;border:0;color:#fff;background:#0071e3;box-shadow:0 7px 18px rgba(0,113,227,.22)}.stButton>button:hover,.stDownloadButton>button:hover{transform:translateY(-1px);box-shadow:0 10px 24px rgba(0,113,227,.28)}[class*="st-key-delete_record_"] button,[class*="st-key-remove_record_evidence_"] button{min-width:46px!important;padding:0!important;border:0!important;color:#fff!important;background:#e11d2e!important;box-shadow:0 7px 18px rgba(225,29,46,.22)!important}[class*="st-key-delete_record_"] button p{font-size:0!important}[class*="st-key-delete_record_"] button span,[class*="st-key-remove_record_evidence_"] button span{color:#fff!important;font-size:1.25rem!important}[class*="st-key-delete_record_"] button:hover,[class*="st-key-remove_record_evidence_"] button:hover{background:#c8102e!important;box-shadow:0 10px 24px rgba(225,29,46,.3)!important}[class*="st-key-trip_voice_autofill"] button,.st-key-expense_voice_autofill button{color:#fff!important;background:linear-gradient(135deg,#1f9d60,#27b974)!important;box-shadow:0 8px 20px rgba(31,157,96,.22)!important}[class*="st-key-trip_voice_autofill"] button:disabled,.st-key-expense_voice_autofill button:disabled{color:#fff!important;background:#8fd5ae!important;opacity:.72!important}
[class*="st-key-evidence_image_frame_"]{position:relative!important;width:min(500px,calc(100% - 18px))!important;overflow:visible!important}[class*="st-key-evidence_image_frame_"] [class*="st-key-remove_record_evidence_"]{position:absolute!important;z-index:20!important;top:-13px!important;right:-13px!important;width:38px!important;height:38px!important}[class*="st-key-remove_record_evidence_"] button{display:flex!important;align-items:center!important;justify-content:center!important;gap:0!important;min-width:38px!important;width:38px!important;height:38px!important;min-height:38px!important;padding:0!important;border-radius:50%!important}[class*="st-key-remove_record_evidence_"] button>div{display:flex!important;align-items:center!important;justify-content:center!important;gap:0!important;width:100%!important;height:100%!important}[class*="st-key-remove_record_evidence_"] button p{display:none!important;width:0!important;margin:0!important;padding:0!important}[class*="st-key-remove_record_evidence_"] button span,[class*="st-key-remove_record_evidence_"] button [data-testid="stIconMaterial"]{display:grid!important;place-items:center!important;width:24px!important;height:24px!important;margin:0!important;padding:0!important;line-height:24px!important;font-size:1.35rem!important;transform:none!important}
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
    if saved_entry_notice:
        st.success(saved_entry_notice, icon="✅")
    entry_generation = st.session_state.setdefault("new_entry_generation", 0)
    entry_prefix = entry_state_prefix(entry_generation)
    st.session_state.setdefault(f"{entry_prefix}_vehicle_placed_by", LOGIN_VEHICLE_PLACERS.get(current_user, current_user))
    c1, c2 = st.columns(2)
    upload = c1.file_uploader("Upload photos or PDFs", type=["jpg", "jpeg", "png", "webp", "pdf"], accept_multiple_files=True, key=f"{entry_prefix}_upload", help="Upload the cheque, invoice, and any supporting evidence together.")
    invoice_filename = None
    if upload:
        invoice_filename = c1.selectbox(
            "Invoice evidence shown in Records", [item.name for item in upload], index=len(upload) - 1,
            key=f"{entry_prefix}_invoice_evidence", help="All files are used for autofill; only this invoice file is displayed in Records.",
        )
    if current_user == "Vijay":
        st.session_state[f"{entry_prefix}_invoice_slots"] = max(1, len(upload or []))
    audio = c2.audio_input("Voice instruction · English / हिन्दी / मराठी", key=f"{entry_prefix}_audio")
    voice_autofill = c2.button("Autofill with Voice Prompt", type="primary", use_container_width=True, disabled=audio is None, key=f"{entry_prefix}_voice_autofill", icon="🎙️")
    files = evidence(upload, audio)
    if upload:
        autofill(evidence(upload, None), "", entry_prefix)
    if voice_autofill:
        autofill(evidence(None, audio), "", entry_prefix)
    with st.container(border=True):
        values = trip_form(entry_prefix, business_memory, allowed_entry_branches, simplified=current_user == "Manish")
        repair_reason_missing = values["simplified"] and number(values["repairs_maintenance"]) > 0 and not clean_text(values["repair_reason"])
        if st.button("Save and Another Entry", type="primary", disabled=not values["branch"] or not values["vehicle_number"] or repair_reason_missing, key=f"{entry_prefix}_save"):
            saved = store.create({**trip_payload(values, files, invoice_filename), "created_by": current_user})
            audit_action("Created trip record", saved, request_label(saved, values["date"]))
            st.session_state["saved_entry_notice"] = f"Saved {request_label(saved, values['date'])}. Ready for another entry."
            st.session_state["reset_trip_form"] = True
            st.session_state["new_entry_generation"] = entry_generation + 1
            st.rerun()

with expense_tab:
    if not can_use_direct_expenses:
        st.warning("Direct Expenses is not available for your account.")
    page_intro("Expense capture", "Direct expense", "Turn bills and spoken notes into clean, categorised expense records.", "₹")
    workflow_steps(["Add receipt", "Categorise", "Save and add another"], 0)
    if saved_expense_notice:
        st.success(saved_expense_notice, icon="✅")
    expense_generation = st.session_state.setdefault("direct_expense_generation", 0)
    expense_prefix = expense_state_prefix(expense_generation)
    c1, c2 = st.columns(2)
    expense_upload = c1.file_uploader("Attach bills or receipts", type=["jpg", "jpeg", "png", "webp", "pdf"], accept_multiple_files=True, key=f"{expense_prefix}_upload", disabled=not can_use_direct_expenses)
    expense_audio = c2.audio_input("Voice instruction · English / हिन्दी / मराठी", key=f"{expense_prefix}_audio", disabled=not can_use_direct_expenses)
    expense_voice_autofill = c2.button("Autofill with Voice Prompt", type="primary", use_container_width=True, disabled=expense_audio is None or not can_use_direct_expenses, key=f"{expense_prefix}_voice_autofill", icon="🎙️")
    expense_files = evidence(expense_upload, expense_audio)
    if expense_upload:
        autofill(evidence(expense_upload, None), "", expense_prefix, "EXPENSE")
    if expense_voice_autofill:
        autofill(evidence(None, expense_audio), "", expense_prefix, "EXPENSE")
    with st.container(border=True):
        is_manish = current_user == "Manish"
        if clean_text(st.session_state.get(f"{expense_prefix}_vehicle")):
            st.session_state[f"{expense_prefix}_vehicle"] = canonical_vehicle_number(st.session_state[f"{expense_prefix}_vehicle"])
        c1, c2, c3 = st.columns(3)
        v = {"date": c1.date_input("Date *", format="DD/MM/YYYY", key=f"{expense_prefix}_date"), "beneficiary_name": c2.text_input("Beneficiary name", key=f"{expense_prefix}_beneficiary", placeholder="e.g., Rajesh Kumar"), "vehicle_number": c3.text_input("Vehicle name / number", key=f"{expense_prefix}_vehicle", placeholder="e.g., MH14JL9818")}
        branch_choices = allowed_entry_branches
        expense_branch_key = f"{expense_prefix}_branch"
        if len(branch_choices) == 1:
            st.session_state[expense_branch_key] = branch_choices[0]
        current_expense_branch = clean_text(st.session_state.get(expense_branch_key))
        if current_expense_branch not in branch_choices:
            current_expense_branch = branch_choices[0] if len(branch_choices) == 1 else ""
            st.session_state[expense_branch_key] = current_expense_branch
        c1, c2, c3 = st.columns(3)
        v["branch"] = c1.selectbox(
            "Branch *", ["", *branch_choices],
            index=["", *branch_choices].index(current_expense_branch), key=expense_branch_key,
            disabled=len(branch_choices) == 1, placeholder="Select a branch",
        )
        v["vehicle_capacity"] = c2.text_input("Vehicle Capacity", key=f"{expense_prefix}_vehicle_capacity", placeholder="e.g., 10 MT")
        v["ownership_type"] = c3.selectbox("Own or Outside", ["", "Own", "Outside"], key=f"{expense_prefix}_ownership_type", placeholder="Select ownership")
        c1, c2 = st.columns(2)
        v["beneficiary_account_number"] = c1.text_input("Bank A/C No:", key=f"{expense_prefix}_bank_account", placeholder="e.g., 0206101019660")
        v["beneficiary_ifsc_code"] = c2.text_input("IFSC Code", key=f"{expense_prefix}_ifsc", placeholder="e.g., ICIC0001234")
        st.markdown("#### Expense breakdown")
        cols = st.columns(3)
        visible_expense_columns = MANISH_DIRECT_EXPENSE_COLUMNS if is_manish else STANDARD_DIRECT_EXPENSE_COLUMNS
        for category in ALL_DIRECT_EXPENSE_COLUMNS:
            v[category] = 0.0
        for i, category in enumerate(visible_expense_columns):
            category_key = DIRECT_EXPENSE_COLUMNS.index(category) if category in DIRECT_EXPENSE_COLUMNS else "passing_expense"
            v[category] = cols[i % 3].number_input(f"{category} (₹)", min_value=0.0, value=None, placeholder="e.g., 5,000", key=f"{expense_prefix}_category_{category_key}")
        active_period_categories = [category for category in PERIOD_EXPENSE_CATEGORIES if number(v.get(category))]
        period_columns = st.columns(2)
        for index, category in enumerate(active_period_categories):
            period_columns[index].caption(category)
            v[f"{category}_period"] = period_columns[index].date_input(
                "Period", value=(v["date"], v["date"]), format="DD/MM/YYYY",
                key=f"{expense_prefix}_period_{category.casefold().replace(' ', '_')}",
            )
        invalid_period = any(not normalize_period(v.get(f"{category}_period")) for category in active_period_categories)
        if invalid_period:
            st.caption("Select both the start and end date for each expense period.")
        expense_categories = [category for category in visible_expense_columns if number(v[category])]
        expense_generated_remark = expense_auto_remark(v["vehicle_number"], v["beneficiary_name"], expense_categories, v["date"])
        if clean_text(v["vehicle_number"]) or clean_text(v["beneficiary_name"]) or expense_categories:
            sync_auto_remark(f"{expense_prefix}_remarks", expense_generated_remark)
        v["remarks"] = st.text_area("Remarks", key=f"{expense_prefix}_remarks", placeholder="Auto-filled from the expense details")
        st.markdown("#### Mode of payment")
        st.caption("Fill every mode used for this expense.")
        payment_columns = st.columns(5 if is_manish else 4)
        for col, (label, field) in zip(payment_columns, PAYMENT_FIELDS.items()):
            v[field] = col.number_input(f"{label} (₹)", min_value=0.0, value=None, placeholder="e.g., 5,000", key=f"{expense_prefix}_{field}")
        if is_manish:
            v["card"] = payment_columns[-1].number_input("Card (₹)", min_value=0.0, value=None, placeholder="e.g., 5,000", key=f"{expense_prefix}_card")
            v["cardholders_name"] = st.text_input("Cardholders Name", key=f"{expense_prefix}_cardholders_name", placeholder="e.g., Manish Jha")
        else:
            v["card"], v["cardholders_name"] = 0.0, ""
        if number(v["diesel_advance"]) > 0:
            pump_col, card_col = st.columns(2)
            v["diesel_pump_name"] = pump_col.text_input("Add Pumps", key=f"{expense_prefix}_diesel_pump_name", placeholder="e.g., HP Petrol Pump")
            v["card_name"] = card_col.text_input("Card Name", key=f"{expense_prefix}_card_name", placeholder="e.g., HPCL DriveTrack")
        else:
            v["diesel_pump_name"], v["card_name"] = "", ""
        expense_total = sum(number(v[name]) for name in ALL_DIRECT_EXPENSE_COLUMNS)
        paid_total = sum(number(v[field]) for field in PAYMENT_FIELDS.values()) + number(v["card"])
        c1, c2 = st.columns(2)
        c1.metric("Total direct expense", f"₹{expense_total:,.2f}")
        c2.metric("Payment modes total", f"₹{paid_total:,.2f}")
        if paid_total and abs(expense_total - paid_total) > 0.01:
            st.warning("Expense total and payment-mode total do not match. Review before saving.")
        save_col, another_col = st.columns(2)
        save_expense = save_col.button("Save direct expense", type="primary", key=f"{expense_prefix}_save", disabled=not can_use_direct_expenses or not v["branch"] or invalid_period)
        save_another_expense = another_col.button("Save & Add Another", key=f"{expense_prefix}_save_another", disabled=not can_use_direct_expenses or not v["branch"] or invalid_period)
        if save_expense or save_another_expense:
            saved = store.create({
                **expense_payload(v, expense_files), "created_by": current_user,
            })
            audit_action("Created direct expense", saved, request_label(saved, v["date"]))
            if save_another_expense:
                st.session_state["saved_expense_notice"] = f"Saved {request_label(saved, v['date'])}. Ready for another expense."
                st.session_state["reset_expense_form"] = True
                st.session_state["direct_expense_generation"] = expense_generation + 1
                st.rerun()
            st.success(f"Saved {request_label(saved, v['date'])}.")

with records_tab:
    page_intro("", "Records", "Find, review, edit, and manage every saved operations record.", "▤")
    all_record_rows = store.list(status="All active")
    rows = list(all_record_rows)
    if record_branch_scope:
        rows = [
            row for row in rows
            if clean_text(row.get("branch")).casefold() == record_branch_scope.casefold()
            or (
                row.get("report_scope") == "Expense"
                and clean_text(row.get("created_by")) == current_user
                and not clean_text(row.get("branch"))
            )
        ]
        st.caption(f"Your account can access {record_branch_scope} records only.")
    if current_user in PRIVATE_RECORD_USERS:
        rows = [row for row in rows if can_view_record(current_user, row)]
        st.caption(f"Your account can access records created by {current_user} only.")
    scoped_rows = list(rows)
    if rows:
        st.markdown("#### Filter records")
        c1, c2, c3 = st.columns(3)
        today = dt.date.today()
        month_start = today.replace(day=1)
        filter_from = c1.date_input("Records from", value=month_start, format="DD/MM/YYYY", key="records_filter_from_v2")
        filter_to = c2.date_input("Records to", value=today, format="DD/MM/YYYY", key="records_filter_to_v2")
        record_type = c3.selectbox("Record Type", RECORD_TYPES, key="records_filter_type")
        type_rows = filter_record_type(rows, record_type)
        vehicle_options = sorted({canonical_vehicle_number(row.get("vehicle_number")) for row in type_rows} - {""}, key=str.casefold)
        if record_type == TRIP_RECORDS:
            placed_by_options = sorted({canonical_vehicle_placer(unpack(row.get("dtr_data")).get("Veh Placed by")) for row in type_rows} - {""}, key=str.casefold)
            c1, c2, c3 = st.columns(3)
            placed_by_filter = c1.selectbox("Vehicle placed by", ["All", *placed_by_options], key="records_filter_placed_by")
            vehicle_filter = c2.selectbox("Vehicle no.", ["All", *vehicle_options], key="records_filter_vehicle")
            ownership_filter = c3.selectbox("Own or outside", ["Both", "Own", "Outside"], key="records_filter_ownership")
        else:
            placed_by_filter, ownership_filter = "All", "Both"
            vehicle_filter = st.selectbox("Vehicle no.", ["All", *vehicle_options], key="records_filter_expense_vehicle")
        date_filtered_rows = [row for row in type_rows if filter_from <= as_date(row.get("trip_date")) <= filter_to]
        rows = [row for row in date_filtered_rows if
                (placed_by_filter == "All" or canonical_vehicle_placer(unpack(row.get("dtr_data")).get("Veh Placed by")) == placed_by_filter)
                and (vehicle_filter == "All" or canonical_vehicle_number(row.get("vehicle_number")) == vehicle_filter)
                and ownership_matches(row.get("ownership_type"), ownership_filter)]
        outside_date_rows = []
        if not rows and vehicle_filter != "All":
            outside_date_rows = [
                row for row in filter_record_type(scoped_rows, record_type)
                if canonical_vehicle_number(row.get("vehicle_number")) == vehicle_filter
                and (placed_by_filter == "All" or canonical_vehicle_placer(unpack(row.get("dtr_data")).get("Veh Placed by")) == placed_by_filter)
                and ownership_matches(row.get("ownership_type"), ownership_filter)
            ]
            if outside_date_rows:
                rows = outside_date_rows
                saved_dates = ", ".join(sorted({f"{as_date(row.get('trip_date')):%d/%m/%Y}" for row in rows}))
                st.warning(
                    f"{vehicle_filter} is saved with date {saved_dates}, outside the selected date range. "
                    "It is shown below so the record can be reviewed."
                )
        if record_type == TRIP_RECORDS:
            leaderboard_source = [
                row for row in all_record_rows
                if filter_from <= as_date(row.get("trip_date")) <= filter_to
            ]
            leaderboard_rows = "".join(
                f"<tr><td>{rank}</td><td>{branch}</td><td>{trip_count}</td><td>₹{revenue:,.2f}</td></tr>"
                for rank, (branch, trip_count, revenue) in enumerate(
                    branch_trip_leaderboard(leaderboard_source, BRANCHES), 1
                )
            )
            st.markdown("#### Trip leaderboard")
            st.markdown(
                f'<table class="billtee-board"><thead><tr><th>Rank</th><th>Branch</th><th>Trip count</th><th>Total revenue</th></tr></thead><tbody>{leaderboard_rows}</tbody></table>',
                unsafe_allow_html=True,
            )
    elif record_branch_scope:
        today = dt.date.today()
        leaderboard_source = [
            row for row in all_record_rows
            if today.replace(day=1) <= as_date(row.get("trip_date")) <= today
        ]
        empty_leaderboard_rows = "".join(
            f"<tr><td>{rank}</td><td>{branch}</td><td>{trip_count}</td><td>₹{revenue:,.2f}</td></tr>"
            for rank, (branch, trip_count, revenue) in enumerate(
                branch_trip_leaderboard(leaderboard_source, BRANCHES), 1
            )
        )
        st.markdown("#### Trip leaderboard")
        st.markdown(
            f'<table class="billtee-board"><thead><tr><th>Rank</th><th>Branch</th><th>Trip count</th><th>Total revenue</th></tr></thead><tbody>{empty_leaderboard_rows}</tbody></table>',
            unsafe_allow_html=True,
        )
    live_title, live_evidence_filter, live_sort = st.columns([5, 3, 1], vertical_alignment="center")
    live_title.markdown("#### Live records")
    without_invoice_evidence = live_evidence_filter.toggle(
        "Show Records without Invoice Evidence",
        key="records_without_invoice_evidence",
    )
    rows = filter_without_invoice_evidence(rows, without_invoice_evidence)
    sort_arrow = live_sort.segmented_control(
        "Record order", ["↓", "↑"], default="↓", key="records_sort_arrow",
        label_visibility="collapsed", help="↓ Newest to oldest · ↑ Oldest to newest",
    )
    if current_user == "Vijay":
        pending_invoice_rows = [
            row for row in filter_without_invoice_evidence(scoped_rows, True)
            if row.get("report_scope") != "Expense"
            and clean_text(row.get("created_by")) == "Vijay"
            and clean_text(row.get("branch")).casefold() == "andheri"
        ]
        with st.expander("Upload Pending Invoices & Match"):
            st.caption(
                "Upload multiple invoice images or PDFs. Review every suggested match before attaching them."
            )
            pending_uploads = st.file_uploader(
                "Pending invoice files",
                type=["png", "jpg", "jpeg", "webp", "pdf"],
                accept_multiple_files=True,
                key="vijay_pending_invoice_uploads",
            )
            if st.button(
                "Analyse and match invoices",
                key="analyse_vijay_pending_invoices",
                disabled=not pending_uploads or not pending_invoice_rows,
            ):
                drafts = []
                progress = st.progress(0, text="Reading pending invoices…")
                for index, uploaded in enumerate(pending_uploads, 1):
                    source = {
                        "filename": uploaded.name,
                        "mime_type": uploaded.type or "application/octet-stream",
                        "data": uploaded.getvalue(),
                    }
                    try:
                        result, _ = extract_intake(
                            secret("GEMINI_API_KEY"), "DTR",
                            "Read this single invoice for matching to an existing Andheri trip record. Do not invent missing values.",
                            [source], secret("GEMINI_MODEL"),
                        )
                        extracted = result.rows[0].model_dump() if result.rows else {}
                        suggested, confidence, reason = suggest_invoice_match(extracted, pending_invoice_rows)
                        drafts.append({
                            **source,
                            "suggested_request_number": suggested.get("request_number") if suggested else "",
                            "confidence": confidence,
                            "reason": reason,
                            "vehicle_number": canonical_vehicle_number(extracted.get("vehicle_number")),
                            "invoice_number": clean_text(extracted.get("invoice_number")),
                            "lr_number": clean_text(extracted.get("lr_number")),
                            "date": clean_text(extracted.get("date")),
                            "error": "",
                        })
                    except Exception as exc:
                        drafts.append({
                            **source, "suggested_request_number": "", "confidence": "Error",
                            "reason": "Invoice could not be read", "vehicle_number": "",
                            "invoice_number": "", "lr_number": "", "date": "", "error": str(exc),
                        })
                    progress.progress(index / len(pending_uploads), text=f"Read {index} of {len(pending_uploads)} invoice(s)")
                progress.empty()
                st.session_state["vijay_pending_invoice_matches"] = drafts

            drafts = st.session_state.get("vijay_pending_invoice_matches", [])
            if drafts:
                candidate_labels = {
                    f"{request_label(candidate)} | {canonical_vehicle_number(candidate.get('vehicle_number')) or 'No vehicle'} | {as_date(candidate.get('trip_date')):%d/%m/%y}": candidate
                    for candidate in pending_invoice_rows
                }
                request_to_label = {
                    candidate["request_number"]: label for label, candidate in candidate_labels.items()
                }
                review_rows = [{
                    "File": draft["filename"],
                    "Vehicle": draft["vehicle_number"] or "—",
                    "Invoice / LR": draft["invoice_number"] or draft["lr_number"] or "—",
                    "Invoice Date": draft["date"] or "—",
                    "Confidence": draft["confidence"],
                    "Match reason": draft["reason"],
                    "Match to record": request_to_label.get(draft["suggested_request_number"], "Do not attach"),
                } for draft in drafts]
                reviewed_matches = st.data_editor(
                    pd.DataFrame(review_rows), hide_index=True, width="stretch",
                    disabled=["File", "Vehicle", "Invoice / LR", "Invoice Date", "Confidence", "Match reason"],
                    column_config={
                        "Match to record": st.column_config.SelectboxColumn(
                            "Match to record", options=["Do not attach", *candidate_labels], required=True,
                        ),
                    },
                    key="vijay_pending_invoice_match_review",
                )
                selected_labels = [
                    label for label in reviewed_matches["Match to record"].tolist()
                    if label != "Do not attach"
                ]
                duplicate_matches = len(selected_labels) != len(set(selected_labels))
                if duplicate_matches:
                    st.warning("The same record is selected for more than one invoice. Choose one invoice per record.")
                if st.button(
                    "Confirm and attach invoices", type="primary",
                    key="confirm_vijay_pending_invoices",
                    disabled=not selected_labels or duplicate_matches,
                ):
                    attached = 0
                    skipped = 0
                    for draft, selected_label in zip(drafts, reviewed_matches["Match to record"].tolist()):
                        candidate = candidate_labels.get(selected_label)
                        if not candidate or not can_view_record(current_user, candidate):
                            continue
                        if store.attach_evidence(
                            candidate["request_number"], draft["filename"], draft["mime_type"],
                            draft["data"], edited_by=current_user,
                        ):
                            attached += 1
                            audit_action(
                                "Attached pending invoice", candidate["request_number"], draft["filename"],
                            )
                        else:
                            skipped += 1
                    st.session_state.pop("vijay_pending_invoice_matches", None)
                    st.toast(f"Attached {attached} invoice(s). {skipped} record(s) were skipped.", icon="✅")
                    st.rerun()
            elif not pending_invoice_rows:
                st.info("There are no Vijay trip records waiting for invoice evidence.")
    trip_record_count = sum(row.get("report_scope") != "Expense" for row in rows)
    expense_record_count = sum(row.get("report_scope") == "Expense" for row in rows)
    st.caption(f"{trip_record_count} trip record(s) and {expense_record_count} direct expense record(s) listed.")
    if not rows:
        st.info("No records match the selected filters.")
    else:
        rows = sort_records_by_date(rows, "Oldest first" if sort_arrow == "↑" else "Newest first")
        if current_user == "Vijay":
            st.download_button(
                "Download Excel", export_records_excel(rows),
                f"Vijay-Records-{filter_from}-{filter_to}.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="download_vijay_filtered_records",
            )
        with st.container(height=420, border=True):
            has_delete_column = current_user == "Sid" or current_user in SELF_DELETE_USERS
            record_widths = [1.35, .8, .9, 1.1, 1.15, 1, .85, .65] if has_delete_column else [1.35, .8, .9, 1.1, 1.15, 1, .85]
            record_titles = ("Record", "Date", "Branch", "Vehicle", "Placed by", "Revenue", "", "") if has_delete_column else ("Record", "Date", "Branch", "Vehicle", "Placed by", "Revenue", "")
            header = st.columns(record_widths)
            for column, title in zip(header, record_titles):
                column.markdown(f"**{title}**")
            for record in rows:
                raw = unpack(record.get("dtr_data"))
                columns = st.columns(record_widths, vertical_alignment="center")
                columns[0].write(request_label(record))
                columns[1].write(f"{as_date(record.get('trip_date')):%d/%m/%y}")
                columns[2].write(clean_text(record.get("branch")) or "—")
                columns[3].write(canonical_vehicle_number(record.get("vehicle_number")) or "—")
                columns[4].write(canonical_vehicle_placer(raw.get("Veh Placed by")) or "—")
                columns[5].write(f"₹{number(record.get('revenue')):,.0f}")
                if columns[6].button("View Evidence", key=f"view_record_{record['request_number']}", use_container_width=True):
                    view_record(record)
                if can_delete_record(current_user, record) and columns[7].button("Delete", icon=":material/delete:", key=f"delete_record_{record['request_number']}", help="Delete record", use_container_width=True):
                    request_number = record["request_number"]
                    if store.delete_request(request_number):
                        audit_action("Deleted record", request_number, request_label(record))
                        st.toast(f"Deleted {request_label(record)}.", icon="🗑️")
                        st.rerun()
        if current_user == "Sid":
            duplicate_rows = duplicate_records(scoped_rows)
            duplicate_labels = {record_select_label(row): row for row in duplicate_rows}
            with st.expander("Delete Duplicate records"):
                if not duplicate_labels:
                    st.info("No duplicate records found.")
                select_all = st.checkbox("Select all duplicates", key="records_delete_all", disabled=not duplicate_labels)
                chosen = list(duplicate_labels) if select_all else st.multiselect("Select duplicate records", list(duplicate_labels), key="records_delete_selection", disabled=not duplicate_labels)
                acknowledged = st.checkbox("I understand this permanently deletes the selected duplicate records.", key="records_delete_ack", disabled=not duplicate_labels)
                if st.button("Delete selected duplicates", disabled=not chosen or not acknowledged, key="records_delete"):
                    for label in chosen:
                        request_number = duplicate_labels[label]["request_number"]
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
    today = dt.date.today()
    start = c1.date_input("Records from", value=today.replace(day=1), format="DD/MM/YYYY", key="report_from_v2")
    end = c2.date_input("Records to", value=today, format="DD/MM/YYYY", key="report_to_v2")
    report_options = ["DTR", "RTGS", *(["P&L"] if can_generate_pnl else [])]
    report_type = st.segmented_control("Report type", report_options, default="DTR", key="report_type")
    pnl_ownership_filter = "Both"
    pnl_vehicle_filter = "All"
    if report_type == "P&L":
        pnl_ownership_filter = st.segmented_control(
            "Own or outside vehicle", ["Both", "Own", "Outside", "Vehicle No. Wise"], default="Both", key="pnl_ownership_filter",
        )
    report_rows = (
        store.list(status="All active") if report_type == "P&L"
        else store.list(start, end, status="All active")
    ) if can_generate_reports and start <= end else []
    selected_rows = [
        row for row in report_rows if start <= as_date(row.get("trip_date")) <= end
    ] if report_type == "P&L" else report_rows
    trips = [row for row in selected_rows if row.get("report_scope") != "Expense"]
    if report_type == "P&L":
        if pnl_ownership_filter != "Vehicle No. Wise":
            trips = [row for row in trips if ownership_matches(row.get("ownership_type"), pnl_ownership_filter)]
        pnl_vehicle_options = sorted({canonical_vehicle_number(row.get("vehicle_number")) for row in trips} - {""}, key=str.casefold)
        pnl_vehicle_filter = st.selectbox("Vehicle no.", ["All", *pnl_vehicle_options], key="pnl_vehicle_filter")
        if pnl_vehicle_filter != "All":
            trips = [row for row in trips if canonical_vehicle_number(row.get("vehicle_number")) == pnl_vehicle_filter]
    expenses = [
        row for row in (report_rows if report_type == "P&L" else selected_rows)
        if row.get("report_scope") == "Expense"
    ]
    if report_type == "P&L":
        if pnl_ownership_filter in {"Own", "Outside"}:
            expenses = [
                row for row in expenses
                if clean_text(row.get("ownership_type")).casefold().startswith(pnl_ownership_filter.casefold())
            ]
        if pnl_vehicle_filter != "All":
            expenses = [
                row for row in expenses
                if canonical_vehicle_number(row.get("vehicle_number")) == pnl_vehicle_filter
            ]
        expense_data = allocate_expenses_for_period(
            [{**row, "categories": unpack(row.get("dtr_data")).get("categories", {})} for row in expenses],
            start, end,
        )
        expenses = expense_data
    st.caption(f"{len(trips)} trip record(s) and {len(expenses)} direct expense record(s) selected.")
    if report_type == "DTR":
        records = []
        for i, row in enumerate(reversed(trips), 1):
            data = unpack(row.get("dtr_data"))
            data["Compnay Name"] = canonical_company(data.get("Compnay Name") or row.get("company_name"), KNOWN_COMPANIES)
            data["Vehicle No."] = canonical_vehicle_number(data.get("Vehicle No.") or row.get("vehicle_number"))
            data["Vehicle Type"] = canonical_vehicle_capacity(data.get("Vehicle Type") or row.get("vehicle_type"))
            data["From"] = canonical_location(data.get("From") or row.get("from_location"), KNOWN_LOCATIONS)
            data["To"] = canonical_location(data.get("To") or row.get("to_location"), KNOWN_LOCATIONS)
            data["Toll Expense"] = data.get("Toll Expense", "")
            data["Repairs & Maintenance"] = data.get("Repairs & Maintenance", "")
            data["Remark"] = trip_auto_remark(
                data.get("Vehicle No.") or row.get("vehicle_number"), data["From"], data["To"],
                data["Vehicle Type"], data.get("Date") or row.get("trip_date"),
            )
            records.append({column: data.get(column, "") for column in DTR_REVIEW_COLUMNS} | {"Sr No.": i})
        frame = pd.DataFrame(records, columns=DTR_REVIEW_COLUMNS)
        display_frame = frame.rename(columns={"Compnay Name": "Company Name"})
        st.dataframe(display_frame, hide_index=True, width="stretch")
        st.download_button("Download DTR report", export_operational_dtr(frame), f"DTR-{start}-{end}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", type="primary", disabled=frame.empty or not can_generate_reports, on_click=audit_action, args=("Downloaded DTR report", "", f"{start:%d/%m/%Y} to {end:%d/%m/%Y}"))
    elif report_type == "RTGS":
        rtgs_candidates = list(reversed([item for item in trips if number(item.get("rtgs_advance")) > 0]))
        select_all_rtgs = st.checkbox("Select all", key="rtgs_select_all")
        selection_frame = pd.DataFrame([
            {
                "Select": select_all_rtgs or not bool(row.get("rtgs_done")),
                "Record": request_label(row),
                "Date": f"{as_date(row.get('trip_date')):%d/%m/%y}",
                "Beneficiary": clean_text(row.get("beneficiary_name")) or "—",
                "Amount": number(row.get("rtgs_advance")),
                "Remarks": rtgs_remark(row),
                "RTGS Status": "RTGS Done" if row.get("rtgs_done") else "Pending",
                "_request_number": row.get("request_number"),
            }
            for row in rtgs_candidates
        ])
        if selection_frame.empty:
            st.info("No RTGS records are available in the selected date range.")
            selected_request_numbers = []
        else:
            edited_selection = st.data_editor(
                selection_frame.drop(columns=["_request_number"]),
                hide_index=True, width="stretch", key="rtgs_record_selection",
                disabled=["Record", "Date", "Beneficiary", "Amount", "Remarks", "RTGS Status"],
                column_config={
                    "Select": st.column_config.CheckboxColumn("Select", required=True),
                    "Amount": st.column_config.NumberColumn("Amount", format="₹%.2f"),
                },
            )
            selected_request_numbers = [
                selection_frame.iloc[index]["_request_number"]
                for index, selected in enumerate(edited_selection["Select"].tolist()) if selected
            ]
        selected_rtgs_rows = [
            row for row in rtgs_candidates if row.get("request_number") in selected_request_numbers
        ]
        mark_col, _ = st.columns([1, 3])
        if mark_col.button(
            "Mark selected as RTGS Done", disabled=not selected_request_numbers,
            key="mark_selected_rtgs_done", use_container_width=True,
        ):
            updated = store.mark_rtgs_done(selected_request_numbers)
            audit_action("Marked RTGS Done", "", f"{updated} record(s)")
            st.toast(f"Marked {updated} record(s) as RTGS Done.", icon="✅")
            st.rerun()
        records = []
        for row in selected_rtgs_rows:
            data = unpack(row.get("rtgs_data"))
            data["AMOUNT"], data["BNF_NAME"] = data.get("AMOUNT") or row.get("rtgs_advance"), data.get("BNF_NAME") or row.get("beneficiary_name")
            data["REMARK"] = rtgs_remark(row)
            records.append(data)
        records = normalize_rtgs_records(records, dt.date.today())
        frame = pd.DataFrame(records, columns=RTGS_REVIEW_COLUMNS)
        st.dataframe(frame, hide_index=True, width="stretch")
        st.download_button(
            "Download selected RTGS report", export_rtgs(frame, dt.date.today()),
            f"RTGS-{start}-{end}.xls", "application/vnd.ms-excel", type="primary",
            disabled=frame.empty or not can_generate_reports,
            on_click=complete_rtgs_download,
            args=(selected_request_numbers, start, end),
        )
    else:
        if pnl_ownership_filter == "Both":
            pnl_rows = branch_pnl_summary(trips, expense_data)
        elif pnl_ownership_filter == "Vehicle No. Wise":
            pnl_rows = vehicle_number_pnl_summary(trips, expense_data)
        else:
            pnl_rows = branch_vehicle_pnl_summary(trips, expense_data, pnl_ownership_filter)
        frame = pd.DataFrame(pnl_rows)
        st.dataframe(frame, hide_index=True, width="stretch")
        st.download_button("Download P&L report", export_pnl(trips, expense_data, start, end, pnl_ownership_filter), f"PNL-{start}-{end}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", type="primary", disabled=not can_generate_pnl, on_click=audit_action, args=("Downloaded P&L report", "", f"{start:%d/%m/%Y} to {end:%d/%m/%Y}"))

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
