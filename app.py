import hashlib
import os
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from src.config import MASTERS, VALIDATION, ROOT
from src.excel_reader import read_table
from src.dtr_generator import generate_dtr, final_review_rows, DTR_COLUMNS, FINANCIAL_COLUMNS
from src.excel_exporter import export_dtr
from src.master_builder import build_all
from src.master_store import workbook_bytes, save_master_safely

load_dotenv(ROOT / ".env")
st.set_page_config(page_title="Project Oneshot", layout="wide")
st.markdown(
    """
    <style>
    :root { color-scheme: light; }
    .stApp, [data-testid="stAppViewContainer"], [data-testid="stHeader"] {
        background: #faf9fc;
        color: #17151c;
    }
    [data-testid="stSidebar"] { background: #f2eef8; }
    [data-testid="stSidebar"] * { color: #231f2b; }
    .oneshot-brand {
        margin: 0 0 .15rem 0;
        font-size: clamp(2.25rem, 5vw, 4rem);
        line-height: 1.05;
        font-weight: 800;
        letter-spacing: -.045em;
    }
    .oneshot-project { color: #111111; }
    .oneshot-name { color: #7c3aed; }
    .oneshot-subtitle {
        color: #5f5968;
        font-size: 1.05rem;
        margin-bottom: 1.75rem;
    }
    h1, h2, h3, p, label, [data-testid="stMarkdownContainer"] { color: #17151c; }
    div[data-testid="stMetric"] {
        background: #ffffff;
        border: 1px solid #e8e2f0;
        border-radius: 14px;
        padding: .85rem 1rem;
        box-shadow: 0 4px 18px rgba(77, 46, 122, .05);
    }
    .stButton > button, .stDownloadButton > button {
        border-radius: 10px;
        border-color: #7c3aed;
    }
    .stButton > button[kind="primary"], .stDownloadButton > button[kind="primary"] {
        background: #7c3aed;
        color: #ffffff;
    }
    </style>
    <div class="oneshot-brand" aria-label="Project Oneshot">
      <span class="oneshot-project">Project</span>
      <span class="oneshot-name">Oneshot</span>
    </div>
    <div class="oneshot-subtitle">Draft DTR Generator for Billtee</div>
    """,
    unsafe_allow_html=True,
)

master_paths = {"Vehicle Master": MASTERS / "vehicle_master.xlsx",
                "Company/Branch Master": MASTERS / "company_branch_master.xlsx",
                "Beneficiary/Transporter Master": MASTERS / "beneficiary_transporter_master.xlsx"}

with st.sidebar:
    page = st.radio("Page", ["Generate DTR", "Master Data Management"])
    st.header("Status")
    for name, path in master_paths.items(): st.write(f"{'✅' if path.exists() else '❌'} {name}")
    if os.getenv("GEMINI_API_KEY"): st.write("✅ Gemini configured")
    else:
        st.write("ℹ️ Gemini not configured (optional)")
        st.caption("Copy `.env.example` to `.env`, add GEMINI_API_KEY, then restart the app.")
    if st.button("Rebuild masters"):
        try:
            files = list(ROOT.rglob("*.xlsx")); dtrs = [p for p in files if "DTR - ALL BRANCH" in p.name.upper()]
            consolidated = next(p for p in files if "CONSOLIDATEDREPORT" in p.name.upper())
            st.success(f"Masters rebuilt: {build_all(dtrs, consolidated, MASTERS, VALIDATION)}")
        except Exception as exc: st.error(str(exc))
    for report in sorted(VALIDATION.glob("*.xlsx")):
        st.download_button(f"Download {report.stem}", report.read_bytes(), report.name)


def load_masters():
    vehicles = st.session_state.get("session_master_Vehicle Master")
    companies = st.session_state.get("session_master_Company/Branch Master")
    beneficiaries = st.session_state.get("session_master_Beneficiary/Transporter Master")
    if vehicles is None: vehicles = pd.read_excel(master_paths["Vehicle Master"], dtype=str).fillna("")
    if companies is None: companies = pd.read_excel(master_paths["Company/Branch Master"], dtype=str).fillna("")
    if beneficiaries is None: beneficiaries = pd.read_excel(master_paths["Beneficiary/Transporter Master"], dtype=str).fillna("")
    return vehicles, companies, beneficiaries


def resolve_vehicle_controls(df, vehicles, prefix):
    if df.empty: return df
    result = df.copy()
    for idx, row in result.iterrows():
        choices = row.get("_vehicle_choices", [])
        identifiers = row.get("_vehicle_identifiers", [])
        if len(choices) > 1 or len(identifiers) > 1:
            label = f"Vehicle for: {row.get('Original Remark', '') or 'confirmed trip'}"
            options = [""] + list(dict.fromkeys(list(choices) + list(identifiers)))
            selected = st.selectbox(label, options, key=f"{prefix}_vehicle_{row.get('_row_id')}",
                                    help="Multiple identifiers or master matches were found. Select the verified full registration.")
            if selected:
                result.at[idx, "Vehicle No."] = selected
                matched = vehicles[vehicles["Vehicle No."].eq(selected)]
                if not matched.empty:
                    master = matched.iloc[0]
                    if not result.at[idx, "Vehicle Type"]: result.at[idx, "Vehicle Type"] = master.get("Vehicle Type", "")
                    result.at[idx, "Own/Outside Vehicle"] = master.get("Ownership Type", "")
                    if not result.at[idx, "Transporter Name"]: result.at[idx, "Transporter Name"] = master.get("Transporter Name", "")
    return result


