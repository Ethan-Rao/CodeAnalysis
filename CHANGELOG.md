# Changelog

All notable changes to the CMS Explorer project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0] - 2025-01-XX

### Major Release: Medical Device Customer Intelligence Platform

This release represents a complete redesign focused on serving medical device companies with comprehensive customer intelligence capabilities.

### Added

#### Hospital-Level Analytics
- **Hospital Search Mode**: New search mode to find hospitals by procedure codes
- **Hospital Statistics**: Comprehensive hospital-level usage statistics including:
  - Total procedures per hospital for selected codes
  - Total Medicare payments per hospital
  - Number of physicians performing procedures at each hospital
  - Average procedures per physician
  - Code breakdown showing procedure distribution
- **Hospital Ranking**: Hospitals ranked by procedure volume for easy identification of high-volume targets

#### HCPCS Code Intelligence System
- **Code Lookup Interface** (`/cms/code-lookup`): 
  - Search codes by description (e.g., "spinal fusion")
  - Browse popular medical device codes
  - View full code details including descriptions and metadata
  - Direct links to search usage for each code
- **Automatic Code Descriptions**: Code descriptions automatically displayed in search results
- **Code Metadata Access**: Integration with HCPCS 2026 data providing:
  - Long and short descriptions
  - Pricing indicators
  - Coverage codes
  - BETOS classifications
  - Type of service codes
  - Effective and termination dates
- **Seamless Integration**: Code information appears automatically - users don't need to know about multiple datasets

#### Enhanced User Experience
- **Code Information Display**: Searched codes shown with descriptions above results
- **Improved Navigation**: New "Code Lookup" menu item for easy access
- **Better Error Messages**: More helpful messages when codes aren't found
- **Professional UI**: Enhanced visual design for business users

#### Technical Improvements
- **New Module: `hospital_analytics.py`**: Dedicated hospital analytics engine
- **New Module: `hcpcs_lookup.py`**: HCPCS code lookup and search system
- **Fixed-Width Parser**: Robust parser for HCPCS 2026 fixed-width data format
- **Multi-Dataset Integration**: Seamless integration of physician, hospital, and HCPCS data

### Changed

#### Search Interface
- **Dual Search Modes**: Explorer now supports both "Doctors" and "Hospitals" search modes
- **Enhanced Results Display**: Results show code descriptions automatically
- **Improved Template**: Better formatting for hospital results vs doctor results
- **Code Lookup Integration**: Link to code lookup from search form

#### Data Integration
- **Transparent Multi-Dataset Handling**: System automatically integrates data from:
  - Physician billing data (`physHCPCS.csv`)
  - Hospital affiliations (`Facility_Affiliation.csv`)
  - Hospital metadata (`Hospital_General_Information.csv`)
  - HCPCS code database (`HCPC2026_JAN_ANWEB_12082025.txt`)
- **User Transparency**: Users see unified results without needing to understand data sources

### Fixed

- **Search Bug**: Fixed template issue preventing search results from displaying
- **Missing Code Descriptions**: Now automatically populated from HCPCS database
- **Hospital Search**: Previously showed placeholder - now fully functional
- **Export Functionality**: Updated to handle both doctor and hospital results

### Technical Details

#### New Files
- `cms_app/hospital_analytics.py` - Hospital-level analytics engine
- `cms_app/hcpcs_lookup.py` - HCPCS code lookup system
- `cms_app/templates/code_lookup.html` - Code lookup interface
- `REDESIGN_PLAN.md` - Comprehensive redesign documentation

#### Modified Files
- `cms_app/views.py` - Added hospital search, code lookup route, code description enrichment
- `cms_app/templates/cms_explorer.html` - Enhanced with code descriptions, dual search modes
- `cms_app/templates/layout.html` - Added Code Lookup navigation
- `SYSTEM_DOCUMENTATION.md` - Updated with v2.0 architecture
- `README.md` - Complete rewrite for business users

#### Dependencies
- No new dependencies added (uses existing Flask, pandas)

### Migration Notes

#### For Existing Users
- **No Breaking Changes**: All existing functionality continues to work
- **New Features Available**: Hospital search and code lookup are new optional features
- **Enhanced Experience**: Code descriptions now appear automatically in results
- **Data Files**: Ensure `HCPCS/HCPC2026_JAN_ANWEB_12082025.txt` is present for code descriptions

#### For New Users
- Start with Code Lookup to find relevant codes for your products
- Use Hospital Search to identify high-volume facilities
- Use Doctor Search to identify high-volume physicians
- Create device categories to organize codes for your product portfolio

### Performance

- **Hospital Analytics**: Efficient aggregation using chunked processing
- **HCPCS Lookup**: Cached in memory for fast access
- **Code Descriptions**: Loaded once and cached per request
- **No Performance Impact**: New features don't slow down existing searches

### Known Limitations

- HCPCS code descriptions require `HCPCS/HCPC2026_JAN_ANWEB_12082025.txt` file
- System gracefully degrades if HCPCS file is missing (descriptions won't show)
- Hospital search requires codes (can't search all hospitals without codes)

---

## [1.1] - 2025-01-XX

### Added

#### Code Classification System
- **Device Category Management**: Create, edit, and delete device categories
- **Code Organization**: Add/remove codes to/from categories
- **Category-Based Search**: Select categories in Explorer to auto-populate codes
- **JSON Persistence**: Categories saved to `code_classifications.json`

#### Enhanced Features
- **Logging System**: Centralized logging for debugging
- **Enhanced Validation**: Better error messages for invalid inputs
- **Improved Documentation**: Comprehensive system documentation

### Changed

- **Enhanced Docstrings**: Detailed documentation for key functions
- **Better Error Handling**: More user-friendly error messages
- **Template Updates**: Improved form layout and hints

---

## [1.0] - 2025-01-XX

### Initial Release

#### Core Features
- **Code-Based Search**: Search physicians by HCPCS/CPT codes
- **State Filtering**: Filter results by state(s)
- **Minimum Services Filter**: Filter by procedure volume threshold
- **Hospital Affiliations**: Automatic display of physician hospital affiliations
- **CSV Export**: Export full results as CSV
- **Basic UI**: Functional search interface

#### Data Integration
- Physician billing data (`physHCPCS.csv`)
- Hospital affiliations (`Facility_Affiliation.csv`)
- Hospital metadata (`Hospital_General_Information.csv`)

---

## Version History Summary

- **v2.0** (Current): Complete redesign with hospital analytics and HCPCS intelligence
- **v1.1**: Code classification system for device companies
- **v1.0**: Initial release with core search functionality

---

**For detailed technical information, see `SYSTEM_DOCUMENTATION.md`.**
