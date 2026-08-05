# Project Oneshot

Project Oneshot is an AI-assisted logistics workflow app for Billtee. Nikhat uploads WhatsApp evidence, creates and finalizes RTGS rows, and saves a labelled request. That request enters Shyam's pending queue; he converts it into a full DTR, completes late-arriving details, and saves/downloads the operational workbook.

Missing or uncertain values remain blank and flagged for later completion in Requests. DTR requests retain the full operational field set, including LR, invoice, freight, UPI, diesel, revenue, damages and remarks. RTGS requests retain the exact 28-column consolidated-report field set. Uploaded evidence and instructions are sent to the configured Google Gemini model during extraction, so every generated row must be reviewed before saving.

The interface contains `New Entry`, `RTGS Records`, `Pending DTR updation`, `Edit DTR Report`, and `Delete Records From Memory`. RTGS and DTR records support both manual table edits and AI-assisted change instructions. Every change writes a revision snapshot.

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

Gemini is required for AI extraction. For local use, set `GEMINI_API_KEY` in `.env`; for Streamlit Cloud, set it in encrypted Secrets. Uploaded evidence may contain complete payment or banking details and is sent to the configured Gemini model, so access and retention must follow company policy.

The default extraction model is `gemini-3.6-flash`. It can be changed without a code deployment by adding `GEMINI_MODEL = "model-name"` to Streamlit Secrets. If the configured/default model returns a model-unavailable error, the app tries supported Flash fallbacks; authentication, quota and content errors are surfaced without retrying other models.

## Persistent storage

Local development uses `data/project_oneshot.db` (SQLite), which survives local app restarts. Streamlit Community Cloud's filesystem is temporary, so production must use hosted PostgreSQL. Create a PostgreSQL database (for example Neon or Supabase) and add this in the app's Streamlit Secrets:

```toml
DATABASE_URL = "postgresql://USER:PASSWORD@HOST/DATABASE?sslmode=require"
```

Do not put the database URL in Git. On startup the app creates its table automatically. Images are stored in the database along with each request, with an 8 MB per-file limit. For larger long-term volumes, move attachments to private object storage and retain only their object keys in PostgreSQL.

No record, request, attachment or revision is removed by refresh, reboot, redeployment or monthly rollover. Permanent deletion occurs only when an authorized user selects a request in `Delete Records From Memory`, types its exact label, acknowledges the warning and clicks the permanent-delete button.

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
