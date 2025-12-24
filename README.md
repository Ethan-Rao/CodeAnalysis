# CMS Explorer - Medical Device Customer Intelligence Platform

A comprehensive web application designed specifically for **medical device companies** to identify and target high-volume physicians and hospitals using Medicare billing data. The platform seamlessly integrates multiple CMS datasets to provide actionable customer intelligence for sales and marketing teams.

## Business Value

**For Medical Device Companies:**
- **Identify Target Customers**: Find physicians and hospitals with high procedure volumes for your device codes
- **Market Intelligence**: Understand procedure distribution across geographic regions
- **Sales Targeting**: Prioritize prospects based on actual Medicare billing data
- **Territory Planning**: Analyze market opportunities by state and region
- **Competitive Analysis**: Track procedure volumes and payment trends

## Key Features

### 🔍 Dual Search Modes
- **Physician Search**: Find doctors by procedure codes with hospital affiliations
- **Hospital Search**: Find hospitals by procedure codes with usage statistics (**NEW in v2.0**)

### 🏥 Hospital-Level Analytics (**NEW in v2.0**)
- Total procedures per hospital for selected codes
- Total Medicare payments per hospital
- Number of physicians performing procedures at each hospital
- Average procedures per physician
- Code breakdown showing procedure distribution

### 📋 HCPCS Code Intelligence (**NEW in v2.0**)
- **Code Lookup Interface**: Search codes by description or browse popular codes
- **Code Descriptions**: Automatic display of code descriptions in search results
- **Code Metadata**: Access to pricing indicators, coverage codes, and classifications
- **Seamless Integration**: Code information appears automatically - users don't need to know about multiple datasets

### 🏷️ Device Category Management
- Organize codes into custom device categories
- Quick category-based searches
- Manage code mappings for your product portfolio

### 📊 Advanced Filtering
- Filter by state(s) for geographic targeting
- Minimum procedure thresholds to focus on high-volume providers
- Combined doctor and hospital views

### 📥 Export Capabilities
- Full CSV export of search results
- Includes all relevant data for CRM import
- Streamed for large result sets

## Quick Start

### Prerequisites
- Python 3.8 or higher
- CMS Medicare data files (see Data Requirements)

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

Then visit: **http://127.0.0.1:5000/cms/explorer**

**Or use the PowerShell script:**
```powershell
.\run_local.ps1
```

## Data Requirements

