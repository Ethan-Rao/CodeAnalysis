# CMS Explorer

A Flask web application for exploring U.S. Medicare billing data. Find physicians who bill specific HCPCS/CPT procedure codes, along with their hospital affiliations. **Designed for medical device companies to identify target customer lists.**

## Features

- **Code-Based Search**: Search by one or more HCPCS/CPT codes (e.g., 62270, L8679)
- **Device Category Search** (NEW): Organize codes into device categories for quick searching
- **State Filtering**: Optional filter by state(s) (e.g., CA, OR)
- **Volume Filtering**: Optional minimum procedures threshold
- **Hospital Affiliations**: Automatically shows which hospitals each doctor is affiliated with
- **Code Classification Management** (NEW): Create and manage device categories with associated codes
- **CSV Export**: Download full results as CSV

## Quick Start

### Prerequisites
- Python 3.8+
- CMS data files (see Data Requirements below)

### Installation

```bash
# Create virtual environment
python -m venv .venv

# Activate (Windows)
.\.venv\Scripts\activate

# Activate (Mac/Linux)
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Run Locally

```bash
python app.py
```

Then visit: http://127.0.0.1:5000/cms/explorer

**Or use the PowerShell script:**
```powershell
.\run_local.ps1
```

## Data Requirements

The application expects the following data files (read-only):

### Required Files

1. **`physHCPCS.csv`** (root level)
   - Physician & Other Supplier PUF (Public Use File)
   - Contains HCPCS/CPT billing data

2. **`Doctors_08_2025/Facility_Affiliation.csv`**
   - Maps NPIs to Facility Certification Numbers
   - Used for hospital affiliation lookup

3. **`hospitals_08_2025/Hospital_General_Information.csv`**
   - Hospital metadata (name, city, state)
   - Used for hospital affiliation details

### Data Sources

These files are typically downloaded from CMS.gov:
- [Physician & Other Practitioners - by Provider and Service](https://www.cms.gov/data-research/statistics-trends-and-reports/medicare-provider-utilization-and-payment-data/physician-and-other-supplier)
- [Doctors & Clinicians Public Use Files](https://www.cms.gov/data-research/statistics-trends-and-reports/medicare-provider-utilization-and-payment-data/doctors-and-clinicians)
- [Hospital General Information](https://www.cms.gov/data-research/statistics-trends-and-reports/medicare-provider-utilization-and-payment-data/hospital)

**Note:** These data folders are gitignored by default due to size. For deployment, ensure data files are available in the runtime environment.

## Usage

### Basic Search

1. Enter one or more CPT/HCPCS codes (comma-separated)
   - Example: `62270, 62272, L8679`
2. Optionally enter states (comma-separated)
   - Example: `CA, OR`
3. Optionally set minimum procedures threshold
   - Example: `25` (filters out doctors with fewer than 25 procedures)
4. Click "Run"

### Device Category Search (NEW)

1. Navigate to **Code Classification** page
2. Create a new device category (e.g., "Spinal Fusion Devices")
3. Add relevant codes to the category
4. In the Explorer, select the category from the dropdown
5. Codes are automatically populated
6. Click "Run" to search

### Understanding Results

- **Doctor name**: Full name (Last, First)
- **NPI**: National Provider Identifier
- **Specialty**: Provider specialty
- **City, State**: Provider location
- **Primary hospital**: Main affiliated hospital
- **Number of procedures**: Total procedures for selected codes
- **Total Medicare payments**: Total payments for selected codes
- **Code breakdown**: Distribution of procedures across codes

### Export Results

Click "Download CSV" to export full results (not limited to the 200-row preview).

## Project Structure

```
CMS/
├── app.py                    # Flask entry point
├── cms_app/                  # Application package
│   ├── views.py             # Routes
│   ├── cms_query.py         # Core query logic
│   ├── code_classification.py # Code classification system (NEW)
│   ├── data_loading.py      # Data loading utilities
│   ├── cms_columns.py      # Column detection
│   ├── logger.py            # Logging configuration (NEW)
│   └── templates/           # HTML templates
├── Doctors_08_2025/         # Physician data (read-only)
├── hospitals_08_2025/       # Hospital data (read-only)
├── physHCPCS.csv            # Physician utilization data
└── code_classifications.json # Device categories (auto-created)
```

See `SYSTEM_DOCUMENTATION.md` for detailed architecture documentation.

## Medical Device Company Workflow

### Step 1: Organize Codes by Device Category

1. Go to **Code Classification** page
2. Create categories for your device types:
   - Example: "Spinal Fusion Devices"
   - Example: "Cardiac Implants"
   - Example: "Orthopedic Implants"
3. Add relevant HCPCS/CPT codes to each category

### Step 2: Find Target Customers

1. Go to **Explorer** page
2. Select a device category (or enter codes manually)
3. Optionally filter by state(s)
4. Set minimum procedures threshold if needed
5. Click "Run"
6. Review results showing:
   - High-volume physicians for your device codes
   - Their hospital affiliations
   - Procedure volumes and Medicare payments

### Step 3: Export and Analyze

1. Click "Download CSV" to export full results
2. Use the data for:
   - Sales targeting
   - Market analysis
   - Territory planning
   - Customer identification

## Development

### Running in Development Mode

```bash
python app.py
# Flask runs with debug=True by default
```

### Testing

Test queries using codes from example scripts:
- `CPTBONESORWA.py` - Example: code 77080
- `CPTNUERO.py` - Examples: codes 61889, L8679, A4593

### Adding Features

1. New query functions → `cms_app/cms_query.py`
2. New routes → `cms_app/views.py`
3. New templates → `cms_app/templates/`
4. New column types → `cms_app/cms_columns.py`

## Deployment

### Using Gunicorn

```bash
gunicorn "app:app"
```

### Environment Variables (Future)

- `CMS_DATA_DIR`: Override data directory path
- `LOG_LEVEL`: Set logging level (INFO, DEBUG, etc.)
- `MAX_TABLE_ROWS`: Override preview row limit

## Troubleshooting

### "Could not detect [column] column"
- Check that data files match expected CMS format
- Column detection is flexible but may need updates for new formats

### No results returned
- Verify codes are correct (check for typos)
- Try removing state filters
- Check that `physHCPCS.csv` contains the codes you're searching

### Memory issues
- The app uses chunked reading for large files
- If issues persist, reduce `chunksize` in `cms_query.py`

### Code classification not saving
- Check file permissions for `code_classifications.json`
- Ensure the application has write access to the project root

## What's New in v1.1

- ✅ **Code Classification System**: Organize codes into device categories
- ✅ **Device Category Management**: Create, edit, and delete categories via web UI
- ✅ **Category-Based Search**: Select categories in Explorer to auto-populate codes
- ✅ **Enhanced Validation**: Better error messages for invalid inputs
- ✅ **Logging System**: Improved debugging and error tracking
- ✅ **Comprehensive Documentation**: System documentation and user guides

## License

[Add your license here]

## Support

For detailed system information, see `SYSTEM_DOCUMENTATION.md`.
