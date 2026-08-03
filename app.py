import datetime as dt
import os

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from src.config import ROOT
from src.entry_finance import financial_values
from src.excel_exporter import export_dtr
from src.request_store import RequestStore, rows_to_dtr


load_dotenv(ROOT / ".env")
st.set_page_config(page_title="Project Oneshot", page_icon="🚚", layout="wide")


def configured_database_url():
    if os.getenv("DATABASE_URL"):
        return os.environ["DATABASE_URL"]
    try:
        return st.secrets.get("DATABASE_URL")
    except (FileNotFoundError, KeyError):
        return None


@st.cache_resource
def get_store(url):
    return RequestStore(url)


try:
    store = get_store(configured_database_url())
except Exception as exc:
    st.error(f"Database connection failed: {exc}")
    st.stop()

st.markdown(
    """
    <style>
    :root { color-scheme: light; }
    .stApp, [data-testid="stAppViewContainer"], [data-testid="stHeader"] { background:#faf9fc; color:#17151c; }
    [data-testid="stSidebar"] { background:#f4f0f8; }
    .brand {font-size:clamp(2.2rem,5vw,3.7rem);font-weight:800;letter-spacing:-.045em;line-height:1.05}
    .brand span {color:#7c3aed}.subtitle {color:#625a6b;margin:.25rem 0 1.2rem}
    div[data-testid="stMetric"] {background:white;border:1px solid #e8e2f0;border-radius:14px;padding:.8rem 1rem}
    .stButton>button, .stDownloadButton>button {border-radius:10px}
    </style>
    <div class="brand">Project <span>Oneshot</span></div>
    <div class="subtitle">Enter once. Store securely. Generate the DTR for any date range.</div>
    """,
    unsafe_allow_html=True,
)

if store.is_durable_cloud:
    st.caption("🟢 Persistent database connected")
else:
    st.warning("Local SQLite mode: data survives local restarts, but will not survive a Streamlit Community Cloud redeploy. Add DATABASE_URL in Streamlit Secrets before production use.")

new_tab, requests_tab, reports_tab, admin_tab = st.tabs(["➕ New entry", "📋 Requests", "📊 Reports", "⚙️ Data management"])

with new_tab:
    st.subheader("New DTR request")
    st.caption("Fields marked * are required. Attach the original WhatsApp image for verification and audit.")
    with st.form("new_request", clear_on_submit=True):
        source_image = st.file_uploader("Source image", type=["jpg", "jpeg", "png", "webp", "pdf"])
        c1, c2, c3 = st.columns(3)
        trip_date = c1.date_input("Trip date *", value=dt.date.today(), format="DD/MM/YYYY")
        vehicle_number = c2.text_input("Full vehicle number *", placeholder="MH14JL9818")
        vehicle_type = c3.text_input("Vehicle type", placeholder="10MT")
        c1, c2, c3 = st.columns(3)
        ownership_type = c1.selectbox("Vehicle ownership", ["", "Own Vehicle", "Outside Vehicle"])
        from_location = c2.text_input("From")
        to_location = c3.text_input("To")
        c1, c2, c3 = st.columns(3)
        company_name = c1.text_input("Company name")
        branch = c2.text_input("Branch")
        invoice_number = c3.text_input("Invoice number")
        c1, c2 = st.columns(2)
        beneficiary_name = c1.text_input("Beneficiary name")
        transporter_name = c2.text_input("Transporter name")

        st.markdown("##### Financial details")
        c1, c2, c3, c4 = st.columns(4)
        expense_type = c1.selectbox("Expense type", ["Trip Advance", "Balance Payment", "Transporter Freight", "Revenue", "Other"])
        amount = c2.number_input("Amount", min_value=0.0, step=100.0, format="%.2f")
        payment_mode = c3.selectbox("Payment mode", ["RTGS/Bank Transfer", "Cash", "UPI", "Diesel", "Other"])
        diesel_quantity = c4.number_input("Diesel quantity (litres)", min_value=0.0, step=1.0, format="%.2f")
        c1, c2, c3 = st.columns(3)
        status = c1.selectbox("Status", ["Submitted", "Draft", "Verified", "Paid"])
        created_by = c2.text_input("Entered by")
        notes = c3.text_input("Notes")
        allow_duplicate = st.checkbox("Allow saving if this matches an existing request")
        save = st.form_submit_button("Save", type="primary")
        save_another = st.form_submit_button("Save & add another")

    if save or save_another:
        normalized_vehicle = "".join(vehicle_number.upper().split())
        errors = []
        if not normalized_vehicle:
            errors.append("Full vehicle number is required.")
        image_bytes = source_image.getvalue() if source_image else None
        if image_bytes and len(image_bytes) > 8 * 1024 * 1024:
            errors.append("Source file must be 8 MB or smaller.")
        duplicate = store.find_duplicate(trip_date, normalized_vehicle, invoice_number.strip(), amount) if not errors else None
        if duplicate and not allow_duplicate:
            errors.append(f"Possible duplicate of {duplicate}. Review the existing request before saving.")
        if errors:
            for error in errors:
                st.error(error)
        else:
            finance = financial_values(expense_type, payment_mode, amount, diesel_quantity or None)
            number = store.create({
                "trip_date": trip_date, "vehicle_number": normalized_vehicle, "vehicle_type": vehicle_type.strip(),
                "ownership_type": ownership_type, "from_location": from_location.strip(), "to_location": to_location.strip(),
                "company_name": company_name.strip(), "branch": branch.strip(), "invoice_number": invoice_number.strip(),
                "beneficiary_name": beneficiary_name.strip(), "transporter_name": transporter_name.strip(),
                "expense_type": expense_type, "amount": amount, "payment_mode": payment_mode,
                **finance, "status": status, "notes": notes.strip(), "created_by": created_by.strip(),
                "source_filename": source_image.name if source_image else "",
                "source_mime_type": source_image.type if source_image else "",
                "source_image": image_bytes,
            })
            st.success(f"Saved successfully as {number}.")
            if save_another:
                st.info("The form is ready for the next entry.")

