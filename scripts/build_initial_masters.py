from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.config import ROOT, MASTERS, VALIDATION
from src.master_builder import build_all

files = list(ROOT.rglob("*.xlsx"))
dtrs = sorted(p for p in files if "DTR - ALL BRANCH" in p.name.upper())
consolidated = next((p for p in files if "CONSOLIDATEDREPORT" in p.name.upper()), None)
if len(dtrs) < 2 or not consolidated:
    raise SystemExit("Could not find both DTR files and the consolidated report.")
print(build_all(dtrs, consolidated, MASTERS, VALIDATION))

