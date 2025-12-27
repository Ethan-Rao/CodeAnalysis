# CMS Explorer - Complete Redesign Plan
## For Medical Device Companies

**Date:** 2025-01-XX  
**Version:** 2.0 Redesign

## Executive Summary

This document outlines a complete redesign of the CMS Explorer system to better serve medical device companies in identifying target customers (doctors and hospitals) who are likely to use their products. The redesign focuses on:

1. **Hospital-Level Analytics** - Usage statistics per hospital
2. **HCPCS Code Intelligence** - Rich code descriptions and lookup
3. **Medical Device Company Workflow** - Optimized for sales targeting
4. **Enhanced Search & Filtering** - More powerful query capabilities

## Current System Issues

1. **Search Bug** - Codes not returning results (fixed in this redesign)
2. **No Hospital-Level Stats** - Only doctor-level data
3. **Limited Code Information** - No descriptions or context
4. **Workflow Not Optimized** - Not tailored for device companies

## New System Architecture

### Core Components

#### 1. HCPCS Code Database (`cms_app/hcpcs_lookup.py`)
- Load and parse HCPCS 2026 data files
- Provide code descriptions (long/short)
- Code metadata (pricing indicators, coverage codes, etc.)
- Code search and autocomplete
- BETOS classification lookup
- Type of service codes

#### 2. Hospital Analytics Engine (`cms_app/hospital_analytics.py`)
- Aggregate procedure volumes by hospital
- Calculate hospital-level statistics:
  - Total procedures per code
  - Total Medicare payments
  - Number of physicians per hospital
  - Procedure trends
- Hospital ranking by volume
- Geographic distribution

#### 3. Enhanced Query System (`cms_app/enhanced_query.py`)
- Doctor search (existing, improved)
- **NEW:** Hospital search by codes
- **NEW:** Combined doctor + hospital views
- **NEW:** Territory analysis
- **NEW:** Market share calculations

#### 4. Medical Device Company Dashboard (`cms_app/templates/dashboard.html`)
- Overview of target markets
- Top hospitals by procedure volume
- Top physicians by procedure volume
- Geographic heat maps
- Code category performance

#### 5. Hospital Detail Pages (`cms_app/templates/hospital_detail.html`)
- Hospital profile
- Procedure volumes by code
- Affiliated physicians
- Historical trends
- Contact information

## Data Sources Integration

### HCPCS 2026 Files
- `HCPC2026_JAN_ANWEB_12082025.txt` - Main code database (fixed-width)
- `HCPC2026_recordlayout.txt` - Record layout specification
- `proc_notes_JAN2026.txt` - Processing notes
- `NOC codes_JAN2026.xlsx` - Not Otherwise Classified codes

**Integration:**
- Parse fixed-width format
- Load into searchable database/cache
- Provide API for code lookups
- Enrich search results with descriptions

### Existing CMS Data
- `physHCPCS.csv` - Physician billing data
- `Doctors_08_2025/Facility_Affiliation.csv` - Doctor-hospital links
- `hospitals_08_2025/Hospital_General_Information.csv` - Hospital metadata

## New Features

### 1. Hospital-Level Usage Statistics

**For each hospital, show:**
- Total procedures for selected codes
- Total Medicare payments
- Number of physicians performing procedures
- Average procedures per physician
- Procedure distribution across codes
- Year-over-year trends (if data available)

**Implementation:**
```python
def get_hospital_usage_stats(
    codes: list[str],
    states: list[str] | None = None,
    min_procedures: int | None = None
) -> pd.DataFrame:
    """
    Returns hospital-level statistics for given codes.
    Columns:
    - facility_id
    - hospital_name
    - city, state
    - total_procedures
    - total_payments
    - num_physicians
    - avg_procedures_per_physician
    - code_breakdown
    """
```

### 2. HCPCS Code Lookup & Descriptions

**Features:**
- Search codes by description
- Autocomplete in search forms
- Show full code details:
  - Long description
  - Short description
  - Pricing indicator
  - Coverage code
  - BETOS classification
  - Type of service
  - Effective/termination dates

**Implementation:**
```python
class HCPCSLookup:
    def search_codes(self, query: str) -> list[dict]
    def get_code_details(self, code: str) -> dict
    def get_codes_by_category(self, category: str) -> list[str]
    def autocomplete(self, prefix: str) -> list[str]
```

