import json
from pathlib import Path
import sys
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.column_mapping import DTR_ALIASES, resolve_columns
from src.config import ROOT
from src.excel_reader import read_table
from src.historical_suggester import normalize_location


def dominant(group, value_columns, minimum, threshold):
    counts = group.groupby(value_columns, dropna=False).size().sort_values(ascending=False)
    if counts.empty: return None
    values, count = counts.index[0], int(counts.iloc[0])
    total = int(counts.sum())
    if total < minimum or count / total < threshold: return None
    if not isinstance(values, tuple): values = (values,)
    return values, count, total


frames = []
for path in sorted(ROOT.rglob("DTR - ALL BRANCH - *.xlsx")):
    df, _ = read_table(path, ["Branch", "Compnay Name", "From", "To"])
    mapping = resolve_columns(df.columns, DTR_ALIASES)
    frame = pd.DataFrame({name: df[mapping[name]].fillna("").astype(str).str.strip()
                          for name in ("Branch", "Compnay Name", "From", "To")})
    frames.append(frame[(frame["From"] != "") & (frame["To"] != "") & (frame["Compnay Name"] != "")])

history = pd.concat(frames, ignore_index=True)
history["route"] = history.apply(lambda r: f"{normalize_location(r['From'])}|{normalize_location(r['To'])}", axis=1)
routes, route_companies = {}, {}
for route, group in history.groupby("route"):
    choice = dominant(group, ["Compnay Name", "Branch"], minimum=3, threshold=0.90)
    if choice:
        (company, branch), count, total = choice
        routes[route] = {"company": company, "branch": branch, "observations": total, "matching": count}
for (route, company), group in history.groupby(["route", history["Compnay Name"].str.casefold()]):
    choice = dominant(group, ["Branch"], minimum=2, threshold=0.90)
    if choice:
        (branch,), count, total = choice
        route_companies[f"{route}|{company}"] = {"branch": branch, "observations": total, "matching": count}

target = ROOT / "data" / "lookups" / "historical_company_branch.json"
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text(json.dumps({"routes": routes, "route_companies": route_companies}, indent=2, ensure_ascii=False), encoding="utf-8")
print({"route_suggestions": len(routes), "route_company_branches": len(route_companies), "output": str(target)})
