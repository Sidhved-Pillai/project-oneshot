"""Read-only reconciliation of external DTR sheets against active app trips."""

import json
import re
from collections import Counter

import pandas as pd

from .vehicle_normalization import canonical_vehicle_number
from .vehicle_placer import LOGIN_VEHICLE_PLACERS, canonical_vehicle_placer
from .current_leaderboard import canonical_branch


ALIASES = {
    "date": {"date", "tripdate"},
    "vehicle": {"vehicleno", "vehiclenumber", "vehiclenamenumber", "vehiclename"},
    "invoice": {"invoiceno", "invoicenumber"},
    "lr": {"lrno", "lrnumber"},
    "owner": ("vehplacedby", "vehicleplacedby", "placedby", "createdby"),
    "branch": ("branch", "branchname"),
    "from": {"from", "fromlocation"}, "to": {"to", "tolocation"},
}


def text(value):
    if value is None or pd.isna(value):
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def heading(value):
    return re.sub(r"[^a-z0-9]", "", text(value).casefold())


def read_review_sheet(file, sheet):
    raw = pd.read_excel(file, sheet_name=sheet, header=None, dtype=object)
    for index, row in raw.head(40).iterrows():
        names = {heading(value) for value in row}
        if names & ALIASES["date"] and names & ALIASES["vehicle"]:
            frame = raw.iloc[index + 1:].copy()
            frame.columns = [text(value) or f"Column {i + 1}" for i, value in enumerate(row)]
            if frame.columns.duplicated().any():
                raise ValueError("The DTR has duplicate column headings. Please give each column a unique name.")
            return frame.dropna(how="all").reset_index(drop=True)
    raise ValueError("Could not find Date and Vehicle No. columns in the first 40 rows of this sheet.")


def identity(row):
    values = {heading(key): value for key, value in row.items()}
    def get(field):
        return next((text(values[key]) for key in ALIASES[field] if key in values and text(values[key])), "")
    date_text = get("date")
    date = pd.to_datetime(date_text, dayfirst=not bool(re.match(r"^\d{4}-\d{2}-\d{2}", date_text)), errors="coerce")
    def identifiers(value):
        return frozenset(heading(part) for part in re.split(r"\s*/\s*", value) if heading(part))
    placer = canonical_vehicle_placer(get("owner"))
    owner = next((login for login, name in LOGIN_VEHICLE_PLACERS.items() if placer == name), placer)
    return {
        "date": None if pd.isna(date) else date.date(),
        "vehicle": canonical_vehicle_number(get("vehicle")),
        "invoice": identifiers(get("invoice")), "lr": identifiers(get("lr")),
        "from": heading(get("from")), "to": heading(get("to")), "owner": owner,
        "branch": canonical_branch(get("branch")),
    }


def app_review_frame(records):
    output = []
    for record in records:
        if record.get("report_scope") == "Expense" or record.get("is_archived") or record.get("status") == "Cancelled":
            continue
        raw = record.get("dtr_data") or {}
        try:
            data = json.loads(raw) if isinstance(raw, str) else dict(raw)
        except (TypeError, ValueError):
            data = {}
        if not isinstance(data, dict):
            data = {}
        output.append({**data, "App Record": record.get("request_number"),
            "Date": record.get("trip_date"), "Vehicle No.": record.get("vehicle_number"),
            "Invoice No.": record.get("invoice_number") or data.get("Invoice No.", ""),
            "From": record.get("from_location") or data.get("From", ""),
            "To": record.get("to_location") or data.get("To", ""),
            "Created By": record.get("created_by", "")})
    return pd.DataFrame(output)