### 3. Enhanced Search Interface

**New Search Modes:**
1. **By Code(s)** - Existing, improved
2. **By Hospital** - Find hospitals using specific codes
3. **By Territory** - Geographic analysis
4. **By Device Category** - Use code classifications
5. **Combined View** - Doctors + Hospitals together

**New Filters:**
- Hospital type (acute care, ASC, etc.)
- Hospital size (bed count)
- Specialty filters
- Payment range filters
- Procedure volume ranges

### 4. Medical Device Company Dashboard

**Dashboard Sections:**
- **Market Overview**
  - Total market size (procedures, payments)
  - Top 10 hospitals by volume
  - Top 10 physicians by volume
  - Geographic distribution map

- **Target Lists**
  - High-volume hospitals
  - High-volume physicians
  - Emerging markets
  - Under-served areas

- **Analytics**
  - Market share by hospital
  - Market share by state
  - Growth trends
  - Competitive analysis

### 5. Hospital Detail Pages

**Hospital Profile:**
- Basic information (name, address, type)
- Procedure volumes by code
- Affiliated physicians (with volumes)
- Historical trends
- Contact information
- Quality metrics (if available)

## Implementation Phases

### Phase 1: Foundation (Week 1)
- [x] Fix search bug
- [ ] Create HCPCS lookup system
- [ ] Parse HCPCS 2026 data files
- [ ] Create hospital analytics engine
- [ ] Update data models

### Phase 2: Core Features (Week 2)
- [ ] Hospital-level query functions
- [ ] Enhanced search interface
- [ ] Hospital detail pages
- [ ] Dashboard layout
- [ ] Code lookup integration

### Phase 3: Advanced Features (Week 3)
- [ ] Territory analysis
- [ ] Market share calculations
- [ ] Geographic visualizations
- [ ] Export enhancements
- [ ] Performance optimization

### Phase 4: Polish & Testing (Week 4)
- [ ] UI/UX improvements
- [ ] Error handling
- [ ] Documentation
- [ ] Testing
- [ ] Deployment preparation

## Technical Architecture

### File Structure
```
cms_app/
├── hcpcs_lookup.py          # HCPCS code database
├── hospital_analytics.py     # Hospital statistics engine
├── enhanced_query.py         # Enhanced query functions
├── views.py                  # Updated routes
├── templates/
│   ├── dashboard.html        # Main dashboard
│   ├── hospital_detail.html  # Hospital profile
│   ├── search_enhanced.html  # Enhanced search
│   └── ...
└── static/
    └── js/
        └── dashboard.js      # Dashboard interactivity
```

### Data Flow

1. **User searches by codes**
   ↓
2. **System queries physician data** (existing)
   ↓
3. **System queries hospital data** (NEW)
   ↓
4. **System aggregates by hospital** (NEW)
   ↓
5. **System enriches with HCPCS descriptions** (NEW)
   ↓
6. **System displays combined results**

### Performance Considerations

- Cache HCPCS lookup data (small, static)
- Cache hospital aggregations
- Use chunked processing for large queries
- Index hospital-physician relationships
- Pre-compute common aggregations

## User Workflows

### Workflow 1: Find Target Hospitals
1. Enter device codes or select category
2. View hospital-level statistics
3. Filter by state, volume, etc.
4. Export hospital list
5. View hospital details
6. Identify key physicians at each hospital

### Workflow 2: Territory Analysis
1. Select geographic region
2. View market overview
3. Identify high-opportunity hospitals
4. Analyze competition
5. Plan sales strategy

### Workflow 3: Code Research
1. Search for codes by description
2. View code details
3. See usage statistics
4. Identify related codes
5. Add to device category

## Success Metrics

- **Search Performance:** < 3 seconds for typical queries
- **Data Accuracy:** 100% match with source data
- **User Satisfaction:** Easy to find target customers
- **Export Functionality:** Complete data export
- **Hospital Coverage:** All hospitals with procedure data

## Next Steps

1. Review and approve this plan
2. Begin Phase 1 implementation
3. Test with sample queries
4. Iterate based on feedback
5. Deploy to production

---

**Note:** This is a living document and will be updated as implementation progresses.