The application integrates data from multiple CMS sources (seamlessly handled - users don't need to manage this):

### Required Files

1. **`physHCPCS.csv`** (root level)
   - Physician & Other Supplier PUF (Public Use File)
   - Contains HCPCS/CPT billing data with procedure volumes

2. **`Doctors_08_2025/Facility_Affiliation.csv`**
   - Maps physicians (NPIs) to hospitals (Facility IDs)
   - Enables hospital affiliation display

3. **`hospitals_08_2025/Hospital_General_Information.csv`**
   - Hospital metadata (name, city, state, facility ID)
   - Used for hospital information display

4. **`HCPCS/HCPC2026_JAN_ANWEB_12082025.txt`** (NEW in v2.0)
   - HCPCS 2026 code database
   - Provides code descriptions and metadata
   - Automatically loaded and integrated

### Data Sources

These files are downloaded from CMS.gov:
- [Physician & Other Practitioners - by Provider and Service](https://www.cms.gov/data-research/statistics-trends-and-reports/medicare-provider-utilization-and-payment-data/physician-and-other-supplier)
- [Doctors & Clinicians Public Use Files](https://www.cms.gov/data-research/statistics-trends-and-reports/medicare-provider-utilization-and-payment-data/doctors-and-clinicians)
- [Hospital General Information](https://www.cms.gov/data-research/statistics-trends-and-reports/medicare-provider-utilization-and-payment-data/hospital)
- [HCPCS Code Files](https://www.cms.gov/medicare/coding-billing/medicare-c coding-hcpcs-release-code-sets)

**Note:** Data folders are gitignored due to size. For deployment, ensure data files are available in the runtime environment.

## Usage Guide

### Workflow 1: Find Target Hospitals

1. Navigate to **Explorer**
2. Select **"Hospitals (by CPT/HCPCS code)"** from Dataset dropdown
3. Enter procedure codes (e.g., `62270, 62272`) or select a device category
4. Optionally filter by state(s) and set minimum procedures
5. Click **"Run"**
6. Review results showing:
   - Hospitals ranked by procedure volume
   - Total procedures and payments per hospital
   - Number of physicians at each hospital
   - Code breakdown
7. Click **"Download CSV"** to export for sales team

### Workflow 2: Find Target Physicians

1. Navigate to **Explorer**
2. Select **"Doctors (by CPT/HCPCS code)"** from Dataset dropdown
3. Enter procedure codes or select a device category
4. Apply filters as needed
5. Click **"Run"**
6. Review results showing:
   - Physicians ranked by procedure volume
   - Hospital affiliations
   - Procedure volumes and payments
   - Code breakdown
7. Export results for CRM import

### Workflow 3: Research Codes

1. Navigate to **Code Lookup**
2. Search by description (e.g., "spinal fusion") or enter a specific code
3. Review code descriptions and metadata
4. Click **"Search Usage"** to find providers using that code
5. Add relevant codes to device categories for future use

### Workflow 4: Organize by Device Category

1. Navigate to **Code Classification**
2. Create categories for your product lines (e.g., "Spinal Fusion Devices")
3. Add relevant codes to each category
4. Use categories in Explorer for quick searches

## Understanding Results

### Doctor Results
- **Doctor name**: Full name (Last, First)
- **NPI**: National Provider Identifier
- **Specialty**: Provider specialty
- **City, State**: Provider location
- **Primary hospital**: Main affiliated hospital
- **Number of procedures**: Total procedures for selected codes
- **Total Medicare payments**: Total payments for selected codes
- **Code breakdown**: Distribution of procedures across codes

### Hospital Results
- **Facility ID**: Hospital certification number
- **Hospital Name**: Hospital name
- **City, State**: Hospital location
- **Total Procedures**: Total procedures for selected codes
- **Total Payments**: Total Medicare payments
- **Number of Physicians**: Count of physicians performing procedures
- **Avg Procedures/Physician**: Average volume per physician
- **Code Breakdown**: Distribution of procedures across codes

### Code Information
When you search, code descriptions automatically appear above results, showing:
- Code number
- Short description
- Full description (on hover/click)

## Project Structure

```
CMS/
├── app.py                          # Flask application entry point
├── cms_app/                        # Main application package
│   ├── views.py                   # Routes and request handling
│   ├── cms_query.py               # Doctor query logic
│   ├── hospital_analytics.py      # Hospital analytics engine (NEW)
│   ├── hcpcs_lookup.py            # HCPCS code lookup system (NEW)
│   ├── code_classification.py     # Device category management
│   ├── data_loading.py            # Data loading utilities
│   ├── cms_columns.py             # Column detection helpers
│   ├── filters.py                 # Filtering functions
│   ├── logger.py                  # Logging configuration
│   ├── templates/
│   │   ├── cms_explorer.html     # Main search interface
│   │   ├── code_lookup.html      # Code lookup interface (NEW)
│   │   └── code_classification.html # Category management
│   └── static/
│       └── css/
│           └── cms.css            # Styles
├── Doctors_08_2025/               # Physician data (read-only)
├── hospitals_08_2025/             # Hospital data (read-only)
├── HCPCS/                         # HCPCS 2026 data files (NEW)
├── physHCPCS.csv                  # Physician utilization data
└── code_classifications.json       # Device categories (auto-created)
```

See `SYSTEM_DOCUMENTATION.md` for detailed technical architecture.

## Development

### Running in Development Mode

```bash
python app.py
# Flask runs with debug=True by default
# Visit http://127.0.0.1:5000/cms/explorer
```

### Testing

Test with common medical device codes:
- Spinal procedures: `62270`, `62272`
- Orthopedic implants: `27215`, `27216`, `27217`
- Cardiac devices: `L8679`, `A4593`
- Imaging: `77080`

### Adding Features

1. New query functions → `cms_app/cms_query.py` or `cms_app/hospital_analytics.py`
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
- Verify codes are correct (use Code Lookup to verify)
- Try removing state filters
- Check that `physHCPCS.csv` contains the codes you're searching
- Ensure minimum procedures threshold isn't too high

### Memory issues
- The app uses chunked reading for large files
- If issues persist, reduce `chunksize` in query modules

### Code descriptions not showing
- Ensure `HCPCS/HCPC2026_JAN_ANWEB_12082025.txt` exists
- Check file permissions
- System will gracefully degrade if HCPCS file is missing

## Version History

See `CHANGELOG.md` for detailed version history.

### Current Version: 2.0

**Major Features:**
- ✅ Hospital-level analytics and search
- ✅ HCPCS code lookup and descriptions
- ✅ Seamless multi-dataset integration
- ✅ Enhanced user experience for medical device companies

## License

[Add your license here]

## Support

For technical documentation, see `SYSTEM_DOCUMENTATION.md`.  
For version history, see `CHANGELOG.md`.

---

**Built for medical device companies seeking data-driven customer intelligence.**