def compare_dtr(imported, app_frame, default_branch="Unassigned", progress=None):
    apps = [identity(row) for row in app_frame.to_dict("records")]
    used, seen, output, found = set(), set(), [], 0
    by_trip = {}
    for i, app in enumerate(apps):
        by_trip.setdefault((app["date"], app["vehicle"]), []).append(i)
    for index, row in enumerate(imported.to_dict("records")):
        trip = identity(row)
        fingerprint = tuple(trip[key] for key in ("date", "vehicle", "invoice", "lr", "from", "to"))
        candidates = []
        if trip["date"] and trip["vehicle"]:
            for i in by_trip.get((trip["date"], trip["vehicle"]), []):
                app = apps[i]
                if i in used:
                    continue
                if trip["invoice"]:
                    matches = bool(trip["invoice"] & app["invoice"])
                elif trip["lr"]:
                    matches = bool(trip["lr"] & app["lr"])
                else:
                    matches = all(not trip[key] or trip[key] == app[key] for key in ("from", "to"))
                if matches:
                    candidates.append(i)
        if not trip["date"] or not trip["vehicle"]:
            status = "Invalid / non-trip row"
        elif fingerprint in seen:
            status = "Repeated upload row"
        elif len(candidates) == 1:
            status = "Found in App"
            used.add(candidates[0])
            found += 1
        elif len(candidates) > 1:
            status = "Needs review: multiple app matches"
        else:
            status = "Missing from App"
        seen.add(fingerprint)
        output.append({**row, "Review Status": status,
            "Review Branch": next((branch for branch in ("Wada", "Pune", "Andheri", "Vadodara")
                if branch.casefold() == (trip["branch"] or default_branch).casefold()), trip["branch"] or default_branch),
            "Matched App Record": app_frame.iloc[candidates[0]].get("App Record", "") if status == "Found in App" else ""})
        if progress:
            progress(index + 1, len(imported), found)
    result = pd.DataFrame(output)
    missing = result[result["Review Status"] == "Missing from App"] if not result.empty else result
    return result, dict(Counter(missing.get("Review Branch", [])))


def render_dtr_review(records):
    import hashlib
    import streamlit as st

    st.markdown("### Review DTR")
    st.caption("View-only comparison. Uploading or matching never creates, edits, or deletes records.")
    upload = st.file_uploader("Import your DTR Excel", type=["xlsx", "xls"], key="shyam_review_upload")
    if upload is None:
        return
    try:
        workbook = pd.ExcelFile(upload)
        sheet = st.selectbox("DTR worksheet", workbook.sheet_names, key="shyam_review_sheet")
        imported = read_review_sheet(workbook, sheet)
    except Exception:
        st.error("Could not read this worksheet. Please upload a valid Excel DTR with Date and Vehicle No. column headings.")
        return
    default_branch = st.selectbox("Branch when the Excel has no Branch field",
        ["Unassigned", "Wada", "Pune", "Andheri", "Vadodara"], key="shyam_review_default_branch")
    st.caption("The Excel's Branch field takes priority. Select a fallback for a branch-specific sheet; otherwise blank branches remain Unassigned.")
    signature = hashlib.sha256(upload.getvalue() + sheet.encode() + default_branch.encode() + b"branch-review-v1").hexdigest()
    clicked = st.button("Match it with App's DTR", type="primary", disabled=imported.empty, key="shyam_review_match")
    if not clicked and st.session_state.get("shyam_review_matched") != signature:
        st.dataframe(imported, hide_index=True, width="stretch")
        return
    app_frame = app_review_frame(records)
    dates = [identity(row)["date"] for row in imported.to_dict("records")]
    dates = [date for date in dates if date]
    if dates and not app_frame.empty:
        app_dates = pd.to_datetime(app_frame["Date"], errors="coerce").dt.date
        app_frame = app_frame[(app_dates >= min(dates)) & (app_dates <= max(dates))].reset_index(drop=True)
    left, middle, right = st.columns([5, 2, 5])
    scan = middle.empty()
    bar = middle.progress(0)
    def progress(done, total, found):
        if done == total or done % max(1, total // 50) == 0:
            scan.info(f"Scanning {done}/{total}\n\n{found} trips found")
            bar.progress(done / total)
    result, counts = compare_dtr(imported, app_frame, default_branch, progress if clicked else None)
    st.session_state["shyam_review_matched"] = signature
    found = int((result["Review Status"] == "Found in App").sum()) if not result.empty else 0
    scan.success(f"{found} trips of imported Excel found in App's DTR")
    bar.progress(1.0)
    left.markdown("#### Imported DTR · view only")
    left.dataframe(result, hide_index=True, height=450, width="stretch")
    right.markdown("#### App's DTR · view only")
    right.dataframe(app_frame, hide_index=True, height=450, width="stretch")
    st.markdown("#### Branch-specific missing trips")
    for branch, count in sorted(counts.items()):
        with st.expander(f"{branch}: {count} trip entries missing from App's DTR"):
            st.dataframe(result[(result["Review Status"] == "Missing from App") & (result["Review Branch"] == branch)], hide_index=True, width="stretch")
    if not counts:
        st.success("No missing trip entries found.")
    exceptions = result[~result["Review Status"].isin(["Found in App", "Missing from App"])] if not result.empty else result
    if not exceptions.empty:
        with st.expander(f"{len(exceptions)} repeated, incomplete, or ambiguous rows need review"):
            st.dataframe(exceptions, hide_index=True, width="stretch")
