# Project Oneshot

Project Oneshot is a transaction-entry and DTR reporting app for Billtee. An operator reads each WhatsApp proof, enters the trip and payment details, attaches the source image, and saves it under a unique Request Number. Saved requests can be searched, verified, and exported in the existing 22-column DTR workbook format for any date range.

Each request can be marked `DTR`, `RTGS`, or `Both`. The Reports tab generates either the existing 22-column DTR or the exact 28-column RTGS/consolidated workbook for the selected date range. Existing records created before RTGS support are retained as DTR records automatically.

Financial entries are mapped into the appropriate DTR field from Expense Type and Payment Mode. Always preview the generated table before operational use.

Beneficiary Name always comes directly from the uploaded consolidated report; there is no fixed beneficiary dependency in the web app. DTR Date always comes from the remark and never falls back to `Pymt_Date`. Supported date forms include `30 07 2026`, `30/07/2026`, and `30.07.26`; date ranges use the ending date.

For best results, use this remark format:

```text
9818 | SG | Talegaon to Bhiwandi | 10MT | 30 07 2026 | INV 12345 | TA
```

The application uses a non-sensitive, derived historical lookup to suggest company and branch only for repeated patterns with at least 90% agreement. Suggestions remain editable; inconsistent or unseen routes stay blank.

## Quick start on macOS

```bash
cd /Users/sidhvedpillai/Documents/Project-Oneshot
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env                 # only if .env does not already exist
python scripts/build_initial_masters.py
python -m pytest
python -m streamlit run app.py
```

Open `http://localhost:8501` if the browser does not open automatically. Stop the app by pressing `Control-C` in Terminal.

Gemini is optional. To enable its safe fallback, edit the local `.env` and set `GEMINI_API_KEY=...`. The app sends only remark text, never complete payment rows or bank details. It continues to work when the key is absent or the service fails.

## Persistent storage

Local development uses `data/project_oneshot.db` (SQLite), which survives local app restarts. Streamlit Community Cloud's filesystem is temporary, so production must use hosted PostgreSQL. Create a PostgreSQL database (for example Neon or Supabase) and add this in the app's Streamlit Secrets:

```toml
DATABASE_URL = "postgresql://USER:PASSWORD@HOST/DATABASE?sslmode=require"
```

Do not put the database URL in Git. On startup the app creates its table automatically. Images are stored in the database along with each request, with an 8 MB per-file limit. For larger long-term volumes, move attachments to private object storage and retain only their object keys in PostgreSQL.

The screens default to the current month, giving the appearance of a fresh monthly register without deleting history. Data Management can archive older entries; archiving is reversible at the database level and does not delete records.

## Updating master files

Replace the private reference workbooks in `reference_files/` (keep the expected DTR/consolidated naming), then run:

```bash
source .venv/bin/activate
python scripts/build_initial_masters.py
```

Resolve reported conflicts manually in the local master workbooks; duplicate four-digit vehicle suffixes require manual selection during review.

## Project folders

- `src/` contains parsing, matching, validation, generation, and export logic.
- `scripts/` contains the master builder.
- `tests/` uses synthetic, non-private examples.
- `docs/` contains the masked reference inspection report.
- `data/lookups/` contains non-sensitive historical suggestion statistics.
- `data/masters/` and `data/validation/` contain private generated workbooks used by offline preparation tools.
- `data/uploads/` and `data/exports/` are local working folders.
- `reference_files/` contains the original private reports and is never modified.

Never commit `.env`, `reference_files/`, generated masters (especially beneficiary banking data), uploads, or exports. `.gitignore` excludes them.

## Troubleshooting

- **Command not found / wrong Python:** activate `.venv`; `python --version` should show 3.12.
- **Missing module:** run `python -m pip install -r requirements.txt` while the venv is active.
- **Masters unavailable:** run the builder and confirm all three reference workbooks are under the project.
- **Workbook rejected:** ensure it is `.xlsx` and contains a Remark/Remarks and Beneficiary Name column.
- **Rows missing from draft:** inspect the excluded and ambiguous sections; ambiguous entries intentionally require review.
- **Gemini unavailable:** the deterministic workflow still works; leave the key blank or retry later.

## Private GitHub and Streamlit deployment readiness

Do not make this repository public: the application processes operational and banking-related data. Create a **private** GitHub repository, review `git status`, then add and push only the source files that are not ignored. Never force-add `.env`, `reference_files/`, `data/masters/`, uploads, exports, or validation reports.

For Streamlit Community Cloud, connect only the private repository and configure `DATABASE_URL` in encrypted Secrets. Confirm the deployment's current viewer-access controls are suitable for the authorized office team before entering operational or banking information.

Private master workbooks are intentionally ignored by Git, so they will not exist in a fresh cloud checkout. The app operates without them and leaves unresolved master-dependent fields editable. Once the verified masters are ready, add them through a secure deployment data-storage design rather than committing beneficiary bank details to Git. For routine sensitive office use, the recommended Phase 1 setup remains the local app on an office-controlled computer or a separately secured private hosting environment.

Before any deployment:

1. Run all tests and test the local review/export workflow.
2. Confirm the GitHub repository is private and ignored files are absent.
3. Confirm only authorized viewers can open the deployed app.
4. Use non-sensitive test data first and confirm missing master-dependent fields remain editable.
5. Verify exported files and uploaded reports are handled under the company's retention policy.
