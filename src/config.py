from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
MASTERS = DATA / "masters"
VALIDATION = DATA / "validation"
UPLOADS = DATA / "uploads"
EXPORTS = DATA / "exports"

for folder in (MASTERS, VALIDATION, UPLOADS, EXPORTS):
    folder.mkdir(parents=True, exist_ok=True)

