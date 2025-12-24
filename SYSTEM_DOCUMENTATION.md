# CMS Explorer - System Documentation

**Last Updated:** 2025-01-XX  
**Version:** 2.0 (Redesigned for Medical Device Companies)

## Overview

The CMS Explorer is a Flask-based web application designed specifically for medical device companies to identify target customer lists by exploring U.S. Medicare billing data. The system helps companies find both physicians and hospitals who are likely to use their products based on procedure code usage patterns.

## Key Features (v2.0)

### 1. Dual Search Modes
- **Doctor Search**: Find physicians by procedure codes (existing, improved)
- **Hospital Search**: Find hospitals by procedure codes (**NEW**)

### 2. Hospital-Level Analytics (**NEW**)
- Total procedures per hospital for selected codes
- Total Medicare payments per hospital
- Number of physicians performing procedures at each hospital
- Average procedures per physician
- Code breakdown showing distribution

### 3. HCPCS Code Intelligence (**NEW**)
- Code descriptions (long and short)
- Code metadata (pricing indicators, coverage codes, BETOS classification)
- Code search and autocomplete
- Integration with HCPCS 2026 data

### 4. Medical Device Company Workflow
- Device category management
- Code classification system
- Target customer identification
- Export capabilities

## Architecture

### Application Structure

```
CMS/
├── app.py                          # Flask application entry point
├── cms_app/                        # Main application package
│   ├── __init__.py                # Flask app factory
│   ├── config.py                  # Configuration
│   ├── views.py                   # Flask routes (blueprint)
│   ├── cms_query.py               # Doctor query logic
│   ├── hospital_analytics.py      # Hospital analytics engine (NEW)
│   ├── hcpcs_lookup.py            # HCPCS code lookup system (NEW)
│   ├── code_classification.py     # Code classification system
│   ├── data_loading.py            # Data loading utilities
│   ├── cms_columns.py             # Column detection helpers
│   ├── filters.py                 # Filtering functions
│   ├── puf_utils.py               # Utility functions
│   ├── logger.py                  # Logging configuration
│   ├── templates/
│   │   ├── layout.html            # Base template
│   │   ├── cms_explorer.html      # Main explorer page
│   │   └── code_classification.html # Code classification interface
│   └── static/
│       └── css/
│           └── cms.css            # Styles
├── Doctors_08_2025/                # Physician data (read-only)
├── hospitals_08_2025/              # Hospital data (read-only)
├── HCPCS/                          # HCPCS 2026 data files (NEW)
│   ├── HCPC2026_JAN_ANWEB_12082025.txt
│   ├── HCPC2026_recordlayout.txt
│   └── proc_notes_JAN2026.txt
├── physHCPCS.csv                   # Physician HCPCS/CPT utilization data
└── code_classifications.json       # Saved code classifications
```

### Key Components

#### 1. Hospital Analytics Engine (`cms_app/hospital_analytics.py`)
**NEW** - Provides hospital-level usage statistics:

- **`hospitals_by_codes()`**: Main function that:
  - Accepts: codes, states (optional), min_procedures (optional), max_rows
  - Aggregates physician billing data by hospital
  - Calculates hospital-level statistics:
    - Total procedures
    - Total payments
    - Number of physicians
    - Average procedures per physician
    - Code breakdown
  - Returns DataFrame with hospital statistics

- **`get_hospital_physicians()`**: Get physicians at a specific hospital
  - Filtered by codes if provided
  - Shows procedure volumes per physician

#### 2. HCPCS Code Lookup System (`cms_app/hcpcs_lookup.py`)
**NEW** - Provides code intelligence:

- **`HCPCSLookup`**: Main class for code lookups
  - Parses fixed-width HCPCS 2026 data file
  - Provides code descriptions and metadata
  - Search functionality
  - Autocomplete support

- **`HCPCSCode`**: Dataclass representing a code with:
  - Code and modifier
  - Long and short descriptions
  - Pricing indicators
  - Coverage codes
  - BETOS classification
  - Type of service
  - Effective/termination dates

#### 3. Enhanced Explorer (`cms_app/views.py`)
Updated to support both doctor and hospital searches:

- **Doctor Search Mode** (existing, improved):
  - Search physicians by codes
  - Filter by state, minimum procedures
  - Device category support
  - Hospital affiliations attached

- **Hospital Search Mode** (NEW):
  - Search hospitals by codes
  - Filter by state, minimum procedures
  - Shows hospital-level statistics
  - Code breakdown per hospital

