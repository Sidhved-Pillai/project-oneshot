import hashlib
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from src.config import MASTERS, ROOT
from src.excel_reader import read_table
from src.dtr_generator import generate_dtr, final_review_rows, DTR_COLUMNS, FINANCIAL_COLUMNS
from src.excel_exporter import export_dtr
from src.historical_suggester import HistoricalSuggester

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
    [data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"] { display: none; }
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
        margin-bottom: 1.25rem;
    }
    .oneshot-steps {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: .85rem;
        margin: 0 0 1.75rem 0;
    }
    .oneshot-step {
        display: flex;
        align-items: center;
        min-height: 82px;
        padding: 1rem 1.1rem;
        background: #ffffff;
        border: 1px solid #e5ddf0;
        border-radius: 14px;
        box-shadow: 0 5px 18px rgba(77, 46, 122, .06);
    }
    .oneshot-step-number {
        display: grid;
        place-items: center;
        flex: 0 0 38px;
        width: 38px;
        height: 38px;
        margin-right: .85rem;
        border-radius: 50%;
        background: #7c3aed;
        color: #ffffff;
        font-weight: 800;
    }
    .oneshot-step-copy strong {
        display: block;
        color: #201a29;
        font-size: .98rem;
        line-height: 1.25;
    }
    .oneshot-step-copy span {
        display: block;
        margin-top: .25rem;
        color: #6b6474;
        font-size: .82rem;
        line-height: 1.3;
    }
    @media (max-width: 760px) {
        .oneshot-steps { grid-template-columns: 1fr; }
        .oneshot-step { min-height: 70px; }
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
    <div class="oneshot-steps" aria-label="How to generate a DTR">
      <div class="oneshot-step">
        <div class="oneshot-step-number">1</div>
        <div class="oneshot-step-copy">
          <strong>Upload Consolidated Report</strong>
          <span>Select the approved Excel report.</span>
        </div>
      </div>
      <div class="oneshot-step">
        <div class="oneshot-step-number">2</div>
        <div class="oneshot-step-copy">
          <strong>Review in Real Time</strong>
          <span>Check and correct details if needed.</span>
        </div>
      </div>
      <div class="oneshot-step">
        <div class="oneshot-step-number">3</div>
        <div class="oneshot-step-copy">
          <strong>Download Excel File</strong>
          <span>Export the reviewed DTR workbook.</span>
        </div>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

owned_vehicle_path = MASTERS / "owned_vehicle_master.xlsx"
suggestion_path = ROOT / "data" / "lookups" / "historical_company_branch.json"

def load_masters():
    vehicle_columns = ["Vehicle No.", "Last 4 Digits", "Vehicle Type", "Ownership Type", "Transporter Name", "Vehicle Status"]
    beneficiary_columns = ["Beneficiary Account No.", "Beneficiary Name", "Beneficiary Type", "Transporter Name"]
    vehicles = (pd.read_excel(owned_vehicle_path, dtype=str).fillna("")
                if owned_vehicle_path.exists() else pd.DataFrame(columns=vehicle_columns))
    beneficiaries = pd.DataFrame(columns=beneficiary_columns)
    return vehicles, beneficiaries


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


uploaded = st.file_uploader("Upload consolidated report", type=["xlsx"])
if uploaded:
    try:
        payload = uploaded.getvalue(); signature = hashlib.sha256(payload).hexdigest()[:16]
        source, info = read_table(uploaded, ["Remark", "Remarks", "Beneficiary Name", "Beneficiary Account No"])
        vehicles, beneficiaries = load_masters()
        historical_suggester = HistoricalSuggester.from_json(suggestion_path)
        state_key = f"pipeline_{signature}"
        if state_key not in st.session_state:
            try:
                confirmed, potential, non_trip = generate_dtr(source, vehicles, beneficiaries, historical_suggester)
            except TypeError as exc:
                # Community Cloud can briefly retain an older imported module
                # while hot-reloading app.py. Keep uploads working until its
                # automatic full process restart completes.
                if "positional argument" not in str(exc) or "4" not in str(exc):
                    raise
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
        st.subheader("Final DTR review")
        st.caption("Add/delete rows and edit all operational fields. Phase 1 financial fields are locked blank.")
        config = {"Date": st.column_config.DateColumn(format="DD-MM-YYYY"),
                  "Compnay Name": st.column_config.TextColumn(),
                  "Branch": st.column_config.TextColumn(),
                  "Invoice No.": st.column_config.TextColumn()}
        edited = st.data_editor(review, num_rows="dynamic", width="stretch", hide_index=True,
                                key=f"final_editor_{signature}", column_config=config, disabled=FINANCIAL_COLUMNS)
        for col in FINANCIAL_COLUMNS: edited[col] = ""
        st.download_button("Download reviewed DTR", export_dtr(edited), "Project_Oneshot_DTR.xlsx",
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", type="primary")
        with st.expander(f"Confirmed Non-trip ({len(non_trip)})"):
            st.dataframe(non_trip[["Original Remark", "Original Beneficiary Name", "Reason"]], width="stretch", hide_index=True)
    except Exception as exc: st.error(f"Could not process this workbook: {exc}")
