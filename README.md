# Project Oneshot

Project Oneshot is a local, browser-based Phase 1 draft DTR generator for Billtee. It reads a consolidated `.xlsx` payment report, excludes clear non-trip rows, parses trip remarks, matches local master data, provides an editable review table, and exports a professionally formatted DTR workbook.

Phase 1 deliberately leaves every financial field—including Payment—blank. Missing business fields remain blank for manual review; the app never invents a company from a route. Always review the generated file once before operational use.

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
- `data/masters/` and `data/validation/` contain private generated workbooks.
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

For Streamlit Community Cloud, connect only the private repository and configure `GEMINI_API_KEY` in the deployment's encrypted secrets/settings if Gemini is required—never commit the value. Confirm the deployment's current viewer-access controls are suitable for the authorized office team before uploading any operational report.

Private master workbooks are intentionally ignored by Git, so they will not exist in a fresh cloud checkout. The app operates without them and leaves unresolved master-dependent fields editable. Once the verified masters are ready, add them through a secure deployment data-storage design rather than committing beneficiary bank details to Git. For routine sensitive office use, the recommended Phase 1 setup remains the local app on an office-controlled computer or a separately secured private hosting environment.

Before any deployment:

1. Run all tests and test the local review/export workflow.
2. Confirm the GitHub repository is private and ignored files are absent.
3. Confirm only authorized viewers can open the deployed app.
4. Use non-sensitive test data first and confirm missing master-dependent fields remain editable.
5. Verify exported files and uploaded reports are handled under the company's retention policy.