with requests_tab:
    st.subheader("Saved requests")
    c1, c2, c3 = st.columns(3)
    request_start = c1.date_input("From date", value=dt.date.today().replace(day=1), key="request_start")
    request_end = c2.date_input("To date", value=dt.date.today(), key="request_end")
    request_status = c3.selectbox("Status", ["All", "Draft", "Submitted", "Verified", "Paid", "Cancelled"])
    saved_rows = store.list(request_start, request_end, request_status)
    st.metric("Requests found", len(saved_rows))
    if saved_rows:
        display_columns = ["request_number", "trip_date", "vehicle_number", "company_name", "invoice_number", "expense_type", "amount", "payment_mode", "status", "created_by"]
        st.dataframe(pd.DataFrame(saved_rows)[display_columns], hide_index=True, width="stretch")
        selected_number = st.selectbox("Open request", [row["request_number"] for row in saved_rows])
        selected = store.get(selected_number)
        with st.expander(f"Details · {selected_number}", expanded=True):
            left, right = st.columns([2, 1])
            left.json({key: str(value) if value is not None else "" for key, value in selected.items() if key not in {"source_image"}})
            if selected.get("source_image"):
                if selected.get("source_mime_type", "").startswith("image/"):
                    right.image(selected["source_image"], caption=selected.get("source_filename"))
                right.download_button("Download source", selected["source_image"], selected.get("source_filename") or "source-file", selected.get("source_mime_type") or None)
        with st.expander("Edit or update status"):
            with st.form(f"edit_{selected_number}"):
                e1, e2, e3 = st.columns(3)
                edit_date = e1.date_input("Trip date", selected["trip_date"], key=f"date_{selected_number}")
                edit_vehicle = e2.text_input("Vehicle number", selected["vehicle_number"])
                statuses = ["Draft", "Submitted", "Verified", "Paid", "Cancelled"]
                current_status = selected["status"] if selected["status"] in statuses else "Submitted"
                edit_status = e3.selectbox("Status", statuses, index=statuses.index(current_status))
                e1, e2, e3 = st.columns(3)
                edit_company = e1.text_input("Company", selected["company_name"])
                edit_branch = e2.text_input("Branch", selected["branch"])
                edit_invoice = e3.text_input("Invoice number", selected["invoice_number"])
                edit_notes = st.text_area("Notes", selected["notes"] or "")
                update_request = st.form_submit_button("Save changes", type="primary")
            if update_request:
                store.update(selected_number, {
                    "trip_date": edit_date, "vehicle_number": "".join(edit_vehicle.upper().split()),
                    "company_name": edit_company.strip(), "branch": edit_branch.strip(),
                    "invoice_number": edit_invoice.strip(), "status": edit_status, "notes": edit_notes.strip(),
                })
                st.success(f"Updated {selected_number}.")
                st.rerun()
    else:
        st.info("No requests found for these filters.")

with reports_tab:
    st.subheader("Generate DTR")
    c1, c2, c3 = st.columns(3)
    report_start = c1.date_input("Report from", value=dt.date.today().replace(day=1), key="report_start")
    report_end = c2.date_input("Report to", value=dt.date.today(), key="report_end")
    report_status = c3.selectbox("Include status", ["Verified", "All active", "Paid", "Submitted", "Draft"])
    report_rows = store.list(report_start, report_end, report_status)
    dtr = rows_to_dtr(report_rows)
    c1, c2, c3 = st.columns(3)
    c1.metric("DTR rows", len(dtr))
    c2.metric("Total amount", f"₹{sum(float(row['amount'] or 0) for row in report_rows):,.2f}")
    c3.metric("Date range", f"{report_start:%d %b} – {report_end:%d %b %Y}")
    st.dataframe(dtr, hide_index=True, width="stretch")
    if not dtr.empty:
        filename = f"Project_Oneshot_DTR_{report_start:%Y%m%d}_{report_end:%Y%m%d}.xlsx"
        st.download_button("Download DTR Excel", export_dtr(dtr, preserve_financials=True), filename,
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", type="primary")

with admin_tab:
    st.subheader("Data retention")
    st.write("A new month does not delete old data. The report and request screens start with the current month, so the visible count naturally resets while history remains available.")
    st.info("Archiving hides older records from normal views without deleting them or their source images.")
    archive_cutoff = st.date_input("Archive entries before", value=dt.date.today().replace(day=1))
    confirm_archive = st.checkbox("I understand these entries will be hidden from normal views")
    if st.button("Archive older entries", disabled=not confirm_archive):
        count = store.archive_before(archive_cutoff)
        st.success(f"Archived {count} request(s). No records were deleted.")
