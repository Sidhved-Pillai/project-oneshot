from pathlib import Path
import re
import pandas as pd
from .column_mapping import DTR_ALIASES, CONSOLIDATED_ALIASES, resolve_columns
from .excel_reader import read_table
from .remark_parser import normalize_vehicle, last_four, normalize_vehicle_type
from .beneficiary_matcher import normalize_account


def _clean(value):
    return "" if pd.isna(value) else str(value).strip()


def build_vehicle_master(dtrs):
    records = []
    for df in dtrs:
        m = resolve_columns(df.columns, DTR_ALIASES)
        for _, row in df.iterrows():
            vehicle = normalize_vehicle(row.get(m.get("Vehicle No.", ""), ""))
            if not vehicle: continue
            ownership = _clean(row.get(m.get("Own/Outside Vehicle", ""), ""))
            if "outside" in ownership.lower(): ownership = "Outside Vehicle"
            elif "own" in ownership.lower(): ownership = "Own Vehicle"
            records.append({"Vehicle No.": vehicle, "Last 4 Digits": last_four(vehicle),
                            "Vehicle Type": normalize_vehicle_type(row.get(m.get("Vehicle Type", ""), "")),
                            "Ownership Type": ownership, "Transporter Name": _clean(row.get(m.get("Transporter Name", ""), "")),
                            "Vehicle Status": "Active", "Notes": ""})
    raw = pd.DataFrame(records)
    conflicts = []
    output = []
    for vehicle, group in raw.groupby("Vehicle No.", sort=True):
        base = group.iloc[0].to_dict()
        for col in ("Vehicle Type", "Ownership Type", "Transporter Name"):
            vals = sorted({v for v in group[col].astype(str) if v})
            if len(vals) > 1:
                conflicts.append({"Vehicle No.": vehicle, "Field": col, "Values": " | ".join(vals)})
                base[col] = ""
        output.append(base)
    return pd.DataFrame(output, columns=["Vehicle No.", "Last 4 Digits", "Vehicle Type", "Ownership Type", "Transporter Name", "Vehicle Status", "Notes"]), pd.DataFrame(conflicts)


def _company_code(name, used):
    words = re.findall(r"[A-Za-z0-9]+", name.upper())
    base = ("".join(w[0] for w in words) if len(words) > 1 else (words[0][:8] if words else "COMPANY"))
    code, n = base, 2
    while code in used: code, n = f"{base}{n}", n + 1
    used.add(code); return code


def build_company_master(dtrs):
    pairs = set()
    for df in dtrs:
        m = resolve_columns(df.columns, DTR_ALIASES)
        for _, row in df.iterrows():
            company, branch = _clean(row.get(m.get("Compnay Name", ""), "")), _clean(row.get(m.get("Branch", ""), ""))
            if company or branch: pairs.add((company, branch))
    used, rows = set(), []
    company_codes = {}
    for company, branch in sorted(pairs):
        if company not in company_codes: company_codes[company] = _company_code(company, used)
        rows.append({"Company Code": company_codes[company], "Company Name": company, "Branch": branch, "Active Status": "Active", "Notes": ""})
    return pd.DataFrame(rows)


def build_beneficiary_master(consolidated):
    m = resolve_columns(consolidated.columns, CONSOLIDATED_ALIASES)
    if "Beneficiary Account No" not in m or "Beneficiary Name" not in m:
        raise ValueError("Beneficiary account/name columns not found")
    pairs = set()
    for _, row in consolidated.iterrows():
        account = normalize_account(row[m["Beneficiary Account No"]]); name = _clean(row[m["Beneficiary Name"]])
        if account or name: pairs.add((account, name))
    rows = [{"Beneficiary Account No.": a, "Beneficiary Name": n, "Beneficiary Type": "", "Transporter Name": "",
             "Linked Vehicle No.": "", "Active Status": "Active", "Notes": ""} for a, n in sorted(pairs)]
    master = pd.DataFrame(rows)
    conflicts = []
    for account, g in master.groupby("Beneficiary Account No."):
        names = sorted(set(g["Beneficiary Name"]))
        if account and len(names) > 1: conflicts.append({"Conflict Type": "One account, multiple names", "Masked Value": "****" + account[-4:], "Count": len(names)})
    for name, g in master.groupby("Beneficiary Name"):
        accounts = sorted(set(g["Beneficiary Account No."]))
        if name and len(accounts) > 1: conflicts.append({"Conflict Type": "One name, multiple accounts", "Masked Value": name[:2] + "***", "Count": len(accounts)})
    return master, pd.DataFrame(conflicts)


def build_all(dtr_paths, consolidated_path, masters_dir, validation_dir):
    masters_dir, validation_dir = Path(masters_dir), Path(validation_dir)
    masters_dir.mkdir(parents=True, exist_ok=True); validation_dir.mkdir(parents=True, exist_ok=True)
    dtrs = [read_table(p, ["Sr No.", "Branch", "Compnay Name", "Vehicle No."])[0] for p in dtr_paths]
    consolidated = read_table(consolidated_path, ["Remark", "Beneficiary Name", "Beneficiary Account No"])[0]
    vehicles, vehicle_conflicts = build_vehicle_master(dtrs)
    companies = build_company_master(dtrs)
    beneficiaries, beneficiary_conflicts = build_beneficiary_master(consolidated)
    vehicles.to_excel(masters_dir / "vehicle_master.xlsx", index=False)
    companies.to_excel(masters_dir / "company_branch_master.xlsx", index=False)
    beneficiaries.to_excel(masters_dir / "beneficiary_transporter_master.xlsx", index=False)
    vehicle_conflicts.to_excel(validation_dir / "vehicle_conflicts.xlsx", index=False)
    beneficiary_conflicts.to_excel(validation_dir / "beneficiary_conflicts.xlsx", index=False)
    return {"vehicles": len(vehicles), "companies": len(companies), "beneficiaries": len(beneficiaries),
            "vehicle_conflicts": len(vehicle_conflicts), "beneficiary_conflicts": len(beneficiary_conflicts)}