#### 4. Core Query Logic (`cms_app/cms_query.py`)
Existing doctor query system (unchanged, but now complemented by hospital analytics).

## Data Flow

### Hospital Search Flow

1. **User Input** → Form submission with codes, states, min_procedures, dataset="Hospitals"
2. **Route Handler** → Parses form, validates codes
3. **Hospital Analytics** (`hospitals_by_codes()`) →
   - Loads physician billing data (`physHCPCS.csv`)
   - Filters by codes and states
   - Aggregates by NPI (sums services, payments)
   - Joins with facility affiliations (NPI → Facility ID)
   - Joins with hospital metadata (Facility ID → Hospital info)
   - Aggregates by hospital (sums across all physicians)
   - Calculates statistics (num_physicians, avg_procedures, etc.)
   - Sorts by total procedures, limits to max_rows
4. **Template Rendering** → Formats results table
5. **User View** → Table with hospital statistics

### Doctor Search Flow (Unchanged)

1. **User Input** → Form submission with codes, states, min_services
2. **Route Handler** → Parses form, validates codes
3. **Query Function** (`doctors_by_codes()`) →
   - Streams `physHCPCS.csv` in chunks
   - Filters by codes/states
   - Aggregates by NPI
   - Attaches hospital affiliations
   - Returns results
4. **Template Rendering** → Formats results table
5. **User View** → Table with doctor information

## Data Sources

### Primary Data Files

1. **`physHCPCS.csv`** (root level)
   - Physician & Other Supplier PUF
   - Contains: NPI, HCPCS/CPT codes, services, payments, provider info
   - Used by: `doctors_by_codes()` and `hospitals_by_codes()`

2. **`Doctors_08_2025/Facility_Affiliation.csv`**
   - Maps NPIs to Facility Certification Numbers
   - Used by: `attach_hospital_affiliations()` and `hospitals_by_codes()`

3. **`hospitals_08_2025/Hospital_General_Information.csv`**
   - Hospital metadata (name, city, state, facility ID)
   - Used by: `attach_hospital_affiliations()` and `hospitals_by_codes()`

4. **`HCPCS/HCPC2026_JAN_ANWEB_12082025.txt`** (NEW)
   - HCPCS 2026 code database (fixed-width format)
   - Contains: codes, descriptions, metadata
   - Used by: `HCPCSLookup` class

5. **`code_classifications.json`**
   - Device category definitions and code mappings
   - Created and managed by users

## Usage Examples

### Example 1: Find Target Hospitals
```
Dataset: Hospitals
Codes: 62270, 62272
States: CA, OR
Minimum procedures: 100
```
Returns: Hospitals in CA/OR with at least 100 procedures for codes 62270/62272, ranked by volume

### Example 2: Find Target Physicians
```
Dataset: Doctors (by CPT/HCPCS code)
Codes: L8679
States: (empty)
Minimum procedures: 25
```
Returns: All physicians billing code L8679 with at least 25 procedures, ranked by volume

### Example 3: Hospital vs Doctor Comparison
1. Search hospitals for codes → Identify high-volume hospitals
2. Search doctors for same codes → Identify high-volume physicians
3. Cross-reference to find physicians at target hospitals

## Performance Considerations

### Caching
- Hospital metadata: `@lru_cache(maxsize=2)`
- Facility affiliations: `@lru_cache(maxsize=2)`
- Physician PUF header: `@lru_cache(maxsize=4)`
- HCPCS lookup: Loaded once, cached in memory

### Chunked Reading
- `physHCPCS.csv` read in 250k row chunks
- Prevents memory issues with large files
- Aggregation happens incrementally

### Memory Efficiency
- Only loads necessary columns (via `usecols`)
- Streams CSV export in 5k row chunks
- Hospital aggregation done in-memory (efficient for typical result sizes)

## Change Log

### 2025-01-XX - Version 2.0 - Complete Redesign
- **Added**: Hospital-level analytics and search
- **Added**: HCPCS code lookup system with 2026 data
- **Added**: Hospital search mode in explorer
- **Fixed**: Template bug causing search to fail
- **Improved**: Enhanced search interface with dual modes
- **Improved**: Better error messages and validation
- **Improved**: Export functionality for hospital results

### 2025-01-XX - Version 1.1 - Medical Device Company Features
- Code classification system
- Device category management
- Enhanced validation and logging

### 2025-01-XX - Version 1.0 - Initial Release
- Core search functionality
- Hospital affiliation joining
- CSV export

---

**Note:** This documentation is maintained alongside code changes. Each significant code update should include a corresponding documentation update.
