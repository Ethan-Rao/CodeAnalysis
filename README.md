# CMS Explorer (Flask)

A standalone Flask web app for exploring CMS **Doctors & Clinicians** and **Hospitals** downloads.

## What it does (v1)

- UI at `/cms/explorer`
  - Dataset: Doctors or Hospitals
  - States: comma-separated (e.g. `CA, OR`)
  - Doctors only: procedure category substrings (comma-separated)
- Shows a preview table (first 200 rows)
- Exports the full filtered results as CSV via `/cms/export`

## Data folders (read-only)

This repo expects raw CMS downloads in:

- `Doctors_08_2025/`
  - `DAC_NationalDownloadableFile.csv`
  - `Utilization.csv`
  - `Facility_Affiliation.csv` (optional for v1)
- `hospitals_08_2025/` (or `Hospitals_08_2025/`)
  - `Hospital_General_Information.csv`

No CSVs are modified in-place.

Note: the raw CMS download folders are intentionally gitignored (they can be very large). For deployment, you’ll need to provide these files to the runtime environment (or switch to a future iteration that loads from object storage / a database).

## Setup

```bash
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

## Run locally

```bash
python app.py
```

Then visit: http://127.0.0.1:5000/cms/explorer

### Minimal manual (Windows)

- Run `./run_local.ps1` (creates `.venv`, installs deps, starts the server)

## Deploy (DigitalOcean App Platform pattern)

- Gunicorn entrypoint: `gunicorn "app:app"`
- Ensure the repo root is this `CMS` folder.

Important: the raw CMS download folders are gitignored by default because they’re large. For a hosted deployment you’ll need to make the data available to the app environment (e.g., via a separate download step in the build/start command, object storage, or a database in a future iteration).

## Dev scripts

- `python dev_scripts/check_doctors_sample.py`
- `python dev_scripts/check_hospitals_sample.py`