if page == "Master Data Management":
    st.subheader("Master Data Management")
    st.warning("These files may contain sensitive operational data. Download a backup before saving and keep access local/authorized.")
    tabs = st.tabs(list(master_paths))
    for tab, (name, path) in zip(tabs, master_paths.items()):
        with tab:
            session_upload = st.file_uploader(f"Load {name} for this private session", type=["xlsx"], key=f"upload_{name}",
                                              help="Useful for cloud/temporary environments. The upload stays in this app session and is not added to Git.")
            if session_upload is not None:
                st.session_state[f"session_master_{name}"] = pd.read_excel(session_upload, dtype=str).fillna("")
                st.success(f"Session copy of {name} loaded.")
            data = st.session_state.get(f"session_master_{name}")
            if data is None and not path.exists(): st.error("Master is missing. Upload a session copy or rebuild masters first."); continue
            if data is None: data = pd.read_excel(path, dtype=str).fillna("")
            st.download_button(f"Download {name} backup", workbook_bytes(data), f"backup_{path.name}", key=f"backup_{name}")
            disabled = []
            edited = st.data_editor(data, num_rows="dynamic", width="stretch", hide_index=True, key=f"master_editor_{name}", disabled=disabled)
            if st.button(f"Save {name}", key=f"save_{name}"):
                text_cols = ["Beneficiary Account No."] if "Beneficiary" in name else ["Vehicle No.", "Last 4 Digits"]
                save_master_safely(edited, path, text_cols)
                st.success(f"{name} saved safely.")
    st.stop()

st.subheader("Generate draft DTR")
uploaded = st.file_uploader("Upload consolidated payment report", type=["xlsx"])
if uploaded:
    try:
        payload = uploaded.getvalue(); signature = hashlib.sha256(payload).hexdigest()[:16]
        source, info = read_table(uploaded, ["Remark", "Remarks", "Beneficiary Name", "Beneficiary Account No"])
        vehicles, companies, beneficiaries = load_masters()
        state_key = f"pipeline_{signature}"
        if state_key not in st.session_state:
            confirmed, potential, non_trip = generate_dtr(source, vehicles, beneficiaries)
            st.session_state[state_key] = {"confirmed": confirmed, "potential": potential, "non_trip": non_trip}
        state = st.session_state[state_key]
        confirmed, potential, non_trip = state["confirmed"], state["potential"], state["non_trip"]
        st.caption(f"Detected sheet: {info['sheet']} · header row: {info['header_row']}")
        c1,c2,c3,c4 = st.columns(4)
        c1.metric("Total rows", len(source)); c2.metric("Confirmed trips", len(confirmed)); c3.metric("Potential trips", len(potential)); c4.metric("Confirmed non-trips", len(non_trip))

        st.subheader("Potential Trip / Needs Review")
        st.info("No potential row is silently discarded. Tick Include in DTR only after reviewing the original remark.")
        potential = resolve_vehicle_controls(potential, vehicles, f"potential_{signature}")
        potential_visible = ["Include in DTR", "Original Remark", "Original Beneficiary Name"] + DTR_COLUMNS[:10] + DTR_COLUMNS[20:]
        potential_edit = st.data_editor(potential[potential_visible], num_rows="fixed", width="stretch", hide_index=True,
                                        key=f"potential_editor_{signature}",
                                        column_config={"Include in DTR": st.column_config.CheckboxColumn(),
                                                       "Date": st.column_config.DateColumn(format="DD-MM-YYYY")})
        for col in potential_visible: potential[col] = potential_edit[col]
        state["potential"] = potential

        confirmed = resolve_vehicle_controls(confirmed, vehicles, f"confirmed_{signature}")
        review = final_review_rows(confirmed, potential)
        company_options = sorted(x for x in companies["Company Name"].unique() if x)
        branch_options = sorted(x for x in companies["Branch"].unique() if x)
        st.subheader("Final DTR review")
        st.caption("Add/delete rows and edit all operational fields. Phase 1 financial fields are locked blank.")
        config = {"Date": st.column_config.DateColumn(format="DD-MM-YYYY"),
                  "Compnay Name": st.column_config.SelectboxColumn(options=company_options),
                  "Branch": st.column_config.SelectboxColumn(options=branch_options),
                  "Invoice No.": st.column_config.TextColumn()}
        edited = st.data_editor(review, num_rows="dynamic", width="stretch", hide_index=True,
                                key=f"final_editor_{signature}", column_config=config, disabled=FINANCIAL_COLUMNS)
        # Apply the unique company-to-branch relationship after edits; multi-branch companies remain user-selectable.
        for idx, row in edited.iterrows():
            matches = companies[companies["Company Name"].eq(str(row.get("Compnay Name", "")))]
            branches = [x for x in matches["Branch"].unique() if x]
            if len(branches) == 1 and not row.get("Branch"): edited.at[idx, "Branch"] = branches[0]
        for col in FINANCIAL_COLUMNS: edited[col] = ""
        st.download_button("Download reviewed DTR", export_dtr(edited), "Project_Oneshot_DTR.xlsx",
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", type="primary")
        with st.expander(f"Confirmed Non-trip ({len(non_trip)})"):
            st.dataframe(non_trip[["Original Remark", "Original Beneficiary Name", "Reason"]], width="stretch", hide_index=True)
    except Exception as exc: st.error(f"Could not process this workbook: {exc}")
